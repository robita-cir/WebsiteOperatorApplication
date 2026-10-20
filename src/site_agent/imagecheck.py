"""Reads just enough of an image or a PDF to tell whether it is what it claims to be. No image library is needed."""

from __future__ import annotations

import struct
from pathlib import Path

MAX_FILE_BYTES = 20 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PDF_SIGNATURE = b"%PDF-"


def is_png(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(len(PNG_SIGNATURE)) == PNG_SIGNATURE
    except OSError:
        return False


def png_size(path: Path) -> tuple[int, int] | None:
    """(width, height) from the IHDR chunk, which a PNG must have first. None when the file is not a readable PNG."""
    try:
        with path.open("rb") as handle:
            head = handle.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != PNG_SIGNATURE or head[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(len(PDF_SIGNATURE)) == PDF_SIGNATURE
    except OSError:
        return False


def file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None
