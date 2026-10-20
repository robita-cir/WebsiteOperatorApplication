"""The audit: one read-only pass over the whole site that ends in a Markdown report for the technical contact.

It never changes a content file. The only thing it writes is the report, inside the site's .site-agent folder.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from site_agent.apply import state_dir
from site_agent.checks import date_warnings, file_warnings, homepage_warnings
from site_agent.errors import SiteAgentError
from site_agent.launch import placeholder_hits, samples
from site_agent.records import SPECS, validate_file_text
from site_agent.repository import Repository
from site_agent.schemas import COLLECTIONS
from site_agent.site import Site
from site_agent.validate import check_collection


@dataclass
class AuditResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: list[tuple[str, int, int]] = field(default_factory=list)  # (collection, files, sample entries)
    placeholders: list[tuple[str, int, str, bool]] = field(default_factory=list)  # (file, line, marker, is_sample)
    report_path: Path | None = None
    text: str = ""

    @property
    def exit_code(self) -> int:
        return 1 if self.errors else 0


def _content_errors(site: Site, result: AuditResult) -> None:
    for key, spec in SPECS.items():
        for rel in site.collection_files(key):
            try:
                text = site.read(rel)
            except (OSError, UnicodeDecodeError) as exc:
                result.errors.append(f"{rel}: could not read the file: {exc}")
                continue
            result.errors += [f"{rel}: {problem}" for problem in validate_file_text(spec, text)]
    for key in COLLECTIONS:
        errors, warnings = check_collection(site, key)
        result.errors += [f"{issue.rel_path}: {issue.message}" for issue in errors]
        result.warnings += [f"{issue.rel_path}: {issue.message}" for issue in warnings]


def _reference_checks(repo: Repository, result: AuditResult) -> None:
    for spec in SPECS.values():
        for rec_id in repo.ids(spec):
            try:
                record = repo.load(spec, rec_id)
            except SiteAgentError:
                continue  # an unreadable file is already an error from the content check
            blockers, warnings = repo.references(spec, record.values)
            result.errors += [f"{record.rel_path}: {text}" for text in blockers]
            result.warnings += [f"{record.rel_path}: {text}" for text in warnings]


def run_checks(site: Site, today: dt.date) -> AuditResult:
    """Runs every check and returns the result without writing anything."""
    repo = Repository(site)
    result = AuditResult()
    _content_errors(site, result)
    _reference_checks(repo, result)

    sample_entries = samples(repo)
    sample_files = {f"{site.content_dir}/{key}/{rid}.md" for key, rid, _ in sample_entries}
    for key in SPECS:
        result.counts.append((key, len(site.collection_files(key)), sum(1 for s in sample_entries if s[0] == key)))

    content_files = [rel for rel in site.iter_text_files() if rel.startswith(site.content_dir + "/")]
    for rel, number, marker in placeholder_hits(site, content_files):
        is_sample = rel in sample_files
        result.placeholders.append((rel, number, marker, is_sample))
        if not is_sample:  # a sample is meant to hold placeholders; the launch check counts the samples themselves
            result.warnings.append(f"{rel} line {number}: placeholder wording ({marker}).")

    result.warnings += date_warnings(repo, today)
    result.warnings += file_warnings(site, repo)
    result.warnings += homepage_warnings(site, repo)
    return result


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["- None."]


def render_report(site: Site, result: AuditResult, now: dt.datetime) -> str:
    lines = [
        "# Site audit",
        "",
        f"- Run: {now:%Y-%m-%d %H:%M:%S} (this machine's local time)",
        f"- Site folder: {site.root}",
        f"- Dates are compared with today's date on this machine: {now.date().isoformat()}.",
        f"- Result: {len(result.errors)} error(s), {len(result.warnings)} warning(s).",
        "- No content file was changed.",
        "",
        "## Errors",
        "",
        *_bullets(result.errors),
        "",
        "## Warnings",
        "",
        *_bullets(result.warnings),
        "",
        "## Entries per collection",
        "",
        "| Collection | Files | Sample entries |",
        "| --- | ---: | ---: |",
        *[f"| {key} | {files} | {sample} |" for key, files, sample in result.counts],
        "",
        "## Placeholder wording in content",
        "",
        *_bullets(
            [
                f"{rel} line {number}: {marker}" + (" (sample entry)" if is_sample else "")
                for rel, number, marker, is_sample in result.placeholders
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def run_audit(site: Site, now: dt.datetime | None = None) -> AuditResult:
    """Runs the audit and writes the report to <state>/audits/<YYYYMMDD-HHMMSS>.md."""
    now = now or dt.datetime.now()
    result = run_checks(site, now.date())
    result.text = render_report(site, result, now)
    folder = state_dir(site) / "audits"
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{now:%Y%m%d-%H%M%S}"
    path = folder / f"{stem}.md"
    extra = 1
    while path.exists():  # two audits in the same second must not overwrite each other
        extra += 1
        path = folder / f"{stem}-{extra}.md"
    path.write_text(result.text, encoding="utf-8", newline="\n")
    result.report_path = path
    return result
