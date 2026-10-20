"""Writes an approved plan to disk. Replaced or removed files are backed up first, so the run can be undone."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NoReturn

from site_agent.config import STATE_DIR
from site_agent.errors import SiteAgentError
from site_agent.plan import Plan
from site_agent.site import Site


@dataclass(frozen=True)
class ApplyResult:
    run_id: str
    written: list[str]
    removed: list[str]
    backup_dir: Path


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    output: str


def state_dir(site: Site) -> Path:
    return site.root / STATE_DIR


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _new_run_id(state: Path) -> str:
    base = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id, number = base, 2
    while (state / "runs" / f"{run_id}.json").exists():
        run_id = f"{base}-{number}"
        number += 1
    return run_id


def _put_back(
    site: Site, backup_dir: Path, created: list[str], modified: list[str], removed: list[str], cause: Exception
) -> NoReturn:
    """Puts every file back as it was before a write failed part way, then reports that nothing was written."""
    try:
        for rel in created:
            if site.exists(rel):
                site.resolve(rel).unlink()
        for rel in modified + removed:
            shutil.copy2(backup_dir / rel, site.resolve(rel))
    except OSError as restore_error:
        raise SiteAgentError(
            f"Writing stopped part way ({cause}), and the files could not all be put back ({restore_error}). "
            f"The originals are in {backup_dir}."
        ) from cause
    raise SiteAgentError(
        f"Writing stopped part way ({cause}), so every change was undone. Nothing was written."
    ) from cause


def apply_plan(site: Site, plan: Plan, *, command: str, model: str, approval_id: str | None = None) -> ApplyResult:
    """Writes every change in the plan, or none of them.

    A write that fails part way is undone before the error is raised, so the site is never left half changed with no
    record of it.
    """
    state = state_dir(site)
    run_id = _new_run_id(state)
    backup_dir = state / "backups" / run_id
    created: list[str] = []
    modified: list[str] = []
    removed: list[str] = []

    for change in plan.changes:
        if not site.is_writable(change.rel_path):
            raise SiteAgentError(f"{change.rel_path} is not in the paths the agent may change. Nothing was written.")
        if change.is_new:
            if site.exists(change.rel_path):
                raise SiteAgentError(f"{change.rel_path} was created after the plan was made. Nothing was written.")
            created.append(change.rel_path)
            continue
        if not site.exists(change.rel_path) or site.read(change.rel_path) != change.before:
            raise SiteAgentError(f"{change.rel_path} changed after the plan was made. Nothing was written.")
        (removed if change.is_removal else modified).append(change.rel_path)

    after_hashes: dict[str, str] = {}
    try:
        for rel in modified + removed:  # byte-exact copies, so a restore gives back exactly what was there
            backup = backup_dir / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(site.resolve(rel), backup)

        for change in plan.changes:
            if change.is_removal:
                site.resolve(change.rel_path).unlink()
            else:
                site.write(change.rel_path, change.after or "")
                after_hashes[change.rel_path] = sha256_text(change.after or "")
    except Exception as exc:
        _put_back(site, backup_dir, created, modified, removed, exc)

    log = {
        "run_id": run_id,
        "time": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "model": model,
        "approval_id": approval_id,
        "created": created,
        "modified": modified,
        "removed": removed,
        "after_hashes": after_hashes,
        "undone": False,
    }
    runs = state / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{run_id}.json").write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return ApplyResult(run_id=run_id, written=created + modified, removed=removed, backup_dir=backup_dir)


def read_run(site: Site, run_id: str) -> dict:
    log_path = state_dir(site) / "runs" / f"{run_id}.json"
    if not log_path.exists():
        raise SiteAgentError(f"no run called '{run_id}'. The run ids are the file names in {STATE_DIR}/runs/.")
    return json.loads(log_path.read_text(encoding="utf-8"))


def restore_run(site: Site, run_id: str) -> list[tuple[str, str]]:
    """Undoes one run: restores replaced and removed files from their backups and removes files the run created.

    Returns (action, path) pairs, where action is 'restored', 'removed' or 'recreated'.
    """
    state = state_dir(site)
    log = read_run(site, run_id)
    if log.get("undone"):
        raise SiteAgentError(f"run {run_id} has already been undone.")
    backup_dir = state / "backups" / run_id
    actions: list[tuple[str, str]] = []
    for rel in log["modified"] + log["removed"]:
        source = backup_dir / rel
        if not source.exists():
            raise SiteAgentError(f"the backup for {rel} is missing from {backup_dir}. Restore it by hand.")
        site.resolve(rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, site.resolve(rel))
        actions.append(("recreated" if rel in log["removed"] else "restored", rel))
    for rel in log["created"]:
        path = site.resolve(rel)
        if path.exists():
            path.unlink()
        actions.append(("removed", rel))
    log["undone"] = True
    (state / "runs" / f"{run_id}.json").write_text(
        json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return actions


def run_check(command: str, cwd: Path, timeout_s: float = 900) -> CheckResult:
    """Runs the operator's check command, for example 'npm run check'. The command comes from site-agent.toml only,
    never from model output."""
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(ok=False, output=f"the check did not finish within {timeout_s:.0f} seconds")
    output = (proc.stdout + proc.stderr).strip()
    return CheckResult(ok=proc.returncode == 0, output=output[-4000:])
