"""
keyboards/mirror/main.py
========================
Persistent reply keyboards for mirror bots.
Uses native Telegram request buttons (KeyboardButtonRequestUsers /
KeyboardButtonRequestChat) so the user gets the built-in picker UI.
"""
from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestUsers,
    KeyboardButtonRequestChat,
)

# ── Request IDs (must be unique per button, 1-2^31) ──────────────────────────
REQ_USER    = 1
REQ_BOT     = 2
REQ_GROUP   = 3
REQ_CHANNEL = 4

# ── Button labels ─────────────────────────────────────────────────────────────
BTN_SEARCH  = "🔍 Search / Seek"
BTN_MENU    = "📋 Menu"
BTN_SELECT  = "🎯 Select"
BTN_BACK    = "« Back"

# Text-only labels (not actual button text for native pickers)
ALL_BUTTONS = {BTN_SEARCH, BTN_MENU, BTN_SELECT, BTN_BACK}


def main_keyboard() -> ReplyKeyboardMarkup:
    """
    Main persistent keyboard:
    [🔍 Search / Seek]
    [📋 Menu]  [🎯 Select]
    """
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_SEARCH)],
            [KeyboardButton(BTN_MENU), KeyboardButton(BTN_SELECT)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def select_keyboard() -> ReplyKeyboardMarkup:
    """
    Sub-keyboard with native Telegram pickers:
    [👤 User]     [🤖 Bot]
    [👥 Group]    [📢 Channel]
    [« Back]
    """
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    "👤 User",
                    request_users=KeyboardButtonRequestUsers(
                        request_id=REQ_USER,
                        user_is_bot=False,
                        max_quantity=1,
                    ),
                ),
                KeyboardButton(
                    "🤖 Bot",
                    request_users=KeyboardButtonRequestUsers(
                        request_id=REQ_BOT,
                        user_is_bot=True,
                        max_quantity=1,
                    ),
                ),
            ],
            [
                KeyboardButton(
                    "👥 Group",
                    request_chat=KeyboardButtonRequestChat(
                        request_id=REQ_GROUP,
                        chat_is_channel=False,
                    ),
                ),
                KeyboardButton(
                    "📢 Channel",
                    request_chat=KeyboardButtonRequestChat(
                        request_id=REQ_CHANNEL,
                        chat_is_channel=True,
                    ),
                ),
            ],
            [KeyboardButton(BTN_BACK)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
