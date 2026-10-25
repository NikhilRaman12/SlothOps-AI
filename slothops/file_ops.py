"""
slothops/file_ops.py
Undoable, collision-safe file operations.
Never deletes files automatically.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def resolve_safe(base: pathlib.Path, target: str) -> pathlib.Path:
    """
    Resolve *target* relative to *base* and raise if it escapes *base*.
    Protects against path-traversal attacks.
    """
    resolved = (base / target).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        raise ValueError(
            f"Path traversal rejected: '{target}' resolves outside base '{base}'"
        )
    return resolved


# ---------------------------------------------------------------------------
# Operation log (undo stack)
# ---------------------------------------------------------------------------


@dataclass
class FileOperation:
    op_type: str          # "copy", "rename"
    src: pathlib.Path
    dst: pathlib.Path
    timestamp: float = field(default_factory=time.time)
    undone: bool = False

    @property
    def description(self) -> str:
        return f"{self.op_type.upper()}: {self.src.name} → {self.dst.name}"


class OperationLog:
    """In-memory log of applied file operations; supports undo."""

    def __init__(self) -> None:
        self._ops: list[FileOperation] = []

    def record(self, op: FileOperation) -> None:
        self._ops.append(op)

    def history(self) -> list[FileOperation]:
        return list(reversed(self._ops))

    def undo_last(self) -> Optional[str]:
        """
        Undo the most-recent un-done operation.
        Returns a human-readable description or None if nothing to undo.
        """
        for op in reversed(self._ops):
            if not op.undone:
                return self._undo(op)
        return None

    def _undo(self, op: FileOperation) -> str:
        if op.op_type == "copy":
            # Remove the copy destination (NOT the original)
            if op.dst.exists():
                op.dst.unlink()
                op.undone = True
                return f"Undone copy: removed '{op.dst}'"
            op.undone = True
            return f"Undo copy: destination '{op.dst}' already gone."

        if op.op_type == "rename":
            # Move it back
            if op.dst.exists() and not op.src.exists():
                op.dst.rename(op.src)
                op.undone = True
                return f"Undone rename: '{op.dst.name}' → '{op.src.name}'"
            op.undone = True
            return f"Undo rename skipped (src/dst state changed)."

        return f"Unknown operation type: {op.op_type}"


# ---------------------------------------------------------------------------
# Collision protection
# ---------------------------------------------------------------------------


def safe_destination(dst: pathlib.Path) -> pathlib.Path:
    """
    If *dst* already exists, append _1, _2, … until a free path is found.
    """
    if not dst.exists():
        return dst
    stem = dst.stem
    suffix = dst.suffix
    parent = dst.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------


def copy_organised(
    src: pathlib.Path,
    base_output: pathlib.Path,
    category: str,
    proposed_name: str,
    log: OperationLog,
) -> tuple[bool, str, Optional[pathlib.Path]]:
    """
    Copy *src* into *base_output/<category>/<proposed_name>*.

    Parameters
    ----------
    src            : Source file path.
    base_output    : Root output directory (must be set by the app).
    category       : Subfolder name derived from AI analysis.
    proposed_name  : Proposed safe filename.
    log            : OperationLog to record the operation.

    Returns
    -------
    (success, message, dst_path)
    """
    # Sanitise category → safe folder name
    safe_cat = pathlib.Path(
        "".join(c if c.isalnum() or c in " _-" else "_" for c in category)
    ).name or "Miscellaneous"

    category_dir = base_output / safe_cat
    category_dir.mkdir(parents=True, exist_ok=True)

    # Validate proposed_name doesn't escape
    try:
        dst = resolve_safe(category_dir, proposed_name)
    except ValueError as exc:
        return False, str(exc), None

    dst = safe_destination(dst)

    try:
        shutil.copy2(src, dst)
    except OSError as exc:
        return False, f"Copy failed: {exc}", None

    op = FileOperation(op_type="copy", src=src, dst=dst)
    log.record(op)
    return True, f"Copied to '{dst}'", dst


def rename_in_place(
    src: pathlib.Path,
    new_name: str,
    log: OperationLog,
) -> tuple[bool, str, Optional[pathlib.Path]]:
    """
    Rename *src* to *new_name* within the same directory.
    Never moves across directories.

    Returns
    -------
    (success, message, new_path)
    """
    parent = src.parent
    try:
        dst = resolve_safe(parent, new_name)
    except ValueError as exc:
        return False, str(exc), None

    dst = safe_destination(dst)

    try:
        src.rename(dst)
    except OSError as exc:
        return False, f"Rename failed: {exc}", None

    op = FileOperation(op_type="rename", src=src, dst=dst)
    log.record(op)
    return True, f"Renamed '{src.name}' → '{dst.name}'", dst
