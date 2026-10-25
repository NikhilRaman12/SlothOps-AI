"""Unit tests for slothops.file_ops"""
import pathlib
import pytest
from slothops.file_ops import (
    resolve_safe,
    safe_destination,
    OperationLog,
    copy_organised,
    rename_in_place,
)


# ── resolve_safe ──────────────────────────────────────────────────────────────
class TestResolveSafe:
    def test_normal_path_ok(self, tmp_path):
        result = resolve_safe(tmp_path, "subdir/file.txt")
        assert result.is_relative_to(tmp_path)

    def test_traversal_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="traversal"):
            resolve_safe(tmp_path, "../../etc/passwd")

    def test_absolute_escape_rejected(self, tmp_path):
        # C:\Windows or /tmp are outside tmp_path, so should be rejected
        import os
        # Build a path that definitely resolves outside tmp_path
        outside = tmp_path.parent / "evil.txt"  # sibling of tmp_path
        relative = pathlib.Path("..") / "evil.txt"  # relative traversal
        with pytest.raises(ValueError):
            resolve_safe(tmp_path, str(relative))

    def test_same_dir_ok(self, tmp_path):
        result = resolve_safe(tmp_path, "file.txt")
        assert result.parent == tmp_path.resolve()


# ── safe_destination ──────────────────────────────────────────────────────────
class TestSafeDestination:
    def test_no_collision(self, tmp_path):
        dst = tmp_path / "file.txt"
        result = safe_destination(dst)
        assert result == dst

    def test_collision_adds_suffix(self, tmp_path):
        existing = tmp_path / "file.txt"
        existing.write_text("existing")
        result = safe_destination(existing)
        assert result == tmp_path / "file_1.txt"
        assert result != existing

    def test_multiple_collisions(self, tmp_path):
        (tmp_path / "file.txt").write_text("1")
        (tmp_path / "file_1.txt").write_text("2")
        result = safe_destination(tmp_path / "file.txt")
        assert result == tmp_path / "file_2.txt"


# ── OperationLog ──────────────────────────────────────────────────────────────
class TestOperationLog:
    def test_empty_undo(self):
        log = OperationLog()
        assert log.undo_last() is None

    def test_history_empty(self):
        log = OperationLog()
        assert log.history() == []

    def test_undo_copy(self, tmp_path):
        log = OperationLog()
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("hello")
        dst.write_text("hello")  # simulate copy result

        from slothops.file_ops import FileOperation
        op = FileOperation(op_type="copy", src=src, dst=dst)
        log.record(op)
        msg = log.undo_last()
        assert "Undone" in msg
        assert not dst.exists()  # copy destination removed
        assert src.exists()      # original untouched

    def test_undo_rename(self, tmp_path):
        log = OperationLog()
        original = tmp_path / "original.txt"
        renamed = tmp_path / "renamed.txt"
        original.write_text("content")
        original.rename(renamed)  # simulate rename

        from slothops.file_ops import FileOperation
        op = FileOperation(op_type="rename", src=original, dst=renamed)
        log.record(op)
        msg = log.undo_last()
        assert "Undone" in msg
        assert original.exists()
        assert not renamed.exists()

    def test_history_returns_reversed(self, tmp_path):
        log = OperationLog()
        from slothops.file_ops import FileOperation
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        op1 = FileOperation(op_type="copy", src=f1, dst=f2)
        op2 = FileOperation(op_type="rename", src=f2, dst=f1)
        log.record(op1)
        log.record(op2)
        h = log.history()
        assert h[0] == op2  # most recent first
        assert h[1] == op1


# ── copy_organised ────────────────────────────────────────────────────────────
class TestCopyOrganised:
    def test_basic_copy(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("Hello")
        output = tmp_path / "output"
        log = OperationLog()
        ok, msg, dst = copy_organised(src, output, "Meeting Notes", "notes.txt", log)
        assert ok
        assert dst is not None
        assert dst.exists()
        assert (output / "Meeting Notes" / "notes.txt").exists()

    def test_category_dir_created(self, tmp_path):
        src = tmp_path / "file.txt"
        src.write_text("content")
        output = tmp_path / "out"
        log = OperationLog()
        ok, _, _ = copy_organised(src, output, "Research / Reference", "ref.txt", log)
        assert ok
        assert (output / "Research _ Reference").exists() or any(
            "Research" in str(d) for d in output.iterdir()
        )

    def test_collision_handled(self, tmp_path):
        src = tmp_path / "file.txt"
        src.write_text("content")
        output = tmp_path / "out"
        log = OperationLog()
        ok1, _, dst1 = copy_organised(src, output, "Misc", "doc.txt", log)
        ok2, _, dst2 = copy_organised(src, output, "Misc", "doc.txt", log)
        assert ok1 and ok2
        assert dst1 != dst2  # collision avoided

    def test_traversal_in_proposed_name_rejected(self, tmp_path):
        src = tmp_path / "file.txt"
        src.write_text("content")
        output = tmp_path / "out"
        log = OperationLog()
        ok, msg, _ = copy_organised(src, output, "Misc", "../../evil.txt", log)
        assert not ok
        assert "traversal" in msg.lower()

    def test_operation_recorded(self, tmp_path):
        src = tmp_path / "file.txt"
        src.write_text("content")
        output = tmp_path / "out"
        log = OperationLog()
        copy_organised(src, output, "Meeting Notes", "notes.txt", log)
        assert len(log.history()) == 1
        assert log.history()[0].op_type == "copy"


# ── rename_in_place ───────────────────────────────────────────────────────────
class TestRenameInPlace:
    def test_basic_rename(self, tmp_path):
        src = tmp_path / "old.txt"
        src.write_text("content")
        log = OperationLog()
        ok, msg, dst = rename_in_place(src, "new.txt", log)
        assert ok
        assert dst is not None
        assert dst.name == "new.txt"
        assert dst.exists()
        assert not src.exists()

    def test_collision_handled(self, tmp_path):
        src = tmp_path / "original.txt"
        src.write_text("content")
        existing = tmp_path / "target.txt"
        existing.write_text("already here")
        log = OperationLog()
        ok, msg, dst = rename_in_place(src, "target.txt", log)
        assert ok
        assert dst.name == "target_1.txt"

    def test_traversal_rejected(self, tmp_path):
        src = tmp_path / "file.txt"
        src.write_text("content")
        log = OperationLog()
        ok, msg, _ = rename_in_place(src, "../../evil.txt", log)
        assert not ok
        assert "traversal" in msg.lower()

    def test_original_not_deleted_on_undo(self, tmp_path):
        """After undo of rename, original is restored — not deleted."""
        src = tmp_path / "original.txt"
        src.write_text("important content")
        log = OperationLog()
        ok, _, dst = rename_in_place(src, "renamed.txt", log)
        assert ok
        assert not src.exists()
        log.undo_last()
        assert src.exists()
        assert not dst.exists()
