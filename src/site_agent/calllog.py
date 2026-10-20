"""An append-only record of model calls: timing, size and a prompt fingerprint, never the text itself.

The log exists so slow or failing calls can be diagnosed and prompt versions compared. Operator content (names,
facts, drafts) must not end up in a file that may be shared in a bug report, so messages are only hashed and counted.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

LOG_NAME = "calls.jsonl"
_ERROR_CHARS = 200


def prompt_fingerprint(messages: list[Any]) -> tuple[str, int]:
    """Returns (sha256 hex, character count) over the roles and contents. JSON framing keeps the hash unambiguous."""
    pairs = [[m.role, m.content] for m in messages]
    digest = hashlib.sha256(json.dumps(pairs, ensure_ascii=False).encode("utf-8")).hexdigest()
    return digest, sum(len(m.content) for m in messages)


def log_call(
    log_dir: Path | str | None,
    *,
    provider: str,
    model: str,
    messages: list[Any],
    json_mode: bool,
    schema_used: bool,
    seconds: float,
    output_tokens: int | None,
    ok: bool,
    error: str | None = None,
) -> None:
    """Appends one JSON line to <log_dir>/calls.jsonl. Does nothing without a folder, and never raises."""
    if log_dir is None:
        return
    try:
        digest, chars = prompt_fingerprint(messages)
        entry = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "provider": provider,
            "model": model,
            "json_mode": json_mode,
            "schema_used": schema_used,
            "seconds": round(seconds, 3),
            "output_tokens": output_tokens if isinstance(output_tokens, int) else None,
            "prompt_sha256": digest,
            "prompt_chars": chars,
            "ok": ok,
            "error": error[:_ERROR_CHARS] if error else None,
        }
        folder = Path(log_dir)
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / LOG_NAME).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except (OSError, ValueError, TypeError, AttributeError):
        # A diagnostic file must never turn a good model answer into a failure.
        return
