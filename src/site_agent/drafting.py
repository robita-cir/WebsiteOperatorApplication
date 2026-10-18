"""Drafting: the local model writes wording from the operator's facts. It never saves anything.

Two things protect the operator. First, every number, year, web address and email in a draft must appear in the facts;
anything else is listed, and saving is blocked while it stays in the text (see repository.py). Second, the model's
answer is only ever text in a box: the operator reads it, edits it, and approves it before it reaches the website.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.request
import uuid
from collections.abc import Callable
from typing import Any

from site_agent.config import LLMSettings
from site_agent.errors import SiteAgentError
from site_agent.llm import ChatClient, Message
from site_agent.llm.parsing import strip_reasoning
from site_agent.prompts import load_prompt
from site_agent.records import Spec

_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_NUMBER = re.compile(r"\b\d{2,}(?:[.,]\d+)?\b")
_URL = re.compile(r"https?://[^\s)]+|\b[\w-]+(?:\.[\w-]+)*\.(?:org|com|edu|net|in|uk|ac\.in|ac\.uk)\b", re.IGNORECASE)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

LENGTHS = {
    "body": "about 60 to 120 words in short paragraphs",
    "summary": "one or two plain sentences",
    "description": "two to four plain sentences",
}


def unsupported_tokens(text: str, facts: str) -> list[str]:
    """Years, numbers, web addresses and emails in `text` that do not appear in `facts`."""
    haystack = facts.casefold()
    found: list[str] = []
    for pattern in (_EMAIL, _URL, _YEAR, _NUMBER):
        for match in pattern.finditer(text):
            token = match.group(0).rstrip(".,;:")
            if token and token.casefold() not in haystack and token not in found:
                found.append(token)
    return found


def facts_text(spec: Spec, values: dict[str, Any], extra: str) -> str:
    """The facts the model may use: the filled-in fields, plus the free-text facts the operator typed."""
    lines = []
    for f in spec.fields:
        value = values.get(f.name)
        if value in (None, "", []) or isinstance(value, bool):
            continue
        shown = ", ".join(value) if isinstance(value, list) else str(value)
        lines.append(f"{f.label}: {shown}")
    lines += [line.strip() for line in extra.splitlines() if line.strip()]
    return "\n".join(lines)


def draft_section(llm: ChatClient, spec: Spec, section: str, length_key: str, facts: str) -> dict[str, Any]:
    """Asks for one piece of wording. Returns {"text", "unsupported"}."""
    if not facts.strip():
        raise SiteAgentError("Write at least one fact first. The model can only use what you give it.")
    system = load_prompt(
        "draft_text",
        singular=spec.singular,
        section=section,
        length=LENGTHS.get(length_key, LENGTHS["body"]),
    )
    reply = llm.chat([Message("system", system), Message("user", f"Facts:\n{facts}")])
    text = strip_reasoning(reply).strip().strip('"').strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
    if not text:
        raise SiteAgentError("The model returned an empty draft. Try again, or add more facts.")
    return {"text": text, "unsupported": unsupported_tokens(text, facts)}


def extract_from_notice(llm: ChatClient, notice: str, today: str) -> dict[str, Any]:
    """Reads a notice about an event and returns its fields, for the form to fill in. Nothing is saved."""
    from site_agent.workflows import ask_json

    system = load_prompt("extract_new_event", today=today)
    raw = ask_json(llm, system, notice)
    keep = ("title", "kind", "series", "date", "endDate", "venue", "summary", "body")
    return {key: raw.get(key) for key in keep if raw.get(key) not in (None, "")}


class JobRunner:
    """Runs slow work (drafting, the site check) off the web request, so the page can show progress and a cancel button.

    With inline=True the work runs immediately, which the tests use. Jobs live in memory: if the app restarts, a job
    in progress is lost, and the operator starts it again.
    """

    def __init__(self, inline: bool = False) -> None:
        self._inline = inline
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start(self, work: Callable[[], Any]) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = {"state": "running", "result": None, "error": None, "cancelled": False, "started": time.time()}
        with self._lock:
            self._jobs[job_id] = job
        if self._inline:
            self._run(job, work)
        else:
            threading.Thread(target=self._run, args=(job, work), daemon=True).start()
        return job_id

    def _run(self, job: dict[str, Any], work: Callable[[], Any]) -> None:
        try:
            result = work()
        except SiteAgentError as exc:
            job.update(state="failed", error=str(exc))
            return
        except Exception as exc:  # the operator sees a plain message; the detail goes in the error text
            job.update(state="failed", error=f"Something went wrong: {exc}")
            return
        if not job["cancelled"]:
            job.update(state="done", result=result)

    def status(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "state": "cancelled" if job["cancelled"] else job["state"],
                "result": job["result"],
                "error": job["error"],
                "seconds": int(time.time() - job["started"]),
            }

    def cancel(self, job_id: str) -> None:
        """Stops waiting for the answer. The model cannot be interrupted mid-answer, so its reply is thrown away."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job["state"] == "running":
                job["cancelled"] = True


def model_status(settings: LLMSettings) -> tuple[bool, str]:
    """Whether the model server answers and has the chosen model. Quick: it gives up after two seconds."""
    base = settings.base_url.rstrip("/")
    url = f"{base}/api/tags" if settings.provider == "ollama" else f"{base}/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return False, "The writing helper is not running. Start Ollama, then reload this page."
    names = (
        [m.get("name", "") for m in data.get("models", [])]
        if settings.provider == "ollama"
        else [m.get("id", "") for m in data.get("data", [])]
    )
    wanted = settings.model
    if any(name == wanted or name == f"{wanted}:latest" for name in names):
        return True, f"Ready: {wanted} is installed."
    return False, f"The model {wanted} is not installed. Run: ollama pull {wanted}"
