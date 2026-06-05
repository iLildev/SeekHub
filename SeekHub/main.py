"""
main.py — SeekHub entry point
==============================
Starts concurrently:
  1. System bot  (@SeekHubBot)    — management only
  2. All mirror bots              — search interface (auto-loaded from DB)
  3. Collector bot (optional)     — passive Bot API indexer
  4. Userbot / MTProto (optional) — active indexer, scraper, online tracker
"""
import asyncio
import logging
import os
import sys

from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from db import init_db
from db.sh_mirrors import get_all_active
from runner import MirrorRunner

from system.start        import cmd_start, WELCOME_TEXT
from system.mirrors      import cmd_mirror
from system.points       import cmd_points
from system.aura         import cmd_aura, cmd_addaura
from system.plan         import cmd_plan
from system.admins       import cmd_stats, cmd_ban, cmd_unban
from system.token_handler import cmd_token
from system.captcha      import handle_captcha_callback
from system.force_join   import handle_check_join_callback

from services.statistics import get_stats_fmt
from keyboards.system.main import main_keyboard, back_keyboard
from utils.fmt import escape

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logger = logging.getLogger("seekhub")


# ── Menu inline callbacks ─────────────────────────────────────────────────────

async def handle_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    data  = query.data
    uid   = query.from_user.id

    if data in ("menu_main", "menu_back"):
        stats = get_stats_fmt()
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
            text = "*No Mirror Found*\n\nUse /token \\<your\\_bot\\_token\\> to register\\."
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=back_keyboard())

    elif data == "menu_points":
        from db.sh_crystals import get_balance
        from db.sh_referrals import count as ref_count
        bal  = get_balance(uid)
        refs = ref_count(uid)
        text = (
            f"*💎 Crystals*\n\nBalance: `{bal}`\nReferrals: `{refs}`\n\n"
            f"Referral link:\n`https://t\\.me/SeekHubBot?start={uid}`"
        )
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=back_keyboard())

    elif data == "menu_aura":
        from db.sh_aura import get_score, get_top
        score  = get_score(uid)
        top    = get_top(5)
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
            lines.append(
                f"{badge} *{escape(p['name'])}* — {price}\n"
                f"  `{p['daily_queries']}` queries/day \\| `{p['max_mirrors']}` mirrors \\| "
                f"`{p['max_tracking']}` tracks"
            )
        await query.edit_message_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=back_keyboard())


# ── System bot builder ────────────────────────────────────────────────────────

def build_system_app(token: str, runner: MirrorRunner) -> Application:
    app = (
        Application.builder()
        .token(token)
        .build()
    )
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


# ── Userbot (MTProto) ─────────────────────────────────────────────────────────

async def start_userbot(system_app: Application) -> object | None:
    from userbot.client import build_client, is_configured
    if not is_configured():
        logger.warning(
            "Userbot not configured — MTProto collection disabled. "
            "Run SeekHub/scripts/gen_session.py and set USERBOT_API_ID, "
            "USERBOT_API_HASH, USERBOT_SESSION secrets to enable."
        )
        return None

    from userbot.handlers import register_handlers
    client = build_client()
    register_handlers(client)
    await client.start()

    me = await client.get_me()
    logger.info("Userbot connected: @%s (id=%s)", me.username, me.id)

    # Share client with system bot (for token handler, tracking, etc.)
    system_app.bot_data["userbot_client"] = client
    return client


# ── Scheduled tasks ───────────────────────────────────────────────────────────

def register_scheduled_tasks(system_app: Application):
    jq = system_app.job_queue
    if not jq:
        return

    from tasks.online_tracker import run_online_tracker, run_name_tracker

    # Online status check every 5 minutes
    jq.run_repeating(run_online_tracker, interval=300, first=60,
                     name="online_tracker")

    # Name/bio/photo change check every hour
    jq.run_repeating(run_name_tracker, interval=3600, first=120,
                     name="name_tracker")

    logger.info("Scheduled tasks registered: online_tracker (5m), name_tracker (1h)")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN is not set")
        sys.exit(1)

    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready")

    # Mirror runner — userbot will be attached after it starts
    runner = MirrorRunner()
    active_mirrors = get_all_active()
    logger.info("Found %d active mirror(s)", len(active_mirrors))

    # System bot
    system_app = build_system_app(bot_token, runner)
    register_scheduled_tasks(system_app)

    await system_app.initialize()
    await system_app.start()
    await system_app.updater.start_polling(
        allowed_updates=["message", "callback_query"],
    )
    logger.info("System bot started")

    # Collector bot (Bot API, optional)
    collector_app = None
    from collector.bot import build_collector_app
    collector_app = build_collector_app()
    if collector_app:
        await collector_app.initialize()
        await collector_app.start()
        await collector_app.updater.start_polling(
            allowed_updates=[
                "message", "edited_message",
                "channel_post", "edited_channel_post",
                "chat_member", "my_chat_member",
            ],
        )
        logger.info("Collector bot started")

    # Userbot (MTProto, optional but powerful) — start BEFORE mirrors so they get the client
    userbot_client = await start_userbot(system_app)

    # Now start mirrors — pass userbot so /near, /track, /user can use MTProto
    await runner.start_all(active_mirrors, userbot_client=userbot_client)

    # Also attach to already-running mirrors (if any were loaded before userbot started)
    if userbot_client:
        runner.attach_userbot(userbot_client)

    logger.info(
        "SeekHub fully operational — system bot ✅ | "
        "%d mirror(s) ✅ | collector %s | userbot %s",
        len(active_mirrors),
        "✅" if collector_app else "⚠️ (set COLLECTOR_BOT_TOKEN)",
        "✅" if userbot_client else "⚠️ (run gen_session.py)",
    )

    # Run forever
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        if userbot_client:
            await userbot_client.stop()
        await runner.stop_all()
        if collector_app:
            await collector_app.updater.stop()
            await collector_app.stop()
            await collector_app.shutdown()
        await system_app.updater.stop()
        await system_app.stop()
        await system_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
