"""Log formatter that reproduces the output shape of the TypeScript GithubTrackerLogFormatter."""

import os
from datetime import datetime, timezone
from typing import Any

from aws_lambda_powertools.logging.formatter import LambdaPowertoolsFormatter

# Flat keys that Powertools adds (log level, location, context injected by
# inject_lambda_context, sampling rate, ...). They are re-shaped into the nested
# structure below and must not also be copied through as extra attributes.
_CONSUMED_KEYS = {
    "level",
    "location",
    "service",
    "sampling_rate",
    "timestamp",
    "asctime",
    "message",
    "cold_start",
    "function_name",
    "function_memory_size",
    "function_arn",
    "function_request_id",
    "function_version",
}


def format_timestamp(epoch_seconds: float) -> str:
    """ISO 8601 UTC timestamp with millisecond precision, e.g. 2026-11-18T18:04:00.000Z."""
    dt = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def xray_root_trace_id() -> str | None:
    """Extract the Root segment from _X_AMZN_TRACE_ID, e.g. 'Root=1-abc-def;Parent=...'."""
    raw = os.getenv("_X_AMZN_TRACE_ID")
    if not raw:
        return None
    for part in raw.split(";"):
        if part.startswith("Root="):
            return part[len("Root=") :]
    return None


def _strip_none(value: Any) -> Any:
    """Drop None values recursively, like JSON.stringify drops undefined."""
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    return value


class StructuredLogFormatter(LambdaPowertoolsFormatter):
    """Powertools formatter whose JSON output matches the TypeScript version.

    Construct it with ``xray_trace_id=None`` so Powertools does not add its own
    top-level ``xray_trace_id``; the trace ID is nested under ``correlationIds``.
    """

    def _extract_log_keys(self, log_record):  # noqa: D401 - Powertools hook
        flat = super()._extract_log_keys(log_record=log_record)
        extras = {k: v for k, v in flat.items() if k not in _CONSUMED_KEYS}

        base = {
            "logLevel": log_record.levelname,
            "environment": os.getenv("ENVIRONMENT"),
            "awsRegion": os.getenv("AWS_REGION"),
            "correlationIds": {
                "awsRequestId": flat.get("function_request_id"),
                "xRayTraceId": xray_root_trace_id(),
            },
            "lambdaFunction": {
                "name": flat.get("function_name"),
                "arn": flat.get("function_arn"),
                "memoryLimitInMB": flat.get("function_memory_size"),
                "version": flat.get("function_version"),
                "coldStart": flat.get("cold_start"),
            },
            "timestamp": format_timestamp(log_record.created),
            "logger": {"sampleRateValue": flat.get("sampling_rate")},
        }
        # Extra attributes are merged at the top level, as addAttributes() does in TypeScript.
        return {**_strip_none(base), **extras}
