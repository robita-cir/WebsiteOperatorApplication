"""Runs the real model server on the regression notices. Off by default. Enable with:
SITE_AGENT_LIVE=1 pytest -m live -s

Set SITE_AGENT_MODEL to the model to test (default qwen2.5:7b). Ollama must be running. The table of results is
printed (use -s to see it). Set SITE_AGENT_MIN_ACCURACY (for example 0.8) to make a lower score fail the test.
"""

import os

import pytest
from test_regression import run_regression

from site_agent.config import LLMSettings
from site_agent.llm import make_client

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("SITE_AGENT_LIVE") != "1", reason="set SITE_AGENT_LIVE=1 to run"),
]


def test_real_model_on_the_regression_notices():
    model = os.environ.get("SITE_AGENT_MODEL", "qwen2.5:7b")
    client = make_client(LLMSettings(model=model, timeout_s=600))
    result = run_regression(client, model)
    print("\n" + result.table())
    assert len(result.cases) == 8
    minimum = os.environ.get("SITE_AGENT_MIN_ACCURACY")
    if minimum:
        assert result.accuracy >= float(minimum)
