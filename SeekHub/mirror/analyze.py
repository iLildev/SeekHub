"""
mirror/analyze.py
=================
/analyze — deep NLP analysis of a user:
  word frequency, reaction stats, activity heatmap, vocabulary score.
/export — export data as CSV (Pro/Elite only).
"""
import io
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import tg_users, sh_users
from services.nlp import (
    get_word_frequency, get_reaction_stats,
    get_activity_heatmap, format_heatmap, vocabulary_score
)
from services.export import export_chat_members, export_user_messages, export_interaction_graph
from utils.fmt import escape


async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /analyze @username or /analyze <id>
    Full NLP analysis: words, reactions, heatmap, vocabulary score.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: `/analyze @username` or `/analyze <id>`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    arg = context.args[0]
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
    name = escape(f"{user.get('first_name') or ''} {user.get('last_name') or ''}".strip() or str(uid))

    words     = get_word_frequency(uid, limit=10)
    reactions = get_reaction_stats(uid)
    heatmap   = get_activity_heatmap(uid)
    vocab     = vocabulary_score(uid)

    lines = [f"🧠 *Analysis: {name}*\n"]

    # Word frequency
    if words:
        lines.append("*📝 Top Words*")
        for word, count in words:
            lines.append(f"  `{escape(word)}` — {count}×")
    else:
        lines.append("*📝 Top Words*\n  _No message data yet_")

    # Reactions
    if reactions:
        lines.append("\n*❤️ Favorite Reactions*")
        for r in reactions[:5]:
            lines.append(f"  {r['emoji']} ×{r['total']}")

    # Vocabulary richness
    lines.append(
        f"\n*📚 Vocabulary*\n"
        f"  {vocab['unique_words']:,} unique / {vocab['total_words']:,} total words\n"
        f"  Richness: `{vocab['richness_pct']}%`"
    )

    # Activity heatmap (abbreviated — peak hours only)
    if any(heatmap.values()):
        peak_hours = sorted(heatmap.items(), key=lambda x: x[1], reverse=True)[:3]
        hours_str  = ", ".join(f"`{h:02d}:00`" for h, _ in peak_hours)
        lines.append(f"\n*🕐 Most Active Hours*\n  {hours_str}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def cmd_heatmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /heatmap @username — full 24-hour activity heatmap.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: `/heatmap @username`", parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    arg  = context.args[0]
    user = None
    try:
        user = tg_users.get(int(arg))
    except ValueError:
        user = tg_users.get_by_username(arg)

    if not user:
        await update.message.reply_text(
            f"😔 User `{escape(arg)}` not found\\.", parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    heatmap = get_activity_heatmap(user["id"])
    name    = escape(user.get("first_name") or str(user["id"]))
    chart   = format_heatmap(heatmap)

    await update.message.reply_text(
        f"🕐 *Activity Heatmap: {name}*\n\n{chart}",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /export members <chat_id>   — CSV of all members
    /export messages <user_id>  — CSV of user's messages
    /export graph <user_id>     — CSV interaction graph
    """
    uid     = update.effective_user.id
    sh_user = sh_users.get(uid)
    can_export = (sh_user or {}).get("can_export", False)

    if not can_export:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        await update.message.reply_text(
            "❌ Export requires a *Pro* or *Elite* plan\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👑 Upgrade Plan", callback_data="show_plan"),
            ]]),
        )
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "*📤 Export*\n\n"
            "`/export members <chat_id>` — member list CSV\n"
            "`/export messages <user_id>` — message history CSV\n"
            "`/export graph <user_id>` — interaction graph CSV",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    export_type = context.args[0].lower()
    try:
        target_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ ID must be a number\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    await update.message.reply_text("⏳ Generating export\\.\\.\\.", parse_mode=ParseMode.MARKDOWN_V2)

    try:
        if export_type == "members":
            data     = export_chat_members(target_id)
            filename = f"seekhub_members_{target_id}.csv"
        elif export_type == "messages":
            data     = export_user_messages(target_id)
            filename = f"seekhub_messages_{target_id}.csv"
        elif export_type == "graph":
            data     = export_interaction_graph(target_id)
            filename = f"seekhub_graph_{target_id}.csv"
        else:
            await update.message.reply_text(
                "❌ Unknown export type\\. Use: `members`, `messages`, or `graph`",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        await update.message.reply_document(
            document=InputFile(io.BytesIO(data), filename=filename),
            caption=f"✅ Export ready: `{filename}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Export failed: `{escape(str(e))}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
