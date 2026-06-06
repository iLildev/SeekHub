"""
mirror/menu.py
==============
Handles all persistent keyboard button presses and the conversational
"awaiting input" state for Search/Seek and Select flows.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import tg_users, tg_chats, sh_hide_plans
from db.sh_mirrors import increment_query_count, track_mirror_user, log_query
from utils.fmt import escape, user_line, chat_line
from keyboards.mirror.main import (
    main_keyboard, select_keyboard,
    BTN_SEARCH, BTN_MENU, BTN_SELECT,
    BTN_GROUP, BTN_USER, BTN_CHANNEL, BTN_BOT, BTN_BACK,
    ALL_BUTTONS,
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


# ── Prompt texts ──────────────────────────────────────────────────────────────

_PROMPTS = {
    "search":  "🔍 *Search SeekHub*\n\nType any name, @username, or keyword\\.\nI'll search across users, groups, channels and bots\\.",
    "user":    "👤 *User Lookup*\n\nSend a @username or Telegram ID\\.",
    "group":   "👥 *Group Lookup*\n\nSend the group @username, invite link, or ID\\.",
    "channel": "📢 *Channel Lookup*\n\nSend the channel @username or ID\\.",
    "bot":     "🤖 *Bot Lookup*\n\nSend the bot @username or ID\\.",
}


# ── Main dispatcher ───────────────────────────────────────────────────────────

async def handle_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text      = update.message.text
    mirror_id = context.bot_data.get("mirror_id", 0)
    user      = update.effective_user

    # ── Navigation buttons ────────────────────────────────────────────────────
    if text == BTN_SELECT:
        context.user_data.pop("awaiting", None)
        await update.message.reply_text(
            "🎯 *Select what to look up:*",
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

    # ── Awaiting triggers ─────────────────────────────────────────────────────
    if text == BTN_SEARCH:
        context.user_data["awaiting"] = "search"
        await update.message.reply_text(
            _PROMPTS["search"],
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if text == BTN_USER:
        context.user_data["awaiting"] = "user"
        await update.message.reply_text(
            _PROMPTS["user"],
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if text == BTN_GROUP:
        context.user_data["awaiting"] = "group"
        await update.message.reply_text(
            _PROMPTS["group"],
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if text == BTN_CHANNEL:
        context.user_data["awaiting"] = "channel"
        await update.message.reply_text(
            _PROMPTS["channel"],
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if text == BTN_BOT:
        context.user_data["awaiting"] = "bot"
        await update.message.reply_text(
            _PROMPTS["bot"],
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # ── Process awaited input ─────────────────────────────────────────────────
    awaiting = context.user_data.get("awaiting")
    if awaiting:
        context.user_data.pop("awaiting", None)
        track_mirror_user(mirror_id, user.id,
                          username=user.username, first_name=user.first_name)
        increment_query_count(mirror_id)
        log_query(mirror_id, text)
        await _dispatch(update, context, awaiting, text, user.id)


# ── Search dispatcher ─────────────────────────────────────────────────────────

async def _dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE,
                    mode: str, query: str, searcher_id: int):
    query = query.strip()

    if mode == "search":
        await _do_search(update, query, searcher_id)

    elif mode in ("user", "bot"):
        await _do_user(update, context, query, searcher_id, bots_only=(mode == "bot"))

    elif mode in ("group", "channel"):
        await _do_chat(update, query, chat_type=mode)


# ── Search: users + groups + channels + bots ─────────────────────────────────

async def _do_search(update: Update, query: str, searcher_id: int):
    arg = query.lstrip("@")

    # Exact username try first
    exact = tg_users.get_by_username(arg)
    if exact and not _is_shadow(exact["id"], searcher_id):
        await _send_user(update, exact, searcher_id)
        return

    # Full-text across users + chats
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
        # Separate by type
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


# ── User / Bot lookup ─────────────────────────────────────────────────────────

async def _do_user(update: Update, context: ContextTypes.DEFAULT_TYPE,
                   query: str, searcher_id: int, bots_only: bool = False):
    arg = query.lstrip("@")
    user = None
    try:
        user = tg_users.get(int(arg))
    except ValueError:
        user = tg_users.get_by_username(arg)

    if not user:
        # Try userbot resolve
        ub = context.bot_data.get("userbot_client")
        if ub and ub.is_connected:
            try:
                from userbot.scraper import resolve_username, index_user_profile
                uid = await resolve_username(ub, arg)
                if uid:
                    await index_user_profile(ub, uid)
                    user = tg_users.get(uid)
            except Exception:
                pass

    if not user:
        await update.message.reply_text(
            f"😔 `{escape(arg)}` not found in SeekHub database\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if bots_only and not user.get("is_bot"):
        await update.message.reply_text(
            f"⚠️ `{escape(arg)}` is not a bot\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if _is_shadow(user["id"], searcher_id):
        await update.message.reply_text(
            "😔 This user is not visible in search results\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    await _send_user(update, user, searcher_id)


# ── Chat / Channel lookup ─────────────────────────────────────────────────────

async def _do_chat(update: Update, query: str, chat_type: str):
    arg = query.lstrip("@")
    chat = None
    try:
        chat = tg_chats.get(int(arg))
    except ValueError:
        chat = tg_chats.get_by_username(arg)

    if not chat:
        results = tg_chats.search(query, limit=5)
        if chat_type == "channel":
            results = [c for c in results if c["type"] == "channel"]
        else:
            results = [c for c in results if c["type"] in ("group", "supergroup", "gigagroup")]

        if not results:
            icon = "📢" if chat_type == "channel" else "👥"
            await update.message.reply_text(
                f"😔 {icon} No {chat_type} found for `{escape(query)}`\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        lines = [f"{'📢' if chat_type == 'channel' else '👥'} *Results for* `{escape(query)}`\n"]
        for c in results:
            lines.append(chat_line(c))
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)
        return

    # Verify type matches
    if chat_type == "channel" and chat["type"] != "channel":
        await update.message.reply_text(
            f"⚠️ This is a group, not a channel\\. Use 👥 *Group* instead\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return
    if chat_type == "group" and chat["type"] == "channel":
        await update.message.reply_text(
            f"⚠️ This is a channel, not a group\\. Use 📢 *Channel* instead\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    from mirror.search import _send_chat_result
    await _send_chat_result(update, chat, full=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_shadow(user_id: int, searcher_id: int) -> bool:
    sub = sh_hide_plans.get_active_subscription(user_id)
    if not sub:
        return False
    return bool((sub.get("plan_features") or {}).get("hide_all"))


async def _send_user(update: Update, user: dict, searcher_id: int):
    from mirror.search import _send_user_result
    await _send_user_result(update, user, full=True, searcher_id=searcher_id)


# ── Inline menu callbacks ─────────────────────────────────────────────────────

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callbacks from the 📋 Menu inline keyboard."""
    query = update.callback_query
    await query.answer()
    data  = query.data

    routes = {
        "kb_profile": "/profile",
        "kb_link":    "/link",
        "kb_tracks":  "/tracks",
        "kb_export":  "/export",
    }

    prompts = {
        "kb_near":  ("near", "📍 Send a @username to find nearby users:"),
        "kb_phone": ("phone", "📞 Send the phone number \\(e\\.g\\. \\+12345678900\\):"),
        "kb_track": ("track_prompt", "👁 Send @username to track:"),
    }

    if data in routes:
        await query.message.reply_text(
            f"Use the command: `{routes[data]}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if data in prompts:
        key, prompt_text = prompts[data]
        context.user_data["awaiting_cmd"] = key
        await query.message.reply_text(prompt_text, parse_mode=ParseMode.MARKDOWN_V2)
        return
