"""Finding and reading event entries in the site."""

from __future__ import annotations

import difflib
import re
from pathlib import PurePosixPath

from pydantic import ValidationError

from site_agent.errors import SiteAgentError
from site_agent.frontmatter import parse_document
from site_agent.schemas import Event, describe_errors
from site_agent.site import Site
from site_agent.text_utils import slugify

COLLECTION = "events"
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def event_files(site: Site) -> list[str]:
    return site.collection_files(COLLECTION)


def _title_of(site: Site, rel: str) -> str | None:
    try:
        title = parse_document(site.read(rel)).data.get("title")
    except (ValueError, OSError, UnicodeDecodeError):
        return None
    return str(title) if title else None


def find_event(site: Site, query: str) -> str:
    """The site path of the event that `query` names: its file name, its exact title, or a close title."""
    files = event_files(site)
    if not files:
        raise SiteAgentError(f"no event files found in {site.content_dir}/{COLLECTION}/")
    needle = query.strip().casefold()
    titles: dict[str, str] = {}
    for rel in files:
        if PurePosixPath(rel).stem.casefold() == needle:
            return rel
        title = _title_of(site, rel)
        if title:
            titles[rel] = title
    exact = [rel for rel, title in titles.items() if title.casefold() == needle]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise SiteAgentError(f"more than one event is called '{query}': {', '.join(exact)}. Use the file name instead.")
    lookup = {title.casefold(): rel for rel, title in titles.items()}
    close = difflib.get_close_matches(needle, list(lookup), n=3, cutoff=0.5)
    hint = f" Did you mean: {', '.join(lookup[c] for c in close)}?" if close else ""
    raise SiteAgentError(f"no event matches '{query}'.{hint}")


def load_event(site: Site, rel: str) -> tuple[Event, str]:
    """The validated event and the file's exact current text."""
    text = site.read(rel)
    try:
        data = parse_document(text).data
    except ValueError as exc:
        raise SiteAgentError(f"{rel}: {exc}") from exc
    try:
        return Event.model_validate(data), text
    except ValidationError as exc:
        raise SiteAgentError(f"{rel} is not a valid event: " + "; ".join(describe_errors(exc))) from exc


def new_event_path(site: Site, title: str, slug: str | None = None) -> str:
    """Where a new event goes. Without a slug, one is made from the title, with a number added if the name is taken."""
    if slug is not None:
        if not _SLUG.fullmatch(slug):
            raise SiteAgentError(f"slug '{slug}' may only contain lower-case letters, digits and single hyphens")
        candidate = slug
    else:
        base = slugify(title) or "event"
        candidate, number = base, 2
        while site.exists(f"{site.content_dir}/{COLLECTION}/{candidate}.md"):
            candidate = f"{base}-{number}"
            number += 1
    rel = f"{site.content_dir}/{COLLECTION}/{candidate}.md"
    if site.exists(rel):
        raise SiteAgentError(f"{rel} already exists. Choose another slug, or update the existing event instead.")
    return rel
