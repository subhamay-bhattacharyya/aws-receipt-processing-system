"""Shared Powertools logger for the repo-tracker Lambda functions."""

import functools
from typing import Any, Callable

from aws_lambda_powertools import Logger

from .formatter import StructuredLogFormatter

SERVICE_NAME = "repo-tracker"
# Fraction of cold starts that log at DEBUG (the TypeScript sampleRate: 0.1).
SAMPLE_RATE = 0.1

logger = Logger(
    service=SERVICE_NAME,
    sampling_rate=SAMPLE_RATE,
    logger_formatter=StructuredLogFormatter(xray_trace_id=None),
)


def inject_lambda_context(handler: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that adds Lambda context to every log line, including function_version.

    Wraps Powertools' ``logger.inject_lambda_context`` and adds the function
    version, which Powertools does not include by default.
    """
    injected = logger.inject_lambda_context(handler)

    @functools.wraps(handler)
    def wrapper(event: Any, context: Any, *args: Any, **kwargs: Any) -> Any:
        logger.append_keys(function_version=context.function_version)
        return injected(event, context, *args, **kwargs)

    return wrapper
