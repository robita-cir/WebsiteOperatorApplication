"""Access to the site folder: which files can be read, where a text is mentioned, and which files may be written."""

from __future__ import annotations

import os
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from site_agent.config import STATE_DIR, SiteSettings
from site_agent.errors import SiteAgentError
from site_agent.text_utils import matching_lines

TEXT_SUFFIXES = frozenset(
    {".md", ".mdx", ".astro", ".ts", ".tsx", ".js", ".mjs", ".json", ".html", ".css", ".txt", ".yml", ".yaml", ".toml"}
)
# Code and page files. The operator tool never writes these, whatever the configuration says.
CODE_SUFFIXES = frozenset({".astro", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".css", ".html"})
IGNORED_DIRS = frozenset({"node_modules", "dist", ".git", ".astro", ".venv", "venv", "__pycache__", STATE_DIR})
MAX_FILE_BYTES = 1_000_000


@dataclass(frozen=True)
class Mention:
    rel_path: str
    line_no: int  # 1-based
    line: str


class Site:
    """Every path here is relative to the site root and uses forward slashes, on every operating system."""

    def __init__(self, settings: SiteSettings) -> None:
        self.settings = settings
        self.root = settings.root

    @property
    def content_dir(self) -> str:
        return PurePosixPath(self.settings.content_dir).as_posix().strip("/")

    def resolve(self, rel_path: str) -> Path:
        pure = PurePosixPath(rel_path)
        if pure.is_absolute() or not pure.parts or ".." in pure.parts:
            raise SiteAgentError(f"refusing to use a path outside the site folder: {rel_path}")
        return self.root.joinpath(*pure.parts)

    def exists(self, rel_path: str) -> bool:
        return self.resolve(rel_path).is_file()

    def read(self, rel_path: str) -> str:
        return self.resolve(rel_path).read_text(encoding="utf-8-sig")

    def is_writable(self, rel_path: str) -> bool:
        if any(part in IGNORED_DIRS for part in PurePosixPath(rel_path).parts):
            return False
        if PurePosixPath(rel_path).suffix.lower() in CODE_SUFFIXES:
            return False
        return any(fnmatch(rel_path, pattern) for pattern in self.settings.writable)

    def write(self, rel_path: str, text: str) -> None:
        """Writes a file the agent is allowed to change. Refuses anything else."""
        if not self.is_writable(rel_path):
            raise SiteAgentError(
                f"{rel_path} is not in the paths the agent may change (see 'writable' in site-agent.toml)"
            )
        self.write_file(rel_path, text)

    def write_file(self, rel_path: str, text: str) -> None:
        """Writes without the allow-list check. Used only when restoring a backup."""
        path = self.resolve(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def collections_present(self) -> list[str]:
        if not self.settings.content_path.is_dir():
            return []
        return sorted(p.name for p in self.settings.content_path.iterdir() if p.is_dir())

    def collection_files(self, collection: str) -> list[str]:
        folder = self.settings.content_path / collection
        if not folder.is_dir():
            return []
        return sorted(p.relative_to(self.root).as_posix() for p in folder.rglob("*.md"))

    def iter_text_files(self) -> list[str]:
        found: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
            for name in filenames:
                if Path(name).suffix.lower() not in TEXT_SUFFIXES:
                    continue
                full = Path(dirpath) / name
                try:
                    if full.stat().st_size > MAX_FILE_BYTES:
                        continue
                except OSError:
                    continue
                found.append(full.relative_to(self.root).as_posix())
        return sorted(found)

    def find_mentions(self, needles: list[str], *, exclude: frozenset[str] | set[str] = frozenset()) -> list[Mention]:
        mentions: list[Mention] = []
        for rel in self.iter_text_files():
            if rel in exclude:
                continue
            try:
                text = self.read(rel)
            except (OSError, UnicodeDecodeError):
                continue
            lines = text.split("\n")
            mentions.extend(Mention(rel, index + 1, lines[index].strip()) for index in matching_lines(text, needles))
        return mentions
