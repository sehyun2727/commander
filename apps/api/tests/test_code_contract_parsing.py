"""Sprint 5, Phase 5: dedicated coverage for the Engineer code-mission
contract parsers (strict file blocks, lenient change summary) -- the
part of workflow_engine/parsing.py that Phase 2/3's tests only
exercised indirectly through the mock provider's fixed output."""

from __future__ import annotations

from app.modules.workflow_engine.parsing import parse_change_summary, parse_file_blocks

_VALID = """**Change Summary:**
Added a landing page with a hero section and stylesheet.

===== FILE: index.html =====
<!DOCTYPE html>
<html></html>
===== END FILE =====

===== FILE: style.css =====
body { margin: 0; }
===== END FILE ====="""


def test_parses_multiple_well_formed_blocks_in_order():
    files = parse_file_blocks(_VALID)
    assert list(files.keys()) == ["index.html", "style.css"]
    assert files["index.html"] == "<!DOCTYPE html>\n<html></html>"
    assert files["style.css"] == "body { margin: 0; }"


def test_parses_the_preceding_change_summary():
    assert parse_change_summary(_VALID) == "Added a landing page with a hero section and stylesheet."


def test_malformed_block_missing_end_marker_is_dropped():
    text = """**Change Summary:** partial output

===== FILE: index.html =====
<html></html>"""
    assert parse_file_blocks(text) == {}


def test_a_repeated_path_keeps_the_last_occurrence():
    text = """===== FILE: index.html =====
first version
===== END FILE =====

===== FILE: index.html =====
second version
===== END FILE ====="""
    assert parse_file_blocks(text) == {"index.html": "second version"}


def test_zero_valid_blocks_returns_empty_dict_without_raising():
    assert parse_file_blocks("Just a plain prose document, no file blocks at all.") == {}


def test_missing_change_summary_returns_empty_string_without_raising():
    text = """===== FILE: index.html =====
<html></html>
===== END FILE ====="""
    assert parse_change_summary(text) == ""


def test_change_summary_is_empty_when_only_prose_is_present():
    assert parse_change_summary("Just a plain prose document, no file blocks at all.") == ""
