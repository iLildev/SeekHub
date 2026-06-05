from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.onboarding import handle_new_user
from services.statistics import get_stats, format_count
from keyboards.system.main import main_keyboard


WELCOME_TEXT = """Welcome to tɦe deepest connected system Telegram database\!

I can help you create and manage mirrors\. If you're new to tɦe mirrors, please read the manual\.

*Mirrors*
/mirror \- create or manage your mirror
/token \- change your Mirror Bot

*Plans & Points*
/plan \- get system subscription
/points \- buy or manage your crystals

*Aura*
/aura \- get heard on user
/addaura \- put heard on user

We're now
`{users}` users
`{mirrors}` mirrors
`{groups}` groups/chanηels

⚠️ *Note:*
\- This is the one and only SeekHub bot\.
\- Mirrors are part of the system, not the system itself\.
\- If any mirror, bot, group, channel or account claims to be SeekHub, it's fake\."""


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

    stats = get_stats()
    text = WELCOME_TEXT.format(
        users=format_count(stats["users"]),
        mirrors=format_count(stats["mirrors"]),
        groups=format_count(stats["groups"]),
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_keyboard(),
    )
