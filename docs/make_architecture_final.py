from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_PATH = Path("docs/architecture_final_s3.png")


def draw_box(ax, x, y, w, h, title, body, fc, ec, title_color="#111827", body_color="#374151", title_size=10, body_size=8.2):
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.015,rounding_size=0.02",
        facecolor=fc,
        edgecolor=ec,
        linewidth=1.8,
        zorder=3,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h - 0.032,
        title,
        ha="center",
        va="top",
        fontsize=title_size,
        fontweight="bold",
        color=title_color,
        zorder=4,
    )
    ax.text(
        x + w / 2,
        y + h - 0.072,
        body,
        ha="center",
        va="top",
        fontsize=body_size,
        color=body_color,
        linespacing=1.35,
        zorder=4,
    )


def draw_arrow(ax, x1, y1, x2, y2, label="", color="#4B5563", rad=0.0, lx_offset=0.0, ly_offset=0.018):
    arrow = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle="-|>,head_length=7,head_width=4.5",
        color=color,
        linewidth=1.7,
        zorder=5,
    )
    ax.add_patch(arrow)
    if label:
        mx, my = (x1 + x2) / 2 + lx_offset, (y1 + y2) / 2 + ly_offset
        ax.text(
            mx,
            my,
            label,
            ha="center",
            va="center",
            fontsize=7.8,
            fontweight="bold",
            color="#1F2937",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85),
            zorder=6,
        )


def build_diagram():
    fig, ax = plt.subplots(figsize=(16, 9), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#F9FAFB")

    # Main Title
    ax.text(
        0.5,
        0.965,
        "Urban Heat & Energy Burden — Final Cloud-Integrated Medallion Architecture",
        ha="center",
        va="top",
        fontsize=15,
        fontweight="bold",
        color="#111827",
    )
    ax.text(
        0.5,
        0.93,
        "End-to-End Reproducible Pipeline (python scripts/run_pipeline.py)  |  Local Medallion Data Lake + Amazon S3 Cloud Sync",
        ha="center",
        va="top",
        fontsize=9.5,
        color="#4B5563",
    )

    # Container: Local Medallion Pipeline
    medallion_bg = FancyBboxPatch(
        (0.215, 0.14),
        0.495,
        0.74,
        boxstyle="round,pad=0.015,rounding_size=0.025",
        facecolor="#FFFFFF",
        edgecolor="#CBD5E1",
        linewidth=1.5,
        linestyle="--",
        zorder=1,
    )
    ax.add_patch(medallion_bg)
    ax.text(
        0.4625,
        0.865,
        "Local Medallion Data Pipeline  (Orchestrated by scripts/run_pipeline.py)",
        ha="center",
        va="top",
        fontsize=10,
        fontweight="bold",
        color="#334155",
        zorder=2,
    )

    # Container: AWS Cloud & Downstream
    cloud_bg = FancyBboxPatch(
        (0.745, 0.14),
        0.235,
        0.74,
        boxstyle="round,pad=0.015,rounding_size=0.025",
        facecolor="#FFFBEB",
        edgecolor="#F59E0B",
        linewidth=1.5,
        linestyle="--",
        zorder=1,
    )
    ax.add_patch(cloud_bg)
    ax.text(
        0.8625,
        0.865,
        "AWS Cloud & Analytics",
        ha="center",
        va="top",
        fontsize=10,
        fontweight="bold",
        color="#B45309",
        zorder=2,
    )

    # --- Column 1: Data Sources ---
    draw_box(
        ax, 0.02, 0.65, 0.165, 0.17,
        "1. Open-Meteo API",
        "Daily BKK Temperature\n(2016–Present)\nbkk_temperature.csv",
        fc="#EFF6FF", ec="#3B82F6",
    )
    draw_box(
        ax, 0.02, 0.42, 0.165, 0.17,
        "2. MEA Electricity",
        "18 MEA Districts\nYearly Sales (2559–2568)\nmea_electricity.csv",
        fc="#EFF6FF", ec="#3B82F6",
    )
    draw_box(
        ax, 0.02, 0.19, 0.165, 0.17,
        "3. ThaiCI Survey",
        "88 Households (Lak Si)\n343 Raw Columns\nQuestionaire.xlsx",
        fc="#EFF6FF", ec="#3B82F6",
    )

    # --- Column 2: Bronze Zone ---
    draw_box(
        ax, 0.235, 0.24, 0.135, 0.56,
        "BRONZE ZONE",
        "Raw Immutable Data\n(data/bronze/)\n\n• 01_ingest.py\n• bkk_temperature.csv\n• mea_electricity.csv\n• ref_mea_districts.csv\n• ThaiCI_Survey.xlsx\n• _manifest.json\n  (SHA-256 Checksum)",
        fc="#FEF3C7", ec="#D97706", title_color="#92400E",
    )

    # --- Column 3: Silver Zone ---
    draw_box(
        ax, 0.395, 0.24, 0.135, 0.56,
        "SILVER ZONE",
        "Cleaned + Quality Gate\n(data/silver/ .parquet)\n\n• 02_validate_clean.py\n• 01_ingest_validate\n  _survey.py\n• Pandera Schema\n  (100% Pass, 88 HH)\n• Midpoint Imputation\n• district_id = 1041",
        fc="#F1F5F9", ec="#64748B", title_color="#334155",
    )

    # --- Column 4: Gold Zone ---
    draw_box(
        ax, 0.555, 0.24, 0.135, 0.56,
        "GOLD ZONE",
        "Star Schema & Joins\n(data/gold/ .parquet)\n\n• 03_transform.py\n  - dim_district\n  - fact_district_yearly\n• 03b_transform_survey\n  - dim_hh_housing (Q1)\n  - dim_hh_socio (Q2)\n  - fact_hh_energy_heat\n  (Joined w/ Bang Khen)",
        fc="#FEF9C3", ec="#CA8A04", title_color="#854D0E",
    )

    # --- Column 5: AWS S3 + Downstream ---
    draw_box(
        ax, 0.765, 0.57, 0.195, 0.25,
        "Amazon S3 Data Lake",
        "s3://urban-heat-energy-\nburden-datalake-2026/\n\n• bronze/  (6 files)\n• silver/  (3 files)\n• gold/    (9 files)\nSynced via 04_upload_s3.py",
        fc="#FFEDD5", ec="#EA580C", title_color="#9A3412",
    )
    draw_box(
        ax, 0.765, 0.37, 0.195, 0.15,
        "AWS Glue / Lambda",
        "Cloud Catalog & Compute\nServerless Query / ETL\n(Connected to S3 Lake)",
        fc="#FCE7F3", ec="#DB2777", title_color="#9D174D",
    )
    draw_box(
        ax, 0.765, 0.17, 0.195, 0.15,
        "Analytics & Report",
        "Q1: Housing vs Heat/Health\nQ2: Income vs Energy Burden\nCharts, Tables & Final PDF",
        fc="#DCFCE7", ec="#16A34A", title_color="#166534",
    )

    # --- Arrows ---
    # Sources -> Bronze
    draw_arrow(ax, 0.185, 0.735, 0.235, 0.68)
    draw_arrow(ax, 0.185, 0.505, 0.235, 0.52)
    draw_arrow(ax, 0.185, 0.275, 0.235, 0.34)

    # Bronze -> Silver -> Gold
    draw_arrow(ax, 0.370, 0.52, 0.395, 0.52)
    draw_arrow(ax, 0.530, 0.52, 0.555, 0.52)

    # Gold / Local Lake -> S3
    draw_arrow(ax, 0.690, 0.695, 0.765, 0.695, label="boto3", ly_offset=0.025)

    # S3 -> AWS Glue/Lambda
    draw_arrow(ax, 0.8625, 0.57, 0.8625, 0.52)

    # Gold & Glue -> Analytics
    draw_arrow(ax, 0.8625, 0.37, 0.8625, 0.32)
    draw_arrow(ax, 0.690, 0.245, 0.765, 0.245, label="Parquet", ly_offset=0.025)

    # Footer note
    ax.text(
        0.5,
        0.06,
        "Note: 04_upload_s3.py supports Smart Skip — automatically syncs 18 files when AWS credentials are present, or skips gracefully in local-only mode.",
        ha="center",
        va="center",
        fontsize=8.5,
        style="italic",
        color="#6B7280",
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUT_PATH, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved Final Architecture Diagram -> {OUT_PATH}")


if __name__ == "__main__":
    build_diagram()