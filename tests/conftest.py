import shutil
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "mini_site"


@pytest.fixture
def site_dir(tmp_path: Path) -> Path:
    """A fresh copy of the example site, so tests can write to it freely."""
    target = tmp_path / "site"
    shutil.copytree(FIXTURE, target)
    return target
