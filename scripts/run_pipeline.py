import subprocess
import logging
import os
from datetime import datetime

# 1. ตั้งค่าระบบ Logging บันทึกผลลงโฟลเดอร์ logs
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"pipeline_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler() # แสดงผลออกหน้าจอ Terminal ด้วย
    ]
)

# 2. กำหนดลำดับไฟล์สคริปต์ที่ต้องรัน (อ้างอิงจากโฟลเดอร์ scripts/)
scripts_to_run = [
    "scripts/01_ingest.py",
    "scripts/02_validate_clean.py",
    "scripts/03_transform.py"
]

def run_pipeline():
    logging.info("🚀 Starting Data Pipeline for 'Heat & Energy Burden'")
    
    for script in scripts_to_run:
        logging.info(f"▶️ Executing: {script}")
        try:
            # สั่งรันไฟล์ Python
            result = subprocess.run(["python", script], check=True, capture_output=True, text=True)
            if result.stdout:
                logging.info(f"Output:\n{result.stdout.strip()}")
            logging.info(f"✅ Successfully finished: {script}")
            
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Error occurred while running {script}")
            logging.error(f"Error Details: {e.stderr.strip()}")
            logging.error("🛑 Pipeline stopped due to error.")
            break # หยุดรันไฟล์ถัดไปทันทีถ้ามี Error
            
    logging.info("🎉 Pipeline execution completed.")

if __name__ == "__main__":
    run_pipeline()