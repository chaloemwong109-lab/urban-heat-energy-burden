import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

SILVER_SURVEY = Path("data/silver/clean_household_survey.parquet")
GOLD_DIR = Path("data/gold")
GOLD_DIM_DISTRICT = GOLD_DIR / "dim_district.parquet"
GOLD_FACT_DISTRICT = GOLD_DIR / "fact_district_energy_heat_yearly.parquet"


def build_survey_star_schema() -> None:
    logger.info("=== Starting Survey Gold Modeling (Star Schema & District Join) ===")

    # 1. โหลดข้อมูล Silver (Survey) และ Gold เดิม (District)
    df_survey = pd.read_parquet(SILVER_SURVEY)
    df_dim_dist = pd.read_parquet(GOLD_DIM_DISTRICT)
    df_fact_dist = pd.read_parquet(GOLD_FACT_DISTRICT)

    logger.info(f"Loaded survey: {len(df_survey)} rows, {len(df_survey.columns)} cols")

    # 2. สร้าง Dimension 1: ลักษณะที่อยู่อาศัย (สำหรับตอบ Q1)
    housing_cols = [
        "household_code",
        "community_name",
        "housing_type",
        "wall_material",
        "roof_material",
        "has_ceiling",
        "has_insulation",
        "ventilation_quality",
        "surrounding_shade",
    ]
    dim_housing = df_survey[housing_cols].drop_duplicates(subset=["household_code"]).copy()

    # 3. สร้าง Dimension 2: เศรษฐกิจครัวเรือน พฤติกรรมการรับมือ และอุปสรรค (สำหรับตอบ Q2)
    socio_cols = [
        "household_code",
        "household_size",
        "income_stability",
        "monthly_income_range",
        "monthly_expense_range",
        "has_savings",
        "debt_range",
        "normal_elec_bill_range",
        "summer_elec_bill_range",
        "summer_elec_increase_level",
        "reduced_elec_due_to_cost",
        "has_fan",
        "has_ac",
        "cope_use_fan",
        "cope_use_ac",
        "cope_open_windows",
        "barrier_no_budget",
        "barrier_renting_no_right",
        "barrier_expensive_material",
    ]
    dim_socio = df_survey[socio_cols].drop_duplicates(subset=["household_code"]).copy()

    # 4. เตรียมข้อมูลเขตหลักสี่จาก Gold เดิมเพื่อนำมา Join
    # (พื้นที่เขตหลักสี่ อยู่ในความดูแลของ กฟน. เขตบางเขน หากไม่มีชื่อ "หลักสี่" ตรงๆ จะใช้ "บางเขน" แทน)
    target_district = "หลักสี่" if "หลักสี่" in df_dim_dist["district"].values else "บางเขน"
    dist_info = df_dim_dist[df_dim_dist["district"] == target_district].head(1).copy()

    if dist_info.empty:
        # Fallback กรณีชื่อเขตไม่ตรง ให้ใช้แถวแรกพร้อมแจ้งเตือน
        logger.warning("ไม่พบเขตหลักสี่หรือบางเขนใน dim_district ใช้ข้อมูลเขตแรกแทนชั่วคราว")
        dist_info = df_dim_dist.head(1).copy()
        target_district = dist_info["district"].iloc[0]

    # ดึงข้อมูลค่าไฟและอุณหภูมิปีล่าสุดของเขตนั้นจาก fact_district_energy_heat_yearly
    dist_yearly = (
        df_fact_dist[df_fact_dist["district"] == target_district]
        .sort_values("year", ascending=False)
        .head(1)
    )

    # 5. สร้าง Fact Table หลัก: fact_household_energy_heat
    fact_cols = [
        "household_code",
        "district_id",
        "district_name",
        "interview_month",
        "summer_heat_severity",
        "impact_insomnia",
        "impact_discomfort",
        "impact_headache_fatigue",
        "impact_higher_elec_bill",
        "est_monthly_income_thb",
        "est_normal_elec_thb",
        "est_summer_elec_thb",
        "summer_energy_burden_pct",
    ]
    fact_hh = df_survey[fact_cols].copy()

    # เพิ่มตัวชี้วัดรวมผลกระทบสุขภาพ (0-3 อาการ) เพื่อให้คนที่ 3 วิเคราะห์ Q1 ง่ายขึ้น
    fact_hh["health_impact_count"] = (
        fact_hh["impact_insomnia"]
        + fact_hh["impact_discomfort"]
        + fact_hh["impact_headache_fatigue"]
    )

    # Join ข้อมูลบริบทระดับเขต (MEA District & Latest Yearly Heat/Energy)
    fact_hh["mea_district"] = target_district
    fact_hh = fact_hh.merge(
        dist_info[["district", "district_en", "lat", "lon", "station_id"]],
        left_on="mea_district",
        right_on="district",
        how="left",
    ).drop(columns=["district"])

    if not dist_yearly.empty:
        latest = dist_yearly.iloc[0]
        fact_hh["district_ref_year"] = int(latest["year"])
        # ดึงคอลัมน์อุณหภูมิ/ค่าไฟเท่าที่มีอยู่ใน fact_district_energy_heat_yearly
        for col in ["mean_temp_c", "cdd", "consumption_mkwh", "total_consumption_mkwh"]:
            if col in dist_yearly.columns:
                fact_hh[f"district_{col}"] = latest[col]

    # 6. บันทึกตาราง Star Schema ทั้ง 3 ไฟล์ลง data/gold/
    out_housing = GOLD_DIR / "dim_household_housing.parquet"
    out_socio = GOLD_DIR / "dim_household_socioeconomic.parquet"
    out_fact = GOLD_DIR / "fact_household_energy_heat.parquet"

    dim_housing.to_parquet(out_housing, index=False)
    dim_socio.to_parquet(out_socio, index=False)
    fact_hh.to_parquet(out_fact, index=False)

    logger.info(f"Saved {out_housing} ({len(dim_housing)} rows)")
    logger.info(f"Saved {out_socio} ({len(dim_socio)} rows)")
    logger.info(f"Saved {out_fact} ({len(fact_hh)} rows, joined with MEA district: {target_district})")
    logger.info("=== Survey Gold Modeling Finished Successfully ===")


if __name__ == "__main__":
    build_survey_star_schema()