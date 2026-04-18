import json
import logging
import os
import re
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

from finance_tip import generate_finance_tip
from utils import parse_csv_transactions
try:
    from .transaction_insights import (
        build_monthly_spend_summary,
        build_transaction_summary,
        detect_outflow_sign,
        format_currency,
        humanize_month,
        is_internal_money_move,
        is_savings_allocation,
        is_vanguard_sell_inflow,
        is_withdrawal_transaction,
        merchant_text,
    )
except Exception:
    from transaction_insights import (  # type: ignore
        build_monthly_spend_summary,
        build_transaction_summary,
        detect_outflow_sign,
        format_currency,
        humanize_month,
        is_internal_money_move,
        is_savings_allocation,
        is_vanguard_sell_inflow,
        is_withdrawal_transaction,
        merchant_text,
    )

try:
    from .subscription_finder import identify_subscriptions
except Exception:
    try:
        from subscription_finder import identify_subscriptions
    except Exception as exc:
        identify_subscriptions = None  # type: ignore
        logging.exception("Subscription analysis unavailable: %s", exc)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 350 * 1024 * 1024  # 350MB max upload size

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# LLM client
try:
    from .llms import categorize_transactions as llm_categorize_transactions
    from .llms import AVAILABLE_OPENAI_MODELS
except Exception:
    try:
        from llms import categorize_transactions as llm_categorize_transactions
        from llms import AVAILABLE_OPENAI_MODELS
    except Exception:
        llm_categorize_transactions = None
        AVAILABLE_OPENAI_MODELS = ['gpt-5-mini-2025-08-07', 'gpt5', 'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo']

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure project .env files are loaded even when running from a different working dir (e.g., Replit).
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "src" / "web" / ".env")
load_dotenv()

parse_apple_health_export = None
generate_apple_health_analysis = None

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
except Exception as exc:
    logging.exception("Plaid helpers unavailable: %s", exc)

try:
    from src.api.bank_data_pipeline import BankDataPipeline
except Exception as exc:
    BankDataPipeline = None  # type: ignore
    logging.exception("Plaid pipeline unavailable: %s", exc)

try:
    from src.api.apple_health_parser import parse_apple_health_export
except Exception as exc:
    parse_apple_health_export = None  # type: ignore
    logging.exception("Apple Health parser unavailable: %s", exc)

try:
    from .apple_health_analysis import generate_apple_health_analysis
except Exception:
    try:
        from apple_health_analysis import generate_apple_health_analysis
    except Exception as exc:
        generate_apple_health_analysis = None  # type: ignore
        logging.exception("Apple Health analysis unavailable: %s", exc)



_bank_pipeline = None


def get_bank_pipeline():
    """Return a cached BankDataPipeline instance."""
    global _bank_pipeline
    if BankDataPipeline is None:
        raise RuntimeError("Plaid pipeline utilities are unavailable. Check your installation.")
    if _bank_pipeline is None:
        _bank_pipeline = BankDataPipeline()
    return _bank_pipeline


@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    """Return JSON for API routes and log the full exception."""
    logging.exception("Unhandled error on %s %s", request.method, request.path)
    if request.path.startswith('/api'):
        return jsonify({'error': f'Internal server error: {type(exc).__name__}', 'path': request.path}), 500
    return ("Internal server error. Check server logs for details.", 500)


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(exc):
    """Return a clear upload-size error for API routes."""
    if request.path.startswith('/api'):
        return jsonify({'error': 'Uploaded file is too large. Apple Health XML uploads are limited to 350MB.'}), 413
    return ('Uploaded file is too large. Apple Health XML uploads are limited to 350MB.', 413)


@app.after_request
def set_security_headers(response):
    """Set baseline HTTP security headers."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


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


def cleanup_transaction_file(file_path):
    """Delete a temporary transaction file if one was created for the request."""
    if not file_path or file_path == 'uploaded_csv':
        return
    try:
        Path(file_path).unlink(missing_ok=True)
        logging.info("Deleted transaction file after processing: %s", file_path)
    except Exception as exc:
        logging.warning("Failed to delete transaction file %s: %s", file_path, exc)


def load_transactions_from_request(data, default_lookback_days=90):
    """Load transactions from CSV upload, fresh Plaid fetch, or cached data."""
    try:
        lookback_days = int(data.get('lookback_days', default_lookback_days))
    except (TypeError, ValueError):
        return {
            'success': False,
            'status_code': 400,
            'error': 'Lookback days must be a whole number.',
            'transactions': [],
            'file_path': None,
            'lookback_days': default_lookback_days,
        }

    lookback_days = max(7, min(lookback_days, 365))
    fetch_fresh = bool(data.get('fetch_fresh', False))
    use_csv = bool(data.get('use_csv', False))
    csv_data = data.get('csv_data', '')
    file_path = None

    if use_csv:
        if not csv_data:
            return {
                'success': False,
                'status_code': 400,
                'error': 'Upload a CSV file before running the analysis.',
                'transactions': [],
                'file_path': None,
                'lookback_days': lookback_days,
            }

        logging.info("Using uploaded CSV data...")
        parse_result = parse_csv_transactions(csv_data)
        if not parse_result['success']:
            return {
                'success': False,
                'status_code': 400,
                'error': f'Failed to parse CSV: {parse_result["error"]}',
                'transactions': [],
                'file_path': None,
                'lookback_days': lookback_days,
            }
        file_path = 'uploaded_csv'
    elif fetch_fresh:
        logging.info("Fetching fresh transactions from Plaid (last %s days)...", lookback_days)
        fetch_result = fetch_fresh_transactions_from_plaid(days_back=lookback_days)
        if not fetch_result['success']:
            return {
                'success': False,
                'status_code': 500,
                'error': f'Failed to fetch transactions: {fetch_result["error"]}',
                'transactions': [],
                'file_path': None,
                'lookback_days': lookback_days,
            }
        file_path = fetch_result['file_path']
        logging.info("Successfully fetched fresh transactions: %s", file_path)
        parse_result = parse_transaction_file(file_path)
        if not parse_result['success']:
            return {
                'success': False,
                'status_code': 500,
                'error': f'Failed to parse transactions: {parse_result["error"]}',
                'transactions': [],
                'file_path': file_path,
                'lookback_days': lookback_days,
            }
    else:
        logging.info("Using cached transaction data...")
        fetch_result = fetch_latest_transactions()
        if not fetch_result['success']:
            return {
                'success': False,
                'status_code': 404,
                'error': 'No cached transactions found. Try checking "Fetch fresh data" to download from your bank.',
                'transactions': [],
                'file_path': None,
                'lookback_days': lookback_days,
            }
        file_path = fetch_result['file_path']
        logging.info("Using cached file: %s", file_path)
        parse_result = parse_transaction_file(file_path)
        if not parse_result['success']:
            return {
                'success': False,
                'status_code': 500,
                'error': f'Failed to parse transactions: {parse_result["error"]}',
                'transactions': [],
                'file_path': file_path,
                'lookback_days': lookback_days,
            }

    transactions = parse_result['transactions']
    if not transactions:
        return {
            'success': False,
            'status_code': 400,
            'error': 'No transactions found.',
            'transactions': [],
            'file_path': file_path,
            'lookback_days': lookback_days,
        }

    cutoff = datetime.now() - timedelta(days=lookback_days)
    filtered_transactions = [
        transaction for transaction in transactions
        if transaction.get('datetime') and transaction['datetime'] >= cutoff
    ]

    if not filtered_transactions:
        return {
            'success': False,
            'status_code': 400,
            'error': 'No transactions within lookback window.',
            'transactions': [],
            'file_path': file_path,
            'lookback_days': lookback_days,
        }

    filtered_transactions.sort(key=lambda item: item.get('datetime', datetime.min), reverse=True)
    return {
        'success': True,
        'status_code': 200,
        'error': None,
        'transactions': filtered_transactions,
        'file_path': file_path,
        'lookback_days': lookback_days,
    }


def get_request_json():
    """Return JSON request payload or an empty dictionary for invalid JSON."""
    try:
        return request.get_json() or {}
    except Exception:
        return {}


def load_transactions_or_error(data, default_lookback_days=90):
    """Load transactions and return either load_result or a Flask error response."""
    load_result = load_transactions_from_request(data, default_lookback_days=default_lookback_days)
    if load_result['success']:
        return load_result, None
    return None, (jsonify({'error': load_result['error']}), load_result['status_code'])


# ==================== ROUTES ====================


@app.route('/api/plaid-token', methods=['POST'])
def set_plaid_token():
    """Store a Plaid access token or exchange a public token provided by the user."""
    if not fetch_and_save_transactions or not store_access_token or not create_plaid_client or not exchange_public_token:
        return jsonify({'error': 'Plaid helpers are unavailable on this server. Check your installation.'}), 500

    data = get_request_json()

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

    data = get_request_json()

    user_id = (data.get('user_id') or '').strip()
    if not user_id:
        user_id = f"web_user_{uuid.uuid4().hex}"

    try:
        link_token = pipeline.create_link_token(user_id)
        return jsonify({'link_token': link_token, 'user_id': user_id})
    except PlaidConfigurationError as exc:
        return jsonify({'error': f'Plaid configuration error: {exc}'}), 400
    except Exception as exc:
        logging.exception("Failed to create Plaid link token")
        return jsonify({'error': f'Failed to create link token: {exc}'}), 500


@app.route('/api/models', methods=['GET'])
def get_available_models():
    """Return list of available OpenAI models"""
    return jsonify({
        'models': AVAILABLE_OPENAI_MODELS,
        'default': 'gpt-5-mini'
    })


@app.route('/')
def index():
    """Home page - Finance tip page"""
    return render_template('finance_tip.html')

@app.route('/tip')
def tip_page():
    """Finance tip page"""
    return render_template('finance_tip.html')


@app.route('/subscriptions')
def subscriptions_page():
    """Subscription detection page."""
    return render_template('subscriptions.html')


@app.route('/monthly-spend')
def monthly_spend_page():
    """Monthly expenditure breakdown page."""
    return render_template('monthly_spend.html')


@app.route('/health')
def apple_health_page():
    """Apple Health upload and analysis page."""
    return render_template('apple_health.html')


@app.route('/plaid-link')
def plaid_link_page():
    """Helper page to run Plaid Link and capture tokens."""
    return render_template('plaid_link.html')


@app.route('/api/apple-health/analyze', methods=['POST'])
def analyze_apple_health_api():
    """Parse an Apple Health export.xml file and analyze the summary with OpenAI."""
    if not parse_apple_health_export or not generate_apple_health_analysis:
        return jsonify({'error': 'Apple Health analysis is unavailable on this server.'}), 500

    uploaded_file = request.files.get('apple_health_file')
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({'error': 'Upload an Apple Health export.xml file.'}), 400

    if not uploaded_file.filename.lower().endswith('.xml'):
        return jsonify({'error': 'Apple Health uploads must be XML files.'}), 400

    openai_api_key = (request.form.get('openai_api_key') or '').strip()
    if not openai_api_key:
        return jsonify({'error': 'OpenAI API key is required for Apple Health analysis.'}), 400

    model = (request.form.get('model') or 'gpt-5-mini').strip() or 'gpt-5-mini'
    lookback_raw = request.form.get('lookback_days', '90')
    try:
        lookback_days = int(lookback_raw)
    except (TypeError, ValueError):
        return jsonify({'error': 'Lookback days must be a whole number.'}), 400

    lookback_days = max(7, min(lookback_days, 365))

    logging.info(
        "Parsing Apple Health upload %s with lookback=%s days",
        uploaded_file.filename,
        lookback_days,
    )
    parse_result = parse_apple_health_export(uploaded_file.stream, lookback_days=lookback_days)
    if not parse_result.get('success'):
        return jsonify({'error': parse_result.get('error', 'Failed to parse Apple Health export.')}), 400

    health_summary = parse_result.get('summary', {})
    analysis_result = generate_apple_health_analysis(
        health_summary,
        openai_api_key=openai_api_key,
        model=model,
    )
    if not analysis_result.get('success'):
        return jsonify({'error': analysis_result.get('error', 'Apple Health analysis failed.')}), 500

    return jsonify({
        'success': True,
        'file_name': uploaded_file.filename,
        'lookback_days': lookback_days,
        'model': model,
        'parsed_summary': health_summary,
        'analysis': analysis_result.get('analysis', {}),
        'timestamp': datetime.now().isoformat(),
    })

@app.route('/api/finance-tip', methods=['POST'])
def get_finance_tip():
    """Generate personalized finance tip"""
    file_path = None
    try:
        data = get_request_json()
        openai_api_key = data.get('openai_api_key', '')
        use_openai = data.get('use_openai', False)
        model = data.get('model', '')
        load_result, error_response = load_transactions_or_error(data)
        if error_response:
            return error_response

        file_path = load_result['file_path']
        lookback_days = load_result['lookback_days']
        transactions = load_result['transactions']
        tip_result = generate_finance_tip(transactions, openai_api_key=openai_api_key, use_openai=use_openai, model=model)
        transaction_summary = build_transaction_summary(transactions, lookback_days)
        response_success = tip_result['success'] or bool(transaction_summary)

        return jsonify({
            'success': response_success,
            'transaction_count': len(transactions),
            'lookback_days': lookback_days,
            'tip_analysis': tip_result.get('analysis', {}),
            'transaction_summary': transaction_summary,
            'error': tip_result.get('error'),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': f'Finance tip analysis failed: {str(e)}'}), 500
    finally:
        cleanup_transaction_file(file_path)


# ==================== EMAIL SIGNUP ====================

# File to store email signups
EMAIL_SIGNUPS_FILE = Path(__file__).parent / 'email_signups.json'
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def load_email_signups():
    """Load existing email signups from file"""
    if EMAIL_SIGNUPS_FILE.exists():
        try:
            with open(EMAIL_SIGNUPS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_email_signup(email, name=None):
    """Save a new email signup"""
    signups = load_email_signups()
    
    # Check if email already exists
    existing_emails = [s.get('email', '').lower() for s in signups]
    if email.lower() in existing_emails:
        return {'success': False, 'error': 'Email already registered'}
    
    signup = {
        'email': email,
        'name': name,
        'signed_up_at': datetime.now().isoformat(),
        'source': 'web_app'
    }
    signups.append(signup)
    
    try:
        with open(EMAIL_SIGNUPS_FILE, 'w') as f:
            json.dump(signups, f, indent=2)
        return {'success': True}
    except IOError as e:
        return {'success': False, 'error': f'Failed to save: {str(e)}'}


@app.route('/api/email-signup', methods=['POST'])
def email_signup():
    """Handle email signup for paid hosted version waitlist"""
    data = get_request_json()
    
    email = (data.get('email') or '').strip().lower()
    name = (data.get('name') or '').strip() or None
    
    # Validate email
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    if not EMAIL_PATTERN.match(email):
        return jsonify({'error': 'Please enter a valid email address'}), 400
    
    result = save_email_signup(email, name)
    
    if result['success']:
        logging.info(f"New email signup: {email}")
        return jsonify({
            'success': True,
            'message': "Thanks for signing up! We'll notify you when our hosted service launches."
        })
    else:
        if 'already registered' in result.get('error', ''):
            return jsonify({
                'success': True,
                'message': "You're already on the list! We'll be in touch soon."
            })
        return jsonify({'error': result.get('error', 'Signup failed')}), 500


@app.route('/api/monthly-spend', methods=['POST'])
def monthly_spend_api():
    """Return month-level expenditure with a category breakdown and savings bucket."""
    if not llm_categorize_transactions:
        return jsonify({'error': 'LLM categorization not available'}), 500

    file_path = None
    try:
        data = get_request_json()
        requested_month = str(data.get('month') or '').strip()
        if requested_month and not re.fullmatch(r'\d{4}-\d{2}', requested_month):
            return jsonify({'error': 'Month must use YYYY-MM format.'}), 400

        openai_api_key = data.get('openai_api_key', '')
        use_openai = data.get('use_openai', False)
        model = data.get('model', '')
        load_result, error_response = load_transactions_or_error(data, default_lookback_days=180)
        if error_response:
            return error_response

        file_path = load_result['file_path']
        lookback_days = load_result['lookback_days']
        transactions = load_result['transactions']

        ordered = sorted(
            [trx for trx in transactions if trx.get('datetime')],
            key=lambda trx: trx['datetime'],
        )
        if not ordered:
            return jsonify({'error': 'No valid transactions with dates were found.'}), 400

        outflow_sign = detect_outflow_sign(ordered)
        outflows = [trx for trx in ordered if float(trx.get('amount') or 0) * outflow_sign > 0]
        if not outflows:
            return jsonify({'error': 'No spend-like transactions were found in the selected window.'}), 400

        month_outflows = defaultdict(list)
        for trx in outflows:
            month_outflows[trx['datetime'].strftime('%Y-%m')].append(trx)

        available_month_keys = sorted(month_outflows.keys(), reverse=True)
        if not available_month_keys:
            return jsonify({'error': 'No monthly spending data found.'}), 400

        selected_month = requested_month if requested_month in month_outflows else available_month_keys[0]
        selected_month_transactions = [
            trx for trx in ordered
            if trx['datetime'].strftime('%Y-%m') == selected_month
        ]
        selected_month_outflows = [
            trx for trx in selected_month_transactions
            if float(trx.get('amount') or 0) * outflow_sign > 0
        ]
        savings_transactions = [trx for trx in selected_month_outflows if is_savings_allocation(trx)]
        vanguard_sell_inflow_transactions = [
            trx for trx in selected_month_transactions
            if is_vanguard_sell_inflow(trx, outflow_sign)
        ]

        spend_transactions = [
            trx for trx in selected_month_outflows
            if not is_internal_money_move(trx) and not is_savings_allocation(trx)
        ]
        if not spend_transactions:
            spend_transactions = [trx for trx in selected_month_outflows if not is_savings_allocation(trx)]

        categorized_transactions = []
        if spend_transactions:
            categorization_result = llm_categorize_transactions(
                spend_transactions,
                model=model,
                openai_api_key=openai_api_key,
                use_openai=use_openai,
            )
            if not categorization_result.get('success'):
                return jsonify({'error': f'Categorization failed: {categorization_result.get("error")}'}), 500
            categorized_transactions = categorization_result.get('categorized_transactions', [])

        categorized_by_transaction_id = {}
        for idx, categorized in enumerate(categorized_transactions):
            if idx < len(spend_transactions):
                categorized_by_transaction_id[id(spend_transactions[idx])] = categorized

        debug_transactions = []
        for trx in sorted(selected_month_transactions, key=lambda item: item.get('datetime', datetime.min), reverse=True):
            raw_amount = float(trx.get('amount') or 0)
            is_outflow = raw_amount * outflow_sign > 0
            is_savings = is_savings_allocation(trx)
            is_internal = is_internal_money_move(trx)
            is_withdrawal = is_withdrawal_transaction(trx)
            is_vanguard_sell = is_vanguard_sell_inflow(trx, outflow_sign)

            if is_vanguard_sell:
                bucket = 'vanguard_sell_inflow'
                bucket_reason = 'savings_offset'
            elif is_outflow and is_savings:
                bucket = 'savings'
                bucket_reason = 'withdrawal' if is_withdrawal else 'savings_destination'
            elif is_outflow and is_internal:
                bucket = 'internal_move'
                bucket_reason = 'internal_transfer_or_payment'
            elif is_outflow:
                bucket = 'expenditure'
                bucket_reason = 'categorized_spending'
            else:
                bucket = 'inflow'
                bucket_reason = 'inflow_or_credit'

            categorized = categorized_by_transaction_id.get(id(trx))
            category = ''
            subcategory = ''
            confidence = ''
            if bucket == 'expenditure':
                if categorized:
                    category = categorized.get('category') or 'Other'
                    subcategory = categorized.get('subcategory') or ''
                    confidence = categorized.get('confidence') or 'medium'
                else:
                    category = 'Uncategorized'
                    subcategory = 'Not analyzed (categorization limit)'
                    confidence = 'n/a'

            debug_transactions.append(
                {
                    'date': trx.get('date'),
                    'merchant': merchant_text(trx),
                    'account_name': trx.get('account_name') or trx.get('account') or '',
                    'raw_amount': round(raw_amount, 2),
                    'amount': round(abs(raw_amount), 2),
                    'amount_display': format_currency(abs(raw_amount)),
                    'bucket': bucket,
                    'bucket_reason': bucket_reason,
                    'category': category,
                    'subcategory': subcategory,
                    'confidence': confidence,
                    'is_savings': is_savings,
                    'is_internal_move': is_internal,
                    'is_withdrawal': is_withdrawal,
                    'is_vanguard_sell_inflow': is_vanguard_sell,
                }
            )

        summary = build_monthly_spend_summary(
            categorized_transactions,
            savings_transactions,
            vanguard_sell_inflow_transactions=vanguard_sell_inflow_transactions,
        )
        savings_offset_transactions = [
            {
                'date': trx.get('date'),
                'merchant': merchant_text(trx),
                'amount': round(abs(float(trx.get('amount') or 0)), 2),
                'display': format_currency(abs(float(trx.get('amount') or 0))),
            }
            for trx in sorted(vanguard_sell_inflow_transactions, key=lambda item: item.get('datetime', datetime.min), reverse=True)
        ]
        available_months = [
            {
                'key': month_key,
                'label': humanize_month(month_key),
                'transaction_count': len(month_outflows[month_key]),
            }
            for month_key in available_month_keys
        ]

        return jsonify({
            'success': True,
            'lookback_days': lookback_days,
            'selected_month': selected_month,
            'selected_month_label': humanize_month(selected_month),
            'available_months': available_months,
            'source_transaction_count': len(transactions),
            'month_transaction_count': len(selected_month_transactions),
            'month_outflow_count': len(selected_month_outflows),
            'savings_transaction_count': len(savings_transactions),
            'vanguard_sell_inflow_count': len(vanguard_sell_inflow_transactions),
            'spend_transaction_count': len(spend_transactions),
            'analyzed_transaction_count': len(categorized_transactions),
            'analysis_limited': len(spend_transactions) > len(categorized_transactions),
            'total_expenditure': summary['total_expenditure'],
            'total_savings': summary['total_savings'],
            'total_savings_gross': summary['total_savings_gross'],
            'vanguard_sell_inflows_offset': summary['vanguard_sell_inflows_offset'],
            'category_count': summary['category_count'],
            'top_category': summary['top_category'],
            'category_breakdown': summary['category_breakdown'],
            'top_merchants': summary['top_merchants'],
            'savings_offset_transactions': savings_offset_transactions,
            'transactions': debug_transactions,
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as exc:
        logging.exception("Monthly spend analysis failed")
        return jsonify({'error': f'Monthly spend analysis failed: {exc}'}), 500
    finally:
        cleanup_transaction_file(file_path)


@app.route('/api/subscriptions', methods=['POST'])
def identify_subscriptions_api():
    """Identify recurring subscription-like charges from transaction history."""
    if not identify_subscriptions:
        return jsonify({'error': 'Subscription analysis is unavailable on this server.'}), 500

    file_path = None
    try:
        data = get_request_json()
        load_result, error_response = load_transactions_or_error(data, default_lookback_days=365)
        if error_response:
            return error_response

        file_path = load_result['file_path']
        lookback_days = load_result['lookback_days']
        transactions = load_result['transactions']

        analysis_result = identify_subscriptions(transactions)
        if not analysis_result.get('success'):
            return jsonify({'error': analysis_result.get('error', 'Subscription analysis failed.')}), 500

        return jsonify({
            'success': True,
            'transaction_count': len(transactions),
            'lookback_days': lookback_days,
            'subscriptions': analysis_result.get('subscriptions', []),
            'summary': analysis_result.get('summary', {}),
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as exc:
        logging.exception("Subscription analysis failed")
        return jsonify({'error': f'Subscription analysis failed: {exc}'}), 500
    finally:
        cleanup_transaction_file(file_path)


if __name__ == '__main__':
    debug_enabled = (os.getenv('FLASK_DEBUG', '0').strip() == '1')
    app.run(debug=debug_enabled, host='0.0.0.0', port=5000)
