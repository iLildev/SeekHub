from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db.connection import get_conn
from keyboards.system.main import back_keyboard
from utils.fmt import escape


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sh_plans ORDER BY id")
            plans = cur.fetchall()

    lines = ["*👑 Subscription Plans*\n"]
    for p in plans:
        badge    = (p["features"] or {}).get("badge", "•")
        price    = "Free" if p["price_crystals"] == 0 else f"`{p['price_crystals']}` crystals/mo"
        duration = "Forever" if p["duration_days"] == 0 else f"{p['duration_days']} days"
        lines.append(
            f"{badge} *{escape(p['name'])}* — {price}\n"
            f"  • Queries/day: `{p['daily_queries']}`\n"
            f"  • Mirrors: `{p['max_mirrors']}`\n"
            f"  • Tracking slots: `{p['max_tracking']}`\n"
            f"  • Export: {'✅' if p['can_export'] else '❌'} \\| "
            f"Online tracking: {'✅' if p['can_track_online'] else '❌'}\n"
        )

    lines.append("Use /points to check your balance\\.")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=back_keyboard(),
    )
