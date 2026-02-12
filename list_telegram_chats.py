#!/usr/bin/env python3
"""
List all Telegram chats and channels you're in, with their IDs.
Use this to find the channel ID for a **private** channel (no @username).
Then set TELEGRAM_CHANNEL=-1001234567890 in your .env
"""
import asyncio
import sys

from telethon import TelegramClient
from telethon.tl.types import Channel

from config import TELEGRAM_API_ID, TELEGRAM_API_HASH


async def main():
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        print("Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env first.", file=sys.stderr)
        sys.exit(1)

    client = TelegramClient(
        "signal_trading_session",
        int(TELEGRAM_API_ID),
        TELEGRAM_API_HASH,
    )
    await client.start()

    print("Your chats and channels (use the ID for private channels):\n")
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        title = getattr(dialog, "name", None) or getattr(entity, "title", "?")
        # Channel IDs are usually negative, e.g. -1001234567890
        pid = entity.id
        if isinstance(entity, Channel):
            kind = "channel" if entity.broadcast else "supergroup"
            username = getattr(entity, "username", None) or "(no @username – private)"
            print(f"  ID: {pid}")
            print(f"     Title: {title}")
            print(f"     Type: {kind}  {username}")
            print()
        else:
            print(f"  ID: {pid}  |  {title}  (chat)")
            print()

    print("Copy the ID of your signal channel into .env as TELEGRAM_CHANNEL=-1001234567890")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
