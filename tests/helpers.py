"""Test doubles shared by the test modules."""

from __future__ import annotations

from site_agent.llm.base import Message


class FakeLLM:
    """Returns scripted replies in order and records what it was asked."""

    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[list[Message], bool]] = []

    def chat(self, messages: list[Message], *, json_mode: bool = False, schema: dict | None = None) -> str:
        self.calls.append((messages, json_mode))
        if not self._replies:
            raise AssertionError("FakeLLM was asked more times than it was scripted for")
        return self._replies.pop(0)
