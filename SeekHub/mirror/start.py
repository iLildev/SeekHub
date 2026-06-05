from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_users, tg_users
from utils.fmt import escape


MIRROR_WELCOME = """👋 *Welcome to SeekHub Mirror*

I'm connected to the SeekHub central database — the deepest Telegram index\\.

*Search Commands*
/search `@username or name` — find users & groups
/user `@username or ID` — full user profile
/group `@groupname or ID` — full group profile
/id `123456789` — look up by Telegram ID
/msearch `keyword` — search inside indexed messages
/phone `+1234567890` — search by phone number
/near `@username` — find nearby users

*Your Profile*
/profile — view your stats & query balance
/link — your referral link \\(earn crystals\\)

*Tracking*
/track `@username` — track a user
/tracks — your active tracks"""


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Upsert to both tg_users and sh_users
    tg_users.upsert(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
    )
    sh_users.upsert(user.id, user.username or "", user.first_name or "")

    # Handle referral: /start ref_12345678
    if context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0][4:])
            from mirror.link import handle_referral
            await handle_referral(referrer_id, user.id)
        except (ValueError, IndexError):
            pass

    await update.message.reply_text(MIRROR_WELCOME, parse_mode=ParseMode.MARKDOWN_V2)
