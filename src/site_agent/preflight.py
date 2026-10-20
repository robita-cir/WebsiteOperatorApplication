"""Runs the site check on a throwaway copy with the pending changes applied, before anything is written for real."""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from site_agent.apply import run_check
from site_agent.config import STATE_DIR
from site_agent.plan import Plan
from site_agent.site import Site

# Left out of the copy: the agent's own state (the copy lives inside it), version history and build output. The
# installed packages are linked in instead, because copying them would take minutes.
_NOT_COPIED = frozenset({STATE_DIR, ".git", "dist", ".astro", "node_modules"})
SKIPPED_REASON = "The check could not run on a copy, so it runs after writing."


@dataclass(frozen=True)
class PreflightResult:
    status: str  # "passed", "failed" or "skipped"
    output: str = ""
    reason: str = ""


def _ignore_top_level(root: Path) -> Callable[[str, list[str]], set[str]]:
    def ignore(directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in _NOT_COPIED} if Path(directory) == root else set()

    return ignore


def _apply_to_copy(site: Site, plan: Plan, copy: Path) -> None:
    for change in plan.changes:
        if not site.is_writable(change.rel_path):
            continue
        target = copy.joinpath(*site.resolve(change.rel_path).relative_to(site.root).parts)
        if change.after is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(change.after, encoding="utf-8", newline="\n")


def run_preflight(site: Site, plan: Plan, check_command: str, state_dir: Path) -> PreflightResult:
    """Applies the plan to a copy of the site and runs the check there. The real site is never written."""
    copy = state_dir / "preflight" / uuid.uuid4().hex[:12]
    try:
        # symlinks=True keeps links as links, so a link in the site cannot pull in files from outside it.
        shutil.copytree(site.root, copy, symlinks=True, ignore=_ignore_top_level(site.root))
        modules = site.root / "node_modules"
        if modules.exists():
            try:
                os.symlink(modules, copy / "node_modules", target_is_directory=True)
            except OSError:
                return PreflightResult("skipped", reason=SKIPPED_REASON)
        _apply_to_copy(site, plan, copy)
        result = run_check(check_command, cwd=copy)
        return PreflightResult("passed" if result.ok else "failed", output=result.output)
    except OSError:
        return PreflightResult("skipped", reason=SKIPPED_REASON)
    finally:
        # rmtree removes a symbolic link without following it, so node_modules in the real site is untouched.
        shutil.rmtree(copy, ignore_errors=True)
