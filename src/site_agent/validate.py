"""Checks that content is valid: before a change is written, and for the whole collection on demand."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from pydantic import BaseModel, ValidationError

from site_agent.frontmatter import parse_document
from site_agent.plan import Plan
from site_agent.records import SPECS, validate_file_text
from site_agent.schemas import COLLECTIONS, describe_errors
from site_agent.site import Site


@dataclass(frozen=True)
class Issue:
    rel_path: str
    message: str


def check_text(rel_path: str, text: str, model: type[BaseModel]) -> tuple[list[Issue], list[Issue]]:
    """Returns (errors, warnings) for one file's text."""
    try:
        doc = parse_document(text)
    except ValueError as exc:
        return [Issue(rel_path, str(exc))], []
    errors: list[Issue] = []
    try:
        model.model_validate(doc.data)
    except ValidationError as exc:
        errors = [Issue(rel_path, line) for line in describe_errors(exc)]
    known = {field.alias or name for name, field in model.model_fields.items()}
    warnings = [Issue(rel_path, f"unknown key '{key}' (the site ignores it)") for key in doc.data if key not in known]
    return errors, warnings


def _content_folder(site: Site, rel_path: str) -> str | None:
    """The folder under the content directory that a file sits in (its collection name), or None."""
    content_parts = PurePosixPath(site.content_dir).parts
    parts = PurePosixPath(rel_path).parts
    if parts[: len(content_parts)] != content_parts or len(parts) <= len(content_parts) + 1:
        return None
    return parts[len(content_parts)]


def collection_of(site: Site, rel_path: str) -> str | None:
    """The collection a content file belongs to, or None when the file is not in a known collection."""
    name = _content_folder(site, rel_path)
    return name if name in COLLECTIONS else None


def check_collection(site: Site, collection: str) -> tuple[list[Issue], list[Issue]]:
    errors: list[Issue] = []
    warnings: list[Issue] = []
    for rel in site.collection_files(collection):
        try:
            text = site.read(rel)
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(Issue(rel, f"could not read the file: {exc}"))
            continue
        file_errors, file_warnings = check_text(rel, text, COLLECTIONS[collection])
        errors += file_errors
        warnings += file_warnings
    return errors, warnings


def check_plan(site: Site, plan: Plan) -> list[Issue]:
    """Problems that would make the plan unsafe to write. An empty list means it can be written.

    Every content file is checked against its collection's rules, not only events, so a change to a news item or a
    person cannot write a file the site would reject.
    """
    problems: list[Issue] = []
    for change in plan.changes:
        if not site.is_writable(change.rel_path):
            problems.append(Issue(change.rel_path, "not in the paths the agent may change"))
            continue
        if change.after is None:  # a removal leaves nothing to check
            continue
        folder = _content_folder(site, change.rel_path)
        if folder in COLLECTIONS:
            errors, _ = check_text(change.rel_path, change.after, COLLECTIONS[folder])
            problems += errors
        elif folder in SPECS:
            problems += [Issue(change.rel_path, text) for text in validate_file_text(SPECS[folder], change.after)]
    return problems


def sample_files(site: Site, collection: str) -> list[str]:
    """Files still marked `sample: true`. The site's launch check refuses to ship while any remain."""
    marked = []
    for rel in site.collection_files(collection):
        try:
            data = parse_document(site.read(rel)).data
        except (ValueError, OSError, UnicodeDecodeError):
            continue
        if data.get("sample") is True:
            marked.append(rel)
    return marked
