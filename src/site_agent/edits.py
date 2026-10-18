"""Search/replace edit blocks: how the model describes a change to an existing file.

Each block names text that must appear exactly once in the file, and the text to put in its place:

    <<<<<<< SEARCH
    old text, copied from the file
    =======
    new text
    >>>>>>> REPLACE

The tool applies a block only when its search text is found exactly once. Anything else is reported, not guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NO_CHANGE = "NO_CHANGE"

_BLOCK = re.compile(
    r"^<{5,9} SEARCH[ \t]*\n(?P<search>.*?)^={5,9}[ \t]*\n(?P<replace>.*?)^>{5,9} REPLACE[ \t]*$",
    re.DOTALL | re.MULTILINE,
)
_PROBLEMS = {
    "missing": "its SEARCH text was not found in the file",
    "ambiguous": "its SEARCH text appears more than once, so it was not applied",
    "empty": "its SEARCH text was empty",
}


@dataclass(frozen=True)
class EditBlock:
    search: str
    replace: str


@dataclass(frozen=True)
class EditResult:
    text: str
    applied: int
    failures: list[str]


def parse_edit_blocks(reply: str) -> list[EditBlock]:
    return [EditBlock(m.group("search"), m.group("replace")) for m in _BLOCK.finditer(reply)]


def _place(text: str, search: str, replace: str) -> tuple[str, str]:
    """Returns (new text, status). Status is 'ok', 'missing', 'ambiguous' or 'empty'.

    The first try uses the text exactly as given. The second drops the newlines at the ends, because models often
    add or lose a trailing newline.
    """
    for candidate_search, candidate_replace in ((search, replace), (search.strip("\n"), replace.strip("\n"))):
        if not candidate_search.strip():
            return text, "empty"
        count = text.count(candidate_search)
        if count == 1:
            return text.replace(candidate_search, candidate_replace, 1), "ok"
        if count > 1:
            return text, "ambiguous"
    return text, "missing"


def apply_edit_blocks(text: str, blocks: list[EditBlock]) -> EditResult:
    applied = 0
    failures: list[str] = []
    for number, block in enumerate(blocks, start=1):
        text, status = _place(text, block.search, block.replace)
        if status == "ok":
            applied += 1
        else:
            failures.append(f"edit {number}: {_PROBLEMS[status]}")
    return EditResult(text=text, applied=applied, failures=failures)
