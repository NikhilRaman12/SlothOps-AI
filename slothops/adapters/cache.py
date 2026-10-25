"""
slothops/adapters/cache.py
SQLite-backed cache for normalised API records with provenance tracking.

Design
------
* One SQLite database: slothops_api_cache.db (separate from session history)
* Records cached with TTL; stale records returned with a warning flag
* Provenance table tracks every fetch: endpoint, timestamp, page, cache_hit
* No record is ever deleted automatically (consistent with file-ops philosophy)
* Thread-safe via SQLite WAL mode
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .models import NormalisedRecord, ProvenanceEntry

DB_PATH = Path(__file__).parent.parent.parent / "slothops_api_cache.db"

# Default TTLs (seconds)
TTL_GITHUB = 3600          # 1 hour
TTL_HUGGINGFACE = 7200     # 2 hours
TTL_OPENALEX = 86400       # 24 hours
TTL_SYNTHETIC = 0          # never expires

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS api_records (
    id            TEXT PRIMARY KEY,   -- NormalisedRecord.display_id
    source        TEXT NOT NULL,
    record_type   TEXT NOT NULL,
    raw_id        TEXT NOT NULL,
    title         TEXT NOT NULL,
    body          TEXT,
    url           TEXT,
    created_at    TEXT,               -- ISO-8601 or NULL
    updated_at    TEXT,
    tags          TEXT,               -- JSON array
    author        TEXT,
    extra         TEXT,               -- JSON object
    synthetic     INTEGER DEFAULT 0,
    is_valid      INTEGER DEFAULT 1,
    validation_errors TEXT,           -- JSON array
    cached_at     REAL NOT NULL,      -- Unix timestamp
    ttl_seconds   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS provenance (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id     TEXT NOT NULL,
    source        TEXT NOT NULL,
    fetch_ts      REAL NOT NULL,
    endpoint      TEXT,
    cache_hit     INTEGER DEFAULT 0,
    ttl_seconds   INTEGER,
    page          INTEGER DEFAULT 1,
    extra         TEXT               -- JSON
);

CREATE INDEX IF NOT EXISTS idx_records_source ON api_records(source);
CREATE INDEX IF NOT EXISTS idx_records_cached_at ON api_records(cached_at);
CREATE INDEX IF NOT EXISTS idx_prov_record_id ON provenance(record_id);
"""


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA_SQL)
    return con


def _dt_to_str(dt) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _str_to_dt(s: Optional[str]):
    if not s:
        return None
    from datetime import datetime, timezone
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _row_to_record(row: sqlite3.Row) -> tuple[NormalisedRecord, bool]:
    """
    Convert a DB row to a NormalisedRecord.
    Returns (record, is_stale).
    """
    cached_at = row["cached_at"]
    ttl = row["ttl_seconds"]
    is_stale = (ttl > 0) and ((time.time() - cached_at) > ttl)

    rec = NormalisedRecord(
        source=row["source"],
        record_type=row["record_type"],
        raw_id=row["raw_id"],
        title=row["title"],
        body=row["body"] or "",
        url=row["url"] or "",
        created_at=_str_to_dt(row["created_at"]),
        updated_at=_str_to_dt(row["updated_at"]),
        tags=json.loads(row["tags"] or "[]"),
        author=row["author"] or "",
        extra=json.loads(row["extra"] or "{}"),
        synthetic=bool(row["synthetic"]),
        is_valid=bool(row["is_valid"]),
        validation_errors=json.loads(row["validation_errors"] or "[]"),
    )
    return rec, is_stale


def cache_put(
    record: NormalisedRecord,
    ttl_seconds: int,
    db_path: Path = DB_PATH,
) -> None:
    """Upsert a normalised record into the cache."""
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO api_records
              (id, source, record_type, raw_id, title, body, url,
               created_at, updated_at, tags, author, extra, synthetic,
               is_valid, validation_errors, cached_at, ttl_seconds)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              title=excluded.title, body=excluded.body, url=excluded.url,
              updated_at=excluded.updated_at, tags=excluded.tags,
              author=excluded.author, extra=excluded.extra,
              is_valid=excluded.is_valid,
              validation_errors=excluded.validation_errors,
              cached_at=excluded.cached_at, ttl_seconds=excluded.ttl_seconds
            """,
            (
                record.display_id,
                record.source,
                record.record_type,
                record.raw_id,
                record.title,
                record.body,
                record.url,
                _dt_to_str(record.created_at),
                _dt_to_str(record.updated_at),
                json.dumps(record.tags),
                record.author,
                json.dumps(record.extra),
                int(record.synthetic),
                int(record.is_valid),
                json.dumps(record.validation_errors),
                time.time(),
                ttl_seconds,
            ),
        )
        con.commit()
    finally:
        con.close()


def cache_get(
    record_id: str,
    db_path: Path = DB_PATH,
) -> tuple[Optional[NormalisedRecord], bool]:
    """
    Retrieve a record by display_id.
    Returns (record, is_stale). Returns (None, False) if not found.
    """
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT * FROM api_records WHERE id=?", (record_id,)
        ).fetchone()
        if row is None:
            return None, False
        return _row_to_record(row)
    finally:
        con.close()


def cache_get_by_source(
    source: str,
    max_age_seconds: Optional[int] = None,
    db_path: Path = DB_PATH,
) -> list[tuple[NormalisedRecord, bool]]:
    """
    Retrieve all records for a source.
    If max_age_seconds is set, only return records newer than that.
    """
    con = _connect(db_path)
    try:
        if max_age_seconds is not None:
            cutoff = time.time() - max_age_seconds
            rows = con.execute(
                "SELECT * FROM api_records WHERE source=? AND cached_at >= ? ORDER BY cached_at DESC",
                (source, cutoff),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM api_records WHERE source=? ORDER BY cached_at DESC",
                (source,),
            ).fetchall()
        return [_row_to_record(r) for r in rows]
    finally:
        con.close()


def cache_stats(db_path: Path = DB_PATH) -> dict:
    """Return cache statistics."""
    con = _connect(db_path)
    try:
        total = con.execute("SELECT COUNT(*) FROM api_records").fetchone()[0]
        by_source = con.execute(
            "SELECT source, COUNT(*) AS n FROM api_records GROUP BY source"
        ).fetchall()
        stale_count = 0
        now = time.time()
        for row in con.execute(
            "SELECT cached_at, ttl_seconds FROM api_records WHERE ttl_seconds > 0"
        ).fetchall():
            if (now - row["cached_at"]) > row["ttl_seconds"]:
                stale_count += 1
        return {
            "total": total,
            "by_source": {r["source"]: r["n"] for r in by_source},
            "stale": stale_count,
        }
    finally:
        con.close()


def provenance_put(entry: ProvenanceEntry, db_path: Path = DB_PATH) -> None:
    """Record a provenance entry."""
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO provenance
              (record_id, source, fetch_ts, endpoint, cache_hit, ttl_seconds, page, extra)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                entry.record_id,
                entry.source,
                entry.fetch_ts,
                entry.endpoint,
                int(entry.cache_hit),
                entry.ttl_seconds,
                entry.page,
                json.dumps(entry.extra),
            ),
        )
        con.commit()
    finally:
        con.close()


def provenance_get(record_id: str, db_path: Path = DB_PATH) -> list[ProvenanceEntry]:
    """Retrieve provenance history for a record."""
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT * FROM provenance WHERE record_id=? ORDER BY fetch_ts DESC LIMIT 20",
            (record_id,),
        ).fetchall()
        return [
            ProvenanceEntry(
                record_id=r["record_id"],
                source=r["source"],
                fetch_ts=r["fetch_ts"],
                endpoint=r["endpoint"] or "",
                cache_hit=bool(r["cache_hit"]),
                ttl_seconds=r["ttl_seconds"] or 0,
                page=r["page"] or 1,
                extra=json.loads(r["extra"] or "{}"),
            )
            for r in rows
        ]
    finally:
        con.close()
