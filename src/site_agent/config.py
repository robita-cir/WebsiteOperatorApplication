"""Settings for a run. They come from `site-agent.toml` in the site root. Every key is optional."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from site_agent.errors import SiteAgentError
from site_agent.hardware import choose_model, total_memory_gb

CONFIG_FILE = "site-agent.toml"
STATE_DIR = ".site-agent"  # backups and run logs, kept inside the site folder

# Files the agent may change, as glob patterns relative to the site root. Content only: the design rule is that
# the operator tool never changes code, so code file types are refused even when a config lists them (see site.py).
DEFAULT_WRITABLE = ("src/content/**/*.md",)


@dataclass(frozen=True)
class LLMSettings:
    # "ollama" for a local Ollama server, or "openai" for any OpenAI-compatible server (llama.cpp, LM Studio, vLLM).
    provider: str = "ollama"
    # "auto" picks the model from the computer's memory when settings are loaded (see hardware.py).
    model: str = "auto"
    base_url: str = "http://localhost:11434"
    timeout_s: float = 600.0  # a 7B model on a laptop CPU has taken over 400 seconds for one long draft
    temperature: float = 0.1
    context_tokens: int = 8192  # Ollama only: the context window requested for each call
    max_output_tokens: int = 1200  # cap on one reply, so a model that never stops cannot run to the timeout
    # Why this model was chosen. Filled in by load_settings and never read from the TOML file.
    model_reason: str = ""


@dataclass(frozen=True)
class SiteSettings:
    root: Path
    content_dir: str = "src/content"
    writable: tuple[str, ...] = DEFAULT_WRITABLE
    check_command: str | None = None  # run after a write, for example "npm run check". Set by the operator only.

    @property
    def content_path(self) -> Path:
        return self.root / self.content_dir


@dataclass(frozen=True)
class Settings:
    site: SiteSettings
    llm: LLMSettings


def _section(raw: dict[str, Any], name: str, cls: type, exclude: tuple[str, ...] = ()) -> dict[str, Any]:
    """Returns the keys of one TOML table, refusing names the agent does not know (so typos are caught)."""
    values = dict(raw.get(name, {}))
    allowed = {f.name for f in fields(cls)} - set(exclude)
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise SiteAgentError(f"{CONFIG_FILE}: unknown setting(s) in [{name}]: {', '.join(unknown)}")
    return values


def load_settings(site_root: Path, *, model: str | None = None) -> Settings:
    root = site_root.resolve()
    if not root.is_dir():
        raise SiteAgentError(f"Site folder not found: {root}")

    raw: dict[str, Any] = {}
    config_path = root / CONFIG_FILE
    if config_path.exists():
        try:
            raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise SiteAgentError(f"{CONFIG_FILE}: {exc}") from exc

    site_values = _section(raw, "site", SiteSettings, exclude=("root",))
    if "writable" in site_values:
        site_values["writable"] = tuple(site_values["writable"])
    llm = LLMSettings(**_section(raw, "llm", LLMSettings, exclude=("model_reason",)))
    if model:
        llm = replace(llm, model=model)
        reason = "set on the command line"
    else:
        reason = "set in site-agent.toml"
    if llm.model == "auto":
        chosen, reason = choose_model(total_memory_gb())
        llm = replace(llm, model=chosen)
    llm = replace(llm, model_reason=reason)
    return Settings(site=SiteSettings(root=root, **site_values), llm=llm)
