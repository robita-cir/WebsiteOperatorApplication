import pytest

from site_agent.config import DEFAULT_WRITABLE, load_settings
from site_agent.errors import SiteAgentError


def test_defaults_are_used_when_there_is_no_config_file(tmp_path):
    settings = load_settings(tmp_path)
    assert settings.llm.provider == "ollama"
    assert settings.site.writable == DEFAULT_WRITABLE
    assert settings.site.check_command is None


def test_values_from_site_agent_toml_are_read(tmp_path):
    (tmp_path / "site-agent.toml").write_text(
        '[llm]\nmodel = "llama3.2:3b"\ntimeout_s = 90\n\n'
        '[site]\nwritable = ["src/**/*.md"]\ncheck_command = "npm run check"\n',
        encoding="utf-8",
    )
    settings = load_settings(tmp_path)
    assert settings.llm.model == "llama3.2:3b" and settings.llm.timeout_s == 90
    assert settings.site.writable == ("src/**/*.md",)
    assert settings.site.check_command == "npm run check"


def test_command_line_model_overrides_the_file(tmp_path):
    (tmp_path / "site-agent.toml").write_text('[llm]\nmodel = "a"\n', encoding="utf-8")
    assert load_settings(tmp_path, model="b").llm.model == "b"


def test_unknown_keys_are_an_error(tmp_path):
    (tmp_path / "site-agent.toml").write_text('[site]\nroot = "/elsewhere"\n', encoding="utf-8")
    with pytest.raises(SiteAgentError, match="unknown setting"):
        load_settings(tmp_path)


def test_a_missing_site_folder_is_an_error(tmp_path):
    with pytest.raises(SiteAgentError, match="Site folder not found"):
        load_settings(tmp_path / "nope")


def _memory(monkeypatch, gb):
    monkeypatch.setattr("site_agent.config.total_memory_gb", lambda: gb)


def test_auto_model_is_chosen_from_memory(tmp_path, monkeypatch):
    _memory(monkeypatch, 8)
    llm = load_settings(tmp_path).llm
    assert llm.model == "llama3.2:3b"
    assert llm.model_reason == "chosen for 8 GB of memory; the larger model needs more"
    _memory(monkeypatch, 16)
    assert load_settings(tmp_path).llm.model == "qwen2.5:7b"


def test_auto_model_with_unreadable_memory_uses_the_default(tmp_path, monkeypatch):
    _memory(monkeypatch, None)
    llm = load_settings(tmp_path).llm
    assert llm.model == "qwen2.5:7b" and "could not be read" in llm.model_reason


def test_explicit_model_in_the_file_wins_over_auto(tmp_path, monkeypatch):
    _memory(monkeypatch, 8)
    (tmp_path / "site-agent.toml").write_text('[llm]\nmodel = "qwen2.5:7b"\n', encoding="utf-8")
    llm = load_settings(tmp_path).llm
    assert llm.model == "qwen2.5:7b" and llm.model_reason == "set in site-agent.toml"


def test_command_line_model_wins_over_file_and_auto(tmp_path, monkeypatch):
    _memory(monkeypatch, 8)
    assert load_settings(tmp_path, model="b").llm.model_reason == "set on the command line"
    (tmp_path / "site-agent.toml").write_text('[llm]\nmodel = "a"\n', encoding="utf-8")
    llm = load_settings(tmp_path, model="b").llm
    assert llm.model == "b" and llm.model_reason == "set on the command line"


def test_the_reason_cannot_be_set_from_the_file(tmp_path):
    (tmp_path / "site-agent.toml").write_text('[llm]\nmodel_reason = "x"\n', encoding="utf-8")
    with pytest.raises(SiteAgentError, match="model_reason"):
        load_settings(tmp_path)
