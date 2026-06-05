from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_users, sh_crystals, sh_aura, sh_referrals
from utils.fmt import escape


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    sh_user = sh_users.get(user.id)

    if not sh_user:
        # Auto-register on first profile view
        sh_users.upsert(user.id, user.username or "", user.first_name or "")
        sh_user = sh_users.get(user.id)

    if not sh_user:
        await update.message.reply_text(
            "Please send /start first\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    crystals  = sh_crystals.get_balance(user.id)
    aura      = sh_aura.get_score(user.id)
    refs      = sh_referrals.count(user.id)
    plan_name = sh_user.get("plan_name") or "Free"
    plan_feat = sh_user.get("plan_features") or {}
    badge     = plan_feat.get("badge", "⚪")

    joined = sh_user["joined_at"].strftime("%Y\\-%m\\-%d") if sh_user.get("joined_at") else "N/A"

    uname_line = (
        f"Username: @{escape(user.username)}"
        if user.username
        else "Username: _none_"
    )

    lines = [
        f"👤 *{escape(user.first_name)}*",
        f"ID: `{user.id}`",
        uname_line,
        f"Joined: `{joined}`",
        f"\n{badge} Plan: *{escape(plan_name)}*",
        f"💎 Crystals: `{crystals}`",
        f"🌟 Aura: `{aura}`",
        f"👥 Referrals: `{refs}`",
        f"\n🔗 Your referral:\n`https://t\\.me/{escape(context.bot.username)}?start={user.id}`",
    ]

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
