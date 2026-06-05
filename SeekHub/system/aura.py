from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import aura as aura_db
from db import users as users_db
from keyboards.system.main import back_keyboard


async def cmd_aura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    total = aura_db.get_aura(user.id)
    top = aura_db.get_top_aura(5)

    lines = []
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, row in enumerate(top):
        name = row["first_name"] or "Unknown"
        lines.append(f"{medals[i]} {name} — `{row['total']}`")

    leaderboard = "\n".join(lines) if lines else "_No aura yet_"

    text = (
        f"*🌟 Aura*\n\n"
        f"Your aura: `{total}`\n\n"
        f"*Top 5 Aura:*\n"
        f"{leaderboard}\n\n"
        f"Use /addaura @username amount to give aura to someone\."
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_keyboard(),
    )


async def cmd_addaura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /addaura @username amount\n\nExample: /addaura @john 10",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    target_username = context.args[0].lstrip("@")
    try:
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Amount must be a positive number\.")
        return

    with __import__("db.connection", fromlist=["get_conn"]).get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, first_name FROM seekhub_users WHERE username = %s",
                (target_username,)
            )
            target = cur.fetchone()

    if not target:
        await update.message.reply_text(
            f"❌ User @{target_username} not found in SeekHub\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if target["id"] == user.id:
        await update.message.reply_text("❌ You cannot give aura to yourself\.")
        return

    aura_db.add_aura(user.id, target["id"], amount)

    await update.message.reply_text(
        f"✅ You gave `{amount}` aura to {target['first_name']}\!",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
