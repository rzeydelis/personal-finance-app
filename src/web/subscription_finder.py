import re
from collections import Counter, defaultdict
from datetime import timedelta


KNOWN_SUBSCRIPTION_KEYWORDS = (
    'adobe',
    'apple one',
    'amazon prime',
    'apple',
    'audible',
    'canva',
    'chatgpt',
    'duolingo',
    'disney',
    'dropbox',
    'figma',
    'github',
    'gitlab',
    'google one',
    'headspace',
    'hulu',
    'icloud',
    'kindle unlimited',
    'max',
    'membership fee',
    'membership',
    'microsoft',
    'microsoft 365',
    'netflix',
    'new york times',
    'notion',
    'openai',
    'paramount',
    'patreon',
    'peacock',
    'peloton',
    'prime video',
    'quickbooks',
    'recurring',
    'ring',
    'spotify',
    'subscr',
    'subscription',
    'tidal',
    'uber one',
    'wall street journal',
    'wsj',
    'youtube',
    'youtube premium',
    'lyft pink',
)

EXCLUDED_KEYWORDS = (
    'ach',
    'atm',
    'bus',
    'cash app',
    'deposit',
    'ezpass',
    'fare',
    'interest',
    'mta',
    'nj transit',
    'path',
    'paycheck',
    'payment received',
    'paygo',
    'parking',
    'payroll',
    'refund',
    'salary',
    'subway',
    'tax refund',
    'toll',
    'train',
    'transfer',
    'transit',
    'venmo',
    'wire',
    'zelle',
)

CADENCE_WINDOWS = {
    'weekly': {'min_days': 5, 'max_days': 9, 'annual_factor': 52},
    'biweekly': {'min_days': 12, 'max_days': 16, 'annual_factor': 26},
    'monthly': {'min_days': 25, 'max_days': 35, 'annual_factor': 12},
    'quarterly': {'min_days': 80, 'max_days': 100, 'annual_factor': 4},
    'yearly': {'min_days': 350, 'max_days': 380, 'annual_factor': 1},
}

MIN_NON_KEYWORD_OCCURRENCES = 3
MIN_NON_KEYWORD_AVERAGE_AMOUNT = 5.0
MAX_NON_KEYWORD_WEEKLY_BIWEEKLY_AMOUNT = 40.0
MAX_KEYWORD_AMOUNT_VARIATION = 0.45


def has_keyword(text, keywords):
    lowered = (text or '').lower()
    return any(keyword in lowered for keyword in keywords)


def normalize_merchant_name(name):
    """Reduce merchant noise so recurring charges from the same service can be grouped."""
    cleaned = (name or '').lower()
    cleaned = re.sub(r'https?://\S+', ' ', cleaned)
    cleaned = re.sub(r'[*#@]', ' ', cleaned)
    cleaned = re.sub(r'\b(?:pos|dbt|debit|credit|purchase|checkcard|online|visa|mc|card|ending|withdrawal)\b', ' ', cleaned)
    cleaned = re.sub(r'\d+', ' ', cleaned)
    cleaned = re.sub(r'[^a-z& ]+', ' ', cleaned)
    tokens = [token for token in cleaned.split() if len(token) > 1]
    if not tokens:
        return (name or 'Unknown').strip().lower()
    return ' '.join(tokens[:4]).strip()


def describe_amount_variation(amounts):
    """Return relative amount variability for a recurring merchant."""
    if not amounts:
        return 0.0
    average = sum(amounts) / len(amounts)
    if average <= 0:
        return 0.0
    return (max(amounts) - min(amounts)) / average


def classify_cadence(intervals):
    """Pick the cadence window that best fits the observed spacing."""
    if not intervals:
        return None, 0.0, None

    best_name = None
    best_ratio = 0.0
    best_typical_interval = None

    for cadence_name, config in CADENCE_WINDOWS.items():
        matching = [days for days in intervals if config['min_days'] <= days <= config['max_days']]
        ratio = len(matching) / len(intervals)
        if ratio > best_ratio:
            best_name = cadence_name
            best_ratio = ratio
            best_typical_interval = round(sum(matching) / len(matching)) if matching else round(sum(intervals) / len(intervals))

    return best_name, best_ratio, best_typical_interval


def score_candidate(keyword_match, amount_variation, cadence_match_ratio, occurrences, recency_ratio):
    """Translate heuristics into a single confidence score."""
    score = 0
    if cadence_match_ratio >= 0.8:
        score += 40
    elif cadence_match_ratio >= 0.5:
        score += 28
    elif cadence_match_ratio > 0:
        score += 16

    if amount_variation <= 0.08:
        score += 22
    elif amount_variation <= 0.18:
        score += 16
    elif amount_variation <= 0.35:
        score += 9

    if keyword_match:
        score += 18

    if occurrences >= 4:
        score += 12
    elif occurrences == 3:
        score += 9
    elif occurrences == 2:
        score += 5

    if recency_ratio <= 1.2:
        score += 8
    elif recency_ratio <= 1.7:
        score += 4

    return min(score, 100)


def get_confidence_label(score):
    if score >= 75:
        return 'high'
    if score >= 55:
        return 'medium'
    return 'low'


def build_reason(occurrences, cadence_name, amount_variation, keyword_match):
    cadence_text = cadence_name or 'recurring'
    stability = 'very stable amounts' if amount_variation <= 0.1 else 'moderately stable amounts'
    keyword_text = ' and matches a common subscription merchant' if keyword_match else ''
    return f'{occurrences} charges on a roughly {cadence_text} schedule with {stability}{keyword_text}.'


def identify_subscriptions(transactions):
    """Identify recurring subscription-like charges from transaction history."""
    if not transactions:
        return {'success': False, 'subscriptions': [], 'summary': {}, 'error': 'No transactions provided'}

    dated_transactions = [item for item in transactions if item.get('datetime')]
    if not dated_transactions:
        return {'success': False, 'subscriptions': [], 'summary': {}, 'error': 'No dated transactions provided'}

    latest_seen_datetime = max(item['datetime'] for item in dated_transactions)

    grouped = defaultdict(list)
    for transaction in transactions:
        amount = transaction.get('amount', 0)
        if amount == 0:
            continue

        merchant = (transaction.get('merchant') or transaction.get('name') or transaction.get('description') or '').strip()
        if not merchant or not transaction.get('datetime'):
            continue

        normalized_name = normalize_merchant_name(merchant)
        merchant_search_text = f"{merchant.lower()} {normalized_name}"
        keyword_match = has_keyword(merchant_search_text, KNOWN_SUBSCRIPTION_KEYWORDS)
        if has_keyword(merchant_search_text, EXCLUDED_KEYWORDS) and not keyword_match:
            continue

        grouped[normalized_name].append(transaction)

    candidates = []

    for normalized_name, merchant_transactions in grouped.items():
        if len(merchant_transactions) < 2:
            continue

        merchant_transactions = sorted(merchant_transactions, key=lambda item: item['datetime'])
        sign_counts = Counter(1 if item.get('amount', 0) >= 0 else -1 for item in merchant_transactions)
        dominant_sign, _ = sign_counts.most_common(1)[0]
        merchant_transactions = [item for item in merchant_transactions if (1 if item.get('amount', 0) >= 0 else -1) == dominant_sign]

        if len(merchant_transactions) < 2:
            continue

        absolute_amounts = [abs(item.get('amount', 0)) for item in merchant_transactions]
        average_amount = sum(absolute_amounts) / len(absolute_amounts)
        if average_amount < 1:
            continue

        intervals = []
        for index in range(1, len(merchant_transactions)):
            delta_days = (merchant_transactions[index]['datetime'] - merchant_transactions[index - 1]['datetime']).days
            if delta_days > 0:
                intervals.append(delta_days)

        cadence_name, cadence_match_ratio, typical_interval = classify_cadence(intervals)
        merchant_search_text = ' '.join(
            (item.get('merchant') or item.get('name') or item.get('description') or '').lower()
            for item in merchant_transactions
        )
        merchant_search_text = f"{merchant_search_text} {normalized_name}"
        keyword_match = has_keyword(merchant_search_text, KNOWN_SUBSCRIPTION_KEYWORDS)
        amount_variation = describe_amount_variation(absolute_amounts)
        occurrences = len(merchant_transactions)

        if has_keyword(merchant_search_text, EXCLUDED_KEYWORDS) and not keyword_match:
            continue

        if cadence_match_ratio == 0 and not (keyword_match and occurrences >= 2 and amount_variation <= MAX_KEYWORD_AMOUNT_VARIATION):
            continue

        if not keyword_match and occurrences < MIN_NON_KEYWORD_OCCURRENCES and cadence_name not in {'quarterly', 'yearly'}:
            continue

        if not keyword_match and average_amount < MIN_NON_KEYWORD_AVERAGE_AMOUNT:
            continue

        if cadence_name in {'weekly', 'biweekly'} and not keyword_match and average_amount < MAX_NON_KEYWORD_WEEKLY_BIWEEKLY_AMOUNT:
            continue

        last_transaction = merchant_transactions[-1]
        if typical_interval:
            next_estimated_date = last_transaction['datetime'] + timedelta(days=typical_interval)
            days_since_last = max((latest_seen_datetime - last_transaction['datetime']).days, 0)
            recency_ratio = days_since_last / typical_interval if typical_interval else 0
        else:
            next_estimated_date = None
            recency_ratio = 0

        score = score_candidate(
            keyword_match=keyword_match,
            amount_variation=amount_variation,
            cadence_match_ratio=cadence_match_ratio,
            occurrences=occurrences,
            recency_ratio=recency_ratio,
        )
        confidence = get_confidence_label(score)

        if confidence == 'low' and not keyword_match:
            continue

        cadence_config = CADENCE_WINDOWS.get(cadence_name or '', {})
        annual_factor = cadence_config.get('annual_factor', 12 if cadence_name == 'monthly' else 1)
        monthly_cost = average_amount * (annual_factor / 12)
        annual_cost = average_amount * annual_factor

        display_name = merchant_transactions[-1].get('merchant') or merchant_transactions[-1].get('name') or normalized_name.title()
        recent_transactions = []
        for item in merchant_transactions[-4:][::-1]:
            recent_transactions.append({
                'date': item['date'],
                'amount': round(abs(item.get('amount', 0)), 2),
                'account_name': item.get('account_name') or item.get('account') or 'Unknown',
            })

        candidates.append({
            'merchant': display_name,
            'normalized_merchant': normalized_name,
            'confidence': confidence,
            'confidence_score': score,
            'cadence': cadence_name or 'irregular',
            'occurrences': occurrences,
            'average_amount': round(average_amount, 2),
            'last_amount': round(abs(last_transaction.get('amount', 0)), 2),
            'last_charge_date': last_transaction['date'],
            'next_estimated_charge_date': next_estimated_date.strftime('%Y-%m-%d') if next_estimated_date else None,
            'monthly_cost_estimate': round(monthly_cost, 2),
            'annual_cost_estimate': round(annual_cost, 2),
            'amount_variation_percent': round(amount_variation * 100, 1),
            'reason': build_reason(occurrences, cadence_name, amount_variation, keyword_match),
            'recent_transactions': recent_transactions,
        })

    candidates.sort(
        key=lambda item: (
            {'high': 2, 'medium': 1, 'low': 0}.get(item['confidence'], 0),
            item['monthly_cost_estimate'],
            item['occurrences'],
        ),
        reverse=True,
    )

    summary = {
        'total_subscriptions': len(candidates),
        'high_confidence_count': sum(1 for item in candidates if item['confidence'] == 'high'),
        'medium_confidence_count': sum(1 for item in candidates if item['confidence'] == 'medium'),
        'total_monthly_spend': round(sum(item['monthly_cost_estimate'] for item in candidates), 2),
        'total_annual_spend': round(sum(item['annual_cost_estimate'] for item in candidates), 2),
    }

    return {
        'success': True,
        'subscriptions': candidates,
        'summary': summary,
        'error': None,
    }
