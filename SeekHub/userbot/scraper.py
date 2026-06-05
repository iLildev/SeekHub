"""
userbot/scraper.py
==================
Active bulk scraping using MTProto — the core advantage over Bot API.

  bulk_index_chat()    — index all members + recent history of a chat
  backfill_history()   — pull full message history of a public chat
  scrape_members()     — fetch complete member list (channels.getParticipants)
  index_user_profile() — deep profile: bio, photo, online status
"""
import asyncio
import logging
from pyrogram import Client
from pyrogram.types import Chat, User
from pyrogram.enums import ChatType, ChatMembersFilter
from pyrogram.errors import (
    FloodWait, ChatAdminRequired, ChannelPrivate,
    UsernameNotOccupied, PeerIdInvalid
)

from db import tg_users, tg_chats, tg_memberships
from db.tg_messages import upsert as msg_upsert
from userbot.handlers import (
    _index_pyrogram_user, _index_pyrogram_chat,
    _get_media_type, _get_file_id
)

logger = logging.getLogger(__name__)

HISTORY_BATCH  = 100     # messages per GetHistory call
MEMBER_BATCH   = 200     # members per getParticipants call
SCRAPE_DELAY   = 0.5     # seconds between API calls (flood control)


# ── Member list scraping ──────────────────────────────────────────────────────

async def scrape_members(client: Client, chat_id: int | str) -> int:
    """
    Fetch the full member list of a public group/channel using MTProto.
    Bot API can only get admins — this gets everyone.
    Returns count of members indexed.
    """
    count = 0
    try:
        chat = await client.get_chat(chat_id)
        _index_pyrogram_chat(chat)

        async for member in client.get_chat_members(chat_id):
            u = member.user
            if u and not u.is_bot:
                _index_pyrogram_user(u)
                tg_memberships.upsert(
                    u.id, chat.id,
                    status=member.status.value,
                    is_admin=member.status.value in ("administrator", "creator"),
                    title=getattr(member, "custom_title", None),
                )
                count += 1
            await asyncio.sleep(0)   # yield to event loop

        logger.info("Scraped %d members from chat %s", count, chat_id)
    except FloodWait as e:
        logger.warning("FloodWait %ds on scrape_members(%s)", e.value, chat_id)
        await asyncio.sleep(e.value)
    except (ChatAdminRequired, ChannelPrivate, PeerIdInvalid) as e:
        logger.warning("Cannot scrape members of %s: %s", chat_id, e)
    except Exception as e:
        logger.error("scrape_members(%s) error: %s", chat_id, e)

    return count


# ── Message history backfill ──────────────────────────────────────────────────

async def backfill_history(client: Client, chat_id: int | str,
                           limit: int = 5000) -> int:
    """
    Pull historical messages from a public chat.
    Bot API cannot do this at all — MTProto only.
    """
    count = 0
    try:
        chat = await client.get_chat(chat_id)
        _index_pyrogram_chat(chat)

        async for msg in client.get_chat_history(chat_id, limit=limit):
            try:
                if msg.from_user:
                    _index_pyrogram_user(msg.from_user)
                    tg_memberships.upsert(msg.from_user.id, chat.id)

                fwd_id = None
                if msg.forward_from:
                    _index_pyrogram_user(msg.forward_from)
                    fwd_id = msg.forward_from.id

                msg_upsert(
                    message_id=msg.id,
                    chat_id=chat.id,
                    sender_id=msg.from_user.id if msg.from_user else None,
                    sender_chat_id=msg.sender_chat.id if msg.sender_chat else None,
                    text=msg.text,
                    caption=msg.caption,
                    media_type=_get_media_type(msg),
                    file_id=_get_file_id(msg),
                    reply_to_msg_id=msg.reply_to_message_id,
                    forward_from_id=fwd_id,
                    forward_date=msg.forward_date,
                    views=msg.views or 0,
                    forwards=msg.forwards or 0,
                    date=msg.date,
                )
                count += 1
            except Exception as e:
                logger.debug("backfill msg error: %s", e)

            if count % 500 == 0:
                logger.info("Backfilled %d messages from %s...", count, chat_id)
                await asyncio.sleep(SCRAPE_DELAY)

        logger.info("Backfill complete: %d messages from chat %s", count, chat_id)
    except FloodWait as e:
        logger.warning("FloodWait %ds on backfill(%s)", e.value, chat_id)
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error("backfill_history(%s) error: %s", chat_id, e)

    return count


# ── Full chat index (members + history) ──────────────────────────────────────

async def bulk_index_chat(client: Client, chat_id: int | str,
                           history_limit: int = 2000):
    """
    Full index of a chat: members first, then message history.
    Call this when the userbot joins a new public group.
    """
    logger.info("Bulk indexing chat %s ...", chat_id)
    m = await scrape_members(client, chat_id)
    await asyncio.sleep(1)
    h = await backfill_history(client, chat_id, limit=history_limit)
    logger.info("Bulk index done for %s — %d members, %d messages", chat_id, m, h)


# ── Deep user profile ─────────────────────────────────────────────────────────

async def index_user_profile(client: Client, user_id: int | str) -> dict | None:
    """
    Fetch full user profile via MTProto — includes bio, photos, online status.
    Bot API cannot get bio or photos of arbitrary users.
    """
    try:
        user = await client.get_users(user_id)
        if not user:
            return None

        # Online status
        status_str = "unknown"
        if user.status:
            from pyrogram.enums import UserStatus
            status_map = {
                UserStatus.ONLINE:     "online",
                UserStatus.RECENTLY:   "recently",
                UserStatus.LAST_WEEK:  "last_week",
                UserStatus.LAST_MONTH: "last_month",
                UserStatus.LONG_AGO:   "long_ago",
                UserStatus.OFFLINE:    "recently",
            }
            status_str = status_map.get(user.status, "unknown")

        # Profile photos
        photo_id = None
        try:
            async for photo in client.get_chat_photos(user_id, limit=1):
                photo_id = photo.file_id
                break
        except Exception:
            pass

        tg_users.upsert(
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            is_bot=user.is_bot,
            is_premium=getattr(user, "is_premium", False),
            lang_code=getattr(user, "language_code", None),
            bio=getattr(user, "bio", None),
            photo_id=photo_id,
            is_verified=getattr(user, "is_verified", False),
            is_deleted=getattr(user, "is_deleted", False),
        )

        if status_str != "unknown":
            tg_users.log_online(user.id, status_str)

        return {"user": user, "status": status_str, "photo_id": photo_id}

    except FloodWait as e:
        await asyncio.sleep(e.value)
        return None
    except Exception as e:
        logger.debug("index_user_profile(%s) error: %s", user_id, e)
        return None


# ── Resolve username to ID ────────────────────────────────────────────────────

async def resolve_username(client: Client, username: str) -> int | None:
    """
    Resolve @username → Telegram ID via MTProto.
    Works for users, groups, channels.
    """
    try:
        entity = await client.get_chat(username.lstrip("@"))
        return entity.id
    except (UsernameNotOccupied, PeerIdInvalid):
        return None
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return None
    except Exception as e:
        logger.debug("resolve_username(%s): %s", username, e)
        return None
