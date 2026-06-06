"""
mirror/main.py
==============
Builds the Application for a single mirror bot.
All mirrors share the same handlers — differ only by token + mirror_id + settings.
"""
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    InlineQueryHandler, MessageHandler, filters,
)

from mirror.start      import cmd_start
from mirror.profile    import cmd_profile
from mirror.search     import cmd_search, cmd_id, cmd_user, cmd_group, cmd_msearch
from mirror.near       import cmd_near
from mirror.track      import cmd_track, cmd_untrack, cmd_tracks
from mirror.analyze    import cmd_analyze, cmd_heatmap, cmd_export
from mirror.phone      import cmd_phone
from mirror.link       import cmd_link
from mirror.callbacks  import handle_callback
from mirror.inline     import handle_inline_query
from mirror.menu       import (
    handle_keyboard, handle_menu_callback,
    handle_users_shared, handle_chat_shared,
)

from keyboards.mirror.main import ALL_BUTTONS


def _guarded(handler_func, setting_key: str):
    """Wrap a command so it can be disabled per-mirror via settings."""
    async def wrapper(update, context):
        settings = context.bot_data.get("settings") or {}
        if not settings.get(setting_key, True):
            await update.message.reply_text(
                "🚫 This command is disabled on this mirror\\.",
                parse_mode="MarkdownV2",
            )
            return
        return await handler_func(update, context)
    return wrapper


def build_mirror_app(token: str, mirror_id: int, settings: dict | None = None) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["mirror_id"] = mirror_id
    app.bot_data["settings"]  = settings or {}

    # ── Core commands ─────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("search",  cmd_search))
    app.add_handler(CommandHandler("id",      cmd_id))
    app.add_handler(CommandHandler("user",    cmd_user))
    app.add_handler(CommandHandler("group",   cmd_group))
    app.add_handler(CommandHandler("msearch", _guarded(cmd_msearch, "msearch_enabled")))
    app.add_handler(CommandHandler("near",    _guarded(cmd_near,    "near_enabled")))
    app.add_handler(CommandHandler("phone",   _guarded(cmd_phone,   "phone_enabled")))

    # ── Profile & referrals ───────────────────────────────────────────────────
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("link",    cmd_link))

    # ── Tracking ──────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("track",   cmd_track))
    app.add_handler(CommandHandler("untrack", cmd_untrack))
    app.add_handler(CommandHandler("tracks",  cmd_tracks))

    # ── Analysis & export ─────────────────────────────────────────────────────
    app.add_handler(CommandHandler("analyze", _guarded(cmd_analyze, "analyze_enabled")))
    app.add_handler(CommandHandler("heatmap", _guarded(cmd_heatmap, "analyze_enabled")))
    app.add_handler(CommandHandler("export",  _guarded(cmd_export,  "export_enabled")))

    # ── Native picker results (highest priority) ──────────────────────────────
    app.add_handler(MessageHandler(
        filters.StatusUpdate.USERS_SHARED,
        handle_users_shared,
    ))
    app.add_handler(MessageHandler(
        filters.StatusUpdate.CHAT_SHARED,
        handle_chat_shared,
    ))

    # ── Persistent keyboard text buttons ──────────────────────────────────────
    if ALL_BUTTONS:
        escaped = [b.replace("\\", "\\\\").replace("/", r"\/") for b in ALL_BUTTONS]
        pattern = "^(" + "|".join(escaped) + ")$"
        app.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(pattern),
            handle_keyboard,
        ))

    # ── Free-text (awaiting state) ────────────────────────────────────────────
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_keyboard,
    ))

    # ── Inline query ──────────────────────────────────────────────────────────
    app.add_handler(InlineQueryHandler(handle_inline_query))

    # ── Callbacks ─────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_menu_callback, pattern=r"^kb_"))
    app.add_handler(CallbackQueryHandler(handle_callback))

    return app
