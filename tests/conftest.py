import sys
from pathlib import Path

import pytest


@pytest.fixture
def add_web_to_syspath():
    web_dir = Path(__file__).resolve().parents[1] / "src" / "web"
    web_dir_str = str(web_dir)
    if web_dir_str not in sys.path:
        sys.path.insert(0, web_dir_str)
    return web_dir_str
