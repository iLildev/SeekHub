"""
mirror/main.py
==============
Builds an Application for a single mirror bot.
All mirrors share the same handlers — they differ only by token.
"""
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from mirror.start import cmd_start
from mirror.profile import cmd_profile
from mirror.search import cmd_search, cmd_id, cmd_user, cmd_group, cmd_msearch
from mirror.callbacks import handle_callback
from system.captcha import handle_captcha_callback
from system.force_join import handle_check_join_callback


def build_mirror_app(token: str, mirror_id: int) -> Application:
    app = Application.builder().token(token).build()

    # Inject mirror_id so handlers can track query counts per mirror
    app.bot_data["mirror_id"] = mirror_id

    # Commands
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("search",  cmd_search))
    app.add_handler(CommandHandler("id",      cmd_id))
    app.add_handler(CommandHandler("user",    cmd_user))
    app.add_handler(CommandHandler("group",   cmd_group))
    app.add_handler(CommandHandler("msearch", cmd_msearch))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_captcha_callback,    pattern=r"^captcha_"))
    app.add_handler(CallbackQueryHandler(handle_check_join_callback, pattern=r"^check_join$"))
    app.add_handler(CallbackQueryHandler(handle_callback))

    return app
