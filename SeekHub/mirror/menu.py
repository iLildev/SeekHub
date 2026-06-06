"""
mirror/menu.py
==============
Handles all persistent keyboard button presses, native Telegram
UsersShared / ChatShared events, and the conversational "awaiting input"
state for free-text Search/Seek flow.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import tg_users, tg_chats, sh_hide_plans
from db.sh_mirrors import increment_query_count, track_mirror_user, log_query
from mirror.quota import charge_query
from utils.fmt import escape, user_line, chat_line
from keyboards.mirror.main import (
    main_keyboard, select_keyboard,
    BTN_SEARCH, BTN_MENU, BTN_SELECT, BTN_BACK,
    ALL_BUTTONS,
    REQ_USER, REQ_BOT, REQ_GROUP, REQ_CHANNEL,
)

logger = logging.getLogger(__name__)


# ── Inline menu shown when pressing 📋 Menu ───────────────────────────────────

def _menu_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 Message Search", switch_inline_query_current_chat=""),
            InlineKeyboardButton("📍 Nearby Users",   callback_data="kb_near"),
        ],
        [
            InlineKeyboardButton("📞 Phone Lookup",   callback_data="kb_phone"),
            InlineKeyboardButton("👁 Track a User",   callback_data="kb_track"),
        ],
        [
            InlineKeyboardButton("📊 My Profile",     callback_data="kb_profile"),
            InlineKeyboardButton("🔗 My Referral",    callback_data="kb_link"),
        ],
        [
            InlineKeyboardButton("📋 My Tracks",      callback_data="kb_tracks"),
            InlineKeyboardButton("📤 Export",         callback_data="kb_export"),
        ],
    ])


# ── Handle UsersShared (👤 User / 🤖 Bot native picker) ──────────────────────

async def handle_users_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called when the user picks a user/bot via the native Telegram picker."""
    msg       = update.message
    shared    = msg.users_shared          # UsersShared object
    req_id    = shared.request_id
    mirror_id = context.bot_data.get("mirror_id", 0)
    user      = update.effective_user
    bots_only = (req_id == REQ_BOT)

    # charge_query handles tracking + quota + crystal deduction
    allowed = await charge_query(update, context, mirror_id)
    if not allowed:
        return

    # shared.users is a list of SharedUser objects
    for shared_user in shared.users:
        uid = shared_user.user_id
        log_query(mirror_id, str(uid))

        record = tg_users.get(uid)
        if not record:
            await msg.reply_text(
                f"😔 User `{uid}` not found in SeekHub database\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            continue

        if bots_only and not record.get("is_bot"):
            await msg.reply_text(
                f"⚠️ `{escape(record.get('username', str(uid)))}` is not a bot\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            continue

        if _is_shadow(uid, user.id):
            await msg.reply_text(
                "😔 This user has hidden themselves from search results\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            continue

        await _send_user(update, record, user.id)


# ── Handle ChatShared (👥 Group / 📢 Channel native picker) ──────────────────

async def handle_chat_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called when the user picks a group/channel via the native Telegram picker."""
    msg       = update.message
    shared    = msg.chat_shared           # ChatShared object
    req_id    = shared.request_id
    mirror_id = context.bot_data.get("mirror_id", 0)
    user      = update.effective_user
    chat_type = "channel" if req_id == REQ_CHANNEL else "group"

    # charge_query handles tracking + quota + crystal deduction
    allowed = await charge_query(update, context, mirror_id)
    if not allowed:
        return

    cid = shared.chat_id
    log_query(mirror_id, str(cid))

    record = tg_chats.get(cid)
    if not record:
        # Try by username if provided
        if hasattr(shared, "username") and shared.username:
            record = tg_chats.get_by_username(shared.username)

    if not record:
        icon = "📢" if chat_type == "channel" else "👥"
        name = getattr(shared, "title", None) or str(cid)
        await msg.reply_text(
            f"😔 {icon} *{escape(name)}* not found in SeekHub database\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Type mismatch guard
    actual_type = record.get("type", "")
    if chat_type == "channel" and actual_type != "channel":
        await msg.reply_text(
            "⚠️ This is a group, not a channel\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    if chat_type == "group" and actual_type == "channel":
        await msg.reply_text(
            "⚠️ This is a channel, not a group\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    from mirror.search import _send_chat_result
    await _send_chat_result(update, record, full=True)


# ── Main text-button dispatcher ───────────────────────────────────────────────

async def handle_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text keyboard buttons + free-text awaiting flow."""
    text      = (update.message.text or "").strip()
    mirror_id = context.bot_data.get("mirror_id", 0)
    user      = update.effective_user

    # ── Navigation ────────────────────────────────────────────────────────────
    if text == BTN_SELECT:
        context.user_data.pop("awaiting", None)
        await update.message.reply_text(
            "🎯 *Select what to look up:*\n\n"
            "Tap a button — Telegram will open its native picker\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=select_keyboard(),
        )
        return

    if text == BTN_BACK:
        context.user_data.pop("awaiting", None)
        await update.message.reply_text(
            "🏠 Main menu",
            reply_markup=main_keyboard(),
        )
        return

    if text == BTN_MENU:
        context.user_data.pop("awaiting", None)
        await update.message.reply_text(
            "📋 *Features*\n\nChoose what you want to do:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=_menu_inline(),
        )
        return

    if text == BTN_SEARCH:
        context.user_data["awaiting"] = "search"
        await update.message.reply_text(
            "🔍 *Search SeekHub*\n\n"
            "Type any name, @username, or keyword\\.\n"
            "I'll search across users, groups, channels and bots\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # ── Direct lookup: @username or numeric ID sent without any command ──────
    is_username = text.startswith("@") and len(text) > 1
    is_numeric  = text.lstrip("-").isdigit() and len(text) >= 5

    if is_username or is_numeric:
        context.user_data.pop("awaiting", None)
        allowed = await charge_query(update, context, mirror_id, text)
        if not allowed:
            return
        await _do_direct_lookup(update, text, user.id)
        return

    # ── Free-text: process awaited input ─────────────────────────────────────
    awaiting = context.user_data.get("awaiting")
    if awaiting and text:
        context.user_data.pop("awaiting", None)
        allowed = await charge_query(update, context, mirror_id, text)
        if not allowed:
            return
        await _do_search(update, text, user.id)


# ── Direct lookup: @username or numeric ID → full profile card ───────────────

async def _do_direct_lookup(update: Update, query: str, searcher_id: int):
    """
    Called when the user sends a bare @username or numeric ID.
    Tries users first, then chats, then returns a full profile card.
    """
    arg = query.lstrip("@")

    # ── Numeric ID ────────────────────────────────────────────────────────────
    if query.lstrip("-").isdigit():
        entity_id = int(query)
        user = tg_users.get(entity_id)
        if user:
            if _is_shadow(user["id"], searcher_id):
                await update.message.reply_text(
                    "😔 هذا المستخدم أخفى نفسه من نتائج البحث\\.",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
                return
            await _send_user(update, user, searcher_id)
            return

        chat = tg_chats.get(entity_id)
        if chat:
            from mirror.search import _send_chat_result
            await _send_chat_result(update, chat, full=True)
            return

        await update.message.reply_text(
            f"😔 لا يوجد مستخدم أو مجموعة بالـ ID `{entity_id}` في قاعدة البيانات\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # ── @username — try user first, then chat ─────────────────────────────────
    user = tg_users.get_by_username(arg)
    if user:
        if _is_shadow(user["id"], searcher_id):
            await update.message.reply_text(
                "😔 هذا المستخدم أخفى نفسه من نتائج البحث\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return
        await _send_user(update, user, searcher_id)
        return

    chat = tg_chats.get_by_username(arg)
    if chat:
        from mirror.search import _send_chat_result
        await _send_chat_result(update, chat, full=True)
        return

    await update.message.reply_text(
        f"😔 لا يوجد نتائج لـ `{escape(query)}` في قاعدة البيانات\\.\n\n"
        "_جرب البحث بالاسم عبر زر 🔍 Search_",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── Search: users + groups + channels + bots ─────────────────────────────────

async def _do_search(update: Update, query: str, searcher_id: int):
    arg = query.lstrip("@")

    exact = tg_users.get_by_username(arg)
    if exact and not _is_shadow(exact["id"], searcher_id):
        await _send_user(update, exact, searcher_id)
        return

    users = tg_users.search(query, limit=4)
    chats = tg_chats.search(query, limit=6)
    users = [u for u in users if not _is_shadow(u["id"], searcher_id)]

    if not users and not chats:
        await update.message.reply_text(
            f"😔 No results for `{escape(query)}`\n\n"
            "_Try a different spelling or use @username format_",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    lines = [f"🔍 *Results for* `{escape(query)}`\n"]

    if users:
        lines.append("*👤 Users*")
        for u in users:
            lines.append(user_line(u))

    if chats:
        groups   = [c for c in chats if c["type"] in ("group", "supergroup", "gigagroup")]
        channels = [c for c in chats if c["type"] == "channel"]
        if groups:
            lines.append("\n*👥 Groups*")
            for c in groups:
                lines.append(chat_line(c))
        if channels:
            lines.append("\n*📢 Channels*")
            for c in channels:
                lines.append(chat_line(c))

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔍 More", callback_data=f"search_more:{query}:0"),
    ]])
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_shadow(user_id: int, searcher_id: int) -> bool:
    sub = sh_hide_plans.get_active_subscription(user_id)
    if not sub:
        return False
    return bool((sub.get("plan_features") or {}).get("hide_all"))


async def _send_user(update: Update, user: dict, searcher_id: int):
    from mirror.search import _send_user_result
    await _send_user_result(update, user, full=True, searcher_id=searcher_id)


# ── Inline menu callbacks (kb_*) ──────────────────────────────────────────────

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callbacks from the 📋 Menu inline keyboard."""
    query = update.callback_query
    await query.answer()
    data  = query.data

    routes = {
        "kb_profile": "`/profile`",
        "kb_link":    "`/link`",
        "kb_tracks":  "`/tracks`",
        "kb_export":  "`/export`",
    }

    prompts = {
        "kb_near":  ("near",         "📍 Send a @username to find nearby users:"),
        "kb_phone": ("phone",        "📞 Send the phone number \\(e\\.g\\. \\+12345678900\\):"),
        "kb_track": ("track_prompt", "👁 Send @username to track:"),
    }

    if data in routes:
        await query.message.reply_text(
            f"Use the command: {routes[data]}",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if data in prompts:
        key, prompt_text = prompts[data]
        context.user_data["awaiting"] = key
        await query.message.reply_text(prompt_text, parse_mode=ParseMode.MARKDOWN_V2)
        return
