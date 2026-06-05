from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from keyboards.system.main import back_keyboard


PLANS = [
    {"name": "Starter", "crystals": 0, "mirrors": 1, "groups": 5, "badge": "🔹"},
    {"name": "Pro", "crystals": 500, "mirrors": 3, "groups": 20, "badge": "🔷"},
    {"name": "Elite", "crystals": 1500, "mirrors": 10, "groups": 100, "badge": "💠"},
]


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["*👑 Subscription Plans*\n"]

    for p in PLANS:
        price = "Free" if p["crystals"] == 0 else f"`{p['crystals']}` crystals"
        lines.append(
            f"{p['badge']} *{p['name']}*\n"
            f"  • Price: {price}\n"
            f"  • Mirrors: up to `{p['mirrors']}`\n"
            f"  • Groups/Channels: up to `{p['groups']}`\n"
        )

    lines.append("Use /points to check your crystal balance\.")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_keyboard(),
    )
