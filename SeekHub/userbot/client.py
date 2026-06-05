"""
userbot/client.py
=================
Pyrogram MTProto userbot client.
Far more powerful than Bot API — can:
  • Fetch full member lists of any public group (channels.getParticipants)
  • Backfill old messages from public chats (GetHistory, unlimited)
  • Snapshot online status (get_users)
  • Passively index any chat the account is in
  • No "must be added" requirement — joins public groups silently

Required secrets:
  USERBOT_API_ID    — from https://my.telegram.org/apps
  USERBOT_API_HASH  — from https://my.telegram.org/apps
  USERBOT_SESSION   — Pyrogram session string (run scripts/gen_session.py once)
"""
import os
import logging

from pyrogram import Client

logger = logging.getLogger(__name__)

API_ID      = os.environ.get("USERBOT_API_ID")
API_HASH    = os.environ.get("USERBOT_API_HASH")
SESSION_STR = os.environ.get("USERBOT_SESSION")


def is_configured() -> bool:
    return bool(API_ID and API_HASH and SESSION_STR)


def build_client() -> Client | None:
    if not is_configured():
        logger.warning(
            "Userbot not configured — set USERBOT_API_ID, USERBOT_API_HASH, "
            "USERBOT_SESSION to enable MTProto collection"
        )
        return None

    return Client(
        name="seekhub_userbot",
        api_id=int(API_ID),
        api_hash=API_HASH,
        session_string=SESSION_STR,
        in_memory=True,          # no session file on disk
        no_updates=False,        # we DO want updates for passive indexing
    )
