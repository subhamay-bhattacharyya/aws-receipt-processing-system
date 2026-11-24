"""Small helpers ported from backend/lambda/utils/utils.ts."""

import os


def get_env_var_or_raise(name: str) -> str:
    """Return the environment variable's value, or raise if it is missing or empty."""
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Environment variable not available: {name}")
    return value
