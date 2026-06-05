"""
mirror/callbacks.py
===================
Handles all inline keyboard callback queries from mirror bots.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import tg_users, tg_chats, tg_messages
from utils.fmt import escape, user_line, chat_line


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data

    # ── mutual:<user_id> ──────────────────────────────────────────────────────
    if data.startswith("mutual:"):
        _, uid = data.split(":", 1)
        uid    = int(uid)
        viewer = update.effective_user.id
        mutuals = tg_users.get_mutual_chats(viewer, uid)
        if not mutuals:
            await query.edit_message_text(
                "No mutual groups found\\.", parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        lines = ["🤝 *Mutual Groups*\n"]
        for c in mutuals:
            lines.append(chat_line(c))
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── near:<user_id> ────────────────────────────────────────────────────────
    elif data.startswith("near:"):
        _, uid = data.split(":", 1)
        uid = int(uid)
        from mirror.near import _near_results
        text = await _near_results(uid)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2)

    # ── user_msgs:<user_id>:<offset> ──────────────────────────────────────────
    elif data.startswith("user_msgs:"):
        _, uid, offset = data.split(":")
        uid, offset = int(uid), int(offset)
        msgs = tg_messages.get_user_messages(uid, limit=5, offset=offset)
        if not msgs:
            await query.answer("No more messages.", show_alert=True)
            return
        lines = [f"💬 *Messages* \\(page {offset//5+1}\\)\n"]
        for m in msgs:
            text     = escape((m["text"] or m["caption"] or "")[:100])
            chat_ref = escape(m["chat_username"] or m["chat_title"] or str(m["chat_id"]))
            date_str = m["date"].strftime("%Y\\-%m\\-%d") if m["date"] else "?"
            lines.append(f"• {chat_ref}\n  `{text}`\n  _{date_str}_")
        kb = []
        if offset > 0:
            kb.append(InlineKeyboardButton("◀️ Prev", callback_data=f"user_msgs:{uid}:{offset-5}"))
        if len(msgs) == 5:
            kb.append(InlineKeyboardButton("Next ▶️", callback_data=f"user_msgs:{uid}:{offset+5}"))
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([kb]) if kb else None,
        )

    # ── chat_msgs:<chat_id>:<offset> ──────────────────────────────────────────
    elif data.startswith("chat_msgs:"):
        _, cid, offset = data.split(":")
        cid, offset    = int(cid), int(offset)
        from db.connection import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT m.message_id, m.text, m.caption, m.media_type,
                           m.date, m.sender_id, u.first_name
                    FROM tg_messages m
                    LEFT JOIN tg_users u ON u.id = m.sender_id
                    WHERE m.chat_id = %s
                    ORDER BY m.date DESC
                    LIMIT 5 OFFSET %s
                """, (cid, offset))
                msgs = cur.fetchall()
        if not msgs:
            await query.answer("No more messages.", show_alert=True)
            return
        lines = [f"💬 *Messages in chat* \\(page {offset//5+1}\\)\n"]
        for m in msgs:
            text     = escape((m["text"] or m["caption"] or "")[:80].replace("\n", " "))
            sender   = escape(m["first_name"] or "Unknown")
            date_str = m["date"].strftime("%Y\\-%m\\-%d") if m["date"] else "?"
            lines.append(f"• *{sender}*: `{text}`\n  _{date_str}_")
        kb = []
        if offset > 0:
            kb.append(InlineKeyboardButton("◀️ Prev", callback_data=f"chat_msgs:{cid}:{offset-5}"))
        if len(msgs) == 5:
            kb.append(InlineKeyboardButton("Next ▶️", callback_data=f"chat_msgs:{cid}:{offset+5}"))
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([kb]) if kb else None,
        )

    # ── members:<chat_id>:<offset> ────────────────────────────────────────────
    elif data.startswith("members:"):
        _, cid, offset = data.split(":")
        cid, offset    = int(cid), int(offset)
        members = tg_chats.get_members(cid, limit=10, offset=offset)
        if not members:
            await query.answer("No more members.", show_alert=True)
            return
        lines = [f"👥 *Members* \\(page {offset//10+1}\\)\n"]
        for m in members:
            lines.append(user_line(m) + (" 👑" if m.get("is_admin") else ""))
        kb = []
        if offset > 0:
            kb.append(InlineKeyboardButton("◀️ Prev", callback_data=f"members:{cid}:{offset-10}"))
        if len(members) == 10:
            kb.append(InlineKeyboardButton("Next ▶️", callback_data=f"members:{cid}:{offset+10}"))
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([kb]) if kb else None,
        )

    # ── interactions:<user_id> ────────────────────────────────────────────────
    elif data.startswith("interactions:"):
        _, uid = data.split(":", 1)
        top    = tg_users.get_top_interactions(int(uid), limit=10)
        if not top:
            await query.edit_message_text(
                "No interactions found\\.", parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        lines = ["🔗 *Top Interactions*\n"]
        for r in top:
            n = escape(r["first_name"] or "Unknown")
            u = f" @{escape(r['username'])}" if r.get("username") else ""
            lines.append(f"• {n}{u} — `{r['interactions']}` interactions")
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── captcha:<answer> ──────────────────────────────────────────────────────
    elif data.startswith("captcha:"):
        from mirror.captcha import handle_captcha_callback
        await handle_captcha_callback(update, context)

    # ── check_join ────────────────────────────────────────────────────────────
    elif data == "check_join":
        from mirror.force_join import check_force_join
        allowed = await check_force_join(update, context)
        if allowed:
            await query.answer("✅ Verified! You're all set.", show_alert=True)
        else:
            await query.answer("❌ Still not a member.", show_alert=True)

    # ── search_more:<query>:<offset> ──────────────────────────────────────────
    elif data.startswith("search_more:"):
        parts  = data.split(":", 2)
        q, offset = parts[1], int(parts[2])
        users  = tg_users.search(q, limit=5)
        chats  = tg_chats.search(q, limit=5)
        if not users and not chats:
            await query.answer("No more results.", show_alert=True)
            return
        lines = [f"🔍 *More results for* `{escape(q)}`\n"]
        for u in users: lines.append(user_line(u))
        for c in chats: lines.append(chat_line(c))
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)
