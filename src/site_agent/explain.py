"""Plain sentences for a failed site check. Matching is on known phrases in the build's output; no model is used."""

from __future__ import annotations

import re

GENERIC = "The check failed. The details below show what the build said."

# A shell's "not found" message that names npm or node, whichever order the words come in.
_TOOL = r"\b(?:npm|node)\b"
_NOT_FOUND = r"(?:command not found|not recognized)"
_MISSING_TOOL = re.compile(rf"{_TOOL}[^\n]*{_NOT_FOUND}|{_NOT_FOUND}[^\n]*{_TOOL}", re.IGNORECASE)

# (test, sentence), in the order the sentences are shown: the machine first, then the content.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_MISSING_TOOL, "The check tool is missing. Install Node.js 22.12 or newer, then try again."),
    (
        re.compile(r"Cannot find module|ERR_MODULE_NOT_FOUND"),
        "The website's packages look incomplete. Run npm install in the website folder, then try again.",
    ),
    (re.compile(r"EADDRINUSE"), "Another program is using a port the build needs. Close it and try again."),
    (
        re.compile(r"InvalidContentEntryDataError|does not match", re.IGNORECASE),
        "A content file has a field that does not match its rules. The message below names the file and the field.",
    ),
    (
        re.compile(r"is required", re.IGNORECASE),
        "A required field is missing in a content file. The message below names it.",
    ),
    (re.compile(r"ENOENT"), "A file the build needs is missing. The message below names it."),
)


def explain_check(output: str) -> list[str]:
    """Plain sentences for the known failures in a check's output, or one generic sentence when none is known."""
    found = [sentence for pattern, sentence in _PATTERNS if pattern.search(output or "")]
    return found or [GENERIC]
