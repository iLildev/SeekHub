"""
system/hide.py
==============
Privacy hide plans — Ghost / Shadow / Spy.
Paid via Telegram Stars through the system bot.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_hide_plans, sh_users
from utils.fmt import escape

logger = logging.getLogger(__name__)

PLAN_STARS = {
    "ghost":  250,
    "shadow": 400,
    "spy":    750,
}

PLAN_DESCRIPTIONS = {
    "ghost": (
        "👻 *Ghost* — $4\\.99/mo\n"
        "• Your username is hidden from all search results\n"
        "• Your profile still appears but username is masked\n"
        "• Ideal for basic privacy"
    ),
    "shadow": (
        "🌑 *Shadow* — $7\\.99/mo\n"
        "• Completely removed from all search results\n"
        "• No one can find you by username or name\n"
        "• Full invisibility"
    ),
    "spy": (
        "🕵️ *Spy* — $14\\.99/mo\n"
        "• Everything in Shadow, plus:\n"
        "• You get notified when someone searches for you\n"
        "• See who's looking for you"
    ),
}


async def cmd_hide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    sh_user = sh_users.get(user.id)
    if not sh_user:
        sh_users.upsert(user.id, user.username or "", user.first_name or "")

    active = sh_hide_plans.get_active_subscription(user.id)

    lines = ["🛡️ *Privacy Plans*\n"]
    lines.append(
        "Choose a plan to hide your presence from SeekHub's search results\\. "
        "All plans are paid monthly via Telegram Stars\\.\n"
    )

    for key, desc in PLAN_DESCRIPTIONS.items():
        lines.append(desc + "\n")

    if active:
        plan_name = active.get("plan_name", "Unknown")
        expires   = active["expires_at"].strftime("%Y\\-%m\\-%d")
        lines.append(f"✅ *Active plan:* {escape(plan_name)} \\(expires {expires}\\)")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👻 Ghost — ⭐250",  callback_data="hide_buy:ghost"),
            InlineKeyboardButton("🌑 Shadow — ⭐400", callback_data="hide_buy:shadow"),
        ],
        [
            InlineKeyboardButton("🕵️ Spy — ⭐750",   callback_data="hide_buy:spy"),
        ],
    ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=keyboard,
    )


async def handle_hide_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_key = query.data.split(":")[1]
    stars    = PLAN_STARS.get(plan_key)
    if not stars:
        return

    plan_labels = {"ghost": "Ghost", "shadow": "Shadow", "spy": "Spy"}
    plan_label  = plan_labels.get(plan_key, plan_key.title())

    await context.bot.send_invoice(
        chat_id=query.from_user.id,
        title=f"SeekHub {plan_label} Plan",
        description=f"30-day privacy subscription — hides your data from SeekHub search results.",
        payload=f"hide_{plan_key}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{plan_label} Plan (30 days)", amount=stars)],
    )


async def handle_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    payload = payment.invoice_payload
    charge_id = payment.telegram_payment_charge_id
    stars     = payment.total_amount

    if not payload.startswith("hide_"):
        return

    plan_key = payload.replace("hide_", "")
    plan     = sh_hide_plans.get_by_name(plan_key)
    if not plan:
        logger.error("Unknown hide plan key: %s", plan_key)
        return

    sh_users.upsert(
        update.effective_user.id,
        update.effective_user.username or "",
        update.effective_user.first_name or "",
    )

    sh_hide_plans.record_star_payment(user_id, charge_id, stars, payload, payload)
    sh_hide_plans.activate_subscription(user_id, plan["id"], charge_id)

    plan_labels = {"ghost": "👻 Ghost", "shadow": "🌑 Shadow", "spy": "🕵️ Spy"}
    label = plan_labels.get(plan_key, plan_key.title())

    await update.message.reply_text(
        f"✅ *{escape(label)} Plan activated\\!*\n\n"
        f"Your privacy is now active for 30 days\\.\n"
        f"Use /hide to check your status\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info("Hide plan '%s' activated for user %d (%d stars)", plan_key, user_id, stars)
