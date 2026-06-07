from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_aura, sh_users
from db.connection import get_conn
from keyboards.system.main import back_keyboard
from utils.fmt import escape


def _vote_keyboard(target_id: int, current_vote: int | None) -> InlineKeyboardMarkup:
    pos_label = "🌟 \\+1" if current_vote != 1  else "✅ \\+1 \\(active\\)"
    neg_label = "💀 \\-1" if current_vote != -1 else "✅ \\-1 \\(active\\)"
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(pos_label.replace("\\", ""), callback_data=f"aura_vote:1:{target_id}"),
        InlineKeyboardButton(neg_label.replace("\\", ""), callback_data=f"aura_vote:-1:{target_id}"),
    ]])


async def cmd_aura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user      = update.effective_user
    score     = sh_aura.get_score(user.id)
    breakdown = sh_aura.get_breakdown(user.id)
    top       = sh_aura.get_top(5)

    sign   = "\\+" if score > 0 else ""
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    lines = [
        f"*🌟 Aura*\n",
        f"Your score: *{sign}{score}*",
        f"🌟 Positive: `{breakdown['positive']}` \\| 💀 Negative: `{breakdown['negative']}`\n",
        "*Top 5:*",
    ]
    for i, row in enumerate(top):
        s    = int(row["score"])
        sign = "\\+" if s > 0 else ""
        name = escape(row["first_name"] or "Unknown")
        lines.append(f"{medals[i]} {name} — *{sign}{s}*")

    lines.append("\n_Use /addaura @username to vote on someone_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_keyboard(),
    )


async def cmd_addaura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "Usage: `/addaura @username`\n\nThen choose 🌟 \\+1 or 💀 \\-1",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    target_username = context.args[0].lstrip("@")

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
        await update.message.reply_text(
            "❌ You cannot vote on yourself\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    score        = sh_aura.get_score(target["id"])
    current_vote = sh_aura.get_vote(user.id, target["id"])
    breakdown    = sh_aura.get_breakdown(target["id"])

    sign = "\\+" if score > 0 else ""
    name = escape(target["first_name"])

    vote_line = ""
    if current_vote == 1:
        vote_line = "\n_Your vote: 🌟 \\+1_"
    elif current_vote == -1:
        vote_line = "\n_Your vote: 💀 \\-1_"

    text = (
        f"*{name}*\n"
        f"Score: *{sign}{score}* "
        f"\\(🌟 {breakdown['positive']} \\| 💀 {breakdown['negative']}\\)"
        f"{vote_line}\n\n"
        f"Cast your vote:"
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=_vote_keyboard(target["id"], current_vote),
    )


async def handle_aura_vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts     = query.data.split(":")   # aura_vote : +1/-1 : target_id
    value     = int(parts[1])
    target_id = int(parts[2])
    voter_id  = query.from_user.id

    if target_id == voter_id:
        await query.answer("❌ You cannot vote on yourself.", show_alert=True)
        return

    current_vote = sh_aura.get_vote(voter_id, target_id)

    if current_vote == value:
        # Toggle off — remove the vote
        sh_aura.remove(voter_id, target_id)
        new_vote = None
        notice   = "Vote removed\\."
    else:
        sh_aura.give(voter_id, target_id, value)
        new_vote = value
        label    = "🌟 \\+1" if value == 1 else "💀 \\-1"
        notice   = f"Vote set to {label}\\."

    score     = sh_aura.get_score(target_id)
    breakdown = sh_aura.get_breakdown(target_id)
    sign      = "\\+" if score > 0 else ""

    # Fetch target name for the updated message
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT first_name FROM sh_users WHERE id = %s", (target_id,))
            row = cur.fetchone()
    name = escape((row or {}).get("first_name") or "User")

    vote_line = ""
    if new_vote == 1:
        vote_line = "\n_Your vote: 🌟 \\+1_"
    elif new_vote == -1:
        vote_line = "\n_Your vote: 💀 \\-1_"

    text = (
        f"*{name}*\n"
        f"Score: *{sign}{score}* "
        f"\\(🌟 {breakdown['positive']} \\| 💀 {breakdown['negative']}\\)"
        f"{vote_line}\n\n"
        f"_{notice}_"
    )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=_vote_keyboard(target_id, new_vote),
    )
