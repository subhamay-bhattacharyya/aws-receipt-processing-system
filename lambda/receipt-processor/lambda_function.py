"""
AWS Lambda boilerplate handler.

Entry point: lambda.handler
Runtime:     Python 3.x (standard library only, no third-party dependencies)
"""

import json
import os
from decimal import Decimal

import boto3
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from boto3.dynamodb.types import TypeSerializer
from PIL import Image
from io import BytesIO
from structured_logging import inject_lambda_context, logger

_environment = json.loads(os.environ["CUSTOM"])
DYNAMODB_TABLE_NAME = _environment["DYNAMODB_TABLE_NAME"]
_type_serializer = TypeSerializer()


def _response(status_code: int, body: dict) -> dict:
    """Build an API Gateway-compatible proxy response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _to_decimal(value):
    """DynamoDB rejects Python floats, so convert them to Decimal recursively."""
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


def detect_labels(photo, bucket):
    """Detect labels in an S3 image with Rekognition and draw bounding boxes on it."""
    # Create a Rekognition client
    client = boto3.client("rekognition")

    # Detect labels in the photo
    response = client.detect_labels(
        Image={"S3Object": {"Bucket": bucket, "Name": photo}},
        MaxLabels=10,
    )

    # Log detected labels
    # logger.info("Detected labels", extra={"photo": photo, "bucket": bucket})
    labels = []
    for label in response["Labels"]:
        labels.append({"label": label["Name"], "confidence": label["Confidence"]})

    logger.info(
        "Label detected",
        extra={"labelCount": len(labels), "labels": labels},
    )

    # Load the image from S3
    s3 = boto3.resource("s3")
    obj = s3.Object(bucket, photo)
    img_data = obj.get()["Body"].read()
    img = Image.open(BytesIO(img_data))

    # Display the image with bounding boxes
    plt.imshow(img)
    ax = plt.gca()
    for label in response["Labels"]:
        for instance in label.get("Instances", []):
            bbox = instance["BoundingBox"]
            left = bbox["Left"] * img.width
            top = bbox["Top"] * img.height
            width = bbox["Width"] * img.width
            height = bbox["Height"] * img.height
            rect = patches.Rectangle(
                (left, top), width, height, linewidth=1, edgecolor="r", facecolor="none"
            )
            ax.add_patch(rect)
            label_text = (
                label["Name"] + " (" + str(round(label["Confidence"], 2)) + "%)"
            )
            plt.text(
                left,
                top - 2,
                label_text,
                color="r",
                fontsize=8,
                bbox=dict(facecolor="white", alpha=0.7),
            )
    plt.show()

    return {"labelsCount": len(labels), "labels": labels}


@inject_lambda_context
def handler(event, context):
    """
    Lambda entry point.

    Args:
        event:   Invocation payload (dict for JSON events, or service-specific shape).
        context: Runtime context object (request id, remaining time, etc.).

    Returns:
        A dict. Shape depends on the trigger; this returns a generic result.
    """
    # logger.info("Received event", extra={"event": event})

    try:
        # ---- Your business logic goes here ----
        for record in event["Records"]:
            body = record["body"]
            # The SQS body is a JSON string containing the S3 notification
            if isinstance(body, str):
                body = json.loads(body)

            for s3_record in body["Records"]:
                bucket = s3_record["s3"]["bucket"]["name"]
                key = s3_record["s3"]["object"]["key"]
                e_tag = s3_record["s3"]["object"]["eTag"]
                version_id = s3_record["s3"]["object"]["versionId"]
                size = s3_record["s3"]["object"]["size"]
                event_time = s3_record["eventTime"]
                dynamodb_item = dict(
                    eTag=e_tag,
                    versionId=version_id,
                    bucketName=bucket,
                    objectKey=key,
                    size=size,
                    eventTime=event_time,
                )

                labels = detect_labels(key, bucket)
                item = {**dynamodb_item, **labels}
                put_dynamodb_item(item)

        result = {"message": "Labels detected!", "request_id": context.aws_request_id}
        # ---------------------------------------

        return _response(200, result)

    except ValueError as exc:
        # Expected, client-side problem (bad input).
        logger.warning("Validation error: %s", exc)
        return _response(400, {"error": str(exc)})

    except Exception:  # pylint: disable=broad-exception-caught
        # Unexpected failure: log the full traceback and return a generic 500.
        logger.exception("Unhandled error")
        return _response(500, {"error": "Internal server error"})
