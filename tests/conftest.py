from pathlib import Path

import pytest


@pytest.fixture
def add_web_to_syspath(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    monkeypatch.syspath_prepend(str(root / 'src' / 'web'))
    return root
