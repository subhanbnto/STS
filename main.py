#!/usr/bin/env python3
"""
Telegram → WEEX Futures signal bot.
Listens to a Telegram channel, parses trading signals, and places futures orders on WEEX.
Run the dashboard at http://localhost:5050 for live status and trades.
"""
import asyncio
import logging
import os
import sys
from datetime import datetime

from config import (
    TELEGRAM_CHANNEL,
    DEFAULT_POSITION_SIZE_USDT,
    DEFAULT_LEVERAGE,
)
from weex_client import (
    place_order,
    usdt_to_size,
    set_take_profit,
    ORDER_TYPE_MARKET,
)
from signal_parser import parse_signal
from telegram_listener import listen_for_messages
from app_state import state, SignalEvent, TradeEvent
from dashboard import run_dashboard_thread

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_trade(signal):
    """Execute one trade on WEEX from a ParsedSignal (blocking)."""
    symbol = signal.mexc_symbol()
    side_label = "LONG" if signal.is_long() else "SHORT"
    size_usdt = signal.position_size_usdt or DEFAULT_POSITION_SIZE_USDT
    state.set_status("Processing", f"{symbol} {side_label}")

    if os.environ.get("DRY_RUN"):
        logger.info("DRY_RUN: would place %s %s (size=%s USDT)", symbol, signal.side, size_usdt)
        state.add_trade_placed(TradeEvent(
            symbol=symbol,
            side=side_label,
            size=0,
            size_usdt=size_usdt,
            success=True,
            message="DRY RUN",
            time_iso=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            take_profit=signal.take_profit,
        ))
        return
    try:
        size = usdt_to_size(symbol, size_usdt)
    except Exception as e:
        logger.exception("Failed to get size for %s: %s", symbol, e)
        state.add_trade_placed(TradeEvent(
            symbol=symbol,
            side=side_label,
            size=0,
            size_usdt=size_usdt,
            success=False,
            message=str(e),
            time_iso=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))
        return

    try:
        result = place_order(
            symbol=symbol,
            position_type=signal.position_type_int(),
            size=size,
            order_type=ORDER_TYPE_MARKET,
        )
        try:
            data = result.get("data", result) if isinstance(result, dict) else result
            order_id = str((data if isinstance(data, dict) else {}).get("orderId", result.get("orderId", "") if isinstance(result, dict) else ""))
        except Exception:
            order_id = ""
        logger.info("Order placed: %s %s size=%s -> %s", symbol, side_label, size, result)
        state.add_trade_placed(TradeEvent(
            symbol=symbol,
            side=side_label,
            size=size,
            size_usdt=size_usdt,
            success=True,
            message=order_id or "Placed",
            time_iso=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            take_profit=signal.take_profit,
            order_id=order_id or None,
        ))
        if signal.take_profit is not None:
            tp_result = set_take_profit(symbol, signal.position_type_int(), size, signal.take_profit)
            if tp_result is None:
                logger.info("Take profit target: %s (set manually on WEEX if needed)", signal.take_profit)
    except Exception as e:
        logger.exception("WEEX order failed: %s", e)
        state.add_trade_placed(TradeEvent(
            symbol=symbol,
            side=side_label,
            size=size,
            size_usdt=size_usdt,
            success=False,
            message=str(e),
            time_iso=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))


async def on_message(text: str, _msg) -> None:
    """Handle each new Telegram message: parse and optionally trade. Non-blocking for real-time response."""
    signal = parse_signal(text)
    if not signal:
        return
    logger.info(
        "Parsed signal: %s %s (size=%s USDT, lev=%s, TP=%s)",
        signal.symbol, signal.side, signal.position_size_usdt, signal.leverage, signal.take_profit,
    )
    state.add_signal(SignalEvent(
        symbol=signal.mexc_symbol(),
        side=signal.side,
        size_usdt=signal.position_size_usdt,
        leverage=signal.leverage,
        take_profit=signal.take_profit,
        time_iso=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        raw_preview=signal.raw_text,
    ))

    async def run_trade_async():
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: run_trade(signal))

    asyncio.create_task(run_trade_async())


def main():
    if not TELEGRAM_CHANNEL:
        logger.error("Set TELEGRAM_CHANNEL in .env (e.g. @your_signal_channel)")
        sys.exit(1)

    state.set_status("Starting…", "Connecting to Telegram")
    run_dashboard_thread(host="0.0.0.0", port=5050)
    logger.info("Dashboard: http://localhost:5050")
    state.set_status("Waiting for signal…", "Listening to channel")
    asyncio.run(listen_for_messages(TELEGRAM_CHANNEL, on_message))


if __name__ == "__main__":
    main()
