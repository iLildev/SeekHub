"""
mirror/search.py
================
The core query interface exposed to end-users via mirror bots.
Every query here hits the central SeekHub DB.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import tg_users, tg_chats, tg_messages
from db.sh_mirrors import increment_query_count, track_mirror_user
from utils.fmt import user_line, chat_line, escape

logger = logging.getLogger(__name__)


async def _charge_query(context: ContextTypes.DEFAULT_TYPE, user_id: int, mirror_id: int) -> bool:
    """
    Returns True if the query is allowed.
    In Free plan: 5 queries/day (enforced later via rate-limit table).
    For now returns True always — rate limiting is a future feature.
    """
    track_mirror_user(mirror_id, user_id)
    increment_query_count(mirror_id)
    return True


# ── /search ───────────────────────────────────────────────────────────────────

async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /search <query>
    Search for users AND chats matching the query.
    """
    if not context.args:
        await update.message.reply_text(
            "🔍 *Search the SeekHub database*\n\n"
            "Usage:\n"
            "`/search @username` — find a user\n"
            "`/search GroupName` — find groups/channels\n"
            "`/id 123456789` — look up by Telegram ID",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    query = " ".join(context.args).strip()
    mirror_id = context.bot_data.get("mirror_id", 0)
    await _charge_query(context, update.effective_user.id, mirror_id)

    # Username lookup — exact match first
    if query.startswith("@") or (len(query) > 3 and "_" not in query and " " not in query):
        user = tg_users.get_by_username(query)
        if user:
            await _send_user_result(update, user)
            return

    # Full-text search — users + chats combined
    users  = tg_users.search(query, limit=5)
    chats  = tg_chats.search(query, limit=5)

    if not users and not chats:
        await update.message.reply_text(
            f"😔 No results found for `{escape(query)}`\n\n"
            "_Try a different spelling or use /id to search by Telegram ID_",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    lines = [f"🔍 *Results for* `{escape(query)}`\n"]

    if users:
        lines.append("*👤 Users*")
        for u in users:
            lines.append(user_line(u))

    if chats:
        lines.append("\n*💬 Groups & Channels*")
        for c in chats:
            lines.append(chat_line(c))

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔍 More results", callback_data=f"search_more:{query}:0"),
    ]])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=keyboard,
    )


# ── /id ───────────────────────────────────────────────────────────────────────

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /id <telegram_id>
    Look up any Telegram entity by numeric ID.
    """
    if not context.args:
        await update.message.reply_text("Usage: `/id 123456789`", parse_mode=ParseMode.MARKDOWN_V2)
        return

    try:
        entity_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID must be a number\.")
        return

    mirror_id = context.bot_data.get("mirror_id", 0)
    await _charge_query(context, update.effective_user.id, mirror_id)

    user = tg_users.get(entity_id)
    if user:
        await _send_user_result(update, user, full=True)
        return

    chat = tg_chats.get(entity_id)
    if chat:
        await _send_chat_result(update, chat, full=True)
        return

    await update.message.reply_text(
        f"😔 No entity found with ID `{entity_id}`",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── /user ─────────────────────────────────────────────────────────────────────

async def cmd_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /user @username  or  /user <id>
    Full profile: name history, username history, groups, message stats.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: `/user @username` or `/user 123456789`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    arg = context.args[0]
    mirror_id = context.bot_data.get("mirror_id", 0)
    await _charge_query(context, update.effective_user.id, mirror_id)

    user = None
    try:
        user = tg_users.get(int(arg))
    except ValueError:
        user = tg_users.get_by_username(arg)

    if not user:
        await update.message.reply_text(
            f"😔 User `{escape(arg)}` not found in SeekHub database\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    await _send_user_result(update, user, full=True)


# ── /group ────────────────────────────────────────────────────────────────────

async def cmd_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /group @username  or  /group <id>
    Full group/channel profile: member count, top posters, history.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: `/group @groupname` or `/group 123456789`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    arg = context.args[0]
    mirror_id = context.bot_data.get("mirror_id", 0)
    await _charge_query(context, update.effective_user.id, mirror_id)

    chat = None
    try:
        chat = tg_chats.get(int(arg))
    except ValueError:
        chat = tg_chats.get_by_username(arg)

    if not chat:
        await update.message.reply_text(
            f"😔 Group/channel `{escape(arg)}` not found\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    await _send_chat_result(update, chat, full=True)


# ── /msearch ──────────────────────────────────────────────────────────────────

async def cmd_msearch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /msearch <keyword>
    Full-text search inside indexed messages.
    """
    if not context.args:
        await update.message.reply_text(
            "Usage: `/msearch keyword` — search indexed messages",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    query = " ".join(context.args).strip()
    mirror_id = context.bot_data.get("mirror_id", 0)
    await _charge_query(context, update.effective_user.id, mirror_id)

    results = tg_messages.search_text(query, limit=10)

    if not results:
        await update.message.reply_text(
            f"😔 No messages found for `{escape(query)}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    lines = [f"💬 *Messages matching* `{escape(query)}`\n"]
    for r in results[:5]:
        chat_ref  = f"@{r['chat_username']}" if r["chat_username"] else str(r["chat_id"])
        sender    = r["first_name"] or "Unknown"
        text_prev = (r["text"] or r["caption"] or "")[:80].replace("\n", " ")
        lines.append(
            f"• [{escape(sender)}](tg://user?id={r['sender_id']}) in {escape(chat_ref)}\n"
            f"  `{escape(text_prev)}`\n"
            f"  _{r['date'].strftime('%Y-%m-%d') if r['date'] else 'unknown'}_"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── Formatters ────────────────────────────────────────────────────────────────

async def _send_user_result(update: Update, user: dict, full: bool = False):
    uid = user["id"]
    name = escape(" ".join(filter(None, [user.get("first_name"), user.get("last_name")])))
    uname = f"@{escape(user['username'])}" if user.get("username") else "_no username_"

    lines = [
        f"👤 *{name}*",
        f"ID: `{uid}`",
        f"Username: {uname}",
    ]

    if user.get("is_premium"):  lines.append("💎 Premium")
    if user.get("is_verified"): lines.append("✅ Verified")
    if user.get("is_deleted"):  lines.append("🗑 Deleted account")
    if user.get("is_bot"):      lines.append("🤖 Bot")

    if full:
        # Username history
        history = tg_users.get_username_history(uid)
        if len(history) > 1:
            old = [f"`@{escape(h['username'])}`" for h in history[1:5]]
            lines.append(f"\n🔄 *Previous usernames:* {', '.join(old)}")

        # Name history
        name_hist = tg_users.get_name_history(uid)
        if len(name_hist) > 1:
            old_names = [escape(" ".join(filter(None, [h["first_name"], h["last_name"]]))) for h in name_hist[1:4]]
            lines.append(f"📝 *Previous names:* {', '.join(old_names)}")

        # Bio
        if user.get("bio"):
            lines.append(f"\n📋 *Bio:* {escape(user['bio'][:200])}")

        # Message stats
        stats = tg_users.get_message_stats(uid)
        if stats and stats["total_messages"]:
            lines.append(
                f"\n📊 *Activity*\n"
                f"Messages: `{stats['total_messages']}`  |  "
                f"Media: `{stats['total_media']}`  |  "
                f"Chats: `{stats['chat_count']}`"
            )
            if stats["first_seen"]:
                lines.append(f"First seen: `{stats['first_seen'].strftime('%Y-%m-%d')}`")

        # Groups
        groups = tg_users.get_chats(uid, limit=8)
        if groups:
            glist = []
            for g in groups:
                gref = f"@{g['username']}" if g.get("username") else g["title"] or str(g["id"])
                glist.append(f"`{escape(gref)}`")
            lines.append(f"\n💬 *Seen in:* {', '.join(glist)}")

    buttons = []
    if full:
        buttons.append([
            InlineKeyboardButton("🤝 Mutual Groups", callback_data=f"mutual:{uid}"),
            InlineKeyboardButton("💬 Messages", callback_data=f"user_msgs:{uid}:0"),
        ])
        buttons.append([
            InlineKeyboardButton("🔗 Interactions", callback_data=f"interactions:{uid}"),
        ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
    )


async def _send_chat_result(update: Update, chat: dict, full: bool = False):
    cid   = chat["id"]
    title = escape(chat.get("title") or "Untitled")
    uname = f"@{escape(chat['username'])}" if chat.get("username") else "_no username_"
    ctype = {"supergroup": "Supergroup", "group": "Group",
              "channel": "Channel", "gigagroup": "Gigagroup"}.get(chat["type"], chat["type"])

    lines = [
        f"{'📢' if chat['type']=='channel' else '💬'} *{title}*",
        f"ID: `{cid}`",
        f"Type: {ctype}",
        f"Username: {uname}",
    ]

    if chat.get("member_count"):
        lines.append(f"Members: `{chat['member_count']:,}`")
    if chat.get("is_verified"):  lines.append("✅ Verified")
    if chat.get("is_scam"):      lines.append("⚠️ Scam")
    if chat.get("is_fake"):      lines.append("⚠️ Fake")

    if full:
        if chat.get("description"):
            lines.append(f"\n📋 {escape(chat['description'][:200])}")

        # History
        hist = tg_chats.get_history(cid)
        if len(hist) > 1:
            old_titles = [escape(h["title"]) for h in hist[1:4] if h.get("title")]
            if old_titles:
                lines.append(f"\n🔄 *Previous names:* {', '.join(old_titles)}")

        # Top posters
        top = tg_chats.get_top_posters(cid, limit=5)
        if top:
            lines.append("\n🏆 *Top Members*")
            medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
            for i, m in enumerate(top):
                n = escape(m["first_name"] or "Unknown")
                lines.append(f"{medals[i]} {n} — `{m['message_count']}` msgs")

    buttons = []
    if full:
        buttons.append([
            InlineKeyboardButton("👥 Members", callback_data=f"members:{cid}:0"),
            InlineKeyboardButton("💬 Messages", callback_data=f"chat_msgs:{cid}:0"),
        ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
    )
