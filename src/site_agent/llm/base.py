"""The one interface every model backend implements, plus the HTTP call and error handling they share."""

from __future__ import annotations

import contextvars
import http.client
import json
import socket
import threading
import time
import urllib.parse
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
    """Runs request(json_mode, schema), retries once without the schema on HTTP 400 or 500, and records the call."""
    started = time.monotonic()
    schema_used = schema is not None
    try:
        try:
            text, tokens = request(json_mode, schema)
        except LLMError as exc:
            if schema is None or exc.status not in (400, 500):
                raise
            # Many servers predate schema-constrained output and answer 400. Some runners stop (500) on a schema they
            # cannot compile. Plain json mode still works for both.
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


CANCEL_POLL_SECONDS = 0.2


class _CancelWatcher:
    """Stops a request that is waiting on a silent server.

    A model that is loading or reading a long prompt sends nothing for a while, so a cancel check that only runs when a
    chunk arrives would not run. This thread polls the job's cancel check and, when it fires, shuts the socket down;
    that wakes the blocked read in the request thread (on Linux, macOS and Windows), which then fails and reports the
    cancel. The socket is known early because the connection is opened before the request is sent.
    """

    def __init__(self, stop: Callable[[], bool]) -> None:
        self._stop_check = stop
        self._done = threading.Event()
        self._sock: socket.socket | None = None
        self.fired = False
        self._thread = threading.Thread(target=self._watch, name="llm-cancel-watcher", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def attach(self, sock: socket.socket | None) -> None:
        self._sock = sock

    def finish(self) -> None:
        self._done.set()
        self._thread.join(timeout=2)

    def _watch(self) -> None:
        while not self._done.wait(CANCEL_POLL_SECONDS):
            if not self._stop_check():
                continue
            sock = self._sock
            if sock is None:  # still connecting: the request thread checks the flag as soon as it has connected
                continue
            self.fired = True
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:  # already closed by the request thread, which is fine
                pass
            return


def post_stream(url: str, payload: dict[str, Any], timeout_s: float) -> Iterator[str]:
    """Posts the request and yields the reply one decoded line at a time, as the server sends it.

    The job's cancel check (if there is one) is asked between lines, and a watcher thread asks it while the request is
    waiting for the reply to begin; on a cancel the connection is closed, so the server stops generating, and
    LLMError("cancelled") is raised. timeout_s limits the wait for each read, not the whole reply, because a reply
    that keeps arriving is making progress.
    """

    def check_cancelled() -> None:
        stop = CANCELLED.get()
        if stop is not None and stop():
            raise LLMError(CANCELLED_TEXT)

    check_cancelled()
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise LLMError(f"the model server address {url!r} is not a valid http or https address.")
    connection_class = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(parts.hostname, parts.port, timeout=timeout_s)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    body = json.dumps(payload).encode("utf-8")
    stop = CANCELLED.get()
    watcher = _CancelWatcher(stop) if stop is not None else None
    if watcher is not None:
        watcher.start()
    connected = False
    response: http.client.HTTPResponse | None = None
    try:
        # Leaving this try (a cancel, an error, or the reader dropping this generator) closes the connection.
        try:
            connection.connect()
            connected = True
            if watcher is not None:
                watcher.attach(connection.sock)
            check_cancelled()
            connection.request("POST", path, body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status >= 300:
                detail = response.read(300).decode("utf-8", "replace")
                raise LLMError(f"the server answered HTTP {response.status}: {detail}", status=response.status)
            while True:
                raw = response.readline()
                if not raw:
                    break
                check_cancelled()
                yield raw.decode("utf-8", "replace").strip()
            check_cancelled()
        except LLMError:
            raise
        except TimeoutError as exc:
            if watcher is not None and watcher.fired:
                raise LLMError(CANCELLED_TEXT) from exc
            if not connected:
                raise LLMError(f"could not reach the model server at {url} (timed out). Is it running?") from exc
            raise LLMError(f"the model did not answer within {timeout_s:.0f} seconds. Try a smaller model.") from exc
        except (http.client.HTTPException, OSError) as exc:
            if watcher is not None and watcher.fired:
                raise LLMError(CANCELLED_TEXT) from exc
            if not connected:
                raise LLMError(f"could not reach the model server at {url} ({exc}). Is it running?") from exc
            # the connection dropped part way through the reply
            raise LLMError(
                f"the connection to the model server was lost before the reply was complete ({exc})"
            ) from exc
    finally:
        if watcher is not None:
            watcher.finish()
        # A reply that ends when the server closes (HTTP/1.0) leaves the socket owned by the response, so closing the
        # connection alone would not hang up on a server that is still generating.
        if response is not None:
            response.close()
        connection.close()


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
