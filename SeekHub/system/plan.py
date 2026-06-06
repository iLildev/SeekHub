"""
system/plan.py
==============
Subscription plans — view + purchase with Crystals.
"""
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db.connection import get_conn
from db import sh_crystals, sh_users
from keyboards.system.main import back_keyboard
from utils.fmt import escape

logger = logging.getLogger(__name__)

PLAN_BADGES = {1: "⚪", 2: "🔹", 3: "🔷", 4: "💠"}


def _plans() -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sh_plans ORDER BY id")
            return cur.fetchall()


def _activate_plan(user_id: int, plan_id: int, duration_days: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if duration_days == 0:
                cur.execute(
                    "UPDATE sh_users SET plan_id = %s, plan_expires_at = NULL WHERE id = %s",
                    (plan_id, user_id),
                )
            else:
                expires = datetime.now(timezone.utc) + timedelta(days=duration_days)
                cur.execute(
                    "UPDATE sh_users SET plan_id = %s, plan_expires_at = %s WHERE id = %s",
                    (plan_id, expires, user_id),
                )
        conn.commit()


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    plans   = _plans()
    sh_user = sh_users.get(user.id)

    if not sh_user:
        sh_users.upsert(user.id, user.username or "", user.first_name or "")
        sh_user = sh_users.get(user.id)

    current_plan_id = (sh_user or {}).get("plan_id", 1)
    balance         = sh_crystals.get_balance(user.id)

    lines = [
        "*👑 Subscription Plans*\n",
        f"💎 Your balance: `{balance}` crystals",
        f"📌 Current plan: *{escape(sh_user['plan_name'] or 'Free')}*\n",
    ]

    for p in plans:
        badge    = (p["features"] or {}).get("badge", "•")
        is_free  = p["price_crystals"] == 0
        price    = "Free" if is_free else f"`{p['price_crystals']}` crystals / 30 days"
        active   = " ✅ *\\(active\\)*" if p["id"] == current_plan_id else ""
        lines.append(
            f"{badge} *{escape(p['name'])}*{active} — {price}\n"
            f"  • Queries/day: `{p['daily_queries']}`\n"
            f"  • Mirrors: `{p['max_mirrors']}`\n"
            f"  • Tracking slots: `{p['max_tracking']}`\n"
            f"  • Export: {'✅' if p['can_export'] else '❌'} \\| "
            f"Online tracking: {'✅' if p['can_track_online'] else '❌'}\n"
        )

    lines.append("Tap a button below to upgrade your plan\\.")

    # Build buy keyboard — only show paid plans the user can afford
    buttons = []
    row = []
    for p in plans:
        if p["price_crystals"] == 0 or p["id"] == current_plan_id:
            continue
        affordable = balance >= p["price_crystals"]
        label = f"{(p['features'] or {}).get('badge','•')} {p['name']} — 💎{p['price_crystals']}"
        if not affordable:
            label = "🔒 " + label
        row.append(InlineKeyboardButton(label, callback_data=f"plan_buy:{p['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else back_keyboard(),
    )


async def handle_plan_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    plan_id = int(query.data.split(":")[1])

    plans   = _plans()
    plan    = next((p for p in plans if p["id"] == plan_id), None)
    if not plan:
        await query.answer("❌ Plan not found.", show_alert=True)
        return

    sh_user = sh_users.get(user_id)
    if not sh_user:
        sh_users.upsert(user_id, query.from_user.username or "", query.from_user.first_name or "")

    if (sh_user or {}).get("plan_id") == plan_id:
        await query.answer("You already have this plan!", show_alert=True)
        return

    cost = plan["price_crystals"]
    bal  = sh_crystals.get_balance(user_id)
    if bal < cost:
        await query.answer(
            f"❌ Not enough crystals.\nYou have {bal} / need {cost}.\n"
            "Earn more via referrals or /submit.",
            show_alert=True,
        )
        return

    ok = sh_crystals.deduct(user_id, cost, f"plan_upgrade:{plan['name'].lower()}")
    if not ok:
        await query.answer("❌ Deduction failed. Try again.", show_alert=True)
        return

    _activate_plan(user_id, plan_id, plan["duration_days"])

    badge = (plan["features"] or {}).get("badge", "•")
    await query.edit_message_text(
        f"✅ *{badge} {escape(plan['name'])} Plan activated\\!*\n\n"
        f"💎 `{cost}` crystals deducted\\.\n"
        f"Plan duration: `{plan['duration_days']}` days\\.\n\n"
        f"Your new limits:\n"
        f"• Queries/day: `{plan['daily_queries']}`\n"
        f"• Mirrors: `{plan['max_mirrors']}`\n"
        f"• Tracking: `{plan['max_tracking']}`\n"
        f"• Export: {'✅' if plan['can_export'] else '❌'} \\| "
        f"Online tracking: {'✅' if plan['can_track_online'] else '❌'}",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info("User %d upgraded to plan %s (%d crystals)", user_id, plan["name"], cost)
