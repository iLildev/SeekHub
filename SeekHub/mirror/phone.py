"""
mirror/phone.py
===============
/phone — search a Telegram user by phone number.

Method:
  1. Try MTProto userbot (Pyrogram) to resolve the phone directly.
     Works when the userbot has the number in contacts OR mutual groups.
  2. Fall back to our indexed tg_phone_index table (populated during collection).
  3. Show the full profile if found.

Privacy note: we only surface users who are already publicly indexed.
"""
import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import tg_users, sh_users
from db.connection import get_conn
from utils.fmt import escape

logger = logging.getLogger(__name__)

# E.164-ish: optional + then 7–15 digits
_PHONE_RE = re.compile(r"^\+?[\d\s\-().]{7,16}$")


def _normalise(phone: str) -> str:
    """Strip everything except digits and leading +."""
    digits = re.sub(r"[^\d]", "", phone)
    return "+" + digits if phone.strip().startswith("+") else digits


def _lookup_db(phone_norm: str) -> dict | None:
    """Check our local phone index table."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.* FROM tg_phone_index pi
                JOIN tg_users u ON u.id = pi.user_id
                WHERE pi.phone = %s
                LIMIT 1
            """, (phone_norm,))
            return cur.fetchone()


def store_phone(user_id: int, phone: str):
    """Save a phone→user mapping whenever the collector sees one."""
    norm = _normalise(phone)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tg_phone_index (phone, user_id)
                VALUES (%s, %s)
                ON CONFLICT (phone) DO UPDATE SET user_id = EXCLUDED.user_id
            """, (norm, user_id))
        conn.commit()


async def cmd_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /phone +1234567890
    Search for a Telegram user by their phone number.
    """
    if not context.args:
        await update.message.reply_text(
            "📱 *Phone Number Search*\n\n"
            "Usage: `/phone \\+1234567890`\n\n"
            "_Include the country code for best results\\._",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    raw = " ".join(context.args).strip()

    if not _PHONE_RE.match(raw):
        await update.message.reply_text(
            "❌ Invalid phone number format\\.\n"
            "Example: `/phone \\+79001234567`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    phone_norm = _normalise(raw)
    mirror_id  = context.bot_data.get("mirror_id", 0)

    # Auto-register the querying user
    querier = update.effective_user
    sh_users.upsert(querier.id, querier.username or "", querier.first_name or "")

    await update.message.reply_text(
        f"🔍 Searching for `{escape(phone_norm)}`\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    user_data = None

    # ── Step 1: DB index ──────────────────────────────────────────────────────
    user_data = _lookup_db(phone_norm)

    # ── Step 2: MTProto userbot ───────────────────────────────────────────────
    if not user_data:
        userbot = context.bot_data.get("userbot_client")
        if userbot and userbot.is_connected:
            user_data = await _resolve_via_userbot(userbot, phone_norm)

    # ── Result ────────────────────────────────────────────────────────────────
    if not user_data:
        await update.message.reply_text(
            f"😔 No Telegram account found for `{escape(phone_norm)}`\\.\n\n"
            "_This number is not indexed in SeekHub yet\\.\n"
            "It may be private or not in any monitored group\\._",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    await _send_phone_result(update, user_data, phone_norm)


async def _resolve_via_userbot(client, phone_norm: str) -> dict | None:
    """
    Try to resolve a phone number via Pyrogram MTProto.
    Returns a tg_users-compatible dict if found, None otherwise.
    """
    try:
        from pyrogram.errors import BadRequest, FloodWait
        from userbot.scraper import index_user_profile

        tg_user = await client.get_users(phone_norm)
        if not tg_user:
            return None

        uid = tg_user.id
        await index_user_profile(client, uid)

        # Also store the phone mapping for future lookups
        store_phone(uid, phone_norm)

        return tg_users.get(uid)

    except Exception as e:
        logger.debug("Userbot phone lookup failed for %s: %s", phone_norm, e)
        return None


async def _send_phone_result(update: Update, user: dict, phone_norm: str):
    uid   = user["id"]
    name  = escape(" ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or "Unknown")
    uname = f"@{escape(user['username'])}" if user.get("username") else "_no username_"

    lines = [
        f"📱 *Phone Lookup Result*\n",
        f"📞 Phone: `{escape(phone_norm)}`\n",
        f"👤 *{name}*",
        f"ID: `{uid}`",
        f"Username: {uname}",
    ]

    if user.get("is_premium"):   lines.append("💎 Premium")
    if user.get("is_verified"):  lines.append("✅ Verified")
    if user.get("is_deleted"):   lines.append("🗑 Deleted account")
    if user.get("is_bot"):       lines.append("🤖 Bot")

    # Username history
    history = tg_users.get_username_history(uid)
    if len(history) > 1:
        old = [f"`@{escape(h['username'])}`" for h in history[1:4]]
        lines.append(f"\n🔄 *Previous usernames:* {', '.join(old)}")

    # Activity
    stats = tg_users.get_message_stats(uid)
    if stats and stats.get("total_messages"):
        lines.append(
            f"\n📊 Messages: `{stats['total_messages']}` \\| "
            f"Chats: `{stats['chat_count']}`"
        )

    # Groups
    groups = tg_users.get_chats(uid, limit=6)
    if groups:
        glist = [
            f"`{escape(g['username'] and '@'+g['username'] or g.get('title') or str(g['id']))}`"
            for g in groups
        ]
        lines.append(f"\n💬 *Seen in:* {', '.join(glist)}")

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = [[
        InlineKeyboardButton("📍 Near Users",    callback_data=f"near:{uid}"),
        InlineKeyboardButton("🔗 Interactions",  callback_data=f"interactions:{uid}"),
    ]]

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(buttons),
    )
