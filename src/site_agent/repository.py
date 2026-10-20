"""The one place where a form becomes a plan: lists records, checks them, and builds the change for a save or removal.

Nothing here writes files. A plan is only written after it is previewed and approved (see appstate.py and web/app.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from site_agent.errors import SiteAgentError
from site_agent.factcheck import fact_problems
from site_agent.frontmatter import parse_document
from site_agent.plan import FileChange, Plan
from site_agent.records import (
    SPECS,
    Record,
    Spec,
    coerce,
    new_id,
    plain_changes,
    record_from_text,
    render_changed,
    render_new,
    validate_file_text,
    validate_values,
)
from site_agent.site import Site

# Which field of one collection names an entry in another. A change to the named entry is reported with its dependants.
DEPENDENCIES = (
    ("projects", "students", "people", "name"),
    ("funding", "partner", "partners", "name"),
)


@dataclass
class ListItem:
    id: str
    title: str
    rel_path: str
    sample: bool
    order: int
    problems: list[str] = field(default_factory=list)


@dataclass
class Outcome:
    """What the form led to. Blockers stop the save; warnings need an explicit tick before approval."""

    errors: dict[str, str] = field(default_factory=dict)  # by field name
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)  # plain sentences
    plan: Plan | None = None
    values: dict[str, Any] = field(default_factory=dict)
    body: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors and not self.blockers


class Repository:
    def __init__(self, site: Site) -> None:
        self.site = site

    # --- lookup -----------------------------------------------------------------------------------

    def spec(self, key: str) -> Spec:
        if key not in SPECS:
            raise SiteAgentError(f"there is no collection called '{key}'")
        return SPECS[key]

    def rel_path(self, spec: Spec, rec_id: str) -> str:
        return f"{self.site.content_dir}/{spec.key}/{rec_id}.md"

    def ids(self, spec: Spec) -> list[str]:
        return [PurePosixPath(rel).stem for rel in self.site.collection_files(spec.key)]

    def load(self, spec: Spec, rec_id: str) -> Record:
        rel = self.rel_path(spec, rec_id)
        if not self.site.exists(rel):
            raise SiteAgentError(f"no {spec.singular} called '{rec_id}' exists")
        text = self.site.read(rel)
        try:
            return record_from_text(spec, rec_id, rel, text)
        except ValueError as exc:
            raise SiteAgentError(f"{rel} cannot be read: {exc}") from exc

    def listing(self, spec: Spec) -> list[ListItem]:
        items: list[ListItem] = []
        for rec_id in self.ids(spec):
            rel = self.rel_path(spec, rec_id)
            try:
                text = self.site.read(rel)
                record = record_from_text(spec, rec_id, rel, text)
                problems = validate_file_text(spec, text)
            except (ValueError, OSError, UnicodeDecodeError) as exc:
                items.append(ListItem(rec_id, rec_id, rel, False, 100, [f"cannot be read: {exc}"]))
                continue
            title = str(record.values.get(spec.title_field) or rec_id)
            order = record.values.get("order")
            items.append(
                ListItem(
                    id=rec_id,
                    title=title,
                    rel_path=rel,
                    sample=bool(record.values.get("sample")),
                    order=order if isinstance(order, int) else 100,
                    problems=problems,
                )
            )
        return sorted(items, key=lambda i: (i.order, i.title.casefold()))

    def _names(self, collection: str, field_name: str) -> set[str]:
        spec = SPECS[collection]
        names: set[str] = set()
        for rec_id in self.ids(spec):
            try:
                data = parse_document(self.site.read(self.rel_path(spec, rec_id))).data
            except (ValueError, OSError, UnicodeDecodeError):
                continue
            if data.get(field_name):
                names.add(str(data[field_name]))
        return names

    # --- checks across records and files ----------------------------------------------------------

    def references(self, spec: Spec, values: dict[str, Any]) -> tuple[list[str], list[str]]:
        """Checks that the entry's links point at things that exist. Returns (blockers, warnings)."""
        blockers: list[str] = []
        warnings: list[str] = []
        for f in spec.fields:
            value = values.get(f.name)
            if f.kind == "path" and value:
                if not (self.site.root / "public" / str(value).lstrip("/")).is_file():
                    blockers.append(
                        f"{f.label}: the file {value} is not in the website's public folder. "
                        "Copy it there first, then save again."
                    )
            if f.kind == "person_list" and value:
                people = self._names("people", "name")
                for name in value:
                    if name not in people:
                        warnings.append(f'"{name}" is not on the People list, so the name will not link to a profile.')
            if f.kind == "partner_name" and value and value not in self._names("partners", "name"):
                warnings.append(f'"{value}" is not on the Partners list.')
        return blockers, warnings

    def dependants(self, spec: Spec, rec_id: str) -> list[str]:
        """Entries in other collections that name this one, for example a project that lists a person."""
        if spec.key not in {target for _, _, target, _ in DEPENDENCIES}:
            return []
        record = self.load(spec, rec_id)
        name = str(record.values.get(spec.title_field) or "")
        found: list[str] = []
        for source, field_name, target, _ in DEPENDENCIES:
            if target != spec.key:
                continue
            source_spec = SPECS[source]
            for other_id in self.ids(source_spec):
                try:
                    data = parse_document(self.site.read(self.rel_path(source_spec, other_id))).data
                except (ValueError, OSError, UnicodeDecodeError):
                    continue
                named = data.get(field_name)
                hit = (name in named) if isinstance(named, list) else (named == name)
                if hit:
                    found.append(f"{source_spec.singular.capitalize()} '{data.get('title', other_id)}'")
        return found

    # --- building outcomes --------------------------------------------------------------------------

    def _finish(
        self,
        spec: Spec,
        rel: str,
        before: str | None,
        old_values: dict[str, Any] | None,
        new_text_fn,
        values: dict[str, Any],
        body: str,
        extra_blockers: list[str],
        outcome: Outcome,
    ) -> Outcome:
        ref_blockers, ref_warnings = self.references(spec, values)
        outcome.blockers += extra_blockers + ref_blockers
        outcome.warnings += ref_warnings
        outcome.values, outcome.body = values, body
        if not outcome.ok:
            return outcome
        new_text = new_text_fn()
        problems = validate_file_text(spec, new_text)
        if problems:
            outcome.blockers += problems
            return outcome
        if new_text == before:
            outcome.warnings.append("Nothing has changed, so there is nothing to save.")
            return outcome
        outcome.changes = plain_changes(spec, old_values, values, _body_of(before), body)
        title = str(values.get(spec.title_field) or "")
        summary = f"{'Add' if before is None else 'Update'} {spec.singular} '{title}' ({rel})"
        outcome.plan = Plan(summary=summary, changes=[FileChange(rel, before, new_text)])
        return outcome

    def create(self, spec: Spec, raw: dict[str, Any], facts: str = "") -> Outcome:
        outcome = Outcome()
        values, outcome.errors, body = coerce(spec, raw)
        outcome.errors.update(validate_values(spec, values, body))
        extra = fact_problems(spec, values, body, facts)
        title = str(values.get(spec.title_field) or "")
        if not title and not outcome.errors.get(spec.title_field):
            outcome.errors[spec.title_field] = f"{spec.field(spec.title_field).label} is required."
        if outcome.errors:
            outcome.values, outcome.body = values, body
            return outcome
        rec_id = new_id(spec, title, set(self.ids(spec)))
        rel = self.rel_path(spec, rec_id)
        return self._finish(spec, rel, None, None, lambda: render_new(spec, values, body), values, body, extra, outcome)

    def update(self, spec: Spec, rec_id: str, raw: dict[str, Any], facts: str = "") -> Outcome:
        record = self.load(spec, rec_id)
        outcome = Outcome()
        values, outcome.errors, body = coerce(spec, raw)
        outcome.errors.update(validate_values(spec, values, body))
        if outcome.errors:
            outcome.values, outcome.body = values, body
            return outcome
        before = record.text
        old_values = dict(record.values)
        extra = fact_problems(spec, values, body, facts, old_values, _body_of(before))
        outcome.warnings += self._rename_warnings(spec, rec_id, old_values, values)
        return self._finish(
            spec,
            record.rel_path,
            before,
            old_values,
            lambda: render_changed(before, spec, old_values, values, body),
            values,
            body,
            extra,
            outcome,
        )

    def archive(self, spec: Spec, rec_id: str) -> Outcome:
        """Plans the removal of a record. The file is removed from the site and kept in the run backup for undo."""
        if not spec.can_archive:
            raise SiteAgentError(f"{spec.label} cannot be removed; only their content can be changed.")
        record = self.load(spec, rec_id)
        outcome = Outcome(values=dict(record.values), body=record.body)
        for name in self.dependants(spec, rec_id):
            outcome.warnings.append(f"{name} still names this {spec.singular}. Update it, or the name will not link.")
        title = str(record.values.get(spec.title_field) or rec_id)
        outcome.changes = [
            f"The {spec.singular} '{title}' will be removed from the website.",
            "A copy is kept, so the removal can be undone from History.",
        ]
        outcome.plan = Plan(
            summary=f"Remove {spec.singular} '{title}' ({record.rel_path})",
            changes=[FileChange(record.rel_path, record.text, None)],
        )
        return outcome

    def _rename_warnings(
        self, spec: Spec, rec_id: str, old_values: dict[str, Any], new_values: dict[str, Any]
    ) -> list[str]:
        if spec.key != "people" or old_values.get("name") == new_values.get("name"):
            return []
        names = self.dependants(spec, rec_id)
        if not names:
            return []
        return [f"Renaming this person breaks the student list of: {', '.join(names)}. Update those projects too."]


def _body_of(text: str | None) -> str:
    if text is None:
        return ""
    return parse_document(text).body.strip()


__all__ = ["Repository", "Outcome", "ListItem", "DEPENDENCIES"]
