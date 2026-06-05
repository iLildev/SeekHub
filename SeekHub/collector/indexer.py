"""
collector/indexer.py
====================
Core indexing logic — called by both the collector bot (when it receives messages
in groups) and by any future userbot scraper.  Keeps the DB in sync with what
we observe on Telegram in real-time.
"""
import logging
from telegram import Message, Chat, User, Update

from db import tg_users, tg_chats, tg_messages, tg_memberships

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _index_user(user: User):
    try:
        tg_users.upsert(
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            is_bot=user.is_bot,
            is_premium=getattr(user, "is_premium", False),
            lang_code=user.language_code if hasattr(user, "language_code") else None,
        )
    except Exception as e:
        logger.warning("Failed to index user %s: %s", user.id, e)


def _index_chat(chat: Chat):
    try:
        tg_chats.upsert(
            chat_id=chat.id,
            type_=chat.type,
            title=chat.title,
            username=chat.username,
            is_broadcast=(chat.type == "channel"),
        )
    except Exception as e:
        logger.warning("Failed to index chat %s: %s", chat.id, e)


def _index_membership(user_id: int, chat_id: int, status: str = "member", is_admin: bool = False):
    try:
        tg_memberships.upsert(user_id=user_id, chat_id=chat_id, status=status, is_admin=is_admin)
    except Exception as e:
        logger.warning("Failed to index membership %s/%s: %s", user_id, chat_id, e)


# ── Main entry point: called for every incoming message ──────────────────────

def index_message(message: Message):
    """
    Index everything observable from a single Telegram message:
    - sender user
    - chat
    - membership (sender is in chat)
    - the message itself
    - reply / forward interactions
    - mentioned users
    """
    if not message or not message.chat:
        return

    chat = message.chat
    _index_chat(chat)

    sender = message.from_user
    if sender and not sender.is_bot:
        _index_user(sender)
        _index_membership(sender.id, chat.id)

    # Forward origin
    forward_from_id = None
    if message.forward_from:
        _index_user(message.forward_from)
        forward_from_id = message.forward_from.id

    # Index the message
    text = message.text or message.caption or None
    media_type = _get_media_type(message)

    try:
        tg_messages.upsert(
            message_id=message.message_id,
            chat_id=chat.id,
            sender_id=sender.id if sender else None,
            sender_chat_id=message.sender_chat.id if message.sender_chat else None,
            text=text,
            caption=message.caption,
            media_type=media_type,
            file_id=_get_file_id(message),
            reply_to_msg_id=message.reply_to_message.message_id if message.reply_to_message else None,
            forward_from_id=forward_from_id,
            forward_date=message.forward_date,
            views=getattr(message, "views", 0) or 0,
            forwards=getattr(message, "forwards", 0) or 0,
            is_pinned=False,
            date=message.date,
        )
    except Exception as e:
        logger.warning("Failed to index message %s/%s: %s", chat.id, message.message_id, e)

    # Reply interaction
    if sender and message.reply_to_message and message.reply_to_message.from_user:
        replied_to = message.reply_to_message.from_user
        _index_user(replied_to)
        try:
            tg_memberships.record_interaction(sender.id, replied_to.id, chat.id, "reply")
        except Exception:
            pass

    # Mention interactions
    if text and sender:
        _index_mentions(text, message.message_id, chat.id, sender.id, message.date)


def _index_mentions(text: str, message_id: int, chat_id: int, by_user_id: int, date):
    import re
    from db.connection import get_conn
    usernames = re.findall(r"@([A-Za-z0-9_]{4,})", text)
    if not usernames:
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            for uname in usernames:
                cur.execute(
                    "SELECT id FROM tg_users WHERE lower(username) = lower(%s)",
                    (uname,)
                )
                row = cur.fetchone()
                mentioned_id = row["id"] if row else None
                cur.execute("""
                    INSERT INTO tg_mentions
                        (mentioned_user_id, mentioned_username, in_chat_id, message_id, by_user_id, mentioned_at)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (mentioned_id, uname, chat_id, message_id, by_user_id, date))

                if mentioned_id:
                    try:
                        tg_memberships.record_interaction(by_user_id, mentioned_id, chat_id, "mention")
                    except Exception:
                        pass
        conn.commit()


def _get_media_type(message: Message) -> str | None:
    if message.photo:        return "photo"
    if message.video:        return "video"
    if message.document:     return "document"
    if message.audio:        return "audio"
    if message.voice:        return "voice"
    if message.video_note:   return "video_note"
    if message.sticker:      return "sticker"
    if message.animation:    return "animation"
    if message.location:     return "location"
    if message.contact:      return "contact"
    if message.poll:         return "poll"
    return None


def _get_file_id(message: Message) -> str | None:
    if message.photo:        return message.photo[-1].file_id
    if message.video:        return message.video.file_id
    if message.document:     return message.document.file_id
    if message.audio:        return message.audio.file_id
    if message.voice:        return message.voice.file_id
    if message.sticker:      return message.sticker.file_id
    if message.animation:    return message.animation.file_id
    return None


# ── Member join/leave events ─────────────────────────────────────────────────

def index_member_join(user: User, chat: Chat):
    _index_user(user)
    _index_chat(chat)
    _index_membership(user.id, chat.id, status="member")


def index_member_left(user: User, chat: Chat):
    _index_user(user)
    try:
        tg_memberships.mark_left(user.id, chat.id)
    except Exception as e:
        logger.warning("Failed to mark left %s/%s: %s", user.id, chat.id, e)


# ── Chat member snapshot (bulk index when bot joins a group) ─────────────────

async def index_chat_members(bot, chat_id: int):
    """
    Called once when our collector bot joins a new group.
    Fetches admins (and where possible members) to seed the DB.
    """
    try:
        admins = await bot.get_chat_administrators(chat_id)
        rows = []
        for member in admins:
            u = member.user
            _index_user(u)
            rows.append({
                "user_id": u.id,
                "chat_id": chat_id,
                "status": member.status,
                "is_admin": True,
                "title": getattr(member, "custom_title", None),
            })
        tg_memberships.bulk_upsert(rows)
        logger.info("Indexed %d admins for chat %s", len(rows), chat_id)
    except Exception as e:
        logger.warning("Could not index members for chat %s: %s", chat_id, e)
