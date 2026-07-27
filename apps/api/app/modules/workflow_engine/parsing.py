"""Pure text parsing for Reviewer and Engineer output.

Reviewer (see app/templates/software_company.py REVIEWER contract) --
two contracts of very different strength:

- `parse_verdict` reads the trailing "**Verdict:** ..." line. This is the
  ONLY hard contract in the pipeline -- workflow_engine has always relied
  on it (provider-agnostic) to route a Mission to a CEO Decision.
- `parse_decision_sections` leniently extracts the Problem/Recommendation/
  Risk/Impact sections the Reviewer is asked to write before the verdict.
  These are best-effort narrative context for the DecisionCard: any
  subset (including none) may be present, and a missing/malformed section
  must never raise or block the pipeline.

Engineer, code missions only (Sprint 5) -- also two contracts of
different strength:

- `parse_file_blocks` strictly extracts `===== FILE: path =====` ...
  `===== END FILE =====` blocks. Zero blocks found is not an error --
  the caller (workflow_engine) treats it as a signal to fall back to a
  document mission, never as a pipeline failure.
- `parse_change_summary` leniently extracts the `**Change Summary:**`
  section that precedes the file blocks. Empty string if missing --
  never raises, never blocks.
"""

from __future__ import annotations

import re

_SECTION_LABELS = ("Problem", "Recommendation", "Risk", "Impact")

_FILE_BLOCK_PATTERN = re.compile(
    r"===== FILE: (?P<path>.+?) =====\r?\n(?P<content>.*?)\r?\n===== END FILE =====",
    flags=re.DOTALL,
)

_CHANGE_SUMMARY_PATTERN = re.compile(
    r"\*\*Change Summary:\*\*\s*(?P<summary>.+?)(?=\n\s*===== FILE:|\Z)",
    flags=re.DOTALL,
)


def parse_verdict(text: str) -> str:
    """"approved" or "changes_requested", read from the trailing
    **Verdict:** line. Defaults to "changes_requested" if the line is
    missing or unrecognized -- never silently treat unparseable output as
    an approval. Uses the LAST match, not the first: real (non-mock)
    Reviewer output can ramble and mention "verdict" conversationally
    before the actual sign-off line, so taking the first match risked
    reading a stray earlier mention instead of the real one."""
    matches = re.findall(r"\*\*Verdict:\*\*\s*(.+)", text, flags=re.IGNORECASE)
    if not matches:
        return "changes_requested"
    verdict = matches[-1].strip().lower()
    return "approved" if verdict.startswith("approved") else "changes_requested"


def parse_decision_sections(text: str) -> dict[str, str]:
    """Best-effort extraction of the four labeled sections. Each label's
    value runs only to the next blank line (paragraph break) -- these are
    one-sentence sections, so anything past the first paragraph (a
    checklist, the Verdict line, unrelated trailing prose) is never
    swept in. Silently omits any label not found -- callers must render
    around missing keys, never rely on all four being present."""
    sections: dict[str, str] = {}
    label_pattern = "|".join(_SECTION_LABELS)
    matches = re.finditer(rf"\*\*({label_pattern}):\*\*\s*(.+?)(?=\n\s*\n|\Z)", text, flags=re.DOTALL)
    for match in matches:
        label, value = match.group(1), match.group(2).strip()
        if value:
            sections[label.lower()] = value
    return sections


def parse_file_blocks(text: str) -> dict[str, str]:
    """Strict extraction of `===== FILE: path =====` ... `===== END FILE
    =====` blocks, in order. A path repeated across blocks keeps its last
    occurrence. Returns {} if no well-formed block is found -- the caller
    must fall back to a document mission, not raise."""
    files: dict[str, str] = {}
    for match in _FILE_BLOCK_PATTERN.finditer(text):
        path = match.group("path").strip()
        if path:
            files[path] = match.group("content")
    return files


def parse_change_summary(text: str) -> str:
    """Lenient extraction of the **Change Summary:** section preceding the
    file blocks. Empty string if missing -- never raises."""
    match = _CHANGE_SUMMARY_PATTERN.search(text)
    return match.group("summary").strip() if match else ""
