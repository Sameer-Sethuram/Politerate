"""
backend/api/validation.py

Checks and clean-up for values that come from requests. Every SQL query
binds its values as parameters, so these are about rejecting malformed or
oversized input early with a clear 400, not about SQL injection.
"""

import re
from datetime import date

MAX_ID_LENGTH = 100
MAX_URL_LENGTH = 2048
MAX_SEARCH_LENGTH = 100

# Control characters other than tab, newline and carriage return. Pasted
# text sometimes carries them (NUL from PDFs, form feeds), and they reach the
# model and the logs as garbage.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def clean_text(value) -> str:
    """`value` as a string without control characters or outer whitespace;
    "" for anything that isn't a string."""
    if not isinstance(value, str):
        return ""
    return _CONTROL_CHARS.sub("", value).strip()


def bounded_int(raw, default: int, low: int, high: int) -> int:
    """A query-string integer clamped to [low, high]; `default` if it's
    missing or not a number."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def is_iso_date(value: str) -> bool:
    """True for a real calendar date written YYYY-MM-DD."""
    if not _ISO_DATE.fullmatch(value or ""):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def is_http_url(value: str) -> bool:
    return (
        bool(value)
        and len(value) <= MAX_URL_LENGTH
        and value.lower().startswith(("http://", "https://"))
    )
