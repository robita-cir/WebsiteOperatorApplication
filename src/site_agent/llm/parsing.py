"""Reads the answers small models give: plain JSON, JSON inside a code fence, or JSON after some chatter."""

from __future__ import annotations

import json
import re

_REASONING = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def strip_reasoning(reply: str) -> str:
    """Removes the thinking block that some models (qwen3, deepseek-r1) print before the answer."""
    return _REASONING.sub("", reply).strip()


def extract_json_object(reply: str) -> dict:
    """The first JSON object in the reply. Raises ValueError with a short reason when there is none."""
    text = strip_reasoning(reply)
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end < start:
            raise ValueError("there is no JSON object in the reply") from None
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"the JSON is invalid ({exc.msg})") from exc
    if not isinstance(value, dict):
        raise ValueError("the reply is JSON, but not a JSON object")
    return value
