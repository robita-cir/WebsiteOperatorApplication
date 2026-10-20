"""The two requests an operator makes: add an event, or change an event and wherever it is mentioned.

The model is only asked for small, checkable output: one JSON object, or search/replace blocks. The tool writes the
event file itself from the validated record, so the model never has to produce YAML.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from site_agent.dates import resolve_relative_date
from site_agent.edits import NO_CHANGE, apply_edit_blocks, parse_edit_blocks
from site_agent.errors import SiteAgentError
from site_agent.events import find_event, load_event, new_event_path
from site_agent.factcheck import fact_problems
from site_agent.frontmatter import render_document, set_frontmatter_values
from site_agent.llm.base import ChatClient, Message
from site_agent.llm.parsing import extract_json_object, strip_reasoning
from site_agent.plan import FileChange, Plan
from site_agent.prompts import load_prompt
from site_agent.records import SPECS
from site_agent.schemas import Event, describe_errors
from site_agent.site import Site
from site_agent.substitute import Substitution, replace_on_anchor_lines, search_needles, substitutions_for
from site_agent.text_utils import excerpt_lines, matching_lines, quote_in_text, ungrounded_fields

JSON_ATTEMPTS = 2
MAX_INPUT_WORDS = 1500  # a small model loses the thread on a longer notice, so the operator is asked to trim it
MAX_EDIT_FILES = 8  # files (including the event itself) the model is asked to check in one update
EXCERPT_RADIUS = 10
EDIT_REMINDER = f"Reply with SEARCH/REPLACE blocks copied from the excerpt, or {NO_CHANGE}."

# Fields the model may set. "sample" and "body" are never taken from the model's answer.
RECORD_FIELDS = ("title", "kind", "series", "date", "endDate", "venue", "summary")

_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_TEXT_OR_NULL = {"type": ["string", "null"]}
# The shape the model is asked for, for clients that can constrain a reply. The harness still checks every value.
EVENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "kind": {"type": "string", "enum": ["workshop", "programme", "talk"]},
        "series": _TEXT_OR_NULL,
        "date": {"type": "string", "pattern": _DATE_PATTERN},
        "endDate": {"type": ["string", "null"], "pattern": _DATE_PATTERN},
        "venue": _TEXT_OR_NULL,
        "summary": _TEXT_OR_NULL,
        "body": {"type": "string"},
        "date_phrase": _TEXT_OR_NULL,
        "sources": {
            "type": "object",
            "properties": {key: _TEXT_OR_NULL for key in ("date", "endDate", "venue", "series")},
        },
    },
    "required": ["title", "kind", "date"],
}
# An update reply is partial: only the keys that changed.
UPDATE_EVENT_SCHEMA: dict[str, Any] = {key: value for key, value in EVENT_SCHEMA.items() if key != "required"}


def ask_json(
    llm: ChatClient,
    system: str,
    user: str,
    *,
    check: Callable[[dict[str, Any]], None] | None = None,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Asks for one JSON object. If the reply is unusable, says why and asks once more.

    `check` raises SiteAgentError for a reply that parses but is wrong. Its message goes back to the model in the same
    conversation, so the model corrects its own record. `schema` is handed to clients that can constrain the reply.
    """
    words = len(user.split())
    if words > MAX_INPUT_WORDS:
        raise SiteAgentError(
            f"The notice is {words:,} words long. The helper reads up to {MAX_INPUT_WORDS:,} words at a time. "
            "Paste the part with the event details."
        )
    options: dict[str, Any] = {"schema": schema} if schema is not None else {}
    messages = [Message("system", system), Message("user", user)]
    for attempt in range(1, JSON_ATTEMPTS + 1):
        reply = llm.chat(messages, json_mode=True, **options)
        last = attempt == JSON_ATTEMPTS
        try:
            raw = extract_json_object(reply)
        except ValueError as exc:
            if last:
                raise SiteAgentError(
                    f"the model did not return a usable record ({exc}). Try again, or use a larger model."
                ) from exc
            follow_up = f"That was not a valid JSON object ({exc}). Reply with only the JSON object."
        else:
            if check is None:
                return raw
            try:
                check(raw)
            except SiteAgentError as exc:
                if last:
                    raise
                follow_up = f"That record is not valid: {exc}. Reply with the corrected JSON object only."
            else:
                return raw
        messages = messages + [Message("assistant", reply), Message("user", follow_up)]
    raise AssertionError("unreachable")


def _clean(raw: dict[str, Any]) -> dict[str, Any]:
    """Keeps only the record fields the model actually sent, and tidies blank strings and the kind's case."""
    cleaned: dict[str, Any] = {}
    for key in RECORD_FIELDS:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, str):
            value = value.strip() or None
        cleaned[key] = value
    if isinstance(cleaned.get("kind"), str):
        cleaned["kind"] = cleaned["kind"].lower()
    return cleaned


def _validate_record(fields: dict[str, Any], label: str) -> Event:
    try:
        return Event.model_validate(fields)
    except ValidationError as exc:
        raise SiteAgentError(f"{label}: " + "; ".join(describe_errors(exc))) from exc


@dataclass
class NoticeReading:
    """A notice's record after the quote and relative-date rules. `blockers` stop a write; `notes` are for review."""

    fields: dict[str, Any]
    blockers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _source_quote(raw: dict[str, Any], key: str, notice: str) -> bool:
    """True when the model gave words for `key` and those words are in the notice."""
    sources = raw.get("sources")
    quote = sources.get(key) if isinstance(sources, dict) else None
    return isinstance(quote, str) and quote_in_text(quote, notice)


def ground_notice(raw: dict[str, Any], notice: str, today: dt.date) -> NoticeReading:
    """Checks the model's record against the notice. A date the notice does not state is a blocker.

    A relative date ("next Monday") is worked out here from the real date, never by the model. The words the model says
    it copied must really be in the notice; otherwise the date has no support and nothing may be written from it.
    """
    reading = NoticeReading(fields=_clean(raw))
    fields = reading.fields
    phrase = raw.get("date_phrase")
    resolved = None
    if isinstance(phrase, str) and phrase.strip() and quote_in_text(phrase, notice):
        resolved = resolve_relative_date(phrase, today)
    if resolved is not None:
        given = fields.get("date")
        if given and str(given) != resolved.isoformat():
            reading.notes.append(
                f"The notice says '{phrase.strip()}': that is {resolved.isoformat()}. "
                f"The model gave {given}, which was not used."
            )
        fields["date"] = resolved.isoformat()
    for key in ("date", "endDate"):
        if not fields.get(key) or (key == "date" and resolved is not None):
            continue
        if not _source_quote(raw, key, notice):
            reading.blockers.append(
                f"{key}: the notice does not state this date in its own words. "
                "Check the notice, or edit the event file by hand."
            )
    for key in ("venue", "series"):
        if fields.get(key) and not _source_quote(raw, key, notice):
            reading.notes.append(f'{key} "{fields[key]}": the notice does not give this in its own words. Check it.')
    return reading


def plan_add_event(
    site: Site, llm: ChatClient, source_text: str, *, slug: str | None = None, today: dt.date | None = None
) -> Plan:
    today = today or dt.date.today()
    system = load_prompt("extract_new_event", today=today.isoformat())
    label = "the event from your text is incomplete or invalid"
    raw = ask_json(
        llm,
        system,
        source_text,
        check=lambda reply: _validate_record(_clean(reply), label),
        schema=EVENT_SCHEMA,
    )
    body = str(raw.get("body") or "").strip()
    reading = ground_notice(raw, source_text, today)
    event = _validate_record(reading.fields, label)
    rel = new_event_path(site, event.title, slug)

    record = event.to_frontmatter()
    plan = Plan(summary=f"Add event '{event.title}' as {rel}")
    plan.changes.append(FileChange(rel, None, render_document(record, body)))
    plan.failures.extend(reading.blockers)
    plan.notes.extend(reading.notes)
    plan.notes.extend(ungrounded_fields(record, source_text))
    # The same rule as for text typed in the web app: numbers and addresses must come from the notice.
    values = {key: record.get(key) for key in RECORD_FIELDS}
    plan.failures.extend(fact_problems(SPECS["events"], values, body, facts=source_text))
    return plan


def _ask_model_for_leftovers(
    llm: ChatClient, target: str, text: str, hits: list[int], subs: list[Substitution], plan: Plan
) -> str:
    """Asks the model to fix the lines the tool could not handle itself. Returns the text with any placed edits."""
    lines = text.split("\n")
    excerpt = excerpt_lines(lines, hits, EXCERPT_RADIUS)
    pairs = [sub for sub in subs if sub.old in excerpt]
    description = "\n".join(f'- replace "{sub.old}" with "{sub.new}"' for sub in pairs)
    system = load_prompt("edit_excerpt", change=description)
    messages = [Message("system", system), Message("user", f"File: {target}\n\n{excerpt}")]
    reply = strip_reasoning(llm.chat(messages))
    blocks = parse_edit_blocks(reply)
    if not blocks and NO_CHANGE not in reply:
        # A small model often answers in prose the first time. One reminder of the format, never more.
        messages = messages + [Message("assistant", reply), Message("user", EDIT_REMINDER)]
        reply = strip_reasoning(llm.chat(messages))
        blocks = parse_edit_blocks(reply)
    if not blocks:
        if NO_CHANGE not in reply:
            plan.failures.append(f"{target}: the model returned no edit blocks")
        return text
    # An edit may only change lines the model was shown. A unique match elsewhere in the file is not enough.
    shown = []
    for number, block in enumerate(blocks, start=1):
        key = block.search.strip("\n")
        if key in excerpt or key not in text:  # text not in the file at all is reported as not found, as before
            shown.append(block)
        else:
            plan.failures.append(f"{target}: edit {number} changes text the model was not shown, so it was not applied")
    result = apply_edit_blocks(text, shown)
    plan.failures.extend(f"{target}: {failure}" for failure in result.failures)
    return result.text


def _lines(indexes: list[int]) -> str:
    """0-based line indexes as the numbers an editor shows: 'line 6' or 'lines 2, 3'."""
    numbers = ", ".join(str(i + 1) for i in indexes)
    return f"line {numbers}" if len(indexes) == 1 else f"lines {numbers}"


def plan_update_event(
    site: Site,
    llm: ChatClient,
    query: str,
    instruction: str,
    *,
    today: dt.date | None = None,
    assisted: bool = False,
) -> Plan:
    rel = find_event(site, query)
    old, original = load_event(site, rel)
    old_record = old.to_frontmatter()
    current = json.dumps(old_record, ensure_ascii=False, indent=2, default=str)
    system = load_prompt("extract_update_event", today=(today or dt.date.today()).isoformat(), current=current)

    # Keys the model leaves out keep their old value. A key set to null is removed.
    label = f"the updated {rel} is invalid"
    reply = ask_json(
        llm,
        system,
        instruction,
        check=lambda partial: _validate_record({**old_record, **_clean(partial)}, label),
        schema=UPDATE_EVENT_SCHEMA,
    )
    merged = {**old_record, **_clean(reply)}
    new_record = _validate_record(merged, label).to_frontmatter()
    changes = {key: new_record.get(key) for key in RECORD_FIELDS if old_record.get(key) != new_record.get(key)}

    edited: dict[str, str] = {rel: set_frontmatter_values(original, changes)}
    plan = Plan(summary="")
    subs = substitutions_for(old_record, changes)
    needles = search_needles(subs)
    # Every change, including a venue or series, is made on the lines that name the event by its old title. So the
    # title is also searched for, to find those lines in other files.
    find_terms = [*needles, old.title] if subs else []
    read_only: list[str] = []
    if subs:
        mention_files = sorted({m.rel_path for m in site.find_mentions(find_terms, exclude={rel})})
        targets = [rel, *mention_files]
        if len(targets) > MAX_EDIT_FILES:
            plan.notes.append(
                f"{len(targets)} files mention the old details; only the first {MAX_EDIT_FILES} were checked. "
                "Search for the old text with 'site-agent find' to see the rest."
            )
            targets = targets[:MAX_EDIT_FILES]
        anchor = old.title
        for target in targets:
            start_text = edited[target] if target in edited else site.read(target)
            if not matching_lines(start_text, find_terms):
                continue
            if not site.is_writable(target):
                read_only.append(target)
                continue
            text, changed = replace_on_anchor_lines(start_text, subs, anchor)
            if changed:
                plan.notes.append(
                    f"{target}: changed automatically on {_lines(changed)}, because it names the event. Check it."
                )
            # Lines already changed are done. Lines that still show the old details but do not name the event are
            # not guessed at: they are listed, and only the model is asked about them when the operator opts in.
            before_lines, after_lines = start_text.split("\n"), text.split("\n")
            leftovers = [i for i in matching_lines(text, needles) if before_lines[i] == after_lines[i]]
            if leftovers and assisted:
                text = _ask_model_for_leftovers(llm, target, text, leftovers, subs, plan)
                plan.notes.append(f"{target}: the model proposed edits for {_lines(leftovers)}. Check them carefully.")
            elif leftovers:
                plan.notes.append(
                    f"{target}: {_lines(leftovers)} still show the old details but do not name the event, so nothing "
                    "was changed there. Edit by hand, or run again with --assisted."
                )
            if text != start_text:
                edited[target] = text

    if read_only:
        plan.notes.append(
            "These files also show the old details, but the agent may not change them. Edit them by hand: "
            + ", ".join(read_only)
        )
    for target, text in edited.items():
        before = original if target == rel else site.read(target)
        if text != before:
            plan.changes.append(FileChange(target, before, text))

    plan.summary = (
        f"Update event '{new_record.get('title', old.title)}' ({rel}): "
        f"{len(changes)} field(s) changed, {len(plan.changes)} file(s) to write"
    )
    if not changes:
        plan.notes.append("The instruction did not change any event field.")
    plan.notes.extend(ungrounded_fields(changes, instruction))
    return plan
