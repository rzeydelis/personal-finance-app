import re
from collections import defaultdict
from datetime import datetime


INFLOW_KEYWORDS = (
    'PAYROLL',
    'DIRECT DEP',
    'DEPOSIT',
    'REFUND',
    'INTEREST',
    'REIMBURSE',
    'VENMO CASHOUT',
    'ZELLE FROM',
    'TRANSFER FROM',
    'ACH CREDIT',
    'RETURN',
)

INTERNAL_MOVE_KEYWORDS = (
    'AUTOPAY',
    'PAYMENT',
    'TRANSFER',
    'VANGUARD',
    'GEMINI',
    'INVESTMENT',
    'CRCARDPMT',
    'CREDIT CRD',
    'THANK',
    'ACH DEBIT',
    'ONLINE PMT',
)

SAVINGS_KEYWORDS = (
    'VANGUARD',
    'GEMINI',
    'COINBASE',
    'ROBINHOOD',
    'FIDELITY',
    'SCHWAB',
    'BETTERMENT',
    'WEALTHFRONT',
    'ACORNS',
)

WITHDRAWAL_REGEX_PATTERNS = (
    r'\bWITHDRAW(?:AL)?\b',
    r'\bATM\b',
    r'\bCASH\s*OUT\b',
    r'\bCASH\s*WDL?\b',
)

VANGUARD_SELL_INFLOW_PATTERNS = (
    r'\bVANGUARD\b.*\bSELL\b',
    r'\bSELL\b.*\bVANGUARD\b',
    r'\bVANGUARD\b.*\bREDEMP(?:TION)?\b',
    r'\bREDEMP(?:TION)?\b.*\bVANGUARD\b',
)

SAVINGS_OFFSET_TRANSACTION_NAMES = (
    'VANGUARD SELL INVESTMENT',
)


def format_currency(value):
    return f"${value:,.2f}"


def format_signed_currency(value):
    prefix = '+' if value >= 0 else '-'
    return f"{prefix}${abs(value):,.2f}"


def humanize_month(month_key):
    try:
        return datetime.strptime(month_key, '%Y-%m').strftime('%b %Y')
    except ValueError:
        return month_key


def merchant_text(transaction):
    return f"{transaction.get('merchant') or transaction.get('name') or transaction.get('description') or 'Unknown'}".strip()


def normalize_merchant_name(name):
    normalized = re.sub(r'\s+', ' ', (name or '').upper()).strip()
    if not normalized:
        return 'UNKNOWN'

    if normalized.startswith('AMAZON MKTPL*') or normalized.startswith('AMZN MKTP'):
        return 'AMAZON'
    if normalized.startswith('TST* '):
        normalized = normalized[5:]
    if normalized.startswith('SQ *'):
        normalized = normalized[4:]
    if normalized.startswith('PAYPAL *'):
        normalized = normalized[8:]

    normalized = re.sub(r'\b\d{4,}\b', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip(' -')
    return normalized or 'UNKNOWN'


def has_keyword(text, keywords):
    upper = (text or '').upper()
    return any(keyword in upper for keyword in keywords)


def detect_outflow_sign(transactions):
    positive = [trx for trx in transactions if float(trx.get('amount') or 0) > 0]
    negative = [trx for trx in transactions if float(trx.get('amount') or 0) < 0]

    if not positive:
        return -1
    if not negative:
        return 1

    positive_inflow_hits = sum(1 for trx in positive if has_keyword(merchant_text(trx), INFLOW_KEYWORDS))
    negative_inflow_hits = sum(1 for trx in negative if has_keyword(merchant_text(trx), INFLOW_KEYWORDS))

    if negative_inflow_hits > positive_inflow_hits:
        return 1
    if positive_inflow_hits > negative_inflow_hits:
        return -1

    return 1 if len(positive) >= len(negative) else -1


def is_internal_money_move(transaction):
    text = merchant_text(transaction)
    return has_keyword(text, INTERNAL_MOVE_KEYWORDS) or has_keyword(text, INFLOW_KEYWORDS)


def is_withdrawal_transaction(transaction):
    text = merchant_text(transaction).upper()
    return any(re.search(pattern, text) for pattern in WITHDRAWAL_REGEX_PATTERNS)


def is_vanguard_sell_inflow(transaction, outflow_sign):
    """Detect Vanguard sell/redemption inflows that should offset savings."""
    raw_amount = float(transaction.get('amount') or 0)
    if raw_amount * outflow_sign >= 0:
        return False

    text = re.sub(r'\s+', ' ', merchant_text(transaction).upper()).strip()
    if text in SAVINGS_OFFSET_TRANSACTION_NAMES:
        return True

    return any(re.search(pattern, text) for pattern in VANGUARD_SELL_INFLOW_PATTERNS)


def is_savings_allocation(transaction):
    """Detect amounts that should count toward savings rather than expenditure."""
    text = merchant_text(transaction).upper()
    return has_keyword(text, SAVINGS_KEYWORDS)


def build_monthly_spend_summary(categorized_transactions, savings_transactions, vanguard_sell_inflow_transactions=None):
    """Build a month-level spending and savings summary."""
    total_spend_amount = sum(abs(float(trx.get('amount') or 0)) for trx in categorized_transactions)
    gross_savings_amount = sum(abs(float(trx.get('amount') or 0)) for trx in savings_transactions)
    vanguard_sell_inflow_amount = sum(
        abs(float(trx.get('amount') or 0))
        for trx in (vanguard_sell_inflow_transactions or [])
    )
    net_savings_amount = gross_savings_amount - vanguard_sell_inflow_amount

    category_summary = {}
    merchant_totals = defaultdict(float)
    for trx in categorized_transactions:
        category = (trx.get('category') or 'Other').strip() or 'Other'
        amount = abs(float(trx.get('amount') or 0))
        merchant_name = merchant_text(trx)

        if category not in category_summary:
            category_summary[category] = {'count': 0, 'total': 0.0, 'merchants': defaultdict(float)}

        category_summary[category]['count'] += 1
        category_summary[category]['total'] += amount
        category_summary[category]['merchants'][merchant_name] += amount
        merchant_totals[merchant_name] += amount

    category_breakdown = []
    for category, stats in sorted(category_summary.items(), key=lambda item: item[1]['total'], reverse=True):
        top_merchants = sorted(stats['merchants'].items(), key=lambda item: item[1], reverse=True)[:3]
        category_breakdown.append(
            {
                'category': category,
                'transaction_count': stats['count'],
                'total': {
                    'amount': round(stats['total'], 2),
                    'display': format_currency(stats['total']),
                },
                'share_percent': round((stats['total'] / total_spend_amount * 100), 1) if total_spend_amount else 0.0,
                'top_merchants': [
                    {
                        'name': name,
                        'amount': round(amount, 2),
                        'display': format_currency(amount),
                    }
                    for name, amount in top_merchants
                ],
            }
        )

    top_merchants = sorted(merchant_totals.items(), key=lambda item: item[1], reverse=True)[:10]

    return {
        'total_expenditure': {
            'amount': round(total_spend_amount, 2),
            'display': format_currency(total_spend_amount),
        },
        'total_savings': {
            'amount': round(net_savings_amount, 2),
            'display': format_signed_currency(net_savings_amount),
        },
        'total_savings_gross': {
            'amount': round(gross_savings_amount, 2),
            'display': format_currency(gross_savings_amount),
        },
        'vanguard_sell_inflows_offset': {
            'amount': round(vanguard_sell_inflow_amount, 2),
            'display': format_currency(vanguard_sell_inflow_amount),
        },
        'category_count': len(category_breakdown),
        'top_category': category_breakdown[0]['category'] if category_breakdown else None,
        'category_breakdown': category_breakdown,
        'top_merchants': [
            {
                'name': name,
                'amount': round(amount, 2),
                'display': format_currency(amount),
            }
            for name, amount in top_merchants
        ],
    }


def build_transaction_summary(transactions, lookback_days):
    """Build a deterministic summary so the UI can show richer insights."""
    if not transactions:
        return {}

    ordered = sorted(
        [trx for trx in transactions if trx.get('datetime')],
        key=lambda trx: trx['datetime'],
    )
    if not ordered:
        return {}

    outflow_sign = detect_outflow_sign(ordered)
    outflows = [trx for trx in ordered if float(trx.get('amount') or 0) * outflow_sign > 0]
    inflows = [trx for trx in ordered if float(trx.get('amount') or 0) * outflow_sign < 0]

    filtered_spend = [trx for trx in outflows if not is_internal_money_move(trx)]
    spend_transactions = filtered_spend if len(filtered_spend) >= 3 else outflows
    if not spend_transactions:
        spend_transactions = ordered

    gross_outflow = sum(abs(float(trx.get('amount') or 0)) for trx in outflows)
    total_spend = sum(abs(float(trx.get('amount') or 0)) for trx in spend_transactions)
    total_inflow = sum(abs(float(trx.get('amount') or 0)) for trx in inflows)
    internal_moves_total = max(gross_outflow - total_spend, 0)

    active_dates = {trx['date'] for trx in spend_transactions if trx.get('date')}
    active_days = len(active_dates) or 1
    avg_daily_spend = total_spend / active_days
    net_flow = total_inflow - gross_outflow

    largest_expense = max(spend_transactions, key=lambda trx: abs(float(trx.get('amount') or 0)))
    largest_expense_amount = abs(float(largest_expense.get('amount') or 0))

    daily_totals = defaultdict(lambda: {'amount': 0.0, 'count': 0})
    for trx in spend_transactions:
        date_key = trx.get('date') or 'Unknown'
        daily_totals[date_key]['amount'] += abs(float(trx.get('amount') or 0))
        daily_totals[date_key]['count'] += 1
    peak_spend_day_key, peak_spend_day_data = max(
        daily_totals.items(),
        key=lambda item: item[1]['amount'],
    )

    merchant_rollup = {}
    for trx in spend_transactions:
        raw_name = merchant_text(trx)
        key = normalize_merchant_name(raw_name)
        amount = abs(float(trx.get('amount') or 0))
        if key not in merchant_rollup:
            merchant_rollup[key] = {
                'merchant': raw_name,
                'count': 0,
                'amount': 0.0,
            }
        merchant_rollup[key]['count'] += 1
        merchant_rollup[key]['amount'] += amount

    ranked_merchants = sorted(
        merchant_rollup.values(),
        key=lambda item: (item['amount'], item['count']),
        reverse=True,
    )
    merchant_leaderboard = [
        {
            'merchant': item['merchant'],
            'count': item['count'],
            'amount': round(item['amount'], 2),
            'display': format_currency(item['amount']),
            'share_percent': round((item['amount'] / total_spend * 100), 1) if total_spend else 0,
        }
        for item in ranked_merchants[:5]
    ]

    recurring_watchlist = [
        {
            'merchant': item['merchant'],
            'count': item['count'],
            'amount': round(item['amount'], 2),
            'display': format_currency(item['amount']),
            'average_display': format_currency(item['amount'] / item['count']),
            'note': f"{item['count']} hits averaging {format_currency(item['amount'] / item['count'])}",
        }
        for item in ranked_merchants
        if item['count'] >= 2
    ][:5]

    monthly_totals = defaultdict(float)
    for trx in spend_transactions:
        monthly_totals[trx['datetime'].strftime('%Y-%m')] += abs(float(trx.get('amount') or 0))
    sorted_months = sorted(monthly_totals.items())
    monthly_comparison = {'available': False}
    if len(sorted_months) >= 2:
        previous_month, previous_total = sorted_months[-2]
        current_month, current_total = sorted_months[-1]
        change_amount = current_total - previous_total
        change_percent = (change_amount / previous_total * 100) if previous_total else None
        monthly_comparison = {
            'available': True,
            'current_month': humanize_month(current_month),
            'previous_month': humanize_month(previous_month),
            'current_total': round(current_total, 2),
            'current_display': format_currency(current_total),
            'previous_total': round(previous_total, 2),
            'previous_display': format_currency(previous_total),
            'change_amount': round(change_amount, 2),
            'change_display': format_signed_currency(change_amount),
            'change_percent': round(change_percent, 1) if change_percent is not None else None,
            'direction': 'up' if change_amount > 0 else 'down' if change_amount < 0 else 'flat',
            'summary': (
                f"{humanize_month(current_month)} was {format_signed_currency(change_amount)} "
                f"({round(change_percent, 1)}%) versus {humanize_month(previous_month)}"
                if change_percent is not None
                else f"{humanize_month(current_month)} moved {format_signed_currency(change_amount)} "
                f"versus {humanize_month(previous_month)}"
            ),
        }

    story_cards = [
        {
            'eyebrow': 'Burn Rate',
            'headline': f"{format_currency(total_spend)} moved through everyday spending",
            'detail': f"That landed across {len(spend_transactions)} purchases in {active_days} active days, or about {format_currency(avg_daily_spend)} per day.",
        },
        {
            'eyebrow': 'Largest Hit',
            'headline': f"{merchant_text(largest_expense)} took {format_currency(largest_expense_amount)}",
            'detail': f"The largest single expense landed on {largest_expense.get('date') or 'an unknown date'}.",
        },
        {
            'eyebrow': 'Peak Spend Day',
            'headline': f"{peak_spend_day_key} reached {format_currency(peak_spend_day_data['amount'])}",
            'detail': f"That came from {peak_spend_day_data['count']} separate transactions hitting on the same day.",
        },
    ]
    if monthly_comparison.get('available'):
        story_cards.append(
            {
                'eyebrow': 'Monthly Swing',
                'headline': monthly_comparison['summary'],
                'detail': f"{monthly_comparison['current_month']} closed at {monthly_comparison['current_display']}.",
            }
        )
    elif internal_moves_total > 0:
        story_cards.append(
            {
                'eyebrow': 'Hidden Weight',
                'headline': f"{format_currency(internal_moves_total)} went to transfers or payments",
                'detail': "That separates daily spending habits from money moving between accounts or cards.",
            }
        )

    return {
        'transaction_count': len(ordered),
        'spend_transaction_count': len(spend_transactions),
        'active_days': active_days,
        'lookback_days': lookback_days,
        'spend_direction': 'positive' if outflow_sign > 0 else 'negative',
        'total_spend': {
            'amount': round(total_spend, 2),
            'display': format_currency(total_spend),
        },
        'gross_outflow': {
            'amount': round(gross_outflow, 2),
            'display': format_currency(gross_outflow),
        },
        'total_inflow': {
            'amount': round(total_inflow, 2),
            'display': format_currency(total_inflow),
        },
        'net_flow': {
            'amount': round(net_flow, 2),
            'display': format_signed_currency(net_flow),
        },
        'avg_daily_spend': {
            'amount': round(avg_daily_spend, 2),
            'display': format_currency(avg_daily_spend),
        },
        'internal_moves_total': {
            'amount': round(internal_moves_total, 2),
            'display': format_currency(internal_moves_total),
        },
        'largest_expense': {
            'merchant': merchant_text(largest_expense),
            'date': largest_expense.get('date'),
            'amount': round(largest_expense_amount, 2),
            'display': format_currency(largest_expense_amount),
        },
        'peak_spend_day': {
            'date': peak_spend_day_key,
            'amount': round(peak_spend_day_data['amount'], 2),
            'display': format_currency(peak_spend_day_data['amount']),
            'transaction_count': peak_spend_day_data['count'],
        },
        'merchant_leaderboard': merchant_leaderboard,
        'recurring_watchlist': recurring_watchlist,
        'monthly_comparison': monthly_comparison,
        'story_cards': story_cards,
    }

