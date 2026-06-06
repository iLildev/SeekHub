"""
system/submit.py
================
/submit — users submit public group/channel links to grow the SeekHub
database and earn 8 crystals per accepted unique submission.

Limits:
  - Max 5 submissions per 24 hours per user
  - Duplicate groups (already indexed or already submitted) earn 0 crystals
"""
import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_users, sh_group_submissions, sh_crystals
from utils.fmt import escape

logger = logging.getLogger(__name__)

MAX_SUBMISSIONS_PER_DAY = 5
USERNAME_RE = re.compile(r"(?:t\.me/|@)([\w]+)", re.IGNORECASE)


def _extract_username(arg: str) -> str | None:
    m = USERNAME_RE.search(arg)
    if m:
        return m.group(1)
    if re.match(r"^[\w]{3,}$", arg):
        return arg
    return None


async def cmd_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    sh_user = sh_users.get(user.id)
    if not sh_user:
        sh_users.upsert(user.id, user.username or "", user.first_name or "")

    if not context.args:
        await update.message.reply_text(
            "📢 *Submit a Public Group or Channel*\n\n"
            "Help grow the SeekHub database and earn *8 crystals* for every new group you add\\!\n\n"
            "Usage:\n"
            "`/submit @groupname`\n"
            "`/submit https://t.me/groupname`\n\n"
            f"Limit: `{MAX_SUBMISSIONS_PER_DAY}` submissions per 24 hours\\.\n"
            "Duplicate groups earn no crystals\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    raw = context.args[0]
    username = _extract_username(raw)

    if not username:
        await update.message.reply_text(
            "❌ Invalid format\\. Use `@groupname` or `https://t\\.me/groupname`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    daily_count = sh_group_submissions.user_submission_today(user.id)
    if daily_count >= MAX_SUBMISSIONS_PER_DAY:
        await update.message.reply_text(
            f"⏳ You've reached the daily limit of `{MAX_SUBMISSIONS_PER_DAY}` submissions\\.\n"
            "Come back in 24 hours\\!",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    chat_id = None
    userbot = context.bot_data.get("userbot_client")
    if userbot and userbot.is_connected:
        try:
            from userbot.scraper import resolve_username
            chat_id = await resolve_username(userbot, username)
        except Exception:
            pass

    result = sh_group_submissions.submit(user.id, username, chat_id)

    if result["status"] == "duplicate":
        await update.message.reply_text(
            f"🔁 `@{escape(username)}` is already in our database\\.\n"
            "No crystals awarded for duplicates\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    sh_crystals.add(user.id, sh_group_submissions.SUBMISSION_CRYSTALS, "group_submission")

    if userbot and chat_id:
        try:
            from userbot.scraper import bulk_index_chat
            context.application.create_task(
                bulk_index_chat(userbot, chat_id, history_limit=2000)
            )
            sh_group_submissions.mark_accepted(result["id"])
            status_msg = "✅ Group verified and indexing started\\!"
        except Exception as e:
            logger.warning("Could not auto-index submitted group %s: %s", username, e)
            status_msg = "⏳ Submitted for review — indexing will begin shortly\\."
    else:
        status_msg = "⏳ Submitted for review — indexing will begin shortly\\."

    bal = sh_crystals.get_balance(user.id)

    await update.message.reply_text(
        f"🎉 *Submission received\\!*\n\n"
        f"Group: `@{escape(username)}`\n"
        f"{status_msg}\n\n"
        f"💎 *\\+8 crystals* earned\\!\n"
        f"Balance: `{bal}` crystals",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info("User %d submitted group @%s (chat_id=%s)", user.id, username, chat_id)
