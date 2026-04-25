import csv
import io
from pathlib import Path

try:
    from .llms import generate_json as llm_generate_json
except Exception:
    from llms import generate_json as llm_generate_json  # type: ignore


MAX_TIP_TRANSACTIONS = 200
PROMPT_TEMPLATE_PATH = Path(__file__).with_name('finance_tip.md')

def _load_prompt_template():
    try:
        return PROMPT_TEMPLATE_PATH.read_text(encoding='utf-8').strip()
    except Exception:
        return None


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
    template = _load_prompt_template()
    return template.replace('{csv_data}', csv_data, 1)


def generate_finance_tip(transactions, openai_api_key=None, use_openai=False, model=None):
    """Generate a personalized finance tip using an LLM."""
    provider = 'openai' if use_openai else 'local'
    limited_transactions = transactions[:MAX_TIP_TRANSACTIONS]
    analyzed_count = len(limited_transactions)
    truncated = len(transactions) > analyzed_count

    if not llm_generate_json:
        return {
            'success': False,
            'analysis': {},
            'error': 'LLM not available',
            'provider': provider,
            'total_processed': analyzed_count,
            'analysis_limit': MAX_TIP_TRANSACTIONS,
            'truncated': truncated,
        }

    prompt = _build_finance_tip_prompt(_transactions_to_csv(limited_transactions))

    try:
        result = llm_generate_json(prompt, model=model, openai_api_key=openai_api_key, use_openai=use_openai)
    except Exception as exc:
        return {
            'success': False,
            'analysis': {},
            'error': str(exc),
            'provider': provider,
            'total_processed': analyzed_count,
            'analysis_limit': MAX_TIP_TRANSACTIONS,
            'truncated': truncated,
        }

    if result.get('success'):
        return {
            'success': True,
            'analysis': result.get('data', {}),
            'error': None,
            'provider': provider,
            'total_processed': analyzed_count,
            'analysis_limit': MAX_TIP_TRANSACTIONS,
            'truncated': truncated,
        }
    return {
        'success': False,
        'analysis': {},
        'error': result.get('error', 'Unknown error'),
        'provider': provider,
        'total_processed': analyzed_count,
        'analysis_limit': MAX_TIP_TRANSACTIONS,
        'truncated': truncated,
    }
