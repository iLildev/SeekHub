from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_mirrors
from keyboards.system.main import back_keyboard
from utils.fmt import escape


async def cmd_mirror(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user   = update.effective_user
    mirrors = sh_mirrors.get_by_owner(user.id)

    if mirrors:
        lines = ["*🔮 Your Mirrors*\n"]
        for m in mirrors:
            lines.append(
                f"🤖 @{escape(m['bot_username'] or 'unknown')}\n"
                f"   Queries: `{m['query_count']}` \\| Users: `{m['user_count']}`\n"
                f"   Created: `{m['created_at'].strftime('%Y-%m-%d')}`"
            )
        lines.append("\nUse /token to add another mirror bot\\.")
        text = "\n".join(lines)
    else:
        text = (
            "*No Mirror Found*\n\n"
            "You don't have a mirror bot yet\\.\n\n"
            "To create one:\n"
            "1️⃣ Create a bot via @BotFather\n"
            "2️⃣ Send the token using /token\n"
            "3️⃣ Your mirror starts automatically"
        )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_keyboard(),
    )
