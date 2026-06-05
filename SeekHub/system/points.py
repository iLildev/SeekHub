from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import points as points_db
from db import referrals as referrals_db
from keyboards.system.main import back_keyboard


async def cmd_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    crystals = points_db.get_crystals(user.id)
    refs = referrals_db.count_referrals(user.id)

    text = (
        f"*💎 Your Crystals*\n\n"
        f"Balance: `{crystals}` crystals\n"
        f"Referrals: `{refs}` users invited\n\n"
        f"*Earn more crystals:*\n"
        f"• Invite friends via your referral link\n"
        f"• Each referral earns you `50` crystals\n\n"
        f"Your referral link:\n"
        f"`https://t\.me/SeekHubBot?start={user.id}`"
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_keyboard(),
    )
