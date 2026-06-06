"""
mirror/inline.py
================
Inline query handler for mirror bots.
Allows @bot <query> from any Telegram chat — the killer UX feature.
"""
import uuid
import logging
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes

from db import tg_users, tg_chats, sh_hide_plans
from db.sh_mirrors import increment_query_count, track_mirror_user, log_query
from utils.fmt import escape

logger = logging.getLogger(__name__)

_HINT = InlineQueryResultArticle(
    id="hint",
    title="🔍 Search SeekHub",
    description="Type a name or @username to search the database",
    input_message_content=InputTextMessageContent(
        "🔍 *SeekHub Inline Search*\n\nType `@thisbot <query>` in any chat to search\\.",
        parse_mode="MarkdownV2",
    ),
)


async def handle_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    iq        = update.inline_query
    text      = iq.query.strip()
    mirror_id = context.bot_data.get("mirror_id", 0)
    searcher  = iq.from_user.id

    if len(text) < 2:
        await iq.answer([_HINT], cache_time=10, is_personal=False)
        return

    track_mirror_user(mirror_id, searcher,
                      username=iq.from_user.username,
                      first_name=iq.from_user.first_name)
    increment_query_count(mirror_id)
    log_query(mirror_id, text)

    results = []

    # ── Exact username match first ────────────────────────────────────────────
    lookup = text.lstrip("@")
    user = tg_users.get_by_username(lookup)
    if user:
        hide = _hide_level(user["id"], searcher)
        if hide != "shadow":
            results.append(_user_article(user, hide))

    # ── Full-text search ──────────────────────────────────────────────────────
    if not results:
        users = tg_users.search(text, limit=5)
        chats = tg_chats.search(text, limit=4)

        for u in users:
            hide = _hide_level(u["id"], searcher)
            if hide != "shadow":
                results.append(_user_article(u, hide))

        for c in chats:
            results.append(_chat_article(c))

    if not results:
        results = [InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title=f"😔 No results for \"{text}\"",
            description="Try a different name or username",
            input_message_content=InputTextMessageContent(
                f"😔 No results found for: *{escape(text)}*",
                parse_mode="MarkdownV2",
            ),
        )]

    await iq.answer(results, cache_time=30, is_personal=True)


# ── Privacy helpers ────────────────────────────────────────────────────────────

def _hide_level(user_id: int, searcher_id: int) -> str | None:
    sub = sh_hide_plans.get_active_subscription(user_id)
    if not sub:
        return None
    feat = sub.get("plan_features") or {}
    if feat.get("hide_all"):
        return "shadow"
    if feat.get("hide_username"):
        return "ghost"
    return None


# ── Result builders ────────────────────────────────────────────────────────────

def _user_article(user: dict, hide_level: str | None) -> InlineQueryResultArticle:
    uid   = user["id"]
    name  = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or "Unknown"
    badges = ("💎" if user.get("is_premium") else "") + ("✅" if user.get("is_verified") else "")

    if hide_level == "ghost":
        uname_display = "🔒 _hidden_"
        uname_plain   = "hidden"
    elif user.get("username"):
        uname_display = f"@{escape(user['username'])}"
        uname_plain   = f"@{user['username']}"
    else:
        uname_display = "_no username_"
        uname_plain   = "no username"

    text = (
        f"👤 *{escape(name)}*{(' ' + escape(badges)) if badges else ''}\n"
        f"ID: `{uid}`\n"
        f"Username: {uname_display}"
    )

    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title=f"👤 {name} {badges}".strip(),
        description=f"ID: {uid}  •  {uname_plain}",
        input_message_content=InputTextMessageContent(text, parse_mode="MarkdownV2"),
    )


def _chat_article(chat: dict) -> InlineQueryResultArticle:
    cid     = chat["id"]
    title   = chat.get("title") or "Untitled"
    icon    = "📢" if chat.get("type") == "channel" else "💬"
    uname_p = f"@{chat['username']}" if chat.get("username") else "no username"
    uname_d = f"@{escape(chat['username'])}" if chat.get("username") else "_no username_"
    members = f"\nMembers: `{chat['member_count']:,}`" if chat.get("member_count") else ""

    text = (
        f"{icon} *{escape(title)}*\n"
        f"ID: `{cid}`\n"
        f"Username: {uname_d}{members}"
    )

    return InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title=f"{icon} {title}",
        description=f"{uname_p}" + (f"  •  {chat['member_count']:,} members" if chat.get("member_count") else ""),
        input_message_content=InputTextMessageContent(text, parse_mode="MarkdownV2"),
    )
