"""Client for any server that speaks the OpenAI chat API: llama.cpp (llama-server), LM Studio, vLLM and similar."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from typing import Any

from site_agent.config import LLMSettings
from site_agent.llm.base import (
    LLMError,
    Message,
    Reply,
    as_token_count,
    chat_logged,
    parse_stream_json,
    post_stream,
    report_progress,
    stream_error,
)


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
            # Streaming lets a cancel close the connection, so the server stops generating, and shows progress.
            "stream": True,
        }
        if schema is not None:
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "record", "schema": schema}}
        elif json_mode:
            payload["response_format"] = {"type": "json_object"}
        parts: list[str] = []
        received = 0
        tokens: int | None = None
        finished = False
        # The reply is server-sent events: lines "data: {json}", ending with "data: [DONE]". Other lines (comments that
        # keep the connection alive, event names) carry nothing for us.
        url = f"{s.base_url.rstrip('/')}/v1/chat/completions"
        with closing(post_stream(url, payload, s.timeout_s)) as lines:
            for line in lines:
                if not line.startswith("data:"):
                    continue
                body = line[len("data:") :].strip()
                if body == "[DONE]":
                    finished = True
                    break
                data = parse_stream_json(body)
                if "error" in data:
                    raise stream_error(data["error"])
                usage = data.get("usage")
                if isinstance(usage, dict) and as_token_count(usage.get("completion_tokens")) is not None:
                    tokens = as_token_count(usage["completion_tokens"])
                choices = data.get("choices")
                first = choices[0] if isinstance(choices, list) and choices else None  # a usage-only chunk has none
                delta = first.get("delta") if isinstance(first, dict) else None
                content = delta.get("content") if isinstance(delta, dict) else None
                if isinstance(content, str) and content:
                    parts.append(content)
                    received += len(content)
                    report_progress(received)
        if not finished:
            raise LLMError("the model's reply stopped before it was complete.")
        if not parts:
            raise LLMError("the server answered, but without a chat reply in the expected form")
        return "".join(parts), tokens
