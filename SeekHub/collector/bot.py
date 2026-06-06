"""
collector/bot.py
================
The collector bot — added to public groups/channels to passively index
all messages, joins, leaves, and chat metadata into the central DB.

When added to a channel by a SeekHub user, it also powers Channel Analytics:
sending join/leave notifications to the channel owner via the system bot.
"""
import os
import logging
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, ChatMemberHandler,
    filters, ContextTypes
)
from collector.indexer import index_message, index_member_join, index_member_left, index_chat_members
from collector.analytics import (
    on_collector_joined_channel,
    on_collector_left_channel,
    on_member_joined_channel,
    on_member_left_channel,
)

logger = logging.getLogger(__name__)

COLLECTOR_TOKEN = os.environ.get("COLLECTOR_BOT_TOKEN")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        index_message(update.message)
    if update.channel_post:
        index_message(update.channel_post)


async def on_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.edited_message:
        index_message(update.edited_message)
    if update.edited_channel_post:
        index_message(update.edited_channel_post)


async def on_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member or update.my_chat_member
    if not result:
        return

    new  = result.new_chat_member
    old  = result.old_chat_member
    chat = result.chat

    is_our_bot   = (new.user.id == context.bot.id)
    is_channel   = (chat.type == "channel")
    joined_now   = new.status in ("member", "administrator") and old.status in ("left", "kicked")
    left_now     = new.status in ("left", "kicked") and old.status not in ("left", "kicked")

    # ── Our bot joined a chat ──────────────────────────────────────────────────
    if is_our_bot and joined_now:
        await index_chat_members(context.bot, chat.id)
        logger.info("Collector joined chat %s (%s)", chat.id, chat.title)

        if is_channel:
            on_collector_joined_channel(chat, added_by=result.from_user)
        return

    # ── Our bot left / was kicked ──────────────────────────────────────────────
    if is_our_bot and left_now:
        if is_channel:
            on_collector_left_channel(chat.id)
        return

    # ── Regular user joined ────────────────────────────────────────────────────
    if joined_now and not is_our_bot:
        index_member_join(new.user, chat)
        if is_channel:
            on_member_joined_channel(chat.id, new.user, channel_title=chat.title or "")

    # ── Regular user left ──────────────────────────────────────────────────────
    elif left_now and not is_our_bot:
        index_member_left(new.user, chat)
        if is_channel:
            on_member_left_channel(chat.id, new.user, channel_title=chat.title or "")


def build_collector_app() -> Application | None:
    if not COLLECTOR_TOKEN:
        logger.warning("COLLECTOR_BOT_TOKEN not set — collector bot disabled")
        return None

    app = Application.builder().token(COLLECTOR_TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE, on_edited_message))
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    return app
