"""The one place where a form becomes a plan: lists records, checks them, and builds the change for a save or removal.

Nothing here writes files. A plan is only written after it is previewed and approved (see appstate.py and web/app.py).
"""

from __future__ import annotations

import datetime as dt
import difflib
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from site_agent.errors import SiteAgentError
from site_agent.factcheck import fact_problems
from site_agent.frontmatter import parse_document
from site_agent.plan import FileChange, Plan
from site_agent.records import (
    FEATURED_PARTNER_LIMIT,
    FEATURED_PROJECT_LIMIT,
    SPECS,
    Record,
    Spec,
    coerce,
    new_id,
    normalise_doi,
    normalise_name,
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
    def __init__(self, site: Site, today: dt.date | None = None) -> None:
        self.site = site
        self._today = today  # fixed by tests; otherwise the local date at the time of the check

    def today(self) -> dt.date:
        return self._today or dt.date.today()

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

    def _values(self, collection: str, field_name: str) -> dict[str, Any]:
        """The value of one frontmatter key for each readable file of a collection, by file id."""
        spec = SPECS[collection]
        found: dict[str, Any] = {}
        for rec_id in self.ids(spec):
            try:
                data = parse_document(self.site.read(self.rel_path(spec, rec_id))).data
            except (ValueError, OSError, UnicodeDecodeError):
                continue
            if data.get(field_name):
                found[rec_id] = data[field_name]
        return found

    def _names(self, collection: str, field_name: str) -> set[str]:
        return {str(v) for v in self._values(collection, field_name).values()}

    @staticmethod
    def _closest(name: str, names: set[str]) -> str:
        """A hint naming the entries nearest to a name that is not on the site, or an empty string."""
        # Compare the plain forms so that case, accents and "Last, First" do not hide a close match.
        by_plain: dict[str, str] = {}
        for candidate in sorted(names):
            by_plain.setdefault(normalise_name(candidate), candidate)
        close = difflib.get_close_matches(normalise_name(name), list(by_plain), n=3, cutoff=0.6)
        return f" Did you mean: {', '.join(by_plain[c] for c in close)}?" if close else ""

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
                        warnings.append(
                            f'"{name}" is not on the People list, so the name will not link to a profile.'
                            + self._closest(name, people)
                        )
            if f.kind == "partner_name" and value:
                partners = self._names("partners", "name")
                if value not in partners:
                    warnings.append(f'"{value}" is not on the Partners list.' + self._closest(value, partners))
        return blockers, warnings

    def duplicates(self, spec: Spec, values: dict[str, Any], own_id: str | None) -> tuple[list[str], list[str]]:
        """Finds an entry that the new or edited one repeats, not counting itself. Returns (blockers, warnings)."""
        blockers: list[str] = []
        warnings: list[str] = []
        if spec.key == "people" and values.get("name"):
            wanted = normalise_name(values["name"])
            for item in self.listing(spec):
                if item.id != own_id and normalise_name(item.title) == wanted:
                    blockers.append(
                        f"A person called {values['name']} is already on the site ({item.id}). "
                        "Edit that entry instead, or use a different name."
                    )
                    break
        elif spec.key == "publications" and values.get("doi"):
            wanted = normalise_doi(values["doi"])
            for rec_id, doi in self._values("publications", "doi").items():
                if rec_id != own_id and normalise_doi(str(doi)) == wanted:
                    blockers.append(f"A publication with this DOI is already on the site ({rec_id}).")
                    break
        elif spec.key == "events" and values.get("title"):
            wanted = normalise_name(values["title"])
            for item in self.listing(spec):
                if item.id != own_id and normalise_name(item.title) == wanted:
                    warnings.append(
                        f"An event called {values['title']} already exists ({item.id}). Check that this is a new event."
                    )
                    break
        return blockers, warnings

    def limit_warnings(self, spec: Spec, values: dict[str, Any], own_id: str | None) -> list[str]:
        """Proposed limits that do not stop a save but would leave something hidden or out of date."""
        warnings: list[str] = []
        limits = {"projects": ("projects", FEATURED_PROJECT_LIMIT), "partners": ("partners", FEATURED_PARTNER_LIMIT)}
        if spec.key in limits and values.get("featured"):
            noun, limit = limits[spec.key]
            others = [i for i, flag in self._values(spec.key, "featured").items() if i != own_id and flag is True]
            # The homepage shows only `limit` featured entries, so this one is hidden once `limit` others are featured.
            if len(others) >= limit:
                words = {4: "four", 6: "six"}.get(limit, str(limit))
                warnings.append(
                    f"There are already {words} featured {noun}. Unfeature one first, "
                    "or this one will not be shown on the homepage."
                )
        deadline = values.get("deadline")
        if spec.key == "openings" and isinstance(deadline, dt.date) and values.get("status") != "closed":
            if deadline < self.today():
                warnings.append(
                    f"This deadline has passed ({deadline.isoformat()}). Check whether the opening should be closed."
                )
        return warnings

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
        outcome.errors.update(validate_values(spec, values, body, self.today()))
        extra = fact_problems(spec, values, body, facts)
        title = str(values.get(spec.title_field) or "")
        if not title and not outcome.errors.get(spec.title_field):
            outcome.errors[spec.title_field] = f"{spec.field(spec.title_field).label} is required."
        if outcome.errors:
            outcome.values, outcome.body = values, body
            return outcome
        dup_blockers, dup_warnings = self.duplicates(spec, values, None)
        extra += dup_blockers
        outcome.warnings += dup_warnings + self.limit_warnings(spec, values, None)
        rec_id = new_id(spec, title, set(self.ids(spec)))
        rel = self.rel_path(spec, rec_id)
        return self._finish(spec, rel, None, None, lambda: render_new(spec, values, body), values, body, extra, outcome)

    def update(self, spec: Spec, rec_id: str, raw: dict[str, Any], facts: str = "") -> Outcome:
        record = self.load(spec, rec_id)
        outcome = Outcome()
        values, outcome.errors, body = coerce(spec, raw)
        outcome.errors.update(validate_values(spec, values, body, self.today()))
        if outcome.errors:
            outcome.values, outcome.body = values, body
            return outcome
        before = record.text
        old_values = dict(record.values)
        extra = fact_problems(spec, values, body, facts, old_values, _body_of(before))
        outcome.warnings += self._rename_warnings(spec, rec_id, old_values, values)
        dup_blockers, dup_warnings = self.duplicates(spec, values, rec_id)
        extra += dup_blockers
        outcome.warnings += dup_warnings + self.limit_warnings(spec, values, rec_id)
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
