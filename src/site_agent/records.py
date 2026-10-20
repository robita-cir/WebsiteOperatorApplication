"""The content rules: one table per collection, used by the forms, the checks and the file writer.

The tables mirror `src/content.config.ts` in the CIR template (commit 23f4878b). Limits that the template does not
enforce, such as https-only addresses and DOIs without a web prefix, are proposed rules (see docs/REQUIREMENTS.md).
A change to the template's schema means a change here, and TEMPLATE_CONTRACT.md says how to check it.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from site_agent.frontmatter import parse_document, render_document, set_body, set_frontmatter_values
from site_agent.text_utils import slugify

AREAS = {
    "human-robot-interaction": "Human-robot interaction",
    "perception-manipulation": "Perception and manipulation",
    "navigation-planning": "Navigation and planning",
    "assistive-health": "Assistive and health robotics",
    "other": "Other",
}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")
_DOI_PREFIX = re.compile(r"^(https?://)?(dx\.)?doi\.org/", re.IGNORECASE)

# Proposed limits from the requirements (docs/REQUIREMENTS.md U6, U9, U26, E14, E46), not enforced by the template.
TITLE_MAX_CHARS = 120
YEAR_MIN = 1950  # the latest allowed year is next year, so a paper in press can be listed
FEATURED_PROJECT_LIMIT = 4  # the homepage shows this many featured projects and hides the rest
FEATURED_PARTNER_LIMIT = 6


@dataclass(frozen=True)
class Field:
    name: str  # the frontmatter key, for example "endDate"
    label: str  # what the operator sees
    kind: str  # text, long, choice, int, bool, date, url, email, list, doi, path, person_list, partner_name
    required: bool = False
    choices: tuple[tuple[str, str], ...] = ()  # (stored value, label)
    default: Any = None
    hint: str = ""
    prefix: str = ""  # for path: the folder under public/ the file must be in
    min_items: int = 0


@dataclass(frozen=True)
class Spec:
    key: str  # folder under src/content, and the collection's id in the app
    label: str  # plural, for headings
    singular: str
    fields: tuple[Field, ...]
    title_field: str
    body_label: str | None = None  # collections with a Markdown body (the text under the top block)
    sample: bool = True  # whether the template lets an entry carry `sample: true`
    fixed_ids: tuple[str, ...] = ()  # only these files may exist (research directions)
    nav: str = "Content"

    def field(self, name: str) -> Field:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(name)

    @property
    def can_add(self) -> bool:
        return not self.fixed_ids

    @property
    def can_archive(self) -> bool:
        return not self.fixed_ids


def _choices(*pairs: tuple[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(pairs)


ORDER = Field("order", "Order (lower numbers are listed first)", "int", default=100)
SAMPLE = Field("sample", "Sample entry: a placeholder to replace or remove before launch", "bool")

PEOPLE = Spec(
    key="people",
    label="People",
    singular="person",
    title_field="name",
    body_label="Biography",
    nav="Content",
    fields=(
        Field("name", "Name", "text", required=True, hint="Write the name as it should appear on the website."),
        Field(
            "group",
            "Group",
            "choice",
            required=True,
            choices=_choices(
                ("faculty", "Faculty"),
                ("scholar", "Research scholar"),
                ("mtech", "M.Tech student"),
                ("alumni-research", "Research alumnus"),
                ("alumni-mtech", "M.Tech alumnus"),
                ("alumni-btech", "B.Tech alumnus"),
            ),
        ),
        Field("role", "Role", "text", hint="For example: Professor, PhD scholar."),
        Field("dept", "Department", "text"),
        Field("interests", "Research interests", "list", hint="One per line."),
        Field("homepage", "Homepage", "url", hint="A full web address that starts with https://"),
        Field("photo", "Portrait file", "path", prefix="/people/", hint="Example: /people/jane-doe.jpg"),
        ORDER,
        SAMPLE,
    ),
)

PROJECTS = Spec(
    key="projects",
    label="Student and research projects",
    singular="project",
    title_field="title",
    body_label="Abstract",
    nav="Content",
    fields=(
        Field("title", "Title", "text", required=True),
        Field("area", "Research direction", "choice", required=True, choices=tuple(AREAS.items())),
        Field(
            "students",
            "Students",
            "person_list",
            required=True,
            hint="One name per line, spelled as on the People page. A matching name becomes a link.",
        ),
        Field(
            "status",
            "Status",
            "choice",
            choices=_choices(("Active", "Active"), ("Completed", "Completed"), ("Planned", "Planned")),
        ),
        Field("summary", "Summary for the project card", "long"),
        Field("featured", "Show on the home page", "bool"),
        ORDER,
        SAMPLE,
    ),
)

RESEARCH = Spec(
    key="research",
    label="Research directions",
    singular="research direction",
    title_field="title",
    nav="Content",
    sample=False,
    fixed_ids=tuple(AREAS)[:4],
    fields=(
        Field("code", "Short code", "text", required=True, hint="For example: NP"),
        Field("title", "Title", "text", required=True),
        Field("description", "Description", "long", required=True),
        ORDER,
    ),
)

EVENTS = Spec(
    key="events",
    label="Events",
    singular="event",
    title_field="title",
    body_label="Description",
    nav="Events and news",
    fields=(
        Field("title", "Title", "text", required=True),
        Field(
            "kind",
            "Kind",
            "choice",
            required=True,
            choices=_choices(("workshop", "Workshop"), ("programme", "Programme"), ("talk", "Talk")),
        ),
        Field("series", "Series", "text", hint="Only names the centre has agreed appear in the series block."),
        Field("date", "First day", "date", required=True),
        Field("endDate", "Last day (if more than one day)", "date", hint="Leave empty for a one-day event."),
        Field("venue", "Place and city", "text"),
        Field("summary", "Summary for the list", "long"),
        SAMPLE,
    ),
)

NEWS = Spec(
    key="news",
    label="News, announcements and insights",
    singular="news item",
    title_field="title",
    body_label="Article text",
    nav="Events and news",
    fields=(
        Field("title", "Headline", "text", required=True),
        Field(
            "kind",
            "Kind",
            "choice",
            required=True,
            choices=_choices(("news", "News"), ("announcement", "Announcement"), ("insight", "Insight")),
        ),
        Field("date", "Date", "date", required=True),
        Field("summary", "Summary for the list", "long", required=True),
        SAMPLE,
    ),
)

OPENINGS = Spec(
    key="openings",
    label="Job and study openings",
    singular="opening",
    title_field="title",
    nav="Opportunities",
    fields=(
        Field("title", "Title", "text", required=True),
        Field(
            "type",
            "Type",
            "choice",
            required=True,
            choices=_choices(
                ("phd", "PhD"),
                ("mtech", "M.Tech"),
                ("research-assistant", "Research assistant"),
                ("internship", "Internship"),
                ("faculty", "Faculty"),
                ("staff", "Staff"),
                ("other", "Other"),
            ),
        ),
        Field("status", "Status", "choice", required=True, choices=_choices(("open", "Open"), ("closed", "Closed"))),
        Field("deadline", "Deadline", "date"),
        Field("summary", "Summary", "long", required=True),
        Field("applyEmail", "Email for applications", "email"),
        ORDER,
        SAMPLE,
    ),
)

PUBLICATIONS = Spec(
    key="publications",
    label="Publications",
    singular="publication",
    title_field="title",
    nav="Research",
    fields=(
        Field("title", "Title", "text", required=True),
        Field(
            "authors", "Authors, in the order of the paper", "list", required=True, min_items=1, hint="One per line."
        ),
        Field("venue", "Journal or conference", "text", required=True),
        Field("year", "Year", "int", required=True),
        Field(
            "type",
            "Type",
            "choice",
            required=True,
            choices=_choices(
                ("journal", "Journal"),
                ("conference", "Conference"),
                ("workshop", "Workshop"),
                ("preprint", "Preprint"),
                ("thesis", "Thesis"),
                ("other", "Other"),
            ),
        ),
        Field("doi", "DOI", "doi", hint="For example: 10.1000/xyz123. Do not type the web address."),
        Field("url", "Web link", "url", hint="A full address that starts with https://"),
        Field("area", "Research direction", "choice", choices=tuple(AREAS.items())),
        SAMPLE,
    ),
)

PARTNERS = Spec(
    key="partners",
    label="Partners",
    singular="partner",
    title_field="name",
    nav="Partners and funding",
    sample=False,
    fields=(
        Field("name", "Name", "text", required=True),
        Field("country", "Country", "text"),
        Field(
            "kind",
            "Kind",
            "choice",
            required=True,
            choices=_choices(("academic", "Academic"), ("industry", "Industry")),
        ),
        Field(
            "status", "Status", "choice", required=True, choices=_choices(("present", "Present"), ("former", "Former"))
        ),
        Field("summary", "One-line description", "long"),
        ORDER,
        Field("featured", "Show on the home page", "bool"),
    ),
)

FUNDING = Spec(
    key="funding",
    label="Funded programmes",
    singular="funded programme",
    title_field="title",
    nav="Partners and funding",
    sample=False,
    fields=(
        Field("title", "Title", "text", required=True),
        Field("funder", "Funding body", "text", required=True),
        Field("partner", "Partner", "partner_name", hint="Must match a name on the Partners list."),
        Field("amount", "Amount, as the funder writes it", "text", hint="For example: EUR 1.2 million"),
        Field("period", "Period", "text", hint="For example: 2024 to 2027"),
        Field("summary", "Summary", "long"),
        ORDER,
    ),
)

FACILITIES = Spec(
    key="facilities",
    label="Facilities and equipment",
    singular="facility",
    title_field="name",
    nav="Research",
    fields=(
        Field("name", "Name", "text", required=True),
        Field("kind", "Type", "text", required=True, hint="For example: Robot platform"),
        Field("summary", "What it is and what it is used for", "long", required=True),
        ORDER,
        SAMPLE,
    ),
)

DOCUMENTS = Spec(
    key="documents",
    label="Documents",
    singular="document",
    title_field="title",
    nav="Documents and gallery",
    fields=(
        Field("title", "Title", "text", required=True),
        Field(
            "kind",
            "Kind",
            "choice",
            required=True,
            choices=_choices(
                ("report", "Report"),
                ("brochure", "Brochure"),
                ("policy", "Policy"),
                ("form", "Form"),
                ("other", "Other"),
            ),
        ),
        Field("date", "Date", "date"),
        Field("description", "Description", "long", required=True),
        Field("file", "PDF file", "path", prefix="/documents/", hint="Example: /documents/annual-report-2025.pdf"),
        ORDER,
        SAMPLE,
    ),
)

GALLERY = Spec(
    key="gallery",
    label="Gallery albums",
    singular="album",
    title_field="title",
    nav="Documents and gallery",
    fields=(
        Field("title", "Title", "text", required=True),
        Field("period", "Period", "text", hint="For example: 2026"),
        Field("description", "Description", "long", required=True),
        ORDER,
        SAMPLE,
    ),
)

SPECS: dict[str, Spec] = {
    spec.key: spec
    for spec in (
        PEOPLE,
        PROJECTS,
        RESEARCH,
        EVENTS,
        NEWS,
        OPENINGS,
        PUBLICATIONS,
        PARTNERS,
        FUNDING,
        FACILITIES,
        DOCUMENTS,
        GALLERY,
    )
}


@dataclass
class Record:
    """One content file, read into values the forms and checks understand."""

    spec: Spec
    id: str
    rel_path: str
    text: str
    values: dict[str, Any]
    body: str


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def coerce(spec: Spec, raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str], str]:
    """Turns form input (strings, or lists of lines) into typed values. Returns (values, errors by field, body).

    `raw` maps field name to the submitted value. Booleans arrive as "on" when ticked, or are absent.
    The body is taken from the key "body".
    """
    values: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for f in spec.fields:
        value = raw.get(f.name)
        try:
            values[f.name] = _coerce_one(f, value)
        except ValueError as exc:
            errors[f.name] = str(exc)
            values[f.name] = None
        if f.required and _empty(values[f.name]) and f.name not in errors:
            errors[f.name] = f"{f.label} is required."
        if f.kind == "list" and f.min_items and len(values.get(f.name) or []) < f.min_items:
            errors[f.name] = f"{f.label} must have at least one entry."
    body = str(raw.get("body") or "").strip() if spec.body_label else ""
    return values, errors, body


def _coerce_one(f: Field, value: Any) -> Any:
    if f.kind == "bool":
        return value in (True, "on", "true", "1", "yes")
    if f.kind == "list" or f.kind == "person_list":
        if value is None:
            return []
        lines = value if isinstance(value, list) else str(value).splitlines()
        return [line.strip() for line in lines if line.strip()]
    text = "" if value is None else str(value).strip()
    if text == "":
        return f.default if f.kind == "int" and f.default is not None else None
    if f.kind in ("text", "long", "partner_name"):
        return text
    if f.kind == "choice":
        allowed = {stored for stored, _ in f.choices}
        if text not in allowed:
            raise ValueError(f"{f.label}: choose one of the listed options.")
        return text
    if f.kind == "int":
        if not re.fullmatch(r"\d{1,4}", text):
            raise ValueError(f"{f.label} must be a whole number.")
        return int(text)
    if f.kind == "date":
        try:
            return dt.date.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{f.label} must be a date such as 2026-11-05.") from exc
    if f.kind == "url":
        parsed = urlparse(text)
        if not text.startswith("https://") or not parsed.netloc:
            raise ValueError(f"{f.label} must start with https://. Change http:// to https:// or leave it empty.")
        return text
    if f.kind == "email":
        if not _EMAIL.match(text):
            raise ValueError(f"{f.label} does not look like an email address.")
        return text
    if f.kind == "doi":
        if _DOI_PREFIX.match(text):
            raise ValueError(f"{f.label}: remove the web address and keep only the number, for example 10.1000/xyz123.")
        if not _DOI.match(text):
            raise ValueError(f"{f.label} must look like 10.1000/xyz123.")
        return text
    if f.kind == "path":
        if not text.startswith(f.prefix) or " " in text:
            raise ValueError(f"{f.label} must start with {f.prefix} and contain no spaces.")
        return text
    raise ValueError(f"unknown field kind {f.kind}")


def normalise_name(name: str) -> str:
    """A name in the form used to compare names: "Doe, Jane" and "jane  DOE" both become "jane doe"."""
    text = str(name).strip()
    if "," in text:
        last, _, first = text.partition(",")
        text = f"{first} {last}"
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = "".join(ch for ch in text if ch.isalnum() or ch.isspace())
    return " ".join(text.split())


def normalise_doi(doi: str) -> str:
    """A DOI without its web prefix and in lower case, since DOIs are not case sensitive."""
    text = str(doi).strip()
    text = _DOI_PREFIX.sub("", text)
    if text.lower().startswith("doi:"):
        text = text[4:]
    return text.strip().lower()


def validate_values(spec: Spec, values: dict[str, Any], body: str = "", today: dt.date | None = None) -> dict[str, str]:
    """Rules that span fields, and checks that can be made without other files."""
    errors: dict[str, str] = {}
    latest_year = (today or dt.date.today()).year + 1
    for f in spec.fields:
        value = values.get(f.name)
        if f.kind == "int" and f.name == "year" and isinstance(value, int) and not YEAR_MIN <= value <= latest_year:
            errors[f.name] = f"Year must be between {YEAR_MIN} and {latest_year}."
        if f.name == "title" and isinstance(value, str) and len(value) > TITLE_MAX_CHARS:
            errors[f.name] = f"Title is too long ({len(value)} characters). Keep it to {TITLE_MAX_CHARS} characters."
    if spec.key == "events" and values.get("endDate") and values.get("date"):
        if values["endDate"] < values["date"]:
            errors["endDate"] = "The last day cannot be before the first day."
    return errors


def record_from_text(spec: Spec, rec_id: str, rel_path: str, text: str) -> Record:
    """Reads a file into a Record. Unknown keys stay in the file and are not shown."""
    doc = parse_document(text)
    values: dict[str, Any] = {}
    for f in spec.fields:
        if f.name in doc.data:
            values[f.name] = doc.data[f.name]
        else:
            values[f.name] = f.default
    return Record(spec=spec, id=rec_id, rel_path=rel_path, text=text, values=values, body=doc.body.strip())


def _frontmatter_value(f: Field, value: Any) -> Any:
    """What to write for a field, or None to leave it out."""
    if f.kind == "bool":
        return True if value else None
    if f.kind in ("list", "person_list"):
        return list(value) if value else None
    if f.kind == "int":
        return value
    return value if not _empty(value) else None


def render_new(spec: Spec, values: dict[str, Any], body: str) -> str:
    data = {}
    for f in spec.fields:
        written = _frontmatter_value(f, values.get(f.name))
        if written is not None:
            data[f.name] = written
    return render_document(data, body)


def render_changed(original: str, spec: Spec, old: dict[str, Any], new: dict[str, Any], body: str) -> str:
    """The original file with only the changed keys and body replaced. Comments and unknown keys are kept."""
    changes: dict[str, Any] = {}
    for f in spec.fields:
        old_written = _frontmatter_value(f, old.get(f.name))
        new_written = _frontmatter_value(f, new.get(f.name))
        if old_written != new_written:
            changes[f.name] = new_written
    text = set_frontmatter_values(original, changes)
    if spec.body_label and body != parse_document(original).body.strip():
        text = set_body(text, body)
    return text


def new_id(spec: Spec, title: str, taken: set[str]) -> str:
    base = slugify(title) or spec.singular.replace(" ", "-")
    candidate, number = base, 2
    while candidate in taken:
        candidate = f"{base}-{number}"
        number += 1
    return candidate


def describe_field(f: Field, value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None or value == "" or value == []:
        return "(empty)"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dt.date):
        return value.isoformat()
    if f.kind == "choice":
        return dict(f.choices).get(str(value), str(value))
    return str(value)


def plain_changes(
    spec: Spec, old: dict[str, Any] | None, new: dict[str, Any], body_old: str, body_new: str
) -> list[str]:
    """Each change as one plain sentence, for the preview."""
    sentences: list[str] = []
    title_field = spec.field(spec.title_field)
    if old is None:
        sentences.append(
            f"A new {spec.singular} will be added: {describe_field(title_field, new.get(spec.title_field))}."
        )
    for f in spec.fields:
        before = (old or {}).get(f.name)
        after = new.get(f.name)
        if old is not None and _frontmatter_value(f, before) == _frontmatter_value(f, after):
            continue
        if old is None and _frontmatter_value(f, after) is None:
            continue
        if old is None and f.kind == "int" and after == f.default:
            continue  # a new entry gets the default order without the operator noticing it
        if old is not None and _empty(after):
            sentences.append(f'{f.label} will be cleared (was "{describe_field(f, before)}").')
        elif old is not None and _empty(before):
            sentences.append(f'{f.label} set to "{describe_field(f, after)}".')
        elif old is None:
            sentences.append(f"{f.label}: {describe_field(f, after)}.")
        else:
            sentences.append(f'{f.label} changed from "{describe_field(f, before)}" to "{describe_field(f, after)}".')
    if spec.body_label and body_old.strip() != body_new.strip():
        verb = "added" if not body_old.strip() else "changed"
        sentences.append(f"{spec.body_label} {verb} ({len(body_new.split())} words).")
    return sentences


def validate_file_text(spec: Spec, text: str) -> list[str]:
    """Problems that would make a content file invalid for the site. Empty list means valid."""
    try:
        doc = parse_document(text)
    except ValueError as exc:
        return [str(exc)]
    problems: list[str] = []
    for f in spec.fields:
        raw = doc.data.get(f.name)
        if f.required and _empty(raw) and f.kind not in ("list", "person_list"):
            problems.append(f"{f.label} is required.")
        if f.kind == "choice" and raw is not None and raw not in {stored for stored, _ in f.choices}:
            problems.append(f'{f.label}: "{raw}" is not one of the listed options.')
        if f.kind == "date" and raw is not None and not isinstance(raw, dt.date):
            problems.append(f"{f.label} must be a date such as 2026-11-05.")
        if f.kind == "int" and raw is not None and not isinstance(raw, int):
            problems.append(f"{f.label} must be a whole number.")
    if spec.key == "events":
        first, last = doc.data.get("date"), doc.data.get("endDate")
        if isinstance(first, dt.date) and isinstance(last, dt.date) and last < first:
            problems.append("The last day cannot be before the first day.")
    return problems
