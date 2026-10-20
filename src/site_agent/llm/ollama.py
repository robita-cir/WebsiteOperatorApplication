"""Client for a local Ollama server, through its /api/chat endpoint (default http://localhost:11434)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from site_agent.config import LLMSettings
from site_agent.llm.base import LLMError, Message, Reply, chat_logged, post_json


class OllamaClient:
    def __init__(self, settings: LLMSettings, log_dir: Path | str | None = None) -> None:
        self._settings = settings
        self._log_dir = log_dir

    def chat(self, messages: list[Message], *, json_mode: bool = False, schema: dict[str, Any] | None = None) -> str:
        return chat_logged(
            provider="ollama",
            model=self._settings.model,
            log_dir=self._log_dir,
            messages=messages,
            json_mode=json_mode,
            schema=schema,
            request=lambda mode, shape: self._request(messages, mode, shape),
        )

    def _request(self, messages: list[Message], json_mode: bool, schema: dict[str, Any] | None) -> Reply:
        s = self._settings
        payload: dict[str, Any] = {
            "model": s.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            # num_predict caps the reply so a model that fails to stop cannot run until the timeout.
            "options": {"temperature": s.temperature, "num_ctx": s.context_tokens, "num_predict": s.max_output_tokens},
        }
        if schema is not None:
            payload["format"] = schema
        elif json_mode:
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
        tokens = data.get("eval_count")
        return content, tokens if isinstance(tokens, int) and not isinstance(tokens, bool) else None
