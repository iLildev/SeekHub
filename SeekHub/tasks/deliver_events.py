"""
tasks/deliver_events.py
=======================
Job queue task — polls sh_analytics_events and delivers DMs via the
system bot.

Runs every 30 seconds.
"""
import logging
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError

from db import sh_channel_analytics
from utils.fmt import escape

logger = logging.getLogger(__name__)

EVENT_TEMPLATES = {
    "channel_connected": (
        "📡 *Channel Analytics Connected*\n\n"
        "Your channel *{channel_title}* is now tracked by SeekHub\\.\n"
        "You'll receive notifications when members join or leave\\."
    ),
    "member_join": (
        "➕ *New member* in *{channel_title}*\n"
        "{user_line}"
    ),
    "member_leave": (
        "➖ *Member left* *{channel_title}*\n"
        "{user_line}"
    ),
    "spy_alert": (
        "🕵️ *Someone searched for you\\!*\n\n"
        "A SeekHub user looked up your profile\\.\n"
        "_Your Spy plan kept your data hidden from them\\._"
    ),
}


def _user_line(payload: dict) -> str:
    name  = escape(payload.get("first_name") or "Unknown")
    uname = payload.get("username", "")
    if uname:
        return f"[{name}](tg://user?id={payload['user_id']}) \\(@{escape(uname)}\\)"
    return f"[{name}](tg://user?id={payload['user_id']})"


def _format_event(event_type: str, payload: dict) -> str | None:
    tpl = EVENT_TEMPLATES.get(event_type)
    if not tpl:
        return None

    channel_title = escape(payload.get("channel_title") or f"Channel {payload.get('channel_id', '')}")

    if event_type in ("member_join", "member_leave"):
        return tpl.format(channel_title=channel_title, user_line=_user_line(payload))
    if event_type == "channel_connected":
        return tpl.format(channel_title=channel_title)
    if event_type == "spy_alert":
        return tpl

    return None


async def deliver_analytics_events(context: ContextTypes.DEFAULT_TYPE):
    events = sh_channel_analytics.pop_pending_events(limit=50)
    if not events:
        return

    for ev in events:
        import json
        payload = ev["payload"] if isinstance(ev["payload"], dict) else json.loads(ev["payload"])
        text    = _format_event(ev["event_type"], payload)
        if not text:
            continue
        try:
            await context.bot.send_message(
                chat_id=ev["recipient_user_id"],
                text=text,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except TelegramError as e:
            logger.debug("Could not deliver event %d to user %d: %s", ev["id"], ev["recipient_user_id"], e)
