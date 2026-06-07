"""
mirror/track.py
===============
/track — subscribe to changes on a user (online, name, bio, photo).
/untrack — remove a tracking entry.
/tracks — list your active tracking entries.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

def _upgrade_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👑 ترقية الخطة", callback_data="show_plan"),
    ]])

from db.connection import get_conn
from db import tg_users, sh_users
from utils.fmt import escape

TRACK_TYPES = {
    "online": "user_online",
    "name":   "user_name",
    "bio":    "user_bio",
    "photo":  "user_photo",
}


async def cmd_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /track @username [online|name|bio|photo]
    Default: all types.
    """
    if not context.args:
        await update.message.reply_text(
            "*🔔 Track a User*\n\n"
            "Get notified when a user changes their name, bio, photo, or comes online\\.\n\n"
            "Usage: `/track @username [online|name|bio|photo]`\n"
            "Example: `/track @durov online`\n\n"
            "_Requires Pro plan or higher\\._",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    uid = update.effective_user.id

    # Check plan
    sh_user = sh_users.get(uid)
    max_tracking = (sh_user or {}).get("max_tracking", 0)
    if max_tracking == 0:
        await update.message.reply_text(
            "❌ التتبع يتطلب خطة *Pro* أو أعلى\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=_upgrade_kb(),
        )
        return

    arg = context.args[0]
    track_type_key = context.args[1].lower() if len(context.args) > 1 else "all"

    # Resolve user
    user = None
    try:
        user = tg_users.get(int(arg))
    except ValueError:
        user = tg_users.get_by_username(arg)

    if not user:
        userbot = context.bot_data.get("userbot_client")
        if userbot and userbot.is_connected:
            try:
                from userbot.scraper import resolve_username, index_user_profile
                target_id = await resolve_username(userbot, arg)
                if target_id:
                    await index_user_profile(userbot, target_id)
                    user = tg_users.get(target_id)
            except Exception:
                pass

    if not user:
        await update.message.reply_text(
            f"❌ User `{escape(arg)}` not found\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Check current tracking count
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM tg_tracking WHERE tracker_user_id = %s AND is_active = TRUE",
                (uid,)
            )
            current = cur.fetchone()["cnt"]

    if current >= max_tracking:
        await update.message.reply_text(
            f"❌ وصلت للحد الأقصى \\(`{max_tracking}`\\)\\.\n"
            "رقّي خطتك أو أوقف تتبع مستخدم آخر أولاً\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=_upgrade_kb(),
        )
        return

    # Determine types to track
    types_to_add = (
        list(TRACK_TYPES.values())
        if track_type_key == "all"
        else [TRACK_TYPES[track_type_key]]
        if track_type_key in TRACK_TYPES
        else list(TRACK_TYPES.values())
    )

    added = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            for t in types_to_add:
                cur.execute("""
                    INSERT INTO tg_tracking (tracker_user_id, target_user_id, track_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (tracker_user_id, target_user_id, track_type) DO NOTHING
                """, (uid, user["id"], t))
                if cur.rowcount:
                    added.append(t)
        conn.commit()

    name = escape(user.get("first_name") or str(user["id"]))
    uname = f" \\(@{escape(user['username'])}\\)" if user.get("username") else ""
    types_str = ", ".join(t.replace("user_", "") for t in added)

    await update.message.reply_text(
        f"✅ Now tracking *{name}*{uname}\n"
        f"Types: `{types_str}`\n\n"
        f"You'll be notified of any changes\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def cmd_untrack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /untrack @username  — remove all tracking for a user
    """
    uid = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "Usage: `/untrack @username`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    arg = context.args[0]
    user = None
    try:
        user = tg_users.get(int(arg))
    except ValueError:
        user = tg_users.get_by_username(arg)

    if not user:
        await update.message.reply_text(f"❌ User `{escape(arg)}` not found\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE tg_tracking SET is_active = FALSE
                WHERE tracker_user_id = %s AND target_user_id = %s
            """, (uid, user["id"]))
            removed = cur.rowcount
        conn.commit()

    name = escape(user.get("first_name") or str(user["id"]))
    await update.message.reply_text(
        f"🔕 Stopped tracking *{name}* \\({removed} tracking entries removed\\)\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def cmd_tracks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /tracks — list all active tracking entries.
    """
    uid = update.effective_user.id

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.track_type, t.created_at, t.last_notified_at,
                       u.first_name, u.username, u.id AS target_id
                FROM tg_tracking t
                LEFT JOIN tg_users u ON u.id = t.target_user_id
                WHERE t.tracker_user_id = %s AND t.is_active = TRUE
                ORDER BY t.created_at DESC
            """, (uid,))
            rows = cur.fetchall()

    if not rows:
        await update.message.reply_text(
            "📭 لا يوجد تتبع نشط حالياً\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    lines = [f"🔔 *Your Tracking* \\({len(rows)} active\\)\n"]
    for r in rows:
        name   = escape(r["first_name"] or str(r["target_id"]))
        uname  = f" @{escape(r['username'])}" if r.get("username") else ""
        ttype  = r["track_type"].replace("user_", "")
        lines.append(f"• *{name}*{uname} — `{ttype}`")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)
