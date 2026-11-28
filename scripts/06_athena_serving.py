"""
06_athena_serving.py — Cloud Serving layer (Glue Data Catalog + Amazon Athena)
Owner: ปุณยนุช แซ่แจ้ง (Member 4 — Cloud Compute)

Waits for the Glue crawler (started by the Lambda) to finish, then runs every
cloud/athena/*.sql query with Athena (serverless SQL on the Parquet files in S3)
and saves each result as evidence:

  local : docs/cloud_evidence/<query>.csv
  S3    : s3://<bucket>/athena-results/   (Athena's own output)

Like 04_upload_s3.py it skips quietly when no AWS credentials are present, so the
local pipeline keeps working without a lab token.

Usage
  export S3_BUCKET_NAME=<your-bucket>
  python scripts/06_athena_serving.py
"""

import csv
import logging
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

BASE_DIR = Path(__file__).resolve().parent.parent
SQL_DIR = BASE_DIR / "cloud" / "athena"
OUT_DIR = BASE_DIR / "docs" / "cloud_evidence"
LOG_DIR = BASE_DIR / "logs"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

REGION = os.getenv("AWS_REGION", "us-east-1")
BUCKET = os.getenv("S3_BUCKET_NAME")
GLUE_DB = "urban_heat_energy"
CRAWLER = "uheb-warehouse-crawler"
EXPECTED_TABLES = {
    "fact_district_energy_heat_yearly", "agg_year_energy_heat", "agg_temperature_monthly",
    "agg_temperature_yearly", "dim_district", "fact_household_energy_heat",
    "dim_household_housing", "dim_household_socioeconomic",
    "clean_household_survey", "clean_temperature", "clean_electricity",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "cloud_serving.log", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("AthenaServing")


def wait_for_crawler(glue, timeout_s: int = 600) -> None:
    start = time.time()
    while True:
        c = glue.get_crawler(Name=CRAWLER)["Crawler"]
        if c["State"] == "READY":
            last = c.get("LastCrawl", {})
            if last.get("Status") not in (None, "SUCCEEDED"):
                raise RuntimeError(f"Last crawl {last.get('Status')}: {last.get('ErrorMessage')}")
            log.info(f"[Glue] crawler READY (last crawl: {last.get('Status', 'never')})")
            return
        if time.time() - start > timeout_s:
            raise TimeoutError("Glue crawler did not finish in time")
        log.info(f"[Glue] crawler {c['State']} ... waiting")
        time.sleep(15)


def check_catalog(glue) -> None:
    tables = {t["Name"] for page in glue.get_paginator("get_tables").paginate(DatabaseName=GLUE_DB)
              for t in page["TableList"]}
    missing = EXPECTED_TABLES - tables
    log.info(f"[Glue] {len(tables)} table(s) in catalog '{GLUE_DB}'")
    if missing:
        raise RuntimeError(f"Tables missing from the catalog: {sorted(missing)} "
                           "(run 04_upload_s3.py, or 05_setup_aws_cloud.py --backfill)")


def run_query(athena, sql: str) -> tuple[list[str], list[list[str]], dict]:
    qid = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": GLUE_DB},
        ResultConfiguration={"OutputLocation": f"s3://{BUCKET}/athena-results/"},
    )["QueryExecutionId"]
    while True:
        ex = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        state = ex["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Athena {state}: {ex['Status'].get('StateChangeReason')}")

    rows = []
    for page in athena.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        for r in page["ResultSet"]["Rows"]:
            rows.append([c.get("VarCharValue", "") for c in r["Data"]])
    header, data = rows[0], rows[1:]
    stats = ex["Statistics"]
    return header, data, {"query_id": qid,
                          "scanned_kb": round(stats.get("DataScannedInBytes", 0) / 1024, 1),
                          "runtime_ms": stats.get("TotalExecutionTimeInMillis")}


def main() -> int:
    if not BUCKET:
        log.warning("S3_BUCKET_NAME not set - skipping Athena serving (local mode)")
        return 0
    session = boto3.Session(region_name=REGION)
    try:
        session.client("sts").get_caller_identity()
    except (NoCredentialsError, ClientError):
        log.warning("No valid AWS credentials - skipping Athena serving (local mode)")
        return 0

    glue, athena = session.client("glue"), session.client("athena")
    log.info(f"=== Athena serving | db {GLUE_DB} | s3://{BUCKET} ===")
    try:
        wait_for_crawler(glue)
        check_catalog(glue)
        for sql_file in sorted(SQL_DIR.glob("*.sql")):
            header, data, stats = run_query(athena, sql_file.read_text(encoding="utf-8"))
            out = OUT_DIR / f"{sql_file.stem}.csv"
            with out.open("w", encoding="utf-8-sig", newline="") as f:  # BOM: Thai opens in Excel
                csv.writer(f).writerows([header, *data])
            log.info(f"[Athena] {sql_file.name}: {len(data)} row(s), scanned {stats['scanned_kb']} KB, "
                     f"{stats['runtime_ms']} ms -> {out.relative_to(BASE_DIR)}")
    except (ClientError, RuntimeError, TimeoutError) as e:
        log.error(f"=== Athena serving FAILED: {e} ===\n")
        return 1
    log.info("=== Athena serving finished ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
