import argparse
import csv
import hashlib
import json
import logging
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"              # landing zone (00_fetch_data.py output)
REFERENCE_DIR = BASE_DIR / "data" / "reference"  # small curated lookup tables (in git)
BRONZE_DIR = BASE_DIR / "data" / "bronze"
HISTORY_DIR = BRONZE_DIR / "_history"
MANIFEST_PATH = BRONZE_DIR / "_manifest.json"
LOG_DIR = BASE_DIR / "logs"

for d in (RAW_DIR, BRONZE_DIR, HISTORY_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging -> logs/ingest.log + stdout (stdout is captured by run_pipeline.py)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "ingest.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("Ingest")

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------
# Bangkok point used by the team's temperature series (Open-Meteo / ERA5 grid cell)
BKK_LAT, BKK_LON = 13.7434, 100.4959
TEMP_START_DATE = "2016-01-01"  # aligned with the first MEA year (2559 B.E.)


def open_meteo_url() -> str:
    # The archive API lags real time by a few days, so stop 5 days before today.
    end = (date.today() - timedelta(days=5)).isoformat()
    return (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={BKK_LAT}&longitude={BKK_LON}"
        f"&start_date={TEMP_START_DATE}&end_date={end}"
        "&daily=temperature_2m_mean&timezone=GMT&format=csv"
    )


SOURCES = [
    {
        "name": "bkk_temperature",
        "file": "bkk_temperature.csv",
        "kind": "api",
        "provider": "Open-Meteo Historical Weather API (ERA5 reanalysis)",
        "url_builder": open_meteo_url,
        "signature": "temperature_2m_mean",
        "description": "Daily mean 2 m air temperature, Bangkok grid cell, 2016-present",
    },
    {
        "name": "mea_electricity",
        "file": "mea_electricity.csv",
        "kind": "file",
        "provider": "Metropolitan Electricity Authority (MEA) open statistics",
        "url_builder": None,  # manual download from MEA; place the file in data/raw/
        "signature": "การไฟฟ้านครหลวงเขต",
        "description": "Units sold (million kWh) per MEA district, yearly 2559-2568 B.E. + monthly",
    },
    {
        "name": "ref_mea_districts",
        "file": "ref_mea_districts.csv",
        "kind": "reference",
        "reference_file": "mea_districts.csv",
        "provider": "Team-curated lookup (manual geocode of MEA district service areas)",
        "url_builder": None,
        "signature": "district,district_en",
        "description": "MEA district names (TH/EN), province, approx. lat/lon for spatial join",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Manifest is corrupted; starting a new one.")
    return {"sources": {}}


def save_manifest(manifest: dict) -> None:
    tmp = MANIFEST_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(MANIFEST_PATH)


def structural_check(source: dict, data: bytes) -> None:
    """Reject files that are clearly not the expected source (not a quality check)."""
    if not data.strip():
        raise ValueError(f"[{source['name']}] file is empty")
    head = data[:8192].decode("utf-8-sig", errors="replace")
    if source["signature"] not in head:
        raise ValueError(
            f"[{source['name']}] expected header text '{source['signature']}' not found "
            "- the file format may have changed or the download failed"
        )


def download(url: str) -> bytes:
    logger.info(f"    GET {url}")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def resolve_source(source: dict, fetch: bool) -> tuple[bytes, str, str | None]:
    """Return (content, origin, url) following the resolution order in the docstring."""
    landing = RAW_DIR / source["file"]
    bronze = BRONZE_DIR / source["file"]
    url = source["url_builder"]() if source["url_builder"] else None

    if fetch and url:
        return download(url), "api", url
    if landing.exists():
        return landing.read_bytes(), f"landing:{landing.relative_to(BASE_DIR)}", None
    if source["kind"] == "reference":
        ref = REFERENCE_DIR / source["reference_file"]
        if not ref.exists():
            raise FileNotFoundError(f"Reference file missing: {ref}")
        return ref.read_bytes(), f"reference:{ref.relative_to(BASE_DIR)}", None
    if bronze.exists():
        return bronze.read_bytes(), "retained", None
    if url:
        return download(url), "api", url
    raise FileNotFoundError(
        f"[{source['name']}] no input found. Put '{source['file']}' in data/raw/ "
        "(run 00_fetch_data.py or download it manually)."
    )


def write_bronze(source: dict, data: bytes, digest: str) -> str:
    """Write content to Bronze, archiving the previous version if it differs."""
    bronze = BRONZE_DIR / source["file"]
    if bronze.exists():
        old = bronze.read_bytes()
        old_digest = sha256_bytes(old)
        if old_digest == digest:
            return "unchanged"
        hist_dir = HISTORY_DIR / source["name"]
        hist_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived = hist_dir / f"{stamp}_{old_digest[:8]}{bronze.suffix}"
        shutil.copy2(bronze, archived)
        logger.info(f"    previous version archived -> {archived.relative_to(BASE_DIR)}")
        status = "updated"
    else:
        status = "created"
    tmp = bronze.with_suffix(bronze.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(bronze)  # atomic swap: readers never see a half-written file
    return status


def extract_temperature_station(data: bytes) -> dict:
    """Open-Meteo CSV starts with a metadata row: latitude,longitude,elevation,..."""
    lines = data.decode("utf-8-sig").splitlines()
    header, values = next(csv.reader([lines[0]])), next(csv.reader([lines[1]]))
    meta = dict(zip(header, values))
    return {
        "station_id": "OM_BKK_01",
        "station_name": "Open-Meteo ERA5 grid cell - Bangkok",
        "lat": float(meta["latitude"]),
        "lon": float(meta["longitude"]),
        "elevation_m": float(meta["elevation"]),
        "source_file": "bkk_temperature.csv",
    }


def write_station_reference(station: dict) -> None:
    out = BRONZE_DIR / "ref_temperature_stations.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(station.keys()))
        writer.writeheader()
        writer.writerow(station)
    logger.info(f"    station metadata -> {out.relative_to(BASE_DIR)} "
                f"(lat={station['lat']}, lon={station['lon']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest raw sources into the Bronze zone")
    parser.add_argument("--fetch", action="store_true",
                        help="download fresh data from APIs instead of using local files")
    args = parser.parse_args()

    logger.info("=== Starting Ingestion (Raw -> Bronze) ===")
    manifest = load_manifest()
    manifest["last_run_at"] = now_iso()
    failures = 0

    for source in SOURCES:
        name = source["name"]
        logger.info(f"--- [{name}] {source['description']}")
        try:
            data, origin, url = resolve_source(source, args.fetch)
            structural_check(source, data)
            digest = sha256_bytes(data)
            status = write_bronze(source, data, digest)

            previous = manifest["sources"].get(name, {})
            ingested_at = (previous.get("ingested_at")
                           if status == "unchanged" and previous.get("sha256") == digest
                           else now_iso())
            manifest["sources"][name] = {
                "file": f"data/bronze/{source['file']}",
                "kind": source["kind"],
                "provider": source["provider"],
                "origin": origin,
                "url": url,
                "sha256": digest,
                "bytes": len(data),
                "lines": data.count(b"\n"),
                "ingested_at": ingested_at,
                "last_checked_at": now_iso(),
                "status": status,
            }
            logger.info(f"    {status.upper()} | origin={origin} | {len(data):,} bytes | sha256={digest[:12]}")

            if name == "bkk_temperature":
                write_station_reference(extract_temperature_station(data))

        except Exception as exc:  # keep going so the log shows every failing source
            failures += 1
            logger.error(f"    FAILED: {exc}")
            manifest["sources"].setdefault(name, {})["status"] = f"failed: {exc}"

    save_manifest(manifest)
    logger.info(f"Manifest saved -> {MANIFEST_PATH.relative_to(BASE_DIR)}")

    if failures:
        logger.error(f"=== Ingestion finished with {failures} failed source(s) ===\n")
        return 1
    logger.info("=== Ingestion Stage Finished Successfully ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
