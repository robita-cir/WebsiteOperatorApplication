"""The one interface every model backend implements, plus the HTTP call and error handling they share."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from site_agent.calllog import log_call


class LLMError(Exception):
    """The model server could not be reached, or it returned something the agent cannot use."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Message:
    role: str  # "system", "user" or "assistant"
    content: str


class ChatClient(Protocol):
    def chat(self, messages: list[Message], *, json_mode: bool = False, schema: dict[str, Any] | None = None) -> str:
        """Returns the model's reply as text.

        json_mode asks the server to return a JSON object where it can. A schema (a JSON Schema dict) asks the server
        to constrain the reply to that shape; a server that rejects it is retried once in plain json mode.
        """
        ...


# What one request returns: the reply text and the number of tokens the server says it generated, if it says.
Reply = tuple[str, int | None]


def chat_logged(
    *,
    provider: str,
    model: str,
    log_dir: Path | str | None,
    messages: list[Message],
    json_mode: bool,
    schema: dict[str, Any] | None,
    request: Callable[[bool, dict[str, Any] | None], Reply],
) -> str:
    """Runs request(json_mode, schema), retries once without the schema on HTTP 400, and records the call."""
    started = time.monotonic()
    schema_used = schema is not None
    try:
        try:
            text, tokens = request(json_mode, schema)
        except LLMError as exc:
            if schema is None or exc.status != 400:
                raise
            # Many servers predate schema-constrained output and answer 400. Plain json mode still works for them.
            schema_used = False
            text, tokens = request(True, None)
    except LLMError as exc:
        log_call(
            log_dir,
            provider=provider,
            model=model,
            messages=messages,
            json_mode=json_mode,
            schema_used=schema_used,
            seconds=time.monotonic() - started,
            output_tokens=None,
            ok=False,
            error=str(exc),
        )
        raise
    log_call(
        log_dir,
        provider=provider,
        model=model,
        messages=messages,
        json_mode=json_mode,
        schema_used=schema_used,
        seconds=time.monotonic() - started,
        output_tokens=tokens,
        ok=True,
    )
    return text


def post_json(url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise LLMError(f"the server answered HTTP {exc.code}: {detail}", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"could not reach the model server at {url} ({exc.reason}). Is it running?") from exc
    except TimeoutError as exc:
        raise LLMError(f"the model did not answer within {timeout_s:.0f} seconds. Try a smaller model.") from exc
    except json.JSONDecodeError as exc:
        raise LLMError(f"the server's reply was not JSON: {exc}") from exc
