"""
slothops/ingest.py
Safe TXT and Markdown file ingestion with path-traversal protection.
"""

from __future__ import annotations

import os
import pathlib
import re
from dataclasses import dataclass, field
from typing import Optional

import chardet

# Maximum file size accepted (bytes)
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

# Allowed extensions (lower-case)
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".txt", ".md", ".markdown"})


@dataclass
class IngestedFile:
    """Parsed representation of an uploaded file."""

    original_name: str
    content: str
    byte_size: int
    encoding: str
    extension: str
    error: Optional[str] = None
    lines: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def word_count(self) -> int:
        return len(self.content.split())

    @property
    def line_count(self) -> int:
        return len(self.lines)


def _safe_filename(name: str) -> str:
    """
    Reject any filename that contains directory separators or parent-directory
    segments, then return the basename.
    Raises ValueError on traversal attempts.
    """
    # Normalise separators so we catch both Unix and Windows paths
    normalised = name.replace("\\", "/")

    # Reject if the raw input contains path separators or .. segments
    parts = normalised.split("/")
    if len(parts) > 1:
        raise ValueError(f"Suspicious filename rejected: {name!r}")
    if any(p == ".." for p in parts):
        raise ValueError(f"Suspicious filename rejected: {name!r}")

    basename = parts[-1]
    if not basename:
        raise ValueError(f"Suspicious filename rejected: {name!r}")

    # Extra guard: reject names with null bytes or control chars
    if any(ord(c) < 32 for c in basename):
        raise ValueError(f"Filename contains control characters: {name!r}")
    return basename


def _detect_encoding(raw: bytes) -> str:
    result = chardet.detect(raw)
    return result.get("encoding") or "utf-8"


def ingest_bytes(filename: str, raw: bytes) -> IngestedFile:
    """
    Ingest raw bytes from an uploaded file.

    Parameters
    ----------
    filename : str
        Original filename from the uploader (untrusted).
    raw : bytes
        Raw file contents.

    Returns
    -------
    IngestedFile
        Parsed result; check `.ok` / `.error` before use.
    """
    try:
        safe_name = _safe_filename(filename)
    except ValueError as exc:
        return IngestedFile(
            original_name=filename,
            content="",
            byte_size=len(raw),
            encoding="unknown",
            extension="",
            error=str(exc),
        )

    ext = pathlib.Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return IngestedFile(
            original_name=safe_name,
            content="",
            byte_size=len(raw),
            encoding="unknown",
            extension=ext,
            error=f"Unsupported extension '{ext}'. Only .txt and .md are allowed.",
        )

    if len(raw) > MAX_FILE_BYTES:
        return IngestedFile(
            original_name=safe_name,
            content="",
            byte_size=len(raw),
            encoding="unknown",
            extension=ext,
            error=f"File too large ({len(raw):,} bytes). Maximum is {MAX_FILE_BYTES:,} bytes.",
        )

    encoding = _detect_encoding(raw)
    try:
        text = raw.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        text = raw.decode("utf-8", errors="replace")
        encoding = "utf-8"

    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = text.splitlines()

    return IngestedFile(
        original_name=safe_name,
        content=text,
        byte_size=len(raw),
        encoding=encoding,
        extension=ext,
        lines=lines,
    )


def ingest_streamlit_file(uploaded_file) -> IngestedFile:
    """
    Convenience wrapper for a Streamlit UploadedFile object.
    """
    raw: bytes = uploaded_file.read()
    return ingest_bytes(uploaded_file.name, raw)


def strip_markdown(text: str) -> str:
    """Remove common Markdown syntax for plain-text processing."""
    # Remove YAML front-matter
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
    # Remove code fences
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Remove inline code backticks but preserve the text content
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove headings
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove links
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove images
    text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", "", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Collapse blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
