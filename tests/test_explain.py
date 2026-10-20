"""Plain sentences for a failed site check."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import FakeLLM

from site_agent.appstate import AppState
from site_agent.config import SiteSettings
from site_agent.explain import GENERIC, explain_check
from site_agent.site import Site
from site_agent.web.app import create_app

TOOL = "The check tool is missing. Install Node.js 22.12 or newer, then try again."
PACKAGES = "The website's packages look incomplete. Run npm install in the website folder, then try again."
PORT = "Another program is using a port the build needs. Close it and try again."
MISMATCH = "A content file has a field that does not match its rules. The message below names the file and the field."
REQUIRED = "A required field is missing in a content file. The message below names it."
MISSING_FILE = "A file the build needs is missing. The message below names it."


@pytest.mark.parametrize(
    ("output", "sentence"),
    [
        ("sh: 1: npm: command not found", TOOL),
        ("'node' is not recognized as an internal or external command", TOOL),
        ("bash: node: command not found", TOOL),
        ("Error: Cannot find module 'astro'", PACKAGES),
        ("code: 'ERR_MODULE_NOT_FOUND'", PACKAGES),
        ("Error: listen EADDRINUSE: address already in use :::4321", PORT),
        ("[InvalidContentEntryDataError] people jane data does not match the collection schema.", MISMATCH),
        ("data does not match the collection schema", MISMATCH),
        ('field "name" is required', REQUIRED),
        ("Error: ENOENT: no such file or directory, open 'public/people/a.jpg'", MISSING_FILE),
    ],
)
def test_known_failures_get_their_sentence(output, sentence):
    assert sentence in explain_check(output)


def test_unknown_output_gets_the_generic_sentence():
    assert explain_check("something unexpected happened") == [GENERIC]
    assert explain_check("") == [GENERIC]
    assert GENERIC == "The check failed. The details below show what the build said."


def test_a_known_failure_does_not_add_the_generic_sentence():
    assert GENERIC not in explain_check("Error: ENOENT: no such file")


def test_several_failures_give_several_sentences():
    assert explain_check("Cannot find module 'x'\nENOENT: no such file") == [PACKAGES, MISSING_FILE]


def test_a_command_not_found_for_another_tool_is_not_the_missing_check_tool():
    assert explain_check("bash: foo: command not found") == [GENERIC]


def _client(site_dir: Path, script: str) -> TestClient:
    command = f'"{sys.executable}" -c "{script}"'
    (site_dir / "site-agent.toml").write_text(f"[site]\ncheck_command = {json.dumps(command)}\n", encoding="utf-8")
    client = TestClient(create_app(site_dir, llm=FakeLLM(), inline_jobs=True))
    client.get("/")  # sets the form token cookie
    return client


def _run_check(client: TestClient) -> None:
    client.post("/check/run", data={"csrf": client.cookies.get("sa_csrf", "")})


def test_a_failed_check_shows_plain_sentences_above_the_raw_output(site_dir):
    client = _client(site_dir, "import sys; print('Error: ENOENT: no such file'); sys.exit(1)")
    _run_check(client)
    page = client.get("/check").text
    assert MISSING_FILE in page
    assert page.index(MISSING_FILE) < page.index("ENOENT: no such file")
    assert "What went wrong" in page


def test_the_plain_sentences_are_stored_with_the_result(site_dir):
    client = _client(site_dir, "import sys; print('boom'); sys.exit(1)")
    _run_check(client)
    saved = AppState(Site(SiteSettings(root=site_dir))).last_check()
    assert saved["ok"] is False
    assert saved["plain"] == [GENERIC]


def test_a_passing_check_shows_no_explanation(site_dir):
    client = _client(site_dir, "print('built')")
    _run_check(client)
    assert "What went wrong" not in client.get("/check").text
