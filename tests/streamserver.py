"""Test servers that answer the way the model servers do when asked to stream: a body sent in pieces.

Used by the streaming tests, and by the older client tests, whose canned replies are converted with as_stream.
"""

from __future__ import annotations

import json
import select
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def as_stream(path: str, body: dict[str, Any]) -> tuple[bytes, str]:
    """A canned non-streamed reply, rewritten as the stream the same server would send, and its content type."""
    if path == "/api/chat":
        return (json.dumps({**body, "done": True}) + "\n").encode("utf-8"), "application/x-ndjson"
    events = []
    if "choices" in body:
        content = body["choices"][0]["message"]["content"]
        events.append({"choices": [{"delta": {"content": content}}]})
    if "usage" in body:
        events.append({"choices": [], "usage": body["usage"]})
    lines = [f"data: {json.dumps(event)}\n\n" for event in events] + ["data: [DONE]\n\n"]
    return "".join(lines).encode("utf-8"), "text/event-stream"


def ollama_chunks(*texts: str, eval_count: int | None = 7) -> list[bytes]:
    lines = [json.dumps({"message": {"role": "assistant", "content": t}, "done": False}) + "\n" for t in texts]
    final: dict[str, Any] = {"message": {"role": "assistant", "content": ""}, "done": True}
    if eval_count is not None:
        final["eval_count"] = eval_count
    lines.append(json.dumps(final) + "\n")
    return [line.encode("utf-8") for line in lines]


def openai_chunks(*texts: str, usage: dict[str, int] | None = None) -> list[bytes]:
    events = [{"choices": [{"delta": {"content": t}}]} for t in texts]
    if usage is not None:
        events.append({"choices": [], "usage": usage})
    return [f"data: {json.dumps(e)}\n\n".encode() for e in events] + [b"data: [DONE]\n\n"]


class StreamServer:
    """Sends its chunks one at a time with a pause between them, and notices when the client hangs up.

    With endless=True it keeps repeating the last chunk until the client closes, which is how a model that is still
    generating looks to a client that cancels.
    """

    def __init__(self, chunks: list[bytes], *, delay: float = 0.05, endless: bool = False, status: int = 200) -> None:
        self.received: list[dict[str, Any]] = []
        self.chunks_sent = 0
        self.closed = threading.Event()  # set when the handler sees the client's end of the connection close
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 (http.server naming)
                outer.received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(status)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()  # HTTP/1.0: the body runs until this side closes
                sequence = iter(chunks)
                last = b""
                for _ in range(2000):
                    chunk = next(sequence, None)
                    if chunk is None:
                        if not endless:
                            return
                        chunk = last
                    last = chunk
                    try:
                        self.wfile.write(chunk)
                    except OSError:
                        outer.closed.set()
                        return
                    outer.chunks_sent += 1
                    if outer._hung_up(self.connection, delay):
                        outer.closed.set()
                        return

            def log_message(self, *args):
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self._httpd.server_port}"
        threading.Thread(target=self._httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    @staticmethod
    def _hung_up(conn: socket.socket, wait: float) -> bool:
        """Waits up to `wait` seconds; true if the client closed its end in that time."""
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            readable, _, _ = select.select([conn], [], [], max(0.0, deadline - time.monotonic()))
            if readable:
                try:
                    if conn.recv(1, socket.MSG_PEEK) == b"":
                        return True
                except OSError:
                    return True
        return False

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


class SilentServer:
    """Accepts a connection, reads the request, and then says nothing, like a model that is still loading.

    `closed` is set when the client's end of the connection closes; `got_request` when the request has arrived.
    """

    def __init__(self, silence: float = 30.0) -> None:
        self.silence = silence
        self.got_request = threading.Event()
        self.closed = threading.Event()
        self._listener = socket.socket()
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(5)
        self.url = f"http://127.0.0.1:{self._listener.getsockname()[1]}"
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        try:
            conn, _ = self._listener.accept()
        except OSError:
            return
        with conn:
            deadline = time.monotonic() + self.silence
            while time.monotonic() < deadline:
                readable, _, _ = select.select([conn], [], [], 0.05)
                if not readable:
                    continue
                try:
                    data = conn.recv(65536)
                except OSError:
                    data = b""
                if data == b"":
                    self.closed.set()
                    return
                self.got_request.set()  # request bytes only; the server never answers them

    def close(self) -> None:
        self._listener.close()
