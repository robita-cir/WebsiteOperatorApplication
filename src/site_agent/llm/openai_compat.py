"""Client for any server that speaks the OpenAI chat API: llama.cpp (llama-server), LM Studio, vLLM and similar."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from site_agent.config import LLMSettings
from site_agent.llm.base import LLMError, Message, Reply, chat_logged, post_json


class OpenAICompatClient:
    def __init__(self, settings: LLMSettings, log_dir: Path | str | None = None) -> None:
        self._settings = settings
        self._log_dir = log_dir

    def chat(self, messages: list[Message], *, json_mode: bool = False, schema: dict[str, Any] | None = None) -> str:
        return chat_logged(
            provider="openai",
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
            "temperature": s.temperature,
            "max_tokens": s.max_output_tokens,
            "stream": False,
        }
        if schema is not None:
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "record", "schema": schema}}
        elif json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = post_json(f"{s.base_url.rstrip('/')}/v1/chat/completions", payload, s.timeout_s)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("the server answered, but without a chat reply in the expected form") from exc
        usage = data.get("usage")
        tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
        return content, tokens if isinstance(tokens, int) and not isinstance(tokens, bool) else None
