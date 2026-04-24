import importlib
import sys
from pathlib import Path


def _load_app_module(monkeypatch, token_value):
    web_dir = Path(__file__).resolve().parents[1] / "src" / "web"
    if str(web_dir) not in sys.path:
        sys.path.insert(0, str(web_dir))

    monkeypatch.setenv("APP_API_TOKEN", token_value)
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_protected_api_fails_closed_without_token_config(monkeypatch):
    app_module = _load_app_module(monkeypatch, "")
    client = app_module.app.test_client()

    response = client.post("/api/link-token", json={})
    payload = response.get_json() or {}

    assert response.status_code == 503
    assert "APP_API_TOKEN" in str(payload.get("error") or "")


def test_protected_api_requires_valid_token_and_allows_valid_header(monkeypatch):
    app_module = _load_app_module(monkeypatch, "test-token")

    class _DummyPipeline:
        def create_link_token(self, user_id):
            return "link-sandbox-token"

    app_module.get_bank_pipeline = lambda: _DummyPipeline()
    client = app_module.app.test_client()

    unauthorized = client.post("/api/link-token", json={})
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/api/link-token",
        json={"user_id": "u-1"},
        headers={"X-API-Key": "test-token"},
    )
    payload = authorized.get_json() or {}

    assert authorized.status_code == 200
    assert payload.get("link_token") == "link-sandbox-token"
