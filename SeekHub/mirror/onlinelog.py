"""
mirror/onlinelog.py
===================
/onlinelog — show the recorded online-status history for a user.
Data is populated by the online_tracker task (requires Userbot).
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import tg_users
from db.connection import get_conn
from mirror.quota import charge_query
from utils.fmt import escape


STATUS_ICON = {
    "online":      "🟢",
    "recently":    "🟡",
    "last_week":   "🟠",
    "last_month":  "🔴",
    "long_ago":    "⚫",
}


async def cmd_onlinelog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /onlinelog @username  or  /onlinelog <id>
    Show the last 25 online-status snapshots for a user.
    """
    if not context.args:
        await update.message.reply_text(
            "*📡 Online Activity Log*\n\n"
            "Usage: `/onlinelog @username` or `/onlinelog <id>`\n"
            "_Shows recorded online\\-status snapshots\\._\n\n"
            "⚠️ _Requires the Userbot to be active\\._",
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
            f"😔 User `{escape(arg)}` not found\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    uid  = user["id"]
    name = escape(
        " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or str(uid)
    )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, recorded_at FROM tg_online_log
                WHERE user_id = %s
                ORDER BY recorded_at DESC
                LIMIT 25
            """, (uid,))
            logs = cur.fetchall()

    if not logs:
        await update.message.reply_text(
            f"😔 No online activity recorded for *{name}*\\.\n\n"
            "_The Userbot must be active and tracking this user\\._\n"
            "Use `/track @username online` to start tracking\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Count sessions (transitions to online)
    online_count = sum(1 for l in logs if l["status"] == "online")

    lines = [
        f"📡 *Online Log: {name}*",
        f"• Snapshots: `{len(logs)}` \\| Online sessions: `{online_count}`\n",
    ]

    for log in logs:
        icon = STATUS_ICON.get(log["status"], "⚪")
        dt   = log["recorded_at"].strftime("%Y\\-%m\\-%d %H:%M")
        lines.append(f"• {icon} `{log['status']}` — _{dt}_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
