"""Pure text parsing for the Reviewer's output.

Two contracts of very different strength (see app/templates/software_company.py
REVIEWER contract):

- `parse_verdict` reads the trailing "**Verdict:** ..." line. This is the
  ONLY hard contract in the pipeline -- workflow_engine has always relied
  on it (provider-agnostic) to route a Mission to a CEO Decision.
- `parse_decision_sections` leniently extracts the Problem/Recommendation/
  Risk/Impact sections the Reviewer is asked to write before the verdict.
  These are best-effort narrative context for the DecisionCard: any
  subset (including none) may be present, and a missing/malformed section
  must never raise or block the pipeline.
"""

from __future__ import annotations

import re

_SECTION_LABELS = ("Problem", "Recommendation", "Risk", "Impact")


def parse_verdict(text: str) -> str:
    """"approved" or "changes_requested", read from the trailing
    **Verdict:** line. Defaults to "changes_requested" if the line is
    missing or unrecognized -- never silently treat unparseable output as
    an approval."""
    match = re.search(r"\*\*Verdict:\*\*\s*(.+)", text, flags=re.IGNORECASE)
    if not match:
        return "changes_requested"
    verdict = match.group(1).strip().lower()
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
