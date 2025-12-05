import csv
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from io import StringIO

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# LLM client
try:
    from .llms import generate_json as llm_generate_json
    from .llms import categorize_transactions as llm_categorize_transactions
    from .llms import AVAILABLE_OPENAI_MODELS
except Exception:
    try:
        from llms import generate_json as llm_generate_json
        from llms import categorize_transactions as llm_categorize_transactions
        from llms import AVAILABLE_OPENAI_MODELS
    except Exception:
        llm_generate_json = None
        llm_categorize_transactions = None
        AVAILABLE_OPENAI_MODELS = ['gpt5', 'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo']

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
    logging.info("Successfully imported BankDataPipeline from src.api.bank_data_pipeline")
except Exception as e:
    logging.warning(f"Failed to import from src.api.bank_data_pipeline: {e}")
    try:
        from ..api.bank_data_pipeline import BankDataPipeline  # type: ignore
        logging.info("Successfully imported BankDataPipeline from ..api.bank_data_pipeline")
    except Exception as e2:
        logging.warning(f"Failed to import from ..api.bank_data_pipeline: {e2}")
        try:
            from api.bank_data_pipeline import BankDataPipeline  # type: ignore
            logging.info("Successfully imported BankDataPipeline from api.bank_data_pipeline")
        except Exception as e3:
            logging.warning(f"Failed to import from api.bank_data_pipeline: {e3}")
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


def parse_csv_transactions(csv_content):
    """Parse CSV content into structured transaction data
    
    Expected CSV formats (case-insensitive headers):
    - date, name/merchant/description, amount [, account]
    - date, time, name, description, amount [, account]
    
    Date formats supported: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, etc.
    Amount formats: with or without $ sign, negative or positive
    """
    transactions = []
    try:
        # Use StringIO to read CSV content
        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        if not reader.fieldnames:
            return {'success': False, 'transactions': [], 'count': 0, 'error': 'CSV file is empty or has no headers'}
        
        # Normalize header names (lowercase, strip whitespace)
        headers = {h.lower().strip(): h for h in reader.fieldnames if h}
        
        # Find required columns (case-insensitive)
        date_col = None
        name_col = None
        amount_col = None
        account_col = None
        time_col = None
        
        for col in headers.keys():
            if 'date' in col:
                date_col = headers[col]
            elif any(term in col for term in ['name', 'merchant', 'description', 'vendor']):
                if not name_col:  # Use first match
                    name_col = headers[col]
            elif 'amount' in col or 'total' in col:
                amount_col = headers[col]
            elif 'account' in col:
                account_col = headers[col]
            elif 'time' in col:
                time_col = headers[col]
        
        if not date_col or not amount_col:
            return {
                'success': False, 
                'transactions': [], 
                'count': 0, 
                'error': 'CSV must have "date" and "amount" columns'
            }
        
        if not name_col:
            # Try to find any text column for name
            for col in headers.keys():
                if col not in ['date', 'amount', 'account', 'time']:
                    name_col = headers[col]
                    break
        
        if not name_col:
            return {
                'success': False, 
                'transactions': [], 
                'count': 0, 
                'error': 'CSV must have a column for transaction name/merchant/description'
            }
        
        # Parse each row
        for i, row in enumerate(reader, 1):
            try:
                date_str = row.get(date_col, '').strip()
                name = row.get(name_col, '').strip() or 'Unknown'
                amount_str = row.get(amount_col, '').strip()
                account_name = row.get(account_col, '').strip() if account_col else None
                time_str = row.get(time_col, '').strip() if time_col else '12:00:00'
                
                if not date_str or not amount_str:
                    continue
                
                # Parse date - try multiple formats
                date_obj = None
                date_formats = [
                    '%Y-%m-%d',
                    '%m/%d/%Y',
                    '%d/%m/%Y',
                    '%Y/%m/%d',
                    '%m-%d-%Y',
                    '%d-%m-%Y',
                    '%b %d, %Y',
                    '%B %d, %Y',
                    '%d %b %Y',
                    '%d %B %Y',
                ]
                
                for fmt in date_formats:
                    try:
                        date_obj = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if not date_obj:
                    logging.warning(f"Could not parse date '{date_str}' in row {i}")
                    continue
                
                # Parse amount - remove $ and commas, handle negative
                amount_str = amount_str.replace('$', '').replace(',', '').strip()
                
                # Handle parentheses for negative amounts (accounting format)
                if amount_str.startswith('(') and amount_str.endswith(')'):
                    amount_str = '-' + amount_str[1:-1]
                
                try:
                    amount = float(amount_str)
                except ValueError:
                    logging.warning(f"Could not parse amount '{amount_str}' in row {i}")
                    continue
                
                transactions.append({
                    'id': len(transactions) + 1,
                    'date': date_obj.strftime('%Y-%m-%d'),
                    'datetime': date_obj,
                    'name': name,
                    'merchant': name,
                    'description': name,
                    'amount': amount,
                    'account_name': account_name,
                    'time': time_str
                })
            except Exception as e:
                logging.warning(f"Error parsing row {i}: {e}")
                continue
        
        if not transactions:
            return {
                'success': False,
                'transactions': [],
                'count': 0,
                'error': 'No valid transactions found in CSV. Check date and amount formats.'
            }
        
        return {'success': True, 'transactions': transactions, 'count': len(transactions), 'error': None}
    except Exception as e:
        logging.exception("Error parsing CSV")
        return {'success': False, 'transactions': [], 'count': 0, 'error': f'CSV parsing error: {str(e)}'}

def generate_finance_tip(transactions, openai_api_key=None, use_openai=False, model=None):
    """Generate personalized finance tip using LLM"""
    if not llm_generate_json:
        return {'success': False, 'analysis': {}, 'error': 'LLM not available'}
    
    # Limit transactions to prevent timeout
    max_transactions = 200
    if len(transactions) > max_transactions:
        transactions = transactions[:max_transactions]
    
    csv_data = "date,time,name,description,amount,account\n"
    for trx in transactions:
        csv_data += f"{trx['date']},{trx.get('time','')},{trx.get('merchant','')},{trx.get('description','')},{trx.get('amount',0)},{trx.get('account','Unknown')}\n"
    # print(f"CSV data: {csv_data}")

    prompt = f"""You are a personal finance coach. Analyze these transactions and provide ONE specific actionable tip.
You must also compare spending across months if the data spans more than one month.

Transaction Data (CSV):
{csv_data}

  Return ONLY valid JSON in this exact format:

{{
  "tip": {{
    "title": "Specific tip title based on the data",
    "advice": "Detailed explanation citing specific transactions with dates and amounts, including month-over-month comparison when available",
    "potential_savings": "$X-$Y/year based on your analysis",
    "actionable_steps": [
      "Step 1: Specific action with timeframe",
      "Step 2: Another specific action",
      "Step 3: Follow-up action"
    ]
  }},
  "spending_insights": {{
    "frequent_merchants": ["merchant1", "merchant2", "merchant3"],
    "spending_trend": "Brief trend observation, including month-over-month comparison if applicable"
  }}
}}

Expanded Analysis Rules (including month-over-month support)

    1. Identify ONE clear actionable pattern:
        * repeated merchants
        * subscription/recurring charges
        * fees
        * large purchases
        * category spikes
        * meaningful changes between months

    2. When data spans multiple months, calculate at least one month-over-month trend, such as:
        * category increase/decrease
        * recurring merchant variance
        * total monthly spend shift
        * volatility or irregular spikes

    3. Cite specific transactions with merchant names, dates (YYYY-MM-DD), and amounts.

    4. Calculate realistic savings projections based on the identified issue.

    5. Provide 2–3 specific, practical steps with timeframes.

    6. If no strong pattern exists, focus on the largest category or month with the biggest spending jump.

    7. Stay strictly grounded in the provided data—do not invent charges, categories, or memberships."""
    try:
        # print(f"Prompt: {prompt}")
        result = llm_generate_json(prompt, model=model, openai_api_key=openai_api_key, use_openai=use_openai)
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


@app.route('/api/models', methods=['GET'])
def get_available_models():
    """Return list of available OpenAI models"""
    return jsonify({
        'models': AVAILABLE_OPENAI_MODELS,
        'default': 'gpt5'
    })


@app.route('/')
def index():
    """Home page - Finance tip page"""
    return render_template('finance_tip.html')

@app.route('/tip')
def tip_page():
    """Finance tip page"""
    return render_template('finance_tip.html')


@app.route('/categorize')
def categorize_page():
    """Transaction categorization page"""
    return render_template('categorize_transactions.html')


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
        use_csv = data.get('use_csv', False)
        csv_data = data.get('csv_data', '')
        openai_api_key = data.get('openai_api_key', '')
        use_openai = data.get('use_openai', False)
        model = data.get('model', '')
        
        if use_csv and csv_data:
            # Parse CSV data directly
            logging.info("Using uploaded CSV data...")
            parse_result = parse_csv_transactions(csv_data)
            if not parse_result['success']:
                return jsonify({'error': f'Failed to parse CSV: {parse_result["error"]}'}), 400
            file_path = 'uploaded_csv'
        elif fetch_fresh:
            # Fetch fresh data from Plaid API
            logging.info(f"Fetching fresh transactions from Plaid (last {lookback_days} days)...")
            fetch_result = fetch_fresh_transactions_from_plaid(days_back=lookback_days)
            if not fetch_result['success']:
                return jsonify({'error': f'Failed to fetch transactions: {fetch_result["error"]}'}), 500
            file_path = fetch_result['file_path']
            logging.info(f"Successfully fetched fresh transactions: {file_path}")
            parse_result = parse_transaction_file(file_path)
            if not parse_result['success']:
                return jsonify({'error': f'Failed to parse transactions: {parse_result["error"]}'}), 500
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
        
        tip_result = generate_finance_tip(transactions, openai_api_key=openai_api_key, use_openai=use_openai, model=model)
        
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


@app.route('/api/categorize-transactions', methods=['POST'])
def categorize_transactions_api():
    """Categorize transactions using LLM"""
    if not llm_categorize_transactions:
        return jsonify({'error': 'LLM categorization not available'}), 500
    
    try:
        data = request.get_json() or {}
        fetch_fresh = data.get('fetch_fresh', False)
        lookback_days = int(data.get('lookback_days', 90))
        use_csv = data.get('use_csv', False)
        csv_data = data.get('csv_data', '')
        openai_api_key = data.get('openai_api_key', '')
        use_openai = data.get('use_openai', False)
        model = data.get('model', '')
        
        if use_csv and csv_data:
            # Parse CSV data directly
            logging.info("Using uploaded CSV data...")
            parse_result = parse_csv_transactions(csv_data)
            if not parse_result['success']:
                return jsonify({'error': f'Failed to parse CSV: {parse_result["error"]}'}), 400
            file_path = 'uploaded_csv'
        elif fetch_fresh:
            logging.info(f"Fetching fresh transactions from Plaid (last {lookback_days} days)...")
            fetch_result = fetch_fresh_transactions_from_plaid(days_back=lookback_days)
            if not fetch_result['success']:
                return jsonify({'error': f'Failed to fetch transactions: {fetch_result["error"]}'}), 500
            file_path = fetch_result['file_path']
            logging.info(f"Successfully fetched fresh transactions: {file_path}")
            parse_result = parse_transaction_file(file_path)
            if not parse_result['success']:
                return jsonify({'error': f'Failed to parse transactions: {parse_result["error"]}'}), 500
        else:
            logging.info("Using cached transaction data...")
            fetch_result = fetch_latest_transactions()
            if not fetch_result['success']:
                return jsonify({'error': 'No cached transactions found. Try checking "Fetch fresh data" to download from your bank.'}), 404
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
        
        # Sort by date descending (most recent first)
        transactions.sort(key=lambda x: x.get('datetime', datetime.min), reverse=True)
        
        logging.info(f"Categorizing {len(transactions)} transactions...")
        categorization_result = llm_categorize_transactions(
            transactions,
            model=model,
            openai_api_key=openai_api_key,
            use_openai=use_openai
        )
        
        if not categorization_result.get('success'):
            return jsonify({
                'error': f'Categorization failed: {categorization_result.get("error")}'
            }), 500
        
        categorized_transactions = categorization_result.get('categorized_transactions', [])
        
        # Calculate category summaries
        category_summary = {}
        for trx in categorized_transactions:
            category = trx.get('category', 'Other')
            amount = trx.get('amount', 0)
            if category not in category_summary:
                category_summary[category] = {'count': 0, 'total': 0}
            category_summary[category]['count'] += 1
            category_summary[category]['total'] += amount
        
        return jsonify({
            'success': True,
            'file_path': file_path,
            'transaction_count': len(categorized_transactions),
            'lookback_days': lookback_days,
            'transactions': categorized_transactions,
            'category_summary': category_summary,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logging.exception("Transaction categorization failed")
        return jsonify({'error': f'Transaction categorization failed: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
