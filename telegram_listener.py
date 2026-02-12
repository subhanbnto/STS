"""
Telegram channel listener using Telethon.
Real-time: uses NewMessage events (push-based), so messages are handled as soon as they arrive.
No polling delay. You must be a member of the channel.
Get API credentials: https://my.telegram.org/apps
"""
import asyncio
import logging
from typing import AsyncIterator, Callable

from telethon import TelegramClient
from telethon.events import NewMessage
from telethon.tl.types import Channel, Message

from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL

logger = logging.getLogger(__name__)


def _client() -> TelegramClient:
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set")
    return TelegramClient(
        "signal_trading_session",
        int(TELEGRAM_API_ID),
        TELEGRAM_API_HASH,
    )


async def get_latest_messages(channel_id: str | int, limit: int = 10) -> list[Message]:
    """
    Fetch the latest N messages from a channel.
    channel_id: @username or channel ID (int or str).
    """
    client = _client()
    await client.start()
    try:
        messages = await client.get_messages(channel_id, limit=limit)
        return list(messages) if messages else []
    finally:
        await client.disconnect()


async def stream_new_messages(channel_id: str | int) -> AsyncIterator[Message]:
    """
    Stream new messages from a channel in real time.
    Yields each new message as it arrives.
    """
    client = _client()
    await client.start()

    async def handler(event: NewMessage.Event):
        yield event.message

    # Use iter_messages in a loop with polling, or use NewMessage listener
    queue: asyncio.Queue[Message] = asyncio.Queue()

    @client.on(NewMessage(chats=channel_id))
    async def on_new_message(event: NewMessage.Event):
        await queue.put(event.message)

    async def produce():
        await client.run_until_disconnected()

    async def consume():
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield msg
            except asyncio.TimeoutError:
                continue

    # Run client in background and yield from queue
    task = asyncio.create_task(client.run_until_disconnected())
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield msg
            except asyncio.TimeoutError:
                if task.done():
                    break
                continue
    finally:
        client.disconnect()
        task.cancel()


async def listen_for_messages(
    channel_id: str | int,
    callback: Callable,
) -> None:
    """
    Listen for new messages and call callback(message) for each.
    callback can be async or sync.
    Runs until disconnected.
    """
    client = _client()
    await client.start()

    @client.on(NewMessage(chats=channel_id))
    async def on_new_message(event: NewMessage.Event):
        msg = event.message
        if msg.text or msg.message:
            text = msg.text or msg.message or ""
            if callable(callback):
                if asyncio.iscoroutinefunction(callback):
                    await callback(text, msg)
                else:
                    callback(text, msg)

    logger.info("Listening for messages on channel %s (real-time)", channel_id)
    await client.run_until_disconnected()
