"""Model backends. Add a new one by implementing ChatClient and returning it from make_client."""

from __future__ import annotations

from pathlib import Path

from site_agent.config import LLMSettings
from site_agent.errors import SiteAgentError
from site_agent.llm.base import ChatClient, LLMError, Message
from site_agent.llm.ollama import OllamaClient
from site_agent.llm.openai_compat import OpenAICompatClient


def make_client(settings: LLMSettings, log_dir: Path | str | None = None) -> ChatClient:
    """log_dir, when given, receives calls.jsonl: a record of each call that holds no message text."""
    if settings.provider == "ollama":
        return OllamaClient(settings, log_dir)
    if settings.provider == "openai":
        return OpenAICompatClient(settings, log_dir)
    raise SiteAgentError(f"unknown llm provider '{settings.provider}'. Use 'ollama' or 'openai'.")


__all__ = ["ChatClient", "LLMError", "Message", "make_client"]
