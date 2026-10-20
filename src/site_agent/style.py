"""Spelling advice for new text. The centre writes British English; common American spellings are pointed out.

This is advice only. It never changes the text and never blocks a save, because a name, a quotation or a software term
may need the American form, and only the person can tell.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CHECK = "Check it."


@dataclass(frozen=True)
class Rule:
    american: str
    british: str
    note: str = CHECK  # said after the suggestion, for words that need a judgement
    # Words that must come just before the word for it to count (for a noun-only rule). Empty means always.
    after: frozenset[str] = frozenset()
    # Words just before the word that show the other sense is meant, so the word is left alone.
    not_after: frozenset[str] = frozenset()


def _family(american: str, british: str, endings: tuple[str, ...]) -> list[Rule]:
    return [Rule(american + end, british + end) for end in endings]


_VERB = ("e", "es", "ed", "ing")
_VERB_ER = (*_VERB, "er", "ers")
_VERB_ATION = (*_VERB, "ation", "ations")
_DOUBLED = ("ed", "ing")

# Verbs that end in -ize here and -ise in British usage, with their noun forms.
_IZE = ("organiz", "recogniz", "realiz", "emphasiz", "summariz", "prioritiz", "minimiz", "maximiz", "customiz")
_IZE_ATION = ("organiz", "specializ", "initializ", "categoriz", "utiliz", "synchroniz", "visualiz")

# -ll- is doubled in British usage: 'modeling' is 'modelling'. The stem is the last letter before the ending.
_DOUBLE_L = ("model", "label", "travel", "cancel", "signal", "fuel", "level", "marvel")

RULES: tuple[Rule, ...] = (
    *[r for stem in _IZE for r in _family(stem, stem[:-1] + "s", _VERB_ER)],
    *[r for stem in _IZE_ATION for r in _family(stem, stem[:-1] + "s", _VERB_ATION)],
    *_family("analyz", "analys", _VERB_ER),
    *_family("paralyz", "paralys", _VERB),
    # -or / -our
    *_family("color", "colour", ("", "s", "ed", "ing", "ful")),
    *_family("behavior", "behaviour", ("", "s", "al")),
    *_family("favor", "favour", ("", "s", "ed", "ing", "able")),
    *_family("favorite", "favourite", ("", "s")),
    *_family("honor", "honour", ("", "s", "ed", "ing")),
    *_family("labor", "labour", ("", "s", "ed")),
    *_family("neighbor", "neighbour", ("", "s", "ing")),
    *_family("humor", "humour", ("", "s")),
    *_family("flavor", "flavour", ("", "s")),
    # -er / -re
    *_family("center", "centre", ("", "s", "ed")),
    Rule("centering", "centring"),
    *_family("theater", "theatre", ("", "s")),
    *_family("fiber", "fibre", ("", "s")),
    *_family("liter", "litre", ("", "s")),
    *_family("caliber", "calibre", ("", "s")),
    *_family("maneuver", "manoeuvre", ("", "s")),
    Rule("maneuvered", "manoeuvred"),
    Rule("maneuvering", "manoeuvring"),
    # -og
    *_family("catalog", "catalogue", ("", "s", "ed")),
    # -se / -ce
    *_family("defense", "defence", ("", "s")),
    *_family("offense", "offence", ("", "s")),
    # single l before -ed or -ing is doubled in British usage
    *[Rule(stem + end, stem + "l" + end) for stem in _DOUBLE_L for end in _DOUBLED],
    # other common spellings
    Rule("gray", "grey"),
    Rule("fulfill", "fulfil"),
    Rule("enrollment", "enrolment"),
    Rule("skillful", "skilful"),
    Rule("aluminum", "aluminium"),
    Rule("sulfur", "sulphur"),
    Rule("skeptic", "sceptic"),
    Rule("skeptical", "sceptical"),
    Rule("jewelry", "jewellery"),
    Rule("pediatric", "paediatric"),
    Rule("anesthesia", "anaesthesia"),
    Rule("esthetic", "aesthetic"),
    Rule("plow", "plough"),
    # The same spelling is right in one sense and wrong in the other, so the advice says which.
    Rule(
        "program",
        "programme",
        note=(
            "Write 'programme' when it means a schedule of events or a funded scheme. "
            "Keep 'program' only for computer software. Check it."
        ),
        not_after=frozenset({"computer", "software", "robot", "control", "python", "test", "training", "source", "c"}),
    ),
    Rule(
        "programs",
        "programmes",
        note=(
            "Write 'programmes' when it means schedules of events or funded schemes. "
            "Keep 'programs' only for computer software. Check it."
        ),
        not_after=frozenset({"computer", "software", "robot", "control", "python", "test", "training", "source", "c"}),
    ),
    Rule(
        "license",
        "licence",
        note="The noun (the document or permission) is 'licence'. The verb stays 'license'. Check it.",
        after=frozenset(
            {
                "a",
                "an",
                "the",
                "this",
                "that",
                "our",
                "your",
                "its",
                "their",
                "my",
                "open",
                "source",
                "software",
                "valid",
                "driving",
                "new",
            }
        ),
    ),
    Rule(
        "licenses",
        "licences",
        note="The noun (the documents or permissions) is 'licences'. The verb stays 'licenses'. Check it.",
        after=frozenset({"the", "these", "those", "our", "your", "their", "open", "valid", "new", "two", "three"}),
    ),
)

_BY_WORD: dict[str, list[Rule]] = {}
for _rule in RULES:
    _BY_WORD.setdefault(_rule.american, []).append(_rule)

_WORD = re.compile(r"\b(" + "|".join(sorted(_BY_WORD, key=len, reverse=True)) + r")\b", re.IGNORECASE)
_PREVIOUS_WORD = re.compile(r"([A-Za-z]+)\W*$")

# Text that is not prose: code, addresses and file names keep their own spelling.
_FENCED_CODE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
_CODE_SPAN = re.compile(r"`[^`\n]*`")
_ADDRESS = re.compile(r"(?:https?://|www\.)\S+|\S+@\S+\.\S+", re.IGNORECASE)
_PATH = re.compile(r"\S*/\S*")


def _prose_only(text: str) -> str:
    """The text with code, addresses and paths blanked out, so that the positions of the other words stay the same."""
    for pattern in (_FENCED_CODE, _CODE_SPAN, _ADDRESS, _PATH):
        text = pattern.sub(lambda match: " " * len(match.group(0)), text)
    return text


def _applies(rule: Rule, before: str) -> bool:
    previous = _PREVIOUS_WORD.search(before)
    word = previous.group(1).lower() if previous else ""
    if rule.after and word not in rule.after:
        return False
    return not (rule.not_after and word in rule.not_after)


def spelling_advice(text: str) -> list[str]:
    """One plain sentence for each American spelling found, in the order the words first appear."""
    prose = _prose_only(text)
    sentences: dict[str, str] = {}
    for match in _WORD.finditer(prose):
        word = match.group(1).lower()
        if word in sentences:
            continue
        for rule in _BY_WORD[word]:
            if _applies(rule, prose[: match.start()]):
                sentences[word] = f"'{word}' is usually written '{rule.british}' in British English. {rule.note}"
                break
    return list(sentences.values())


__all__ = ["spelling_advice", "RULES", "Rule"]
