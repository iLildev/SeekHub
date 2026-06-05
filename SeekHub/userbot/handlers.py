"""
userbot/handlers.py
===================
Pyrogram event handlers — passively index every message/join/leave
the userbot account observes across all its chats.
"""
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus, ChatType

from db import tg_users, tg_chats, tg_memberships
from db.tg_messages import upsert as msg_upsert

logger = logging.getLogger(__name__)


def _tg_chat_type(t) -> str:
    mapping = {
        ChatType.GROUP:      "group",
        ChatType.SUPERGROUP: "supergroup",
        ChatType.CHANNEL:    "channel",
        ChatType.PRIVATE:    "private",
        ChatType.BOT:        "bot",
    }
    return mapping.get(t, "unknown")


def _index_pyrogram_user(user):
    if not user or user.is_bot:
        return
    try:
        tg_users.upsert(
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            is_bot=user.is_bot,
            is_premium=getattr(user, "is_premium", False),
            lang_code=getattr(user, "language_code", None),
            is_verified=getattr(user, "is_verified", False),
            is_deleted=getattr(user, "is_deleted", False),
        )
    except Exception as e:
        logger.debug("user upsert failed %s: %s", user.id, e)


def _index_pyrogram_chat(chat):
    if not chat or chat.type == ChatType.PRIVATE:
        return
    try:
        tg_chats.upsert(
            chat_id=chat.id,
            type_=_tg_chat_type(chat.type),
            title=chat.title,
            username=chat.username,
            description=getattr(chat, "description", None),
            member_count=getattr(chat, "members_count", None),
            is_verified=getattr(chat, "is_verified", False),
            is_scam=getattr(chat, "is_scam", False),
            is_fake=getattr(chat, "is_fake", False),
            is_broadcast=(chat.type == ChatType.CHANNEL),
            linked_chat_id=getattr(getattr(chat, "linked_chat", None), "id", None),
        )
    except Exception as e:
        logger.debug("chat upsert failed %s: %s", chat.id, e)


def register_handlers(app: Client):

    @app.on_message()
    async def on_msg(client: Client, msg: Message):
        try:
            _index_pyrogram_chat(msg.chat)
            if msg.from_user:
                _index_pyrogram_user(msg.from_user)
                tg_memberships.upsert(msg.from_user.id, msg.chat.id)

            # Forward origin
            fwd_id = None
            if msg.forward_from:
                _index_pyrogram_user(msg.forward_from)
                fwd_id = msg.forward_from.id

            media_type = _get_media_type(msg)
            file_id    = _get_file_id(msg)

            msg_upsert(
                message_id=msg.id,
                chat_id=msg.chat.id,
                sender_id=msg.from_user.id if msg.from_user else None,
                sender_chat_id=msg.sender_chat.id if msg.sender_chat else None,
                text=msg.text,
                caption=msg.caption,
                media_type=media_type,
                file_id=file_id,
                reply_to_msg_id=msg.reply_to_message_id,
                forward_from_id=fwd_id,
                forward_date=msg.forward_date,
                views=msg.views or 0,
                forwards=msg.forwards or 0,
                is_pinned=getattr(msg, "pinned", False),
                date=msg.date,
            )

            # Interactions
            if msg.from_user and msg.reply_to_message and msg.reply_to_message.from_user:
                tg_memberships.record_interaction(
                    msg.from_user.id,
                    msg.reply_to_message.from_user.id,
                    msg.chat.id,
                    "reply"
                )
        except Exception as e:
            logger.debug("message handler error: %s", e)

    @app.on_chat_member_updated()
    async def on_member_update(client: Client, update: ChatMemberUpdated):
        try:
            _index_pyrogram_chat(update.chat)
            if update.new_chat_member:
                u = update.new_chat_member.user
                _index_pyrogram_user(u)
                status = update.new_chat_member.status
                if status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                    is_admin = status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
                    tg_memberships.upsert(u.id, update.chat.id, status=status.value, is_admin=is_admin)
                elif status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
                    tg_memberships.mark_left(u.id, update.chat.id)
        except Exception as e:
            logger.debug("member update handler error: %s", e)


def _get_media_type(msg: Message) -> str | None:
    if msg.photo:        return "photo"
    if msg.video:        return "video"
    if msg.document:     return "document"
    if msg.audio:        return "audio"
    if msg.voice:        return "voice"
    if msg.video_note:   return "video_note"
    if msg.sticker:      return "sticker"
    if msg.animation:    return "animation"
    if msg.location:     return "location"
    if msg.contact:      return "contact"
    if msg.poll:         return "poll"
    return None


def _get_file_id(msg: Message) -> str | None:
    if msg.photo:        return msg.photo.file_id
    if msg.video:        return msg.video.file_id
    if msg.document:     return msg.document.file_id
    if msg.audio:        return msg.audio.file_id
    if msg.voice:        return msg.voice.file_id
    if msg.sticker:      return msg.sticker.file_id
    if msg.animation:    return msg.animation.file_id
    return None
