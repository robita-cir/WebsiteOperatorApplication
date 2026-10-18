"""What happened, and what can be undone.

Undo is strict on purpose. A run can be undone only when no later run touched the same files, and when each file still
holds exactly what the run wrote. Otherwise undo would silently throw away newer work, so the app says why instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from site_agent.apply import read_run, restore_run, sha256_text, state_dir
from site_agent.errors import SiteAgentError
from site_agent.site import Site


@dataclass
class RunView:
    run_id: str
    time: str
    command: str
    model: str
    approval_id: str | None
    files: list[str]
    undone: bool
    can_undo: bool
    reason: str = ""
    labels: list[str] = field(default_factory=list)


def _files_of(log: dict) -> list[str]:
    return list(log.get("created", [])) + list(log.get("modified", [])) + list(log.get("removed", []))


def _sorted_runs(site: Site) -> list[dict]:
    runs_dir = state_dir(site) / "runs"
    if not runs_dir.is_dir():
        return []
    logs = [read_run(site, path.stem) for path in runs_dir.glob("*.json")]
    return sorted(logs, key=lambda log: (log["time"], log["run_id"]))


def _current_matches(site: Site, log: dict) -> str:
    """Empty string when every file still holds what this run left there. Otherwise, the first file that changed."""
    hashes = log.get("after_hashes", {})
    for rel in log.get("created", []) + log.get("modified", []):
        if not site.exists(rel) or sha256_text(site.read(rel)) != hashes.get(rel):
            return rel
    for rel in log.get("removed", []):
        if site.exists(rel):
            return rel
    return ""


def undo_status(site: Site, run_id: str) -> tuple[bool, str]:
    """(can undo, reason if not)."""
    runs = _sorted_runs(site)
    target = next((log for log in runs if log["run_id"] == run_id), None)
    if target is None:
        raise SiteAgentError(f"no run called '{run_id}'")
    if target.get("undone"):
        return False, "This change has already been undone."
    later = runs[runs.index(target) + 1 :]
    touched = set(_files_of(target))
    for log in later:
        if not log.get("undone") and touched & set(_files_of(log)):
            return False, f"A later change ({log['run_id']}) touched the same file. Undo that first."
    changed = _current_matches(site, target)
    if changed:
        return False, f"{changed} has been edited since this change. Undoing it would overwrite that work."
    return True, ""


def list_runs(site: Site) -> list[RunView]:
    views = []
    for log in reversed(_sorted_runs(site)):
        can, reason = undo_status(site, log["run_id"]) if not log.get("undone") else (False, "Already undone.")
        views.append(
            RunView(
                run_id=log["run_id"],
                time=log["time"],
                command=log["command"],
                model=log.get("model", ""),
                approval_id=log.get("approval_id"),
                files=_files_of(log),
                undone=bool(log.get("undone")),
                can_undo=can,
                reason=reason,
            )
        )
    return views


def undo(site: Site, run_id: str) -> list[tuple[str, str]]:
    can, reason = undo_status(site, run_id)
    if not can:
        raise SiteAgentError(reason)
    return restore_run(site, run_id)
