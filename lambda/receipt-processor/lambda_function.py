"""
AWS Lambda boilerplate template (event-source agnostic).

Entry point : lambda_function.handler   (set the handler to "lambda_function.handler")
Runtime     : Python 3.12 (standard library + boto3, which the runtime provides)

The handler passes the raw event to process_event() and does not assume a
trigger type. Add parsing for your own event shape inside process_event().
Replace the TODO sections with your business logic.
"""

import json
import re
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import BotoCoreError, ClientError
import urllib.parse
import logging
import os
from decimal import Decimal
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Optional JSON blob in one env var, e.g. APP_CONFIG='{"TABLE_NAME": "my-table"}'
APP_CONFIG: Dict[str, Any] = json.loads(os.environ.get("APP_CONFIG", "{}"))

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# Create SDK clients once per container, outside the handler, so warm
# invocations reuse them. Example:
s3_client = boto3.client("s3")
textract_client = boto3.client("textract")
dynamodb_client = boto3.resource("dynamodb")
ses = boto3.client("ses")

_environment = json.loads(os.environ["CUSTOM"])
DYNAMODB_TABLE_NAME = _environment["DYNAMODB_TABLE_NAME"]
_type_serializer = TypeSerializer()


class ObjectAccessError(Exception):
    """Raised when the S3 object referenced by an event cannot be verified."""


class ReceiptExtractionError(Exception):
    """Raised when Textract AnalyzeExpense fails for a receipt/invoice."""


def _response(status_code: int, body: dict) -> dict:
    """Build an API Gateway-compatible proxy response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


# ---------------------------------------------------------------------------
# Business logic (TODO: replace)
# ---------------------------------------------------------------------------
def process_event(event: Any, context: Any) -> Any:
    """
    Core logic. Receives the raw event exactly as Lambda delivers it.
    TODO: parse the event shape you expect and do the work.

    Return any JSON-serializable value. Raise an exception to signal failure;
    the invoking service decides what to do with it (retry, DLQ, or error).
    """
    try:
        # ---- Logic to process the event (SQS-triggered) ----
        for record in event["Records"]:
            body = record["body"]
            # The SQS body is a JSON string containing the S3 notification
            if isinstance(body, str):
                body = json.loads(body)

            for s3_record in body["Records"]:
                bucket = s3_record["s3"]["bucket"]["name"]
                key = urllib.parse.unquote_plus(s3_record["s3"]["object"]["key"])
                e_tag = s3_record["s3"]["object"]["eTag"]
                version_id = s3_record["s3"]["object"]["versionId"]
                size = s3_record["s3"]["object"]["size"]
                event_time = s3_record["eventTime"]
                s3_object_attributes = dict(
                    eTag=e_tag,
                    versionId=version_id,
                    bucketName=bucket,
                    objectKey=key,
                    size=size,
                    eventTime=event_time,
                )

            logger.info(
                "Received event with keys: %s",
                (
                    list(s3_object_attributes.keys())
                    if isinstance(s3_object_attributes, dict)
                    else type(s3_object_attributes).__name__
                ),
            )

        return _response(200, s3_object_attributes)

    except ValueError as exc:
        # Expected, client-side problem (bad input).
        logger.warning("Validation error: %s", exc)
        return _response(400, {"error": str(exc)})

    except Exception:  # pylint: disable=broad-exception-caught
        # Unexpected failure: log the full traceback and return a generic 500.
        logger.exception("Unhandled error")
        return _response(500, {"error": "Internal server error"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
# Textract SummaryFields type -> receipt attribute name
RECEIPT_FIELD_MAP = {
    "VENDOR_ADDRESS": "store_address",
    "VENDOR_PHONE": "store_phone",
    "VENDOR_URL": "store_website",
    "INVOICE_RECEIPT_ID": "receipt_number",
    "INVOICE_RECEIPT_DATE": "date",
    "SUBTOTAL": "subtotal",
    "TAX": "sales_tax",
    "TOTAL": "total",
}

# Textract reports these as type OTHER; match on the label text instead
RECEIPT_LABEL_MAP = {
    "cashier": "cashier",
    "register": "register",
    "change due": "change_due",
}


def process_receipt_with_textract(bucket: str, key: str) -> Dict[str, Any]:
    """
    Extract receipt attributes and line items from a receipt in S3 using
    Textract AnalyzeExpense.

    Returns {"attributes": {...}, "line_items": [...]}, where attributes has
    keys store_name, store_address, store_phone, store_website, receipt_number,
    date, cashier, register, subtotal, sales_tax, total, change_due
    (missing values are omitted) and each line item has item, quantity,
    unit_price, amount. Logs both. Raises ReceiptExtractionError if the
    Textract call fails.
    """
    logger.info("Calling Textract analyze_expense for %s/%s", bucket, key)
    try:
        response = textract_client.analyze_expense(
            Document={"S3Object": {"Bucket": bucket, "Name": key}}
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        logger.error(
            "Textract analyze_expense failed for %s/%s (%s): %s",
            bucket,
            key,
            code,
            exc,
        )
        raise ReceiptExtractionError(
            f"Textract AnalyzeExpense failed ({code}) for {bucket}/{key}"
        ) from exc
    except BotoCoreError as exc:
        logger.error("Textract analyze_expense failed for %s/%s: %s", bucket, key, exc)
        raise ReceiptExtractionError(
            f"Textract AnalyzeExpense failed for {bucket}/{key}"
        ) from exc

    attributes: Dict[str, str] = {}
    vendor_names: list[str] = []
    items: list[dict[str, str]] = []
    field_map = {
        "ITEM": "item",
        "QUANTITY": "quantity",
        "UNIT_PRICE": "unit_price",
        "PRICE": "amount",
    }

    for expense_doc in response.get("ExpenseDocuments", []):
        # Header attributes (store, receipt number, date, cashier, register)
        for field in expense_doc.get("SummaryFields", []):
            field_type = field.get("Type", {}).get("Text", "")
            value = field.get("ValueDetection", {}).get("Text", "")

            if field_type == "VENDOR_NAME":
                # Collected separately; the store name is chosen after the loop
                vendor_names.append(value)
            elif field_type in RECEIPT_FIELD_MAP:
                attributes.setdefault(RECEIPT_FIELD_MAP[field_type], value)
            elif field_type == "OTHER":
                label = field.get("LabelDetection", {}).get("Text", "")
                label = label.rstrip(":").strip().lower()
                if label in RECEIPT_LABEL_MAP:
                    attributes.setdefault(RECEIPT_LABEL_MAP[label], value)

        # Line items
        for group in expense_doc.get("LineItemGroups", []):
            for line_item in group.get("LineItems", []):
                row: dict[str, str] = {}
                for field in line_item.get("LineItemExpenseFields", []):
                    field_type = field.get("Type", {}).get("Text", "")
                    if field_type in field_map:
                        row[field_map[field_type]] = field.get(
                            "ValueDetection", {}
                        ).get("Text", "")
                if "item" in row:
                    items.append(row)

    # Textract can tag other text (e.g. a footer "Thank you for shopping at X!")
    # as VENDOR_NAME. Prefer the name that matches the first line of the address,
    # otherwise use the first VENDOR_NAME found.
    address_first_line = (
        attributes.get("store_address", "").split("\n")[0].strip().lower()
    )
    store_name = next(
        (n for n in vendor_names if n.strip().lower() == address_first_line),
        vendor_names[0] if vendor_names else None,
    )
    if store_name:
        attributes["store_name"] = store_name

    logger.info("Receipt attributes from %s/%s: %s", bucket, key, attributes)
    logger.info(
        "Extracted %d line items from %s/%s: %s", len(items), bucket, key, items
    )
    return {"attributes": attributes, "line_items": items}


def _to_decimal(value: Any) -> Any:
    """Recursively convert floats to Decimal, since DynamoDB does not accept floats."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_decimal(v) for v in value]
    return value


def serialize_dynamodb_item(item: dict) -> dict:
    """Convert a Python dict into DynamoDB attribute-value format, e.g. {"S": "..."}."""
    return {k: _type_serializer.serialize(_to_decimal(v)) for k, v in item.items()}


def put_dynamodb_item(item: dict) -> None:
    """Serialize the item and write it to the Image-labels DynamoDB table."""
    dynamodb = boto3.client("dynamodb")
    dynamodb.put_item(
        TableName=DYNAMODB_TABLE_NAME,
        Item=serialize_dynamodb_item(item),
    )


def _normalize_receipt_date(raw: str) -> str | None:
    """Return the first YYYY-MM-DD or MM/DD/YYYY date in raw as YYYY-MM-DD, else None."""
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if m:
        year, month, day = m.groups()
    else:
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
        if not m:
            return None
        month, day, year = m.groups()
    try:
        return datetime(int(year), int(month), int(day)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def build_dynamodb_item(
    bucket: str, key: str, receipt: Dict[str, Any], object_attrs: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build a plain Python dict for the receipt returned by process_receipt_with_textract().
    object_attrs is the S3 event data (eTag, size, eventTime, versionId) stored as
    objectMetadata. Pass the result to put_dynamodb_item(), which serializes it.

    Table keys: receiptId (partition, S) and receiptDate (sort, S, YYYY-MM-DD).
    receiptId holds the receipt number. If none was found, a generated UUID is used
    because DynamoDB rejects empty key values. If no usable date is found on the
    receipt, the processing date (UTC) is used.
    """
    attrs = receipt["attributes"]
    receipt_number = attrs.get("receipt_number", "")
    if not receipt_number:
        receipt_number = str(uuid.uuid4())
        logger.warning("No receipt number on %s/%s; generated one", bucket, key)
    receipt_date = _normalize_receipt_date(attrs.get("date", ""))
    if receipt_date is None:
        receipt_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.warning("No usable date on %s/%s; using processing date", bucket, key)

    # storeAddress holds the address followed by the phone and website, if found
    store_address = ", ".join(
        part
        for part in (
            attrs.get("store_address", ""),
            attrs.get("store_phone", ""),
            attrs.get("store_website", ""),
        )
        if part
    )

    document = {
        "receiptNo": receipt_number,
        "receiptDate": receipt_date,
        "storeName": attrs.get("store_name", ""),
        "storeAddress": store_address,
        "cashier": attrs.get("cashier", ""),
        "register": attrs.get("register", ""),
        "subtotal": attrs.get("subtotal", ""),
        "salesTax": attrs.get("sales_tax", ""),
        "total": attrs.get("total", ""),
        "changeDue": attrs.get("change_due", ""),
        "lineItems": [
            {
                "item": li.get("item", ""),
                "quantity": li.get("quantity", ""),
                "unitPrice": li.get("unit_price", ""),
                "amount": li.get("amount", ""),
            }
            for li in receipt["line_items"]
        ],
        "s3Path": f"s3://{bucket}/{key}",
        "objectMetadata": {
            "s3Uri": f"s3://{bucket}/{key}",
            "eTag": object_attrs.get("eTag", ""),
            "size": object_attrs.get("size", 0),
            "eventTime": object_attrs.get("eventTime", ""),
            "versionId": object_attrs.get("versionId", ""),
        },
        "extractedAt": datetime.now(timezone.utc).isoformat(),
    }
    return document


def handler(event: Any, context: Any) -> Any:
    """
    Lambda entry point. Logs the request ID, delegates to process_event(),
    and lets exceptions propagate so the trigger's normal retry behavior applies.
    """
    request_id = getattr(context, "aws_request_id", "local")
    logger.info("Request %s started", request_id)

    result = process_event(event, context)
    if result["statusCode"] != 200:
        raise RuntimeError(f"Event processing failed: {result['body']}")

    # _response() JSON-encodes the body, so decode it before reading fields
    s3_object_attributes = json.loads(result["body"])
    bucket_name = s3_object_attributes["bucketName"]
    object_key = s3_object_attributes["objectKey"]

    # Verify the object exists before proceeding
    try:
        s3_client.head_object(
            Bucket=bucket_name,
            Key=object_key,
        )
        logger.info(
            "Object verification successful: %s/%s",
            bucket_name,
            object_key,
        )
    except Exception as e:
        logger.error("Object verification failed: %s", e)
        raise ObjectAccessError(
            f"Unable to access object {object_key} " f"in bucket {bucket_name}: {e}"
        ) from e

    # Extract invoice/receipt fields with Textract (errors propagate for retry)
    receipt = process_receipt_with_textract(bucket_name, object_key)
    item = build_dynamodb_item(bucket_name, object_key, receipt, s3_object_attributes)
    put_dynamodb_item(item)
    logger.info(
        "Stored receipt %s from %s/%s in %s",
        item["receiptId"],
        bucket_name,
        object_key,
        DYNAMODB_TABLE_NAME,
    )

    logger.info("Request %s finished", request_id)
    return item
