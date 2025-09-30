from pathlib import Path
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

