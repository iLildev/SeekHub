"""
mirror/captcha.py
=================
Simple math captcha for mirror bots to prevent bot abuse.
New users must solve a captcha before accessing search features.
"""
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

CAPTCHA_KEY = "captcha_verified"


def _generate_captcha() -> tuple[str, int]:
    """Returns (question_text, correct_answer)."""
    a = random.randint(1, 12)
    b = random.randint(1, 12)
    ops = [
        (f"{a} \\+ {b}", a + b),
        (f"{a} × {b}", a * b),
        (f"{max(a,b)} \\- {min(a,b)}", max(a,b) - min(a,b)),
    ]
    q, ans = random.choice(ops)
    return q, ans


async def send_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and send a captcha challenge."""
    question, answer = _generate_captcha()
    context.user_data["captcha_answer"] = answer

    # Generate 4 choices: correct + 3 decoys
    choices = {answer}
    while len(choices) < 4:
        choices.add(random.randint(1, 144))
    choices = list(choices)
    random.shuffle(choices)

    kb = [
        [InlineKeyboardButton(str(c), callback_data=f"captcha:{c}") for c in choices[:2]],
        [InlineKeyboardButton(str(c), callback_data=f"captcha:{c}") for c in choices[2:]],
    ]

    await update.message.reply_text(
        f"🔐 *Human Verification*\n\n"
        f"Solve: *{question}* \\= ?",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def handle_captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handle captcha button press.
    Returns True if solved correctly, False otherwise.
    """
    query  = update.callback_query
    chosen = int(query.data.split(":")[1])
    correct = context.user_data.get("captcha_answer")

    if chosen == correct:
        context.user_data[CAPTCHA_KEY] = True
        await query.edit_message_text(
            "✅ Verified\\! You can now use all search features\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return True
    else:
        question, answer = _generate_captcha()
        context.user_data["captcha_answer"] = answer
        choices = {answer}
        while len(choices) < 4:
            choices.add(random.randint(1, 144))
        choices = list(choices)
        random.shuffle(choices)
        kb = [
            [InlineKeyboardButton(str(c), callback_data=f"captcha:{c}") for c in choices[:2]],
            [InlineKeyboardButton(str(c), callback_data=f"captcha:{c}") for c in choices[2:]],
        ]
        await query.edit_message_text(
            f"❌ Wrong\\! Try again:\n\n*{question}* \\= ?",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return False


def is_verified(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return context.user_data.get(CAPTCHA_KEY, False)
