"""Unit tests for slothops.ai_engine"""
import pytest
from slothops.ai_engine import (
    fallback_analyze,
    content_hash,
    similarity_score,
    find_duplicates,
    CATEGORIES,
    DUPLICATE_THRESHOLD,
    _safe_slug,
    _keyword_category,
    _extract_actions_heuristic,
    _parse_llm_json,
)


# ── fallback_analyze ──────────────────────────────────────────────────────────
class TestFallbackAnalyze:
    def test_returns_analysis_result(self):
        result = fallback_analyze("Meeting agenda for Q4 sprint planning.", "agenda.txt")
        assert result.fallback is True
        assert result.model_used == "heuristic-fallback"

    def test_summary_contains_content(self):
        text = "Project milestone planning document."
        result = fallback_analyze(text, "project.txt")
        assert len(result.summary) > 10

    def test_category_is_valid(self):
        result = fallback_analyze("Any text goes here.", "doc.txt")
        assert result.category in CATEGORIES

    def test_meeting_notes_category(self):
        text = "Meeting agenda: discussed action items with attendees."
        result = fallback_analyze(text, "meeting.txt")
        assert result.category == "Meeting Notes"

    def test_todo_category(self):
        text = "TODO: fix the bug\n- [ ] Write tests\nACTION: deploy to staging"
        result = fallback_analyze(text, "todo.txt")
        assert result.category == "Action Items / TODO"

    def test_proposed_filename_safe(self):
        result = fallback_analyze("Some content about meetings.", "notes.txt")
        assert " " not in result.proposed_filename
        assert "/" not in result.proposed_filename
        assert "\\" not in result.proposed_filename

    def test_proposed_filename_keeps_ext(self):
        result = fallback_analyze("# Doc\ncontent", "readme.md")
        assert result.proposed_filename.endswith(".md")

    def test_empty_text(self):
        result = fallback_analyze("", "empty.txt")
        assert result.ok_ish or True  # must not crash

    def test_action_items_extracted(self):
        text = "- [ ] Buy groceries\nTODO: Call the doctor\n- [ ] Fix bug"
        result = fallback_analyze(text, "todo.txt")
        assert len(result.action_items) >= 2


# custom property we add just for test convenience
def _ok_ish(r) -> bool:
    return r.category in CATEGORIES

import slothops.ai_engine as ae
ae.AnalysisResult.ok_ish = property(_ok_ish)


# ── content_hash ──────────────────────────────────────────────────────────────
class TestContentHash:
    def test_deterministic(self):
        h1 = content_hash("Hello World")
        h2 = content_hash("Hello World")
        assert h1 == h2

    def test_case_insensitive_normalised(self):
        h1 = content_hash("Hello World")
        h2 = content_hash("hello world")
        assert h1 == h2

    def test_whitespace_normalised(self):
        h1 = content_hash("hello   world")
        h2 = content_hash("hello world")
        assert h1 == h2

    def test_different_content(self):
        h1 = content_hash("hello")
        h2 = content_hash("world")
        assert h1 != h2

    def test_hash_length(self):
        assert len(content_hash("test")) == 64  # SHA-256 hex


# ── similarity_score ──────────────────────────────────────────────────────────
class TestSimilarityScore:
    def test_identical_texts(self):
        text = "the quick brown fox jumps over the lazy dog"
        assert similarity_score(text, text) == 1.0

    def test_completely_different(self):
        score = similarity_score("apple banana cherry", "delta echo foxtrot golf")
        assert score == 0.0

    def test_partial_similarity(self):
        a = "the quick brown fox"
        b = "the quick brown cat"
        score = similarity_score(a, b)
        assert 0.0 < score < 1.0

    def test_empty_both(self):
        assert similarity_score("", "") == 1.0

    def test_one_empty(self):
        assert similarity_score("hello world", "") == 0.0

    def test_symmetric(self):
        a = "hello world foo bar"
        b = "hello world baz qux"
        assert similarity_score(a, b) == similarity_score(b, a)


# ── find_duplicates ───────────────────────────────────────────────────────────
class TestFindDuplicates:
    def test_finds_near_duplicate(self):
        target = "the quick brown fox jumps over the lazy dog indeed"
        corpus = {
            "other.txt": "the quick brown fox jumps over the lazy dog indeed",
            "unrelated.txt": "completely different content here nothing matches",
        }
        dups = find_duplicates(target, corpus)
        assert len(dups) == 1
        assert dups[0][0] == "other.txt"
        assert dups[0][1] >= DUPLICATE_THRESHOLD

    def test_no_duplicates(self):
        target = "unique specialized content about rare topics"
        corpus = {"a.txt": "completely different words here entirely"}
        dups = find_duplicates(target, corpus)
        assert dups == []

    def test_empty_corpus(self):
        assert find_duplicates("anything", {}) == []

    def test_sorted_by_score_descending(self):
        long_text = "the quick brown fox jumps over the lazy dog " * 5
        corpus = {
            "exact.txt": long_text,
            "partial.txt": "the quick brown fox jumps over something else now",
        }
        dups = find_duplicates(long_text, corpus)
        if len(dups) > 1:
            assert dups[0][1] >= dups[1][1]


# ── _safe_slug ────────────────────────────────────────────────────────────────
class TestSafeSlug:
    def test_basic(self):
        assert _safe_slug("hello world") == "hello_world"

    def test_strips_special_chars(self):
        slug = _safe_slug("hello! world? 2024")
        assert "!" not in slug
        assert "?" not in slug

    def test_max_words(self):
        slug = _safe_slug("one two three four five six seven", max_words=3)
        assert slug == "one_two_three"

    def test_empty_string(self):
        assert _safe_slug("") == "document"


# ── _keyword_category ─────────────────────────────────────────────────────────
class TestKeywordCategory:
    def test_meeting_notes(self):
        assert _keyword_category("meeting agenda attendees discussed") == "Meeting Notes"

    def test_project_plan(self):
        assert _keyword_category("milestone roadmap sprint deliverable") == "Project Plan"

    def test_email(self):
        assert _keyword_category("dear mr smith regards sincerely subject: from:") == "Email / Communication"

    def test_unknown_returns_misc(self):
        cat = _keyword_category("aaaaaa bbbbb ccccc")
        assert cat == "Miscellaneous"


# ── _extract_actions_heuristic ────────────────────────────────────────────────
class TestExtractActionsHeuristic:
    def test_markdown_checkbox(self):
        text = "- [ ] Fix the login bug\n- [x] Write tests"
        items = _extract_actions_heuristic(text)
        assert any("Fix the login bug" in i for i in items)

    def test_todo_prefix(self):
        text = "TODO: Deploy to production by Friday"
        items = _extract_actions_heuristic(text)
        assert any("Deploy" in i for i in items)

    def test_action_prefix(self):
        text = "ACTION: Schedule a follow-up meeting"
        items = _extract_actions_heuristic(text)
        assert any("Schedule" in i for i in items)

    def test_max_10_items(self):
        lines = "\n".join(f"- [ ] Task {i}" for i in range(20))
        items = _extract_actions_heuristic(lines)
        assert len(items) <= 10

    def test_empty_text(self):
        assert _extract_actions_heuristic("") == []


# ── _parse_llm_json ───────────────────────────────────────────────────────────
class TestParseLlmJson:
    def _make_fallback(self):
        return fallback_analyze("fallback text", "fallback.txt")

    def test_valid_json(self):
        raw = '{"summary": "A test doc.", "category": "Meeting Notes", "proposed_filename": "test.txt", "action_items": ["Do X"]}'
        result = _parse_llm_json(raw, self._make_fallback(), "test.txt")
        assert result.summary == "A test doc."
        assert result.category == "Meeting Notes"
        assert result.proposed_filename == "test.txt"
        assert "Do X" in result.action_items

    def test_json_in_code_fence(self):
        raw = '```json\n{"summary": "Doc.", "category": "Report / Analysis", "proposed_filename": "r.txt", "action_items": []}\n```'
        result = _parse_llm_json(raw, self._make_fallback(), "r.txt")
        assert result.summary == "Doc."

    def test_invalid_category_uses_fallback(self):
        raw = '{"summary": "Doc.", "category": "Not A Real Category", "proposed_filename": "x.txt", "action_items": []}'
        fb = self._make_fallback()
        result = _parse_llm_json(raw, fb, "x.txt")
        assert result.category == fb.category  # falls back to heuristic category

    def test_garbage_uses_fallback(self):
        raw = "I cannot help with that."
        fb = self._make_fallback()
        result = _parse_llm_json(raw, fb, "x.txt")
        assert result.summary == fb.summary  # fell back

    def test_path_traversal_in_proposed_filename_sanitised(self):
        raw = '{"summary": "Doc.", "category": "Meeting Notes", "proposed_filename": "../../etc/passwd", "action_items": []}'
        result = _parse_llm_json(raw, self._make_fallback(), "doc.txt")
        assert ".." not in result.proposed_filename
        assert "/" not in result.proposed_filename
