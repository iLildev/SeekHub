"""
mirror/search.py
================
Core query interface for mirror bots.
All searches hit the central SeekHub DB and go through charge_query()
which enforces daily limits and crystal-based bypass.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import tg_users, tg_chats, tg_messages, sh_hide_plans
from db.connection import get_conn
from mirror.quota import charge_query
from utils.fmt import user_line, chat_line, escape

logger = logging.getLogger(__name__)


# ── /search ───────────────────────────────────────────────────────────────────

async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/search <query> — search users AND chats."""
    if not context.args:
        await update.message.reply_text(
            "🔍 *Search SeekHub*\n\n"
            "• `/search @username` — find a user\n"
            "• `/search GroupName` — find groups/channels\n"
            "• `/id 123456789` — lookup by Telegram ID",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    query     = " ".join(context.args).strip()
    mirror_id = context.bot_data.get("mirror_id", 0)
    allowed   = await charge_query(update, context, mirror_id, query)
    if not allowed:
        return

    if query.startswith("@") or (len(query) > 3 and "_" not in query and " " not in query):
        user = tg_users.get_by_username(query)
        if user:
            await _send_user_result(update, user, searcher_id=update.effective_user.id)
            return

    users = tg_users.search(query, limit=5)
    chats = tg_chats.search(query, limit=5)

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
    """/id <telegram_id> — look up any entity by numeric ID."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/id 123456789`", parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    try:
        entity_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ ID must be a number\\.", parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    mirror_id = context.bot_data.get("mirror_id", 0)
    allowed   = await charge_query(update, context, mirror_id, str(entity_id))
    if not allowed:
        return

    user = tg_users.get(entity_id)
    if user:
        await _send_user_result(update, user, full=True, searcher_id=update.effective_user.id)
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
    """/user @username or /user <id> — full user profile."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/user @username` or `/user 123456789`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    arg       = context.args[0]
    mirror_id = context.bot_data.get("mirror_id", 0)
    allowed   = await charge_query(update, context, mirror_id, arg)
    if not allowed:
        return

    user = None
    try:
        user = tg_users.get(int(arg))
    except ValueError:
        user = tg_users.get_by_username(arg)

    if not user:
        userbot = context.bot_data.get("userbot_client")
        if userbot and userbot.is_connected:
            try:
                from userbot.scraper import resolve_username, index_user_profile
                uid = await resolve_username(userbot, arg)
                if uid:
                    await index_user_profile(userbot, uid)
                    user = tg_users.get(uid)
            except Exception:
                pass

    if not user:
        await update.message.reply_text(
            f"😔 User `{escape(arg)}` not found in SeekHub database\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    await _send_user_result(update, user, full=True, searcher_id=update.effective_user.id)


# ── /group ────────────────────────────────────────────────────────────────────

async def cmd_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/group @username or /group <id> — full group/channel profile."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/group @groupname` or `/group 123456789`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    arg       = context.args[0]
    mirror_id = context.bot_data.get("mirror_id", 0)
    allowed   = await charge_query(update, context, mirror_id, arg)
    if not allowed:
        return

    chat = None
    try:
        chat = tg_chats.get(int(arg))
    except ValueError:
        chat = tg_chats.get_by_username(arg)

    if not chat:
        await update.message.reply_text(
            f"😔 Group/channel `{escape(arg)}` not found\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    await _send_chat_result(update, chat, full=True)


# ── /msearch ──────────────────────────────────────────────────────────────────

async def cmd_msearch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/msearch <keyword> — full-text search inside indexed messages."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/msearch keyword`", parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    query     = " ".join(context.args).strip()
    mirror_id = context.bot_data.get("mirror_id", 0)
    allowed   = await charge_query(update, context, mirror_id, query)
    if not allowed:
        return

    results = tg_messages.search_text(query, limit=10)

    if not results:
        await update.message.reply_text(
            f"😔 No messages found for `{escape(query)}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    lines = [f"💬 *Messages matching* `{escape(query)}`\n"]
    for r in results[:5]:
        chat_ref  = f"@{escape(r['chat_username'])}" if r["chat_username"] else escape(str(r["chat_id"]))
        sender    = escape(r["first_name"] or "Unknown")
        text_prev = escape((r["text"] or r["caption"] or "")[:80].replace("\n", " "))
        date_str  = r["date"].strftime("%Y\\-%m\\-%d") if r["date"] else "unknown"
        lines.append(
            f"• [{sender}](tg://user?id={r['sender_id']}) in {chat_ref}\n"
            f"  `{text_prev}`\n"
            f"  _{date_str}_"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── Privacy / Hide layer ──────────────────────────────────────────────────────

def _check_hide(user_id: int, searcher_id: int) -> str | None:
    """Returns 'shadow', 'ghost', or None."""
    sub = sh_hide_plans.get_active_subscription(user_id)
    if not sub:
        return None
    feat = sub.get("plan_features") or {}
    if feat.get("see_searchers") and searcher_id != user_id:
        from db.sh_hide_plans import notify_searcher
        notify_searcher(user_id, searcher_id)
    if feat.get("hide_all"):
        return "shadow"
    if feat.get("hide_username"):
        return "ghost"
    return None


def _get_photo_count(user_id: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM tg_photo_history WHERE user_id = %s",
                (user_id,)
            )
            return cur.fetchone()["cnt"]


# ── User result card ──────────────────────────────────────────────────────────

async def _send_user_result(update: Update, user: dict, full: bool = False,
                            searcher_id: int | None = None):
    uid        = user["id"]
    hide_level = _check_hide(uid, searcher_id or 0)
    if hide_level == "shadow":
        return

    name  = escape(" ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or "Unknown")
    uname = (
        "🔒 _hidden_"
        if hide_level == "ghost"
        else (f"@{escape(user['username'])}" if user.get("username") else "_no username_")
    )

    badges = []
    if user.get("is_premium"):  badges.append("💎 Premium")
    if user.get("is_verified"): badges.append("✅ Verified")
    if user.get("is_deleted"):  badges.append("🗑 Deleted")
    if user.get("is_bot"):      badges.append("🤖 Bot")

    lines = [f"👤 *{name}*"]
    lines.append(f"• ID: `{uid}`")
    lines.append(f"• Username: {uname}")
    if badges:
        badge_str = " | ".join(badges)
        lines.append(f"• {badge_str}")

    if full:
        lines.append("")

        # ── History section ────────────────────────────────────────────────────
        hist_lines = []

        username_hist = tg_users.get_username_history(uid)
        if len(username_hist) > 1:
            old = [f"`@{escape(h['username'])}`" for h in username_hist[1:5]]
            hist_lines.append(f"• 🔄 Old usernames: {', '.join(old)}")

        name_hist = tg_users.get_name_history(uid)
        if len(name_hist) > 1:
            old_names = [
                escape(" ".join(filter(None, [h["first_name"], h["last_name"]])))
                for h in name_hist[1:4]
            ]
            hist_lines.append(f"• 📝 Old names: {', '.join(old_names)}")

        bio_hist = tg_users.get_bio_history(uid)
        if bio_hist:
            bio_text = escape(bio_hist[0]["bio"][:150]) if bio_hist[0].get("bio") else "_empty_"
            hist_lines.append(f"• 📋 Bio: _{bio_text}_")
            if len(bio_hist) > 1:
                hist_lines.append(f"• 🔁 Bio changed `{len(bio_hist) - 1}`× before")
        elif user.get("bio"):
            hist_lines.append(f"• 📋 Bio: _{escape(user['bio'][:150])}_")

        photo_count = _get_photo_count(uid)
        if photo_count > 0:
            hist_lines.append(f"• 🖼 Profile photos: `{photo_count}` recorded")

        if hist_lines:
            lines.append("📜 *History*")
            lines.extend(hist_lines)
            lines.append("")

        # ── Activity section ───────────────────────────────────────────────────
        stats = tg_users.get_message_stats(uid)
        if stats and stats["total_messages"]:
            lines.append("📊 *Activity*")
            lines.append(f"• 💬 Messages: `{stats['total_messages']}` \\| 📸 Media: `{stats['total_media']}`")
            lines.append(f"• 🗂 Active in `{stats['chat_count']}` chats")
            if stats.get("first_seen"):
                date_str = stats["first_seen"].strftime("%Y\\-%m\\-%d")
                lines.append(f"• 📅 First seen: `{date_str}`")
            if stats.get("last_seen"):
                date_str = stats["last_seen"].strftime("%Y\\-%m\\-%d")
                lines.append(f"• 🕐 Last active: `{date_str}`")
            lines.append("")

        # ── Groups section ─────────────────────────────────────────────────────
        groups = tg_users.get_chats(uid, limit=10)
        if groups:
            glist = []
            for g in groups:
                gref = f"@{g['username']}" if g.get("username") else (g.get("title") or str(g["id"]))
                glist.append(f"`{escape(gref)}`")
            lines.append(f"💬 *Seen in \\({len(groups)}\\)*")
            lines.append("• " + ", ".join(glist))

    buttons = []
    if full:
        buttons.append([
            InlineKeyboardButton("🤝 Mutual", callback_data=f"mutual:{uid}"),
            InlineKeyboardButton("💬 Messages", callback_data=f"user_msgs:{uid}:0"),
        ])
        buttons.append([
            InlineKeyboardButton("🔗 Interactions", callback_data=f"interactions:{uid}"),
            InlineKeyboardButton("📍 Near Users", callback_data=f"near:{uid}"),
        ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
    )


# ── Chat result card ──────────────────────────────────────────────────────────

async def _send_chat_result(update: Update, chat: dict, full: bool = False):
    cid   = chat["id"]
    title = escape(chat.get("title") or "Untitled")
    uname = f"@{escape(chat['username'])}" if chat.get("username") else "_no username_"
    ctype = {"supergroup": "Supergroup", "group": "Group",
              "channel": "Channel", "gigagroup": "Gigagroup"}.get(chat["type"], chat["type"])
    icon  = "📢" if chat["type"] == "channel" else "💬"

    lines = [f"{icon} *{title}*"]
    lines.append(f"• ID: `{cid}`")
    lines.append(f"• Type: {ctype}")
    lines.append(f"• Username: {uname}")
    if chat.get("member_count"):
        lines.append(f"• 👥 Members: `{chat['member_count']:,}`")

    flags = []
    if chat.get("is_verified"):  flags.append("✅ Verified")
    if chat.get("is_scam"):      flags.append("⚠️ Scam")
    if chat.get("is_fake"):      flags.append("⚠️ Fake")
    if flags:
        flag_str = " | ".join(flags)
        lines.append(f"• {flag_str}")

    if full:
        lines.append("")

        if chat.get("description"):
            lines.append(f"📋 *Description*")
            lines.append(f"• _{escape(chat['description'][:200])}_")
            lines.append("")

        hist = tg_chats.get_history(cid)
        if len(hist) > 1:
            old_titles = [escape(h["title"]) for h in hist[1:4] if h.get("title")]
            if old_titles:
                lines.append(f"🔄 *Previous names*")
                for t in old_titles:
                    lines.append(f"• _{t}_")
                lines.append("")

        top = tg_chats.get_top_posters(cid, limit=5)
        if top:
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            lines.append("🏆 *Top Members*")
            for i, m in enumerate(top):
                n = escape(m["first_name"] or "Unknown")
                lines.append(f"• {medals[i]} {n} — `{m['message_count']}` msgs")

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
