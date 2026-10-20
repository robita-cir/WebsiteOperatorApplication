"""The state folder reaches the model client, so each model call is logged in the site's own folder."""

from helpers import FakeLLM

import site_agent.cli as cli
from site_agent.apply import state_dir
from site_agent.config import SiteSettings, load_settings
from site_agent.site import Site


def test_the_command_line_passes_the_state_folder_to_the_model_client(site_dir, monkeypatch):
    seen = {}

    def fake_make_client(llm_settings, log_dir=None):
        seen["log_dir"] = log_dir
        return FakeLLM()

    monkeypatch.setattr(cli, "make_client", fake_make_client)
    settings = load_settings(site_dir)
    site = Site(SiteSettings(root=site_dir))
    cli._llm(settings, None, site)
    assert seen["log_dir"] == state_dir(site)
