from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import users as users_db, points as points_db, aura as aura_db, referrals as referrals_db


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = users_db.get_user(user.id)

    if not db_user:
        await update.message.reply_text("Please send /start first.")
        return

    crystals = points_db.get_crystals(user.id)
    aura_total = aura_db.get_aura(user.id)
    refs = referrals_db.count_referrals(user.id)

    joined = db_user["joined_at"].strftime("%Y-%m-%d") if db_user.get("joined_at") else "N/A"

    text = (
        f"*👤 Profile*\n\n"
        f"Name: {user.first_name}\n"
        f"Username: @{user.username or 'none'}\n"
        f"Joined: `{joined}`\n\n"
        f"💎 Crystals: `{crystals}`\n"
        f"🌟 Aura: `{aura_total}`\n"
        f"👥 Referrals: `{refs}`\n"
    )

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)
