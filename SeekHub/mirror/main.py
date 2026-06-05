from telegram.ext import Application, CommandHandler, MessageHandler, filters

from mirror.start import cmd_start
from mirror.profile import cmd_profile
from mirror.link import cmd_link
from mirror.search import cmd_search
from mirror.captcha import handle_captcha_callback
from mirror.force_join import handle_check_join_callback


def build_mirror_app(token: str) -> Application:
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("link", cmd_link))
    app.add_handler(CommandHandler("search", cmd_search))

    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(handle_captcha_callback, pattern=r"^captcha_"))
    app.add_handler(CallbackQueryHandler(handle_check_join_callback, pattern=r"^check_join$"))

    return app
