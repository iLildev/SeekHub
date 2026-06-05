import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

PENDING_CAPTCHA: dict[int, int] = {}


def _gen_captcha() -> tuple[str, int]:
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    answer = a + b
    question = f"What is {a} + {b}?"
    return question, answer


async def send_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    question, answer = _gen_captcha()
    PENDING_CAPTCHA[user.id] = answer

    options = list({answer, random.randint(1, 18), random.randint(1, 18), random.randint(1, 18)})
    random.shuffle(options)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(str(opt), callback_data=f"captcha_{user.id}_{opt}") for opt in options]
    ])

    await update.message.reply_text(
        f"🔒 *Captcha Verification*\n\n{question}",
        parse_mode="MarkdownV2",
        reply_markup=keyboard,
    )


async def handle_captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, user_id_str, answer_str = query.data.split("_", 2)
    user_id = int(user_id_str)
    given = int(answer_str)

    if query.from_user.id != user_id:
        await query.answer("This captcha is not for you.", show_alert=True)
        return

    expected = PENDING_CAPTCHA.get(user_id)
    if expected is None:
        await query.edit_message_text("⏰ Captcha expired. Please try again.")
        return

    if given == expected:
        del PENDING_CAPTCHA[user_id]
        await query.edit_message_text("✅ Verified! Welcome to SeekHub.")
    else:
        await query.edit_message_text("❌ Wrong answer. Please start again with /start.")
