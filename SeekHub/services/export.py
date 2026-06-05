"""
services/export.py
==================
Export indexed data as CSV — members list, message history,
interaction graph. Available to Pro/Elite plan users.
"""
import csv
import io
import logging
from db.connection import get_conn

logger = logging.getLogger(__name__)


def export_chat_members(chat_id: int) -> bytes:
    """
    Export full member list of a chat as CSV bytes.
    Columns: id, first_name, last_name, username, status, is_admin, first_seen, last_seen
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    u.id, u.first_name, u.last_name, u.username,
                    u.is_premium, u.is_verified, u.is_deleted,
                    m.status, m.is_admin, m.title,
                    m.first_seen_at, m.last_seen_at
                FROM tg_memberships m
                JOIN tg_users u ON u.id = m.user_id
                WHERE m.chat_id = %s
                ORDER BY m.last_seen_at DESC
            """, (chat_id,))
            rows = cur.fetchall()

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "id","first_name","last_name","username","is_premium","is_verified",
        "is_deleted","status","is_admin","admin_title","first_seen","last_seen"
    ])
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "id":           r["id"],
            "first_name":   r["first_name"] or "",
            "last_name":    r["last_name"] or "",
            "username":     r["username"] or "",
            "is_premium":   r["is_premium"],
            "is_verified":  r["is_verified"],
            "is_deleted":   r["is_deleted"],
            "status":       r["status"],
            "is_admin":     r["is_admin"],
            "admin_title":  r["title"] or "",
            "first_seen":   r["first_seen_at"].isoformat() if r["first_seen_at"] else "",
            "last_seen":    r["last_seen_at"].isoformat()  if r["last_seen_at"]  else "",
        })

    return buf.getvalue().encode("utf-8-sig")   # BOM for Excel compatibility


def export_user_messages(user_id: int, chat_id: int = None) -> bytes:
    """Export all indexed messages of a user as CSV."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            params = [user_id]
            chat_clause = ""
            if chat_id:
                chat_clause = "AND m.chat_id = %s"
                params.append(chat_id)

            cur.execute(f"""
                SELECT
                    m.message_id, m.chat_id, c.title AS chat_title, c.username AS chat_username,
                    m.text, m.caption, m.media_type,
                    m.reply_to_msg_id, m.views, m.forwards, m.date
                FROM tg_messages m
                JOIN tg_chats c ON c.id = m.chat_id
                WHERE m.sender_id = %s {chat_clause}
                ORDER BY m.date DESC
                LIMIT 50000
            """, params)
            rows = cur.fetchall()

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "message_id","chat_id","chat_title","chat_username",
        "text","caption","media_type","reply_to","views","forwards","date"
    ])
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "message_id":    r["message_id"],
            "chat_id":       r["chat_id"],
            "chat_title":    r["chat_title"] or "",
            "chat_username": r["chat_username"] or "",
            "text":          (r["text"] or "").replace("\n", " "),
            "caption":       (r["caption"] or "").replace("\n", " "),
            "media_type":    r["media_type"] or "",
            "reply_to":      r["reply_to_msg_id"] or "",
            "views":         r["views"] or 0,
            "forwards":      r["forwards"] or 0,
            "date":          r["date"].isoformat() if r["date"] else "",
        })

    return buf.getvalue().encode("utf-8-sig")


def export_interaction_graph(user_id: int) -> bytes:
    """
    Export interaction graph as CSV edge list.
    Columns: from_id, from_name, to_id, to_name, type, count, last_at
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    i.from_user_id, uf.first_name AS from_name, uf.username AS from_uname,
                    i.to_user_id,   ut.first_name AS to_name,   ut.username AS to_uname,
                    i.interaction_type AS type, i.count, i.last_at
                FROM tg_interactions i
                JOIN tg_users uf ON uf.id = i.from_user_id
                JOIN tg_users ut ON ut.id = i.to_user_id
                WHERE i.from_user_id = %s OR i.to_user_id = %s
                ORDER BY i.count DESC
                LIMIT 10000
            """, (user_id, user_id))
            rows = cur.fetchall()

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "from_id","from_name","from_username",
        "to_id","to_name","to_username",
        "type","count","last_interaction"
    ])
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "from_id":       r["from_user_id"],
            "from_name":     r["from_name"] or "",
            "from_username": r["from_uname"] or "",
            "to_id":         r["to_user_id"],
            "to_name":       r["to_name"] or "",
            "to_username":   r["to_uname"] or "",
            "type":          r["type"],
            "count":         r["count"],
            "last_interaction": r["last_at"].isoformat() if r["last_at"] else "",
        })

    return buf.getvalue().encode("utf-8-sig")
