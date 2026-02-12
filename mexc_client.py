"""
MEXC Futures API client.
Places orders and reads positions/account using OPEN-API auth (ApiKey + Signature).
Docs: https://www.mexc.com/api-docs/futures/
"""
import hashlib
import hmac
import json
import time
from typing import Any

import requests

from config import (
    MEXC_API_KEY,
    MEXC_API_SECRET,
    MEXC_BASE_URL,
    MEXC_OPEN_TYPE,
    DEFAULT_LEVERAGE,
)


def _sign(access_key: str, secret_key: str, timestamp: str, body: str) -> str:
    """HMAC-SHA256 signature: accessKey + timestamp + body (for POST, body is JSON string)."""
    to_sign = access_key + timestamp + body
    return hmac.new(
        secret_key.encode("utf-8"),
        to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _headers(body: str | None = None) -> dict[str, str]:
    """Build authenticated headers for MEXC OPEN-API."""
    if not MEXC_API_KEY or not MEXC_API_SECRET:
        raise ValueError("MEXC_API_KEY and MEXC_API_SECRET must be set")
    timestamp = str(int(time.time() * 1000))
    param_str = body if body else ""
    sig = _sign(MEXC_API_KEY, MEXC_API_SECRET, timestamp, param_str)
    return {
        "ApiKey": MEXC_API_KEY,
        "Request-Time": timestamp,
        "Signature": sig,
        "Content-Type": "application/json",
    }


# --- Order types (MEXC futures) ---
# openType: 1=open position, 2=close position
# positionType: 1=long, 2=short
# orderType: 1=limit, 2=market, etc.
OPEN_TYPE_OPEN = 1
OPEN_TYPE_CLOSE = 2
POSITION_TYPE_LONG = 1
POSITION_TYPE_SHORT = 2
ORDER_TYPE_LIMIT = 1
ORDER_TYPE_MARKET = 2


def place_order(
    symbol: str,
    position_type: int,
    vol: float,
    order_type: int = ORDER_TYPE_MARKET,
    price: float | None = None,
    open_type: int = OPEN_TYPE_OPEN,
    leverage: int | None = None,
    open_type_margin: int | None = None,
) -> dict[str, Any]:
    """
    Place a futures order on MEXC.
    symbol: e.g. "BTC_USDT"
    position_type: 1=long, 2=short
    vol: volume (in contracts)
    order_type: 1=limit, 2=market
    price: required for limit orders
    open_type: 1=open, 2=close
    leverage: optional; uses config default if not set
    open_type_margin: 1=isolated, 2=cross
    """
    leverage = leverage or DEFAULT_LEVERAGE
    open_type_margin = open_type_margin if open_type_margin is not None else MEXC_OPEN_TYPE

    body: dict[str, Any] = {
        "symbol": symbol,
        "openType": open_type,
        "positionType": position_type,
        "orderType": order_type,
        "vol": vol,
        "leverage": leverage,
        "openTypeMargin": open_type_margin,
    }
    if order_type == ORDER_TYPE_LIMIT and price is not None:
        body["price"] = price

    body_str = json.dumps(body, separators=(",", ":"))
    url = f"{MEXC_BASE_URL}/api/v1/private/order/place"
    r = requests.post(url, headers=_headers(body_str), data=body_str, timeout=30)
    out = r.json()
    if not out.get("success"):
        raise RuntimeError(f"MEXC order failed: {out}")
    return out


def get_open_positions(symbol: str | None = None) -> list[dict[str, Any]]:
    """Get current open positions. Optional symbol filter."""
    url = f"{MEXC_BASE_URL}/api/v1/private/position/open_positions"
    params = {}
    if symbol:
        params["symbol"] = symbol
    # GET: params sorted, underscore naming
    param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items())) if params else ""
    r = requests.get(
        url,
        headers=_headers(param_str),
        params=params,
        timeout=30,
    )
    out = r.json()
    if not out.get("success"):
        raise RuntimeError(f"MEXC positions failed: {out}")
    return out.get("data") or []


def get_assets() -> list[dict[str, Any]]:
    """Get account assets (e.g. USDT balance)."""
    url = f"{MEXC_BASE_URL}/api/v1/private/account/assets"
    r = requests.get(url, headers=_headers(""), timeout=30)
    out = r.json()
    if not out.get("success"):
        raise RuntimeError(f"MEXC assets failed: {out}")
    return out.get("data") or []


def get_contract_detail(symbol: str | None = None) -> list[dict[str, Any]]:
    """Get contract specs (minVol, volUnit, etc.) - public endpoint, no auth."""
    url = f"{MEXC_BASE_URL}/api/v1/contract/detail"
    params = {}
    if symbol:
        params["symbol"] = symbol
    r = requests.get(url, params=params, timeout=30)
    out = r.json()
    if not out.get("success"):
        raise RuntimeError(f"MEXC contract detail failed: {out}")
    return out.get("data") or []


def get_fair_price(symbol: str) -> float:
    """Get current fair/mark price for a symbol (public)."""
    url = f"{MEXC_BASE_URL}/api/v1/contract/fair_price/{symbol}"
    r = requests.get(url, timeout=10)
    out = r.json()
    if not out.get("success"):
        raise RuntimeError(f"MEXC fair price failed: {out}")
    return float(out["data"]["fairPrice"])


def usdt_to_contract_vol(symbol: str, position_size_usdt: float) -> float:
    """
    Convert USDT position size to contract volume for MEXC futures.
    Uses contract detail (contractSize, volUnit, minVol) and current fair price.
    """
    contracts = get_contract_detail(symbol)
    if not contracts:
        raise ValueError(f"No contract detail for {symbol}")
    detail = contracts[0] if isinstance(contracts, list) else contracts
    contract_size = float(detail.get("contractSize", 0.0001))
    vol_unit = int(detail.get("volUnit", 1))
    min_vol = float(detail.get("minVol", 1))
    price = get_fair_price(symbol)
    # notional = vol * contractSize * price  =>  vol = position_size_usdt / (contractSize * price)
    raw_vol = position_size_usdt / (contract_size * price) if price else 0
    # Round to volUnit and enforce minVol
    vol = max(min_vol, round(raw_vol / vol_unit) * vol_unit)
    return vol
