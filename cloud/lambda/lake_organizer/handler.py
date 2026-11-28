"""
AWS Lambda — uheb-lake-organizer

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
