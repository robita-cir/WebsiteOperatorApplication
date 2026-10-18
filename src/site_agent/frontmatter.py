"""Reads and writes Markdown files that start with a YAML frontmatter block (the lines between two '---' lines).

Changes to an existing file are made line by line, so comments, quoting and the order of other keys stay as they were.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import yaml

FENCE = "---"


@dataclass(frozen=True)
class Document:
    data: dict[str, Any]
    body: str


def _closing_fence(lines: list[str]) -> int:
    """Index of the second '---' line. Raises ValueError when the file has no frontmatter block."""
    if not lines or lines[0].strip() != FENCE:
        raise ValueError("the file does not start with a '---' frontmatter block")
    for index in range(1, len(lines)):
        if lines[index].strip() == FENCE:
            return index
    raise ValueError("the frontmatter block is not closed by a second '---' line")


def parse_document(text: str) -> Document:
    lines = text.split("\n")
    close = _closing_fence(lines)
    try:
        data = yaml.safe_load("\n".join(lines[1:close])) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"the frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("the frontmatter must be 'key: value' lines")
    return Document(data=data, body="\n".join(lines[close + 1 :]).removeprefix("\n"))


def format_scalar(value: Any) -> str:
    """One value as YAML. Strings are double-quoted, dates are written bare (YYYY-MM-DD), None becomes null."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        # A YAML flow sequence. JSON strings are valid YAML, so json quoting is safe here.
        return "[" + ", ".join(format_scalar(item) for item in value) + "]"
    raise TypeError(f"cannot write a {type(value).__name__} into frontmatter")


def render_document(data: Mapping[str, Any], body: str) -> str:
    """A complete new file. Keys with None are left out."""
    lines = [FENCE]
    lines += [f"{key}: {format_scalar(value)}" for key, value in data.items() if value is not None]
    lines.append(FENCE)
    text = "\n".join(lines) + "\n"
    body = body.strip()
    return f"{text}\n{body}\n" if body else text


def set_body(text: str, body: str) -> str:
    """Replaces the Markdown body and leaves the top block exactly as it was. An unchanged body gives the same text."""
    lines = text.split("\n")
    close = _closing_fence(lines)
    head = "\n".join(lines[: close + 1])
    body = body.strip()
    return f"{head}\n\n{body}\n" if body else f"{head}\n"


def set_frontmatter_values(text: str, changes: Mapping[str, Any]) -> str:
    """Changes single keys of an existing file and leaves every other line as it is.

    A value of None removes the key. A key that is not there yet is added at the end of the block.
    """
    lines = text.split("\n")
    close = _closing_fence(lines)
    head, block, tail = lines[:1], lines[1:close], lines[close:]
    for key, value in changes.items():
        pattern = re.compile(rf"^{re.escape(key)}\s*:")
        index = next((i for i, line in enumerate(block) if pattern.match(line)), None)
        replacement = [] if value is None else [f"{key}: {format_scalar(value)}"]
        if index is None:
            block.extend(replacement)
            continue
        end = index + 1
        while end < len(block) and block[end][:1] in (" ", "\t"):  # continuation lines of a multi-line value
            end += 1
        block[index:end] = replacement
    return "\n".join(head + block + tail)
