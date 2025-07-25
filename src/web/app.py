from flask import Flask, render_template, jsonify, request
import requests
import pandas as pd
from io import StringIO
from datetime import datetime
import os
import tempfile
import PyPDF2
from PIL import Image
import pytesseract
import openai
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Configure OpenAI (you'll need to set your API key)
# openai.api_key = os.getenv('OPENAI_API_KEY')  # Uncomment and set your API key

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
    
    # Check if OpenAI API key is configured
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    if openai_api_key and len(text.strip()) > 50:
        try:
            # Use OpenAI for comprehensive analysis
            openai.api_key = openai_api_key
            
            response = openai.ChatCompletion.create(
                model="gpt-4",  # Use GPT-4 for better analysis
                messages=[
                    {"role": "system", "content": "You are an experienced real-estate attorney and consumer-rights advocate specializing in mortgage document analysis."},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            ai_analysis = response.choices[0].message.content
            
            # Parse the structured response into our expected format
            analysis_result = parse_structured_analysis(ai_analysis)
            analysis_result['full_analysis'] = ai_analysis
            analysis_result['analysis_method'] = 'OpenAI GPT-4'
            
            return analysis_result
            
        except Exception as e:
            print(f"OpenAI analysis failed: {e}")
            # Fall back to rule-based analysis
            return perform_rule_based_analysis(text)
    else:
        # Use rule-based analysis if no OpenAI or insufficient text
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
    with open('plaid_link_demo.html', 'r') as f:
        content = f.read()
    return content

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 