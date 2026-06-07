"""
mirror/callbacks.py
===================
Handles ALL inline keyboard callback queries from mirror bots.

Crystal-gated callbacks (crystal_*):
  Each costs a fixed number of crystals drawn from the tapping user's balance.
  If insufficient balance → show_alert with earn instructions.
  If enough → deduct, show_alert with new balance, send the data.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from db import tg_users, tg_chats, tg_messages, sh_crystals
from utils.fmt import escape, user_line, chat_line

# Crystal costs (keep in sync with search.py CRYSTAL_COSTS)
COSTS = {
    "names":     7,
    "groups":   15,
    "messages": 20,
    "channels": 15,
    "friends":   8,
    "reactions": 10,
}


# ── Crystal gate helper ───────────────────────────────────────────────────────

async def _crystal_gate(query, cost: int, feature: str) -> bool:
    """
    Check balance, deduct crystals.
    Returns True if deduction succeeded.
    Shows a Telegram alert (popup) either way.
    """
    user_id = query.from_user.id
    balance = sh_crystals.get_balance(user_id)

    if balance < cost:
        await query.answer(
            f"❌ Need {cost}💠 — you have {balance}💠\n"
            f"Earn more: /link (referrals +10💠) | /submit (+8💠)",
            show_alert=True,
        )
        return False

    sh_crystals.deduct(user_id, cost, f"view_{feature}")
    await query.answer(
        f"💠 -{cost} crystals | Remaining: {balance - cost}💠",
        show_alert=False,
    )
    return True


# ── Main dispatcher ───────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data

    # ── mutual:<user_id> ──────────────────────────────────────────────────────
    if data.startswith("mutual:"):
        uid    = int(data.split(":", 1)[1])
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
        uid = int(data.split(":", 1)[1])
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
        cid, offset = int(cid), int(offset)
        from db.connection import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT m.message_id, m.text, m.caption, m.date, m.sender_id, u.first_name
                    FROM tg_messages m
                    LEFT JOIN tg_users u ON u.id = m.sender_id
                    WHERE m.chat_id = %s ORDER BY m.date DESC LIMIT 5 OFFSET %s
                """, (cid, offset))
                msgs = cur.fetchall()
        if not msgs:
            await query.answer("No more messages.", show_alert=True)
            return
        lines = [f"💬 *Messages* \\(page {offset//5+1}\\)\n"]
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
        cid, offset = int(cid), int(offset)
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
        uid = int(data.split(":", 1)[1])
        top = tg_users.get_top_interactions(uid, limit=10)
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

    # ── stats:<user_id> ───────────────────────────────────────────────────────
    elif data.startswith("stats:"):
        uid   = int(data.split(":", 1)[1])
        user  = tg_users.get(uid)
        if not user:
            await query.answer("User not found.", show_alert=True)
            return
        stats = tg_users.get_extended_stats(uid)
        tm    = int(stats.get("total_messages") or 0)
        tm_m  = int(stats.get("total_media")    or 0)
        tm_r  = int(stats.get("total_replies")  or 0)
        tm_f  = int(stats.get("total_forwards") or 0)
        gc    = int(stats.get("group_count")    or 0)
        cc    = int(stats.get("channel_count")  or 0)
        name  = escape((user.get("first_name") or "") + " " + (user.get("last_name") or "")).strip()
        lines = [
            f"📊 *Stats for {name}*\n",
            f"• 💬 Messages: `{tm}`",
            f"• 📸 Media: `{tm_m}` \\| ↩️ Replies: `{tm_r}` \\| ↪️ Forwards: `{tm_f}`",
            f"• 👥 Groups: `{gc}` \\| 📢 Channels: `{cc}`",
            f"• 🎥 Circles: `{stats.get('circles',0)}` \\| 🎙 Voice: `{stats.get('voice',0)}`",
            f"• 👑 Admin in: `{stats.get('admin_count',0)}` groups",
        ]
        if stats.get("first_message"):
            first_d = escape(stats["first_message"].strftime("%Y-%m-%d"))
            last_d  = escape(stats["last_message"].strftime("%Y-%m-%d"))
            lines.append(f"• 📅 Active: `{first_d}` → `{last_d}`")
        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── words:<user_id> ───────────────────────────────────────────────────────
    elif data.startswith("words:"):
        uid = int(data.split(":", 1)[1])
        from services.nlp import get_word_frequency
        top = get_word_frequency(uid, limit=15)
        if not top:
            await query.answer("No word data available.", show_alert=True)
            return
        user = tg_users.get(uid)
        name = escape((user.get("first_name") or str(uid)) if user else str(uid))
        lines = [f"🔤 *Top Words — {name}*\n"]
        medals = ["🥇","🥈","🥉"] + ["•"] * 20
        for i, (word, cnt) in enumerate(top):
            lines.append(f"{medals[i]} `{escape(word)}` — {cnt}×")
        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── analysis:<user_id> ────────────────────────────────────────────────────
    elif data.startswith("analysis:"):
        uid  = int(data.split(":", 1)[1])
        user = tg_users.get(uid)
        if not user:
            await query.answer("User not found.", show_alert=True)
            return
        name = escape((user.get("first_name") or str(uid)))
        from services.nlp import (
            get_word_frequency, get_reaction_stats,
            get_activity_heatmap, format_heatmap, vocabulary_score
        )
        words     = get_word_frequency(uid, limit=10)
        reactions = get_reaction_stats(uid)
        heatmap   = get_activity_heatmap(uid)
        vocab     = vocabulary_score(uid)
        lines     = [f"🧠 *Analysis — {name}*\n"]
        if words:
            lines.append("*📝 Top Words*")
            for word, count in words:
                lines.append(f"  `{escape(word)}` — {count}×")
        else:
            lines.append("*📝 Top Words*\n  _No message data yet_")
        if reactions:
            lines.append("\n*❤️ Reactions*")
            for r in reactions[:5]:
                lines.append(f"  {r['emoji']} ×{r['total']}")
        lines.append(
            f"\n*📚 Vocabulary*\n"
            f"  {vocab.get('unique_words',0):,} unique / {vocab.get('total_words',0):,} total\n"
            f"  Richness: `{vocab.get('richness_pct',0)}%`"
        )
        if heatmap and any(heatmap.values()):
            peak = sorted(heatmap.items(), key=lambda x: x[1], reverse=True)[:3]
            hrs  = ", ".join(f"`{h:02d}:00`" for h, _ in peak)
            lines.append(f"\n*🕐 Peak Hours*\n  {hrs}")
        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── aura:<user_id> ────────────────────────────────────────────────────────
    elif data.startswith("aura:"):
        uid = int(data.split(":", 1)[1])
        from db import sh_aura
        score = sh_aura.get_score(uid)
        user  = tg_users.get(uid)
        name  = escape((user.get("first_name") or str(uid)) if user else str(uid))
        lines = [
            f"🌟 *Reputation — {name}*\n",
            f"• Aura score: `{score}`",
            f"• Earned from community interactions",
        ]
        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── track_user:<user_id> ─ show inline tracking menu ──────────────────────
    elif data.startswith("track_user:"):
        uid  = int(data.split(":", 1)[1])
        user = tg_users.get(uid)
        if not user:
            await query.answer("User not found.", show_alert=True)
            return
        name = escape(user.get("first_name") or str(uid))
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 online",    callback_data=f"track_do:{uid}:online"),
                InlineKeyboardButton("📝 name",      callback_data=f"track_do:{uid}:name"),
                InlineKeyboardButton("📋 bio",       callback_data=f"track_do:{uid}:bio"),
            ],
            [
                InlineKeyboardButton("🖼 photo",     callback_data=f"track_do:{uid}:photo"),
                InlineKeyboardButton("✅ all types", callback_data=f"track_do:{uid}:all"),
            ],
        ])
        await query.message.reply_text(
            f"🔔 *Track {name}*\n\nChoose what to track:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb,
        )

    # ── track_do:<user_id>:<type> ─ actually register tracking ───────────────
    elif data.startswith("track_do:"):
        _, uid_s, track_type_key = data.split(":", 2)
        uid      = int(uid_s)
        actor_id = query.from_user.id

        from db import sh_users as sh_users_db
        from db.connection import get_conn
        sh_user     = sh_users_db.get(actor_id)
        max_tracking = (sh_user or {}).get("max_tracking", 0)
        if max_tracking == 0:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("👑 Upgrade Plan", callback_data="show_plan"),
            ]])
            await query.message.reply_text(
                "❌ Tracking requires a *Pro* plan or higher\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=kb,
            )
            return

        TRACK_TYPES = {
            "online": "user_online", "name": "user_name",
            "bio": "user_bio",       "photo": "user_photo",
        }
        types_to_add = (
            list(TRACK_TYPES.values()) if track_type_key == "all"
            else [TRACK_TYPES[track_type_key]] if track_type_key in TRACK_TYPES
            else list(TRACK_TYPES.values())
        )

        added = []
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM tg_tracking WHERE tracker_user_id = %s AND is_active = TRUE",
                    (actor_id,)
                )
                current = (cur.fetchone() or {}).get("cnt", 0)
                if current >= max_tracking:
                    kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton("👑 Upgrade Plan", callback_data="show_plan"),
                    ]])
                    await query.message.reply_text(
                        f"❌ Tracking limit reached \\(`{max_tracking}`\\)\\.\nUpgrade your plan or untrack someone first\\.",
                        parse_mode=ParseMode.MARKDOWN_V2,
                        reply_markup=kb,
                    )
                    return
                for t in types_to_add:
                    cur.execute("""
                        INSERT INTO tg_tracking (tracker_user_id, target_user_id, track_type)
                        VALUES (%s,%s,%s)
                        ON CONFLICT (tracker_user_id, target_user_id, track_type) DO NOTHING
                    """, (actor_id, uid, t))
                    if cur.rowcount:
                        added.append(t)
            conn.commit()

        user = tg_users.get(uid)
        name = escape(user.get("first_name") or str(uid) if user else str(uid))
        types_str = escape(", ".join(t.replace("user_", "") for t in added) or "already tracked")
        await query.message.reply_text(
            f"✅ Now tracking *{name}* — `{types_str}`\nYou'll be notified of any changes\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    # ── crystal_prices ────────────────────────────────────────────────────────
    elif data == "crystal_prices":
        lines = [
            "💠 *Crystal Price List*\n",
            f"• Names history — `{COSTS['names']}` 💠",
            f"• Groups list   — `{COSTS['groups']}` 💠",
            f"• Messages      — `{COSTS['messages']}` 💠",
            f"• Channels list — `{COSTS['channels']}` 💠",
            f"• Friends/interactions — `{COSTS['friends']}` 💠",
            f"• Reaction stats  — `{COSTS['reactions']}` 💠",
            "",
            "*How to earn crystals:*",
            "• Share /link — \\+10💠 per new user",
            "• Submit group /submit — \\+8💠",
            "• Refer friends — \\+4💠 per active ref",
        ]
        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── crystal_names:<uid> ───────────────────────────────────────────────────
    elif data.startswith("crystal_names:"):
        uid  = int(data.split(":", 1)[1])
        cost = COSTS["names"]
        ok   = await _crystal_gate(query, cost, "names")
        if not ok:
            return

        user = tg_users.get(uid)
        name = escape((user.get("first_name") or str(uid)) if user else str(uid))

        username_hist = tg_users.get_username_history(uid)
        name_hist     = tg_users.get_name_history(uid)
        bio_hist      = tg_users.get_bio_history(uid)

        lines = [f"📋 *Full History — {name}*\n"]

        if username_hist:
            lines.append("*🔄 Usernames:*")
            for h in username_hist:
                dt = h["seen_at"].strftime("%Y\\-%m\\-%d") if h.get("seen_at") else "?"
                lines.append(f"• `{dt}`  ➜  @{escape(h['username'])}")
            lines.append("")

        if name_hist:
            lines.append("*📝 Names:*")
            for h in name_hist:
                dt      = h["seen_at"].strftime("%Y\\-%m\\-%d") if h.get("seen_at") else "?"
                full_n  = " ".join(filter(None, [h.get("first_name"), h.get("last_name")])) or "?"
                lines.append(f"• `{dt}`  ➜  {escape(full_n)}")
            lines.append("")

        if bio_hist:
            lines.append("*📋 Bio changes:*")
            for h in bio_hist[:5]:
                dt  = h["seen_at"].strftime("%Y\\-%m\\-%d") if h.get("seen_at") else "?"
                bio = escape((h.get("bio") or "_empty_")[:100])
                lines.append(f"• `{dt}` — _{bio}_")

        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── crystal_groups:<uid> ──────────────────────────────────────────────────
    elif data.startswith("crystal_groups:"):
        uid  = int(data.split(":", 1)[1])
        cost = COSTS["groups"]
        ok   = await _crystal_gate(query, cost, "groups")
        if not ok:
            return

        user   = tg_users.get(uid)
        name   = escape((user.get("first_name") or str(uid)) if user else str(uid))
        groups = tg_users.get_chats(uid, limit=30)
        groups = [g for g in groups if g["type"] in ("group", "supergroup", "gigagroup")]

        if not groups:
            await query.message.reply_text(
                f"😔 No groups found for *{name}*\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        lines = [f"👥 *Groups — {name}* \\({len(groups)}\\)\n"]
        for g in groups:
            ref  = f"@{escape(g['username'])}" if g.get("username") else escape(g.get("title") or str(g["id"]))
            role = " 👑" if g.get("is_admin") else ""
            lines.append(f"• {ref}{role}")

        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── crystal_channels:<uid> ────────────────────────────────────────────────
    elif data.startswith("crystal_channels:"):
        uid  = int(data.split(":", 1)[1])
        cost = COSTS["channels"]
        ok   = await _crystal_gate(query, cost, "channels")
        if not ok:
            return

        user     = tg_users.get(uid)
        name     = escape((user.get("first_name") or str(uid)) if user else str(uid))
        channels = tg_users.get_user_channels(uid, limit=25)

        if not channels:
            await query.message.reply_text(
                f"😔 No channels found for *{name}*\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        lines = [f"📢 *Channels — {name}* \\({len(channels)}\\)\n"]
        for c in channels:
            ref   = f"@{escape(c['username'])}" if c.get("username") else escape(c.get("title") or str(c["id"]))
            count = c.get("message_count", 0)
            lines.append(f"• {ref} — `{count}` msgs")

        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── crystal_msgs:<uid>:<offset> ───────────────────────────────────────────
    elif data.startswith("crystal_msgs:"):
        parts  = data.split(":")
        uid    = int(parts[1])
        offset = int(parts[2])
        cost   = COSTS["messages"] if offset == 0 else 0  # only charge first page

        if offset == 0:
            ok = await _crystal_gate(query, cost, "messages")
            if not ok:
                return
        else:
            await query.answer()

        msgs = tg_messages.get_user_messages(uid, limit=5, offset=offset)
        if not msgs:
            await query.answer("No more messages.", show_alert=True)
            return

        user = tg_users.get(uid)
        name = escape((user.get("first_name") or str(uid)) if user else str(uid))
        lines = [f"💬 *Messages — {name}* \\(page {offset//5+1}\\)\n"]
        for m in msgs:
            text     = escape((m["text"] or m["caption"] or "")[:100])
            chat_ref = escape(m.get("chat_username") or m.get("chat_title") or str(m["chat_id"]))
            date_str = m["date"].strftime("%Y\\-%m\\-%d") if m["date"] else "?"
            lines.append(f"• {chat_ref}\n  `{text}`\n  _{date_str}_")

        kb = []
        if offset > 0:
            kb.append(InlineKeyboardButton("◀️ Prev", callback_data=f"crystal_msgs:{uid}:{offset-5}"))
        if len(msgs) == 5:
            kb.append(InlineKeyboardButton("Next ▶️", callback_data=f"crystal_msgs:{uid}:{offset+5}"))

        await query.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([kb]) if kb else None,
        )

    # ── crystal_friends:<uid> ─────────────────────────────────────────────────
    elif data.startswith("crystal_friends:"):
        uid  = int(data.split(":", 1)[1])
        cost = COSTS["friends"]
        ok   = await _crystal_gate(query, cost, "friends")
        if not ok:
            return

        top = tg_users.get_top_interactions(uid, limit=15)
        user = tg_users.get(uid)
        name = escape((user.get("first_name") or str(uid)) if user else str(uid))

        if not top:
            await query.message.reply_text(
                f"😔 No interaction data for *{name}*\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        medals = ["🥇","🥈","🥉"] + ["•"] * 20
        lines  = [f"🔗 *Friends/Interactions — {name}*\n"]
        for i, r in enumerate(top):
            n = escape(r["first_name"] or "Unknown")
            u = f" @{escape(r['username'])}" if r.get("username") else ""
            lines.append(f"{medals[i]} {n}{u} — `{r['interactions']}`×")

        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── crystal_reactions:<uid> ───────────────────────────────────────────────
    elif data.startswith("crystal_reactions:"):
        uid  = int(data.split(":", 1)[1])
        cost = COSTS["reactions"]
        ok   = await _crystal_gate(query, cost, "reactions")
        if not ok:
            return

        from services.nlp import get_reaction_stats
        reactions = get_reaction_stats(uid)
        user = tg_users.get(uid)
        name = escape((user.get("first_name") or str(uid)) if user else str(uid))

        if not reactions:
            await query.message.reply_text(
                f"😔 No reaction data for *{name}*\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        lines = [f"👍 *Reactions — {name}*\n"]
        for r in reactions:
            lines.append(f"• {r['emoji']} — `{r['total']}`×")

        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── search_more:<query>:<offset> ──────────────────────────────────────────
    elif data.startswith("search_more:"):
        parts     = data.split(":", 2)
        q, offset = parts[1], int(parts[2])
        PAGE      = 5
        users     = tg_users.search(q, limit=PAGE, offset=offset)
        chats     = tg_chats.search(q, limit=PAGE, offset=offset)
        if not users and not chats:
            await query.answer("No more results.", show_alert=True)
            return
        page_num = offset // PAGE + 1
        lines = [f"🔍 *Results for* `{escape(q)}` \\(page {page_num}\\)\n"]
        for u in users:
            lines.append(user_line(u))
        for c in chats:
            lines.append(chat_line(c))
        kb = []
        if offset > 0:
            kb.append(InlineKeyboardButton("◀️ Prev", callback_data=f"search_more:{q}:{offset - PAGE}"))
        if len(users) == PAGE or len(chats) == PAGE:
            kb.append(InlineKeyboardButton("Next ▶️", callback_data=f"search_more:{q}:{offset + PAGE}"))
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([kb]) if kb else None,
        )

    # ── show_link ─ open referral page inline ────────────────────────────────
    elif data == "show_link":
        user      = query.from_user
        from db import sh_referrals, sh_crystals as sh_cr
        ref_count = sh_referrals.count(user.id)
        balance   = sh_cr.get_balance(user.id)
        system_uname = escape(query.message.bot.username or "")
        link = f"https://t\\.me/{system_uname}?start=ref_{user.id}"
        await query.message.reply_text(
            f"🔗 *Your Referral Link*\n\n"
            f"`{link}`\n\n"
            f"👥 Referrals: `{ref_count}`\n"
            f"💠 Crystals: `{balance}`\n\n"
            f"_Every new user who joins via your link earns you `10` 💠_",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    # ── show_submit ─ open group submission inline ────────────────────────────
    elif data == "show_submit":
        await query.message.reply_text(
            "📢 *Submit a Group to SeekHub*\n\n"
            "Command: `/submit @groupusername`\n\n"
            "• \\+8💠 per approved group\n"
            "• You must be a member or admin of the group",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    # ── show_plan ─ open plan page inline ────────────────────────────────────
    elif data == "show_plan":
        from db import sh_users as sh_users_mod
        sh_user   = sh_users_mod.get(query.from_user.id)
        plan_name = escape((sh_user or {}).get("plan_name") or "Free")
        daily_q   = (sh_user or {}).get("daily_queries", 5)
        max_trk   = (sh_user or {}).get("max_tracking", 0)
        can_exp   = "✅" if (sh_user or {}).get("can_export") else "❌"
        lines = [
            f"👑 *Your Plan: {plan_name}*\n",
            f"• 🔍 Daily queries: `{daily_q}`",
            f"• 🔔 Tracking slots: `{max_trk}`",
            f"• 📤 Export: {can_exp}",
            "",
            "*Available Plans:*",
            "• Free — 5 queries/day",
            "• Pro  — 50 queries/day \\+ tracking",
            "• Elite — unlimited \\+ export",
            "",
            "_Contact the system admin to upgrade\\._",
        ]
        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

    # ── help_how ─ quick onboarding card ──────────────────────────────────────
    elif data == "help_how":
        lines = [
            "❓ *How SeekHub works*\n",
            "*Search a user:*",
            "Just type their name or @username — no command needed\\.",
            "",
            "*Search a group or channel:*",
            "Type the group name or use 🎯 Select to pick from your list\\.",
            "",
            "*Profile cards:*",
            "Each result shows activity stats, name history, and action buttons\\.",
            "Tap any button to dig deeper — some details cost 💠 crystals\\.",
            "",
            "*Earn crystals:*",
            "• Share your referral link — \\+10💠 per new user",
            "• Submit a group — \\+8💠 per approval",
            "",
            "*Track a user:*",
            "Get notified when they change name, bio, photo, or come online\\.",
            "Requires a Pro plan\\.",
        ]
        await query.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)

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
