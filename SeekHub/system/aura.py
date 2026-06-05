from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_aura, sh_users
from db.connection import get_conn
from keyboards.system.main import back_keyboard
from utils.fmt import escape


async def cmd_aura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    score = sh_aura.get_score(user.id)
    top   = sh_aura.get_top(5)

    medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
    lines  = [f"*🌟 Aura*\n\nYour score: `{score}`\n\n*Top 5:*"]
    for i, row in enumerate(top):
        name = escape(row["first_name"] or "Unknown")
        lines.append(f"{medals[i]} {name} — `{row['score']}`")

    lines.append("\nUse /addaura @username amount to give aura\\.")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_keyboard(),
    )


async def cmd_addaura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /addaura @username amount\nExample: /addaura @john 10",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    target_username = context.args[0].lstrip("@")
    try:
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Amount must be a positive number\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, first_name FROM sh_users WHERE username = %s",
                (target_username,)
            )
            target = cur.fetchone()

    if not target:
        await update.message.reply_text(
            f"❌ User @{escape(target_username)} not found\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if target["id"] == user.id:
        await update.message.reply_text("❌ You cannot give aura to yourself\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    sh_aura.give(user.id, target["id"], amount)

    await update.message.reply_text(
        f"✅ You gave `{amount}` aura to {escape(target['first_name'])}\\!",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
