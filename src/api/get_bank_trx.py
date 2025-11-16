"""
Plaid transaction export utilities.

This module can be imported from the web application or executed directly
from the command line to fetch transactions and cache them in ``data/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import plaid
from dotenv import load_dotenv
from plaid.api import plaid_api
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions

# Load environment variables once on import. Individual functions handle validation.
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ACCESS_TOKEN_PATTERN = re.compile(r"^access-(sandbox|development|production)-[A-Za-z0-9-]+$")


class PlaidConfigurationError(RuntimeError):
    """Raised when the Plaid client cannot be configured from the environment."""


class PlaidAccessTokenError(RuntimeError):
    """Raised when no valid Plaid access token is available."""


@dataclass
class PlaidCredentials:
    client: plaid_api.PlaidApi
    environment: str


def project_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parents[2]


def default_token_store_path() -> Path:
    """Location used to persist exchanged access tokens."""
    return project_root() / "data" / "plaid_access_tokens.json"


def read_token_store(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the persisted token store, ignoring format errors."""
    target = Path(path) if path else default_token_store_path()
    if not target.exists():
        return {"items": {}}
    try:
        return json.loads(target.read_text())
    except Exception as exc:  # pragma: no cover - extremely unlikely
        logger.warning("Unable to read token store %s: %s", target, exc)
        return {"items": {}}


def write_token_store(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Persist the token store to disk."""
    target = Path(path) if path else default_token_store_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, sort_keys=True))


def store_access_token(
    access_token: str,
    item_id: Optional[str] = None,
    token_store_path: Optional[Path] = None,
    source: str = "manual",
) -> Dict[str, Any]:
    """
    Persist an access token for reuse and update process environment variables.

    Returns metadata about the stored token.
    """
    token = (access_token or "").strip()
    if not is_valid_access_token(token):
        raise PlaidAccessTokenError(
            "Provided access token is invalid. Expected format: access-<environment>-<identifier>"
        )

    resolved_item_id = (item_id or os.getenv("PLAID_ITEM_ID") or "").strip() or None
    if not resolved_item_id:
        resolved_item_id = f"manual_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    store = read_token_store(token_store_path)
    items = store.setdefault("items", {})
    items[resolved_item_id] = token

    item_metadata = store.setdefault("item_metadata", {})
    item_metadata[resolved_item_id] = {
        "source": source,
        "updated_at": datetime.utcnow().isoformat(),
    }

    store["last_updated"] = datetime.utcnow().isoformat()
    store["last_item_id"] = resolved_item_id
    write_token_store(store, token_store_path)

    os.environ["PLAID_ACCESS_TOKEN"] = token
    os.environ["PLAID_ITEM_ID"] = resolved_item_id

    return {
        "access_token": token,
        "item_id": resolved_item_id,
        "source": source,
        "stored_at": store["last_updated"],
    }


def is_valid_access_token(token: Optional[str]) -> bool:
    """Return True if the string matches Plaid access token format."""
    token = (token or "").strip()
    return bool(token and ACCESS_TOKEN_PATTERN.match(token))


def extract_plaid_error(exc: plaid.ApiException) -> str:
    """Extract a readable error message from Plaid ApiException."""
    body = getattr(exc, "body", "")
    try:
        payload = json.loads(body) if body else {}
    except Exception:
        payload = {}

    code = payload.get("error_code")
    message = payload.get("error_message") or payload.get("display_message")
    request_id = payload.get("request_id")

    parts = []
    if code:
        parts.append(code)
    if message:
        parts.append(message)
    if request_id:
        parts.append(f"request_id={request_id}")

    if parts:
        return ": ".join(parts)
    return str(exc)


def create_plaid_client() -> PlaidCredentials:
    """Instantiate a Plaid client from environment variables."""
    client_id = os.getenv("PLAID_CLIENT_ID")
    secret = os.getenv("PLAID_SECRET")
    env_name = (os.getenv("PLAID_ENV") or "production").strip().lower()

    if not client_id or not secret:
        raise PlaidConfigurationError(
            "Missing Plaid credentials. Please set PLAID_CLIENT_ID and PLAID_SECRET "
            "in your environment or .env file."
        )

    env_mapping = {
        "sandbox": plaid.Environment.Sandbox,
        "development": plaid.Environment.Sandbox,  # Development maps to sandbox for most workflows
        "production": plaid.Environment.Production,
    }

    plaid_env = env_mapping.get(env_name)
    if plaid_env is None:
        raise PlaidConfigurationError(
            f"Unsupported PLAID_ENV '{env_name}'. Valid options: sandbox, development, production."
        )

    configuration = plaid.Configuration(
        host=plaid_env,
        api_key={
            "clientId": client_id,
            "secret": secret,
        },
    )
    api_client = plaid.ApiClient(configuration)
    return PlaidCredentials(client=plaid_api.PlaidApi(api_client), environment=env_name)


def exchange_public_token(
    credentials: PlaidCredentials,
    public_token: str,
    token_store_path: Optional[Path] = None,
    write_to_store: bool = True,
) -> Tuple[str, Optional[str]]:
    """Exchange a public token and persist the resulting access token."""
    try:
        request = ItemPublicTokenExchangeRequest(public_token=public_token)
        response = credentials.client.item_public_token_exchange(request)
        access_token = response["access_token"]
        item_id = response.get("item_id")

        if write_to_store:
            store_access_token(
                access_token,
                item_id=item_id,
                token_store_path=token_store_path,
                source="exchange",
            )

        if write_to_store:
            logger.info("Stored exchanged access token for item %s", item_id or "<unknown>")
        else:
            logger.info("Exchanged public token for item %s", item_id or "<unknown>")
        return access_token, item_id
    except plaid.ApiException as exc:
        raise PlaidAccessTokenError(
            f"Failed to exchange public token. {extract_plaid_error(exc)}"
        ) from exc


def resolve_access_token(
    credentials: PlaidCredentials,
    preferred_item_id: Optional[str] = None,
    token_store_path: Optional[Path] = None,
) -> Tuple[str, Optional[str], str]:
    """
    Find a usable Plaid access token.

    Order of precedence:
    1. PLAID_ACCESS_TOKEN (must look like access-<env>-<identifier>)
    2. PLAID_ACCESS_TOKENS (comma-separated list)
    3. Token store on disk (persisted exchanges)
    4. Exchange PLAID_PUBLIC_TOKEN if provided
    """
    candidates: List[Tuple[str, Optional[str], str]] = []

    env_token = (os.getenv("PLAID_ACCESS_TOKEN") or "").strip()
    env_item = (os.getenv("PLAID_ITEM_ID") or "").strip() or None
    if is_valid_access_token(env_token):
        candidates.append((env_token, env_item, "PLAID_ACCESS_TOKEN"))
    elif env_token:
        logger.warning("PLAID_ACCESS_TOKEN is set but not a valid Plaid access token format.")

    csv_tokens = os.getenv("PLAID_ACCESS_TOKENS")
    if csv_tokens:
        for raw in csv_tokens.split(","):
            token = raw.strip()
            if not token:
                continue
            if is_valid_access_token(token):
                candidates.append((token, None, "PLAID_ACCESS_TOKENS"))
            else:
                logger.warning("Ignoring token that does not match Plaid format from PLAID_ACCESS_TOKENS.")

    store = read_token_store(token_store_path)
    for item_id, token in (store.get("items") or {}).items():
        if is_valid_access_token(token):
            candidates.append((token, item_id, "token_store"))

    if preferred_item_id:
        for token, item_id, source in candidates:
            if item_id == preferred_item_id:
                return token, item_id, source

    if candidates:
        return candidates[0]

    public_token = (os.getenv("PLAID_PUBLIC_TOKEN") or "").strip()
    if public_token:
        logger.info("No saved access token found. Attempting exchange using PLAID_PUBLIC_TOKEN.")
        access_token, item_id = exchange_public_token(credentials, public_token, token_store_path)
        return access_token, item_id, "PLAID_PUBLIC_TOKEN"

    raise PlaidAccessTokenError(
        "No valid Plaid access token available. Please run the Plaid Link flow to obtain a token.\n"
        "Helpful steps:\n"
        "  1. Run `python src/api/bank_data_pipeline.py --link your_user_id` to generate a link token.\n"
        "  2. Complete Plaid Link and capture the public_token.\n"
        "  3. Exchange it via `python src/api/bank_data_pipeline.py <public_token>` "
        "and set PLAID_ACCESS_TOKEN or place it in data/plaid_access_tokens.json."
    )


def parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD string into a date."""
    return datetime.strptime(value, "%Y-%m-%d").date()


def determine_date_range(
    days_back: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Tuple[date, date]:
    """Compute a valid date range for the transaction query."""
    if start_date and end_date:
        pass
    elif start_date:
        end_date = datetime.today().date()
    elif end_date:
        start_date = end_date - timedelta(days=days_back or 90)
    else:
        end_date = datetime.today().date()
        start_date = end_date - timedelta(days=days_back or 90)

    if start_date is None or end_date is None:
        raise ValueError("Unable to determine date range.")

    if start_date > end_date:
        raise ValueError("Start date must be on or before end date.")

    return start_date, end_date


def build_account_filters() -> Dict[str, List[str]]:
    """Read optional account filtering configuration from environment variables."""
    account_ids = [x.strip() for x in (os.getenv("PLAID_ACCOUNT_IDS") or "").split(",") if x.strip()]
    account_name_keywords = [
        x.strip().lower() for x in (os.getenv("PLAID_ACCOUNT_NAME_FILTER") or "").split(",") if x.strip()
    ]
    account_subtypes = [
        x.strip().lower() for x in (os.getenv("PLAID_ACCOUNT_SUBTYPES") or "").split(",") if x.strip()
    ]

    return {
        "account_ids": account_ids,
        "account_name_keywords": account_name_keywords,
        "account_subtypes": account_subtypes,
    }


def filter_transactions(
    transactions: Iterable[Any],
    account_map: Dict[str, Any],
    filters: Dict[str, List[str]],
) -> List[Any]:
    """Filter transactions based on configured account criteria."""
    account_ids = set(filters.get("account_ids") or [])
    name_keywords = filters.get("account_name_keywords") or []
    subtypes = set(filters.get("account_subtypes") or [])

    if not account_ids and not name_keywords and not subtypes:
        return list(transactions)

    result: List[Any] = []
    for txn in transactions:
        account = account_map.get(txn.account_id)
        account_name = ""
        account_subtype = ""
        if account is not None:
            account_name = (getattr(account, "official_name", None) or getattr(account, "name", "") or "").lower()
            account_subtype = (getattr(account, "subtype", "") or "").lower()

        keep = True
        if account_ids:
            keep = txn.account_id in account_ids
        if keep and name_keywords:
            keep = bool(account_name and any(keyword in account_name for keyword in name_keywords))
        if keep and subtypes:
            keep = account_subtype in subtypes

        if keep:
            result.append(txn)

    return result


def fetch_transactions_for_token(
    credentials: PlaidCredentials,
    access_token: str,
    start_date: date,
    end_date: date,
    filters: Optional[Dict[str, List[str]]] = None,
) -> Tuple[List[Any], Dict[str, Any]]:
    """Retrieve Plaid transactions and accompanying accounts."""
    filters = filters or {}
    options = TransactionsGetRequestOptions()
    account_ids = filters.get("account_ids") or []
    if account_ids:
        options.account_ids = list(account_ids)

    request = TransactionsGetRequest(
        access_token=access_token,
        start_date=start_date,
        end_date=end_date,
        options=options,
    )

    try:
        response = credentials.client.transactions_get(request)
    except plaid.ApiException as exc:
        raise RuntimeError(f"Plaid API Error: {extract_plaid_error(exc)}") from exc

    transactions = list(response.transactions)
    accounts = {acct.account_id: acct for acct in getattr(response, "accounts", [])}

    while len(transactions) < response.total_transactions:
        request.options.offset = len(transactions)
        response = credentials.client.transactions_get(request)
        transactions.extend(response.transactions)
        for acct in getattr(response, "accounts", []):
            accounts[acct.account_id] = acct

    transactions = filter_transactions(transactions, accounts, filters)
    return transactions, accounts


def serialize_transactions(transactions: Iterable[Any], account_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert Plaid transaction models into serializable dicts."""
    data: List[Dict[str, Any]] = []
    for txn in transactions:
        account = account_map.get(txn.account_id)
        account_name = ""
        if account is not None:
            account_name = (
                getattr(account, "official_name", None)
                or getattr(account, "name", None)
                or getattr(account, "masked", None)
                or ""
            )

        data.append(
            {
                "date": str(getattr(txn, "date", "")),
                "name": getattr(txn, "name", ""),
                "merchant_name": getattr(txn, "merchant_name", None),
                "amount": float(getattr(txn, "amount", 0.0)),
                "account_id": getattr(txn, "account_id", ""),
                "account_name": account_name,
                "category": list(getattr(txn, "category", []) or []),
                "transaction_id": getattr(txn, "transaction_id", ""),
            }
        )
    return data


def write_transactions_to_file(
    transactions: List[Dict[str, Any]],
    start_date: date,
    end_date: date,
    output_dir: Optional[Path] = None,
) -> Path:
    """Persist transactions to a text file and return the path."""
    target_dir = Path(output_dir) if output_dir else project_root() / "data"
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = target_dir / f"transactions_{start_date}_to_{end_date}.txt"
    with filename.open("w", encoding="utf-8") as handle:
        header = f"Found {len(transactions)} transactions from {start_date} to {end_date}:\n"
        header += "=" * 60 + "\n\n"
        handle.write(header)

        for txn in transactions:
            amount = txn["amount"]
            line = f"Date: {txn['date']}, Name: {txn['name']}, Amount: ${amount:.2f}"
            if txn.get("account_name"):
                line += f", Account: {txn['account_name']}"
            handle.write(line + "\n")

        summary = "\n" + "=" * 60 + f"\nTotal transactions saved to: {filename}\n"
        handle.write(summary)

    return filename


def fetch_and_save_transactions(
    days_back: int = 90,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    item_id: Optional[str] = None,
    output_dir: Optional[Path] = None,
    token_store_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    High-level helper used by the web app to fetch and cache transactions.

    Returns a dictionary containing metadata about the export.
    """
    credentials = create_plaid_client()
    start_date, end_date = determine_date_range(days_back=days_back, start_date=start_date, end_date=end_date)
    filters = build_account_filters()

    access_token, resolved_item_id, token_source = resolve_access_token(
        credentials, preferred_item_id=item_id, token_store_path=token_store_path
    )

    transactions, accounts = fetch_transactions_for_token(credentials, access_token, start_date, end_date, filters)
    serialised = serialize_transactions(transactions, accounts)
    serialised.sort(key=lambda record: (record["date"], record["transaction_id"]))

    file_path = write_transactions_to_file(serialised, start_date, end_date, output_dir)

    total_amount = sum(txn["amount"] for txn in serialised)
    return {
        "file_path": str(file_path),
        "transaction_count": len(serialised),
        "total_amount": total_amount,
        "item_id": resolved_item_id,
        "access_token_source": token_source,
        "start_date": str(start_date),
        "end_date": str(end_date),
    }


def cli(argv: Optional[List[str]] = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Fetch transactions from Plaid and cache them locally.")
    parser.add_argument("start_date", nargs="?", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("end_date", nargs="?", help="End date in YYYY-MM-DD format.")
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of days to look back when start/end dates are not provided (default: 90).",
    )
    parser.add_argument("--item-id", help="Prefer transactions for the specified Plaid item_id.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory where the transaction file should be written (default: data/).",
    )
    parser.add_argument(
        "--token-store",
        type=Path,
        help="Override the location used to persist exchanged access tokens.",
    )

    args = parser.parse_args(argv)

    try:
        start_date = parse_date(args.start_date) if args.start_date else None
        end_date = parse_date(args.end_date) if args.end_date else None
        result = fetch_and_save_transactions(
            days_back=args.days,
            start_date=start_date,
            end_date=end_date,
            item_id=args.item_id,
            output_dir=args.output_dir,
            token_store_path=args.token_store,
        )
        logger.info(
            "Fetched %s transactions (%s to %s) -> %s",
            result["transaction_count"],
            result["start_date"],
            result["end_date"],
            result["file_path"],
        )
        return 0
    except (PlaidConfigurationError, PlaidAccessTokenError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(cli())
