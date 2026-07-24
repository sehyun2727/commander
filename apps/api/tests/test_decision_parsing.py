from __future__ import annotations

from app.modules.workflow_engine.parsing import parse_decision_sections, parse_verdict

_FULL = """## Audit: Build a thing

**Problem:** The mission needed someone to deliver "Build a thing".

**Recommendation:** Approve the deliverable for "Build a thing" as submitted.

**Risk:** Low risk -- the change is small and easy to revert.

**Impact:** Small, incremental progress toward the company's goals.

- [x] Matches the PM's plan
- [x] No obvious regressions introduced

**Verdict:** Approved"""


def test_parses_all_four_sections_and_stops_at_the_checklist():
    sections = parse_decision_sections(_FULL)
    assert sections == {
        "problem": 'The mission needed someone to deliver "Build a thing".',
        "recommendation": 'Approve the deliverable for "Build a thing" as submitted.',
        "risk": "Low risk -- the change is small and easy to revert.",
        "impact": "Small, incremental progress toward the company's goals.",
    }
    assert parse_verdict(_FULL) == "approved"


def test_partial_sections_are_returned_leniently():
    text = "Some preamble.\n\n**Problem:** Only this one is present.\n\n**Verdict:** Changes requested"
    assert parse_decision_sections(text) == {"problem": "Only this one is present."}
    assert parse_verdict(text) == "changes_requested"


def test_no_sections_returns_empty_dict_without_raising():
    text = "No structured sections here at all.\n\n**Verdict:** Approved"
    assert parse_decision_sections(text) == {}
    assert parse_verdict(text) == "approved"


def test_missing_verdict_line_defaults_to_changes_requested():
    assert parse_verdict("Nothing parseable in this reply.") == "changes_requested"


def test_verdict_is_case_insensitive_on_the_label():
    assert parse_verdict("**verdict:** Approved") == "approved"
