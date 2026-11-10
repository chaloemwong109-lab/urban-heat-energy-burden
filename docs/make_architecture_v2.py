"""
Run:  python docs/make_architecture_v2.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "architecture_v2.png"

# palette (one hue per layer, light fill + darker edge)
C = {
    "source": ("#FDECEA", "#C0392B"),
    "ingest": ("#EAF2FB", "#2E6DB4"),
    "bronze": ("#F6E7D8", "#A0522D"),
    "silver": ("#EEF0F2", "#6B7785"),
    "gold":   ("#FFF6D6", "#B8860B"),
    "xform":  ("#E8F6EF", "#1E8449"),
    "serve":  ("#F3E9F7", "#7D3C98"),
    "ops":    ("#F4F4F4", "#555555"),
}
INK = "#1F2933"
MUTED = "#5F6B76"

fig, ax = plt.subplots(figsize=(22, 11.5), dpi=150)
ax.set_xlim(0, 100)
ax.set_ylim(0, 55)
ax.axis("off")
fig.patch.set_facecolor("white")


def panel(x, y, w, h, title, layer, subtitle=None):
    fill, edge = C[layer]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=0.8",
                                fc=fill, ec=edge, lw=1.6, alpha=0.55))
    ax.text(x + 0.6, y + h - 1.2, title, fontsize=12, fontweight="bold", color=edge, va="top")
    if subtitle:
        ax.text(x + 0.6, y + h - 2.9, subtitle, fontsize=8.5, color=MUTED, va="top", style="italic")


def box(x, y, w, h, title, lines=(), layer="ingest", dashed=False):
    fill, edge = C[layer]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15,rounding_size=0.5",
                                fc="white", ec=edge, lw=1.3, ls=(0, (4, 3)) if dashed else "-"))
    ax.text(x + 0.45, y + h - 0.55, title, fontsize=9.3, fontweight="bold",
            color=MUTED if dashed else INK, va="top")
    for i, line in enumerate(lines):
        ax.text(x + 0.45, y + h - 2.05 - i * 1.25, line, fontsize=7.9, color=MUTED, va="top")


def arrow(x1, y1, x2, y2, color="#34495E", label=None, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=16,
                                 lw=1.6, color=color, ls=ls, shrinkA=2, shrinkB=2))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.6, label, fontsize=7.8, color=color,
                ha="center", va="bottom")


# ---------------------------------------------------------------- title
ax.text(0.5, 54.6, "Urban Heat & Energy Burden — Data Architecture v2 (Checkpoint, as implemented)",
        fontsize=17, fontweight="bold", color=INK, va="top")
ax.text(0.5, 52.4, "Local-first Medallion architecture: Python scripts + Parquet files + DuckDB (in-process) + GeoPandas. "
        "Solid = running now · Dashed = planned for Final.", fontsize=10, color=MUTED, va="top")

TOP, BOT = 49.0, 9.5  # vertical extent of the layer panels
H = TOP - BOT

# ---------------------------------------------------------------- 1. sources
panel(0.5, BOT, 14.5, H, "1 · Data Sources", "source")
box(1.1, 37.0, 13.3, 6.2, "Open-Meteo Archive API", ["Daily mean temp 2 m (ERA5)", "Bangkok cell · 2016 → 2026", "JSON/CSV over HTTPS"], "source")
box(1.1, 29.6, 13.3, 6.2, "MEA open statistics (CSV)", ["Units sold, million kWh", "18 MEA districts", "yearly 2559–2568 B.E. + monthly"], "source")
box(1.1, 22.2, 13.3, 6.2, "District reference (curated)", ["TH/EN name, province,", "approx. lat/lon per district", "data/reference/mea_districts.csv"], "source")
box(1.1, 10.4, 13.3, 10.6, "Planned for Final", ["• Happy Home / SoVI survey", "   (income, energy cost, roof)", "• NSO SES income by area", "• LST satellite / more grid", "   cells for spatial variation"], "source", dashed=True)

# ---------------------------------------------------------------- 2. ingestion
panel(16.0, BOT, 12.8, H, "2 · Ingestion", "ingest", "Bronze = immutable raw copy")
box(16.6, 37.0, 11.6, 6.2, "00_fetch_data.py", ["API / open-data download", "→ data/raw/ (landing zone)"], "ingest")
box(16.6, 18.0, 11.6, 17.6, "01_ingest.py", [
    "resolve: --fetch API → landing", "   → reference → keep bronze",
    "structural check (header", "   signature, non-empty)",
    "sha256 + bytes + lines", "   → _manifest.json (lineage)",
    "changed file → archive old", "   copy to bronze/_history/",
    "atomic write · idempotent", "station metadata extract"], "ingest")

# ---------------------------------------------------------------- 3. bronze
panel(29.8, BOT, 12.4, H, "3 · Bronze zone", "bronze", "data/bronze/  (raw CSV)")
box(30.4, 37.0, 11.2, 6.2, "bkk_temperature.csv", ["3,964 daily rows", "+ Open-Meteo metadata row"], "bronze")
box(30.4, 29.6, 11.2, 6.2, "mea_electricity.csv", ["wide, Thai headers, B.E.,", "comma numbers, notes rows"], "bronze")
box(30.4, 22.2, 11.2, 6.2, "ref_* lookups", ["ref_mea_districts.csv", "ref_temperature_stations.csv", "(tiny lookups: checked in 03)"], "bronze")
box(30.4, 14.8, 11.2, 6.2, "_manifest.json", ["origin, url, sha256,", "ingested_at, status"], "bronze")

# ---------------------------------------------------------------- 4. validation -> silver
panel(43.2, BOT, 13.6, H, "4 · Validate → Silver", "silver", "data/silver/  (typed Parquet)")
box(43.8, 28.0, 12.4, 15.2, "02_validate_clean.py", [
    "Pandera schemas (lazy):", "  temp 15–48 °C, year 2000–2030,", "  month 1–12, kWh > 0, not-null",
    "outlier filter + logging", "wide → long (unpivot districts)", "B.E. → C.E., strip commas",
    "→ logs/quality_report.log"], "silver")
box(43.8, 20.4, 12.4, 6.2, "clean_temperature.parquet", ["date, year, month, avg_temp", "3,964 rows · PASSED"], "silver")
box(43.8, 12.8, 12.4, 6.2, "clean_electricity.parquet", ["year, district, consumption", "180 rows (18 × 10 yrs) · PASSED"], "silver")

# ---------------------------------------------------------------- 5. transform
panel(57.8, BOT, 13.8, H, "5 · Transform", "xform", "03_transform.py")
box(58.4, 35.4, 12.6, 7.8, "Spatial join (GeoPandas)", ["ref_* lookups (Bronze) →", "district points → nearest temp", "cell: sjoin_nearest, UTM 47N,", "keep distance_km"], "xform")
box(58.4, 25.6, 12.6, 8.4, "Temporal (DuckDB)", ["daily → monthly / yearly:", "mean, hottest month, hot days", "(≥30 °C), CDD base 24 °C,", "completeness ≥ 95 %"], "xform")
box(58.4, 17.0, 12.6, 7.2, "Integration join (DuckDB)", ["elec JOIN district (spatial key)", "JOIN heat (station_id + year)", "YoY, index, share, COVID flag"], "xform")
box(58.4, 10.4, 12.6, 5.4, "Integration checks", ["key match · no dup keys · row", "count kept · no null metrics"], "xform")

# ---------------------------------------------------------------- 6. gold
panel(72.6, BOT, 14.2, H, "6 · Gold zone", "gold", "data/gold/  (curated Parquet)")
box(73.2, 35.4, 13.0, 7.8, "dim_district", [".parquet + .geojson (map)", "18 districts · station_id,", "distance_km"], "gold")
box(73.2, 26.6, 13.0, 7.4, "agg_temperature_", ["monthly (131) / yearly (11)", "per station, completeness"], "gold")
box(73.2, 17.0, 13.0, 8.0, "fact_district_energy_", ["heat_yearly.parquet", "district × year · 180 rows", "kWh + temp, CDD, hot days"], "gold")
box(73.2, 10.4, 13.0, 5.6, "agg_year_energy_heat", ["city total / year · 10 rows", "kWh, CDD, YoY, COVID flag"], "gold")

# ---------------------------------------------------------------- 7. serving
panel(87.8, BOT, 11.7, H, "7 · Serving", "serve")
box(88.4, 32.0, 10.5, 11.2, "eda_checkpoint.ipynb", ["DuckDB SQL / pandas", "on Gold Parquet", "plots: CDD vs kWh,", "district trends"], "serve")
box(88.4, 21.0, 10.5, 9.6, "Answers (Proposal)", ["Q1/Q2: heat ↔ electricity", "use, by district & year", "+ limitation notes"], "serve")
box(88.4, 11.4, 10.5, 8.2, "Final (planned)", ["map of districts,", "survey-level burden", "(cost ÷ income)"], "serve", dashed=True)

# ---------------------------------------------------------------- arrows (main flow)
for (x1, x2, y) in [(14.4, 16.6, 40.1), (14.4, 16.6, 32.7), (14.4, 16.6, 25.3)]:
    arrow(x1, y, x2, y if y == 40.1 else 26.8)
arrow(22.4, 37.0, 22.4, 35.6, label="")
arrow(28.2, 26.8, 30.4, 32.0, label="")
arrow(28.2, 26.8, 30.4, 25.3)
arrow(28.2, 26.8, 30.4, 39.5)
arrow(28.2, 22.0, 30.4, 17.9)
arrow(41.6, 40.1, 43.8, 38.0)
arrow(41.6, 32.7, 43.8, 33.0)
arrow(50.0, 28.0, 50.0, 26.6)
arrow(56.2, 23.5, 58.4, 29.8)
arrow(56.2, 15.9, 58.4, 20.6)
arrow(64.7, 35.4, 64.7, 34.0)
arrow(64.7, 25.6, 64.7, 24.2)
arrow(64.7, 17.0, 64.7, 15.8)
arrow(71.0, 39.3, 73.2, 39.3)   # spatial    -> dim_district
arrow(71.0, 29.8, 73.2, 29.8)   # temporal   -> agg_temperature
arrow(71.0, 20.6, 73.2, 21.0)   # integration-> fact
arrow(71.0, 19.0, 73.2, 13.2)   # integration-> agg_year
arrow(86.2, 21.0, 88.4, 33.0)
arrow(86.2, 13.2, 88.4, 32.4)
arrow(93.6, 32.0, 93.6, 30.6)

# ---------------------------------------------------------------- orchestration & logs
fill, edge = C["ops"]
ax.add_patch(FancyBboxPatch((0.5, 1.0), 99.0, 7.0, boxstyle="round,pad=0.2,rounding_size=0.8",
                            fc=fill, ec=edge, lw=1.4))
ax.text(1.2, 7.2, "Orchestration & observability", fontsize=11.5, fontweight="bold", color=edge, va="top")
ax.text(1.2, 5.2, "run_pipeline.py  →  01_ingest.py  →  02_validate_clean.py  →  03_transform.py"
        "   (sequential; stops on the first non-zero exit code)", fontsize=9.5, color=INK, va="top")
ax.text(1.2, 3.1, "logs/: pipeline_run_<timestamp>.log · ingest.log · quality_report.log · transform.log"
        "      |      env: requirements.txt + .venv      |      repo: GitHub (README = how to run)",
        fontsize=9.0, color=MUTED, va="top")

fig.savefig(OUT, bbox_inches="tight", facecolor="white")
print(f"saved {OUT}")
