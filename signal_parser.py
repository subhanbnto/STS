"""
Parse trading signals from Telegram message text.
Extracts symbol, side (long/short), and optional size/leverage.
Supports instruction-line filtering and optional AI parsing.
"""
import re
from dataclasses import dataclass
from typing import Optional

# Lines matching these patterns are ignored (e.g. "dont pick old signal")
INSTRUCTION_LINE_PATTERNS = [
    r"dont?\s*pick\s*old",
    r"don'?t\s*pick\s*old",
    r"do\s*not\s*pick\s*old",
    r"ignore\s*old\s*signal",
    r"ignore\s*old",
    r"no\s*old\s*signal",
    r"only\s*new\s*signal",
    r"wait\s*for\s*new",
]

# Common futures symbols (BASE_USDT)
COMMON_SYMBOLS = {
    "btc", "eth", "bnb", "sol", "xrp", "doge", "ada", "avax", "link",
    "dot", "matic", "uni", "atom", "ltc", "etc", "fil", "apt", "arb",
    "op", "sui", "pepe", "wif", "bonk", "not", "trump", "qtum", "etc",
    "xlm", "near", "ftm", "sand", "mana", "axs", "gala", "hbar", "vet",
}


@dataclass
class ParsedSignal:
    symbol: str          # e.g. "BTC_USDT"
    side: str            # "long" or "short"
    position_size_usdt: Optional[float] = None
    leverage: Optional[int] = None
    take_profit: Optional[float] = None   # target price for TP
    raw_text: str = ""

    def mexc_symbol(self) -> str:
        """Return MEXC futures symbol (e.g. BTC_USDT)."""
        base = self.symbol.upper().replace("USDT", "").strip("_")
        if not base:
            base = self.symbol.upper()
        if "_" in base:
            return base
        return f"{base}_USDT"

    def is_long(self) -> bool:
        return self.side.lower() == "long"

    def position_type_int(self) -> int:
        """1=long, 2=short for MEXC."""
        return 1 if self.is_long() else 2


def _normalize_symbol(s: str) -> str:
    s = s.upper().strip()
    if "/" in s:
        base = s.split("/")[0].strip()
        return f"{base}_USDT"
    if s.endswith("USDT") or s.endswith("_USDT"):
        return s if "_" in s else s.replace("USDT", "_USDT")
    return f"{s}_USDT"


def _parse_structured_signal(text: str) -> Optional[ParsedSignal]:
    """
    Parse structured format (blank lines between parts are OK):
      Short
      QTUM
      Target
      0.919
    (or Long, then symbol, then Target then price)
    """
    # Normalize line endings and drop blank/whitespace-only lines
    raw_lines = text.strip().replace("\r\n", "\n").replace("\r", "\n").split("\n")
    stripped = [ln.strip() for ln in raw_lines if ln and ln.strip()]
    # Drop instruction lines (e.g. "dont pick old signal") so they don't break parsing
    lines = [
        ln for ln in stripped
        if not any(re.search(p, ln, re.I) for p in INSTRUCTION_LINE_PATTERNS)
    ]
    if len(lines) < 2:
        return None
    first = lines[0].lower()
    if first == "long":
        is_long = True
    elif first == "short":
        is_long = False
    else:
        return None
    # Second line = symbol (e.g. QTUM, BTC)
    symbol_raw = lines[1].upper()
    if symbol_raw in ("LONG", "SHORT", "TARGET", "BUY", "SELL"):
        return None
    symbol = _normalize_symbol(symbol_raw)
    # Find Target and price (next line or same line: "Target 0.919" / "Target: 0.919")
    take_profit = None
    for i, ln in enumerate(lines):
        if re.match(r"^target\s*[:\s]*$", ln, re.I) and i + 1 < len(lines):
            try:
                take_profit = float(lines[i + 1].replace(",", "").strip())
            except ValueError:
                pass
            break
        m = re.search(r"target\s*[:\s]*(\d+(?:\.\d+)?)", ln, re.I)
        if m:
            take_profit = float(m.group(1))
            break
    return ParsedSignal(
        symbol=symbol,
        side="long" if is_long else "short",
        position_size_usdt=None,
        leverage=None,
        take_profit=take_profit,
        raw_text=text[:200],
    )


def parse_signal(text: str) -> Optional[ParsedSignal]:
    """
    Try to parse a trading signal from message text.
    If OPENAI_API_KEY is set, tries AI parsing first; otherwise uses rule-based only.
    Supports structured format (Short/Long + symbol + Target + price) and free-form.
    Instruction lines (e.g. "dont pick old signal") are filtered in structured parse and understood by AI.
    """
    if not text or not text.strip():
        return None
    text = text.strip()
    text_lower = text.lower()

    # Optional: AI parser when API key is set (understands instructions like "dont pick old signal")
    try:
        from config import OPENAI_API_KEY
        if OPENAI_API_KEY:
            from ai_signal_parser import parse_signal_ai
            ai_signal = parse_signal_ai(text, OPENAI_API_KEY)
            if ai_signal is not None:
                return ai_signal
    except Exception:
        pass  # fall back to rule-based

    # Try structured format first: "Short\nQTUM\nTarget\n0.919" or "Long\nBTC\nTarget\n50000"
    structured = _parse_structured_signal(text)
    if structured is not None:
        return structured

    # Free-form: detect side
    long_patterns = [
        r"\blong\b", r"\bbuy\b", r"\bcall\b", r"\b🟢\b", r"\b🟩\b",
        r"⬆", r"bullish", r"bull\b", r"📈",
    ]
    short_patterns = [
        r"\bshort\b", r"\bsell\b", r"\bput\b", r"\b🔴\b", r"\b🟥\b",
        r"⬇", r"bearish", r"bear\b", r"📉",
    ]
    is_long = None
    for p in long_patterns:
        if re.search(p, text_lower, re.I):
            is_long = True
            break
    if is_long is None:
        for p in short_patterns:
            if re.search(p, text_lower, re.I):
                is_long = False
                break
    if is_long is None:
        return None

    # Extract symbol
    symbol = None
    m = re.search(r"[$#](\w{2,10})\b", text, re.I)
    if m:
        symbol = _normalize_symbol(m.group(1))
    if not symbol:
        m = re.search(r"(\w{2,10})\s*[/_]\s*USDT", text, re.I)
        if m:
            symbol = _normalize_symbol(m.group(1))
    if not symbol:
        for word in re.findall(r"\b[A-Z]{2,10}\b", text.upper()):
            if word in ("LONG", "SHORT", "BUY", "SELL", "USDT"):
                continue
            if word.lower() in COMMON_SYMBOLS or len(word) <= 5:
                symbol = _normalize_symbol(word)
                break
    if not symbol:
        for ticker in COMMON_SYMBOLS:
            if re.search(rf"\b{ticker}\b", text_lower):
                symbol = _normalize_symbol(ticker)
                break
    if not symbol:
        return None

    # Optional: Target / take profit (e.g. "Target 0.919", "Target: 0.919", or "Target"\n"0.919")
    take_profit = None
    m = re.search(r"target\s*[:\s]*(\d+(?:\.\d+)?)", text_lower)
    if m:
        take_profit = float(m.group(1))

    # Optional: position size in USDT
    size_usdt = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:usdt|usd|\$)", text_lower)
    if m:
        size_usdt = float(m.group(1))
    if not size_usdt:
        m = re.search(r"(?:usdt|usd|\$)\s*(\d+(?:\.\d+)?)", text_lower)
        if m:
            size_usdt = float(m.group(1))

    # Optional: leverage (e.g. 5x, 10x)
    leverage = None
    m = re.search(r"(\d{1,3})\s*[xX]", text)
    if m:
        leverage = int(m.group(1))

    return ParsedSignal(
        symbol=symbol,
        side="long" if is_long else "short",
        position_size_usdt=size_usdt,
        leverage=leverage,
        take_profit=take_profit,
        raw_text=text[:200],
    )
