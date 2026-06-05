import os
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_users
from services.statistics import get_stats, get_stats_fmt
from utils.fmt import escape

ADMIN_IDS = set(
    int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()
)


def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied\\.", parse_mode=ParseMode.MARKDOWN_V2)
            return
        return await func(update, context)
    return wrapper


@admin_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_stats()
    text = (
        f"*📊 SeekHub Statistics*\n\n"
        f"👤 Indexed users: `{s['users']:,}`\n"
        f"💬 Indexed chats: `{s['chats']:,}`\n"
        f"📨 Indexed messages: `{s['messages']:,}`\n"
        f"🔮 Active mirrors: `{s['mirrors']:,}`\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /ban <user\\_id>", parse_mode=ParseMode.MARKDOWN_V2)
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    sh_users.ban(target_id)
    await update.message.reply_text(f"✅ User `{target_id}` banned\\.", parse_mode=ParseMode.MARKDOWN_V2)


@admin_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /unban <user\\_id>", parse_mode=ParseMode.MARKDOWN_V2)
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return
    sh_users.unban(target_id)
    await update.message.reply_text(f"✅ User `{target_id}` unbanned\\.", parse_mode=ParseMode.MARKDOWN_V2)
