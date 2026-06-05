"""
mirror/force_join.py
====================
Mirror-level force join gate.
Each mirror owner can configure a required channel/group that users must join
before using the mirror's search features.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# In a production system this would be stored per-mirror in the DB.
# For now it reads from bot_data["force_join_chat"] set by the mirror owner.


async def check_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Returns True if the user is allowed to proceed.
    Returns False and sends the gate message if they need to join first.
    """
    required_chat = context.bot_data.get("force_join_chat")
    if not required_chat:
        return True

    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(required_chat, user_id)
        if member.status in ("member", "administrator", "creator"):
            return True
    except Exception as e:
        logger.warning("Force-join check failed for %s: %s", required_chat, e)
        return True

    # User is not a member — send gate message
    try:
        chat = await context.bot.get_chat(required_chat)
        invite = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else None
    except Exception:
        invite = None

    kb = []
    if invite:
        kb.append([InlineKeyboardButton("✅ Join Channel", url=invite)])
    kb.append([InlineKeyboardButton("🔄 I Joined — Check Again", callback_data="check_join")])

    await update.message.reply_text(
        "🔒 *Access Required*\n\n"
        "You must join our channel to use this bot\\.\n"
        "After joining, press the button below\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return False
