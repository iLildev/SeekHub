"""
mirror/link.py
==============
Referral link generation and invite handling for mirror bots.
Users get crystals for inviting others through their personal link.
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_users, sh_referrals, sh_crystals
from utils.fmt import escape


async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /link
    Show the user's personal referral link for this mirror.
    Inviting new users earns crystals.
    """
    user = update.effective_user
    sh_users.upsert(user.id, user.username or "", user.first_name or "")

    ref_count = sh_referrals.count(user.id)
    crystals  = sh_crystals.get_balance(user.id)

    # Referral always points to the SeekHub system, not any specific mirror
    system_uname = escape(
        context.bot_data.get("system_bot_username") or context.bot.username or ""
    )
    link = f"https://t\\.me/{system_uname}?start=ref_{user.id}"

    text = (
        f"🔗 *رابط الإحالة الخاص بك*\n\n"
        f"`{link}`\n\n"
        f"👥 المدعوون: `{ref_count}`\n"
        f"💠 الكريستالات: `{crystals}`\n\n"
        f"_كل مستخدم جديد ينضم عبر رابطك يمنحك `10` 💠_\n"
        f"_الدعوة تعمل لكامل منظومة SeekHub، مش لمرآة بعينها\\._"
    )

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


async def handle_referral(referrer_id: int, new_user_id: int):
    """Called from mirror/start.py when a new user starts via a referral link."""
    if referrer_id == new_user_id:
        return
    already = sh_referrals.exists(new_user_id)
    if already:
        return
    sh_referrals.add(referrer_id, new_user_id)
    sh_crystals.add(referrer_id, 10, reason="referral")
