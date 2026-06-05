"""
mirror/main.py
==============
Builds the Application for a single mirror bot.
All mirrors share the same handlers — differ only by token + mirror_id.
"""
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from mirror.start     import cmd_start
from mirror.profile   import cmd_profile
from mirror.search    import cmd_search, cmd_id, cmd_user, cmd_group, cmd_msearch
from mirror.near      import cmd_near
from mirror.track     import cmd_track, cmd_untrack, cmd_tracks
from mirror.analyze   import cmd_analyze, cmd_heatmap, cmd_export
from mirror.callbacks import handle_callback
from system.captcha   import handle_captcha_callback
from system.force_join import handle_check_join_callback


def build_mirror_app(token: str, mirror_id: int) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["mirror_id"] = mirror_id

    # ── Search & lookup ──────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("search",  cmd_search))
    app.add_handler(CommandHandler("id",      cmd_id))
    app.add_handler(CommandHandler("user",    cmd_user))
    app.add_handler(CommandHandler("group",   cmd_group))
    app.add_handler(CommandHandler("msearch", cmd_msearch))
    app.add_handler(CommandHandler("near",    cmd_near))

    # ── Profile & tracking ───────────────────────────────────────────────────
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("track",   cmd_track))
    app.add_handler(CommandHandler("untrack", cmd_untrack))
    app.add_handler(CommandHandler("tracks",  cmd_tracks))

    # ── Analysis & export ────────────────────────────────────────────────────
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("heatmap", cmd_heatmap))
    app.add_handler(CommandHandler("export",  cmd_export))

    # ── Callbacks ────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_captcha_callback,    pattern=r"^captcha_"))
    app.add_handler(CallbackQueryHandler(handle_check_join_callback, pattern=r"^check_join$"))
    app.add_handler(CallbackQueryHandler(handle_callback))

    return app
