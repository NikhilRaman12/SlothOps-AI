"""
slothops/history.py
Optional SQLite history for file-organisation sessions.
All data is stored 100% locally — nothing leaves the machine.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "slothops_history.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL    NOT NULL,
    filename    TEXT    NOT NULL,
    category    TEXT,
    summary     TEXT,
    proposed_fn TEXT,
    action_items TEXT,
    model_used  TEXT,
    applied     INTEGER DEFAULT 0
);
"""


@dataclass
class HistoryEntry:
    id: int
    ts: float
    filename: str
    category: str
    summary: str
    proposed_fn: str
    action_items: list[str]
    model_used: str
    applied: bool

    @property
    def ts_human(self) -> str:
        import datetime
        return datetime.datetime.fromtimestamp(self.ts).strftime("%Y-%m-%d %H:%M")


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute(_CREATE_SQL)
    con.commit()
    return con


def save_session(
    filename: str,
    category: str,
    summary: str,
    proposed_fn: str,
    action_items: list[str],
    model_used: str,
    applied: bool = False,
    db_path: Path = DB_PATH,
) -> int:
    """Insert a session record and return its row id."""
    con = _connect(db_path)
    cur = con.execute(
        """
        INSERT INTO sessions
            (ts, filename, category, summary, proposed_fn, action_items, model_used, applied)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            time.time(),
            filename,
            category,
            summary,
            proposed_fn,
            json.dumps(action_items),
            model_used,
            int(applied),
        ),
    )
    con.commit()
    con.close()
    return cur.lastrowid  # type: ignore[return-value]


def mark_applied(row_id: int, db_path: Path = DB_PATH) -> None:
    con = _connect(db_path)
    con.execute("UPDATE sessions SET applied=1 WHERE id=?", (row_id,))
    con.commit()
    con.close()


def get_all(db_path: Path = DB_PATH) -> list[HistoryEntry]:
    con = _connect(db_path)
    rows = con.execute(
        "SELECT * FROM sessions ORDER BY ts DESC LIMIT 200"
    ).fetchall()
    con.close()
    entries = []
    for row in rows:
        entries.append(
            HistoryEntry(
                id=row["id"],
                ts=row["ts"],
                filename=row["filename"],
                category=row["category"] or "",
                summary=row["summary"] or "",
                proposed_fn=row["proposed_fn"] or "",
                action_items=json.loads(row["action_items"] or "[]"),
                model_used=row["model_used"] or "",
                applied=bool(row["applied"]),
            )
        )
    return entries


def clear_history(db_path: Path = DB_PATH) -> int:
    """Delete all history rows; returns count deleted."""
    con = _connect(db_path)
    cur = con.execute("DELETE FROM sessions")
    con.commit()
    con.close()
    return cur.rowcount
