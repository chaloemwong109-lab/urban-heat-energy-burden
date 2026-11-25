import logging
import os
from pathlib import Path
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "urban-heat-energy-burden-datalake-2026")
LAYERS = ["bronze", "silver", "gold"]
DATA_DIR = Path("data")


def upload_datalake_to_s3() -> None:
    # ตรวจสอบ AWS Credentials ก่อนเริ่มอัปโหลด
    session = boto3.Session()
    if session.get_credentials() is None:
        logger.warning(
            "ไม่พบ AWS Credentials ในเครื่อง — ข้ามขั้นตอนการอัปโหลดขึ้น Amazon S3 (รันโหมด Local เท่านั้น)"
        )
        return

    logger.info(f"=== Starting Upload Data Lake to s3://{S3_BUCKET_NAME}/ ===")
    s3_client = session.client("s3")

    uploaded_count = 0
    for layer in LAYERS:
        layer_dir = DATA_DIR / layer
        if not layer_dir.exists():
            logger.warning(f"Skip missing directory: {layer_dir}")
            continue

        for file_path in layer_dir.rglob("*"):
            if file_path.is_file() and file_path.name != ".gitkeep":
                s3_key = f"{layer}/{file_path.relative_to(layer_dir).as_posix()}"
                try:
                    s3_client.upload_file(str(file_path), S3_BUCKET_NAME, s3_key)
                    logger.info(f"Uploaded -> s3://{S3_BUCKET_NAME}/{s3_key}")
                    uploaded_count += 1
                except NoCredentialsError:
                    logger.warning("ไม่พบ AWS Credentials — ข้ามการอัปโหลดขึ้น S3")
                    return
                except ClientError as e:
                    logger.error(f"อัปโหลดไม่สำเร็จ ({s3_key}): {e}")
                    raise

    logger.info(f"=== Upload Finished: {uploaded_count} files synced to S3 ===")


if __name__ == "__main__":
    upload_datalake_to_s3()