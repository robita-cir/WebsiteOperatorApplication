"""The two HTTP backends, tested against a tiny local server that records what it was sent."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from streamserver import as_stream

from site_agent.config import LLMSettings
from site_agent.llm import LLMError, Message, make_client
from site_agent.llm.ollama import OllamaClient
from site_agent.llm.openai_compat import OpenAICompatClient


class _Server:
    def __init__(self, reply: dict, status: int = 200) -> None:
        self.received: list[tuple[str, dict]] = []
        received, canned, code = self.received, reply, status

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 (http.server naming)
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                received.append((self.path, body))
                # The clients ask for a stream, so a good reply is sent as one; an error is a plain JSON body.
                if code == 200:
                    payload, kind = as_stream(self.path, canned)
                else:
                    payload, kind = json.dumps(canned).encode("utf-8"), "application/json"
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):  # keep test output quiet
                pass

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_port}"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def messages():
    return [Message("system", "be brief"), Message("user", "hello")]


def test_ollama_sends_the_chat_request_and_reads_the_reply(messages):
    server = _Server({"message": {"role": "assistant", "content": '{"ok": true}'}})
    try:
        client = OllamaClient(LLMSettings(provider="ollama", model="m1", base_url=server.url, temperature=0.2))
        assert client.chat(messages, json_mode=True) == '{"ok": true}'
    finally:
        server.close()
    path, body = server.received[0]
    assert path == "/api/chat"
    assert body["model"] == "m1" and body["stream"] is True and body["format"] == "json"
    assert body["options"]["temperature"] == 0.2
    assert body["messages"][1] == {"role": "user", "content": "hello"}


def test_openai_compatible_server_gets_json_mode_and_reads_choices(messages):
    server = _Server({"choices": [{"message": {"role": "assistant", "content": "{}"}}]})
    try:
        client = make_client(LLMSettings(provider="openai", model="local", base_url=server.url))
        assert isinstance(client, OpenAICompatClient)
        assert client.chat(messages, json_mode=True) == "{}"
    finally:
        server.close()
    path, body = server.received[0]
    assert path == "/v1/chat/completions"
    assert body["response_format"] == {"type": "json_object"}


def test_a_missing_model_gets_the_ollama_pull_hint(messages):
    server = _Server({"error": 'model "nope" not found'}, status=404)
    try:
        client = OllamaClient(LLMSettings(model="nope", base_url=server.url))
        with pytest.raises(LLMError, match="ollama pull nope"):
            client.chat(messages)
    finally:
        server.close()


def test_an_unreachable_server_says_so(messages):
    server = _Server({})
    url = server.url
    server.close()  # nothing listens on this port any more
    with pytest.raises(LLMError, match="Is it running"):
        OllamaClient(LLMSettings(base_url=url, timeout_s=5)).chat(messages)


def test_unknown_provider_is_rejected():
    from site_agent.errors import SiteAgentError

    with pytest.raises(SiteAgentError, match="unknown llm provider"):
        make_client(LLMSettings(provider="carrier-pigeon"))
