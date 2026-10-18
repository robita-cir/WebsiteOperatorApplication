"""Small records the app keeps in the site's state folder: settings, previews, approvals, drafts and the last check.

Everything is JSON in `.site-agent/`, so it moves with the site folder and can be read in a text editor.
Writes go to a temporary file first, then replace the old file in one step, so a crash cannot leave half a file.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from site_agent.apply import state_dir
from site_agent.site import Site

DEFAULT_SETTINGS: dict[str, Any] = {"operator_name": "", "approvers": []}


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


class AppState:
    def __init__(self, site: Site) -> None:
        self.root = state_dir(site)

    # --- settings: who operates the app and who may approve ----------------------------------------

    def settings(self) -> dict[str, Any]:
        data = _read_json(self.root / "settings.json", {})
        merged = {**DEFAULT_SETTINGS, **data}
        merged["approvers"] = list(merged.get("approvers") or [])
        return merged

    def save_settings(self, operator_name: str, approvers: list[dict[str, str]]) -> None:
        _write_json(self.root / "settings.json", {"operator_name": operator_name, "approvers": approvers})

    # --- previews: a plan waiting for approval ---------------------------------------------------------

    def save_preview(self, data: dict[str, Any]) -> str:
        preview_id = uuid.uuid4().hex[:12]
        data = {**data, "id": preview_id, "created": datetime.now().isoformat(timespec="seconds")}
        _write_json(self.root / "previews" / f"{preview_id}.json", data)
        return preview_id

    def load_preview(self, preview_id: str) -> dict[str, Any] | None:
        if not preview_id.isalnum():
            return None
        return _read_json(self.root / "previews" / f"{preview_id}.json", None)

    def delete_preview(self, preview_id: str) -> None:
        path = self.root / "previews" / f"{preview_id}.json"
        if path.exists():
            path.unlink()

    # --- drafts: wording the model produced, kept until it is used or thrown away ----------------

    def save_draft(self, data: dict[str, Any]) -> str:
        draft_id = uuid.uuid4().hex[:12]
        _write_json(self.root / "drafts" / f"{draft_id}.json", {**data, "id": draft_id})
        return draft_id

    def load_draft(self, draft_id: str) -> dict[str, Any] | None:
        if not draft_id.isalnum():
            return None
        return _read_json(self.root / "drafts" / f"{draft_id}.json", None)

    # --- approvals: an append-only log -------------------------------------------------------------

    def add_approval(self, record: dict[str, Any]) -> str:
        approval_id = record.get("id") or uuid.uuid4().hex[:10]
        record = {**record, "id": approval_id, "time": datetime.now().isoformat(timespec="seconds")}
        path = self.root / "approvals.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return approval_id

    def approvals(self) -> list[dict[str, Any]]:
        path = self.root / "approvals.jsonl"
        if not path.exists():
            return []
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return list(reversed(records))

    # --- the last site check ---------------------------------------------------------------------------

    def save_check(self, result: dict[str, Any]) -> None:
        _write_json(self.root / "last_check.json", result)

    def last_check(self) -> dict[str, Any] | None:
        return _read_json(self.root / "last_check.json", None)
