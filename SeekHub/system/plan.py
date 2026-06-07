"""
system/plan.py
==============
Privacy plans — Ghost / Shadow / Spy.
Paid via Telegram Stars through the system bot.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_hide_plans, sh_users
from utils.fmt import escape

logger = logging.getLogger(__name__)

PLAN_DESCRIPTIONS = {
    "ghost": (
        "👻 *Ghost* — $4\\.99/mo\n"
        "• Your username is hidden from all search results\n"
        "• Your profile still appears but username is masked\n"
        "• Ideal for basic privacy"
    ),
    "shadow": (
        "🌑 *Shadow* — $7\\.99/mo\n"
        "• Completely removed from all search results\n"
        "• No one can find you by username or name\n"
        "• Full invisibility"
    ),
    "spy": (
        "🕵️ *Spy* — $14\\.99/mo\n"
        "• Everything in Shadow, plus:\n"
        "• You get notified when someone searches for you\n"
        "• See who's looking for you"
    ),
}


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    sh_user = sh_users.get(user.id)
    if not sh_user:
        sh_users.upsert(user.id, user.username or "", user.first_name or "")

    active = sh_hide_plans.get_active_subscription(user.id)

    lines = ["🛡️ *Privacy Plans*\n"]
    lines.append(
        "Choose a plan to hide your presence from SeekHub's search results\\. "
        "All plans are paid monthly via Telegram Stars\\.\n"
    )

    for desc in PLAN_DESCRIPTIONS.values():
        lines.append(desc + "\n")

    if active:
        plan_name = active.get("plan_name", "Unknown")
        expires   = active["expires_at"].strftime("%Y\\-%m\\-%d")
        lines.append(f"✅ *Active plan:* {escape(plan_name)} \\(expires {expires}\\)")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👻 Ghost — ⭐250",  callback_data="hide_buy:ghost"),
            InlineKeyboardButton("🌑 Shadow — ⭐400", callback_data="hide_buy:shadow"),
        ],
        [
            InlineKeyboardButton("🕵️ Spy — ⭐750",   callback_data="hide_buy:spy"),
        ],
    ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=keyboard,
    )
