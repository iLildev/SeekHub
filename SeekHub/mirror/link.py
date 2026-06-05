from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import mirrors as mirrors_db


async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    mirror = mirrors_db.get_mirror_by_owner(user.id)

    if not mirror:
        await update.message.reply_text(
            "You don't have a mirror yet\\. Go to @SeekHubBot and use /mirror to create one\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    link = f"https://t.me/{mirror['bot_username']}"
    await update.message.reply_text(
        f"🔗 *Your Mirror Link*\n\n`{link}`",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
