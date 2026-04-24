import importlib
import sys
from pathlib import Path

import pytest


def _import_app_or_skip(monkeypatch=None, token_value=None):
    try:
        if monkeypatch is not None and token_value is not None:
            monkeypatch.setenv("APP_API_TOKEN", token_value)
            sys.modules.pop("app", None)
        web_dir = Path(__file__).resolve().parents[1] / "src" / "web"
        if str(web_dir) not in sys.path:
            sys.path.insert(0, str(web_dir))
        return importlib.import_module("app")  # type: ignore
    except Exception as exc:
        pytest.skip(f"Skipping: unable to import web app module: {exc}")


def test_rag_page_renders(add_web_to_syspath):
    app_module = _import_app_or_skip()
    client = app_module.app.test_client()

    response = client.get("/rag")

    assert response.status_code == 200
    assert b"Transaction RAG Chat" in response.data


def test_rag_query_falls_back_when_lookback_empty(add_web_to_syspath, monkeypatch):
    app_module = _import_app_or_skip(monkeypatch=monkeypatch, token_value="test-token")
    client = app_module.app.test_client()

    old_csv = (
        "date,name,amount,account\n"
        "2020-01-03,Coffee Shop,8.75,Credit Card\n"
        "2020-01-04,Neighborhood Grocery,54.12,Checking\n"
    )
    payload = {
        "question": "How much did I spend at coffee shops?",
        "use_csv": True,
        "csv_data": old_csv,
        "lookback_days": 30,
        "use_llm": False,
        "top_k": 5,
        "api_token": "test-token",
    }

    response = client.post("/api/transactions-rag/query", json=payload)
    data = response.get_json() or {}

    assert response.status_code == 200
    assert data.get("success") is True
    assert data.get("lookback_fallback_used") is True
    assert "Using all available transactions" in str(data.get("lookback_fallback_message") or "")
