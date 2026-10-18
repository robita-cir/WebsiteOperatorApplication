"""Client for any server that speaks the OpenAI chat API: llama.cpp (llama-server), LM Studio, vLLM and similar."""

from __future__ import annotations

from typing import Any

from site_agent.config import LLMSettings
from site_agent.llm.base import LLMError, Message, post_json


class OpenAICompatClient:
    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings

    def chat(self, messages: list[Message], *, json_mode: bool = False) -> str:
        s = self._settings
        payload: dict[str, Any] = {
            "model": s.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": s.temperature,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        data = post_json(f"{s.base_url.rstrip('/')}/v1/chat/completions", payload, s.timeout_s)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("the server answered, but without a chat reply in the expected form") from exc
