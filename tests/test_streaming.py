"""Streamed model replies, and a cancel that closes the connection so the model server stops generating."""

import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from streamserver import StreamServer, ollama_chunks, openai_chunks

from site_agent.config import LLMSettings
from site_agent.drafting import JobRunner
from site_agent.llm import LLMError, Message
from site_agent.llm.base import CANCELLED, PROGRESS, report_progress
from site_agent.llm.ollama import OllamaClient
from site_agent.llm.openai_compat import OpenAICompatClient
from site_agent.web.app import create_app

MESSAGES = [Message("user", "hello")]
QUICK = 3.0  # seconds a cancel may take; the server pauses 0.05 s between chunks, so a real stop needs far less


@pytest.fixture
def servers():
    started: list[StreamServer] = []

    def start(chunks, **kw) -> StreamServer:
        started.append(StreamServer(chunks, **kw))
        return started[-1]

    yield start
    for server in started:
        server.close()


def _ollama(server, log_dir=None):
    return OllamaClient(LLMSettings(provider="ollama", model="m1", base_url=server.url, timeout_s=10), log_dir)


def _openai(server, log_dir=None):
    return OpenAICompatClient(LLMSettings(provider="openai", model="m1", base_url=server.url, timeout_s=10), log_dir)


def _entries(log_dir: Path) -> list[dict]:
    return [json.loads(line) for line in (log_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()]


# --- assembling the reply -------------------------------------------------------------------------------


def test_ollama_reply_is_assembled_from_the_chunks_and_the_token_count_comes_from_the_last(servers, tmp_path):
    server = servers(ollama_chunks('{"ti', 'tle": ', '"x"}', eval_count=42))
    assert _ollama(server, tmp_path).chat(MESSAGES, json_mode=True) == '{"title": "x"}'
    assert server.received[0]["stream"] is True and server.received[0]["format"] == "json"
    (entry,) = _entries(tmp_path)  # exactly one log line for the call
    assert entry["ok"] is True and entry["output_tokens"] == 42


def test_openai_reply_is_assembled_from_the_events_and_tokens_are_null_without_usage(servers, tmp_path):
    server = servers(openai_chunks("Hel", "lo ", "there"))
    assert _openai(server, tmp_path).chat(MESSAGES) == "Hello there"
    assert server.received[0]["stream"] is True
    (entry,) = _entries(tmp_path)
    assert entry["ok"] is True and entry["output_tokens"] is None


def test_openai_usage_chunk_gives_the_token_count(servers, tmp_path):
    server = servers(openai_chunks("a", "b", usage={"completion_tokens": 9}))
    assert _openai(server, tmp_path).chat(MESSAGES) == "ab"
    assert _entries(tmp_path)[0]["output_tokens"] == 9


def test_openai_ignores_keep_alive_comments_and_empty_role_deltas(servers):
    chunks = [
        b": keep-alive\n\n",
        b'data: {"choices": [{"delta": {"role": "assistant"}}]}\n\n',
        b'data: {"choices": [{"delta": {"content": "ok"}}]}\n\n',
        b"data: [DONE]\n\n",
    ]
    assert _openai(servers(chunks)).chat(MESSAGES) == "ok"


@pytest.mark.parametrize(
    ("client_for", "chunks"),
    [(_ollama, ollama_chunks("par", "tial")[:-1]), (_openai, openai_chunks("par")[:-1])],
    ids=["ollama", "openai"],
)
def test_a_stream_that_stops_before_its_end_marker_is_an_error(servers, client_for, chunks, tmp_path):
    with pytest.raises(LLMError, match="stopped before it was complete"):
        client_for(servers(chunks), tmp_path).chat(MESSAGES)
    assert _entries(tmp_path)[0]["ok"] is False


def test_an_error_sent_inside_the_stream_is_reported(servers):
    server = servers([b'{"error": "model runner crashed"}\n'])
    with pytest.raises(LLMError, match="model runner crashed"):
        _ollama(server).chat(MESSAGES)


def test_progress_counts_the_characters_received_so_far(servers):
    seen: list[int] = []
    token = PROGRESS.set(seen.append)
    try:
        _ollama(servers(ollama_chunks("abc", "de", "f"))).chat(MESSAGES)
    finally:
        PROGRESS.reset(token)
    assert seen == [3, 5, 6]


def test_without_a_job_nothing_is_checked_or_reported():
    report_progress(5)  # no callback set: must not raise
    assert CANCELLED.get() is None and PROGRESS.get() is None


# --- cancelling ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("client_for", "chunks"),
    [(_ollama, ollama_chunks("word ")[:-1]), (_openai, openai_chunks("word ")[:-1])],
    ids=["ollama", "openai"],
)
def test_a_cancel_during_streaming_closes_the_connection_and_raises_cancelled(servers, client_for, chunks, tmp_path):
    server = servers(chunks, endless=True)
    cancelled = threading.Event()
    received = []

    def progress(characters: int) -> None:
        received.append(characters)
        if characters >= 15:  # a few chunks in, the operator presses Cancel
            cancelled.set()

    cancel_token = CANCELLED.set(cancelled.is_set)
    progress_token = PROGRESS.set(progress)
    started = time.monotonic()
    try:
        with pytest.raises(LLMError) as caught:
            client_for(server, tmp_path).chat(MESSAGES)
    finally:
        CANCELLED.reset(cancel_token)
        PROGRESS.reset(progress_token)
    assert str(caught.value) == "cancelled"
    assert time.monotonic() - started < QUICK
    assert server.closed.wait(QUICK), "the server never saw the connection close"
    assert server.chunks_sent < 50  # it was stopped, not left to run to the end
    (entry,) = _entries(tmp_path)  # still exactly one log line, marked as a failure with the reason
    assert entry["ok"] is False and entry["error"] == "cancelled"


def test_a_job_cancelled_before_the_call_starts_never_connects(servers):
    server = servers(ollama_chunks("x"))
    token = CANCELLED.set(lambda: True)
    try:
        with pytest.raises(LLMError, match="cancelled"):
            _ollama(server).chat(MESSAGES)
    finally:
        CANCELLED.reset(token)
    assert server.received == []


# --- the job runner --------------------------------------------------------------------------------------


def _wait_for(condition, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_cancelling_a_job_stops_the_model_and_does_not_run_finish(servers):
    server = servers(ollama_chunks("word ")[:-1], endless=True)
    client = _ollama(server)
    runner = JobRunner()
    finished = []
    job_id = runner.start(lambda: client.chat(MESSAGES), lambda text: finished.append(text) or "saved")
    assert _wait_for(lambda: runner.status(job_id)["characters"] > 0)
    assert runner.status(job_id)["state"] == "running"
    runner.cancel(job_id)
    assert server.closed.wait(QUICK), "cancelling the job did not close the connection to the model"
    assert _wait_for(lambda: runner._jobs[job_id]["state"] != "running")
    status = runner.status(job_id)
    assert status["state"] == "cancelled" and status["error"] is None and status["result"] is None
    assert finished == []


def test_a_job_that_finishes_normally_runs_finish_once(servers):
    server = servers(ollama_chunks("one ", "two"))
    client = _ollama(server)
    runner = JobRunner()
    finished = []
    job_id = runner.start(lambda: client.chat(MESSAGES), lambda text: finished.append(text) or "saved-id")
    assert _wait_for(lambda: runner.status(job_id)["state"] == "done")
    assert finished == ["one two"]
    status = runner.status(job_id)
    assert status["result"] == "saved-id" and status["characters"] == len("one two")


def test_job_progress_rises_while_the_reply_streams(servers):
    server = servers(ollama_chunks(*["abcde"] * 8), delay=0.15)
    client = _ollama(server)
    runner = JobRunner()
    job_id = runner.start(lambda: client.chat(MESSAGES))
    seen: list[int] = []
    while runner.status(job_id)["state"] == "running":
        seen.append(runner.status(job_id)["characters"])
        time.sleep(0.05)
    positive = sorted({n for n in seen if n > 0})
    assert len(positive) >= 3, f"expected the count to rise over several reads, saw {seen}"
    assert seen == sorted(seen) and runner.status(job_id)["characters"] == 40


def test_the_job_thread_does_not_leak_the_hooks_into_the_caller():
    runner = JobRunner(inline=True)
    runner.start(lambda: "x")
    assert CANCELLED.get() is None and PROGRESS.get() is None


def test_a_job_that_fails_without_a_cancel_still_shows_as_failed():
    runner = JobRunner(inline=True)

    def work():
        raise LLMError("could not reach the model server")

    job_id = runner.start(work)
    status = runner.status(job_id)
    assert status["state"] == "failed" and "could not reach" in status["error"]


def test_an_error_after_a_cancel_stays_cancelled():
    runner = JobRunner(inline=True)

    def work():
        runner.cancel(next(iter(runner._jobs)))
        raise LLMError("cancelled")

    job_id = runner.start(work)
    status = runner.status(job_id)
    assert status["state"] == "cancelled" and status["error"] is None


# --- the wait page ---------------------------------------------------------------------------------------


class _SlowModel:
    """Reports some progress, then waits, like a model part way through its answer."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.started = threading.Event()

    def chat(self, messages, *, json_mode=False, schema=None) -> str:
        report_progress(321)
        self.started.set()
        self.release.wait(10)
        raise LLMError("cancelled")


def test_the_wait_page_shows_how_many_characters_have_arrived(site_dir):
    model = _SlowModel()
    client = TestClient(create_app(site_dir, llm=model))
    client.get("/")
    token = client.cookies.get("sa_csrf", "")
    form = {
        "csrf": token,
        "name": "Ravi Kumar",
        "group": "scholar",
        "role": "Research scholar",
        "dept": "",
        "interests": "Grasping",
        "homepage": "",
        "photo": "",
        "order": "100",
        "body": "",
        "facts": "Studies grasping.",
        "action": "draft:body",
    }
    try:
        response = client.post("/c/people/new", data=form, follow_redirects=False)
        job_url = response.headers["location"]
        assert job_url.startswith("/jobs/")
        assert model.started.wait(5)
        page = client.get(job_url).text
        assert "About 321 characters received so far" in page
        assert 'http-equiv="refresh"' in page  # the page still refreshes on its own
    finally:
        model.release.set()
