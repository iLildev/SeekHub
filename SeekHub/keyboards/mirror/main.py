"""
keyboards/mirror/main.py
========================
Persistent reply keyboards for mirror bots.
"""
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton

# ── Button labels (single source of truth) ───────────────────────────────────

BTN_SEARCH  = "🔍 Search / Seek"
BTN_MENU    = "📋 Menu"
BTN_SELECT  = "🎯 Select"
BTN_GROUP   = "👥 Group"
BTN_USER    = "👤 User"
BTN_CHANNEL = "📢 Channel"
BTN_BOT     = "🤖 Bot"
BTN_BACK    = "« Back"

ALL_BUTTONS = {BTN_SEARCH, BTN_MENU, BTN_SELECT,
               BTN_GROUP, BTN_USER, BTN_CHANNEL, BTN_BOT, BTN_BACK}


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
    Sub-keyboard shown after pressing Select:
    [👥 Group]    [👤 User]
    [📢 Channel]  [🤖 Bot]
    [« Back]
    """
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_GROUP),   KeyboardButton(BTN_USER)],
            [KeyboardButton(BTN_CHANNEL), KeyboardButton(BTN_BOT)],
            [KeyboardButton(BTN_BACK)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
