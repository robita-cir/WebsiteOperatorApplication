"""Loads the instructions sent to the model. They live in prompts/*.md so they can be tuned without changing code."""

from __future__ import annotations

from importlib.resources import files


def load_prompt(name: str, **values: str) -> str:
    """Reads prompts/<name>.md and fills each {{key}} placeholder with its value."""
    text = (files("site_agent") / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text
