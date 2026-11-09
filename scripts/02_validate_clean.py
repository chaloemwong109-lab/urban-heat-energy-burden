import sys
import logging
from pathlib import Path
import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema
from pandera.errors import SchemaErrors

# 1. จัดการ Path ให้เป็นมาตรฐานสากล
BASE_DIR = Path(__file__).resolve().parent.parent
BRONZE_DIR = BASE_DIR / "data" / "bronze"
SILVER_DIR = BASE_DIR / "data" / "silver"
LOG_DIR = BASE_DIR / "logs"

SILVER_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 2. ตั้งค่าระบบ Logging บันทึกลง logs/quality_report.log
log_file_path = LOG_DIR / "quality_report.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DataQuality")

# 3. กำหนด Pandera Schema สำหรับข้อมูลที่จะเก็บลง Silver Zone
temperature_schema = DataFrameSchema(
    columns={
        "year": Column(pa.Int, Check.in_range(2000, 2030), nullable=False),
        "month": Column(pa.Int, Check.in_range(1, 12), nullable=False),
        "date": Column(pa.String, nullable=False),
        "avg_temp": Column(pa.Float, Check.in_range(15.0, 48.0), nullable=True),
    },
    coerce=True
)

electricity_schema = DataFrameSchema(
    columns={
        "year": Column(pa.Int, Check.in_range(2000, 2030), nullable=False),
        "district": Column(pa.String, nullable=False),
        "consumption_million_kwh": Column(pa.Float, Check.greater_than(0), nullable=False),
    },
    coerce=True
)

def clean_temperature_data(raw_path: Path) -> pd.DataFrame:
    logger.info("--- [START] Validating & Cleaning Temperature Data ---")
    # ข้าม 3 บรรทัดแรกที่เป็น metadata ของ Open-Meteo
    df = pd.read_csv(raw_path, skiprows=3)
    
    # ดึงคอลัมน์อุณหภูมิและเปลี่ยนชื่อให้กระชับ
    temp_col = [c for c in df.columns if "temperature" in c.lower()][0]
    df = df.rename(columns={"time": "date", temp_col: "avg_temp"})
    
    # แปลง Format วันที่และสกัด year, month
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    
    # ตรวจสอบและกรอง Outliers (เกณฑ์ 15 - 48 องศาเซลเซียส)
    outliers = (df["avg_temp"] < 15.0) | (df["avg_temp"] > 48.0)
    if outliers.any():
        logger.warning(f"[Temperature] Found {outliers.sum()} outliers out of 15-48 C range. Filtering out.")
        df = df[~outliers]

    # ทำ Data Validation ด้วย Pandera
    try:
        validated_df = temperature_schema.validate(df, lazy=True)
        logger.info(f"[Temperature] Pandera Validation PASSED ({len(validated_df)} rows).")
        return validated_df
    except SchemaErrors as err:
        logger.error(f"[Temperature] Pandera Validation FAILED:\n{err.failure_cases[['column', 'check', 'failure_case']]}")
        raise err

def clean_electricity_data(raw_path: Path) -> pd.DataFrame:
    logger.info("--- [START] Validating & Cleaning MEA Electricity Data ---")
    # ข้าม 3 บรรทัดแรกและใช้บรรทัดที่ 4 เป็น Header
    df = pd.read_csv(raw_path, skiprows=3, encoding="utf-8")
    
    # คอลัมน์แรกคือ ปี
    first_col = df.columns[0]
    df = df.rename(columns={first_col: "year"})
    
    # ตัดคอลัมน์ที่ไม่ใช่ข้อมูลเขตออก
    cols_to_drop = [c for c in df.columns if "หน่วยขายทั้งหมด" in c or "หักไฟ" in c or "Unnamed" in c or str(c).strip() == ""]
    df = df.drop(columns=cols_to_drop)

    # กรองและแปลงปี พ.ศ. เป็น ค.ศ.
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    df["year"] = df["year"].apply(lambda y: y - 543 if y > 2400 else y)

    # Unpivot จาก Wide format เป็น Long format เพื่อให้พร้อมทำ Data Integration
    melted_df = df.melt(id_vars=["year"], var_name="district", value_name="consumption_million_kwh")
    melted_df["district"] = melted_df["district"].str.strip()

    # ลบ Comma ช่องว่าง และแปลงเป็นตัวเลขทศนิยม
    melted_df["consumption_million_kwh"] = (
        melted_df["consumption_million_kwh"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    melted_df["consumption_million_kwh"] = pd.to_numeric(melted_df["consumption_million_kwh"], errors="coerce")
    
    # ลบค่า Missing Values และตัดค่าไฟที่ <= 0
    clean_df = melted_df.dropna(subset=["consumption_million_kwh"]).copy()
    clean_df = clean_df[clean_df["consumption_million_kwh"] > 0]

    # ทำ Data Validation ด้วย Pandera
    try:
        validated_df = electricity_schema.validate(clean_df, lazy=True)
        logger.info(f"[Electricity] Pandera Validation PASSED ({len(validated_df)} rows).")
        return validated_df
    except SchemaErrors as err:
        logger.error(f"[Electricity] Pandera Validation FAILED:\n{err.failure_cases[['column', 'check', 'failure_case']]}")
        raise err

def main():
    logger.info("=== Starting Data Validation & Cleansing Pipeline ===")
    
    temp_raw = BRONZE_DIR / "bkk_temperature.csv"
    elec_raw = BRONZE_DIR / "mea_electricity.csv"

    if not temp_raw.exists() or not elec_raw.exists():
        logger.error("Raw CSV files missing in data/bronze/.")
        return

    # รันการทำความสะอาดและตรวจสอบ
    clean_temp = clean_temperature_data(temp_raw)
    clean_elec = clean_electricity_data(elec_raw)

    # บันทึกลง Silver Zone เป็น Parquet
    out_temp = SILVER_DIR / "clean_temperature.parquet"
    out_elec = SILVER_DIR / "clean_electricity.parquet"

    clean_temp.to_parquet(out_temp, index=False)
    clean_elec.to_parquet(out_elec, index=False)

    logger.info(f"Saved: {out_temp}")
    logger.info(f"Saved: {out_elec}")
    logger.info("=== Validation & Cleaning Stage Finished Successfully ===\n")

if __name__ == "__main__":
    main()