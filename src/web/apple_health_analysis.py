import json

try:
    from .llms import generate_json as llm_generate_json
except Exception:
    from llms import generate_json as llm_generate_json


def generate_apple_health_analysis(health_summary, openai_api_key=None, model=None):
    """Analyze parsed Apple Health data with OpenAI and return structured insights."""
    if not llm_generate_json:
        return {"success": False, "analysis": {}, "error": "LLM not available"}

    if not openai_api_key:
        return {"success": False, "analysis": {}, "error": "OpenAI API key is required"}

    summary_payload = json.dumps(health_summary, indent=2)

    system_prompt = """You are a health and wellness data analyst reviewing Apple Health exports.
Use only the provided summary data. Do not diagnose medical conditions or claim certainty that the data cannot support.
Keep recommendations practical, non-alarmist, and grounded in trends visible in the data.
If a metric is missing or sparse, say that clearly.
Return ONLY valid JSON."""

    prompt = f"""Analyze this Apple Health summary for the most recent {health_summary.get('lookback_days', 90)} days.

Parsed Apple Health summary:
{summary_payload}

Return JSON in this exact format:
{{
  "summary": {{
    "headline": "Short title",
    "overview": "2-4 sentence plain-English summary of the biggest patterns in the data"
  }},
  "metric_highlights": [
    {{
      "metric": "Average daily steps",
      "value": "8,420 steps/day",
      "trend": "Up 12% versus the prior week",
      "insight": "Brief interpretation tied directly to the parsed data"
    }}
  ],
  "strengths": [
    "One positive pattern supported by the data"
  ],
  "watchouts": [
    "One caution or inconsistency supported by the data"
  ],
  "recommendations": [
    {{
      "title": "Action title",
      "priority": "high",
      "why_it_matters": "Why this action is relevant based on the data",
      "next_step": "Concrete next step for the user"
    }}
  ],
  "workout_story": "Short summary of workout consistency and mix, or state that workout data is limited",
  "disclaimer": "Short note that this is informational only and not medical advice"
}}

Rules:
1. Include 3 to 5 metric highlights when the data supports them.
2. Include 2 to 4 recommendations.
3. Priority must be one of: high, medium, low.
4. Keep the tone practical and specific.
5. Do not invent metrics, symptoms, diagnoses, or lab values.
6. If the data coverage is thin, say so directly in the overview or watchouts.
"""

    result = llm_generate_json(
        prompt,
        model=model,
        system=system_prompt,
        timeout_seconds=180,
        openai_api_key=openai_api_key,
        use_openai=True,
    )

    if not result.get("success"):
        return {
            "success": False,
            "analysis": {},
            "error": result.get("error", "Failed to analyze Apple Health data"),
        }

    return {
        "success": True,
        "analysis": result.get("data", {}),
        "error": None,
    }
