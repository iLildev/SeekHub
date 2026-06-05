"""
main.py — SeekHub entry point
==============================
Starts:
  1. The system bot  (@SeekHubBot)  — management only
  2. All active mirror bots         — search interface for end-users
  3. The collector bot (optional)   — passive data indexer in groups

All three run concurrently in the same asyncio event loop.
"""
import asyncio
import logging
import os
import sys

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
)

from db import init_db
from db.sh_mirrors import get_all_active
from runner import MirrorRunner

from system.start import cmd_start
from system.mirrors import cmd_mirror
from system.points import cmd_points
from system.aura import cmd_aura, cmd_addaura
from system.plan import cmd_plan
from system.admins import cmd_stats, cmd_ban, cmd_unban
from system.token_handler import cmd_token
from system.captcha import handle_captcha_callback
from system.force_join import handle_check_join_callback

from services.statistics import get_stats_fmt
from keyboards.system.main import main_keyboard
from utils.fmt import escape

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger("seekhub")


# ── Menu callbacks for the system bot ────────────────────────────────────────

async def handle_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    data  = query.data
    uid   = query.from_user.id

    from keyboards.system.main import back_keyboard

    if data == "menu_main":
        stats = get_stats_fmt()
        from system.start import WELCOME_TEXT
        await query.edit_message_text(
            WELCOME_TEXT.format(users=stats["users"], mirrors=stats["mirrors"], chats=stats["chats"]),
            parse_mode="MarkdownV2",
            reply_markup=main_keyboard(),
        )

    elif data == "menu_mirror":
        from db.sh_mirrors import get_by_owner
        mirrors = get_by_owner(uid)
        if mirrors:
            lines = ["*🔮 Your Mirrors*\n"]
            for m in mirrors:
                lines.append(
                    f"🤖 @{escape(m['bot_username'] or 'unknown')}\n"
                    f"   Queries: `{m['query_count']}` \\| Users: `{m['user_count']}`"
                )
            text = "\n".join(lines)
        else:
            text = "*No Mirror Found*\n\nUse /token to register your mirror bot\\."
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=back_keyboard())

    elif data == "menu_points":
        from db.sh_crystals import get_balance
        from db.sh_referrals import count as ref_count
        balance = get_balance(uid)
        refs    = ref_count(uid)
        text = (
            f"*💎 Crystals*\n\nBalance: `{balance}`\nReferrals: `{refs}`\n\n"
            f"Referral link:\n`https://t\\.me/SeekHubBot?start={uid}`"
        )
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=back_keyboard())

    elif data == "menu_aura":
        from db.sh_aura import get_score, get_top
        score = get_score(uid)
        top   = get_top(5)
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
        lines  = [f"*🌟 Aura*\n\nYour score: `{score}`\n\n*Top 5:*"]
        for i, r in enumerate(top):
            lines.append(f"{medals[i]} {escape(r['first_name'] or 'Unknown')} — `{r['score']}`")
        await query.edit_message_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=back_keyboard())

    elif data == "menu_plan":
        from db.connection import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sh_plans ORDER BY id")
                plans = cur.fetchall()
        lines = ["*👑 Plans*\n"]
        for p in plans:
            badge = (p["features"] or {}).get("badge", "•")
            price = "Free" if p["price_crystals"] == 0 else f"`{p['price_crystals']}` crystals"
            lines.append(f"{badge} *{escape(p['name'])}* — {price} \\| `{p['daily_queries']}` q/day")
        await query.edit_message_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=back_keyboard())

    elif data == "menu_back":
        stats = get_stats_fmt()
        from system.start import WELCOME_TEXT
        await query.edit_message_text(
            WELCOME_TEXT.format(users=stats["users"], mirrors=stats["mirrors"], chats=stats["chats"]),
            parse_mode="MarkdownV2",
            reply_markup=main_keyboard(),
        )


# ── Build system bot ──────────────────────────────────────────────────────────

def build_system_app(token: str, runner: MirrorRunner) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["mirror_runner"] = runner

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("mirror",  cmd_mirror))
    app.add_handler(CommandHandler("token",   cmd_token))
    app.add_handler(CommandHandler("points",  cmd_points))
    app.add_handler(CommandHandler("aura",    cmd_aura))
    app.add_handler(CommandHandler("addaura", cmd_addaura))
    app.add_handler(CommandHandler("plan",    cmd_plan))
    app.add_handler(CommandHandler("stats",   cmd_stats))
    app.add_handler(CommandHandler("ban",     cmd_ban))
    app.add_handler(CommandHandler("unban",   cmd_unban))

    app.add_handler(CallbackQueryHandler(handle_captcha_callback,    pattern=r"^captcha_"))
    app.add_handler(CallbackQueryHandler(handle_check_join_callback, pattern=r"^check_join$"))
    app.add_handler(CallbackQueryHandler(handle_menu_callback,       pattern=r"^menu_"))

    return app


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN is not set")
        sys.exit(1)

    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready")

    runner = MirrorRunner()

    # Load all active mirrors from DB and start them
    active_mirrors = get_all_active()
    logger.info("Found %d active mirror(s) to start", len(active_mirrors))
    await runner.start_all(active_mirrors)

    # Build and start system bot
    system_app = build_system_app(bot_token, runner)
    await system_app.initialize()
    await system_app.start()
    await system_app.updater.start_polling(
        allowed_updates=["message", "callback_query"],
    )
    logger.info("SeekHub system bot started")

    # Start collector bot (optional)
    from collector.bot import build_collector_app
    collector_app = build_collector_app()
    if collector_app:
        await collector_app.initialize()
        await collector_app.start()
        await collector_app.updater.start_polling(
            allowed_updates=["message", "edited_message",
                             "channel_post", "edited_channel_post",
                             "chat_member", "my_chat_member"],
        )
        logger.info("SeekHub collector bot started")

    logger.info("SeekHub fully operational — system bot + %d mirror(s)", len(active_mirrors))

    # Run forever
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        await runner.stop_all()
        await system_app.updater.stop()
        await system_app.stop()
        await system_app.shutdown()
        if collector_app:
            await collector_app.updater.stop()
            await collector_app.stop()
            await collector_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
