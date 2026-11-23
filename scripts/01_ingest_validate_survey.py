import logging
import os
import pandas as pd
import pandera.pandas as pa
from pandera import Check, Column, DataFrameSchema

# ตั้งค่า Logging ให้เขียนลง quality_report.log เหมือนท่อเดิม
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/quality_report.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

RAW_PATH = "data/bronze/ThaiCI_Household_Questionaire_anonymized.xlsx"
SILVER_PATH = "data/silver/clean_household_survey.parquet"

# 1. แมปชื่อคอลัมน์ภาษาไทย (ใช้เลข Index หรือชื่อคอลัมน์จริง) -> ชื่อคอลัมน์ภาษาอังกฤษใน Silver
SELECTED_INDICES = {
    0: "household_code",
    1: "community_name",
    4: "interview_month",
    12: "income_stability",
    13: "monthly_income_range",
    14: "monthly_expense_range",
    24: "has_savings",
    25: "debt_range",
    26: "household_size",
    61: "housing_type",
    63: "wall_material",
    64: "roof_material",
    66: "has_ceiling",
    67: "has_insulation",
    68: "ventilation_quality",
    69: "surrounding_shade",
    82: "barrier_no_budget",
    84: "barrier_renting_no_right",
    86: "barrier_expensive_material",
    115: "summer_heat_severity",
    120: "impact_insomnia",
    121: "impact_discomfort",
    122: "impact_headache_fatigue",
    125: "impact_higher_elec_bill",
    130: "cope_use_fan",
    131: "cope_use_ac",
    133: "cope_open_windows",
    225: "normal_elec_bill_range",
    226: "summer_elec_bill_range",
    227: "summer_elec_increase_level",
    231: "has_fan",
    232: "has_ac",
    249: "reduced_elec_due_to_cost",
}

# ฟังก์ชันแปลงช่วงรายได้และค่าไฟเป็นค่าประมาณการตัวเลข (บาท/เดือน) เพื่อให้คำนวณ Energy Burden % ได้
INCOME_MAP = {
    "ต่ำกว่า 5,000 บาท": 4000.0,
    "5,001–10,000 บาท": 7500.0,
    "10,001–20,000 บาท": 15000.0,
    "20,001–50,000 บาท": 35000.0,
    "มากกว่า 50,000 บาท": 60000.0,
}

ELEC_BILL_MAP = {
    "ต่ำกว่า 500 บาท": 400.0,
    "500–1,000 บาท": 750.0,
    "1,001–2,000 บาท": 1500.0,
    "2,001–3,000 บาท": 2500.0,
    "มากกว่า 3,000 บาท": 3500.0,
}


def ingest_and_clean():
  logging.info("Starting Survey Ingestion & Cleaning...")
  df_raw = pd.read_excel(RAW_PATH, sheet_name=0)
  logging.info(f"Loaded raw survey data: {df_raw.shape[0]} rows, {df_raw.shape[1]} columns")

  # เลือกเฉพาะคอลัมน์ที่ต้องการตาม Index และเปลี่ยนชื่อ
  df = df_raw.iloc[:, list(SELECTED_INDICES.keys())].copy()
  df.columns = list(SELECTED_INDICES.values())

  # เพิ่ม district_id = 1041 (รหัสเขตหลักสี่ กทม. เพื่อใช้ Join กับตาราง Gold เดิม)
  df["district_id"] = 1041
  df["district_name"] = "หลักสี่"

  # ทำความสะอาดช่องว่างในข้อความ (Strip whitespace)
  str_cols = df.select_dtypes(include="object").columns
  for c in str_cols:
    df[c] = df[c].astype(str).str.strip().replace({"nan": None, "None": None})

  # แปลงคอลัมน์ตัวเลข (0/1) ให้เป็น int และเติม 0 หากเป็นค่าว่าง
  binary_cols = [
      "barrier_no_budget",
      "barrier_renting_no_right",
      "barrier_expensive_material",
      "impact_insomnia",
      "impact_discomfort",
      "impact_headache_fatigue",
      "impact_higher_elec_bill",
      "cope_use_fan",
      "cope_use_ac",
      "cope_open_windows",
      "has_fan",
      "has_ac",
  ]
  for c in binary_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

  # คำนวณค่าประมาณการรายได้และค่าไฟ (บาท) + สัดส่วนภาระค่าไฟหน้าร้อนต่อรายได้ (%)
  df["est_monthly_income_thb"] = df["monthly_income_range"].map(INCOME_MAP)
  df["est_normal_elec_thb"] = df["normal_elec_bill_range"].map(ELEC_BILL_MAP)
  df["est_summer_elec_thb"] = df["summer_elec_bill_range"].map(ELEC_BILL_MAP)
  df["summer_energy_burden_pct"] = (
      (df["est_summer_elec_thb"] / df["est_monthly_income_thb"]) * 100
  ).round(2)

  return df


# 2. กำหนดกฎ Pandera Schema ตรวจสอบคุณภาพข้อมูล (Data Quality Gate)
survey_schema = DataFrameSchema(
    columns={
        "household_code": Column(
            str, checks=Check.str_startswith("HH-"), unique=True, nullable=False
        ),
        "district_id": Column(int, checks=Check.equal_to(1041), nullable=False),
        "community_name": Column(str, nullable=False),
        "roof_material": Column(str, nullable=True),
        "ventilation_quality": Column(str, nullable=True),
        "surrounding_shade": Column(str, nullable=True),
        "summer_heat_severity": Column(str, nullable=True),
        "monthly_income_range": Column(str, nullable=True),
        "est_monthly_income_thb": Column(
            float, checks=Check.greater_than(0), nullable=True
        ),
        "est_summer_elec_thb": Column(
            float, checks=Check.greater_than_or_equal_to(0), nullable=True
        ),
        "has_ac": Column(int, checks=Check.isin([0, 1]), nullable=False),
        "has_fan": Column(int, checks=Check.isin([0, 1]), nullable=False),
    },
    strict=False,  # อนุญาตให้คอลัมน์อื่นๆ ที่คลีนแล้วผ่านลง Silver ได้
)


if __name__ == "__main__":
  try:
    df_clean = ingest_and_clean()
    validated_df = survey_schema.validate(df_clean, lazy=True)

    os.makedirs("data/silver", exist_ok=True)
    validated_df.to_parquet(SILVER_PATH, index=False)

    logging.info(
        f"✅ Pandera Validation PASSED! Saved {len(validated_df)} clean household records to {SILVER_PATH}"
    )
    print("\n--- สรุปตัวอย่างข้อมูลสะอาดใน Silver Zone ---")
    print(
        validated_df[[
            "household_code",
            "roof_material",
            "summer_heat_severity",
            "monthly_income_range",
            "summer_energy_burden_pct",
        ]].head()
    )
  except pa.errors.SchemaErrors as err:
    logging.error(f"❌ Pandera Validation FAILED:\n{err.failure_cases}")
    raise