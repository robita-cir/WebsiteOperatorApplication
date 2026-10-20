"""The one interface every model backend implements, plus the HTTP call and error handling they share."""

from __future__ import annotations

import contextvars
import http.client
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
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


# Set by the job runner, in the job's own thread, while a job's work runs. The clients read them when a call runs, so
# the ChatClient signature stays the same and a call made outside a job (a command line run) checks nothing.
# CANCELLED answers "should this call stop now?"; PROGRESS receives the number of characters received so far.
CANCELLED: contextvars.ContextVar[Callable[[], bool] | None] = contextvars.ContextVar("llm_cancelled", default=None)
PROGRESS: contextvars.ContextVar[Callable[[int], None] | None] = contextvars.ContextVar("llm_progress", default=None)

CANCELLED_TEXT = "cancelled"


def report_progress(characters: int) -> None:
    callback = PROGRESS.get()
    if callback is not None:
        callback(characters)


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


def post_stream(url: str, payload: dict[str, Any], timeout_s: float) -> Iterator[str]:
    """Posts the request and yields the reply one decoded line at a time, as the server sends it.

    Between lines it asks the job's cancel check (if there is one) whether to stop; if so it closes the connection, so
    the server stops generating, and raises LLMError("cancelled"). timeout_s limits the wait for each read, not the
    whole reply, because a reply that keeps arriving is making progress.
    """

    def check_cancelled() -> None:
        stop = CANCELLED.get()
        if stop is not None and stop():
            raise LLMError(CANCELLED_TEXT)

    check_cancelled()
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        # Leaving the with block (a cancel, an error, or the reader dropping this generator) closes the connection.
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            for raw in response:
                check_cancelled()
                yield raw.decode("utf-8", "replace").strip()
            check_cancelled()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise LLMError(f"the server answered HTTP {exc.code}: {detail}", status=exc.code) from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"could not reach the model server at {url} ({exc.reason}). Is it running?") from exc
    except TimeoutError as exc:
        raise LLMError(f"the model did not answer within {timeout_s:.0f} seconds. Try a smaller model.") from exc
    except (http.client.HTTPException, OSError) as exc:  # the connection dropped part way through the reply
        raise LLMError(f"the connection to the model server was lost before the reply was complete ({exc})") from exc


def stream_error(detail: Any) -> LLMError:
    """An error the server reported inside the stream, after it had already answered 200."""
    message = detail.get("message") if isinstance(detail, dict) else detail
    return LLMError(f"the model server reported an error: {str(message)[:300]}")


def parse_stream_json(line: str) -> dict[str, Any]:
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise LLMError(f"the server's reply was not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("the server's reply was not in the expected form")
    return data


def as_token_count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
