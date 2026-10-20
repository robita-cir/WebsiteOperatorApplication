"""Drafting: the local model writes wording from the operator's facts. It never saves anything.

Two things protect the operator. First, every number, year, web address and email in a draft must appear in the facts;
anything else is listed, and saving is blocked while it stays in the text (see repository.py). Second, the model's
answer is only ever text in a box: the operator reads it, edits it, and approves it before it reaches the website.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import time
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from site_agent.config import LLMSettings
from site_agent.errors import SiteAgentError
from site_agent.factcheck import claim_sentences, unsupported_tokens
from site_agent.llm import ChatClient, Message
from site_agent.llm.parsing import strip_reasoning
from site_agent.prompts import load_prompt
from site_agent.records import Spec
from site_agent.text_utils import ungrounded_fields

LENGTHS = {
    "body": "about 60 to 120 words in short paragraphs",
    "summary": "one or two plain sentences",
    "description": "two to four plain sentences",
}


def draft_section(llm: ChatClient, spec: Spec, section: str, length_key: str, facts: str) -> dict[str, Any]:
    """Asks for one piece of wording. Returns {"text", "unsupported", "claims"}."""
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
    return {"text": text, "unsupported": unsupported_tokens(text, facts), "claims": claim_sentences(text, facts)}


@dataclass(frozen=True)
class NoticeResult:
    fields: dict[str, Any]  # for the form to fill in
    notes: list[str]  # what the operator should check: unstated dates, places and series, and relative dates


def extract_notice(llm: ChatClient, notice: str, today: str | dt.date) -> NoticeResult:
    """Reads a notice about an event. Returns the form fields and the notes to show beside them. Nothing is saved.

    A date the notice does not state in its own words is kept in the form, since the operator fills the form in and
    checks it, but it is listed in the notes. A relative date such as "next Monday" is worked out from today's date.
    """
    from site_agent.workflows import ask_json, ground_notice

    day = today if isinstance(today, dt.date) else _parse_day(today)
    system = load_prompt("extract_new_event", today=day.isoformat())
    raw = ask_json(llm, system, notice)
    reading = ground_notice(raw, notice, day)
    keep = ("title", "kind", "series", "date", "endDate", "venue", "summary", "body")
    fields = {key: raw.get(key) for key in keep if raw.get(key) not in (None, "")}
    if reading.fields.get("date"):  # a relative date, worked out here, replaces the model's
        fields["date"] = reading.fields["date"]
    if isinstance(fields.get("kind"), str):  # the kinds in the form are lower case, as the record rules require
        fields["kind"] = fields["kind"].strip().lower()
    notes = [*reading.blockers, *reading.notes, *notice_notes(fields, notice)]
    return NoticeResult(fields, notes)


def extract_from_notice(llm: ChatClient, notice: str, today: str) -> dict[str, Any]:
    """Reads a notice about an event and returns its fields, for the form to fill in. Nothing is saved."""
    return extract_notice(llm, notice, today).fields


def _parse_day(text: str) -> dt.date:
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return dt.date.today()


def notice_notes(fields: dict[str, Any], notice: str) -> list[str]:
    """Dates, places and series in the filled-in fields that the notice does not state, for the operator to check."""
    checked: dict[str, Any] = dict(fields)
    for key in ("date", "endDate"):
        try:
            checked[key] = dt.date.fromisoformat(str(fields[key])) if fields.get(key) else None
        except ValueError:
            checked[key] = None
    return ungrounded_fields(checked, notice)


class JobRunner:
    """Runs slow work (drafting, the site check) off the web request, so the page can show progress and a cancel button.

    With inline=True the work runs immediately, which the tests use. Jobs live in memory: if the app restarts, a job
    in progress is lost, and the operator starts it again.
    """

    def __init__(self, inline: bool = False) -> None:
        self._inline = inline
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def start(self, work: Callable[[], Any], finish: Callable[[Any], Any] | None = None) -> str:
        """Runs `work` in the background. `finish` then turns its result into the job's result (for example, saves a
        draft). `finish` runs only if the job was not cancelled, and it runs under the lock, so a cancel that returns
        guarantees nothing is saved afterwards."""
        job_id = uuid.uuid4().hex[:12]
        job = {"state": "running", "result": None, "error": None, "cancelled": False, "started": time.time()}
        with self._lock:
            self._jobs[job_id] = job
        if self._inline:
            self._run(job, work, finish)
        else:
            threading.Thread(target=self._run, args=(job, work, finish), daemon=True).start()
        return job_id

    def _run(self, job: dict[str, Any], work: Callable[[], Any], finish: Callable[[Any], Any] | None) -> None:
        try:
            result = work()
        except SiteAgentError as exc:
            job.update(state="failed", error=str(exc))
            return
        except Exception as exc:  # the operator sees a plain message; the detail goes in the error text
            job.update(state="failed", error=f"Something went wrong: {exc}")
            return
        with self._lock:
            if job["cancelled"]:
                return
            try:
                if finish is not None:
                    result = finish(result)
            except SiteAgentError as exc:
                job.update(state="failed", error=str(exc))
                return
            except Exception as exc:
                job.update(state="failed", error=f"Something went wrong: {exc}")
                return
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
