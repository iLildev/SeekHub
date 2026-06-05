"""
mirror/near.py
==============
/near command — finds users who appear in the most of the same groups
as a given user. Similar to FunStat's /near feature.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db.connection import get_conn
from db import tg_users
from utils.fmt import escape


async def _near_results(uid: int) -> str:
    """Shared logic — returns formatted text for /near and callback."""
    from db.connection import get_conn
    from db import tg_users

    user = tg_users.get(uid)
    if not user:
        return f"😔 User `{uid}` not found\\."

    name = escape(f"{user.get('first_name') or ''} {user.get('last_name') or ''}".strip() or str(uid))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    m2.user_id,
                    u.first_name, u.last_name, u.username,
                    u.is_premium, u.is_verified,
                    COUNT(DISTINCT m2.chat_id) AS shared_groups
                FROM tg_memberships m1
                JOIN tg_memberships m2
                    ON m1.chat_id = m2.chat_id
                    AND m2.user_id != %s
                    AND m2.status NOT IN ('left', 'kicked')
                JOIN tg_users u ON u.id = m2.user_id
                WHERE m1.user_id = %s
                  AND m1.status NOT IN ('left', 'kicked')
                  AND u.is_bot = FALSE
                GROUP BY m2.user_id, u.first_name, u.last_name, u.username,
                         u.is_premium, u.is_verified
                ORDER BY shared_groups DESC
                LIMIT 15
            """, (uid, uid))
            results = cur.fetchall()

    if not results:
        return (
            f"😔 No nearby users found for *{name}*\\.\n\n"
            "_Not enough indexed group memberships yet\\._"
        )

    lines = [f"📍 *Users near* {name}\n"]
    for r in results:
        uname  = f" @{escape(r['username'])}" if r.get("username") else ""
        fname  = escape(r["first_name"] or "Unknown")
        badges = ""
        if r.get("is_premium"):  badges += " 💎"
        if r.get("is_verified"): badges += " ✅"
        shared = r["shared_groups"]
        lines.append(
            f"• [{fname}](tg://user?id={r['user_id']}){uname}{badges}\n"
            f"  `{shared}` shared group{'s' if shared != 1 else ''}"
        )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS cnt FROM tg_memberships
                WHERE user_id = %s AND status NOT IN ('left', 'kicked')
            """, (uid,))
            total_groups = cur.fetchone()["cnt"]

    lines.append(
        f"\n_Based on {total_groups} indexed group{'s' if total_groups != 1 else ''}_"
    )
    return "\n".join(lines)


async def cmd_near(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /near @username or /near <id>
    Find users who share the most groups with a given user.
    """
    if not context.args:
        await update.message.reply_text(
            "*📍 Near Users*\n\n"
            "Find users who share the most groups with someone\\.\n\n"
            "Usage:\n"
            "`/near @username`\n"
            "`/near 123456789`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    arg = context.args[0]

    # Resolve to user
    user = None
    try:
        user = tg_users.get(int(arg))
    except ValueError:
        user = tg_users.get_by_username(arg)

    if not user:
        # Try resolving via userbot if available
        userbot = context.bot_data.get("userbot_client")
        if userbot and userbot.is_connected:
            try:
                from userbot.scraper import resolve_username, index_user_profile
                resolved_id = await resolve_username(userbot, arg)
                if resolved_id:
                    await index_user_profile(userbot, resolved_id)
                    user = tg_users.get(resolved_id)
            except Exception:
                pass

    if not user:
        await update.message.reply_text(
            f"😔 User `{escape(arg)}` not found in the SeekHub database\\.\n\n"
            "_They may not have been indexed yet\\._",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    text = await _near_results(user["id"])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)
