from pathlib import Path
from datetime import datetime
import pytest


def _import_app_or_skip():
    try:
        import app  # type: ignore
        return app
    except Exception as e:
        pytest.skip(f"Skipping: unable to import web app module: {e}")


def test_parse_transaction_file_extracts_rows(tmp_path, add_web_to_syspath):
    app = _import_app_or_skip()

    sample = (
        "Date: 2024-01-01, Name: COFFEE SHOP, Amount: $-3.50\n"
        "Date: 2024-01-02, Name: GROCERY STORE, Amount: $-45.10\n"
        "Date: 2024-01-03, Name: PAYCHECK, Amount: $2500.00\n"
    )
    file_path = tmp_path / "transactions_2024-01.txt"
    file_path.write_text(sample)

    result = app.parse_transaction_file(str(file_path))
    assert result["success"] is True
    assert result["count"] == 3

    tx0 = result["transactions"][0]
    expected_keys = {"id", "date", "datetime", "name", "merchant", "description", "amount", "time"}
    assert expected_keys.issubset(tx0.keys())
    assert tx0["date"] == "2024-01-01"
    assert isinstance(tx0["amount"], float)


def test_build_transaction_summary_surfaces_spend_patterns(add_web_to_syspath):
    app = _import_app_or_skip()

    transactions = [
        {
            "date": "2025-01-02",
            "datetime": datetime(2025, 1, 2),
            "merchant": "Coffee Shop",
            "description": "Coffee Shop",
            "amount": 8.5,
        },
        {
            "date": "2025-01-03",
            "datetime": datetime(2025, 1, 3),
            "merchant": "AMAZON MKTPL*ABC123",
            "description": "Amazon order",
            "amount": 42.0,
        },
        {
            "date": "2025-01-03",
            "datetime": datetime(2025, 1, 3),
            "merchant": "Coffee Shop",
            "description": "Coffee Shop",
            "amount": 11.5,
        },
        {
            "date": "2025-02-01",
            "datetime": datetime(2025, 2, 1),
            "merchant": "Coffee Shop",
            "description": "Coffee Shop",
            "amount": 9.0,
        },
        {
            "date": "2025-02-02",
            "datetime": datetime(2025, 2, 2),
            "merchant": "Payroll Deposit",
            "description": "Payroll Deposit",
            "amount": -2500.0,
        },
    ]

    summary = app.build_transaction_summary(transactions, lookback_days=60)

    assert summary["total_spend"]["amount"] == pytest.approx(71.0)
    assert summary["avg_daily_spend"]["amount"] == pytest.approx(23.67, abs=0.01)
    assert summary["largest_expense"]["merchant"] == "AMAZON MKTPL*ABC123"
    assert summary["peak_spend_day"]["date"] == "2025-01-03"
    assert summary["merchant_leaderboard"][0]["merchant"] == "AMAZON MKTPL*ABC123"
    assert summary["monthly_comparison"]["available"] is True

