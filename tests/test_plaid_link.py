import pytest


def _import_app_or_skip():
    try:
        import app  # type: ignore
        return app
    except Exception as exc:
        pytest.skip(f"Skipping: unable to import web app module: {exc}")


def test_plaid_link_route_removed(add_web_to_syspath):
    app_module = _import_app_or_skip()
    client = app_module.app.test_client()

    response = client.get('/plaid-link')

    assert response.status_code == 404
    csp = response.headers.get('Content-Security-Policy', '')
    assert "frame-src 'self' https://cdn.plaid.com https://*.plaid.com" in csp
    assert "connect-src 'self' https://api.openai.com http://localhost:11434 https://localhost:11434 https://cdn.plaid.com https://*.plaid.com" in csp


def test_main_page_opens_plaid_link_without_redirect(add_web_to_syspath):
    app_module = _import_app_or_skip()
    client = app_module.app.test_client()

    response = client.get('/main')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "https://cdn.plaid.com/link/v2/stable/link-initialize.js" in html
    assert "fetch('/api/link-token'" in html
    assert "window.Plaid.create({" in html
    assert "window.location.href = '/plaid-link';" not in html
