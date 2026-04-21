import csv
import io
from typing import Optional, Tuple

import requests


FRED_30YR_MORTGAGE_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"


def _parse_latest_mortgage_rate(csv_text: str) -> Tuple[Optional[str], Optional[float]]:
    latest_date = None
    latest_rate = None
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        rate_text = (row.get("MORTGAGE30US") or "").strip()
        if not rate_text or rate_text == ".":
            continue
        latest_date = (row.get("observation_date") or "").strip() or None
        latest_rate = float(rate_text)
    return latest_date, latest_rate


def get_latest_30yr_mortgage_rate():
    """
    Fetch the latest 30-year mortgage rate from FRED.
    Returns a dictionary with date, rate, and error information.
    """
    try:
        response = requests.get(FRED_30YR_MORTGAGE_CSV_URL, timeout=15)
        response.raise_for_status()
        latest_date, latest_rate = _parse_latest_mortgage_rate(response.text)
        if latest_date is None or latest_rate is None:
            raise RuntimeError("FRED response did not include a valid mortgage rate row.")
        return {
            "success": True,
            "date": latest_date,
            "rate": latest_rate,
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "date": None,
            "rate": None,
            "error": str(exc),
        }
