"""A fixed set of realistic notices with the record each one should give, and a runner that scores a model on them.

The default run checks the runner and the case files offline, with a scripted model. The real model is run by
tests/test_live.py, which calls run_regression(). See tests/regression/README.txt for the case set.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from conftest import FIXTURE
from helpers import FakeLLM

from site_agent.config import SiteSettings
from site_agent.errors import SiteAgentError
from site_agent.frontmatter import parse_document
from site_agent.llm.base import ChatClient
from site_agent.site import Site
from site_agent.text_utils import normalise
from site_agent.workflows import plan_add_event

CASE_DIR = Path(__file__).parent / "regression"

# The fields a record is scored on. A case that must be rejected is scored on one field, "rejected".
SCORED_FIELDS = ("title", "kind", "date", "endDate", "venue", "series")
REJECTED = "rejected"
TEXT_FIELDS = ("title", "venue", "series")  # compared ignoring case and spacing; the others must match exactly


@dataclass(frozen=True)
class Case:
    name: str
    notice: str
    expected: dict[str, Any]

    @property
    def today(self) -> dt.date:
        return dt.date.fromisoformat(self.expected["today"])

    @property
    def must_be_rejected(self) -> bool:
        return "error" in self.expected


def load_cases(directory: Path = CASE_DIR) -> list[Case]:
    cases = []
    for notice in sorted((directory / "notices").glob("*.txt")):
        expected = json.loads((directory / "expected" / f"{notice.stem}.json").read_text(encoding="utf-8"))
        cases.append(Case(notice.stem, notice.read_text(encoding="utf-8"), expected))
    return cases


@dataclass
class CaseResult:
    name: str
    right: list[str] = field(default_factory=list)
    wrong: dict[str, tuple[Any, Any]] = field(default_factory=dict)  # field -> (expected, got)
    error: str | None = None  # why plan_add_event raised, when it did
    seconds: float = 0.0
    noted: int = 0  # warnings the plan carries for the operator (values not found in the notice)

    @property
    def raised(self) -> bool:
        return self.error is not None


@dataclass
class RegressionResult:
    model: str
    cases: list[CaseResult]

    @property
    def fields_right(self) -> int:
        return sum(len(c.right) for c in self.cases)

    @property
    def fields_wrong(self) -> int:
        return sum(len(c.wrong) for c in self.cases)

    @property
    def errors(self) -> int:
        """Cases that raised an error although a record was expected."""
        return sum(1 for c in self.cases if c.raised and REJECTED not in c.right)

    @property
    def noted(self) -> int:
        return sum(c.noted for c in self.cases)

    @property
    def seconds(self) -> float:
        return sum(c.seconds for c in self.cases)

    @property
    def accuracy(self) -> float:
        total = self.fields_right + self.fields_wrong
        return self.fields_right / total if total else 0.0

    def by_field(self) -> dict[str, tuple[int, int]]:
        """Field name -> (right, scored), over all cases."""
        counts: dict[str, list[int]] = {}
        for case in self.cases:
            for name in case.right:
                counts.setdefault(name, [0, 0])[0] += 1
                counts[name][1] += 1
            for name in case.wrong:
                counts.setdefault(name, [0, 0])[1] += 1
        return {name: (right, total) for name, (right, total) in counts.items()}

    def table(self) -> str:
        width = max(len("case"), *(len(c.name) for c in self.cases))
        lines = [
            f"model: {self.model}",
            f"{'case'.ljust(width)}  right  wrong  noted  seconds  result",
        ]
        for c in self.cases:
            if c.raised and REJECTED not in c.right:
                result = f"ERROR: {c.error}"
            elif c.wrong:
                result = "wrong: " + ", ".join(f"{k} (wanted {e!r}, got {g!r})" for k, (e, g) in c.wrong.items())
            else:
                result = "ok"
            row = f"{c.name.ljust(width)}  {len(c.right):>5}  {len(c.wrong):>5}  {c.noted:>5}  {c.seconds:>7.1f}  "
            lines.append(row + result)
        lines.append(
            f"{'total'.ljust(width)}  {self.fields_right:>5}  {self.fields_wrong:>5}  {self.noted:>5}  "
            f"{self.seconds:>7.1f}  {self.accuracy:.0%} of fields right, {self.errors} case(s) raised an error"
        )
        lines.append(
            "per field: " + ", ".join(f"{name} {right}/{total}" for name, (right, total) in self.by_field().items())
        )
        return "\n".join(lines)


def _same(name: str, expected: Any, got: Any) -> bool:
    if expected is None or got is None:
        return expected is None and got is None
    if name in TEXT_FIELDS:
        return normalise(str(expected)) == normalise(str(got))
    return str(expected) == str(got)


def score_case(case: Case, client: ChatClient, site: Site) -> CaseResult:
    result = CaseResult(case.name)
    started = time.perf_counter()
    try:
        plan = plan_add_event(site, client, case.notice, today=case.today)
    except SiteAgentError as exc:
        result.error = str(exc)
        plan = None
    result.seconds = time.perf_counter() - started

    if case.must_be_rejected:
        if plan is None:
            result.right.append(REJECTED)
        else:
            result.wrong[REJECTED] = ("an error", "a record that would be written")
        return result
    if plan is None:
        # A record was wanted and none came back: every field counts as wrong, so the accuracy is not flattered.
        for name in SCORED_FIELDS:
            result.wrong[name] = (case.expected.get(name), None)
        return result

    record = parse_document(plan.changes[0].after or "").data
    result.noted = len(plan.notes)
    for name in SCORED_FIELDS:
        expected, got = case.expected.get(name), record.get(name)
        if _same(name, expected, got):
            result.right.append(name)
        else:
            result.wrong[name] = (expected, None if got is None else str(got))
    return result


def run_regression(client: ChatClient, model_name: str, cases: list[Case] | None = None) -> RegressionResult:
    """Runs every case through plan_add_event with the case's own fixed today, and scores the record it gives."""
    chosen = load_cases() if cases is None else cases
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch) / "site"
        shutil.copytree(FIXTURE, root)  # plan_add_event only reads the site, but the copy keeps the fixture untouched
        site = Site(SiteSettings(root=root))
        return RegressionResult(model_name, [score_case(case, client, site) for case in chosen])


# ---- offline tests of the runner, with a scripted model ----


def scripted_reply(case: Case, **overrides: Any) -> str:
    """What a perfect model would answer for this case (or a deliberately imperfect one, with overrides)."""
    record: dict[str, Any] = {name: case.expected.get(name) for name in SCORED_FIELDS}
    if case.must_be_rejected:
        record.update(title="Planning Paths for Drone Swarms", kind="talk", date=None)
    record.update(overrides, summary=None, body="")
    # The model is asked for the words it used for the date and venue, and for a relative date phrase.
    record["sources"] = {
        "date": case.expected.get("dateQuote"),
        "endDate": None,
        "venue": case.expected.get("venueQuote"),
        "series": None,
    }
    record["date_phrase"] = case.expected.get("dateQuote") if case.expected.get("dateQuote") == "next Monday" else None
    return json.dumps(record)


def fake_for(
    cases: list[Case],
    overrides: Callable[[Case], dict[str, Any]] = lambda case: {},
    repeat: tuple[str, ...] = (),
) -> FakeLLM:
    replies: list[str] = []
    for case in cases:
        reply = scripted_reply(case, **overrides(case))
        replies.append(reply)
        # A refused record makes the harness ask the model once more. The scripted model repeats its answer, as a
        # real one would, so the next case still gets its own reply.
        if not json.loads(reply).get("date") or case.name in repeat:
            replies.append(reply)
    return FakeLLM(*replies)


def test_there_are_eight_cases_and_each_notice_has_an_expected_file():
    cases = load_cases()
    assert len(cases) == 8
    assert len(list((CASE_DIR / "expected").glob("*.json"))) == 8
    assert sum(c.must_be_rejected for c in cases) == 1


def test_expected_quotes_are_exact_words_of_the_notice():
    for case in load_cases():
        for key in ("dateQuote", "venueQuote"):
            if key in case.expected:
                assert case.expected[key] in case.notice, f"{case.name}: {key} is not in the notice"


def test_the_long_notice_is_about_five_hundred_words_with_the_details_last():
    case = next(c for c in load_cases() if c.name == "long_notice")
    assert 450 <= len(case.notice.split()) <= 600
    last_paragraph = case.notice.strip().split("\n\n")[-1]
    assert case.expected["dateQuote"] in last_paragraph
    assert case.expected["venueQuote"] in last_paragraph


def test_the_relative_date_case_is_computed_from_its_fixed_today():
    case = next(c for c in load_cases() if c.name == "relative_date")
    today = case.today
    days_ahead = (0 - today.weekday()) % 7 or 7  # the next Monday after today
    assert dt.date.fromisoformat(case.expected["date"]) == today + dt.timedelta(days=days_ahead)


def test_a_perfect_scripted_model_scores_every_field_right():
    cases = load_cases()
    result = run_regression(fake_for(cases), "scripted")
    assert result.fields_wrong == 0
    assert result.errors == 0
    assert result.fields_right == 6 * 7 + 1  # six fields in seven cases, and the no-date case rejected
    assert result.by_field()["date"] == (7, 7)
    assert result.by_field()[REJECTED] == (1, 1)
    assert "scripted" in result.table()
    assert "100% of fields right" in result.table()


def test_a_wrong_date_is_reported_as_wrong_and_other_fields_still_count():
    cases = load_cases()
    result = run_regression(fake_for(cases, lambda c: {"date": "2026-01-01"} if c.name == "one_day_talk" else {}), "x")
    talk = next(c for c in result.cases if c.name == "one_day_talk")
    assert set(talk.wrong) == {"date"}
    assert talk.wrong["date"] == ("2026-05-12", "2026-01-01")
    assert len(talk.right) == 5
    assert result.fields_wrong == 1
    assert "one_day_talk" in result.table() and "wanted '2026-05-12', got '2026-01-01'" in result.table()


def test_a_case_that_raises_counts_every_field_wrong_and_is_listed_as_an_error():
    cases = load_cases()
    result = run_regression(
        fake_for(cases, lambda c: {"kind": "party"} if c.name == "list_layout" else {}, repeat=("list_layout",)), "x"
    )
    bad = next(c for c in result.cases if c.name == "list_layout")
    assert bad.raised and len(bad.wrong) == 6
    assert result.errors == 1
    assert "ERROR" in result.table()


def test_a_record_for_the_no_date_notice_is_reported_as_wrong():
    cases = load_cases()
    result = run_regression(fake_for(cases, lambda c: {"date": "2026-06-01"} if c.name == "no_date" else {}), "x")
    case = next(c for c in result.cases if c.name == "no_date")
    assert REJECTED in case.wrong and not case.raised


def test_the_runner_notes_values_that_are_not_in_the_notice_and_times_each_case():
    cases = load_cases()
    result = run_regression(fake_for(cases), "x")
    relative = next(c for c in result.cases if c.name == "relative_date")
    assert relative.noted == 1  # 2026-04-06 is not written in the notice
    assert all(c.seconds >= 0 for c in result.cases)
    assert result.seconds == pytest.approx(sum(c.seconds for c in result.cases))
