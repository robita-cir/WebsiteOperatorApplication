"""Runs the real model server. Off by default. Enable with:  SITE_AGENT_LIVE=1 pytest -m live

Set SITE_AGENT_MODEL to the model to test (default qwen2.5:7b). Ollama must be running.
"""

import datetime as dt
import os

import pytest

from site_agent.config import LLMSettings, SiteSettings
from site_agent.llm import make_client
from site_agent.site import Site
from site_agent.workflows import plan_add_event

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("SITE_AGENT_LIVE") != "1", reason="set SITE_AGENT_LIVE=1 to run"),
]


def test_real_model_extracts_a_valid_event(site_dir):
    model = os.environ.get("SITE_AGENT_MODEL", "qwen2.5:7b")
    client = make_client(LLMSettings(model=model, timeout_s=600))
    notice = (
        "Our annual open day is on Saturday 14 March 2026 at the Robotics Lab, Block C, Example City. "
        "Visitors can see the arm demos and meet the students. Free entry, no registration needed."
    )
    plan = plan_add_event(Site(SiteSettings(root=site_dir)), client, notice, today=dt.date(2026, 2, 1))
    [change] = plan.changes
    assert "date: 2026-03-14" in change.after
    assert "kind:" in change.after
    print("\n" + plan.render())
