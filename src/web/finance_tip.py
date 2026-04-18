import csv
import io

try:
    from .llms import generate_json as llm_generate_json
except Exception:
    from llms import generate_json as llm_generate_json  # type: ignore


MAX_TIP_TRANSACTIONS = 200


def _transactions_to_csv(transactions):
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=['date', 'time', 'name', 'description', 'amount', 'account'],
        lineterminator='\n',
    )
    writer.writeheader()
    for trx in transactions:
        writer.writerow(
            {
                'date': trx.get('date', ''),
                'time': trx.get('time', ''),
                'name': trx.get('merchant', ''),
                'description': trx.get('description', ''),
                'amount': trx.get('amount', 0),
                'account': trx.get('account', 'Unknown'),
            }
        )
    return output.getvalue()


def _build_finance_tip_prompt(csv_data):
    return f"""You are a personal finance coach. Analyze these transactions and provide ONE specific actionable tip.
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
5. Provide 2-3 specific, practical steps with timeframes.
6. If no strong pattern exists, focus on the largest category or month with the biggest spending jump.
7. Stay strictly grounded in the provided data; do not invent charges, categories, or memberships."""


def generate_finance_tip(transactions, openai_api_key=None, use_openai=False, model=None):
    """Generate a personalized finance tip using an LLM."""
    if not llm_generate_json:
        return {'success': False, 'analysis': {}, 'error': 'LLM not available'}

    limited_transactions = transactions[:MAX_TIP_TRANSACTIONS]
    prompt = _build_finance_tip_prompt(_transactions_to_csv(limited_transactions))

    try:
        result = llm_generate_json(prompt, model=model, openai_api_key=openai_api_key, use_openai=use_openai)
    except Exception as exc:
        return {'success': False, 'analysis': {}, 'error': str(exc)}

    if result.get('success'):
        return {'success': True, 'analysis': result.get('data', {}), 'error': None}
    return {'success': False, 'analysis': {}, 'error': result.get('error', 'Unknown error')}
