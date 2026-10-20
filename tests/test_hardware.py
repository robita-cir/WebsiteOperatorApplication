import pytest

from site_agent import hardware
from site_agent.hardware import choose_model, total_memory_gb


@pytest.mark.parametrize(
    ("gb", "model"),
    [
        (4, "llama3.2:3b"),
        (8, "llama3.2:3b"),
        (11.9, "llama3.2:3b"),
        (12, "qwen2.5:7b"),
        (16, "qwen2.5:7b"),
        (64, "qwen2.5:7b"),
    ],
)
def test_each_memory_size_maps_to_the_right_model(gb, model):
    assert choose_model(gb)[0] == model


def test_reasons_name_the_memory():
    assert choose_model(16) == ("qwen2.5:7b", "chosen for 16 GB of memory")
    assert choose_model(8) == ("llama3.2:3b", "chosen for 8 GB of memory; the larger model needs more")


def test_unknown_memory_gives_the_default_with_its_reason():
    assert choose_model(None) == ("qwen2.5:7b", "memory could not be read; using the default model")


def test_meminfo_kb_is_converted_to_gb(monkeypatch):
    monkeypatch.setattr(hardware.sys, "platform", "linux")
    monkeypatch.setattr(
        hardware, "_read_meminfo", lambda: "MemFree: 1 kB\nMemTotal:       16777216 kB\nMemAvailable: 5 kB\n"
    )
    assert total_memory_gb() == pytest.approx(16.0)


def test_meminfo_without_a_total_is_unknown(monkeypatch):
    monkeypatch.setattr(hardware.sys, "platform", "linux")
    monkeypatch.setattr(hardware, "_read_meminfo", lambda: "MemFree: 1 kB\n")
    assert total_memory_gb() is None


def _fail(*_args):
    raise OSError("not available")


def test_a_failed_linux_read_gives_none(monkeypatch):
    monkeypatch.setattr(hardware.sys, "platform", "linux")
    monkeypatch.setattr(hardware, "_read_meminfo", _fail)
    assert total_memory_gb() is None


def test_a_failed_windows_read_gives_none(monkeypatch):
    monkeypatch.setattr(hardware.sys, "platform", "win32")
    monkeypatch.setattr(hardware, "_windows_memory_bytes", _fail)
    assert total_memory_gb() is None


def test_a_failed_sysconf_read_gives_none(monkeypatch):
    monkeypatch.setattr(hardware.sys, "platform", "darwin")
    monkeypatch.setattr(hardware, "_sysconf_memory_bytes", _fail)
    assert total_memory_gb() is None


def test_sysconf_memory_is_converted_to_gb(monkeypatch):
    monkeypatch.setattr(hardware.sys, "platform", "darwin")
    monkeypatch.setattr(hardware, "_sysconf_memory_bytes", lambda: 8 * 1024**3)
    assert total_memory_gb() == pytest.approx(8.0)
