"""Schema-constrained output, the output cap, the 400 fallback and the call log, against a local scripted server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from streamserver import as_stream

from site_agent.calllog import log_call
from site_agent.config import LLMSettings
from site_agent.llm import LLMError, Message, make_client
from site_agent.llm.ollama import OllamaClient
from site_agent.llm.openai_compat import OpenAICompatClient

SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}
SECRET = "Maya Lin studies grasping at the zebrafish bench"

OLLAMA_OK = (200, {"message": {"role": "assistant", "content": '{"title": "x"}'}, "eval_count": 42})
OPENAI_OK = (200, {"choices": [{"message": {"content": '{"title": "x"}'}}], "usage": {"completion_tokens": 17}})
REJECTED = (400, {"error": "unsupported response_format"})


class _Server:
    """Answers each POST with the next scripted (status, body) pair, and records what it was sent."""

    def __init__(self, *script: tuple[int, dict]) -> None:
        self.received: list[dict] = []
        received, queue = self.received, list(script)

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 (http.server naming)
                received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                code, body = queue.pop(0)
                # The clients ask for a stream, so a good reply is sent as one; an error is a plain JSON body.
                if code == 200:
                    payload, kind = as_stream(self.path, body)
                else:
                    payload, kind = json.dumps(body).encode("utf-8"), "application/json"
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_port}"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture
def server_for():
    servers = []

    def start(*script):
        servers.append(_Server(*script))
        return servers[-1]

    yield start
    for s in servers:
        s.close()


@pytest.fixture
def messages():
    return [Message("system", "be brief"), Message("user", SECRET)]


def _ollama(server, log_dir=None, **kw):
    return OllamaClient(LLMSettings(provider="ollama", model="m1", base_url=server.url, **kw), log_dir)


def _openai(server, log_dir=None, **kw):
    return OpenAICompatClient(LLMSettings(provider="openai", model="m1", base_url=server.url, **kw), log_dir)


def test_defaults_are_a_longer_timeout_and_a_token_cap():
    s = LLMSettings()
    assert s.timeout_s == 600.0 and s.max_output_tokens == 1200


def test_ollama_sends_the_schema_as_format_and_the_token_cap(server_for, messages):
    server = server_for(OLLAMA_OK)
    assert _ollama(server, max_output_tokens=300).chat(messages, json_mode=True, schema=SCHEMA) == '{"title": "x"}'
    body = server.received[0]
    assert body["format"] == SCHEMA
    assert body["options"]["num_predict"] == 300


def test_ollama_without_a_schema_keeps_plain_json_mode(server_for, messages):
    server = server_for(OLLAMA_OK, OLLAMA_OK)
    client = _ollama(server)
    client.chat(messages, json_mode=True)
    client.chat(messages)
    assert server.received[0]["format"] == "json"
    assert "format" not in server.received[1]
    assert server.received[0]["options"]["num_predict"] == 1200


def test_openai_sends_the_schema_as_response_format_and_max_tokens(server_for, messages):
    server = server_for(OPENAI_OK)
    assert _openai(server, max_output_tokens=250).chat(messages, schema=SCHEMA) == '{"title": "x"}'
    body = server.received[0]
    assert body["response_format"] == {"type": "json_schema", "json_schema": {"name": "record", "schema": SCHEMA}}
    assert body["max_tokens"] == 250


def test_openai_without_a_schema_keeps_json_object_mode(server_for, messages):
    server = server_for(OPENAI_OK)
    _openai(server).chat(messages, json_mode=True)
    assert server.received[0]["response_format"] == {"type": "json_object"}
    assert server.received[0]["max_tokens"] == 1200


def test_ollama_falls_back_to_plain_json_when_the_schema_is_rejected(server_for, messages):
    server = server_for(REJECTED, OLLAMA_OK)
    assert _ollama(server).chat(messages, schema=SCHEMA) == '{"title": "x"}'
    assert [b["format"] for b in server.received] == [SCHEMA, "json"]


def test_openai_falls_back_to_json_object_when_the_schema_is_rejected(server_for, messages):
    server = server_for(REJECTED, OPENAI_OK)
    assert _openai(server).chat(messages, schema=SCHEMA) == '{"title": "x"}'
    assert [b["response_format"]["type"] for b in server.received] == ["json_schema", "json_object"]


def test_the_fallback_happens_once_and_a_second_400_is_an_error(server_for, messages):
    server = server_for(REJECTED, REJECTED)
    with pytest.raises(LLMError) as caught:
        _openai(server).chat(messages, schema=SCHEMA)
    assert caught.value.status == 400
    assert len(server.received) == 2


def test_a_400_without_a_schema_is_not_retried(server_for, messages):
    server = server_for(REJECTED)
    with pytest.raises(LLMError):
        _openai(server).chat(messages, json_mode=True)
    assert len(server.received) == 1


def test_other_errors_are_not_retried_with_a_schema(server_for, messages):
    server = server_for((503, {"error": "busy"}))
    with pytest.raises(LLMError):
        _ollama(server).chat(messages, schema=SCHEMA)
    assert len(server.received) == 1


def _entries(log_dir):
    lines = (log_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_the_call_log_records_counts_and_a_hash_but_no_text(server_for, messages, tmp_path):
    server = server_for(OLLAMA_OK, OPENAI_OK)
    _ollama(server, tmp_path / "state").chat(messages, json_mode=True, schema=SCHEMA)
    _openai(server, tmp_path / "state").chat(messages, json_mode=True)
    raw = (tmp_path / "state" / "calls.jsonl").read_text(encoding="utf-8")
    assert SECRET not in raw and "be brief" not in raw and "zebrafish" not in raw
    first, second = _entries(tmp_path / "state")
    assert first["provider"] == "ollama" and first["model"] == "m1"
    assert first["json_mode"] is True and first["schema_used"] is True
    assert first["output_tokens"] == 42 and second["output_tokens"] == 17
    assert first["ok"] is True and first["error"] is None
    assert first["prompt_chars"] == len("be brief") + len(SECRET)
    assert len(first["prompt_sha256"]) == 64 and first["prompt_sha256"] == second["prompt_sha256"]
    assert isinstance(first["seconds"], float) and first["time"]
    assert second["schema_used"] is False


def test_the_hash_tells_prompt_versions_apart(server_for, tmp_path):
    server = server_for(OLLAMA_OK, OLLAMA_OK)
    client = _ollama(server, tmp_path)
    client.chat([Message("user", "version one")])
    client.chat([Message("user", "version two")])
    a, b = _entries(tmp_path)
    assert a["prompt_sha256"] != b["prompt_sha256"]


def test_the_log_notes_a_fallback_and_a_failure_without_message_text(server_for, messages, tmp_path):
    server = server_for(REJECTED, OLLAMA_OK, (500, {"error": "boom"}))
    client = _ollama(server, tmp_path)
    client.chat(messages, schema=SCHEMA)
    with pytest.raises(LLMError):
        client.chat(messages)
    ok_entry, failed = _entries(tmp_path)
    assert ok_entry["ok"] is True and ok_entry["schema_used"] is False
    assert failed["ok"] is False and failed["output_tokens"] is None and "500" in failed["error"]
    assert SECRET not in (tmp_path / "calls.jsonl").read_text(encoding="utf-8")


def test_a_missing_token_count_is_null(server_for, messages, tmp_path):
    server = server_for((200, {"choices": [{"message": {"content": "{}"}}]}))
    _openai(server, tmp_path).chat(messages)
    assert _entries(tmp_path)[0]["output_tokens"] is None


def test_make_client_passes_the_log_folder_through(server_for, messages, tmp_path):
    server = server_for(OLLAMA_OK)
    make_client(LLMSettings(base_url=server.url), tmp_path / "logs").chat(messages)
    assert (tmp_path / "logs" / "calls.jsonl").exists()


def test_no_log_folder_writes_nothing(server_for, messages, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = server_for(OLLAMA_OK)
    _ollama(server, None).chat(messages)
    assert list(tmp_path.iterdir()) == []


def test_a_log_folder_that_cannot_be_written_does_not_break_the_call(server_for, messages, tmp_path):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("a file where the folder should be")
    server = server_for(OLLAMA_OK)
    assert _ollama(server, blocker / "inside").chat(messages) == '{"title": "x"}'


def test_log_call_itself_swallows_write_errors(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    log_call(
        blocker / "sub",
        provider="ollama",
        model="m",
        messages=[Message("user", "hi")],
        json_mode=False,
        schema_used=False,
        seconds=0.1,
        output_tokens=None,
        ok=True,
    )


def test_a_runner_that_stops_on_a_schema_falls_back_to_plain_json(server_for, messages):
    # A 500 is what the local runner answers when it cannot compile a schema; the same request without one works.
    server = server_for((500, {"error": "model runner has unexpectedly stopped"}), OLLAMA_OK)
    assert _ollama(server).chat(messages, schema=SCHEMA) == '{"title": "x"}'
    assert [b["format"] for b in server.received] == [SCHEMA, "json"]
