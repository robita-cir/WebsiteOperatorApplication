"""Checks that report on content that looks out of date or wrong. They only read: nothing here changes a file.

Each check returns warnings as short plain sentences. They are warnings, not errors, because only a person can say
whether an old event should be archived or a photo is the right one.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path, PurePosixPath

from site_agent.errors import SiteAgentError
from site_agent.imagecheck import MAX_FILE_BYTES, file_size, is_pdf, is_png, png_size
from site_agent.records import SPECS
from site_agent.repository import Repository
from site_agent.site import Site
from site_agent.text_utils import date_variants, matching_lines, phrase_pattern

STALE_NEWS_DAYS = 60
FUTURE_WORDING = ("coming up", "will take place", "almost here", "upcoming", "next week")
PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
SOCIAL_IMAGE = "public/og-default.png"
SOCIAL_SIZE = (1200, 630)

_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
    "|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
# "10 March 2026" and "March 10, 2026", the two ways pages write a date.
WRITTEN_DATE = re.compile(
    r"(?<!\w)(?:\d{1,2}\s+(?:" + _MONTHS + r")\.?\s+\d{4}|(?:" + _MONTHS + r")\.?\s+\d{1,2},\s*\d{4})(?!\w)",
    re.IGNORECASE,
)


def say_date(day: dt.date) -> str:
    return f"{day.day} {day:%B} {day.year}"


def _as_date(value: object) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    return value if isinstance(value, dt.date) else None


def _records(repo: Repository, key: str) -> list[tuple[str, dict, str]]:
    """(title, values, body) for each readable record of a collection. Broken files are left to the validity check."""
    spec = SPECS[key]
    found = []
    for rec_id in repo.ids(spec):
        try:
            record = repo.load(spec, rec_id)
        except SiteAgentError:
            continue
        found.append((str(record.values.get(spec.title_field) or rec_id), record.values, record.body))
    return found


def _is_sample(values: dict) -> bool:
    return values.get("sample") is True


# --- dates --------------------------------------------------------------------------------------------


def date_warnings(repo: Repository, today: dt.date) -> list[str]:
    """Events that have ended, and news that still says something is coming up long after its date."""
    warnings: list[str] = []
    for title, values, _ in _records(repo, "events"):
        if _is_sample(values):  # a sample is a placeholder with an invented date; the launch check covers it
            continue
        last_day = _as_date(values.get("endDate")) or _as_date(values.get("date"))
        if last_day is not None and last_day < today:
            warnings.append(f"The event {title} ended on {say_date(last_day)}. Archive it or update it.")
    for title, values, body in _records(repo, "news"):
        if _is_sample(values):
            continue
        day = _as_date(values.get("date"))
        if day is None or (today - day).days <= STALE_NEWS_DAYS:
            continue
        text = f"{title}\n{values.get('summary') or ''}\n{body}"
        if any(phrase_pattern(wording).search(text) for wording in FUTURE_WORDING):
            warnings.append(f"News {title} says it is coming up, but is dated {say_date(day)}. Check the wording.")
    return warnings


# --- images and files ---------------------------------------------------------------------------------


def _public_file(site: Site, site_path: str) -> Path | None:
    """The file on disk for a site-root path such as /people/x.jpg, or None when the path is not usable."""
    try:
        return site.resolve("public/" + site_path.lstrip("/"))
    except SiteAgentError:
        return None


def file_warnings(site: Site, repo: Repository) -> list[str]:
    warnings: list[str] = []
    for title, values, _ in _records(repo, "people"):
        photo = values.get("photo")
        if not photo:
            continue
        photo = str(photo)
        path = _public_file(site, photo)
        if path is None or not path.is_file():
            warnings.append(f"The photo for {title} ({photo}) is not in the website's public folder.")
        elif PurePosixPath(photo).suffix.lower() not in PHOTO_SUFFIXES:
            warnings.append(f"The photo for {title} ({photo}) must be a .jpg, .jpeg, .png or .webp file.")
    for title, values, _ in _records(repo, "documents"):
        pdf = values.get("file")
        if not pdf:
            continue
        pdf = str(pdf)
        path = _public_file(site, pdf)
        if path is None or not path.is_file():
            warnings.append(f"The PDF for {title} ({pdf}) is not in the website's public folder.")
        elif not is_pdf(path):
            warnings.append(f"The file for {title} ({pdf}) is not a real PDF. Export it as a PDF again.")
    warnings += _social_image_warnings(site)
    warnings += _large_file_warnings(site)
    return warnings


def _social_image_warnings(site: Site) -> list[str]:
    path = site.root / SOCIAL_IMAGE
    if not path.is_file() or not is_png(path):  # a missing image is the launch check's blocker
        return []
    size = png_size(path)
    if size is None:
        return [f"{SOCIAL_IMAGE} is not a readable PNG picture."]
    if size != SOCIAL_SIZE:
        return [
            f"{SOCIAL_IMAGE} is {size[0]} by {size[1]} pixels. "
            f"The sharing image must be {SOCIAL_SIZE[0]} by {SOCIAL_SIZE[1]} pixels."
        ]
    return []


def _large_file_warnings(site: Site) -> list[str]:
    warnings: list[str] = []
    public = site.root / "public"
    for dirpath, dirnames, filenames in os.walk(public):
        dirnames.sort()
        for name in sorted(filenames):
            full = Path(dirpath) / name
            size = file_size(full)
            if size is not None and size > MAX_FILE_BYTES:
                rel = full.relative_to(site.root).as_posix()
                megabytes = size / (1024 * 1024)
                warnings.append(f"{rel} is {megabytes:.0f} MB. Files over 20 MB slow the site. Make it smaller.")
    return warnings


# --- the homepage and news against the events ------------------------------------------------------


def homepage_warnings(site: Site, repo: Repository) -> list[str]:
    """Lines in the pages and news that name an event next to a date that is not the event's date."""
    pages = [rel for rel in site.iter_text_files() if rel.startswith("src/pages/") and rel.endswith(".astro")]
    files = pages + site.collection_files("news")
    texts: dict[str, str] = {}
    for rel in files:
        try:
            texts[rel] = site.read(rel)
        except (OSError, UnicodeDecodeError):
            continue
    warnings: list[str] = []
    for title, values, _ in _records(repo, "events"):
        if _is_sample(values):
            continue
        days = [d for d in (_as_date(values.get("date")), _as_date(values.get("endDate"))) if d is not None]
        if not days:
            continue
        variants = [v for day in days for v in date_variants(day)]
        shown = " to ".join(say_date(day) for day in days)
        for rel, text in texts.items():
            lines = text.split("\n")
            for index in matching_lines(text, [title]):
                line = lines[index]
                if not WRITTEN_DATE.search(line):
                    continue
                if any(phrase_pattern(v).search(line) for v in variants):
                    continue
                warnings.append(
                    f"{rel} line {index + 1} names the event {title} but gives a different date "
                    f"from the event's date {shown}."
                )
    return warnings


def all_warnings(site: Site, repo: Repository | None = None, today: dt.date | None = None) -> list[str]:
    """Every check in this module. `today` defaults to the machine's local date."""
    repo = repo or Repository(site)
    today = today or dt.date.today()
    return date_warnings(repo, today) + file_warnings(site, repo) + homepage_warnings(site, repo)


__all__ = ["all_warnings", "date_warnings", "file_warnings", "homepage_warnings"]
