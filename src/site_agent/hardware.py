"""Reads the computer's memory, so the model can be chosen to fit it (see docs/MODELS.md)."""

from __future__ import annotations

import ctypes
import os
import sys

BYTES_PER_GB = 1024**3
LARGE_MODEL = "qwen2.5:7b"
SMALL_MODEL = "llama3.2:3b"
# The 7B model needs about 8 GB for itself; a 16 GB computer runs it, a computer with 8 GB does not. Twelve sits
# between the two sizes, so a nominal 16 GB machine that reports a little less still gets the larger model.
LARGE_MODEL_MIN_GB = 12.0


def _read_meminfo() -> str:
    # A separate function so tests can replace the file read.
    with open("/proc/meminfo", encoding="utf-8") as handle:
        return handle.read()


def _linux_memory_bytes() -> int | None:
    for line in _read_meminfo().splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) * 1024  # the file reports kB
    return None


def _windows_memory_bytes() -> int | None:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
        return None
    return int(status.ullTotalPhys)


def _sysconf_memory_bytes() -> int | None:
    # macOS has no /proc; sysconf reports pages and the page size.
    return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")


def total_memory_gb() -> float | None:
    """Total physical memory in GB, or None when this computer will not say."""
    try:
        if sys.platform.startswith("linux"):
            size = _linux_memory_bytes()
        elif sys.platform == "win32":
            size = _windows_memory_bytes()
        else:
            size = _sysconf_memory_bytes()
    except Exception:  # any failure means "unknown"; the caller falls back to the default model
        return None
    if not size or size <= 0:
        return None
    return size / BYTES_PER_GB


def choose_model(memory_gb: float | None) -> tuple[str, str]:
    """Returns (model, reason) for this much memory."""
    if memory_gb is None:
        return LARGE_MODEL, "memory could not be read; using the default model"
    shown = f"{memory_gb:.0f}"  # a "16 GB" computer reports a little under 16; whole numbers read as the label
    if memory_gb >= LARGE_MODEL_MIN_GB:
        return LARGE_MODEL, f"chosen for {shown} GB of memory"
    return SMALL_MODEL, f"chosen for {shown} GB of memory; the larger model needs more"
