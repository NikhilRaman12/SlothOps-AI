"""Unit tests for slothops.history (SQLite)"""
import pathlib
import pytest
from slothops import history as h


@pytest.fixture
def tmp_db(tmp_path) -> pathlib.Path:
    return tmp_path / "test_history.db"


class TestHistory:
    def test_save_and_retrieve(self, tmp_db):
        row_id = h.save_session(
            filename="notes.txt",
            category="Meeting Notes",
            summary="A test summary.",
            proposed_fn="meeting_notes.txt",
            action_items=["Do X", "Do Y"],
            model_used="heuristic-fallback",
            db_path=tmp_db,
        )
        assert row_id == 1
        entries = h.get_all(db_path=tmp_db)
        assert len(entries) == 1
        assert entries[0].filename == "notes.txt"
        assert entries[0].category == "Meeting Notes"
        assert "Do X" in entries[0].action_items

    def test_mark_applied(self, tmp_db):
        row_id = h.save_session(
            filename="f.txt",
            category="Misc",
            summary="s",
            proposed_fn="f.txt",
            action_items=[],
            model_used="test",
            db_path=tmp_db,
        )
        entries_before = h.get_all(db_path=tmp_db)
        assert not entries_before[0].applied
        h.mark_applied(row_id, db_path=tmp_db)
        entries_after = h.get_all(db_path=tmp_db)
        assert entries_after[0].applied

    def test_clear_history(self, tmp_db):
        h.save_session("a.txt", "M", "s", "a.txt", [], "m", db_path=tmp_db)
        h.save_session("b.txt", "M", "s", "b.txt", [], "m", db_path=tmp_db)
        deleted = h.clear_history(db_path=tmp_db)
        assert deleted == 2
        assert h.get_all(db_path=tmp_db) == []

    def test_multiple_saves_ordered_desc(self, tmp_db):
        h.save_session("first.txt", "M", "s", "f.txt", [], "m", db_path=tmp_db)
        h.save_session("second.txt", "M", "s", "s.txt", [], "m", db_path=tmp_db)
        entries = h.get_all(db_path=tmp_db)
        assert entries[0].filename == "second.txt"  # most recent first

    def test_ts_human_format(self, tmp_db):
        h.save_session("x.txt", "M", "s", "x.txt", [], "m", db_path=tmp_db)
        entry = h.get_all(db_path=tmp_db)[0]
        ts = entry.ts_human
        assert len(ts) == 16  # "YYYY-MM-DD HH:MM"
        assert "-" in ts
        assert ":" in ts

    def test_action_items_roundtrip(self, tmp_db):
        items = ["Fix bug #1", "Write documentation", "Deploy to prod"]
        h.save_session("todo.txt", "M", "s", "t.txt", items, "m", db_path=tmp_db)
        entry = h.get_all(db_path=tmp_db)[0]
        assert entry.action_items == items

    def test_empty_db(self, tmp_db):
        entries = h.get_all(db_path=tmp_db)
        assert entries == []
