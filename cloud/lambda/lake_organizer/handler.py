"""
AWS Lambda — uheb-lake-organizer
Owner: ปุณยนุช แซ่แจ้ง (Member 4 — Cloud Compute)

Trigger : S3 ObjectCreated on  silver/*.parquet  and  gold/*.parquet
          (written by scripts/04_upload_s3.py)
What it does
  1. Copies each new Parquet file into a "one folder per table" layout:
         gold/fact_x.parquet  ->  warehouse/gold/fact_x/fact_x.parquet
     Glue/Athena treat a *folder* as a table, so flat files in gold/ cannot be
     queried directly. The original upload is left untouched (Bronze/Silver/Gold
     stay exactly as the local pipeline produced them).
  2. Starts the Glue crawler so the Data Catalog (and Athena) see new tables or
     schema changes. Several files arrive together, so "already running" is normal.
  3. Writes a JSON run record to _ops/lambda_runs/ (cloud-side lineage / audit log).

Only boto3 is used (built into the Lambda Python runtime) -> no layers to manage.
"""

import json
import os
import urllib.parse
from datetime import datetime, timezone

import boto3

s3 = boto3.client("s3")
glue = boto3.client("glue")

CRAWLER_NAME = os.environ["CRAWLER_NAME"]
WAREHOUSE_PREFIX = os.environ.get("WAREHOUSE_PREFIX", "warehouse")
LAYERS = ("silver", "gold")


def target_key(key: str) -> str | None:
    """silver/x.parquet -> warehouse/silver/x/x.parquet ; anything else -> None."""
    layer, _, name = key.partition("/")
    if layer not in LAYERS or "/" in name or not name.endswith(".parquet"):
        return None
    table = name[: -len(".parquet")]
    return f"{WAREHOUSE_PREFIX}/{layer}/{table}/{name}"


def start_crawler() -> str:
    try:
        glue.start_crawler(Name=CRAWLER_NAME)
        return "started"
    except glue.exceptions.CrawlerRunningException:
        return "already_running"


def handler(event, context):
    now = datetime.now(timezone.utc)
    copied, skipped, bucket = [], [], None

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        dest = target_key(key)
        if dest is None:
            skipped.append(key)
            continue
        s3.copy_object(Bucket=bucket, Key=dest, CopySource={"Bucket": bucket, "Key": key})
        copied.append({"source": key, "target": dest,
                       "bytes": record["s3"]["object"].get("size")})

    crawler = start_crawler() if copied else "not_needed"
    run = {
        "function": context.function_name if context else "local-test",
        "request_id": context.aws_request_id if context else "local-test",
        "invoked_at_utc": now.isoformat(timespec="seconds"),
        "copied": copied,
        "skipped": skipped,
        "crawler": {"name": CRAWLER_NAME, "status": crawler},
    }
    if bucket:
        s3.put_object(
            Bucket=bucket,
            Key=f"_ops/lambda_runs/{now:%Y%m%dT%H%M%S}_{run['request_id']}.json",
            Body=json.dumps(run, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
    print(json.dumps(run, ensure_ascii=False))  # also visible in CloudWatch Logs
    return run
