from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_PATH = Path("docs/architecture_v4_final.png")


def draw_lane(ax, x, y, w, h, title, subtitle, fc, ec, title_color):
    lane = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.004,rounding_size=0.012",
        facecolor=fc,
        edgecolor=ec,
        linewidth=1.6,
        zorder=1,
    )
    ax.add_patch(lane)
    ax.text(
        x + 0.008,
        y + h - 0.018,
        title,
        ha="left",
        va="top",
        fontsize=9.2,
        fontweight="bold",
        color=title_color,
        zorder=2,
    )
    ax.text(
        x + 0.008,
        y + h - 0.043,
        subtitle,
        ha="left",
        va="top",
        fontsize=7.0,
        color="#4B5563",
        zorder=2,
    )


def draw_card(ax, x, y, w, h, title, lines, ec="#94A3B8", badge=None):
    card = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.003,rounding_size=0.008",
        facecolor="#FFFFFF",
        edgecolor=ec,
        linewidth=1.1,
        zorder=3,
    )
    ax.add_patch(card)

    # Card title
    ax.text(
        x + 0.006,
        y + h - 0.011,
        title,
        ha="left",
        va="top",
        fontsize=7.6,
        fontweight="bold",
        color="#111827",
        zorder=4,
    )

    # Card body
    body_text = "\n".join(lines)
    ax.text(
        x + 0.006,
        y + h - 0.032,
        body_text,
        ha="left",
        va="top",
        fontsize=6.7,
        color="#374151",
        linespacing=1.32,
        zorder=4,
    )

    # Optional NEW v4 badge
    if badge:
        badge_w = 0.034
        badge_h = 0.018
        bx = x + w - badge_w - 0.003
        by = y + h - 0.008
        pill = FancyBboxPatch(
            (bx, by),
            badge_w,
            badge_h,
            boxstyle="round,pad=0.002,rounding_size=0.006",
            facecolor="#F97316",
            edgecolor="none",
            zorder=5,
        )
        ax.add_patch(pill)
        ax.text(
            bx + badge_w / 2,
            by + badge_h / 2,
            badge,
            ha="center",
            va="center",
            fontsize=6.0,
            fontweight="bold",
            color="#FFFFFF",
            zorder=6,
        )


def draw_arrow(ax, x1, y1, x2, y2, color="#475569", ls="-", rad=0.0, label=None, ly_off=0.012):
    arrow = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle="-|>,head_length=5.5,head_width=3.5",
        color=color,
        linewidth=1.4,
        linestyle=ls,
        zorder=5,
    )
    ax.add_patch(arrow)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 + ly_off
        ax.text(
            mx,
            my,
            label,
            ha="center",
            va="center",
            fontsize=6.5,
            fontweight="bold",
            color="#334155",
            bbox=dict(boxstyle="round,pad=0.18", fc="#FFFFFF", ec="none", alpha=0.9),
            zorder=6,
        )


def build_architecture_v4():
    fig, ax = plt.subplots(figsize=(22, 11.5), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    # Header
    ax.text(
        0.015,
        0.968,
        "Urban Heat & Energy Burden — Data Architecture v4 (Final Cloud-Integrated)",
        ha="left",
        va="top",
        fontsize=17,
        fontweight="bold",
        color="#111827",
    )
    ax.text(
        0.015,
        0.932,
        "Medallion Architecture: Python + Parquet + DuckDB + GeoPandas + Pandera + Amazon S3 Cloud Sync  |  Orange Badge (NEW v4) = Star Schema & AWS Cloud Upgrade",
        ha="left",
        va="top",
        fontsize=9.5,
        color="#4B5563",
    )

    # Column geometry (8 lanes)
    n_cols = 8
    margin_x = 0.015
    gap_x = 0.012
    col_w = (1.0 - 2 * margin_x - (n_cols - 1) * gap_x) / n_cols
    col_y = 0.145
    col_h = 0.755
    xs = [margin_x + i * (col_w + gap_x) for i in range(n_cols)]

    lanes_spec = [
        ("1 · Data Sources", "Raw external & field data", "#FEF2F2", "#EF4444", "#B91C1C"),
        ("2 · Ingestion", "Fetch & landing scripts", "#EFF6FF", "#3B82F6", "#1D4ED8"),
        ("3 · Bronze Zone", "data/bronze/ (Raw + Hash)", "#FFFBEB", "#D97706", "#B45309"),
        ("4 · Validate -> Silver", "data/silver/ (Parquet)", "#F5F3FF", "#8B5CF6", "#6D28D9"),
        ("5 · Transform", "Spatial, Temporal & Joins", "#ECFDF5", "#10B981", "#047857"),
        ("6 · Gold Zone", "data/gold/ (Star Schema)", "#FEFCE8", "#CA8A04", "#854D0E"),
        ("7 · AWS Cloud Lake", "Amazon S3 + Cloud Compute", "#FFF7ED", "#EA580C", "#C2410C"),
        ("8 · Serving & Report", "Q1/Q2 Analytics & PDF", "#F8FAFC", "#64748B", "#334155"),
    ]

    for i, (title, sub, fc, ec, tc) in enumerate(lanes_spec):
        draw_lane(ax, xs[i], col_y, col_w, col_h, title, sub, fc, ec, tc)

    # Helper to stack cards top-down inside a lane
    def place_cards(col_idx, cards_data, ec):
        cx = xs[col_idx] + 0.006
        cw = col_w - 0.012
        curr_y = col_y + col_h - 0.072
        gap_y = 0.015
        centers = []
        for c_title, c_lines, c_h, c_badge in cards_data:
            cy = curr_y - c_h
            draw_card(ax, cx, cy, cw, c_h, c_title, c_lines, ec=ec, badge=c_badge)
            centers.append(cy + c_h / 2)
            curr_y = cy - gap_y
        return centers

    # Col 1: Data Sources
    place_cards(0, [
        ("Open-Meteo Archive API", [
            "Daily mean temp 2m (ERA5)",
            "Bangkok 2016–2026",
            "Format: JSON / CSV",
        ], 0.135, None),
        ("MEA Open Statistics", [
            "Electricity sold (million kWh)",
            "18 MEA districts",
            "2559–2568 B.E. (yearly)",
        ], 0.135, None),
        ("District Reference", [
            "Curated TH/EN names",
            "Province & approx. lat/lon",
            "data/reference/mea_districts",
        ], 0.135, None),
        ("ThaiCI Household Survey", [
            "88 households (Lak Si)",
            "Khlong Prem Prachakon",
            "343 raw columns (.xlsx)",
        ], 0.135, None),
    ], ec="#FCA5A5")

    # Col 2: Ingestion
    place_cards(1, [
        ("01_ingest.py", [
            "Retain/fetch -> Bronze",
            "Structural check + bytes",
            "SHA-256 hash verification",
            "Atomic write _manifest.json",
            "Station metadata export",
        ], 0.255, None),
        ("01_ingest_validate_survey.py", [
            "Read ThaiCI .xlsx (openpyxl)",
            "Select 33 core variables",
            "Add key: district_id = 1041",
            "Midpoint imputation (income",
            "& electric bill ranges)",
            "Compute Energy Burden %",
        ], 0.285, None),
    ], ec="#93C5FD")

    # Col 3: Bronze Zone
    place_cards(2, [
        ("bkk_temperature.csv", [
            "3,964 daily rows",
            "Open-Meteo station meta",
        ], 0.108, None),
        ("mea_electricity.csv", [
            "18 districts x 10 years",
            "Wide -> long prep source",
        ], 0.108, None),
        ("ref_* lookups", [
            "ref_mea_districts.csv",
            "ref_temperature_stations.csv",
        ], 0.108, None),
        ("ThaiCI_...anonymized.xlsx", [
            "Raw household survey",
            "88 households, 343 cols",
        ], 0.108, None),
        ("_manifest.json", [
            "Origin, SHA-256 checksum,",
            "bytes, status (lineage)",
        ], 0.108, None),
    ], ec="#FCD34D")

    # Col 4: Validate -> Silver
    place_cards(3, [
        ("02_validate_clean.py", [
            "Pandera schemas (lazy=True)",
            "Range, null & type checks",
            "B.E. -> C.E. year convert",
        ], 0.125, None),
        ("clean_temperature.parquet", [
            "3,964 rows · PASSED",
            "Typed daily temp series",
        ], 0.102, None),
        ("clean_electricity.parquet", [
            "180 rows (18x10) · PASSED",
            "Clean district consumption",
        ], 0.102, None),
        ("Pandera Quality Gate", [
            "Survey: unique 'HH-*',",
            "district_id=1041, {0,1}",
            "88/88 rows PASSED (100%)",
        ], 0.125, None),
        ("clean_household_survey", [
            ".parquet (88 rows, 39 cols)",
            "Ready for Star Schema",
        ], 0.102, None),
    ], ec="#C4B5FD")

    # Col 5: Transform
    place_cards(4, [
        ("03_transform.py (District)", [
            "GeoPandas sjoin_nearest",
            "  (district -> temp station)",
            "DuckDB temporal features:",
            "  CDD base 24°C, hot days",
            "Join elec x dist x heat",
            "  (180/180 rows matched)",
        ], 0.235, None),
        ("03b_transform_survey_gold", [
            "Build Household Star Schema",
            "  for Q1 & Q2 analytics",
            "Compute health_impact_count",
            "  (0–3 symptom score)",
            "JOIN Lak Si (1041) ->",
            "  MEA Bang Khen context",
        ], 0.245, "NEW v4"),
        ("Integration Checks", [
            "Key match, 0 null metrics",
            "Row counts kept (88 & 180)",
        ], 0.105, None),
    ], ec="#6EE7B7")

    # Col 6: Gold Zone
    place_cards(5, [
        ("dim_district + agg_temp_*", [
            ".parquet & .geojson (18)",
            "monthly (131) / yearly (11)",
        ], 0.105, None),
        ("fact_district_energy_heat", [
            "180 rows (dist x yr) +",
            "agg_year_energy_heat (10)",
        ], 0.105, None),
        ("dim_household_housing", [
            "88 rows · Q1 Dimension",
            "roof, ceiling, insulation,",
            "ventilation, shade",
        ], 0.125, "NEW v4"),
        ("dim_household_socioecon", [
            "88 rows · Q2 Dimension",
            "income, debt, coping &",
            "renovation barriers",
        ], 0.125, "NEW v4"),
        ("fact_household_energy_heat", [
            "88 rows · Central Fact",
            "heat, health, burden % +",
            "MEA Bang Khen ref metrics",
        ], 0.125, "NEW v4"),
    ], ec="#FDE047")

    # Col 7: AWS Cloud Lake
    place_cards(6, [
        ("04_upload_s3.py (boto3)", [
            "Sync bronze/, silver/, gold/",
            "Smart Skip: bypasses S3",
            "gracefully if no AWS token",
            "(local-friendly pipeline)",
        ], 0.185, "NEW v4"),
        ("Amazon S3 Data Lake", [
            "Bucket (us-east-1):",
            "urban-heat-energy-burden-",
            "datalake-2026/",
            "• bronze/ (6 files)",
            "• silver/ (3 files)",
            "• gold/   (9 files) = 18",
        ], 0.225, "NEW v4"),
        ("AWS Glue / Lambda", [
            "Cloud Data Catalog & ETL",
            "Serverless compute linked",
            "to S3 Medallion zones",
            "(Member 4 integration)",
        ], 0.175, "NEW v4"),
    ], ec="#FDBA74")

    # Col 8: Serving & Report
    place_cards(7, [
        ("eda_checkpoint.ipynb", [
            "DuckDB SQL / pandas",
            "CDD vs kWh trends",
            "r = 0.667 (0.811 ex-COVID)",
        ], 0.155, None),
        ("Q1 & Q2 Analytics", [
            "Q1: Housing -> Heat/Health",
            "Q2: Income -> Burden %",
            "Boxplots, Bar Charts & CLD",
            "(Member 3 evidence)",
        ], 0.195, None),
        ("Final Report (PDF)", [
            "Problem & Architecture v4",
            "Quality Gate & Trade-offs",
            "Findings, Limitations &",
            "Responsible AI Use",
        ], 0.195, None),
    ], ec="#CBD5E1")

    # Inter-column arrows (clean horizontal flow)
    arrow_ys = [0.68, 0.48, 0.28]
    for i in range(n_cols - 1):
        x1 = xs[i] + col_w
        x2 = xs[i + 1]
        if i == 5:  # Gold -> AWS S3
            draw_arrow(ax, x1, 0.72, x2, 0.72, color="#EA580C", label="boto3", ly_off=0.016)
            draw_arrow(ax, x1, 0.50, x2, 0.50, color="#EA580C")
        elif i == 6:  # AWS -> Serving
            draw_arrow(ax, x1, 0.50, x2, 0.50, color="#475569")
            draw_arrow(ax, x1, 0.28, x2, 0.28, color="#475569")
        else:
            for ay in arrow_ys:
                draw_arrow(ax, x1, ay, x2, ay, color="#64748B")

    # Direct dashed line: Local Gold Parquet -> Serving (Member 3 local mode)
    draw_arrow(
        ax,
        xs[5] + col_w / 2,
        col_y,
        xs[7] + col_w / 2,
        col_y,
        color="#64748B",
        ls="--",
        rad=0.14,
        label="Local Gold Parquet (No AWS Token Required for Member 3)",
        ly_off=-0.022,
    )

    # Bottom Bar: Orchestration & Observability
    orch = FancyBboxPatch(
        (0.015, 0.022),
        0.970,
        0.095,
        boxstyle="round,pad=0.004,rounding_size=0.010",
        facecolor="#F8FAFC",
        edgecolor="#94A3B8",
        linewidth=1.4,
        zorder=2,
    )
    ax.add_patch(orch)
    ax.text(
        0.025,
        0.104,
        "Orchestration, Reproducibility & Observability",
        ha="left",
        va="top",
        fontsize=9.2,
        fontweight="bold",
        color="#1E293B",
        zorder=3,
    )
    ax.text(
        0.025,
        0.076,
        "Pipeline (1-Command):  python scripts/run_pipeline.py  ->  01_ingest.py  ->  01_ingest_validate_survey.py  ->  02_validate_clean.py  ->  03_transform.py  ->  03b_transform_survey_gold.py  ->  04_upload_s3.py",
        ha="left",
        va="top",
        fontsize=7.6,
        fontweight="bold",
        color="#0F172A",
        zorder=3,
    )
    ax.text(
        0.025,
        0.048,
        "Logs: logs/pipeline_run_<timestamp>.log | ingest.log | quality_report.log | transform.log     ||     Env: requirements.txt (boto3, openpyxl, pandera, duckdb, geopandas) + venv     ||     Cloud: AWS S3 (us-east-1)",
        ha="left",
        va="top",
        fontsize=7.3,
        color="#475569",
        zorder=3,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT_PATH, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved Final Architecture Diagram v4 -> {OUT_PATH}")


if __name__ == "__main__":
    build_architecture_v4()