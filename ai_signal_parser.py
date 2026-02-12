"""
Optional AI-powered signal parser. Set OPENAI_API_KEY in .env to enable.
Uses the model to understand the message and extract trading signal or reject non-signals.
"""
import json
import logging
from typing import Optional

from signal_parser import ParsedSignal

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a trading signal extractor for crypto futures (USDT-margined).
Given a Telegram message, decide if it contains ONE clear trading signal: direction (Long/Short), a coin symbol (e.g. BTC, QTUM, ETH), and optionally a take-profit target number.
- Ignore instruction lines like "dont pick old signal", "ignore old", "only new signals" – they are reminders, not part of the signal.
- If the message is ONLY instructions or noise with no actual signal, return is_signal: false.
- If there is a clear signal, return is_signal: true and fill symbol (e.g. QTUM, BTC), side (long or short), and take_profit (number or null).
- Reply with ONLY a single JSON object, no other text. Example: {"is_signal":true,"symbol":"QTUM","side":"short","take_profit":0.919}
Another: {"is_signal":false}"""


def _call_openai(text: str, api_key: str) -> Optional[dict]:
    """Call OpenAI API (chat completions). Returns parsed JSON dict or None."""
    try:
        import requests
    except ImportError:
        return None
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Message:\n{text[:1500]}"},
        ],
        "temperature": 0.1,
        "max_tokens": 200,
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=15)
        r.raise_for_status()
        data = r.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        if not content:
            return None
        # Extract JSON from response (in case model adds extra text)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())
    except Exception as e:
        logger.warning("AI parser failed: %s", e)
        return None


def parse_signal_ai(text: str, api_key: str) -> Optional[ParsedSignal]:
    """
    Use AI to parse the message. Returns ParsedSignal if the model says it's a signal, else None.
    """
    if not text or not text.strip() or not api_key:
        return None
    out = _call_openai(text.strip(), api_key)
    if not out or not out.get("is_signal"):
        return None
    symbol = (out.get("symbol") or "").strip().upper()
    side = (out.get("side") or "").strip().lower()
    if symbol and side in ("long", "short"):
        # Normalize symbol to BASE_USDT
        s = symbol.upper().strip()
        if not s.endswith("USDT") and "_USDT" not in s:
            s = f"{s}_USDT"
        elif s.endswith("USDT") and "_" not in s:
            s = s.replace("USDT", "_USDT")
        take_profit = out.get("take_profit")
        if take_profit is not None:
            try:
                take_profit = float(take_profit)
            except (TypeError, ValueError):
                take_profit = None
        return ParsedSignal(
            symbol=s,
            side=side,
            position_size_usdt=None,
            leverage=None,
            take_profit=take_profit,
            raw_text=text[:200],
        )
    return None
