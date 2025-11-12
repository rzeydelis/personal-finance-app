import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# LLM client
try:
    from .llms import generate_json as llm_generate_json
except Exception:
    try:
        from llms import generate_json as llm_generate_json
    except Exception:
        llm_generate_json = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

fetch_and_save_transactions = None
store_access_token = None
create_plaid_client = None
exchange_public_token = None
PlaidAccessTokenError = RuntimeError  # type: ignore
PlaidConfigurationError = RuntimeError  # type: ignore
BankDataPipeline = None  # type: ignore

try:
    from src.api.get_bank_trx import (
        PlaidAccessTokenError,
        PlaidConfigurationError,
        create_plaid_client,
        exchange_public_token,
        fetch_and_save_transactions,
        store_access_token,
    )
except Exception:
    try:
        from ..api.get_bank_trx import (  # type: ignore
            PlaidAccessTokenError,
            PlaidConfigurationError,
            create_plaid_client,
            exchange_public_token,
            fetch_and_save_transactions,
            store_access_token,
        )
    except Exception:
        try:
            from api.get_bank_trx import (  # type: ignore
                PlaidAccessTokenError,
                PlaidConfigurationError,
                create_plaid_client,
                exchange_public_token,
                fetch_and_save_transactions,
                store_access_token,
            )
        except Exception:
            pass

try:
    from src.api.bank_data_pipeline import BankDataPipeline  # type: ignore
except Exception:
    try:
        from ..api.bank_data_pipeline import BankDataPipeline  # type: ignore
    except Exception:
        try:
            from api.bank_data_pipeline import BankDataPipeline  # type: ignore
        except Exception:
            BankDataPipeline = None  # type: ignore

_bank_pipeline = None


def get_bank_pipeline():
    """Return a cached BankDataPipeline instance."""
    global _bank_pipeline
    if BankDataPipeline is None:
        raise RuntimeError("Plaid pipeline utilities are unavailable. Check your installation.")
    if _bank_pipeline is None:
        _bank_pipeline = BankDataPipeline()
    return _bank_pipeline


def fetch_fresh_transactions_from_plaid(days_back=90):
    """Fetch fresh transactions from Plaid API"""
    try:
        if not fetch_and_save_transactions:
            return {
                'success': False,
                'file_path': None,
                'error': 'Plaid fetch utilities are unavailable. Ensure src/api/get_bank_trx.py is accessible.'
            }

        result = fetch_and_save_transactions(days_back=days_back)
        file_path = result.get('file_path')
        if file_path and Path(file_path).exists():
            logging.info(
                "Fetched %s transactions from %s to %s (item_id=%s, source=%s)",
                result.get('transaction_count'),
                result.get('start_date'),
                result.get('end_date'),
                result.get('item_id'),
                result.get('access_token_source'),
            )
            return {'success': True, 'file_path': file_path, 'error': None}
        return {'success': False, 'file_path': None, 'error': 'Transaction file was not created'}
    except PlaidConfigurationError as e:
        return {'success': False, 'file_path': None, 'error': f'Plaid configuration error: {e}'}
    except PlaidAccessTokenError as e:
        return {'success': False, 'file_path': None, 'error': str(e)}
    except Exception as e:
        logging.exception("Unexpected error fetching transactions from Plaid")
        return {'success': False, 'file_path': None, 'error': str(e)}

def fetch_latest_transactions():
    """Fetch latest transactions from data directory"""
    try:
        data_dir = Path(__file__).parent.parent.parent / 'data'
        transaction_files = list(data_dir.glob('transactions_*.txt'))
        if transaction_files:
            latest_file = max(transaction_files, key=lambda x: x.stat().st_mtime)
            return {'success': True, 'file_path': str(latest_file), 'error': None}
        return {'success': False, 'file_path': None, 'error': 'No transaction files found'}
    except Exception as e:
        return {'success': False, 'file_path': None, 'error': str(e)}

def parse_transaction_file(file_path):
    """Parse transaction file into structured data"""
    transactions = []
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        pattern = r'Date: ([\d-]+), Name: ([^,]+), Amount: \$([+-]?[\d.]+)(?:, Account: ([^\n]+))?'
        matches = re.findall(pattern, content)

        for i, (date_str, name, amount_str, account_name) in enumerate(matches):
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                amount = float(amount_str.strip())
                account_clean = account_name.strip() if account_name else None

                transactions.append({
                    'id': i + 1,
                    'date': date_str,
                    'datetime': date_obj,
                    'name': name.strip(),
                    'merchant': name.strip(),
                    'description': name.strip(),
                    'amount': amount,
                    'account_name': account_clean,
                    'time': '12:00:00'
                })
            except (ValueError, IndexError):
                continue

        return {'success': True, 'transactions': transactions, 'count': len(transactions), 'error': None}
    except Exception as e:
        return {'success': False, 'transactions': [], 'count': 0, 'error': str(e)}

def generate_finance_tip(transactions):
    """Generate personalized finance tip using LLM"""
    if not llm_generate_json:
        return {'success': False, 'analysis': {}, 'error': 'LLM not available'}
    
    # Limit transactions to prevent timeout
    max_transactions = 200
    if len(transactions) > max_transactions:
        transactions = transactions[:max_transactions]
    
    csv_data = "Date,Time,Merchant,Description,Amount\n"
    for trx in transactions:
        csv_data += f"{trx['date']},{trx.get('time','')},{trx.get('merchant','')},{trx.get('description','')},{trx.get('amount',0)}\n"
    # print(f"CSV data: {csv_data}")
#     prompt = """
#     You are a **personal finance coach** analyzing the user’s recent transactions.
# Your goal is to identify **exactly one** specific, data-grounded savings or optimization tip.
# Base all reasoning **strictly on the provided transaction data**—do not invent facts, products, or services.

# Reality checks
# - If you mention a product/membership/subscription, only do so if it (a) clearly appears in the data or (b) is widely known to exist (e.g., Netflix, Spotify). If uncertain, generalize (e.g., “seek commuter discounts”).
# - Do NOT recommend programs that don’t exist (e.g., PATH “annual subscription”).

# Must-choose rule (no empty responses)
# You MUST return one tip even if patterns are weak. Use this priority order and pick the first that applies; if ties, choose the one with the largest **annualized savings**:
# 1) Bank/ATM fees, interest, overdraft, or late fees.
# 2) Repeat merchant (≥2 occurrences) with meaningful total.
# 3) Category spike (one category >30% of total or >2× the next category).
# 4) Unusually large charge (single txn ≥ 3× the median txn).
# 5) High-frequency small purchases from the same category/merchant (≥4).
# 6) Fallback: If none apply or data is sparse/unparsable, give a neutral, data-anchored ops tip (e.g., “label uncategorized transactions to surface savings next run”). Still include dates/amounts if any.

# What to produce (exactly one tip)
# - Title: short and specific to the pattern (e.g., “Reduce repeated DoorDash spend (4 charges)”).
# - Advice: Explain the pattern and why it matters, citing specific transactions (date, merchant, amount).
# - Potential savings: Numeric dollar range or projection tied to your math (e.g., “$180–$260/year”).
# - Actionable steps (2–3): Each step must include a trigger, an owner (“you”), and a timeframe.
# - Avoid vague platitudes (“track subscriptions”) unless directly evidenced by the data.

# Math rules
# - Show quick math that aggregates to monthly and/or yearly.
# - If savings are small (<$50/year), still output a tip and label it a “small win.”

# Output format (JSON only)
# Return ONLY valid JSON (no markdown, no extra text, no trailing commas) in this exact shape, with non-empty strings and 2–3 steps:
# {
#   "tip": {
#     "title": "...",
#     "advice": "...",
#     "potential_savings": "...",
#     "actionable_steps": ["...", "..."]
#   }
# }

# Deterministic tie-breakers
# - If multiple candidates exist, pick the one with the highest annualized savings.
# - If savings are equal, prefer fees/interest > repeat merchant > category spike > large charge > high-frequency small purchases.
# - If still tied, choose the one with more transactions cited.

# Error/sparsity handling
# - If {csv_data} is empty or cannot be parsed, output a tip titled “Data insufficient: prepare for savings next run” with steps like categorizing uncategorized items, connecting missing accounts, or fixing date/amount formats. Keep fields non-empty.

# Examples

# Example A — Repeat merchant (food delivery)
# Transactions (CSV)
# date,merchant,amount,category,account
# 2025-10-02,DoorDash,24.18,Food Delivery,Visa
# 2025-10-06,DoorDash,18.75,Food Delivery,Visa
# 2025-10-12,DoorDash,27.40,Food Delivery,Visa
# 2025-10-21,DoorDash,22.10,Food Delivery,Visa
# 2025-10-25,Trader Joe's,62.33,Grocery,Checking
# Output
# {
#   "tip": {
#     "title": "Trim repeat DoorDash spend (4 charges, $92.43 in Oct)",
#     "advice": "You placed four DoorDash orders on 10/02 ($24.18), 10/06 ($18.75), 10/12 ($27.40), and 10/21 ($22.10), totaling $92.43. If this cadence continues (~$90–$95/month), that’s ~$1,100/year. Replacing even 2 of 4 orders per month with grocery or pickup alternatives reduces delivery/service fees.",
#     "potential_savings": "$180–$360/year (cut 2 of 4 monthly orders; ~$7–$15 in fees per avoided order × 24 orders/year)",
#     "actionable_steps": [
#       "Trigger: placing a delivery order; Owner: you; Timeframe: next 30 days — choose pickup for 2 orders/month to avoid delivery/service fees.",
#       "Trigger: Sunday meal planning; Owner: you; Timeframe: weekly — buy $20 of ready-to-heat items at Trader Joe’s to replace one delivery night.",
#       "Trigger: spending alert over $75 in Food Delivery/month; Owner: you; Timeframe: set today — send a mobile alert and switch to at-home meal."
#     ]
#   }
# }

# Example B — Fees (highest priority)
# Transactions (CSV)
# date,merchant,amount,category,account
# 2025-11-05,Bank Maintenance Fee,12.00,Fees,Checking
# 2025-10-05,Bank Maintenance Fee,12.00,Fees,Checking
# 2025-10-27,Starbucks,5.45,Coffee,Visa
# 2025-10-31,Uber,18.90,Transport,Visa
# Output
# {
#   "tip": {
#     "title": "Eliminate monthly bank maintenance fees ($12/month)",
#     "advice": "You were charged maintenance fees on 10/05 ($12.00) and 11/05 ($12.00). That’s $24 in two months, projecting to ~$144/year if unchanged.",
#     "potential_savings": "$120–$144/year (waive fees via minimum balance or direct deposit)",
#     "actionable_steps": [
#       "Trigger: paycheck setup; Owner: you; Timeframe: this week — enable direct deposit to meet the no-fee requirement.",
#       "Trigger: balance below bank’s waiver threshold; Owner: you; Timeframe: ongoing — keep the required minimum in Checking to avoid the $12 charge.",
#       "Trigger: if waiver not feasible; Owner: you; Timeframe: within 14 days — open a fee-free checking account and move bill-pay/ACH."
#     ]
#   }
# }

# Example C — Unusually large charge (one-off optimization)
# Transactions (CSV)
# date,merchant,amount,category,account
# 2025-10-08,WholeLife Insurance Annual,1,280.00,Insurance,Checking
# 2025-10-14,Shell,42.10,Gas,Visa
# 2025-10-21,CVS,17.85,Pharmacy,Visa
# 2025-10-25,Costco,128.40,Grocery,Visa
# Output
# {
#   "tip": {
#     "title": "Optimize large annual insurance payment ($1,280 on 10/08)",
#     "advice": "You paid a single $1,280 insurance premium on 10/08. Large annual payments can incur opportunity costs or miss autopay discounts. If a pay-in-full or autopay discount (2–5%) exists, it could reduce this expense next cycle.",
#     "potential_savings": "$25–$65/year (2–5% discount on $1,280, if available; otherwise small win via autopay/loyalty checks)",
#     "actionable_steps": [
#       "Trigger: policy renewal notice; Owner: you; Timeframe: 30 days before renewal — ask the insurer to confirm any pay-in-full or autopay discount and apply it.",
#       "Trigger: monthly cash-flow plan; Owner: you; Timeframe: this month — set aside ~$107/month in a savings bucket to avoid fees and capture any early-pay discount.",
#       "Trigger: competing quote available; Owner: you; Timeframe: within 2 weeks — get 2 comparison quotes to validate the current rate."
#     ]
#   }
# }

# Example D — Sparse/uncertain data (fallback)
# Transactions (CSV)
# date,merchant,amount,category,account
# Output
# {
#   "tip": {
#     "title": "Data insufficient: prepare for savings next run",
#     "advice": "No parsable transactions were provided, so pattern detection (repeat merchant, category spikes, fees) couldn’t run. Ensuring clean dates, merchants, categories, and amounts will unlock targeted savings.",
#     "potential_savings": "$50–$200/year (typical small wins from basic fee waivers and duplicate subscription checks once data is available)",
#     "actionable_steps": [
#       "Trigger: account linking; Owner: you; Timeframe: today — connect all checking, credit cards, and popular wallets to capture a full 30–90 days.",
#       "Trigger: CSV export; Owner: you; Timeframe: today — re-export with headers (date, merchant, amount, category, account) and standard date format (YYYY-MM-DD).",
#       "Trigger: next import; Owner: you; Timeframe: within 48 hours — re-run the analysis to surface high-confidence tips."
#     ]
#   }
# }

# Transactions (CSV)
# {csv_data}
# """
    prompt = """
You are a personal finance analyst. Your task is to analyze and summarize the user’s transactions clearly, concretely, and insightfully.
Your analysis should extract meaningful financial behavior patterns while remaining strictly grounded in the provided data.

Data Schema

CSV columns:
date,time,name,description,amount,account

Dates: YYYY-MM-DD

Amounts: positive numbers = spending (debits), negative numbers or explicit “credit/refund” language = refunds or inflows

Accounts: may indicate source (e.g., “Total Checking”, “Ultimate Rewards®”)

Name = merchant or payee.

Goals

Summarize the spending window — include number of days, total spend, and transaction count.

Highlight interesting insights, such as:

Repeat or frequent merchants

Unusual spending spikes or quiet periods

Category clusters (e.g., food, utilities, health, subscriptions inferred by merchant patterns)

Fees or charges (ATM, maintenance, overdraft, transfer)

Cash withdrawals or peer-to-peer transfers (Zelle, Venmo, Cash App)

Large purchases vs. typical amounts

Micro-orders (frequent small transactions from same merchant)

Account usage patterns (if multiple accounts are present)

Quantify with math — totals, medians, projections, comparisons to averages when relevant.

Stay strictly within data evidence — do not infer non-existent memberships or assumptions (e.g., no guessing “Netflix subscription” unless name explicitly contains it).

If data covers multiple months, mention month-over-month or weekly trends if detectable.

Parsing & Normalization Rules

Treat a row as valid if date and amount parse.

Normalize merchant name as first token before *, /, or first space (e.g., Amazon.com*ABCD → “Amazon”).

Normalize fees by matching FEE, MAINTENANCE, OVERDRAFT, ATM, WITHDRAW.

Normalize cash transfers by matching: Zelle, Venmo, Cash App, Transfer, Withdraw.

Identify repeat merchants as ≥2 transactions with same normalized merchant.

Define large purchase as amount ≥ 3× median spend.

Define micro-orders as ≥4 purchases ≤ $25 from same merchant within 7 days.

If no valid rows, output "status": "insufficient_data".

Computed Metrics

window: min and max dates found

totals: count of valid transactions, total spend (sum of positive amounts)

top_merchants: up to 5 merchants by total spend

fees: each fee with date, name, description, amount; add monthly projection if ≥2 similar fees

cash_transfers: list each with date, amount, and type (e.g., “Zelle payment”)

large_purchases: list each with date, merchant, amount, and × median multiple

micro_orders: summarize clusters (merchant, count, total, date range)

insights: 3–6 short sentences describing most interesting behavioral or numerical findings (e.g., “Frequent Zelle transfers totaling $900 in August,” “Noticeable spending dip in mid-September”).

notes: include parsing caveats, rules applied, or missing data details.

Output Format (JSON only; no markdown)



Tie-Breakers and Guardrails

For top_merchants, tie-break by higher spend → higher count → lexicographic name.

Do not hallucinate unknown categories, subscriptions, or rewards programs.

Keep insights concise (≤ 20 words each).

If multiple accounts, mention cross-account trends only if data supports it.

Transactions (CSV)
{csv_data}

✅ Example Input Snippet
date,time,name,description,amount,account
2025-08-07,12:00:00,FUEL 4 GROVE STREET,FUEL 4 GROVE STREET,35.96,Ultimate Rewards®
2025-08-07,12:00:00,Target,Target,78.48,Ultimate Rewards®
2025-08-07,12:00:00,Schweiger Dermatology,Schweiger Dermatology,30.00,Ultimate Rewards®
2025-08-07,12:00:00,CURSOR, AI POWERED IDE,CURSOR, AI POWERED IDE,21.78,Ultimate Rewards®
2025-08-07,12:00:00,Zelle payment to felix JPM99bij2gar,Zelle payment to felix JPM99bij2gar,64.00,Total Check
    """.format(csv_data=csv_data)
    try:
        print(f"Prompt: {prompt}")
        result = llm_generate_json(prompt)
        print(f"LLM result: {result}")
        if result.get('success'):
            return {'success': True, 'analysis': result.get('data', {}), 'error': None}
        return {'success': False, 'analysis': {}, 'error': result.get('error', 'Unknown error')}
    except Exception as e:
        return {'success': False, 'analysis': {}, 'error': str(e)}

# ==================== ROUTES ====================


@app.route('/api/plaid-token', methods=['POST'])
def set_plaid_token():
    """Store a Plaid access token or exchange a public token provided by the user."""
    if not fetch_and_save_transactions or not store_access_token or not create_plaid_client or not exchange_public_token:
        return jsonify({'error': 'Plaid helpers are unavailable on this server. Check your installation.'}), 500

    try:
        data = request.get_json() or {}
    except Exception:
        data = {}

    access_token = (data.get('access_token') or '').strip()
    public_token = (data.get('public_token') or '').strip()
    item_id = (data.get('item_id') or '').strip() or None

    if not access_token and not public_token:
        return jsonify({'error': 'Provide either an access token or a public token.'}), 400

    try:
        metadata = None
        if public_token:
            credentials = create_plaid_client()
            access_token, exchanged_item_id = exchange_public_token(
                credentials,
                public_token,
                write_to_store=False,
            )
            item_id = exchanged_item_id or item_id
            metadata = store_access_token(access_token, item_id=item_id, source='exchange')
        else:
            metadata = store_access_token(access_token, item_id=item_id, source='manual')

        response = {
            'success': True,
            'item_id': metadata.get('item_id'),
            'access_token': metadata.get('access_token'),
            'source': metadata.get('source'),
            'stored_at': metadata.get('stored_at'),
        }
        return jsonify(response)
    except PlaidConfigurationError as e:
        return jsonify({'error': f'Plaid configuration error: {e}'}), 400
    except PlaidAccessTokenError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.exception("Failed to store Plaid token")
        return jsonify({'error': f'Failed to store Plaid token: {e}'}), 500


@app.route('/api/link-token', methods=['POST'])
def create_link_token_api():
    """Create a fresh Plaid link token for launching Plaid Link."""
    try:
        pipeline = get_bank_pipeline()
    except Exception as exc:
        logging.exception("Unable to initialize Plaid pipeline")
        return jsonify({'error': str(exc)}), 500

    try:
        data = request.get_json() or {}
    except Exception:
        data = {}

    user_id = (data.get('user_id') or 'web_user').strip() or 'web_user'

    try:
        link_token = pipeline.create_link_token(user_id)
        return jsonify({'link_token': link_token, 'user_id': user_id})
    except PlaidConfigurationError as exc:
        return jsonify({'error': f'Plaid configuration error: {exc}'}), 400
    except Exception as exc:
        logging.exception("Failed to create Plaid link token")
        return jsonify({'error': f'Failed to create link token: {exc}'}), 500


@app.route('/')
def index():
    """Home page - Finance tip page"""
    return render_template('finance_tip.html')

@app.route('/tip')
def tip_page():
    """Finance tip page"""
    return render_template('finance_tip.html')


@app.route('/plaid-link')
def plaid_link_page():
    """Helper page to run Plaid Link and capture tokens."""
    return render_template('plaid_link.html')

@app.route('/api/finance-tip', methods=['POST'])
def get_finance_tip():
    """Generate personalized finance tip"""
    try:
        data = request.get_json() or {}
        fetch_fresh = data.get('fetch_fresh', False)
        lookback_days = int(data.get('lookback_days', 90))
        
        if fetch_fresh:
            # Fetch fresh data from Plaid API
            logging.info(f"Fetching fresh transactions from Plaid (last {lookback_days} days)...")
            fetch_result = fetch_fresh_transactions_from_plaid(days_back=lookback_days)
            if not fetch_result['success']:
                return jsonify({'error': f'Failed to fetch transactions: {fetch_result["error"]}'}), 500
            file_path = fetch_result['file_path']
            logging.info(f"Successfully fetched fresh transactions: {file_path}")
        else:
            # Use existing cached transaction file
            logging.info("Using cached transaction data...")
            fetch_result = fetch_latest_transactions()
            if not fetch_result['success']:
                return jsonify({'error': f'No cached transactions found. Try checking "Fetch fresh data" to download from your bank.'}), 404
            file_path = fetch_result['file_path']
            logging.info(f"Using cached file: {file_path}")
        
        parse_result = parse_transaction_file(file_path)
        if not parse_result['success']:
            return jsonify({'error': f'Failed to parse transactions: {parse_result["error"]}'}), 500
        
        transactions = parse_result['transactions']
        if not transactions:
            return jsonify({'error': 'No transactions found'}), 400
        
        cutoff = datetime.now() - timedelta(days=lookback_days)
        transactions = [t for t in transactions if t.get('datetime') and t['datetime'] >= cutoff]
        
        if not transactions:
            return jsonify({'error': 'No transactions within lookback window'}), 400
        
        tip_result = generate_finance_tip(transactions)
        
        return jsonify({
            'success': tip_result['success'],
            'file_path': file_path,
            'transaction_count': len(transactions),
            'lookback_days': lookback_days,
            'tip_analysis': tip_result.get('analysis', {}),
            'error': tip_result.get('error'),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': f'Finance tip analysis failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
