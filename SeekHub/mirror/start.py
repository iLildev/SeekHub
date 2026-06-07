from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_users, tg_users
from utils.fmt import escape
from keyboards.mirror.main import main_keyboard


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

    first = escape(user.first_name or "there")

    welcome = (
        f"👋 Hey *{first}\\!*\n\n"
        f"I'm *SeekHub* — a Telegram intelligence database\\.\n"
        f"Search any user, group, or channel by name, @username, or ID\\.\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔍 *Search* — type any name or @username\n"
        f"🎯 *Select* — pick from your contacts/groups directly\n"
        f"📋 *Menu* — your profile, referrals, tracking & more\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 *Tip:* Just type a name or @username here — no command needed\\."
    )

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❓ How does it work?", callback_data="help_how"),
        InlineKeyboardButton("👤 My Profile",        callback_data="kb_profile"),
    ]])

    await update.message.reply_text(
        welcome,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_keyboard(),
    )
    # Brief tip card
    await update.message.reply_text(
        "👆 Use the buttons below to navigate, or just start typing\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb,
    )
