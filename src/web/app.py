from flask import Flask, render_template, jsonify, request, send_from_directory
import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
import os
import tempfile
import PyPDF2
from PIL import Image
import pytesseract
import openai
from werkzeug.utils import secure_filename
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Configure OpenAI (you'll need to set your API key)
# openai.api_key = os.getenv('OPENAI_API_KEY')  # Uncomment and set your API key

# Ollama configuration
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1')

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error extracting PDF text: {str(e)}"

def extract_text_from_image(file_path):
    """Extract text from image using OCR"""
    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        return f"Error extracting image text: {str(e)}"

def analyze_mortgage_with_ai(text):
    """Analyze mortgage document text using AI with comprehensive legal perspective"""
    
    # Comprehensive mortgage analysis prompt
    analysis_prompt = f"""
Role & Perspective
You are an experienced real-estate attorney and consumer-rights advocate. Your goal is to give a concise, plain-English assessment of the mortgage contract provided below.

Document Text to Analyze:
{text}

Tasks - Please provide your analysis in the following exact format with numbered headings:

1. Executive Summary (≤ 200 words) – Summarize the loan's purpose, parties, and any immediately obvious risks or benefits.

2. Key Financial Terms – List, in a table format, the interest rate type (fixed/ARM), APR, payment frequency, amortization length, points/discount fees, escrow requirements, and any mortgage-insurance triggers (PMI/MIP).

3. Fees & Penalties – Identify: late-payment fees, prepayment penalties, balloon payments, servicing or "junk" fees, rate-adjustment caps or floors (for ARMs).

4. Borrower Obligations & Covenants – Explain escrow, insurance, maintenance, occupancy requirements, due-on-sale clauses, and any cross-default provisions.

5. Lender Rights & Remedies – Describe default definition, acceleration, foreclosure timeline, deficiency-judgment language, forced-placement insurance, and dispute-resolution (arbitration/venue).

6. Risk / Red-Flag Checklist – Bullet-point any terms that are unusually costly, ambiguous, or out of step with FHA/Fannie-Mae norms. Flag anything that could become a surprise expense.

7. Comparison to Market Norms (Optional) – If enough data appear, state whether rate, APR, or fees are above/below current New Jersey–area averages for a borrower with similar credit (cite date/source if known).

8. Questions for the Borrower to Ask – List any clarifications or concessions the borrower should request before signing.

9. References – Cite clause numbers / page numbers for every point you raise so the borrower can verify your reading.

Style & Output Format:
- Use numbered headings exactly as above
- Write for a non-lawyer audience—avoid jargon or define it briefly in parentheses
- Keep each bullet under ~40 words
- Do not give legal advice; frame findings as educational insights
- Provide specific references to document sections where possible
"""
    
    # Use Ollama for comprehensive analysis if sufficient text
    if len(text.strip()) > 50:
        try:
            # Add system context to the prompt for Ollama
            full_prompt = f"""You are an experienced real-estate attorney and consumer-rights advocate specializing in mortgage document analysis.

{analysis_prompt}"""
            
            # Use Ollama for comprehensive analysis
            result = call_ollama_api(full_prompt)
            
            if result['success']:
                ai_analysis = result['response']
                
                # Parse the structured response into our expected format
                analysis_result = parse_structured_analysis(ai_analysis)
                analysis_result['full_analysis'] = ai_analysis
                analysis_result['analysis_method'] = f'Ollama ({OLLAMA_MODEL})'
                
                return analysis_result
            else:
                print(f"Ollama analysis failed: {result['error']}")
                # Fall back to rule-based analysis
                return perform_rule_based_analysis(text)
            
        except Exception as e:
            print(f"Ollama analysis failed: {e}")
            # Fall back to rule-based analysis
            return perform_rule_based_analysis(text)
    else:
        # Use rule-based analysis if insufficient text
        return perform_rule_based_analysis(text)

def parse_structured_analysis(ai_analysis):
    """Parse the AI's structured analysis into our expected JSON format"""
    
    # Split the analysis into sections based on numbered headings
    sections = {}
    current_section = None
    current_content = []
    
    lines = ai_analysis.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check for numbered section headers
        if line.startswith('1.') and 'Executive Summary' in line:
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            current_section = 'executive_summary'
            current_content = []
        elif line.startswith('2.') and 'Key Financial Terms' in line:
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            current_section = 'key_financial_terms'
            current_content = []
        elif line.startswith('3.') and 'Fees & Penalties' in line:
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            current_section = 'fees_penalties'
            current_content = []
        elif line.startswith('4.') and 'Borrower Obligations' in line:
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            current_section = 'borrower_obligations'
            current_content = []
        elif line.startswith('5.') and 'Lender Rights' in line:
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            current_section = 'lender_rights'
            current_content = []
        elif line.startswith('6.') and 'Risk' in line and 'Red-Flag' in line:
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            current_section = 'risk_red_flags'
            current_content = []
        elif line.startswith('7.') and 'Comparison to Market' in line:
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            current_section = 'market_comparison'
            current_content = []
        elif line.startswith('8.') and 'Questions for the Borrower' in line:
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            current_section = 'borrower_questions'
            current_content = []
        elif line.startswith('9.') and 'References' in line:
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            current_section = 'references'
            current_content = []
        else:
            # Add content to current section
            if current_section and line:
                current_content.append(line)
    
    # Add the last section
    if current_section:
        sections[current_section] = '\n'.join(current_content)
    
    # Map to our expected format
    return {
        'executive_summary': sections.get('executive_summary', 'No executive summary available'),
        'key_financial_terms': sections.get('key_financial_terms', 'No financial terms extracted'),
        'fees_penalties': sections.get('fees_penalties', 'No fees and penalties information found'),
        'borrower_obligations': sections.get('borrower_obligations', 'No borrower obligations identified'),
        'lender_rights': sections.get('lender_rights', 'No lender rights information found'),
        'risk_red_flags': sections.get('risk_red_flags', 'No risk flags identified'),
        'market_comparison': sections.get('market_comparison', 'No market comparison available'),
        'borrower_questions': sections.get('borrower_questions', 'No specific questions generated'),
        'references': sections.get('references', 'No references available'),
        
        # Legacy fields for backwards compatibility
        'loan_details': sections.get('key_financial_terms', 'See Key Financial Terms section'),
        'interest_rate_info': sections.get('key_financial_terms', 'See Key Financial Terms section'),
        'payment_terms': sections.get('key_financial_terms', 'See Key Financial Terms section'),
        'key_terms': sections.get('borrower_obligations', 'See Borrower Obligations section'),
        'recommendations': sections.get('borrower_questions', 'See Questions for Borrower section'),
        'summary': sections.get('executive_summary', 'Analysis completed successfully')
    }

def perform_rule_based_analysis(text):
    """Fallback rule-based analysis when OpenAI is not available"""
    
    text_lower = text.lower()
    
    # Basic pattern matching for key terms
    executive_summary = "Document analysis completed using rule-based text processing. "
    key_financial_terms = "Financial terms analysis: "
    fees_penalties = "Fees and penalties analysis: "
    borrower_obligations = "Borrower obligations analysis: "
    lender_rights = "Lender rights analysis: "
    risk_red_flags = "Risk assessment: "
    market_comparison = "Market comparison not available in rule-based analysis."
    borrower_questions = "Questions to ask: "
    references = "Document references would be provided with full AI analysis."
    
    # Look for interest rate information
    if any(term in text_lower for term in ['interest rate', 'annual percentage rate', 'apr', '%']):
        key_financial_terms += "Interest rate information found in document. "
        executive_summary += "Interest rate terms identified. "
    
    # Look for loan amount
    if any(term in text_lower for term in ['loan amount', 'principal', 'loan balance']):
        key_financial_terms += "Loan amount/principal information detected. "
        executive_summary += "Principal loan information present. "
    
    # Look for payment terms
    if any(term in text_lower for term in ['monthly payment', 'payment schedule', 'due date']):
        key_financial_terms += "Payment schedule information found. "
        executive_summary += "Payment terms documented. "
    
    # Look for fees
    if any(term in text_lower for term in ['late fee', 'penalty', 'prepayment', 'closing cost']):
        fees_penalties += "Fee and penalty terms identified in document. "
        risk_red_flags += "• Fee structures require review. "
    
    # Look for insurance requirements
    if any(term in text_lower for term in ['insurance', 'pmi', 'escrow']):
        borrower_obligations += "Insurance and escrow requirements found. "
        key_financial_terms += "Insurance/escrow terms present. "
    
    # Look for default/foreclosure terms
    if any(term in text_lower for term in ['default', 'foreclosure', 'acceleration']):
        lender_rights += "Default and foreclosure procedures documented. "
        risk_red_flags += "• Review default and foreclosure terms carefully. "
    
    # Generate questions based on found terms
    borrower_questions += "1. Verify all interest rate calculations. 2. Confirm payment due dates. 3. Review all fee structures. 4. Understand default procedures."
    
    if not any([
        'interest rate' in text_lower,
        'loan amount' in text_lower, 
        'payment' in text_lower
    ]):
        executive_summary = "Limited mortgage terms detected. Document may be incomplete or require OCR improvement. "
        risk_red_flags += "• Document completeness should be verified. "
    
    return {
        'executive_summary': executive_summary.strip(),
        'key_financial_terms': key_financial_terms.strip(),
        'fees_penalties': fees_penalties.strip(),
        'borrower_obligations': borrower_obligations.strip(),
        'lender_rights': lender_rights.strip(),
        'risk_red_flags': risk_red_flags.strip(),
        'market_comparison': market_comparison,
        'borrower_questions': borrower_questions.strip(),
        'references': references,
        'analysis_method': 'Rule-based (basic)',
        
        # Legacy fields for backwards compatibility
        'loan_details': key_financial_terms.strip(),
        'interest_rate_info': key_financial_terms.strip(),
        'payment_terms': key_financial_terms.strip(),
        'key_terms': borrower_obligations.strip(),
        'recommendations': borrower_questions.strip(),
        'summary': executive_summary.strip(),
        'extracted_text_preview': text[:500] + "..." if len(text) > 500 else text
    }

def call_ollama_api(prompt, model=None):
    """Call Ollama API for text analysis"""
    if model is None:
        model = OLLAMA_MODEL
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        return {
            'success': True,
            'response': result.get('response', ''),
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'response': '',
            'error': str(e)
        }

def fetch_latest_transactions():
    """Fetch latest transactions using the get_bank_trx.py script"""
    import logging
    logging.info("fetching latest transactions")
    print("fetching latest transactions")
    try:
        # Get the path to the get_bank_trx.py script
        script_path = Path(__file__).parent.parent / 'api' / 'get_bank_trx.py'
        
        # Change to the data directory to save the output file there
        data_dir = Path(__file__).parent.parent.parent / 'data'
        data_dir.mkdir(exist_ok=True)
        
        # Run the script from the data directory
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(data_dir),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Find the most recent transaction file
            transaction_files = list(data_dir.glob('transactions_*.txt'))
            if transaction_files:
                latest_file = max(transaction_files, key=lambda x: x.stat().st_mtime)
                return {
                    'success': True,
                    'file_path': str(latest_file),
                    'output': result.stdout,
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'file_path': None,
                    'output': result.stdout,
                    'error': 'No transaction files found after script execution'
                }
        else:
            return {
                'success': False,
                'file_path': None,
                'output': result.stdout,
                'error': result.stderr
            }
    
    except Exception as e:
        return {
            'success': False,
            'file_path': None,
            'output': '',
            'error': str(e)
        }

def parse_transaction_file(file_path):
    """Parse transaction file into structured data"""
    transactions = []
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract transaction lines using regex
        pattern = r'Date: ([\d-]+), Name: ([^,]+), Amount: \$([+-]?[\d.]+)'
        matches = re.findall(pattern, content)
        
        for i, (date_str, name, amount_str) in enumerate(matches):
            try:
                # Parse date
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                
                # Parse amount (remove any extra whitespace)
                amount = float(amount_str.strip())
                
                transactions.append({
                    'id': i + 1,
                    'date': date_str,
                    'datetime': date_obj,
                    'name': name.strip(),
                    'merchant': name.strip(),  # Use name as merchant for now
                    'description': name.strip(),  # Use name as description for now
                    'amount': amount,
                    'time': '12:00:00'  # Default time since we don't have it in current format
                })
            except (ValueError, IndexError) as e:
                print(f"Error parsing transaction line: {date_str}, {name}, {amount_str} - {e}")
                continue
        
        return {
            'success': True,
            'transactions': transactions,
            'count': len(transactions),
            'error': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'transactions': [],
            'count': 0,
            'error': str(e)
        }

def analyze_duplicates_with_ollama(transactions, config=None):
    """Analyze transactions for duplicates using Ollama"""
    
    if config is None:
        config = {
            'time_window_hours': 1,
            'expected_pairs': {
                'PATH': {'morning_window': '06:00-10:00', 'evening_window': '16:00-20:00', 'max_pairs': 2},
                'E-Z*PASSNY': {'morning_window': '06:00-10:00', 'evening_window': '16:00-20:00', 'max_pairs': 3}
            }
        }
    
    # Convert transactions to CSV-like format for the prompt
    csv_data = "Date,Time,Amount,Merchant,Description\n"
    for trx in transactions:
        csv_data += f"{trx['date']},{trx['time']},{trx['amount']},{trx['merchant']},{trx['description']}\n"
    
    prompt = f"""I have a CSV of my credit-card transactions with columns like Date, Time, Amount, Merchant, and Description. Please:

Identify potential duplicate charges.

A "duplicate" is defined as two or more transactions with the same Amount (to the cent) and very similar Merchant or Description, occurring within a short window (e.g. {config['time_window_hours']} hour).

Flag each group of potential duplicates and list all their details.

Avoid false positives for expected pairs.

For round-trip commute expenses (e.g. PATH train), the same merchant ("PATH") will appear twice daily with identical fares.

Exclude any transactions where Merchant contains "PATH" or "E-Z*PASSNY" (or your specified transit vendors) that occur once in the morning and once in the evening with identical amounts.

Allow me to customize this "expected-pair" rule by merchant name, time-of-day window, and number of repeats.

Expected pair configuration: {json.dumps(config['expected_pairs'])}

Provide context and next steps.

For each flagged group, give a brief rationale ("same amount, same merchant, 5 mins apart"), and recommend whether it's likely an error.

If uncertain, ask me to confirm or provide more context.

Output format.

Present results as JSON with an array of objects, each containing:

transactions: list of raw rows
reason: why flagged
is_commute_pair: true/false
likely_duplicate_error: true/false or "undecided"
notes: any special handling or questions for me

Here is the transaction data:

{csv_data}

Please analyze this data and return ONLY valid JSON output with no additional text or explanation outside the JSON."""
    
    result = call_ollama_api(prompt)
    
    if result['success']:
        try:
            # Try to parse the JSON response
            analysis = json.loads(result['response'])
            return {
                'success': True,
                'analysis': analysis,
                'error': None
            }
        except json.JSONDecodeError as e:
            # If JSON parsing fails, try to extract JSON from the response
            try:
                # Look for JSON content between potential markdown code blocks or other text
                json_match = re.search(r'\[.*\]', result['response'], re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group(0))
                    return {
                        'success': True,
                        'analysis': analysis,
                        'error': None
                    }
                else:
                    return {
                        'success': False,
                        'analysis': [],
                        'error': f'Could not parse JSON from Ollama response: {str(e)}'
                    }
            except Exception as parse_error:
                return {
                    'success': False,
                    'analysis': [],
                    'error': f'JSON parsing failed: {str(parse_error)}'
                }
    else:
        return {
            'success': False,
            'analysis': [],
            'error': result['error']
        }

def fetch_transactions_by_month(year, month):
    """Fetch transactions for a specific month using the get_bank_trx.py script with custom date range"""
    try:
        # Import required modules for date calculations
        from calendar import monthrange
        
        # Calculate start and end dates for the specified month
        start_date = datetime(year, month, 1).date()
        _, last_day = monthrange(year, month)
        end_date = datetime(year, month, last_day).date()
        
        # Get the path to the get_bank_trx.py script
        script_path = Path(__file__).parent.parent / 'api' / 'get_bank_trx_custom.py'
        
        # Change to the data directory to save the output file there
        data_dir = Path(__file__).parent.parent.parent / 'data'
        data_dir.mkdir(exist_ok=True)
        
        # Run the script with custom date parameters
        result = subprocess.run(
            [sys.executable, str(script_path), str(start_date), str(end_date)],
            cwd=str(data_dir),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Find the transaction file for this specific month
            output_filename = f"transactions_{start_date}_to_{end_date}.txt"
            file_path = data_dir / output_filename
            
            if file_path.exists():
                return {
                    'success': True,
                    'file_path': str(file_path),
                    'output': result.stdout,
                    'start_date': str(start_date),
                    'end_date': str(end_date),
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'file_path': None,
                    'output': result.stdout,
                    'error': f'Expected output file {output_filename} not found'
                }
        else:
            return {
                'success': False,
                'file_path': None,
                'output': result.stdout,
                'error': result.stderr
            }
    
    except Exception as e:
        return {
            'success': False,
            'file_path': None,
            'output': '',
            'error': str(e)
        }

def analyze_monthly_duplicates_with_ollama(transactions, safe_merchants=None, commute_times=None):
    """Analyze transactions for duplicates using the improved forensic prompt"""
    
    if safe_merchants is None:
        safe_merchants = ["PATH", "STARBUCKS", "DUNKIN", "SUBWAY", "MTA", "E-ZPASSNY"]
    
    if commute_times is None:
        commute_times = "Morning: 6:00-10:00 AM, Evening: 4:00-8:00 PM"
    
    # Convert transactions to CSV format for the prompt
    csv_data = "Date,PostedTime,Merchant,Category,Amount,Currency,TransactionID,Memo\n"
    for i, trx in enumerate(transactions):
        # Use the transaction data to populate CSV fields
        csv_data += f"{trx['date']},{trx['time']},{trx['merchant']},{trx.get('category', 'N/A')},{trx['amount']},USD,{i},{trx['description']}\n"
    
    prompt = f"""You are a financial‑forensics analyst.
Your task is to scan the credit‑card transactions I provide and identify probable duplicate charges—unintentional repeats for the same purchase—while avoiding legitimate, repeated expenses (e.g., daily transit fares, split restaurant bills, subscription renewals, pre‑authorization + final charge pairs).

Input format
I will paste all transactions as a CSV (or JSON) table with at least these columns:

Date, PostedTime(optional), Merchant, Category(optional), Amount, Currency, TransactionID(optional), Memo(optional)

Detection rules & heuristics
Core match criteria (all must be true):

Merchant names are highly similar (≥90 % token similarity after stripping punctuation & common company suffixes).

Amounts match exactly or differ only by rounding to the nearest cent (e.g., $19.00 vs $19).

Transactions are posted within 1 calendar day of each other (use Date + PostedTime if available).

Secondary signals that raise confidence (list them): identical TransactionID, same currency, same BIN code, or an authorization followed immediately by a capture.

Exclusion rules that lower confidence—do NOT flag if any are true:

Merchant is on the user‑supplied safe list of expected multi‑charge vendors: {safe_merchants}

Charges follow a recognisable commuting pattern (e.g., two PATH or subway fares 8–12 h apart).

Amounts fall within ±5 % of a known subscription price or membership fee that recurs on a schedule.

A debit immediately precedes a credit (possible reversal).

For each candidate duplicate, compute a confidence score from 0–100.

≥80 = High (likely accidental duplicate)

60–79 = Medium (worth user review)

40–59 = Low (probably valid, include only if user opts in)

<40 = Ignore

Output
Return only JSON structured like:

{{
  "summary": {{
    "possible_duplicates": 3,
    "high_confidence": 1,
    "medium_confidence": 2
  }},
  "details": [
    {{
      "transaction_indices": [15, 42],
      "reason": "Same merchant & amount, posted 45 minutes apart",
      "confidence": 86
    }}
  ]
}}

transaction_indices are the 0‑based row numbers from the input you received.

Known frequent‑repeat merchants: {safe_merchants}

Typical commute times: {commute_times}

Tone & extra guidance
Be conservative—favor not flagging over flagging if uncertain.

Explain your decision factors clearly in "reason".

Never redact or modify the original monetary amounts.

Here is the transaction data:

{csv_data}

Please analyze this data and return ONLY valid JSON output with no additional text or explanation outside the JSON."""
    
    result = call_ollama_api(prompt)
    
    if result['success']:
        try:
            # Try to parse the JSON response
            analysis = json.loads(result['response'])
            return {
                'success': True,
                'analysis': analysis,
                'error': None
            }
        except json.JSONDecodeError as e:
            # If JSON parsing fails, try to extract JSON from the response
            try:
                # Look for JSON content between potential markdown code blocks or other text
                json_match = re.search(r'\{.*\}', result['response'], re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group(0))
                    return {
                        'success': True,
                        'analysis': analysis,
                        'error': None
                    }
                else:
                    return {
                        'success': False,
                        'analysis': {},
                        'error': f'Could not parse JSON from Ollama response: {str(e)}'
                    }
            except Exception as parse_error:
                return {
                    'success': False,
                    'analysis': {},
                    'error': f'JSON parsing failed: {str(parse_error)}'
                }
    else:
        return {
            'success': False,
            'analysis': {},
            'error': result['error']
        }

def get_latest_30yr_mortgage_rate():
    """
    Fetch the latest 30-year mortgage rate from FRED.
    Returns a dictionary with date, rate, and any error information.
    """
    try:
        # FRED CSV export URL for the MORTGAGE30US series
        csv_url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US'
        
        # Fetch the CSV data
        resp = requests.get(csv_url)
        resp.raise_for_status()  # ensure we notice bad responses
        
        # Load into pandas
        df = pd.read_csv(StringIO(resp.text))
        
        # Drop any missing values and grab the last row
        df = df.dropna(subset=['MORTGAGE30US'])
        latest = df.iloc[-1]
        
        # Extract date and value
        date = latest['observation_date']
        rate = float(latest['MORTGAGE30US'])
        
        return {
            'success': True,
            'date': date,
            'rate': rate,
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'date': None,
            'rate': None,
            'error': str(e)
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/plaid-demo')
def plaid_demo():
    """Serve the Plaid Link demo page with mortgage analysis"""
    web_dir = Path(__file__).parent
    return send_from_directory(str(web_dir), 'plaid_link_demo.html')

@app.route('/api/mortgage-data')
def get_mortgage_data():
    # Your current mortgage rate
    your_rate = 6.575
    
    # Get current 30-year rate
    market_data = get_latest_30yr_mortgage_rate()
    
    if not market_data['success']:
        return jsonify({
            'error': market_data['error']
        }), 500
    
    current_rate = market_data['rate']
    rate_difference = your_rate - current_rate
    
    # Determine if refinancing should be considered
    should_refinance = rate_difference > 1.0
    
    return jsonify({
        'success': True,
        'your_rate': your_rate,
        'current_rate': current_rate,
        'rate_difference': rate_difference,
        'should_refinance': should_refinance,
        'date': market_data['date'],
        'refinance_message': "Consider refinancing" if should_refinance else "Current rate difference doesn't warrant refinancing"
    })

@app.route('/api/analyze-mortgage', methods=['POST'])
def analyze_mortgage():
    """Analyze uploaded mortgage document"""
    try:
        # Check if file was uploaded
        if 'mortgage_file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['mortgage_file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload PDF, PNG, or JPG files.'}), 400
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            # Extract text based on file type
            file_extension = filename.rsplit('.', 1)[1].lower()
            
            if file_extension == 'pdf':
                extracted_text = extract_text_from_pdf(file_path)
            elif file_extension in ['png', 'jpg', 'jpeg']:
                extracted_text = extract_text_from_image(file_path)
            else:
                return jsonify({'error': 'Unsupported file type'}), 400
            
            # Analyze the extracted text
            analysis_result = analyze_mortgage_with_ai(extracted_text)
            
            # Add extracted text to result for debugging (optional)
            analysis_result['extracted_text_preview'] = extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
            
            return jsonify(analysis_result)
            
        finally:
            # Clean up temporary file
            if os.path.exists(file_path):
                os.remove(file_path)
    
    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@app.route('/api/analyze-duplicates', methods=['GET', 'POST'])
def analyze_duplicates():
    import logging
    """Analyze transactions for duplicates using Ollama"""
    try:
        # Handle configuration from request
        logging.info("analyzing duplicates")
        config = None
        use_existing_file = False
        
        if request.method == 'POST':
            data = request.get_json() or {}
            config = data.get('config')
            use_existing_file = data.get('use_existing_file', False)
        else:
            # GET request - use query parameters
            use_existing_file = request.args.get('use_existing', 'false').lower() == 'true'
        
        # Step 1: Get latest transactions
        logging.info("fetching latest transactions")
        if not use_existing_file:
            fetch_result = fetch_latest_transactions()
            logging.info(f"Fetch result: {fetch_result}")
            if not fetch_result['success']:
                return jsonify({
                    'error': f'Failed to fetch transactions: {fetch_result["error"]}',
                    'fetch_output': fetch_result['output']
                }), 500
            
            file_path = fetch_result['file_path']
        else:
            # Use the most recent existing file
            data_dir = Path(__file__).parent.parent.parent / 'data'
            transaction_files = list(data_dir.glob('transactions_*.txt'))
            if not transaction_files:
                return jsonify({'error': 'No existing transaction files found'}), 404
            
            file_path = str(max(transaction_files, key=lambda x: x.stat().st_mtime))
        
        # Step 2: Parse transaction file
        parse_result = parse_transaction_file(file_path)
        if not parse_result['success']:
            return jsonify({
                'error': f'Failed to parse transactions: {parse_result["error"]}'
            }), 500
        
        transactions = parse_result['transactions']
        
        if not transactions:
            return jsonify({
                'error': 'No transactions found in file',
                'file_path': file_path
            }), 400
        
        # Step 3: Analyze for duplicates
        analysis_result = analyze_duplicates_with_ollama(transactions, config)
        
        if not analysis_result['success']:
            return jsonify({
                'error': f'Duplicate analysis failed: {analysis_result["error"]}',
                'transaction_count': len(transactions),
                'file_path': file_path
            }), 500
        
        # Step 4: Return results
        return jsonify({
            'success': True,
            'transaction_count': len(transactions),
            'file_path': file_path,
            'analysis': analysis_result['analysis'],
            'config_used': config,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@app.route('/api/fetch-transactions', methods=['POST'])
def fetch_transactions():
    """Fetch fresh transactions from Plaid API"""
    try:
        fetch_result = fetch_latest_transactions()
        
        if fetch_result['success']:
            # Also parse the file to return transaction count
            parse_result = parse_transaction_file(fetch_result['file_path'])
            
            return jsonify({
                'success': True,
                'file_path': fetch_result['file_path'],
                'transaction_count': parse_result['count'] if parse_result['success'] else 0,
                'output': fetch_result['output'],
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': fetch_result['error'],
                'output': fetch_result['output']
            }), 500
    
    except Exception as e:
        return jsonify({'error': f'Failed to fetch transactions: {str(e)}'}), 500

@app.route('/api/transactions-summary')
def transactions_summary():
    """Get summary of available transaction data"""
    try:
        data_dir = Path(__file__).parent.parent.parent / 'data'
        transaction_files = list(data_dir.glob('transactions_*.txt'))
        
        if not transaction_files:
            return jsonify({
                'files': [],
                'latest_file': None,
                'total_files': 0
            })
        
        # Sort by modification time
        transaction_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest_file = transaction_files[0]
        
        # Parse the latest file to get transaction count
        parse_result = parse_transaction_file(str(latest_file))
        
        file_info = []
        for file_path in transaction_files:
            stat = file_path.stat()
            file_info.append({
                'name': file_path.name,
                'path': str(file_path),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'size': stat.st_size
            })
        
        return jsonify({
            'files': file_info,
            'latest_file': {
                'path': str(latest_file),
                'name': latest_file.name,
                'transaction_count': parse_result['count'] if parse_result['success'] else 0,
                'modified': datetime.fromtimestamp(latest_file.stat().st_mtime).isoformat()
            },
            'total_files': len(transaction_files)
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get summary: {str(e)}'}), 500

@app.route('/api/analyze-month-duplicates', methods=['POST'])
def analyze_month_duplicates():
    """Analyze transactions for a specific month using the improved forensic analysis"""
    try:
        data = request.get_json() or {}
        
        # Get parameters from request
        year = data.get('year')
        month = data.get('month')
        safe_merchants = data.get('safe_merchants', ["PATH", "STARBUCKS", "DUNKIN", "SUBWAY", "MTA", "E-ZPASSNY"])
        commute_times = data.get('commute_times', "Morning: 6:00-10:00 AM, Evening: 4:00-8:00 PM")
        fetch_fresh = data.get('fetch_fresh', True)
        
        # Validate parameters
        if not year or not month:
            return jsonify({'error': 'Year and month are required'}), 400
        
        try:
            year = int(year)
            month = int(month)
            if month < 1 or month > 12:
                raise ValueError("Month must be between 1 and 12")
        except ValueError as e:
            return jsonify({'error': f'Invalid year or month: {str(e)}'}), 400
        
        # Step 1: Fetch transactions for the specified month
        if fetch_fresh:
            fetch_result = fetch_transactions_by_month(year, month)
            if not fetch_result['success']:
                return jsonify({
                    'error': f'Failed to fetch transactions for {year}-{month:02d}: {fetch_result["error"]}',
                    'fetch_output': fetch_result.get('output', '')
                }), 500
            
            file_path = fetch_result['file_path']
            date_range = {
                'start_date': fetch_result['start_date'],
                'end_date': fetch_result['end_date']
            }
        else:
            # Use existing file for the month if available
            data_dir = Path(__file__).parent.parent.parent / 'data'
            from calendar import monthrange
            start_date = datetime(year, month, 1).date()
            _, last_day = monthrange(year, month)
            end_date = datetime(year, month, last_day).date()
            
            expected_filename = f"transactions_{start_date}_to_{end_date}.txt"
            file_path = str(data_dir / expected_filename)
            
            if not os.path.exists(file_path):
                return jsonify({
                    'error': f'No existing transaction file found for {year}-{month:02d}. Try with fetch_fresh=true.',
                    'expected_file': expected_filename
                }), 404
            
            date_range = {
                'start_date': str(start_date),
                'end_date': str(end_date)
            }
        
        # Step 2: Parse transaction file
        parse_result = parse_transaction_file(file_path)
        if not parse_result['success']:
            return jsonify({
                'error': f'Failed to parse transactions: {parse_result["error"]}'
            }), 500
        
        transactions = parse_result['transactions']

        # If fresh fetch returned no transactions, try fallback to an existing cached file for the month
        if fetch_fresh and not transactions:
            try:
                data_dir = Path(__file__).parent.parent.parent / 'data'
                fallback_filename = f"transactions_{date_range['start_date']}_to_{date_range['end_date']}.txt"
                fallback_path = data_dir / fallback_filename
                if fallback_path.exists():
                    fallback_parse = parse_transaction_file(str(fallback_path))
                    if fallback_parse['success']:
                        transactions = fallback_parse['transactions']
                        file_path = str(fallback_path)
            except Exception:
                pass

        # Filter transactions strictly to requested month range if we used a broader file
        try:
            start_dt = datetime.strptime(date_range['start_date'], '%Y-%m-%d').date()
            end_dt = datetime.strptime(date_range['end_date'], '%Y-%m-%d').date()
            transactions = [t for t in transactions if start_dt <= t['datetime'].date() <= end_dt]
        except Exception:
            # If parsing fails for any reason, continue with unfiltered list
            pass
        
        if not transactions:
            return jsonify({
                'error': f'No transactions found for {year}-{month:02d}',
                'file_path': file_path,
                'date_range': date_range
            }), 400
        
        # Step 3: Analyze for duplicates using the improved prompt
        analysis_result = analyze_monthly_duplicates_with_ollama(
            transactions, 
            safe_merchants=safe_merchants,
            commute_times=commute_times
        )
        
        if not analysis_result['success']:
            return jsonify({
                'error': f'Duplicate analysis failed: {analysis_result["error"]}',
                'transaction_count': len(transactions),
                'file_path': file_path,
                'date_range': date_range
            }), 500
        
        # Step 4: Return comprehensive results
        return jsonify({
            'success': True,
            'month': f"{year}-{month:02d}",
            'date_range': date_range,
            'transaction_count': len(transactions),
            'file_path': file_path,
            'analysis': analysis_result['analysis'],
            'configuration': {
                'safe_merchants': safe_merchants,
                'commute_times': commute_times
            },
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@app.route('/api/available-months', methods=['GET'])
def get_available_months():
    """Get list of months for which transaction data is available"""
    try:
        data_dir = Path(__file__).parent.parent.parent / 'data'
        transaction_files = list(data_dir.glob('transactions_*_to_*.txt'))
        
        available_months = []
        for file_path in transaction_files:
            # Parse filename to extract date range
            filename = file_path.name
            # Example: transactions_2024-01-01_to_2024-01-31.txt
            match = re.match(r'transactions_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})\.txt', filename)
            if match:
                start_date_str, end_date_str = match.groups()
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                
                # Check if this represents a full month
                from calendar import monthrange
                expected_start = datetime(start_date.year, start_date.month, 1).date()
                _, last_day = monthrange(start_date.year, start_date.month)
                expected_end = datetime(start_date.year, start_date.month, last_day).date()
                
                if (start_date.date() == expected_start and 
                    end_date.date() == expected_end):
                    
                    stat = file_path.stat()
                    available_months.append({
                        'year': start_date.year,
                        'month': start_date.month,
                        'month_name': start_date.strftime('%B %Y'),
                        'file_name': filename,
                        'file_path': str(file_path),
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'size': stat.st_size
                    })
        
        # Sort by year and month (most recent first)
        available_months.sort(key=lambda x: (x['year'], x['month']), reverse=True)
        
        return jsonify({
            'success': True,
            'available_months': available_months,
            'total_months': len(available_months)
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to get available months: {str(e)}'}), 500

@app.route('/api/update-safe-merchants', methods=['POST'])
def update_safe_merchants():
    """Update the safe merchants list for duplicate analysis"""
    try:
        data = request.get_json() or {}
        
        safe_merchants = data.get('safe_merchants', [])
        
        if not isinstance(safe_merchants, list):
            return jsonify({'error': 'safe_merchants must be a list'}), 400
        
        # Here you could save this to a configuration file or database
        # For now, we'll just return the updated list
        
        return jsonify({
            'success': True,
            'safe_merchants': safe_merchants,
            'message': 'Safe merchants list updated successfully'
        })
    
    except Exception as e:
        return jsonify({'error': f'Failed to update safe merchants: {str(e)}'}), 500

def _round_to_nearest(value: float, step: int) -> int:
    try:
        return int(round(value / step) * step)
    except Exception:
        return int(value)

def calculate_condo_insurance_recommendations(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based HO-6 (condo) insurance needs calculator.

    Inputs expected (all optional, with sensible defaults):
      - square_feet: int/float
      - finish_level: 'basic'|'standard'|'premium'
      - hoa_policy_type: 'all-in'|'single-entity'|'bare-walls'
      - hoa_deductible: number
      - personal_property_estimate: number or None
      - risk_factors: { hurricane, wildfire, earthquake, water_backup_risk, short_term_rental, floor_level }
      - liability_preference: 'low'|'standard'|'high'
      - deductible_preference: 'low'|'standard'|'high'
      - high_value_items_total: number
      - max_single_item_value: number
    """
    # Defaults and maps
    finish = (payload.get('finish_level') or 'standard').lower()
    finish_to_improvement_cost = {
        'basic': 60,
        'standard': 90,
        'premium': 130,
    }
    finish_to_property_cost = {
        'basic': 30,
        'standard': 60,
        'premium': 90,
    }
    square_feet = float(payload.get('square_feet') or 800)
    hoa_type = (payload.get('hoa_policy_type') or 'single-entity').lower()
    hoa_deductible = float(payload.get('hoa_deductible') or 25000)
    personal_property_estimate = payload.get('personal_property_estimate')
    risk = payload.get('risk_factors') or {}
    liability_pref = (payload.get('liability_preference') or 'standard').lower()
    deductible_pref = (payload.get('deductible_preference') or 'standard').lower()
    high_value_total = float(payload.get('high_value_items_total') or 0)
    max_single_item = float(payload.get('max_single_item_value') or 0)

    # Compute Coverage A (Dwelling/Improvements) based on HOA policy type
    per_sf_improve = float(finish_to_improvement_cost.get(finish, 90))
    dwelling = 0.0
    notes = []

    if hoa_type in ['bare-walls', 'barewalls', 'bare_walls']:
        dwelling = square_feet * per_sf_improve
        notes.append('Bare-walls master policy: your HO-6 should insure interior structure to studs.')
    elif hoa_type in ['single-entity', 'single_entity', 'singleentity']:
        dwelling = max(25000, square_feet * per_sf_improve * 0.25)
        notes.append('Single-entity master policy: base finishes covered; insure owner upgrades/betterments.')
    else:  # all-in
        dwelling = max(15000, square_feet * per_sf_improve * 0.10)
        notes.append('All-in master policy: consider coverage for upgrades beyond original spec.')

    # Coverage C (Personal Property)
    per_sf_property = float(finish_to_property_cost.get(finish, 60))
    if personal_property_estimate is None or float(personal_property_estimate) <= 0:
        personal_property = square_feet * per_sf_property
        notes.append('Personal property estimated from square footage and finish level — adjust if you have a detailed inventory.')
    else:
        personal_property = float(personal_property_estimate)

    # Coverage D (Loss of Use) ~20% of Coverage C, with a sensible floor
    loss_of_use = max(personal_property * 0.20, 30000)

    # Coverage E (Personal Liability)
    if liability_pref == 'low':
        liability = 300_000
    elif liability_pref == 'high':
        liability = 1_000_000
    else:
        liability = 500_000
    if risk.get('short_term_rental'):
        liability = max(liability, 1_000_000)
        notes.append('Short-term rental exposure detected — higher liability recommended and consider a personal umbrella policy.')

    # Medical Payments to Others
    medical_payments = 10_000 if liability_pref == 'high' else 5_000

    # Loss Assessment — aim to at least match HOA deductible; many carriers cap at $50k–$100k
    loss_assessment_target = max(hoa_deductible, 50_000)
    if risk.get('hurricane') or risk.get('wildfire'):
        loss_assessment_target = max(loss_assessment_target, 100_000)
    loss_assessment = loss_assessment_target
    notes.append('Loss assessment should at least match your HOA master deductible; many policies cap at $50k–$100k.')

    # Water backup — higher if basement/ground or explicit risk
    floor_level = (risk.get('floor_level') or '').lower()
    water_backup = 5_000
    if risk.get('water_backup_risk') or floor_level in ['basement', 'ground']:
        water_backup = 10_000

    # Deductible recommendation
    if deductible_pref == 'low':
        deductible = 500 if hoa_deductible <= 10_000 else 1_000
    elif deductible_pref == 'high':
        deductible = 2_500
    else:
        deductible = 1_000

    # Ordinance or Law — % of Coverage A
    ordinance_or_law = max(dwelling * 0.10, 10_000)

    # Scheduled property guidance
    should_schedule = max_single_item >= 1500 or high_value_total >= 5_000
    sched_limit = max_single_item if should_schedule else 0
    sched_notes = 'Schedule jewelry/collectibles individually to avoid sublimits.' if should_schedule else 'No scheduling needed based on provided values.'

    # Hazard disclaimers
    if risk.get('earthquake'):
        notes.append('Earthquake is not covered by standard HO-6; consider separate EQ policy or endorsement if available.')
    if risk.get('hurricane'):
        notes.append('Wind/hail and hurricane deductibles may apply under the master policy and your HO-6; verify percentages and triggers.')
    if risk.get('wildfire'):
        notes.append('Wildfire risk may impact availability and pricing; keep inventories and defensible-space practices.')
    notes.append('Flood (rising water) is excluded — consider an NFIP or private flood policy if in a flood-risk area.')

    # Rounding for quoting clarity
    dwelling = _round_to_nearest(dwelling, 1000)
    personal_property = _round_to_nearest(personal_property, 1000)
    loss_of_use = _round_to_nearest(loss_of_use, 1000)
    ordinance_or_law = _round_to_nearest(ordinance_or_law, 1000)
    loss_assessment = _round_to_nearest(loss_assessment, 5000)
    water_backup = _round_to_nearest(water_backup, 1000)

    return {
        'inputs_echo': payload,
        'recommended_coverages': {
            'dwelling_improvements': dwelling,
            'personal_property': personal_property,
            'loss_of_use': loss_of_use,
            'personal_liability': liability,
            'medical_payments': medical_payments,
            'loss_assessment': loss_assessment,
            'water_backup': water_backup,
            'deductible': deductible,
            'ordinance_or_law': ordinance_or_law,
        },
        'scheduled_property_recommendation': {
            'should_schedule': should_schedule,
            'suggested_schedule_limit': _round_to_nearest(sched_limit, 100),
            'notes': sched_notes,
        },
        'notes': notes,
        'disclaimer': 'This is an educational estimate. Final eligibility, limits, and premium depend on insurer underwriting and policy forms.'
    }

@app.route('/api/condo-insurance-recommendations', methods=['POST'])
def condo_insurance_recommendations():
    try:
        data = request.get_json() or {}
        result = calculate_condo_insurance_recommendations(data)
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to calculate recommendations: {str(e)}'}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 