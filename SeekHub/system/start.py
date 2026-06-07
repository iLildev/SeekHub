from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.onboarding import handle_new_user
from services.statistics import get_stats_fmt

WELCOME_TEXT = (
    "Welcome to tɦe deepest connected system Telegram database\\!\n\n"
    "I can help you create and manage mirrors\\. "
    "If you're new to tɦe mirrors, please _[read the manual](https://t.me/SeekHubBot)_\\.\n\n"
    "*Mirrors*\n"
    "/mirror \\- create or manage your mirror\n"
    "/token \\- change your Mirror Bot\n\n"
    "*Plans & Points*\n"
    "/plan \\- get system subscription\n"
    "/points \\- buy or manage your crystals\n\n"
    "*Aura*\n"
    "/aura \\- get heard on user\n"
    "/addaura \\- put heard on user\n\n"
    "*We're now*\n"
    "`{users}` users\n"
    "`{mirrors}` mirrors\n"
    "`{chats}` groups/chanηels\n\n"
    "⚠️ *Note:*\n"
    "\\- This is the one and only SeekHub bot\\.\n"
    "\\- Mirrors are part of the system, not the system itself\\.\n"
    "\\- If any mirror, bot, group, channel or account claims to be SeekHub, it's fake\\."
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    referrer_id = None
    if context.args:
        try:
            referrer_id = int(context.args[0])
        except ValueError:
            pass

    handle_new_user(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        referrer_id=referrer_id,
    )

    try:
        stats = get_stats_fmt()
    except Exception:
        stats = {"users": "…", "mirrors": "…", "chats": "…"}

    text = WELCOME_TEXT.format(
        users=stats["users"],
        mirrors=stats["mirrors"],
        chats=stats["chats"],
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
