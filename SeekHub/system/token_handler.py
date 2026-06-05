from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import mirrors as mirrors_db


async def cmd_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "*🔑 Set Mirror Bot Token*\n\n"
            "Send your bot token to register your mirror:\n\n"
            "Usage: `/token <your_bot_token>`\n\n"
            "Get a token from @BotFather by creating a new bot\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    token = context.args[0].strip()

    if ":" not in token or len(token) < 30:
        await update.message.reply_text(
            "❌ Invalid token format\\. A valid token looks like:\n`1234567890:ABCdefGHI...`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    try:
        from telegram import Bot
        bot = Bot(token=token)
        bot_info = await bot.get_me()
        bot_username = bot_info.username
    except Exception:
        await update.message.reply_text(
            "❌ Could not verify this token\\. Make sure it's correct and try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    mirrors_db.create_mirror(user.id, token, bot_username)

    await update.message.reply_text(
        f"✅ Mirror bot registered\\!\n\n"
        f"🤖 Bot: @{bot_username}\n\n"
        f"Add your mirror bot to a group or channel to start using it\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
