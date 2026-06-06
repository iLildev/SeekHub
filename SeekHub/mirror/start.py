from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_users, tg_users
from utils.fmt import escape
from keyboards.mirror.main import main_keyboard


MIRROR_WELCOME = (
    "🔍 *SeekHub — Telegram Intelligence*\n\n"
    "أكبر قاعدة بيانات لفهرسة Telegram\\.\n"
    "ابحث عن أي مستخدم، مجموعة، قناة أو بوت\\.\n\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "🔍 *Search / Seek* — ابحث في قاعدة البيانات\n"
    "🎯 *Select* — اختر نوع ما تبحث عنه\n"
    "📋 *Menu* — بقية المميزات\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "💡 يمكنك أيضاً كتابة `@هذا_البوت query` في أي محادثة للبحث الفوري\\."
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    tg_users.upsert(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
    )
    sh_users.upsert(user.id, user.username or "", user.first_name or "")

    if context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0][4:])
            from mirror.link import handle_referral
            await handle_referral(referrer_id, user.id)
        except (ValueError, IndexError):
            pass

    await update.message.reply_text(
        MIRROR_WELCOME,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=main_keyboard(),
    )
