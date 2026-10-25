"""
slothops/adapters/normaliser.py
Validates and normalises raw API payloads into NormalisedRecord objects.
API content is UNTRUSTED — strings are stripped, truncated, and validated.
Embedded instructions are never executed.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from .models import (
    NormalisedRecord,
    VALID_SOURCES,
    RECORD_TYPES,
)

# ---------------------------------------------------------------------------
# Field length limits (chars)
# ---------------------------------------------------------------------------

MAX_TITLE = 500
MAX_BODY = 4000
MAX_TAG = 100
MAX_TAGS = 30
MAX_AUTHOR = 200
MAX_URL = 2048
MAX_RAW_ID = 500


# ---------------------------------------------------------------------------
# Sanitisation helpers
# ---------------------------------------------------------------------------


def _clean_str(value: Any, max_len: int, label: str) -> tuple[str, Optional[str]]:
    """
    Coerce to string, strip whitespace, truncate.
    Returns (cleaned_value, error_or_None).
    """
    if value is None:
        return "", None
    try:
        s = str(value).strip()
    except Exception:
        return "", f"{label}: could not convert to string"
    if len(s) > max_len:
        s = s[:max_len]
    # Remove null bytes and control characters (except tabs and newlines)
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
    return s, None


def _clean_url(raw: Any) -> tuple[str, Optional[str]]:
    """Allow only https:// URLs (or empty string)."""
    url, err = _clean_str(raw, MAX_URL, "url")
    if err or not url:
        return "", err
    if not url.startswith("https://"):
        return "", f"URL rejected (must start with https://): {url[:80]!r}"
    return url, None


def _parse_dt(raw: Any, label: str) -> tuple[Optional[datetime], Optional[str]]:
    """Parse ISO-8601 datetime strings. Returns (dt, error)."""
    if raw is None:
        return None, None
    raw_str, _ = _clean_str(raw, 64, label)
    if not raw_str:
        return None, None
    # Try standard ISO formats
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S+00:00", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw_str[:19], fmt[:len(fmt)])
            return dt.replace(tzinfo=timezone.utc), None
        except ValueError:
            continue
    # Fallback: fromisoformat (Python 3.11+)
    try:
        dt = datetime.fromisoformat(raw_str.replace("Z", "+00:00"))
        return dt, None
    except Exception:
        return None, f"{label}: cannot parse datetime {raw_str!r}"


def _clean_tags(raw: Any) -> list[str]:
    """Clean a list of tag strings."""
    if not isinstance(raw, list):
        return []
    result = []
    for t in raw[:MAX_TAGS]:
        cleaned, _ = _clean_str(t, MAX_TAG, "tag")
        if cleaned:
            result.append(cleaned)
    return result


# ---------------------------------------------------------------------------
# Public normaliser
# ---------------------------------------------------------------------------


def normalise(
    source: str,
    record_type: str,
    raw_id: Any,
    title: Any,
    body: Any,
    url: Any,
    created_at: Any = None,
    updated_at: Any = None,
    tags: Any = None,
    author: Any = None,
    extra: Any = None,
    synthetic: bool = False,
) -> NormalisedRecord:
    """
    Validate and normalise raw API data into a NormalisedRecord.
    All inputs are treated as untrusted. Errors are collected and stored on
    the record (is_valid=False); no exceptions are raised to the caller.
    """
    errors: list[str] = []

    # Source / type validation
    if source not in VALID_SOURCES:
        errors.append(f"Unknown source: {source!r}")
        source = "unknown"
    if record_type not in RECORD_TYPES:
        errors.append(f"Unknown record_type: {record_type!r}")
        record_type = "synthetic"

    # Field cleaning
    raw_id_clean, e = _clean_str(raw_id, MAX_RAW_ID, "raw_id")
    if e:
        errors.append(e)
    if not raw_id_clean:
        errors.append("raw_id is required")

    title_clean, e = _clean_str(title, MAX_TITLE, "title")
    if e:
        errors.append(e)

    body_clean, e = _clean_str(body, MAX_BODY, "body")
    if e:
        errors.append(e)

    url_clean, e = _clean_url(url)
    if e:
        errors.append(e)

    created_dt, e = _parse_dt(created_at, "created_at")
    if e:
        errors.append(e)

    updated_dt, e = _parse_dt(updated_at, "updated_at")
    if e:
        errors.append(e)

    tags_clean = _clean_tags(tags or [])

    author_clean, e = _clean_str(author, MAX_AUTHOR, "author")
    if e:
        errors.append(e)

    extra_clean = extra if isinstance(extra, dict) else {}

    return NormalisedRecord(
        source=source,
        record_type=record_type,
        raw_id=raw_id_clean,
        title=title_clean or "(no title)",
        body=body_clean,
        url=url_clean,
        created_at=created_dt,
        updated_at=updated_dt,
        tags=tags_clean,
        author=author_clean,
        extra=extra_clean,
        synthetic=synthetic,
        is_valid=len(errors) == 0,
        validation_errors=errors,
    )
