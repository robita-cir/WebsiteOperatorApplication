"""Client for a local Ollama server, through its /api/chat endpoint (default http://localhost:11434)."""

from __future__ import annotations

from typing import Any

from site_agent.config import LLMSettings
from site_agent.llm.base import LLMError, Message, post_json


class OllamaClient:
    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings

    def chat(self, messages: list[Message], *, json_mode: bool = False) -> str:
        s = self._settings
        payload: dict[str, Any] = {
            "model": s.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": s.temperature, "num_ctx": s.context_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        try:
            data = post_json(f"{s.base_url.rstrip('/')}/api/chat", payload, s.timeout_s)
        except LLMError as exc:
            if exc.status == 404:
                raise LLMError(
                    f"model '{s.model}' was not found. If it is not installed, run: ollama pull {s.model}"
                ) from exc
            raise
        content = data.get("message", {}).get("content")
        if not isinstance(content, str):
            raise LLMError("Ollama answered without any text.")
        return content
