from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_users, sh_crystals, sh_aura, sh_referrals
from utils.fmt import escape


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    sh_user = sh_users.get(user.id)

    if not sh_user:
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
    daily_q   = sh_user.get("daily_queries", 5)
    max_trk   = sh_user.get("max_tracking", 0)

    joined = sh_user["joined_at"].strftime("%b %d, %Y") if sh_user.get("joined_at") else "—"
    name   = escape(user.first_name or "User")
    uname  = f"@{escape(user.username)}" if user.username else "_no username_"

    lines = [
        f"👤 *{name}*",
        f"{uname}  ·  `{user.id}`",
        f"Joined: {joined}",
        "",
        f"{badge} *{escape(plan_name)} Plan*",
        f"• 🔍 Daily searches: `{daily_q}`",
        f"• 🔔 Tracking slots: `{max_trk}`",
        "",
        f"💠 Crystals: `{crystals}`",
        f"🌟 Reputation: `{aura}`",
        f"👥 Referrals: `{refs}`",
    ]

    bot_uname = escape(context.bot.username or "")
    ref_link  = f"`https://t\\.me/{bot_uname}?start=ref_{user.id}`"
    lines.append(f"\n🔗 *Your referral link*\n{ref_link}")
    lines.append(f"_Each new user earns you \\+10 💠_")

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Share Referral",  callback_data="show_link"),
            InlineKeyboardButton("👑 Upgrade Plan",    callback_data="show_plan"),
        ],
        [
            InlineKeyboardButton("🔔 My Tracking",     callback_data="kb_tracks"),
            InlineKeyboardButton("💠 Crystal Prices",  callback_data="crystal_prices"),
        ],
    ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb,
    )
