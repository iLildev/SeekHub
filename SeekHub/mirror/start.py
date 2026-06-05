from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_users
from utils.fmt import escape


MIRROR_WELCOME = """👋 *Welcome to SeekHub Mirror*

I'm connected to the SeekHub central database — the deepest Telegram index\.

*Search Commands*
/search `@username or name` — find users & groups
/user `@username or ID` — full user profile
/group `@groupname or ID` — full group profile
/id `123456789` — look up by Telegram ID
/msearch `keyword` — search inside indexed messages

*Your Profile*
/profile — view your stats & query balance"""


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sh_users.upsert(user.id, user.username or "", user.first_name or "")
    await update.message.reply_text(MIRROR_WELCOME, parse_mode=ParseMode.MARKDOWN_V2)
