from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_users, tg_users
from utils.fmt import escape
from keyboards.mirror.main import main_keyboard


MIRROR_WELCOME = (
    "🔍 *SeekHub — Telegram Intelligence*\n\n"
    "The largest Telegram indexing database\\.\n"
    "Search any user, group, channel, or bot\\.\n\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🔍 *Search / Seek* — search the database\n"
    "🎯 *Select* — pick what you're looking for\n"
    "📋 *Menu* — more features\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "💡 You can also type `@this_bot query` in any chat for instant search\\."
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    tg_users.upsert(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
    )
    sh_users.upsert(user.id, user.username or "", user.first_name or "")

    if context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0][4:])
            from mirror.link import handle_referral
            await handle_referral(referrer_id, user.id)
        except (ValueError, IndexError):
            pass

    await update.message.reply_text(
        MIRROR_WELCOME,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_keyboard(),
    )
