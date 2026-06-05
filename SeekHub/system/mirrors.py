from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import mirrors as mirrors_db
from keyboards.system.main import back_keyboard


async def cmd_mirror(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    mirror = mirrors_db.get_mirror_by_owner(user.id)

    if mirror:
        text = (
            f"*Your Mirror*\n\n"
            f"🤖 Bot: @{mirror['bot_username'] or 'unknown'}\n"
            f"📅 Created: {mirror['created_at'].strftime('%Y-%m-%d')}\n"
            f"✅ Status: Active\n\n"
            f"Use /token to change your mirror bot token\."
        )
    else:
        text = (
            "*No Mirror Found*\n\n"
            "You don't have a mirror bot yet\.\n\n"
            "To create one:\n"
            "1️⃣ Create a bot via @BotFather\n"
            "2️⃣ Send the token using /token\n"
            "3️⃣ Add your bot to a group/channel"
        )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_keyboard(),
    )
