"""Load configuration from environment."""
import os
from dotenv import load_dotenv

load_dotenv()


def get_env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


# Telegram
TELEGRAM_API_ID = get_env("TELEGRAM_API_ID")
TELEGRAM_API_HASH = get_env("TELEGRAM_API_HASH")
# Channel: @username (public) or numeric ID (private), e.g. -1001234567890
TELEGRAM_CHANNEL_RAW = get_env("TELEGRAM_CHANNEL")


def _telegram_channel():
    raw = TELEGRAM_CHANNEL_RAW
    if not raw:
        return None
    raw = raw.strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    return raw


TELEGRAM_CHANNEL = _telegram_channel() if TELEGRAM_CHANNEL_RAW else None

# WEEX Contract (Futures) - https://www.weex.com/account/newapi
# We use USDT-M (USDT-margined) futures only; symbols are cmt_*usdt.
WEEX_API_KEY = get_env("WEEX_API_KEY")
WEEX_SECRET_KEY = get_env("WEEX_SECRET_KEY")
WEEX_PASSPHRASE = get_env("WEEX_PASSPHRASE")
WEEX_BASE_URL = get_env("WEEX_BASE_URL", "https://api-contract.weex.com")
# Isolated margin: set on WEEX per contract (Leverage/Margin). This flag is for docs/future API use.
WEEX_ISOLATED_MARGIN = get_env("WEEX_ISOLATED_MARGIN", "1").strip().lower() in ("1", "true", "yes")

# Trading defaults
DEFAULT_POSITION_SIZE_USDT = float(get_env("DEFAULT_POSITION_SIZE_USDT", "10"))
DEFAULT_LEVERAGE = int(get_env("DEFAULT_LEVERAGE", "5"))

# Optional: OpenAI API key for AI signal parsing (leave unset to use rule-based only)
OPENAI_API_KEY = get_env("OPENAI_API_KEY")

# Dashboard login (single user; set in .env)
DASHBOARD_USERNAME = get_env("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = get_env("DASHBOARD_PASSWORD", "")
FLASK_SECRET_KEY = get_env("FLASK_SECRET_KEY", "change-me-in-production")
