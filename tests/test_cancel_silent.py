"""A cancel stops the request even while the model has not yet said anything."""

import socket
import threading
import time

import pytest
from streamserver import SilentServer, StreamServer, ollama_chunks

from site_agent.config import LLMSettings
from site_agent.drafting import JobRunner
from site_agent.llm import LLMError, Message
from site_agent.llm.base import CANCELLED
from site_agent.llm.ollama import OllamaClient
from site_agent.llm.openai_compat import OpenAICompatClient

MESSAGES = [Message("user", "hello")]


@pytest.fixture
def silent():
    started: list[SilentServer] = []

    def start(**kw) -> SilentServer:
        started.append(SilentServer(**kw))
        return started[-1]

    yield start
    for server in started:
        server.close()


def _client(kind, url, timeout_s=60):
    settings = LLMSettings(provider=kind, model="m1", base_url=url, timeout_s=timeout_s)
    return OllamaClient(settings) if kind == "ollama" else OpenAICompatClient(settings)


@pytest.mark.parametrize("kind", ["ollama", "openai"])
def test_a_cancel_while_the_model_is_silent_stops_the_call_and_closes_the_connection(silent, kind):
    server = silent()
    cancelled = threading.Event()
    threading.Timer(0.5, cancelled.set).start()
    token = CANCELLED.set(cancelled.is_set)
    started = time.monotonic()
    try:
        with pytest.raises(LLMError) as caught:
            _client(kind, server.url).chat(MESSAGES)
    finally:
        CANCELLED.reset(token)
    assert str(caught.value) == "cancelled"
    assert 0.4 < time.monotonic() - started < 2.0
    assert server.got_request.is_set(), "the cancel should have come after the request was sent"
    assert server.closed.wait(2), "the server never saw the connection close"


def test_cancelling_a_job_whose_model_is_silent_ends_the_job_as_cancelled(silent):
    server = silent()
    client = _client("ollama", server.url)
    runner = JobRunner()
    job_id = runner.start(lambda: client.chat(MESSAGES), lambda text: "saved")
    assert server.got_request.wait(5)
    runner.cancel(job_id)
    assert server.closed.wait(2), "cancelling the job did not close the connection to the silent model"
    deadline = time.monotonic() + 2
    while runner._jobs[job_id]["state"] == "running" and time.monotonic() < deadline:
        time.sleep(0.02)
    status = runner.status(job_id)
    assert status["state"] == "cancelled" and status["error"] is None and status["result"] is None


def test_a_job_that_is_not_cancelled_still_completes_with_the_watcher_running():
    server = StreamServer(ollama_chunks("one ", "two"), delay=0.3)
    try:
        client = _client("ollama", server.url)
        runner = JobRunner()
        job_id = runner.start(lambda: client.chat(MESSAGES))
        deadline = time.monotonic() + 5
        while runner.status(job_id)["state"] == "running" and time.monotonic() < deadline:
            time.sleep(0.02)
        status = runner.status(job_id)
        assert status["state"] == "done" and status["result"] == "one two"
    finally:
        server.close()


def test_a_silent_model_still_times_out_when_nobody_cancels(silent):
    server = silent()
    token = CANCELLED.set(lambda: False)
    try:
        with pytest.raises(LLMError, match="did not answer within"):
            _client("ollama", server.url, timeout_s=0.5).chat(MESSAGES)
    finally:
        CANCELLED.reset(token)


def test_a_refused_connection_is_reported_as_unreachable():
    sock = socket.socket()  # bound but never listening, so the connection is refused
    sock.bind(("127.0.0.1", 0))
    try:
        url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        with pytest.raises(LLMError, match="could not reach the model server"):
            _client("ollama", url, timeout_s=2).chat(MESSAGES)
    finally:
        sock.close()
