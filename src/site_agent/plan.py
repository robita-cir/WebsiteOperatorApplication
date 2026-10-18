"""A proposed set of file changes. The operator sees the whole plan before anything is written."""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileChange:
    rel_path: str
    before: str | None  # None when the file would be created
    after: str | None  # None when the file would be removed (kept in the backup for undo)

    @property
    def is_new(self) -> bool:
        return self.before is None and self.after is not None

    @property
    def is_removal(self) -> bool:
        return self.after is None

    def diff(self) -> str:
        before = (self.before or "").splitlines(keepends=True)
        after = (self.after or "").splitlines(keepends=True)
        old_name = "/dev/null" if self.is_new else f"a/{self.rel_path}"
        new_name = "/dev/null" if self.is_removal else f"b/{self.rel_path}"
        lines = difflib.unified_diff(before, after, fromfile=old_name, tofile=new_name)
        return "".join(lines).rstrip("\n")


def fingerprint(changes: list[FileChange]) -> str:
    """A hash of exactly what the plan would write. An approval is tied to this value, so any later edit voids it."""
    digest = hashlib.sha256()
    for change in sorted(changes, key=lambda c: c.rel_path):
        digest.update(change.rel_path.encode("utf-8") + b"\0")
        digest.update((change.after if change.after is not None else "\0REMOVED").encode("utf-8") + b"\0")
    return digest.hexdigest()


@dataclass
class Plan:
    summary: str
    changes: list[FileChange] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # things the operator should check
    failures: list[str] = field(default_factory=list)  # model edits that could not be placed safely, so not applied

    def render(self) -> str:
        out = [self.summary, ""]
        if not self.changes:
            out.append("No files would change.")
        for change in self.changes:
            out.append(change.diff())
            out.append("")
        if self.notes:
            out.append("Check before applying:")
            out += [f"  - {note}" for note in self.notes]
            out.append("")
        if self.failures:
            out.append("Not applied (the model's edits could not be placed safely):")
            out += [f"  - {failure}" for failure in self.failures]
        return "\n".join(out).rstrip("\n")
