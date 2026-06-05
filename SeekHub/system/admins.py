import os
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.statistics import get_stats, format_count

ADMIN_IDS = set(
    int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()
)


def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access denied.")
            return
        return await func(update, context)
    return wrapper


@admin_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_stats()
    text = (
        f"*📊 SeekHub Statistics*\n\n"
        f"👤 Users: `{format_count(stats['users'])}`\n"
        f"🔮 Mirrors: `{format_count(stats['mirrors'])}`\n"
        f"💬 Groups/Channels: `{format_count(stats['groups'])}`\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    from db.connection import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE seekhub_users SET is_banned = TRUE WHERE id = %s",
                (target_id,)
            )
        conn.commit()

    await update.message.reply_text(f"✅ User `{target_id}` has been banned\.", parse_mode=ParseMode.MARKDOWN_V2)


@admin_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    from db.connection import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE seekhub_users SET is_banned = FALSE WHERE id = %s",
                (target_id,)
            )
        conn.commit()

    await update.message.reply_text(f"✅ User `{target_id}` has been unbanned\.", parse_mode=ParseMode.MARKDOWN_V2)
