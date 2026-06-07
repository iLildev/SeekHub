"""
mirror/quota.py
===============
Daily query quota enforcement with crystal bypass.

Every search/lookup goes through charge_query():
  • Within daily limit    → allow (free)
  • Over limit, crystals  → deduct 1 crystal, allow, notify user
  • Over limit, no balance → send helpful error explaining how to earn more, deny
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_users, sh_crystals
from db.sh_mirrors import (
    track_mirror_user, increment_query_count,
    log_query, get_user_daily_count,
)
from utils.fmt import escape

logger = logging.getLogger(__name__)

# Loaded once at import — admins have unlimited queries/crystals
import os as _os
_ADMIN_IDS: set[int] = set(
    int(x) for x in _os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()
)


async def charge_query(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       mirror_id: int, query_text: str = "") -> bool:
    """
    Call before every search/lookup. Returns True if allowed, False if blocked.
    Handles tracking, counting, quota check, and crystal deduction.
    """
    user = update.effective_user
    if not user:
        return False

    # ── Admins bypass all quota and crystal checks ─────────────────────────
    if user.id in _ADMIN_IDS:
        track_mirror_user(mirror_id, user.id,
                          username=user.username, first_name=user.first_name)
        increment_query_count(mirror_id)
        if query_text:
            log_query(mirror_id, query_text, user_id=user.id)
        return True

    track_mirror_user(mirror_id, user.id,
                      username=user.username, first_name=user.first_name)
    increment_query_count(mirror_id)
    if query_text:
        log_query(mirror_id, query_text, user_id=user.id)

    sh_user     = sh_users.get(user.id)
    daily_limit = (sh_user or {}).get("daily_queries", 5)
    today_count = get_user_daily_count(mirror_id, user.id)

    if today_count <= daily_limit:
        return True

    balance = sh_crystals.get_balance(user.id)
    if balance >= 1:
        sh_crystals.deduct(user.id, 1, "extra_query")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔗 Referral link", callback_data="show_link"),
            InlineKeyboardButton("📢 Submit group",  callback_data="show_submit"),
        ]])
        await update.message.reply_text(
            f"💠 \\-1 crystal \\| Remaining: `{balance - 1}`",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb,
        )
        return True

    plan_name = escape((sh_user or {}).get("plan_name") or "Free")
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Referral link +10💠", callback_data="show_link"),
            InlineKeyboardButton("📢 Submit group +8💠",   callback_data="show_submit"),
        ],
        [
            InlineKeyboardButton("👑 Upgrade Plan", callback_data="show_plan"),
        ],
    ])
    await update.message.reply_text(
        f"⛔ *Daily limit reached* \\(`{daily_limit}` queries\\)\n\n"
        f"_You're on the *{plan_name}* plan\\._\n"
        f"Earn crystals or upgrade to keep searching:",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb,
    )
    return False
