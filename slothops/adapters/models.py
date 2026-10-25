"""
slothops/adapters/models.py
Canonical normalised record schema shared by all source adapters.
API content is treated as UNTRUSTED — never executed, never forwarded to
external LLMs, never used in file paths without explicit sanitisation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Source identifiers
# ---------------------------------------------------------------------------

SOURCE_GITHUB = "github"
SOURCE_HUGGINGFACE = "huggingface"
SOURCE_OPENALEX = "openalex"
SOURCE_SYNTHETIC = "synthetic"   # offline fixtures — clearly labeled

VALID_SOURCES = frozenset(
    {SOURCE_GITHUB, SOURCE_HUGGINGFACE, SOURCE_OPENALEX, SOURCE_SYNTHETIC}
)

RECORD_TYPES = frozenset(
    {
        "github_issue",
        "github_pr",
        "hf_model",
        "hf_dataset",
        "openalex_work",
        "synthetic",
    }
)


# ---------------------------------------------------------------------------
# Canonical record
# ---------------------------------------------------------------------------


@dataclass
class NormalisedRecord:
    """
    A normalised, validated record from any source adapter.

    Security guarantees
    -------------------
    * All string fields are stripped and truncated to safe lengths.
    * ``url`` is validated to start with https:// (or empty).
    * No field is ever executed or forwarded to an external service.
    * ``source`` and ``record_type`` are validated against allowlists.
    * ``raw_id`` is used only for deduplication; it is never used in file paths.
    """

    source: str           # SOURCE_* constant
    record_type: str      # RECORD_TYPES constant
    raw_id: str           # Source-specific unique id
    title: str            # Truncated, stripped
    body: str             # Truncated, stripped (max 4000 chars)
    url: str              # https:// only, or ""
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    tags: list[str] = field(default_factory=list)        # labels / topics
    author: str = ""
    extra: dict = field(default_factory=dict)            # source-specific extras
    synthetic: bool = False   # True for demo fixtures

    # Set by normaliser after validation
    is_valid: bool = True
    validation_errors: list[str] = field(default_factory=list)

    @property
    def age_days(self) -> Optional[float]:
        if self.updated_at is None:
            return None
        now = datetime.now(tz=timezone.utc)
        delta = now - (
            self.updated_at
            if self.updated_at.tzinfo
            else self.updated_at.replace(tzinfo=timezone.utc)
        )
        return delta.total_seconds() / 86400

    @property
    def display_id(self) -> str:
        return f"{self.source}:{self.raw_id}"

    @property
    def short_body(self) -> str:
        return self.body[:300] + ("…" if len(self.body) > 300 else "")

    def to_plain_text(self) -> str:
        """Return a safe plain-text representation for local AI analysis."""
        parts = [
            f"Source: {self.source}",
            f"Type: {self.record_type}",
            f"Title: {self.title}",
        ]
        if self.author:
            parts.append(f"Author: {self.author}")
        if self.tags:
            parts.append(f"Tags: {', '.join(self.tags)}")
        if self.body:
            parts.append(f"\n{self.body}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Provenance record
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceEntry:
    """Tracks when and how a record was fetched."""

    record_id: str          # NormalisedRecord.display_id
    source: str
    fetch_ts: float         # Unix timestamp
    endpoint: str           # URL / API endpoint used (sanitised)
    cache_hit: bool
    ttl_seconds: int
    page: int = 1
    extra: dict = field(default_factory=dict)
