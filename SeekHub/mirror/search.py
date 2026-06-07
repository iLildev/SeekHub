"""
mirror/search.py
================
Core query interface for mirror bots.
All searches go through charge_query() which enforces daily limits
and crystal-based bypass.

Profile cards: clean, structured layout with clear action buttons.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import tg_users, tg_chats, tg_messages, sh_hide_plans, sh_users
from mirror.quota import charge_query
from utils.fmt import user_line, chat_line, escape

logger = logging.getLogger(__name__)

# Crystal costs per feature (must match callbacks.py)
CRYSTAL_COSTS = {
    "names":     7,
    "groups":   15,
    "messages": 20,
    "channels": 15,
    "friends":   8,
    "reactions": 10,
}


# ── /search ───────────────────────────────────────────────────────────────────

async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "🔍 *Search SeekHub*\n\n"
            "Send a name, @username, or keyword — or just type it without any command\\.\n\n"
            "• `/search @username` — find a specific user\n"
            "• `/search GroupName` — find groups or channels\n"
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
            f"😔 No results for `{escape(query)}`\n\n"
            "_Try a different spelling, or use /id to search by Telegram ID_",
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


# ── Clean User Profile Card ───────────────────────────────────────────────────

async def _send_user_result(update: Update, user: dict, full: bool = True,
                            searcher_id: int | None = None):
    uid        = user["id"]
    hide_level = _check_hide(uid, searcher_id or 0)
    if hide_level == "shadow":
        return

    # Track view
    if searcher_id:
        try:
            tg_users.track_profile_view(searcher_id, uid)
        except Exception:
            pass

    fn    = user.get("first_name") or ""
    ln    = user.get("last_name") or ""
    name  = escape((fn + " " + ln).strip() or "Unknown")
    uname = user.get("username") or ""

    if hide_level == "ghost":
        uname_display = ""
    elif uname:
        uname_display = f"@{escape(uname)}"
    else:
        uname_display = "_no username_"

    # ── Header ────────────────────────────────────────────────────────────────
    # Badges row
    badges = []
    if user.get("is_premium"):  badges.append("💎 Premium")
    if user.get("is_verified"): badges.append("✅ Verified")
    if user.get("is_bot"):      badges.append("🤖 Bot")
    if user.get("is_deleted"):  badges.append("🗑 Deleted")
    badge_line = "  ".join(badges) if badges else ""

    uses_seekhub = sh_users.is_seekhub_user(uid)
    seekhub_line = "✅ SeekHub user" if uses_seekhub else "⚪ Not on SeekHub"

    lines = [f"👤 *{name}*"]
    if uname_display:
        lines.append(uname_display)
    if badge_line:
        lines.append(badge_line)
    lines.append(seekhub_line)
    lines.append(f"`{uid}`")

    # ── Stats ─────────────────────────────────────────────────────────────────
    stats         = tg_users.get_extended_stats(uid)
    total_msgs    = int(stats.get("total_messages") or 0)
    total_media   = int(stats.get("total_media")    or 0)
    total_replies = int(stats.get("total_replies")  or 0)
    group_count   = int(stats.get("group_count")    or 0)
    circles       = int(stats.get("circles")        or 0)
    voice         = int(stats.get("voice")          or 0)
    admin_count   = int(stats.get("admin_count")    or 0)
    fav           = stats.get("fav_group")
    first_msg     = stats.get("first_message")
    last_msg      = stats.get("last_message")

    reply_pct = round(total_replies / total_msgs * 100) if total_msgs else 0
    media_pct = round(total_media   / total_msgs * 100) if total_msgs else 0

    lines.append("")
    lines.append("📊 *Activity*")

    if first_msg and last_msg:
        from_d = escape(first_msg.strftime("%b %Y"))
        to_d   = escape(last_msg.strftime("%b %Y"))
        lines.append(f"• Active: `{from_d}` → `{to_d}`")

    lines.append(f"• Messages: `{total_msgs:,}` across `{group_count}` groups")

    if total_msgs > 0:
        lines.append(f"• Replies: `{reply_pct}%`  ·  Media: `{media_pct}%`")

    if circles or voice:
        lines.append(f"• Voice notes: `{voice}`  ·  Video circles: `{circles}`")

    if admin_count:
        lines.append(f"• Admin in `{admin_count}` group{'s' if admin_count != 1 else ''}")

    if fav:
        fav_name = escape(fav.get("title") or fav.get("username") or "Unknown")
        lines.append(f"• Favorite group: {fav_name}")

    view_count = tg_users.get_profile_view_count(uid)
    if view_count:
        lines.append(f"• Profile views: `{view_count}`")

    # ── History preview ───────────────────────────────────────────────────────
    username_hist = tg_users.get_username_history(uid)
    name_hist     = tg_users.get_name_history(uid)

    if username_hist and len(username_hist) > 1:
        prev = [f"@{escape(h['username'])}" for h in username_hist[1:4] if h.get("username")]
        if prev:
            lines.append("")
            lines.append(f"🔄 *Previous usernames*: {' · '.join(prev)}")

    if name_hist and len(name_hist) > 1:
        lines.append("")
        lines.append("📝 *Name changes*")
        for h in name_hist[1:3]:
            dt     = h["seen_at"].strftime("%b %Y") if h.get("seen_at") else "?"
            full_n = " ".join(filter(None, [h.get("first_name"), h.get("last_name")])) or "?"
            lines.append(f"  `{dt}` — {escape(full_n)}")

    # ── Action buttons (clean, clear labels) ─────────────────────────────────
    costs = CRYSTAL_COSTS
    buttons = [
        [
            InlineKeyboardButton("📊 Full Stats",          callback_data=f"stats:{uid}"),
            InlineKeyboardButton("🧠 Analysis",            callback_data=f"analysis:{uid}"),
            InlineKeyboardButton("🔔 Track",               callback_data=f"track_user:{uid}"),
        ],
        [
            InlineKeyboardButton(f"📋 Name History  {costs['names']}💠",    callback_data=f"crystal_names:{uid}"),
            InlineKeyboardButton(f"👥 Groups  {costs['groups']}💠",         callback_data=f"crystal_groups:{uid}"),
        ],
        [
            InlineKeyboardButton(f"💬 Messages  {costs['messages']}💠",     callback_data=f"crystal_msgs:{uid}:0"),
            InlineKeyboardButton(f"📢 Channels  {costs['channels']}💠",     callback_data=f"crystal_channels:{uid}"),
        ],
        [
            InlineKeyboardButton(f"🤝 Interactions  {costs['friends']}💠",  callback_data=f"crystal_friends:{uid}"),
            InlineKeyboardButton(f"❤️ Reactions  {costs['reactions']}💠",   callback_data=f"crystal_reactions:{uid}"),
        ],
        [
            InlineKeyboardButton("🤝 Mutual Groups",       callback_data=f"mutual:{uid}"),
            InlineKeyboardButton("🌟 Reputation",          callback_data=f"aura:{uid}"),
            InlineKeyboardButton("🔗 Share",               switch_inline_query=f"user {uid}"),
        ],
    ]

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ── Chat result card ──────────────────────────────────────────────────────────

async def _send_chat_result(update: Update, chat: dict, full: bool = False):
    cid   = chat["id"]
    title = escape(chat.get("title") or "Untitled")
    uname = f"@{escape(chat['username'])}" if chat.get("username") else "_no username_"
    ctype = {
        "supergroup": "Supergroup", "group": "Group",
        "channel": "Channel",       "gigagroup": "Gigagroup",
    }.get(chat["type"], chat["type"])
    icon = "📢" if chat["type"] == "channel" else "💬"

    lines = [f"{icon} *{title}*"]
    lines.append(f"• `{cid}`  ·  {ctype}  ·  {uname}")
    if chat.get("member_count"):
        lines.append(f"• 👥 `{chat['member_count']:,}` members")

    flags = []
    if chat.get("is_verified"): flags.append("✅ Verified")
    if chat.get("is_scam"):     flags.append("⚠️ Scam")
    if chat.get("is_fake"):     flags.append("⚠️ Fake")
    if flags:
        lines.append(f"• {' | '.join(flags)}")

    if full:
        if chat.get("description"):
            lines.append("")
            lines.append(f"_{escape(chat['description'][:200])}_")

        hist = tg_chats.get_history(cid)
        if len(hist) > 1:
            old_titles = [escape(h["title"]) for h in hist[1:4] if h.get("title")]
            if old_titles:
                lines.append("")
                lines.append("🔄 *Previous names:* " + "  ·  ".join(old_titles))

        top = tg_chats.get_top_posters(cid, limit=5)
        if top:
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            lines.append("")
            lines.append("🏆 *Top Members*")
            for i, m in enumerate(top):
                n = escape(m["first_name"] or "Unknown")
                lines.append(f"  {medals[i]} {n} — `{m['message_count']}` msgs")

    buttons = []
    if full:
        buttons.append([
            InlineKeyboardButton("👥 Members",  callback_data=f"members:{cid}:0"),
            InlineKeyboardButton("💬 Messages", callback_data=f"chat_msgs:{cid}:0"),
        ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
    )
