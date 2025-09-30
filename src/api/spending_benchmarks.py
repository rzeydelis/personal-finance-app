from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json
import re
import sys


def _get_llm_generate_json():
    """Try to import the local LLM JSON generator (Ollama)."""
    # Try relative to web module first
    try:
        from ..web.llms import generate_json as llm_generate_json  # type: ignore
        return llm_generate_json
    except Exception:
        pass
    # Try adding src/web to path
    web_path = Path(__file__).parent.parent / 'web'
    if str(web_path) not in sys.path:
        sys.path.append(str(web_path))
    try:
        from llms import generate_json as llm_generate_json  # type: ignore
        return llm_generate_json
    except Exception:
        return None


def normalize_category(name: str) -> str:
    """
    Normalize a category label to a small canonical set.
    """
    n = (name or "").strip().lower()
    # Common aliases
    if n in {"dining", "restaurants", "eating out", "food_out"}:
        return "dining_out"
    if n in {"auto_insurance", "car", "car insurance", "auto"}:
        return "car_insurance"
    if n in {"grocery", "supermarket", "food_home"}:
        return "groceries"
    if n in {"utility", "power", "electric", "gas", "water", "internet", "cable"}:
        return "utilities"
    return re.sub(r"[^a-z0-9_]+", "_", n) or "other"


# Very lightweight merchant keyword classifier to get started
_MERCHANT_TO_CATEGORY: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(geico|state\s*farm|progressive|allstate|liberty\s*mutual|njm)\b", re.I), "car_insurance"),
    (re.compile(r"\b(chipotle|mcdonald|burger\s*king|wendy|starbucks|dunkin|panera|taco\s*bell|doordash|ubereats|grubhub)\b", re.I), "dining_out"),
    (re.compile(r"\b(whole\s*foods|trader\s*joe|kroger|heb|publix|shoprite|acme|stop\s*&\s*shop|costco|walmart)\b", re.I), "groceries"),
    (re.compile(r"\b(pseg|coned|edison|verizon|comcast|xfinity|spectrum|at\&t|att|nj\s*gas|nj\s*water)\b", re.I), "utilities"),
]


def classify_transaction(merchant: str, description: str = "", explicit_category: Optional[str] = None) -> str:
    """
    Map a transaction to a coarse category for benchmarking.
    Priority: explicit_category -> merchant keywords -> description keywords -> other
    """
    if explicit_category:
        return normalize_category(explicit_category)
    text = f"{merchant or ''} {description or ''}"
    for pat, cat in _MERCHANT_TO_CATEGORY:
        if pat.search(text):
            return cat
    return "other"


def monthly_spend_by_category(transactions: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Aggregate absolute monthly spending per category.
    Assumes charges are negative amounts; treats amount<0 as spend.
    """
    totals: Dict[str, float] = {}
    for t in transactions:
        amt = float(t.get("amount", 0) or 0)
        if amt >= 0:
            continue  # ignore income/refunds
        cat = classify_transaction(t.get("merchant") or t.get("name", ""), t.get("description", ""), t.get("category"))
        totals[cat] = totals.get(cat, 0.0) + abs(amt)
    return totals


def compare_to_benchmarks_rule_of_thumb(user_spend: Dict[str, float], state: Optional[str] = None, categories: Optional[List[str]] = None) -> Dict[str, Any]:
    """Very rough fallback comparison if LLM is unavailable. Uses broad national heuristics only."""
    region = (state or "US").strip().upper()
    # Very rough placeholders to provide some signal without external data
    baseline = {
        "car_insurance": 175.0,
        "dining_out": 280.0,
        "groceries": 500.0,
        "utilities": 210.0,
    }
    cats = categories or list(set(list(user_spend.keys()) + list(baseline.keys())))
    comparisons: List[Dict[str, Any]] = []
    for c in cats:
        cat = normalize_category(c)
        user_val = float(user_spend.get(cat, 0.0))
        avg_val = float(baseline.get(cat, 0.0))
        if avg_val <= 0 and user_val <= 0:
            continue
        diff = user_val - avg_val
        pct = (diff / avg_val * 100.0) if avg_val > 0 else None
        msg = None
        if pct is not None and abs(pct) >= 10:
            polarity = "more" if pct > 0 else "less"
            msg = f"You are spending {abs(pct):.0f}% {polarity} than a rough national average on {cat.replace('_',' ')}."
        comparisons.append({
            "category": cat,
            "user_monthly": round(user_val, 2),
            "estimated_average_monthly": round(avg_val, 2),
            "difference": round(diff, 2),
            "percent_diff": round(pct, 1) if pct is not None else None,
            "region": region,
            "insight": msg,
        })
    comparisons.sort(key=lambda x: abs(x.get("percent_diff") or 0), reverse=True)
    highlights = [c for c in comparisons if c.get("insight")][:3]
    return {
        "region": region,
        "comparisons": comparisons,
        "highlights": highlights,
        "disclaimer": "LLM unavailable. Using rough national heuristics; may be inaccurate.",
    }


def generate_benchmark_comparison_with_llm(user_spend: Dict[str, float], state: Optional[str] = None, categories: Optional[List[str]] = None) -> Dict[str, Any]:
    """Use the local LLM to estimate typical monthly spend by region and compare to user's spending."""
    llm_generate_json = _get_llm_generate_json()
    if llm_generate_json is None:
        return compare_to_benchmarks_rule_of_thumb(user_spend, state=state, categories=categories)

    region = (state or "US").strip().upper()
    cats = categories or list(user_spend.keys())

    # Build prompt
    summary_lines = [f"- {c}: ${user_spend[c]:.2f}" for c in cats]
    user_spend_json = json.dumps({c: round(float(user_spend.get(c, 0.0)), 2) for c in cats})

    prompt = f"""
You are a personal finance analyst. Compare a user's recent monthly spending to typical averages for households in the specified US state (or national if unknown).

State/Region: {region}

User monthly spending by category (USD):
{user_spend_json}

Tasks:
- For each category, estimate a reasonable average monthly spend for typical households in {region} (or US if state is unknown). If you are uncertain, provide a conservative estimate and set confidence to "low".
- Compute difference and percent_diff = (user - average) / average * 100.
- Provide a one‑sentence insight for each category. Keep it neutral and actionable.
- Create up to 3 short highlight messages only for categories where abs(percent_diff) >= 10.
- Include a brief disclaimer noting that these are estimates, not advice, and to verify with official sources.

Output strictly as JSON with this schema:
{{
  "region": "{region}",
  "comparisons": [
    {{
      "category": "<string>",
      "user_monthly": <number>,
      "estimated_average_monthly": <number>,
      "difference": <number>,
      "percent_diff": <number>,
      "confidence": "low"|"medium"|"high",
      "insight": "<short sentence>"
    }}
  ],
  "highlights": ["<short message>", "..."],
  "disclaimer": "<string>"
}}

Return ONLY JSON, no markdown, no extra text.
"""

    result = llm_generate_json(prompt)
    if result.get("success"):
        data = result.get("data") or {}
        # Ensure region field present
        data.setdefault("region", region)
        return data
    # Fallback
    return compare_to_benchmarks_rule_of_thumb(user_spend, state=state, categories=categories)
