"""
system/mirror_settings.py
==========================
/mset — lets mirror owners toggle commands on/off for their mirrors.
Admin-only controls (captcha, force_join, welcome) are NOT here.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import sh_mirrors
from db.sh_mirrors import get_by_owner, get_settings, set_setting
from utils.fmt import escape

TOGGLEABLE = {
    "phone_enabled":   ("📞 /phone",   "Phone number lookup"),
    "near_enabled":    ("📍 /near",    "Nearby users search"),
    "msearch_enabled": ("💬 /msearch", "Message full-text search"),
    "analyze_enabled": ("📊 /analyze", "User activity analysis"),
    "export_enabled":  ("📤 /export",  "Data export"),
}


def _settings_text(mirror: dict, settings: dict) -> str:
    uname = escape(mirror["bot_username"] or "unknown")
    lines = [f"*⚙️ Settings — @{uname}*\n"]
    for key, (label, desc) in TOGGLEABLE.items():
        enabled = settings.get(key, True)
        status  = "✅ ON" if enabled else "❌ OFF"
        lines.append(f"{label} — {status}\n  _{escape(desc)}_")
    lines.append("\nTap a button to toggle\\.")
    return "\n".join(lines)


def _settings_keyboard(mirror_id: int, settings: dict) -> InlineKeyboardMarkup:
    buttons = []
    for key, (label, _) in TOGGLEABLE.items():
        enabled = settings.get(key, True)
        btn_label = f"{'✅' if enabled else '❌'} {label}"
        buttons.append([InlineKeyboardButton(btn_label, callback_data=f"mset:{mirror_id}:{key}")])
    return InlineKeyboardMarkup(buttons)


async def cmd_mset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    mirrors = get_by_owner(user.id)

    if not mirrors:
        await update.message.reply_text(
            "❌ You have no mirrors yet\\. Use /token to register one\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if len(mirrors) == 1:
        m        = mirrors[0]
        settings = get_settings(m["id"])
        await update.message.reply_text(
            _settings_text(m, settings),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=_settings_keyboard(m["id"], settings),
        )
        return

    # Multiple mirrors — let them pick
    if context.args:
        arg = context.args[0].lstrip("@").lower()
        m = next((x for x in mirrors if (x["bot_username"] or "").lower() == arg), None)
        if not m:
            await update.message.reply_text(
                "❌ Mirror not found\\. Use /mirror to see your mirrors\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return
        settings = get_settings(m["id"])
        await update.message.reply_text(
            _settings_text(m, settings),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=_settings_keyboard(m["id"], settings),
        )
        return

    lines = ["*⚙️ Select a mirror to configure:*\n"]
    for m in mirrors:
        lines.append(f"• @{escape(m['bot_username'] or 'unknown')} — `/mset {escape(m['bot_username'] or '')}`")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)


async def handle_mset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts     = query.data.split(":", 2)
    mirror_id = int(parts[1])
    key       = parts[2]
    user_id   = query.from_user.id

    mirrors = get_by_owner(user_id)
    m = next((x for x in mirrors if x["id"] == mirror_id), None)
    if not m:
        await query.answer("❌ Not your mirror.", show_alert=True)
        return

    if key not in TOGGLEABLE:
        await query.answer("❌ Unknown setting.", show_alert=True)
        return

    settings = get_settings(mirror_id)
    current  = settings.get(key, True)
    set_setting(mirror_id, key, not current)
    settings[key] = not current

    await query.edit_message_text(
        _settings_text(m, settings),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=_settings_keyboard(mirror_id, settings),
    )
