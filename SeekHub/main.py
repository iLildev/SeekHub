import os
import sys
import logging

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from db import init_db
from system.start import cmd_start
from system.mirrors import cmd_mirror
from system.points import cmd_points
from system.aura import cmd_aura, cmd_addaura
from system.plan import cmd_plan
from system.admins import cmd_stats, cmd_ban, cmd_unban
from system.token_handler import cmd_token
from system.captcha import handle_captcha_callback
from system.force_join import handle_check_join_callback
from keyboards.system.main import main_keyboard

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def handle_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu_main":
        from services.statistics import get_stats, format_count
        from system.start import WELCOME_TEXT
        stats = get_stats()
        text = WELCOME_TEXT.format(
            users=format_count(stats["users"]),
            mirrors=format_count(stats["mirrors"]),
            groups=format_count(stats["groups"]),
        )
        await query.edit_message_text(
            text,
            parse_mode="MarkdownV2",
            reply_markup=main_keyboard(),
        )

    elif data == "menu_mirror":
        from db import mirrors as mirrors_db
        from keyboards.system.main import back_keyboard
        mirror = mirrors_db.get_mirror_by_owner(query.from_user.id)
        if mirror:
            text = (
                f"*Your Mirror*\n\n"
                f"🤖 Bot: @{mirror['bot_username'] or 'unknown'}\n"
                f"✅ Status: Active\n\n"
                f"Use /token to change your mirror bot token\\."
            )
        else:
            text = (
                "*No Mirror Found*\n\n"
                "You don't have a mirror bot yet\\.\n\n"
                "Use /token \\<your\\_token\\> to create one\\."
            )
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=back_keyboard())

    elif data == "menu_points":
        from db import points as points_db, referrals as referrals_db
        from keyboards.system.main import back_keyboard
        uid = query.from_user.id
        crystals = points_db.get_crystals(uid)
        refs = referrals_db.count_referrals(uid)
        text = (
            f"*💎 Your Crystals*\n\n"
            f"Balance: `{crystals}` crystals\n"
            f"Referrals: `{refs}` users invited\n\n"
            f"Your referral link:\n"
            f"`https://t\\.me/SeekHubBot?start={uid}`"
        )
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=back_keyboard())

    elif data == "menu_aura":
        from db import aura as aura_db
        from keyboards.system.main import back_keyboard
        uid = query.from_user.id
        total = aura_db.get_aura(uid)
        top = aura_db.get_top_aura(5)
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        lines = [f"{medals[i]} {r['first_name']} — `{r['total']}`" for i, r in enumerate(top)]
        leaderboard = "\n".join(lines) if lines else "_No aura yet_"
        text = (
            f"*🌟 Aura*\n\n"
            f"Your aura: `{total}`\n\n"
            f"*Top 5:*\n{leaderboard}"
        )
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=back_keyboard())

    elif data == "menu_plan":
        from system.plan import PLANS
        from keyboards.system.main import back_keyboard
        lines = ["*👑 Subscription Plans*\n"]
        for p in PLANS:
            price = "Free" if p["crystals"] == 0 else f"`{p['crystals']}` crystals"
            lines.append(f"{p['badge']} *{p['name']}* — {price}")
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="MarkdownV2",
            reply_markup=back_keyboard(),
        )


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN environment variable not set")
        sys.exit(1)

    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("mirror", cmd_mirror))
    app.add_handler(CommandHandler("token", cmd_token))
    app.add_handler(CommandHandler("points", cmd_points))
    app.add_handler(CommandHandler("aura", cmd_aura))
    app.add_handler(CommandHandler("addaura", cmd_addaura))
    app.add_handler(CommandHandler("plan", cmd_plan))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))

    app.add_handler(CallbackQueryHandler(handle_captcha_callback, pattern=r"^captcha_"))
    app.add_handler(CallbackQueryHandler(handle_check_join_callback, pattern=r"^check_join$"))
    app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern=r"^menu_"))

    logger.info("SeekHub bot starting...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
