from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import users as users_db


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users_db.upsert_user(user.id, user.username or "", user.first_name or "")

    await update.message.reply_text(
        f"👋 Hello, {user.first_name}\\!\n\n"
        "This is a *SeekHub Mirror*\\.\n"
        "Use /search to find groups and channels\\.\n"
        "Use /profile to view your profile\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
