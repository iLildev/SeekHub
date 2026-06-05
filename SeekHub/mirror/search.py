from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db.connection import get_conn


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /search \\<keyword\\>\n\nExample: /search music",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    query = " ".join(context.args).strip()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title FROM seekhub_groups WHERE title ILIKE %s LIMIT 10",
                (f"%{query}%",)
            )
            results = cur.fetchall()

    if not results:
        await update.message.reply_text(
            f"No groups/channels found for *{query}*\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    lines = [f"🔍 *Results for* `{query}`:\n"]
    for row in results:
        lines.append(f"• {row['title']}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
