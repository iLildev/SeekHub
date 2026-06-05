import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

REQUIRED_CHANNELS = [
    ch.strip()
    for ch in os.environ.get("REQUIRED_CHANNELS", "").split(",")
    if ch.strip()
]


async def check_membership(bot, user_id: int) -> list[str]:
    not_joined = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked", "banned"):
                not_joined.append(channel)
        except Exception:
            not_joined.append(channel)
    return not_joined


async def force_join_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not REQUIRED_CHANNELS:
        return True

    user = update.effective_user
    not_joined = await check_membership(context.bot, user.id)

    if not not_joined:
        return True

    buttons = [
        [InlineKeyboardButton(f"Join {ch}", url=f"https://t.me/{ch.lstrip('@')}")]
        for ch in not_joined
    ]
    buttons.append([InlineKeyboardButton("✅ I Joined", callback_data="check_join")])

    await update.message.reply_text(
        "⚠️ *Join Required*\n\nPlease join the required channels to use SeekHub:",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return False


async def handle_check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    not_joined = await check_membership(context.bot, user.id)

    if not not_joined:
        await query.edit_message_text("✅ Access granted! Send /start to begin.")
    else:
        await query.answer("❌ You haven't joined all channels yet.", show_alert=True)
