"""The two requests an operator makes: add an event, or change an event and wherever it is mentioned.

The model is only asked for small, checkable output: one JSON object, or search/replace blocks. The tool writes the
event file itself from the validated record, so the model never has to produce YAML.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from pydantic import ValidationError

from site_agent.edits import NO_CHANGE, apply_edit_blocks, parse_edit_blocks
from site_agent.errors import SiteAgentError
from site_agent.events import find_event, load_event, new_event_path
from site_agent.frontmatter import render_document, set_frontmatter_values
from site_agent.llm.base import ChatClient, Message
from site_agent.llm.parsing import extract_json_object
from site_agent.plan import FileChange, Plan
from site_agent.prompts import load_prompt
from site_agent.schemas import Event, describe_errors
from site_agent.site import Site
from site_agent.substitute import Substitution, replace_on_anchor_lines, search_needles, substitutions_for
from site_agent.text_utils import excerpt_lines, matching_lines, ungrounded_fields

JSON_ATTEMPTS = 2
MAX_EDIT_FILES = 8  # files (including the event itself) the model is asked to check in one update
EXCERPT_RADIUS = 10

# Fields the model may set. "sample" and "body" are never taken from the model's answer.
RECORD_FIELDS = ("title", "kind", "series", "date", "endDate", "venue", "summary")


def ask_json(llm: ChatClient, system: str, user: str) -> dict[str, Any]:
    """Asks for one JSON object. If the reply is unusable, says why and asks once more."""
    messages = [Message("system", system), Message("user", user)]
    for attempt in range(1, JSON_ATTEMPTS + 1):
        reply = llm.chat(messages, json_mode=True)
        try:
            return extract_json_object(reply)
        except ValueError as exc:
            if attempt == JSON_ATTEMPTS:
                raise SiteAgentError(
                    f"the model did not return a usable record ({exc}). Try again, or use a larger model."
                ) from exc
            messages = messages + [
                Message("assistant", reply),
                Message("user", f"That was not a valid JSON object ({exc}). Reply with only the JSON object."),
            ]
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


def plan_add_event(
    site: Site, llm: ChatClient, source_text: str, *, slug: str | None = None, today: dt.date | None = None
) -> Plan:
    system = load_prompt("extract_new_event", today=(today or dt.date.today()).isoformat())
    raw = ask_json(llm, system, source_text)
    body = str(raw.get("body") or "").strip()
    event = _validate_record(_clean(raw), "the event from your text is incomplete or invalid")
    rel = new_event_path(site, event.title, slug)

    record = event.to_frontmatter()
    plan = Plan(summary=f"Add event '{event.title}' as {rel}")
    plan.changes.append(FileChange(rel, None, render_document(record, body)))
    plan.notes.extend(ungrounded_fields(record, source_text))
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
    reply = llm.chat([Message("system", system), Message("user", f"File: {target}\n\n{excerpt}")])
    blocks = parse_edit_blocks(reply)
    if not blocks:
        if NO_CHANGE not in reply:
            plan.failures.append(f"{target}: the model returned no edit blocks")
        return text
    result = apply_edit_blocks(text, blocks)
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
    merged = {**old_record, **_clean(ask_json(llm, system, instruction))}
    new_record = _validate_record(merged, f"the updated {rel} is invalid").to_frontmatter()
    changes = {key: new_record.get(key) for key in RECORD_FIELDS if old_record.get(key) != new_record.get(key)}

    edited: dict[str, str] = {rel: set_frontmatter_values(original, changes)}
    plan = Plan(summary="")
    subs = substitutions_for(old_record, changes)
    needles = search_needles(subs)
    read_only: list[str] = []
    if subs:
        mention_files = sorted({m.rel_path for m in site.find_mentions(needles, exclude={rel})})
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
            if not matching_lines(start_text, needles):
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
