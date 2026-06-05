from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_crystals, sh_referrals
from keyboards.system.main import back_keyboard
from utils.fmt import escape


async def cmd_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user     = update.effective_user
    balance  = sh_crystals.get_balance(user.id)
    refs     = sh_referrals.count(user.id)
    log      = sh_crystals.get_log(user.id, limit=5)

    lines = [
        "*💎 Crystals*\n",
        f"Balance: `{balance}` crystals",
        f"Referrals: `{refs}` users invited",
    ]

    if log:
        lines.append("\n*Recent transactions:*")
        for entry in log:
            sign  = "\\+" if entry["amount"] > 0 else ""
            date  = entry["created_at"].strftime("%m\\-%d")
            lines.append(f"• `{sign}{entry['amount']}` — {escape(entry['reason'])} _{date}_")

    lines.append(
        f"\n🔗 Your referral link:\n"
        f"`https://t\\.me/SeekHubBot?start={user.id}`"
    )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_keyboard(),
    )
