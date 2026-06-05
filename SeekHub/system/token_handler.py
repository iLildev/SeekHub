import asyncio
import logging
from telegram import Update, Bot
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_mirrors, sh_users, tg_users
from utils.fmt import escape

logger = logging.getLogger(__name__)


async def cmd_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "*🔑 Register Mirror Bot*\n\n"
            "Usage: `/token <your\\_bot\\_token>`\n\n"
            "Get a token from @BotFather\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    token = context.args[0].strip()
    if ":" not in token or len(token) < 30:
        await update.message.reply_text(
            "❌ Invalid token format\\.\nA valid token looks like: `1234567890:ABCdef\\.\\.\\.`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Validate the token with Telegram
    try:
        bot = Bot(token=token)
        bot_info = await bot.get_me()
    except Exception:
        await update.message.reply_text(
            "❌ Could not verify this token\\. Make sure it's correct and try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Ensure user exists in both tg_users and sh_users BEFORE touching sh_mirrors
    tg_users.upsert(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
    )
    sh_users.upsert(user.id, user.username or "", user.first_name or "")

    # Register mirror in DB
    mirror = sh_mirrors.create(
        owner_id=user.id,
        bot_token=token,
        bot_id=bot_info.id,
        bot_username=bot_info.username,
    )

    await update.message.reply_text(
        f"✅ Mirror registered\\!\n\n"
        f"🤖 Bot: @{escape(bot_info.username)}\n\n"
        f"Your mirror is now live and connected to the SeekHub database\\.\n"
        f"Users can search via your mirror and you earn crystals per query\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    # Signal the runner to start this mirror bot
    if "mirror_runner" in context.application.bot_data:
        runner = context.application.bot_data["mirror_runner"]
        userbot = context.application.bot_data.get("userbot_client")
        asyncio.create_task(runner.start_mirror(mirror["id"], token, userbot_client=userbot))
        logger.info("Triggered start for new mirror bot @%s", bot_info.username)
