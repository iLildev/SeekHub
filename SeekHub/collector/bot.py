"""
collector/bot.py
================
The collector bot — added to public groups/channels to passively index
all messages, joins, leaves, and chat metadata into the central DB.

This is a SEPARATE bot from the system bot and mirrors.
Its sole purpose is data collection.
"""
import os
import logging
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, ChatMemberHandler,
    filters, ContextTypes
)
from collector.indexer import index_message, index_member_join, index_member_left, index_chat_members

logger = logging.getLogger(__name__)

COLLECTOR_TOKEN = os.environ.get("COLLECTOR_BOT_TOKEN")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        index_message(update.message)
    if update.channel_post:
        index_message(update.channel_post)


async def on_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member or update.my_chat_member
    if not result:
        return

    new = result.new_chat_member
    old = result.old_chat_member

    # Our collector bot just joined a chat → seed member list
    if (result.new_chat_member.user.id == context.bot.id and
            new.status in ("member", "administrator")):
        await index_chat_members(context.bot, result.chat.id)
        logger.info("Collector joined chat %s (%s)", result.chat.id, result.chat.title)
        return

    # A user joined
    if new.status in ("member", "administrator") and old.status in ("left", "kicked"):
        index_member_join(new.user, result.chat)

    # A user left
    elif new.status in ("left", "kicked") and old.status not in ("left", "kicked"):
        index_member_left(new.user, result.chat)


async def on_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.edited_message:
        index_message(update.edited_message)
    if update.edited_channel_post:
        index_message(update.edited_channel_post)


def build_collector_app() -> Application | None:
    if not COLLECTOR_TOKEN:
        logger.warning("COLLECTOR_BOT_TOKEN not set — collector bot disabled")
        return None

    app = Application.builder().token(COLLECTOR_TOKEN).build()

    # Index every message in every group/channel the bot is in
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.COMMAND, on_message))

    # Index edited messages
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE, on_edited_message))

    # Track member joins/leaves
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    return app
