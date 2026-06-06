"""
collector/analytics.py
=======================
Channel Analytics — when the collector bot is added to a channel by a
SeekHub user, we record the owner and queue real-time notifications:
  - Member joined / left
  - Channel connected confirmation

Notifications are queued in sh_analytics_events and delivered by the
system bot's deliver_analytics_events job (every 30 seconds).
"""
import logging
from telegram import Chat, User

from db import sh_channel_analytics, tg_chats

logger = logging.getLogger(__name__)


def on_collector_joined_channel(chat: Chat, added_by: User | None):
    if not added_by:
        return

    tg_chats.upsert(
        chat_id=chat.id,
        type_=chat.type,
        title=chat.title,
        username=chat.username,
        member_count=getattr(chat, "member_count", None),
        is_broadcast=(chat.type == "channel"),
    )

    sh_channel_analytics.register_channel(chat.id, added_by.id)

    sh_channel_analytics.queue_event(
        recipient_user_id=added_by.id,
        event_type="channel_connected",
        payload={
            "channel_id":       chat.id,
            "channel_title":    chat.title or "",
            "channel_username": chat.username or "",
        },
    )
    logger.info(
        "Channel analytics registered: channel=%s (%d) owner=%d",
        chat.title, chat.id, added_by.id,
    )


def on_collector_left_channel(chat_id: int):
    sh_channel_analytics.deactivate_channel(chat_id)
    logger.info("Channel analytics deactivated for channel %d", chat_id)


def on_member_joined_channel(channel_id: int, user: User, channel_title: str = ""):
    owner_id = sh_channel_analytics.get_owner(channel_id)
    if not owner_id:
        return
    sh_channel_analytics.queue_event(
        recipient_user_id=owner_id,
        event_type="member_join",
        payload={
            "channel_id":    channel_id,
            "channel_title": channel_title,
            "user_id":       user.id,
            "first_name":    user.first_name or "",
            "username":      user.username or "",
        },
    )


def on_member_left_channel(channel_id: int, user: User, channel_title: str = ""):
    owner_id = sh_channel_analytics.get_owner(channel_id)
    if not owner_id:
        return
    sh_channel_analytics.queue_event(
        recipient_user_id=owner_id,
        event_type="member_leave",
        payload={
            "channel_id":    channel_id,
            "channel_title": channel_title,
            "user_id":       user.id,
            "first_name":    user.first_name or "",
            "username":      user.username or "",
        },
    )
