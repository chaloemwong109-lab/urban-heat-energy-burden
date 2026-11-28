"""
05_setup_aws_cloud.py — Cloud Compute set-up (S3 + Lambda + Glue + Athena)

"""

import argparse
import io
import json
import logging
import os
import sys
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

BASE_DIR = Path(__file__).resolve().parent.parent
LAMBDA_SRC = BASE_DIR / "cloud" / "lambda" / "lake_organizer" / "handler.py"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

REGION = os.getenv("AWS_REGION", "us-east-1")
BUCKET = os.getenv("S3_BUCKET_NAME")
ROLE_NAME = os.getenv("LAB_ROLE_NAME", "LabRole")
GLUE_DB = "urban_heat_energy"
CRAWLER = "uheb-warehouse-crawler"
FUNCTION = "uheb-lake-organizer"
WAREHOUSE = "warehouse"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "cloud_setup.log", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("CloudSetup")


def ensure_bucket(s3) -> None:
    try:
        s3.head_bucket(Bucket=BUCKET)
        log.info(f"[S3] bucket exists: s3://{BUCKET}")
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
            raise  # 403 = the name belongs to someone else's account
        kwargs = {} if REGION == "us-east-1" else {
            "CreateBucketConfiguration": {"LocationConstraint": REGION}}
        s3.create_bucket(Bucket=BUCKET, **kwargs)
        s3.put_public_access_block(Bucket=BUCKET, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True,
            "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
        log.info(f"[S3] bucket created (private): s3://{BUCKET}")


def ensure_glue(glue, role_arn: str) -> None:
    try:
        glue.create_database(DatabaseInput={
            "Name": GLUE_DB,
            "Description": "CS341 Urban Heat & Energy Burden - curated silver/gold tables"})
        log.info(f"[Glue] database created: {GLUE_DB}")
    except glue.exceptions.AlreadyExistsException:
        log.info(f"[Glue] database exists: {GLUE_DB}")

    crawler = {
        "Name": CRAWLER,
        "Role": role_arn,
        "DatabaseName": GLUE_DB,
        "Description": "One table per folder under warehouse/silver and warehouse/gold",
        "Targets": {"S3Targets": [{"Path": f"s3://{BUCKET}/{WAREHOUSE}/{layer}/"}
                                  for layer in ("silver", "gold")]},
        "SchemaChangePolicy": {"UpdateBehavior": "UPDATE_IN_DATABASE",
                               "DeleteBehavior": "DEPRECATE_IN_DATABASE"},
        # s3://bucket(1)/warehouse(2)/gold(3)/<table>(4)/ -> force one table per folder,
        # so tables with similar columns are never merged into one partitioned table
        "Configuration": json.dumps({"Version": 1.0,
                                     "Grouping": {"TableLevelConfiguration": 4}}),
    }
    try:
        glue.create_crawler(**crawler)
        log.info(f"[Glue] crawler created: {CRAWLER}")
    except glue.exceptions.AlreadyExistsException:
        glue.update_crawler(**crawler)
        log.info(f"[Glue] crawler updated: {CRAWLER}")


def lambda_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(LAMBDA_SRC, arcname="handler.py")
    return buf.getvalue()


def ensure_lambda(lam, role_arn: str) -> str:
    config = {
        "Role": role_arn,
        "Handler": "handler.handler",
        "Runtime": "python3.12",
        "Timeout": 60,
        "MemorySize": 128,
        "Description": "Organise silver/gold Parquet into table folders and refresh Glue catalog",
        "Environment": {"Variables": {"CRAWLER_NAME": CRAWLER, "WAREHOUSE_PREFIX": WAREHOUSE}},
    }
    try:
        fn = lam.create_function(FunctionName=FUNCTION, Code={"ZipFile": lambda_zip()}, **config)
        log.info(f"[Lambda] function created: {FUNCTION}")
    except lam.exceptions.ResourceConflictException:
        lam.update_function_code(FunctionName=FUNCTION, ZipFile=lambda_zip())
        lam.get_waiter("function_updated_v2").wait(FunctionName=FUNCTION)
        fn = lam.update_function_configuration(FunctionName=FUNCTION, **config)
        log.info(f"[Lambda] function updated: {FUNCTION}")
    lam.get_waiter("function_active_v2").wait(FunctionName=FUNCTION)
    lam.get_waiter("function_updated_v2").wait(FunctionName=FUNCTION)
    return fn["FunctionArn"]


def ensure_trigger(lam, s3, fn_arn: str, account: str) -> None:
    try:
        lam.add_permission(
            FunctionName=FUNCTION, StatementId=f"s3-invoke-{BUCKET}"[:100],
            Action="lambda:InvokeFunction", Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{BUCKET}", SourceAccount=account)
        log.info("[Lambda] S3 invoke permission added")
    except lam.exceptions.ResourceConflictException:
        log.info("[Lambda] S3 invoke permission exists")

    # Only silver/ and gold/ trigger the function; warehouse/ (its own output) never does,
    # so there is no infinite loop.
    s3.put_bucket_notification_configuration(Bucket=BUCKET, NotificationConfiguration={
        "LambdaFunctionConfigurations": [{
            "Id": f"uheb-{layer}-parquet",
            "LambdaFunctionArn": fn_arn,
            "Events": ["s3:ObjectCreated:*"],
            "Filter": {"Key": {"FilterRules": [{"Name": "prefix", "Value": f"{layer}/"},
                                               {"Name": "suffix", "Value": ".parquet"}]}},
        } for layer in ("silver", "gold")]})
    log.info("[S3] event trigger set: silver/*.parquet, gold/*.parquet -> Lambda")


def backfill(lam, s3) -> None:
    """Send existing silver/gold objects through the Lambda (same event shape as S3)."""
    records = []
    for layer in ("silver", "gold"):
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=f"{layer}/"):
            for obj in page.get("Contents", []):
                records.append({"s3": {"bucket": {"name": BUCKET},
                                       "object": {"key": obj["Key"], "size": obj["Size"]}}})
    if not records:
        log.warning("[Backfill] nothing in silver/ or gold/ yet - run scripts/04_upload_s3.py first")
        return
    resp = lam.invoke(FunctionName=FUNCTION, Payload=json.dumps({"Records": records}).encode())
    result = json.loads(resp["Payload"].read())
    if resp.get("FunctionError"):
        raise RuntimeError(f"Lambda error: {result}")
    log.info(f"[Backfill] Lambda copied {len(result['copied'])} file(s); crawler {result['crawler']['status']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create/update the AWS cloud side of the pipeline")
    parser.add_argument("--backfill", action="store_true",
                        help="run the Lambda over files that are already in S3")
    args = parser.parse_args()

    if not BUCKET:
        log.error("Set S3_BUCKET_NAME first, e.g.  export S3_BUCKET_NAME=uheb-datalake-xxxx")
        return 1
    session = boto3.Session(region_name=REGION)
    try:
        account = session.client("sts").get_caller_identity()["Account"]
    except (NoCredentialsError, ClientError) as e:
        log.error(f"AWS credentials missing or expired ({e}). Start the Learner Lab and "
                  "paste 'AWS CLI' credentials into ~/.aws/credentials")
        return 1
    role_arn = f"arn:aws:iam::{account}:role/{ROLE_NAME}"
    log.info(f"=== Cloud set-up | region {REGION} | bucket {BUCKET} | role {ROLE_NAME} ===")

    s3, glue, lam = session.client("s3"), session.client("glue"), session.client("lambda")
    try:
        ensure_bucket(s3)
        ensure_glue(glue, role_arn)
        fn_arn = ensure_lambda(lam, role_arn)
        ensure_trigger(lam, s3, fn_arn, account)
        if args.backfill:
            backfill(lam, s3)
    except ClientError as e:
        log.error(f"AWS error: {e}")
        return 1
    log.info("=== Cloud set-up finished ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
