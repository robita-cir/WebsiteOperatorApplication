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
