"""
system/mirrors.py
=================
Mirror management commands for the system bot.
/mirror  — list mirrors
/mystats — per-mirror dashboard for owners
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_mirrors
from db.sh_mirrors import get_mirror_stats, get_top_queries
from keyboards.system.main import back_keyboard
from utils.fmt import escape


async def cmd_mirror(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    mirrors = sh_mirrors.get_by_owner(user.id)

    if mirrors:
        lines = ["*🔮 Your Mirrors*\n"]
        for m in mirrors:
            lines.append(
                f"🤖 @{escape(m['bot_username'] or 'unknown')}\n"
                f"   Queries: `{m['query_count']}` \\| Users: `{m['user_count']}`\n"
                f"   Created: `{m['created_at'].strftime('%Y-%m-%d')}`"
            )
        lines.append("\nUse /mystats for detailed stats\\.")
        lines.append("Use /mset to configure your mirror\\.")
        lines.append("Use /token to add another mirror bot\\.")
        text = "\n".join(lines)
    else:
        text = (
            "*No Mirror Found*\n\n"
            "You don't have a mirror bot yet\\.\n\n"
            "To create one:\n"
            "1️⃣ Create a bot via @BotFather\n"
            "2️⃣ Send the token using /token\n"
            "3️⃣ Your mirror starts automatically"
        )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_keyboard(),
    )


async def cmd_mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    mirrors = sh_mirrors.get_by_owner(user.id)

    if not mirrors:
        await update.message.reply_text(
            "❌ You have no mirrors yet\\. Use /token to register one\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    lines = ["*📊 Mirror Stats Dashboard*\n"]

    for m in mirrors:
        mid      = m["id"]
        username = m["bot_username"] or "unknown"
        stats    = get_mirror_stats(mid)
        top_q    = get_top_queries(mid, limit=5)

        lines.append(f"🤖 *@{escape(username)}*")
        lines.append(f"   Total queries: `{m['query_count']:,}`")
        lines.append(f"   Total users:   `{m['user_count']:,}`")

        if stats:
            lines.append(f"   Active \\(7d\\):   `{stats.get('active_7d', 0):,}`")
            lines.append(f"   Active \\(30d\\):  `{stats.get('active_30d', 0):,}`")
            lines.append(f"   New today:     `{stats.get('new_today', 0):,}`")

        if top_q:
            lines.append("   🔍 *Top searches:*")
            for i, row in enumerate(top_q, 1):
                q = escape(row["query_text"][:30])
                lines.append(f"   {i}\\. `{q}` — `{row['cnt']}×`")

        lines.append("")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
