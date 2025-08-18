import os
import json
from typing import Any, Dict, Optional, Tuple

import requests


# Basic Ollama configuration via environment variables
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3:4b')


def _post_ollama_generate(payload: Dict[str, Any], timeout_seconds: int = 60) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        parsed = response.json()
        return True, parsed, None
    except Exception as exc:  # Broad except is fine for transport layer
        return False, {}, str(exc)


def generate_text(prompt: str, model: Optional[str] = None, stream: bool = False, system: Optional[str] = None, timeout_seconds: int = 60) -> Dict[str, Any]:
    """Call Ollama to generate plain text.

    Returns a dict: { success: bool, text: str, error: Optional[str] }
    """
    payload = {
        "model": model or OLLAMA_MODEL,
        "prompt": f"{system + '\n\n' if system else ''}{prompt}",
        "stream": bool(stream),
    }

    ok, raw, err = _post_ollama_generate(payload, timeout_seconds=timeout_seconds)
    if not ok:
        return {"success": False, "text": "", "error": err}

    return {"success": True, "text": raw.get("response", ""), "error": None}


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


def generate_json(prompt: str, model: Optional[str] = None, system: Optional[str] = None, timeout_seconds: int = 300) -> Dict[str, Any]:
    """Call Ollama to generate valid JSON.

    Returns a dict: { success: bool, data: Any, raw_text: str, error: Optional[str] }
    """
    payload = {
        "model": model or OLLAMA_MODEL,
        "prompt": f"{system + '\n\n' if system else ''}{prompt}",
        "stream": False,
        # Ollama's `format: "json"` nudges the model to emit JSON; still validate client-side.
        "format": "json",
        "keep_alive": "15m",
    }

    ok, raw, err = _post_ollama_generate(payload, timeout_seconds=timeout_seconds)
    if not ok:
        return {"success": False, "data": None, "raw_text": "", "error": err}

    raw_text = raw.get("response", "")
    parsed = _extract_json_maybe(raw_text)
    if parsed is None:
        return {"success": False, "data": None, "raw_text": raw_text, "error": "Failed to parse JSON from model response"}

    return {"success": True, "data": parsed, "raw_text": raw_text, "error": None}


