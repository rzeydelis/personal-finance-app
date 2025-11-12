"""
Bank data pipeline built on Plaid helpers.

This module layers user-friendly orchestration on top of the reusable Plaid
utilities defined in ``src/api/get_bank_trx.py`` so the CLI and web tier can:

1. Create Plaid Link tokens.
2. Exchange Plaid public tokens for access tokens and persist them locally.
3. Fetch Chase (or other selected) transactions for the past *N* days.
4. Format the transactions for download (JSON/CSV/TXT).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

import plaid
from plaid.model.country_code import CountryCode
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products

from get_bank_trx import (  # type: ignore
    PlaidAccessTokenError,
    PlaidConfigurationError,
    PlaidCredentials,
    build_account_filters,
    create_plaid_client,
    default_token_store_path,
    determine_date_range,
    exchange_public_token,
    fetch_transactions_for_token,
    resolve_access_token,
    serialize_transactions,
    store_access_token,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class BankDataPipeline:
    """High-level Plaid workflow helper."""

    def __init__(self, token_store_path: Optional[Path] = None):
        project_root = Path(__file__).resolve().parents[2]
        env_file = project_root / ".env"
        if env_file.exists():
            load_dotenv(env_file)
        load_dotenv()

        self.credentials: PlaidCredentials = create_plaid_client()
        self.client = self.credentials.client
        self.environment = self.credentials.environment
        self.token_store_path = token_store_path or default_token_store_path()
        logger.info("BankDataPipeline ready (env=%s, token_store=%s)", self.environment, self.token_store_path)

    # ------------------------------------------------------------------ #
    # Plaid Link helpers

    def create_link_token(self, user_id: str) -> str:
        """
        Create a Plaid Link token the frontend can use to launch Plaid Link.

        Args:
            user_id: Stable identifier for the end-user.
        """
        client_name = os.getenv("PLAID_CLIENT_NAME", "Personal Finance App")
        request = LinkTokenCreateRequest(
            products=[Products("transactions")],
            client_name=client_name,
            country_codes=[CountryCode("US")],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id=user_id),
        )
        try:
            response = self.client.link_token_create(request)
            link_token = response.get("link_token")
            if not link_token:
                raise RuntimeError("Plaid did not return a link_token payload.")
            logger.info("Created Plaid link token for user %s", user_id)
            return link_token
        except plaid.ApiException as exc:  # pragma: no cover - Plaid decides errors
            logger.error("Failed to create link token: %s", exc)
            raise

    # ------------------------------------------------------------------ #
    # Token storage helpers

    def store_access_token(
        self,
        access_token: str,
        item_id: Optional[str] = None,
        source: str = "manual",
    ) -> Dict[str, Any]:
        """
        Persist and activate a Plaid access token for subsequent requests.
        """
        return store_access_token(
            access_token=access_token,
            item_id=item_id,
            token_store_path=self.token_store_path,
            source=source,
        )

    def exchange_public_token(self, public_token: str, item_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Exchange a Plaid public token for an access token and persist it.
        """
        access_token, exchanged_item_id = exchange_public_token(
            self.credentials,
            public_token,
            token_store_path=self.token_store_path,
            write_to_store=False,
        )
        metadata = self.store_access_token(
            access_token,
            item_id=exchanged_item_id or item_id,
            source="exchange",
        )
        logger.info("Token exchange complete for item %s", metadata.get("item_id"))
        return metadata

    # ------------------------------------------------------------------ #
    # Transactions

    def get_transactions(
        self,
        days_back: int = 90,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        item_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve and summarise transactions for the configured Plaid item.
        """
        filters = build_account_filters()
        start, end = determine_date_range(days_back=days_back, start_date=start_date, end_date=end_date)

        if access_token:
            token_meta = self.store_access_token(access_token, item_id=item_id, source="manual")
            access_token = token_meta["access_token"]
            item_id = token_meta["item_id"]
            token_source = token_meta["source"]
        else:
            access_token, item_id, token_source = resolve_access_token(
                self.credentials,
                preferred_item_id=item_id,
                token_store_path=self.token_store_path,
            )

        transactions, accounts = fetch_transactions_for_token(
            self.credentials,
            access_token,
            start,
            end,
            filters,
        )

        records = serialize_transactions(transactions, accounts)
        records.sort(key=lambda row: (row["date"], row["transaction_id"]))

        summary = {
            "transactions": records,
            "item_id": item_id,
            "access_token_source": token_source,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "total_transactions": len(records),
            "total_amount": sum(row["amount"] for row in records),
        }
        logger.info(
            "Retrieved %s transactions (%s to %s) using item %s",
            summary["total_transactions"],
            summary["start_date"],
            summary["end_date"],
            item_id,
        )
        return summary

    # ------------------------------------------------------------------ #
    # Formatting helpers

    def format_transactions_for_download(
        self,
        transactions: List[Dict[str, Any]],
        format_type: str = "json",
    ) -> Tuple[str, str]:
        """
        Convert transactions to the requested format.
        """
        format_type = (format_type or "json").lower()
        if format_type == "csv":
            import csv
            import io

            buffer = io.StringIO()
            if transactions:
                writer = csv.DictWriter(buffer, fieldnames=sorted(transactions[0].keys()))
                writer.writeheader()
                writer.writerows(transactions)
            return buffer.getvalue(), "csv"

        if format_type == "txt":
            lines: List[str] = []
            lines.append(f"Bank Transactions Report - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("=" * 80)
            lines.append("")
            total_amount = 0.0
            for index, txn in enumerate(transactions, 1):
                total_amount += txn["amount"]
                lines.append(f"{index:3d}. {txn['date']} | {txn['name']:<30} | ${txn['amount']:>8.2f}")
                if txn.get("account_name"):
                    lines.append(f"     Account: {txn['account_name']}")
                if txn.get("category"):
                    lines.append(f"     Category: {', '.join(txn['category'])}")
                lines.append("")
            lines.append("=" * 80)
            lines.append(f"Total transactions: {len(transactions)}")
            lines.append(f"Total amount: ${total_amount:.2f}")
            return "\n".join(lines), "txt"

        payload = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_transactions": len(transactions),
                "total_amount": sum(txn["amount"] for txn in transactions),
            },
            "transactions": transactions,
        }
        return json.dumps(payload, indent=2), "json"

    def one_click_download(
        self,
        *,
        user_id: str,
        days_back: int = 90,
        format_type: str = "json",
        public_token: Optional[str] = None,
        access_token: Optional[str] = None,
        item_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete pipeline: (optionally) exchange token, fetch transactions, format output.
        """
        metadata: Optional[Dict[str, Any]] = None
        if public_token:
            metadata = self.exchange_public_token(public_token, item_id=item_id)
        elif access_token:
            metadata = self.store_access_token(access_token, item_id=item_id, source="manual")

        item_hint = (metadata or {}).get("item_id") or item_id

        transactions_summary = self.get_transactions(days_back=days_back, item_id=item_hint)
        formatted_data, file_extension = self.format_transactions_for_download(
            transactions_summary["transactions"],
            format_type=format_type,
        )

        filename = f"bank_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"

        return {
            "success": True,
            "filename": filename,
            "data": formatted_data,
            "metadata": {
                "user_id": user_id,
                "format": format_type,
                "generated_at": datetime.now().isoformat(),
                **{k: v for k, v in transactions_summary.items() if k != "transactions"},
            },
        }


# ---------------------------------------------------------------------- #
# CLI

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Plaid one-click bank data pipeline.")
    parser.add_argument("--link", nargs="?", const="demo_user_123", help="Create a Plaid link token for the given user id.")
    parser.add_argument("--exchange", help="Exchange a Plaid public token for an access token.")
    parser.add_argument("--store-access", dest="store_access", help="Store a Plaid access token manually.")
    parser.add_argument("--item-id", help="Override item id when storing or downloading.")
    parser.add_argument("--download", action="store_true", help="Fetch and format transactions.")
    parser.add_argument("--days", type=int, default=90, help="Lookback window when downloading transactions (default 90).")
    parser.add_argument("--format", choices=["json", "csv", "txt"], default="json", help="Download format (default json).")
    parser.add_argument("--public-token", help="Exchange this public token before downloading transactions.")
    parser.add_argument("--access-token", help="Use and persist this access token before downloading transactions.")
    parser.add_argument("--output", type=Path, help="Write formatted data to this path.")
    parser.add_argument("legacy_public_token", nargs="?", help="(Legacy) public token shorthand to exchange.")

    args = parser.parse_args(argv)

    tasks = []
    if args.link is not None:
        tasks.append("link")
    if args.exchange:
        tasks.append("exchange")
    if args.store_access:
        tasks.append("store")
    if args.download:
        tasks.append("download")

    if not tasks and args.legacy_public_token:
        args.exchange = args.legacy_public_token
        tasks.append("exchange")

    if not tasks:
        # Default legacy behaviour: create a link token.
        args.link = "demo_user_123"
        tasks.append("link")

    if len(tasks) > 1:
        parser.error("Specify only one primary action among --link, --exchange, --store-access, or --download.")

    pipeline = BankDataPipeline()

    try:
        if tasks[0] == "link":
            user_id = args.link or "demo_user_123"
            token = pipeline.create_link_token(user_id)
            print(f"Link token for user '{user_id}':\n{token}")
            return 0

        if tasks[0] == "exchange":
            metadata = pipeline.exchange_public_token(args.exchange, item_id=args.item_id)
            print(json.dumps(metadata, indent=2))
            return 0

        if tasks[0] == "store":
            metadata = pipeline.store_access_token(args.store_access, item_id=args.item_id, source="manual")
            print(json.dumps(metadata, indent=2))
            return 0

        if tasks[0] == "download":
            metadata: Optional[Dict[str, Any]] = None
            if args.public_token:
                metadata = pipeline.exchange_public_token(args.public_token, item_id=args.item_id)
            elif args.access_token:
                metadata = pipeline.store_access_token(args.access_token, item_id=args.item_id, source="manual")

            result = pipeline.one_click_download(
                user_id="cli_user",
                days_back=args.days,
                format_type=args.format,
                item_id=(metadata or {}).get("item_id") or args.item_id,
            )

            if args.output:
                args.output.write_text(result["data"])
                print(f"Wrote {args.format.upper()} data to {args.output}")
            else:
                print(result["data"])
            print(json.dumps(result["metadata"], indent=2))
            return 0

    except (PlaidConfigurationError, PlaidAccessTokenError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    except plaid.ApiException as exc:  # pragma: no cover
        logger.error("Plaid API error: %s", exc)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
