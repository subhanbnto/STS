# STS - Signal Trading Software

Bot that reads messages from a **Telegram channel** and places **futures trades on WEEX** based on parsed signals.

## Features

- **Telegram**: Listens to a channel using [Telethon](https://docs.telethon.dev/) (you must have access to the channel).
- **Signal parsing**: Detects symbol (e.g. BTC, ETH), side (long/short), optional size (USDT) and leverage. Instruction lines (e.g. "dont pick old signal") are filtered; optional **AI parsing** (OpenAI) can interpret messages when `OPENAI_API_KEY` is set.
- **WEEX**: Places **USDT-M (USDT-margined) futures** orders with **isolated margin** via the official API. Real-time reaction to new messages (no polling).

## Setup

### 1. Telegram API credentials

1. Go to [my.telegram.org/apps](https://my.telegram.org/apps).
2. Create an app and get **API ID** and **API hash**.
3. Add them to `.env` (see below).

### 2. WEEX API key

1. Go to [WEEX → Create API Key](https://www.weex.com/account/newapi).
2. Create an API key with **Trade** permission for contract/futures.
3. Save **API Key**, **Secret Key**, and **Passphrase** (passphrase cannot be recovered).
4. Add all three to `.env`.

### 3. Environment

```bash
cp .env.example .env
# Edit .env with your values
```

Required in `.env`:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_API_ID` | Telegram app API ID (number) |
| `TELEGRAM_API_HASH` | Telegram app API hash |
| `TELEGRAM_CHANNEL` | Channel to listen to: `@channel_username` (public) or **numeric ID** (private, e.g. `2305855779`) |
| `WEEX_API_KEY` | WEEX API key |
| `WEEX_SECRET_KEY` | WEEX Secret key |
| `WEEX_PASSPHRASE` | WEEX API passphrase (set when creating the key) |

Optional:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Optional. If set, AI parses messages first (understands "dont pick old signal" etc.); otherwise rule-based only |
| `DEFAULT_POSITION_SIZE_USDT` | 10 | Default position size in USDT per trade |
| `DEFAULT_LEVERAGE` | 5 | Default leverage |
| `WEEX_ISOLATED_MARGIN` | 1 | Use isolated margin only (1=yes, 0=no) |

### 4. Install and run

```bash
python3 -m venv venv
source venv/bin/activate   # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

On macOS/Linux, use `python3` and `pip3` if `python`/`pip` are not available.

To test without placing real orders, run with `DRY_RUN=1 python main.py`.

**Live dashboard:** When the bot is running, open **http://localhost:5050** in your browser to see real-time status, recent signals, active trades, closed trades (success/fail), and insights—no need to watch the terminal.

**Private channel (no @username)?** If you're in the channel but it has no public handle:

1. Run `python3 list_telegram_chats.py` (after setting Telegram env vars and logging in once).
2. Find your signal channel in the list and copy its **ID** (e.g. `2305855779`).
3. In `.env` set `TELEGRAM_CHANNEL=2305855779` (use your actual ID).

The bot works the same for public (@channel) and private (numeric ID) channels.

On first run, Telethon may ask you to log in (phone number + code). The session is saved so you only do this once.

## How signals are parsed

The bot **only reacts to new messages** (no old signals). It supports:

**Structured format (e.g. from Weex Trading channel):**
```
Short
QTUM
Target
0.919
```
- First line: **Short** or **Long**
- Second line: **Symbol** (e.g. QTUM, BTC, ETH)
- **Target** and a number = take-profit price (logged; set manually on WEEX until TP API is wired)

**Free-form:** side (long/short, buy/sell, 🟢/🔴), symbol (#BTC, BTC/USDT, or common tickers), optional size (e.g. `100 USDT`), optional leverage (`5x`), optional `Target 0.919`.

If no size is found, `DEFAULT_POSITION_SIZE_USDT` is used. Orders are **market** on WEEX (symbol format `cmt_btcusdt`, etc.).

## WEEX API

- **Futures**: **USDT-M only** (symbols like `cmt_btcusdt`). No coin-margined contracts.
- **Margin**: **Isolated margin** only (set `WEEX_ISOLATED_MARGIN=1` in `.env`). If the API rejects `marginType`, set it to `0` and configure isolated margin in the WEEX app per contract.
- **Real-time**: Messages are handled as soon as they arrive (Telethon `NewMessage` events). Trades are scheduled without blocking the next message, so fast-coming signals are all processed quickly.
- Endpoint: `POST /capi/v2/order/placeOrder` on `https://api-contract.weex.com`. See [WEEX API docs](https://www.weex.com/api-doc/contract).

## Disclaimer

- **Risk**: Automated trading can lose money. Only use with funds you can afford to lose.
- **API keys**: Never share or commit `.env`. Restrict WEEX API key to trading only and consider IP whitelist.
- **Signals**: The parser is heuristic; wrong or partial messages can trigger wrong trades. Test with small size or DRY_RUN first.

---

© 2026 Signal Trading Software. All rights reserved.
