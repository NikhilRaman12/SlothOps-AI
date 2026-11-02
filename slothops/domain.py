from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, UUID4, field_validator, model_validator

VALID_CATEGORIES = [
    "Meeting Notes",
    "Project Plan",
    "Technical Documentation",
    "Research / Reference",
    "Action Items / TODO",
    "Personal Journal",
    "Report / Analysis",
    "Creative Writing",
    "Email / Communication",
    "Miscellaneous",
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class DocumentStatus(str, Enum):
    PENDING = "pending"
    INGESTED = "ingested"
    ANALYZED = "analyzed"
    DUPLICATE = "duplicate"
    REVIEW = "review"
    ORGANIZED = "organized"
    FAILED = "failed"


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: UUID4 = Field(default_factory=uuid.uuid4)
    filename: str
    original_name: str
    extension: str = ".txt"
    byte_size: int = Field(gt=0)
    content_hash: str
    category: str = "Miscellaneous"
    summary: str = ""
    proposed_filename: str = ""
    processing_status: DocumentStatus = DocumentStatus.PENDING
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    storage_reference: str | None = None
    source_path: str | None = None

    @field_validator("filename", "original_name")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("filename is required")
        if value in {".", ".."}:
            raise ValueError("invalid filename")
        cleaned = Path(value).name
        if cleaned != value:
            raise ValueError("path separators are not allowed in filenames")
        if any(ch in value for ch in ("/", "\\")) or value.startswith("../"):
            raise ValueError("unsafe filename")
        if any(ord(ch) < 32 for ch in value):
            raise ValueError("control characters are not allowed in filenames")
        return value

    @field_validator("extension")
    @classmethod
    def validate_extension(cls, value: str) -> str:
        normalized = value.lower()
        if not normalized:
            return ".txt"
        if not normalized.startswith("."):
            normalized = f".{normalized}"
        return normalized

    @field_validator("content_hash")
    @classmethod
    def validate_content_hash(cls, value: str) -> str:
        hash_value = value.strip()
        if len(hash_value) != 64:
            raise ValueError("content hash must be a SHA-256 hex digest")
        try:
            int(hash_value, 16)
        except ValueError as exc:
            raise ValueError("content hash must be hexadecimal") from exc
        return hash_value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        if value not in VALID_CATEGORIES:
            raise ValueError(f"Unsupported category: {value!r}")
        return value

    @field_validator("proposed_filename")
    @classmethod
    def validate_proposed_filename(cls, value: str | None) -> str:
        if value is None or not value:
            return ""
        candidate = Path(value).name
        if not candidate or candidate in {".", ".."}:
            raise ValueError("invalid proposed filename")
        if any(ch in candidate for ch in ("/", "\\")):
            raise ValueError("unsafe proposed filename")
        return candidate

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "Document":
        if self.processing_status == DocumentStatus.FAILED and not self.summary:
            return self
        if self.processing_status == DocumentStatus.ORGANIZED and not self.storage_reference:
            self.storage_reference = self.source_path
        return self

    @classmethod
    def from_bytes(
        cls,
        *,
        filename: str,
        raw: bytes,
        category: str = "Miscellaneous",
        summary: str = "",
        proposed_filename: str = "",
        processing_status: DocumentStatus = DocumentStatus.PENDING,
        storage_reference: str | None = None,
        source_path: str | None = None,
    ) -> "Document":
        safe_name = Path(filename).name
        if not safe_name or safe_name in {".", ".."}:
            raise ValueError("unsafe source filename")
        digest = hashlib.sha256(raw).hexdigest()
        extension = Path(safe_name).suffix.lower() or ".txt"
        return cls(
            filename=safe_name,
            original_name=safe_name,
            extension=extension,
            byte_size=len(raw),
            content_hash=digest,
            category=category,
            summary=summary,
            proposed_filename=proposed_filename,
            processing_status=processing_status,
            storage_reference=storage_reference,
            source_path=source_path,
        )


class DuplicateCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID4
    other_document_id: UUID4
    similarity: float = Field(ge=0.0, le=1.0)
    reason: str = "content similarity"


__all__ = [
    "Document",
    "DocumentStatus",
    "DuplicateCandidate",
    "VALID_CATEGORIES",
]
