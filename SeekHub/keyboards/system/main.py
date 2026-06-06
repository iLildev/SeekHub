from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔮 Mirror",  callback_data="menu_mirror"),
            InlineKeyboardButton("💎 Points",  callback_data="menu_points"),
        ],
        [
            InlineKeyboardButton("🌟 Aura",    callback_data="menu_aura"),
            InlineKeyboardButton("👑 Plans",   callback_data="menu_plan"),
        ],
        [
            InlineKeyboardButton("🛡️ Privacy", callback_data="menu_hide"),
            InlineKeyboardButton("📢 Submit",  callback_data="menu_submit"),
        ],
        [
            InlineKeyboardButton("📖 Manual",  url="https://t.me/SeekHubBot"),
        ],
    ])


def back_keyboard(callback: str = "menu_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Back", callback_data=callback)]
    ])
