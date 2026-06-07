"""
main.py — SeekHub entry point
==============================
Starts concurrently:
  1. System bot  (@SeekHubBot)    — management only
  2. Collector bot (optional)     — passive Bot API indexer
  3. Mirror bots                  — one PTB app per active mirror in DB
  4. Userbot / MTProto (optional) — active indexer, scraper, online tracker
"""
import asyncio
import logging
import os
import sys

from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, PreCheckoutQueryHandler, filters,
)

from db import init_db

from system.start          import cmd_start, WELCOME_TEXT
from system.points         import cmd_points
from system.aura           import cmd_aura, cmd_addaura
from system.plan           import cmd_plan, handle_plan_buy_callback
from system.admins         import cmd_stats, cmd_ban, cmd_unban
from system.token_handler  import cmd_token
from system.mirrors        import cmd_mirror, cmd_mystats
from system.mirror_settings import cmd_mset, handle_mset_callback
from system.captcha        import handle_captcha_callback
from system.force_join     import handle_check_join_callback
from system.hide           import (
    cmd_hide, handle_hide_buy_callback,
    handle_pre_checkout, handle_successful_payment,
)
from system.submit         import cmd_submit

from runner import MirrorRunner

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

    elif data == "menu_points":
        from db.sh_crystals import get_balance
        from db.sh_referrals import count as ref_count
        bal  = get_balance(uid)
        refs = ref_count(uid)
        text = (
            f"*💎 Crystals*\n\nBalance: `{bal}`\nReferrals: `{refs}`\n\n"
            f"Referral link:\n`https://t\\.me/SeekHubBot?start={uid}`\n\n"
            f"*Earn crystals:*\n"
            f"• Share your referral link — *\\+10 crystals* per new user\n"
            f"• New users get *\\+4 crystals* on join"
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
                f"  `{p['daily_queries']}` queries/day \\| `{p['max_tracking']}` tracks"
            )
        await query.edit_message_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=back_keyboard())

    elif data == "menu_hide":
        from db import sh_hide_plans
        active = sh_hide_plans.get_active_subscription(uid)
        plans  = sh_hide_plans.get_all()
        lines  = ["*🛡️ Privacy Plans*\n",
                  "Hide yourself from SeekHub search results\\. Paid monthly via Telegram Stars\\.\n"]
        badges = {"ghost": "👻", "shadow": "🌑", "spy": "🕵️"}
        for p in plans:
            feat  = p["features"] or {}
            badge = feat.get("badge", "•")
            price = feat.get("price_display", f"⭐{p['price_stars']}")
            lines.append(f"{badge} *{escape(p['name'])}* — {escape(price)}")
        if active:
            exp   = active["expires_at"].strftime("%Y\\-%m\\-%d")
            pname = escape(active.get("plan_name", ""))
            lines.append(f"\n✅ Active: *{pname}* \\(expires {exp}\\)")
        lines.append("\nUse /hide to purchase a plan\\.")
        await query.edit_message_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=back_keyboard())



# ── System bot builder ────────────────────────────────────────────────────────

def build_system_app(token: str) -> Application:
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("mirror",   cmd_mirror))
    app.add_handler(CommandHandler("mystats",  cmd_mystats))
    app.add_handler(CommandHandler("mset",     cmd_mset))
    app.add_handler(CommandHandler("token",    cmd_token))
    app.add_handler(CommandHandler("points",   cmd_points))
    app.add_handler(CommandHandler("aura",     cmd_aura))
    app.add_handler(CommandHandler("addaura",  cmd_addaura))
    app.add_handler(CommandHandler("plan",     cmd_plan))
    app.add_handler(CommandHandler("stats",    cmd_stats))
    app.add_handler(CommandHandler("ban",      cmd_ban))
    app.add_handler(CommandHandler("unban",    cmd_unban))
    app.add_handler(CommandHandler("hide",     cmd_hide))
    app.add_handler(CommandHandler("submit",   cmd_submit))

    app.add_handler(CallbackQueryHandler(handle_captcha_callback,    pattern=r"^captcha_"))
    app.add_handler(CallbackQueryHandler(handle_check_join_callback, pattern=r"^check_join$"))
    app.add_handler(CallbackQueryHandler(handle_menu_callback,       pattern=r"^menu_"))
    app.add_handler(CallbackQueryHandler(handle_hide_buy_callback,   pattern=r"^hide_buy:"))
    app.add_handler(CallbackQueryHandler(handle_plan_buy_callback,   pattern=r"^plan_buy:"))
    app.add_handler(CallbackQueryHandler(handle_mset_callback,       pattern=r"^mset:"))

    app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))

    return app


# ── Userbot (MTProto) ─────────────────────────────────────────────────────────
# ⚠️  الـ Userbot معطّل افتراضياً لأنه يعمل على حساب Telegram شخصي وقد يعرّضه للحظر.
#     لتفعيله لاحقاً: أضف ENABLE_USERBOT=true في Secrets ثم أعدّ تشغيل البوت.
#     كذلك تحتاج: USERBOT_API_ID, USERBOT_API_HASH, USERBOT_SESSION (من gen_session.py)

async def start_userbot(system_app: Application) -> object | None:
    if os.environ.get("ENABLE_USERBOT", "").lower() != "true":
        logger.info("Userbot disabled — set ENABLE_USERBOT=true in Secrets to enable MTProto collection.")
        return None

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

    system_app.bot_data["userbot_client"] = client
    return client


# ── Scheduled tasks ───────────────────────────────────────────────────────────

def register_scheduled_tasks(system_app: Application):
    jq = system_app.job_queue
    if not jq:
        return

    from tasks.online_tracker  import run_online_tracker, run_name_tracker
    from tasks.deliver_events  import deliver_analytics_events

    jq.run_repeating(run_online_tracker,        interval=300,  first=60,  name="online_tracker")
    jq.run_repeating(run_name_tracker,          interval=3600, first=120, name="name_tracker")
    jq.run_repeating(deliver_analytics_events,  interval=30,   first=15,  name="deliver_events")

    logger.info("Scheduled tasks registered: online_tracker(5m), name_tracker(1h), deliver_events(30s)")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN is not set")
        sys.exit(1)

    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready")

    system_app = build_system_app(bot_token)
    register_scheduled_tasks(system_app)

    await system_app.initialize()
    await system_app.start()
    await system_app.updater.start_polling(
        allowed_updates=["message", "callback_query", "pre_checkout_query"],
    )
    logger.info("System bot started")

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

    userbot_client = await start_userbot(system_app)

    # ── Mirror bots ───────────────────────────────────────────────────────────
    mirror_runner = MirrorRunner()
    from db import sh_mirrors
    active_mirrors = sh_mirrors.get_all_active()
    if active_mirrors:
        await mirror_runner.start_all(active_mirrors, userbot_client=userbot_client)
        logger.info("Started %d mirror bot(s)", len(active_mirrors))
    else:
        logger.info("No active mirrors in DB — mirror runner idle")

    system_app.bot_data["mirror_runner"] = mirror_runner

    logger.info(
        "SeekHub fully operational — system bot ✅ | collector %s | mirrors %s | userbot %s",
        "✅" if collector_app else "⚠️ (set COLLECTOR_BOT_TOKEN)",
        f"✅ ({len(active_mirrors)})" if active_mirrors else "💤 (none registered)",
        "✅" if userbot_client else "⚠️ (run gen_session.py)",
    )

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        await mirror_runner.stop_all()
        if userbot_client:
            await userbot_client.stop()
        if collector_app:
            await collector_app.updater.stop()
            await collector_app.stop()
            await collector_app.shutdown()
        await system_app.updater.stop()
        await system_app.stop()
        await system_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
