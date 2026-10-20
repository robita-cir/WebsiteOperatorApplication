"""Launch readiness: what still stands between the current content and a public launch.

The blockers and warnings here mirror the template's own launch check (scripts/launch-check.mjs), and add what that
check cannot see: placeholder wording inside content and configuration files, and the result of the last site check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from site_agent.appstate import AppState
from site_agent.records import SPECS
from site_agent.repository import Repository
from site_agent.site import Site

# Each marker has a plain label (shown to the operator) and a case-insensitive pattern. Numbered names such as
# "Partner 3" are patterns so every number is caught. "Placeholder" skips the HTML attribute and CSS forms
# (placeholder="...", ::placeholder), which are real interface code and not unfinished wording.
_MARKER_SOURCES = (
    ("Institute name", r"institute name"),
    ("example.org", r"example\.org"),
    ("Venue name", r"venue name"),
    ("Building name", r"building name"),
    ("+00-000", r"\+00-000"),
    ("[Sample]", r"\[sample\]"),
    ("Partner N", r"\bpartner \d+\b"),
    ("Funder N", r"\bfunder \d+\b"),
    ("Funded programme N", r"\bfunded programme \d+\b"),
    ("Country name", r"country name"),
    ("Amount placeholder", r"amount placeholder"),
    ("Facility type", r"facility type"),
    ("Sample answer", r"sample answer"),
    # Last, so a line that matches a more specific marker is labelled with that one.
    ("Placeholder", r"(?<![.\w:-])placeholder(?!\s*=)"),
)
PLACEHOLDER_MARKERS = tuple(label for label, _ in _MARKER_SOURCES)
_MARKER_PATTERNS = tuple((label, re.compile(source, re.IGNORECASE)) for label, source in _MARKER_SOURCES)
# Page wording and site configuration live in these folders. The technical contact edits them, not the operator.
PAGE_PREFIXES = ("src/pages/", "src/config/")
LEGAL_PAGES = ("src/pages/accessibility.astro", "src/pages/privacy.astro", "src/pages/terms.astro")
SITE_CONFIG = "src/config/site.ts"
STYLEGUIDE_PAGE = "src/pages/styleguide.astro"
SOCIAL_IMAGE = "public/og-default.png"
SEARCH_INDEX = "dist/pagefind/pagefind-ui.js"
# The same patterns as the template's check: an item to complete in legal text, the club link in the site settings,
# and a portrait line in a person's file.
OPEN_ITEM = re.compile(r"\[[A-Za-z][^\]]*\]")
CLUB_URL = re.compile(r"robita[\s\S]*?url:\s*'([^']+)'")
PHOTO_LINE = re.compile(r"^photo:", re.MULTILINE)


class Note(str):
    """A blocker or warning. It is a plain string, and also says where to fix it and who does the fixing."""

    link: str | None
    owner: str

    def __new__(cls, text: str, link: str | None = None, owner: str = "operator") -> Note:
        note = super().__new__(cls, text)
        note.link = link
        note.owner = owner
        return note


@dataclass
class Report:
    blockers: list[Note] = field(default_factory=list)
    warnings: list[Note] = field(default_factory=list)
    passes: list[str] = field(default_factory=list)
    samples: list[tuple[str, str, str]] = field(default_factory=list)  # (collection, id, title)

    @property
    def ready(self) -> bool:
        return not self.blockers


def placeholder_hits(site: Site, rel_paths: list[str]) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for rel in rel_paths:
        # A file that is not valid text (or vanished mid-scan) cannot hold wording to fix, so it is skipped.
        try:
            lines = site.read(rel).split("\n")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(lines, start=1):
            for label, pattern in _MARKER_PATTERNS:
                if pattern.search(line):
                    hits.append((rel, number, label))
                    break
    return hits


def samples(repo: Repository) -> list[tuple[str, str, str]]:
    found = []
    for key, spec in SPECS.items():
        if not spec.sample:
            continue
        for item in repo.listing(spec):
            if item.sample:
                found.append((key, item.id, item.title))
    return found


def launch_report(site: Site, repo: Repository, state: AppState) -> Report:
    report = Report()
    report.samples = samples(repo)
    if report.samples:
        report.blockers.append(
            Note(
                f"{len(report.samples)} sample entries are still on the site. Replace them or remove them.", "/samples"
            )
        )
    else:
        report.passes.append("No sample entries remain in the collections that can carry one.")
    if site.exists(STYLEGUIDE_PAGE):
        report.blockers.append(
            Note(f"{STYLEGUIDE_PAGE} is still present. Delete it before launch.", owner="technical contact")
        )

    all_files = site.iter_text_files()
    content_files = [rel for rel in all_files if rel.startswith(site.content_dir + "/")]
    content_hits = placeholder_hits(site, content_files)
    sample_files = {f"{site.content_dir}/{key}/{rid}.md" for key, rid, _ in report.samples}
    loose = [hit for hit in content_hits if hit[0] not in sample_files]
    if loose:
        report.warnings.append(
            Note(
                f"{len(loose)} placeholder words are in content that is not marked as a sample "
                f"(first one in {loose[0][0]}).",
                "/samples",
            )
        )

    # The site settings file has its own blocker below, and the styleguide page must be deleted, so neither is
    # counted again as page wording.
    page_files = [
        rel for rel in all_files if rel.startswith(PAGE_PREFIXES) and rel not in (SITE_CONFIG, STYLEGUIDE_PAGE)
    ]
    page_hits = placeholder_hits(site, page_files)
    if page_hits:
        report.warnings.append(
            Note(
                f"{len(page_hits)} placeholder words are in the site pages. The technical contact edits those files.",
                owner="technical contact",
            )
        )

    if site.exists(SITE_CONFIG):
        config_hits = placeholder_hits(site, [SITE_CONFIG])
        if config_hits:
            found = ", ".join(sorted({marker for _, _, marker in config_hits}))
            report.blockers.append(
                Note(
                    f"The site settings file still has placeholder values ({found}). "
                    "The technical contact must set them before launch.",
                    owner="technical contact",
                )
            )
        else:
            report.passes.append("The site settings have no placeholder values.")
        club = CLUB_URL.search(site.read(SITE_CONFIG))
        if club and ("github.com" in club.group(1) or "example." in club.group(1)):
            report.warnings.append(
                Note(
                    "The student club pointer still goes to a repository or placeholder address. "
                    "Replace it with the club site's live address.",
                    owner="technical contact",
                )
            )

    legal_drafts = [rel for rel in LEGAL_PAGES if site.exists(rel) and "Draft for review" in site.read(rel)]
    if legal_drafts:
        report.blockers.append(
            Note(
                "These legal pages are still marked 'Draft for review': "
                + ", ".join(Path(rel).name for rel in legal_drafts)
                + ". The institute must approve them first.",
                owner="institute",
            )
        )
    for rel in LEGAL_PAGES:
        if not site.exists(rel):
            continue
        open_items = OPEN_ITEM.findall(site.read(rel))
        if open_items:
            shown = " ".join(open_items[:3]) + (" …" if len(open_items) > 3 else "")
            report.warnings.append(
                Note(f"{rel} has {len(open_items)} bracketed placeholder(s) to complete: {shown}", owner="institute")
            )

    last = state.last_check()
    if last is None:
        report.warnings.append(Note("The site check has not been run yet. Run it from the Check screen.", "/check"))
    elif not last.get("ok"):
        report.blockers.append(
            Note("The last site check did not pass. Fix the problem shown on the Check screen.", "/check")
        )
    else:
        report.passes.append(f"The last site check passed ({last.get('time', 'time unknown')}).")

    if not site.exists(SOCIAL_IMAGE):
        report.blockers.append(
            Note(
                f"{SOCIAL_IMAGE} is missing. Generate it (see docs/06-handover-checklist.md).",
                owner="technical contact",
            )
        )
    if not site.exists(SEARCH_INDEX):
        report.warnings.append(
            Note("No search index in dist/. Run npm run build before checking the site.", owner="technical contact")
        )

    people = site.collection_files("people")
    without_photo = [rel for rel in people if not PHOTO_LINE.search(site.read(rel))]
    if without_photo:
        report.warnings.append(
            Note(
                f"{len(without_photo)} of {len(people)} people entries have no portrait (initials are shown).",
                "/c/people",
            )
        )
    return report
