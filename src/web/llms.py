import os
import json
from typing import Any, Dict, Optional, Tuple

import requests


# Basic Ollama configuration via environment variables
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3:latest')
OLLAMA_TIMEOUT_SECONDS = int(os.getenv('OLLAMA_TIMEOUT_SECONDS', '5000'))

# OpenAI configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.1')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')

# Available OpenAI models for selection
AVAILABLE_OPENAI_MODELS = [
    'gpt-5.1',
    'gpt-4o',
    'gpt-5-mini',
    'gpt-oss-120b',
]


def _post_ollama_generate(payload: Dict[str, Any], timeout_seconds: Optional[int] = None) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """Send a request to Ollama's generate endpoint."""
    timeout = timeout_seconds or OLLAMA_TIMEOUT_SECONDS
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        parsed = response.json()
        return True, parsed, None
    except Exception as exc:  # Broad except is fine for transport layer
        return False, {}, str(exc)


def _post_openai_chat(
    messages: list,
    model: str,
    api_key: str,
    base_url: str = 'https://api.openai.com/v1',
    timeout_seconds: int = 120,
    response_format: Optional[str] = None
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """Send a request to OpenAI's chat completion endpoint."""
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model,
            'messages': messages
        }
        
        if response_format == 'json':
            payload['response_format'] = {'type': 'json_object'}
        
        response = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        parsed = response.json()
        return True, parsed, None
    except Exception as exc:
        return False, {}, str(exc)


def _extract_json_maybe(text: str) -> Optional[Any]:
    """Attempt to parse JSON from a model response. Tries direct parse, then extracts first {...} or [...] block."""
    if not text:
        return None
    # First try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to extract JSON object
    import re

    obj_match = re.search(r"\{[\s\S]*\}", text)
    if obj_match:
        try:
            return json.loads(obj_match.group(0))
        except Exception:
            pass

    arr_match = re.search(r"\[[\s\S]*\]", text)
    if arr_match:
        try:
            return json.loads(arr_match.group(0))
        except Exception:
            pass

    return None


def generate_json(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    openai_api_key: Optional[str] = None,
    use_openai: bool = False,
) -> Dict[str, Any]:
    """Call LLM (Ollama or OpenAI) to generate valid JSON.

    Returns a dict: { success: bool, data: Any, raw_text: str, error: Optional[str] }
    """
    # Determine if we should use OpenAI
    should_use_openai = use_openai or openai_api_key or OPENAI_API_KEY
    
    if should_use_openai:
        # Use OpenAI API
        api_key = openai_api_key or OPENAI_API_KEY
        if not api_key:
            return {"success": False, "data": None, "raw_text": "", "error": "OpenAI API key is required"}
        
        timeout = timeout_seconds or 120
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        ok, raw, err = _post_openai_chat(
            messages=messages,
            model=model or OPENAI_MODEL,
            api_key=api_key,
            base_url=OPENAI_BASE_URL,
            timeout_seconds=timeout,
            response_format='json'
        )
        
        if not ok:
            return {"success": False, "data": None, "raw_text": "", "error": err}
        
        try:
            raw_text = raw.get('choices', [{}])[0].get('message', {}).get('content', '')
        except (KeyError, IndexError):
            return {"success": False, "data": None, "raw_text": "", "error": "Invalid OpenAI response format"}
        
        parsed = _extract_json_maybe(raw_text)
        if parsed is None:
            return {"success": False, "data": None, "raw_text": raw_text, "error": "Failed to parse JSON from OpenAI response"}
        
        return {"success": True, "data": parsed, "raw_text": raw_text, "error": None}
    
    else:
        # Use Ollama (local)
        timeout = timeout_seconds or OLLAMA_TIMEOUT_SECONDS
        newlines = "\n\n"
        payload = {
            "model": model or OLLAMA_MODEL,
            "prompt": f"{system + newlines if system else ''}{prompt}",
            "stream": False,
            # Ollama's `format: "json"` nudges the model to emit JSON; still validate client-side.
            "format": "json",
            "keep_alive": "15m",
        }

        ok, raw, err = _post_ollama_generate(payload, timeout_seconds=timeout)
        if not ok:
            return {"success": False, "data": None, "raw_text": "", "error": err}

        raw_text = raw.get("response", "")
        parsed = _extract_json_maybe(raw_text)
        if parsed is None:
            return {"success": False, "data": None, "raw_text": raw_text, "error": "Failed to parse JSON from model response"}

        return {"success": True, "data": parsed, "raw_text": raw_text, "error": None}


def categorize_transactions(
    transactions: list,
    model: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    openai_api_key: Optional[str] = None,
    use_openai: bool = False,
) -> Dict[str, Any]:
    """Categorize a list of transactions using LLM.
    
    Args:
        transactions: List of transaction dicts with keys: date, name, amount, account_name
        model: Optional model name to use
        timeout_seconds: Optional timeout override
        
    Returns:
        Dict with keys: success (bool), categorized_transactions (list), error (Optional[str])
    """
    if not transactions:
        return {"success": False, "categorized_transactions": [], "error": "No transactions provided"}
    
    # Limit to prevent timeouts
    max_transactions = 100
    limited_transactions = transactions[:max_transactions]
    
    # Build transaction data for prompt
    transaction_lines = []
    for idx, trx in enumerate(limited_transactions, 1):
        date = trx.get('date', 'N/A')
        name = trx.get('name') or trx.get('merchant', 'Unknown')
        amount = trx.get('amount', 0)
        account = trx.get('account_name') or trx.get('account', 'Unknown')
        transaction_lines.append(f"{idx}. {date} | {name} | ${amount:.2f} | {account}")
    
    transaction_text = "\n".join(transaction_lines)
    
    system_prompt = """You are a financial transaction categorization expert. 
Categorize each transaction into ONE of these standard categories:
- Food & Dining (restaurants, groceries, cafes, food delivery)
- Transportation (public transit, parking, tolls, gas, rideshare)
- Shopping (retail, clothing, general merchandise, online shopping)
- Entertainment (movies, games, subscriptions, hobbies)
- Bills & Utilities (electricity, gas, water, internet, phone)
- Healthcare (medical, pharmacy, veterinary)
- Personal Care (salon, spa, beauty)
- Transfer & Payments (Zelle, Venmo, peer-to-peer payments)
- Income (salary, deposits, refunds)
- Fees & Charges (ATM fees, bank fees, service charges)
- Other (anything that doesn't fit above)

Return ONLY valid JSON."""
    
    prompt = f"""Categorize each of these transactions:

{transaction_text}

Return valid JSON in this exact format:
{{
  "categorized_transactions": [
    {{
      "id": 1,
      "category": "Food & Dining",
      "subcategory": "Restaurant",
      "confidence": "high"
    }},
    {{
      "id": 2,
      "category": "Transportation",
      "subcategory": "Public Transit",
      "confidence": "high"
    }}
  ]
}}

Rules:
1. Assign ONE primary category to each transaction
2. Add a specific subcategory when possible
3. Confidence can be: "high", "medium", or "low"
4. Use transaction IDs from 1 to {len(limited_transactions)}
5. Be consistent with similar merchants
6. Income transactions (deposits, salary) should be marked as "Income"
"""
    
    result = generate_json(
        prompt, 
        model=model, 
        system=system_prompt, 
        timeout_seconds=timeout_seconds,
        openai_api_key=openai_api_key,
        use_openai=use_openai
    )
    
    if not result.get('success'):
        return {
            "success": False,
            "categorized_transactions": [],
            "error": result.get('error', 'Failed to categorize transactions')
        }
    
    data = result.get('data', {})
    categorized = data.get('categorized_transactions', [])
    
    # Merge categories back into original transactions
    categorized_dict = {item.get('id'): item for item in categorized}
    
    enriched_transactions = []
    for idx, trx in enumerate(limited_transactions, 1):
        enriched_trx = trx.copy()
        if idx in categorized_dict:
            cat_info = categorized_dict[idx]
            enriched_trx['category'] = cat_info.get('category', 'Other')
            enriched_trx['subcategory'] = cat_info.get('subcategory', '')
            enriched_trx['confidence'] = cat_info.get('confidence', 'medium')
        else:
            enriched_trx['category'] = 'Other'
            enriched_trx['subcategory'] = ''
            enriched_trx['confidence'] = 'low'
        enriched_transactions.append(enriched_trx)
    
    return {
        "success": True,
        "categorized_transactions": enriched_transactions,
        "total_processed": len(enriched_transactions),
        "error": None
    }

