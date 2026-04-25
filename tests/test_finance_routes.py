from datetime import datetime

import pytest


def _import_app_or_skip():
    try:
        import app  # type: ignore
        return app
    except Exception as exc:
        pytest.skip(f"Skipping: unable to import web app module: {exc}")


def _today_transaction_lines(count):
    today = datetime.now().strftime('%Y-%m-%d')
    return ''.join(
        f"Date: {today}, Name: MERCHANT {index}, Amount: $12.34\n"
        for index in range(count)
    )


def test_finance_tip_failure_returns_error_and_keeps_cached_file(tmp_path, add_web_to_syspath, monkeypatch):
    app_module = _import_app_or_skip()
    client = app_module.app.test_client()
    transaction_file = tmp_path / 'transactions_latest.txt'
    transaction_file.write_text(_today_transaction_lines(3), encoding='utf-8')

    monkeypatch.setattr(app_module, 'API_AUTH_TOKEN', '')
    monkeypatch.setattr(app_module, 'is_local_request_without_proxy', lambda: True)
    monkeypatch.setattr(
        app_module,
        'fetch_latest_transactions',
        lambda: {'success': True, 'file_path': str(transaction_file), 'error': None},
    )
    monkeypatch.setattr(
        app_module,
        'generate_finance_tip',
        lambda *args, **kwargs: {
            'success': False,
            'analysis': {},
            'error': 'LLM unavailable',
            'provider': 'local',
            'total_processed': 3,
            'analysis_limit': 200,
            'truncated': False,
        },
    )

    response = client.post('/api/finance-tip', json={})

    assert response.status_code == 502
    payload = response.get_json()
    assert payload['success'] is False
    assert payload['error'] == 'LLM unavailable'
    assert payload['analysis_provider'] == 'local'
    assert transaction_file.exists()


def test_monthly_spend_reports_analysis_limited_for_large_windows(add_web_to_syspath, monkeypatch):
    app_module = _import_app_or_skip()
    client = app_module.app.test_client()

    transactions = []
    for index in range(105):
        transactions.append(
            {
                'date': f'2026-04-{(index % 28) + 1:02d}',
                'datetime': datetime(2026, 4, (index % 28) + 1),
                'merchant': f'Coffee Shop {index}',
                'description': f'Coffee Shop {index}',
                'amount': 8.5,
                'account_name': 'Checking',
            }
        )

    monkeypatch.setattr(app_module, 'API_AUTH_TOKEN', '')
    monkeypatch.setattr(app_module, 'is_local_request_without_proxy', lambda: True)
    monkeypatch.setattr(
        app_module,
        'load_transactions_or_error',
        lambda data, default_lookback_days=180: (
            {
                'success': True,
                'transactions': transactions,
                'file_path': None,
                'cleanup_after_request': False,
                'lookback_days': 180,
            },
            None,
        ),
    )
    monkeypatch.setattr(
        app_module,
        'llm_categorize_transactions',
        lambda trx_list, **kwargs: {
            'success': True,
            'categorized_transactions': [
                {
                    **trx,
                    'category': 'Food & Dining',
                    'subcategory': 'Coffee',
                    'confidence': 'high',
                }
                for trx in trx_list[:100]
            ],
            'total_processed': 100,
            'error': None,
        },
    )
    monkeypatch.setattr(
        app_module,
        'identify_subscriptions',
        lambda trx_list: {'success': True, 'subscriptions': [], 'summary': {}, 'error': None},
    )

    response = client.post('/api/monthly-spend', json={})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['spend_transaction_count'] == 105
    assert payload['analyzed_transaction_count'] == 100
    assert payload['analysis_limited'] is True
    assert any(item['category'] == 'Uncategorized' for item in payload['transactions'])
