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
from site_agent.llm.base import CANCELLED, PROGRESS
from site_agent.llm.parsing import extract_json_object, strip_reasoning
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
    for key in ("venue", "series"):  # a value that held more than the notice's words was cut back to them
        if key in fields and reading.fields.get(key):
            fields[key] = reading.fields[key]
    if isinstance(fields.get("kind"), str):  # the kinds in the form are lower case, as the record rules require
        fields["kind"] = fields["kind"].strip().lower()
    notes = [*reading.blockers, *reading.notes, *notice_notes(fields, notice)]
    return NoticeResult(fields, notes)


def _clean_reply(reply: str) -> str:
    text = strip_reasoning(reply).strip().strip('"').strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
    return text


def rephrase_draft(llm: ChatClient, spec: Spec, section: str, text: str, facts: str) -> dict[str, Any]:
    """Asks for the same text again with every sentence the facts do not support removed or reworded.

    The reply is checked here, not trusted: the returned "unsupported" lists what the facts still do not give, so a
    rewrite that keeps an invented number is shown to the operator as such. Returns {"text", "unsupported"}.
    """
    if not facts.strip():
        raise SiteAgentError("Write at least one fact first. The model can only use what you give it.")
    if not text.strip():
        raise SiteAgentError("There is no text to rewrite yet.")
    system = load_prompt("rephrase_draft", singular=spec.singular, section=section)
    reply = llm.chat([Message("system", system), Message("user", f"Facts:\n{facts}\n\nText to fix:\n{text}")])
    new_text = _clean_reply(reply)
    if not new_text:
        raise SiteAgentError("The model returned an empty text. Try again, or edit the text yourself.")
    return {"text": new_text, "unsupported": unsupported_tokens(new_text, facts)}


def suggest_choice(llm: ChatClient, spec: Spec, field_name: str, title: str, summary: str, facts: str) -> str | None:
    """Asks which of a choice field's options fits. Returns the stored value, or None when the answer is not one of
    the listed options. The operator accepts or changes it; nothing is saved here."""
    field = spec.field(field_name)
    options = "\n".join(f"- {stored} ({label})" for stored, label in field.choices)
    system = load_prompt("suggest_choice", label=field.label, singular=spec.singular, options=options)
    given = [f"Title: {title.strip()}"] if title.strip() else []
    if summary.strip():
        given.append(f"Summary: {summary.strip()}")
    if facts.strip():
        given.append(f"Facts:\n{facts.strip()}")
    reply = llm.chat([Message("system", system), Message("user", "\n".join(given))], json_mode=True)
    try:
        chosen = extract_json_object(reply).get("value")
    except ValueError:
        return None
    # Only the stored value counts: a label, a different case or an invented option is refused.
    return chosen if isinstance(chosen, str) and chosen in {stored for stored, _ in field.choices} else None


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
        job = {
            "state": "running",
            "result": None,
            "error": None,
            "cancelled": False,
            "started": time.time(),
            "characters": 0,
        }
        with self._lock:
            self._jobs[job_id] = job
        if self._inline:
            self._run(job, work, finish)
        else:
            threading.Thread(target=self._run, args=(job, work, finish), daemon=True).start()
        return job_id

    def _run(self, job: dict[str, Any], work: Callable[[], Any], finish: Callable[[Any], Any] | None) -> None:
        # The model clients read these two while `work` runs in this thread: the cancel check lets a cancel close the
        # connection to the model, and the progress callback feeds the wait page. Reset after, because with
        # inline=True this thread is the caller's.
        cancel_token = CANCELLED.set(lambda: job["cancelled"])
        progress_token = PROGRESS.set(lambda characters: job.update(characters=characters))
        try:
            result = work()
        except SiteAgentError as exc:
            self._fail(job, str(exc))
            return
        except Exception as exc:  # the operator sees a plain message; the detail goes in the error text
            self._fail(job, f"Something went wrong: {exc}")
            return
        finally:
            CANCELLED.reset(cancel_token)
            PROGRESS.reset(progress_token)
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

    def _fail(self, job: dict[str, Any], message: str) -> None:
        # A call stopped by a cancel ends in an error ("cancelled"); that is the operator's choice, not a failure.
        job.update(state="cancelled" if job["cancelled"] else "failed", error=None if job["cancelled"] else message)

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
                "characters": job["characters"],
            }

    def cancel(self, job_id: str) -> None:
        """Stops the job. A call to the model that is streaming closes its connection at the next chunk; whatever
        the job produces after this is thrown away and never saved."""
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
