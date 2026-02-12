"""
WEEX Contract (Futures) API client.
Places orders and reads positions. Auth: API Key + Secret + Passphrase, HMAC-SHA256 + Base64.
Docs: https://www.weex.com/api-doc/contract/
"""
import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import requests

from config import WEEX_API_KEY, WEEX_SECRET_KEY, WEEX_PASSPHRASE, WEEX_BASE_URL

# WEEX symbol format: cmt_btcusdt (lowercase, cmt_ prefix)
# Order: type 1=buy(long), 2=sell(short); order_type 0=market, 1=limit; match_price 1=market
ORDER_TYPE_MARKET = 0
ORDER_TYPE_LIMIT = 1
SIDE_BUY = 1
SIDE_SELL = 2


def _sign(secret_key: str, timestamp: str, method: str, request_path: str, query_string: str, body: str) -> str:
    """Signature = Base64(HMAC-SHA256(secret, timestamp + method + path + query + body))."""
    message = timestamp + method.upper() + request_path + query_string + body
    sig = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(sig).decode("utf-8")


def _headers(method: str, request_path: str, query_string: str, body: str = "") -> dict[str, str]:
    if not WEEX_API_KEY or not WEEX_SECRET_KEY or not WEEX_PASSPHRASE:
        raise ValueError("WEEX_API_KEY, WEEX_SECRET_KEY, WEEX_PASSPHRASE must be set")
    timestamp = str(int(time.time() * 1000))
    signature = _sign(WEEX_SECRET_KEY, timestamp, method, request_path, query_string, body)
    return {
        "ACCESS-KEY": WEEX_API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": WEEX_PASSPHRASE,
        "Content-Type": "application/json",
        "locale": "en-US",
    }


def to_weex_symbol(symbol: str) -> str:
    """Convert BTC_USDT or BTCUSDT to WEEX USDT-M format: cmt_btcusdt (always USDT-margined)."""
    s = symbol.upper().replace("_", "").replace("USDT", "").strip()
    if not s:
        s = symbol.upper().replace("_", "").replace("USDT", "")
    return f"cmt_{s.lower()}usdt"


def get_last_price(symbol_weex: str) -> float:
    """Get last price from recent trades (public)."""
    url = f"{WEEX_BASE_URL}/capi/v2/market/trades"
    params = {"symbol": symbol_weex, "limit": 1}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list) and data:
        return float(data[0].get("price", 0))
    raise RuntimeError(f"WEEX trades unexpected response: {data}")


def place_order(
    symbol: str,
    position_type: int,
    size: float,
    order_type: int = ORDER_TYPE_MARKET,
    price: float | None = None,
) -> dict[str, Any]:
    """
    Place a USDT-M futures order on WEEX with isolated margin.
    symbol: e.g. "BTC_USDT" -> cmt_btcusdt (USDT-M only)
    position_type: 1=long (buy), 2=short (sell)
    size: order size in base currency (e.g. BTC amount)
    order_type: 0=market, 1=limit
    price: required for limit orders
    """
    symbol_weex = to_weex_symbol(symbol)
    side = SIDE_BUY if position_type == 1 else SIDE_SELL
    body: dict[str, Any] = {
        "symbol": symbol_weex,
        "client_oid": str(uuid.uuid4()).replace("-", "")[:24],
        "size": str(round(size, 8)),
        "type": str(side),
        "order_type": str(order_type),
        "match_price": "1" if order_type == ORDER_TYPE_MARKET else "0",
    }
    if order_type == ORDER_TYPE_LIMIT and price is not None:
        body["price"] = str(price)
    # Isolated margin: set per contract in WEEX app (Account → Contract → Leverage/Margin).
    # We only trade USDT-M (cmt_*usdt). WEEX_ISOLATED_MARGIN is for documentation; add body param when API supports it.
    body_str = json.dumps(body, separators=(",", ":"))
    request_path = "/capi/v2/order/placeOrder"
    url = f"{WEEX_BASE_URL}{request_path}"
    headers = _headers("POST", request_path, "", body_str)
    r = requests.post(url, headers=headers, data=body_str, timeout=30)
    out = r.json()
    if r.status_code != 200:
        raise RuntimeError(f"WEEX order failed: {r.status_code} {out}")
    if isinstance(out, dict) and (out.get("code") not in (None, 0, "0", 200)):
        raise RuntimeError(f"WEEX order error: {out}")
    return out


def get_open_positions(symbol: str | None = None) -> list[dict[str, Any]]:
    """Get current open positions. Optional symbol filter (WEEX format or BTC_USDT)."""
    request_path = "/capi/v2/account/position/singlePosition"
    query = f"?symbol={to_weex_symbol(symbol)}" if symbol else ""
    url = f"{WEEX_BASE_URL}{request_path}{query}" if query else f"{WEEX_BASE_URL}{request_path}"
    headers = _headers("GET", request_path, query)
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        return [data] if data.get("symbol") else []
    if isinstance(data, list):
        return data
    return []


def usdt_to_size(symbol: str, position_size_usdt: float) -> float:
    """
    Convert USDT notional to base currency size (e.g. USDT -> BTC amount).
    size_base = position_size_usdt / price
    """
    symbol_weex = to_weex_symbol(symbol)
    price = get_last_price(symbol_weex)
    if not price or price <= 0:
        raise ValueError(f"Invalid price for {symbol}: {price}")
    size = position_size_usdt / price
    # Round to 8 decimals to avoid precision issues
    return round(size, 8)


def set_take_profit(
    symbol: str,
    position_type: int,
    size: float,
    trigger_price: float,
) -> dict[str, Any] | None:
    """
    Set take-profit for an open position at trigger_price.
    WEEX: TP is position-based; implement via their plan/trigger order API when available.
    Returns None until endpoint is implemented; caller should log target for manual set.
    """
    # TODO: WEEX contract API for TP - check /capi/v2/order/ placePlanOrder or similar
    return None
