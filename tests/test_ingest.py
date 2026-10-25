"""Unit tests for slothops.ingest"""
import pytest
from slothops.ingest import (
    ingest_bytes,
    strip_markdown,
    _safe_filename,
    ALLOWED_EXTENSIONS,
    MAX_FILE_BYTES,
)


# ── _safe_filename ─────────────────────────────────────────────────────────────
class TestSafeFilename:
    def test_plain_name_passes(self):
        assert _safe_filename("hello.txt") == "hello.txt"

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError, match="Suspicious"):
            _safe_filename("../../../etc/passwd")

    def test_windows_path_traversal_rejected(self):
        with pytest.raises(ValueError):
            _safe_filename("..\\..\\windows\\system32\\cmd.exe")

    def test_null_byte_rejected(self):
        with pytest.raises(ValueError, match="control"):
            _safe_filename("file\x00name.txt")

    def test_deep_path_rejected(self):
        with pytest.raises(ValueError):
            _safe_filename("foo/bar/baz.txt")


# ── ingest_bytes ───────────────────────────────────────────────────────────────
class TestIngestBytes:
    def test_basic_txt(self):
        raw = b"Hello world\nSecond line\n"
        result = ingest_bytes("test.txt", raw)
        assert result.ok
        assert result.content == "Hello world\nSecond line\n"
        assert result.extension == ".txt"
        assert result.word_count == 4
        assert result.line_count == 2

    def test_basic_md(self):
        raw = b"# Title\n\nSome content here.\n"
        result = ingest_bytes("notes.md", raw)
        assert result.ok
        assert result.extension == ".md"

    def test_disallowed_extension(self):
        result = ingest_bytes("script.py", b"print('hi')")
        assert not result.ok
        assert "Unsupported extension" in result.error

    def test_file_too_large(self):
        raw = b"x" * (MAX_FILE_BYTES + 1)
        result = ingest_bytes("big.txt", raw)
        assert not result.ok
        assert "too large" in result.error

    def test_path_traversal_in_filename(self):
        result = ingest_bytes("../../etc/passwd", b"root:x:0:0")
        assert not result.ok
        # The error may say "Suspicious" (traversal check) or something else safety-related
        assert result.error is not None and len(result.error) > 0

    def test_crlf_normalised(self):
        raw = b"line1\r\nline2\r\nline3"
        result = ingest_bytes("crlf.txt", raw)
        assert result.ok
        assert "\r" not in result.content

    def test_markdown_extension_accepted(self):
        result = ingest_bytes("doc.markdown", b"# Doc")
        assert result.ok
        assert result.extension == ".markdown"

    def test_empty_file(self):
        result = ingest_bytes("empty.txt", b"")
        assert result.ok
        assert result.word_count == 0
        assert result.line_count == 0


# ── strip_markdown ─────────────────────────────────────────────────────────────
class TestStripMarkdown:
    def test_removes_heading(self):
        text = "# My Heading\n\nSome text."
        stripped = strip_markdown(text)
        assert "#" not in stripped
        assert "My Heading" in stripped

    def test_removes_bold(self):
        text = "This is **bold** text."
        stripped = strip_markdown(text)
        assert "**" not in stripped
        assert "bold" in stripped

    def test_removes_link(self):
        text = "Visit [Google](https://google.com) now."
        stripped = strip_markdown(text)
        assert "https://google.com" not in stripped
        assert "Google" in stripped

    def test_removes_code_fence(self):
        text = "Before\n```python\nprint('hi')\n```\nAfter"
        stripped = strip_markdown(text)
        assert "```" not in stripped

    def test_removes_inline_code(self):
        text = "Use `pathlib.Path` for paths."
        stripped = strip_markdown(text)
        assert "`" not in stripped
        assert "pathlib.Path" in stripped

    def test_front_matter_removed(self):
        text = "---\ntitle: Test\n---\nContent here."
        stripped = strip_markdown(text)
        assert "title:" not in stripped
        assert "Content here" in stripped
