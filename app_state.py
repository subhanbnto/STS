"""
Shared state for the dashboard. Updated by the bot; read by the web server.
Thread-safe for use from async bot and Flask.
"""
import threading
import time
from dataclasses import dataclass, field
from typing import Any

_lock = threading.Lock()


@dataclass
class SignalEvent:
    symbol: str
    side: str
    size_usdt: float | None
    leverage: int | None
    take_profit: float | None
    time_iso: str
    raw_preview: str


@dataclass
class TradeEvent:
    symbol: str
    side: str
    size: float
    size_usdt: float
    success: bool
    message: str
    time_iso: str
    take_profit: float | None = None
    order_id: str | None = None


def _ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


class AppState:
    def __init__(self):
        self._status = "Waiting for signal..."
        self._status_detail = ""
        self._last_activity_ts: float = 0
        self._signals: list[dict[str, Any]] = []
        self._trades_active: list[dict[str, Any]] = []
        self._trades_closed: list[dict[str, Any]] = []
        self._max_signals = 20
        self._max_active = 50
        self._max_closed = 100

    def set_status(self, status: str, detail: str = ""):
        with _lock:
            self._status = status
            self._status_detail = detail
            self._last_activity_ts = time.time()

    def add_signal(self, event: SignalEvent):
        with _lock:
            self._signals.insert(0, {
                "symbol": event.symbol,
                "side": event.side,
                "size_usdt": event.size_usdt,
                "leverage": event.leverage,
                "take_profit": event.take_profit,
                "time": event.time_iso,
                "raw_preview": event.raw_preview[:80] + "..." if len(event.raw_preview) > 80 else event.raw_preview,
            })
            self._signals[:] = self._signals[: self._max_signals]
            self._status = f"Signal: {event.symbol} {event.side}"
            self._last_activity_ts = time.time()

    def add_trade_placed(self, event: TradeEvent):
        with _lock:
            obj = {
                "symbol": event.symbol,
                "side": event.side,
                "size": event.size,
                "size_usdt": event.size_usdt,
                "success": event.success,
                "message": event.message,
                "time": event.time_iso,
                "take_profit": event.take_profit,
                "order_id": event.order_id,
            }
            if event.success:
                self._trades_active.insert(0, obj)
                self._trades_active[:] = self._trades_active[: self._max_active]
                self._status = f"Placed: {event.symbol} {event.side}"
            else:
                self._trades_closed.insert(0, {**obj, "outcome": "failed"})
                self._trades_closed[:] = self._trades_closed[: self._max_closed]
                self._status = f"Failed: {event.symbol} {event.side}"
            self._last_activity_ts = time.time()

    def move_to_closed(self, symbol: str, side: str, time_iso: str, success: bool, message: str = ""):
        with _lock:
            for i, t in enumerate(self._trades_active):
                if t["symbol"] == symbol and t["side"] == side and t["time"] == time_iso:
                    self._trades_active.pop(i)
                    self._trades_closed.insert(0, {
                        **t,
                        "outcome": "success" if success else "failed",
                        "closed_message": message,
                    })
                    self._trades_closed[:] = self._trades_closed[: self._max_closed]
                    break

    def snapshot(self) -> dict[str, Any]:
        with _lock:
            return {
                "status": self._status,
                "status_detail": self._status_detail,
                "last_activity_ts": self._last_activity_ts,
                "signals": list(self._signals),
                "trades_active": list(self._trades_active),
                "trades_closed": list(self._trades_closed),
                "insights": {
                    "signals_today": len(self._signals),
                    "active_count": len(self._trades_active),
                    "closed_count": len(self._trades_closed),
                    "success_count": sum(1 for t in self._trades_closed if t.get("outcome") == "success" or t.get("success") is True),
                    "fail_count": sum(1 for t in self._trades_closed if t.get("outcome") == "failed" or t.get("success") is False),
                },
            }


state = AppState()
