"""Launch readiness: what still stands between the current content and a public launch.

The blockers and warnings here mirror the template's own launch check (scripts/launch-check.mjs), and add what that
check cannot see: placeholder wording inside content and configuration files, and the result of the last site check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from site_agent.appstate import AppState
from site_agent.records import SPECS
from site_agent.repository import Repository
from site_agent.site import Site

PLACEHOLDER_MARKERS = (
    "Institute name",
    "INSTITUTE NAME",
    "example.org",
    "Venue name",
    "Building name",
    "+00-000",
    "Placeholder",
)
LEGAL_PAGES = ("src/pages/accessibility.astro", "src/pages/privacy.astro", "src/pages/terms.astro")
SITE_CONFIG = "src/config/site.ts"


@dataclass
class Report:
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    passes: list[str] = field(default_factory=list)
    samples: list[tuple[str, str, str]] = field(default_factory=list)  # (collection, id, title)

    @property
    def ready(self) -> bool:
        return not self.blockers


def placeholder_hits(site: Site, rel_paths: list[str]) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for rel in rel_paths:
        try:
            lines = site.read(rel).split("\n")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(lines, start=1):
            for marker in PLACEHOLDER_MARKERS:
                if marker in line:
                    hits.append((rel, number, marker))
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
            f"{len(report.samples)} sample entries are still on the site. Replace them or remove them."
        )
    else:
        report.passes.append("No sample entries remain in the collections that can carry one.")

    content_files = [rel for rel in site.iter_text_files() if rel.startswith(site.content_dir + "/")]
    content_hits = placeholder_hits(site, content_files)
    sample_files = {f"{site.content_dir}/{key}/{rid}.md" for key, rid, _ in report.samples}
    loose = [hit for hit in content_hits if hit[0] not in sample_files]
    if loose:
        report.warnings.append(
            f"{len(loose)} placeholder words are in content that is not marked as a sample "
            f"(first one in {loose[0][0]})."
        )

    if site.exists(SITE_CONFIG):
        config_hits = placeholder_hits(site, [SITE_CONFIG])
        if config_hits:
            found = ", ".join(sorted({marker for _, _, marker in config_hits}))
            report.blockers.append(
                f"The site settings file still has placeholder values ({found}). "
                "The technical contact must set them before launch."
            )
        else:
            report.passes.append("The site settings have no placeholder values.")

    legal_drafts = [rel for rel in LEGAL_PAGES if site.exists(rel) and "Draft for review" in site.read(rel)]
    if legal_drafts:
        report.blockers.append(
            "These legal pages are still marked 'Draft for review': "
            + ", ".join(Path(rel).name for rel in legal_drafts)
            + ". The institute must approve them first."
        )

    last = state.last_check()
    if last is None:
        report.warnings.append("The site check has not been run yet. Run it from the Check screen.")
    elif not last.get("ok"):
        report.blockers.append("The last site check did not pass. Fix the problem shown on the Check screen.")
    else:
        report.passes.append(f"The last site check passed ({last.get('time', 'time unknown')}).")
    return report
