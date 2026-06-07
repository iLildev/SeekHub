from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💎 Points",  callback_data="menu_points"),
            InlineKeyboardButton("👑 Plans",   callback_data="menu_plan"),
        ],
        [
            InlineKeyboardButton("🌟 Aura",    callback_data="menu_aura"),
            InlineKeyboardButton("🛡️ Privacy", callback_data="menu_hide"),
        ],
        [
            InlineKeyboardButton("📖 Manual",  url="https://t.me/SeekHubBot"),
        ],
    ])


def back_keyboard(callback: str = "menu_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Back", callback_data=callback)]
    ])
