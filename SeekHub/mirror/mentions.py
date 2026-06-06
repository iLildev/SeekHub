"""
mirror/mentions.py
==================
/mentions — top users that a given user mentions most in indexed messages.
Uses the tg_mentions table populated by the collector.
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import tg_users
from mirror.quota import charge_query
from services.nlp import get_top_mentioned
from utils.fmt import escape


async def cmd_mentions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /mentions @username  or  /mentions <id>
    Show the top users that this person mentions most.
    """
    if not context.args:
        await update.message.reply_text(
            "*🏷 Top Mentions*\n\n"
            "Usage: `/mentions @username` or `/mentions <id>`\n"
            "_Shows who a user mentions most in indexed messages\\._",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    mirror_id = context.bot_data.get("mirror_id", 0)
    allowed   = await charge_query(update, context, mirror_id, context.args[0])
    if not allowed:
        return

    arg  = context.args[0]
    user = None
    try:
        user = tg_users.get(int(arg))
    except ValueError:
        user = tg_users.get_by_username(arg)

    if not user:
        await update.message.reply_text(
            f"😔 User `{escape(arg)}` not found in the SeekHub database\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    uid  = user["id"]
    name = escape(
        " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or str(uid)
    )

    top = get_top_mentioned(uid, limit=10)

    if not top:
        await update.message.reply_text(
            f"😔 No mention data found for *{name}*\\.\n\n"
            "_No indexed messages with @mentions yet\\._",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines  = [f"🏷 *Most Mentioned by {name}*\n"]

    for i, r in enumerate(top):
        fname = escape(r.get("first_name") or r.get("mentioned_username") or "Unknown")
        uname = f" @{escape(r['mentioned_username'])}" if r.get("mentioned_username") else ""
        uid_r = r.get("user_id")
        link  = f"[{fname}](tg://user?id={uid_r})" if uid_r else fname
        lines.append(f"{medals[i]} {link}{uname} — `{r['mention_count']}`×")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
