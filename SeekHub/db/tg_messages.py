"""
Indexed public messages — insert, search, stats.
"""
from .connection import get_conn


def upsert(message_id: int, chat_id: int, sender_id: int = None,
           sender_chat_id: int = None, text: str = None, caption: str = None,
           media_type: str = None, file_id: str = None,
           reply_to_msg_id: int = None, forward_from_id: int = None,
           forward_date=None, views: int = 0, forwards: int = 0,
           reactions_count: int = 0, is_pinned: bool = False, date=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tg_messages
                    (message_id, chat_id, sender_id, sender_chat_id, text, caption,
                     media_type, file_id, reply_to_msg_id, forward_from_id,
                     forward_date, views, forwards, reactions_count, is_pinned, date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (chat_id, message_id) DO UPDATE SET
                    views           = GREATEST(tg_messages.views, EXCLUDED.views),
                    forwards        = GREATEST(tg_messages.forwards, EXCLUDED.forwards),
                    reactions_count = GREATEST(tg_messages.reactions_count, EXCLUDED.reactions_count),
                    is_pinned       = EXCLUDED.is_pinned
            """, (message_id, chat_id, sender_id, sender_chat_id, text, caption,
                  media_type, file_id, reply_to_msg_id, forward_from_id,
                  forward_date, views, forwards, reactions_count, is_pinned, date))

            # Update user-chat stats
            if sender_id:
                is_media = bool(media_type and media_type != "sticker")
                is_sticker = media_type == "sticker"
                is_reply = bool(reply_to_msg_id)
                is_forward = bool(forward_from_id)

                cur.execute("""
                    INSERT INTO tg_user_chat_stats
                        (user_id, chat_id, message_count, media_count, sticker_count,
                         forward_count, reply_count, first_message_at, last_message_at)
                    VALUES (%s,%s,1,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (user_id, chat_id) DO UPDATE SET
                        message_count    = tg_user_chat_stats.message_count + 1,
                        media_count      = tg_user_chat_stats.media_count   + %s,
                        sticker_count    = tg_user_chat_stats.sticker_count + %s,
                        forward_count    = tg_user_chat_stats.forward_count + %s,
                        reply_count      = tg_user_chat_stats.reply_count   + %s,
                        first_message_at = LEAST(tg_user_chat_stats.first_message_at, %s),
                        last_message_at  = GREATEST(tg_user_chat_stats.last_message_at, %s)
                """, (
                    sender_id, chat_id,
                    1 if is_media else 0, 1 if is_sticker else 0,
                    1 if is_forward else 0, 1 if is_reply else 0,
                    date, date,
                    # ON CONFLICT values
                    1 if is_media else 0, 1 if is_sticker else 0,
                    1 if is_forward else 0, 1 if is_reply else 0,
                    date, date,
                ))

        conn.commit()


def search_text(query: str, chat_id: int = None, sender_id: int = None,
                limit: int = 20, offset: int = 0):
    """Full-text search in indexed messages."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            conditions = ["(to_tsvector('simple', coalesce(text,'') || ' ' || coalesce(caption,'')) @@ plainto_tsquery('simple', %s))"]
            params: list = [query]

            if chat_id:
                conditions.append("chat_id = %s")
                params.append(chat_id)
            if sender_id:
                conditions.append("sender_id = %s")
                params.append(sender_id)

            where = " AND ".join(conditions)
            params += [limit, offset]

            cur.execute(f"""
                SELECT m.message_id, m.chat_id, m.sender_id, m.text, m.caption,
                       m.media_type, m.date, m.views, m.forwards,
                       u.first_name, u.username,
                       c.title AS chat_title, c.username AS chat_username
                FROM tg_messages m
                LEFT JOIN tg_users u ON u.id = m.sender_id
                LEFT JOIN tg_chats c ON c.id = m.chat_id
                WHERE {where}
                ORDER BY m.date DESC
                LIMIT %s OFFSET %s
            """, params)
            return cur.fetchall()


def get_user_messages(user_id: int, chat_id: int = None, limit: int = 20, offset: int = 0):
    with get_conn() as conn:
        with conn.cursor() as cur:
            params = [user_id]
            chat_clause = ""
            if chat_id:
                chat_clause = "AND m.chat_id = %s"
                params.append(chat_id)
            params += [limit, offset]

            cur.execute(f"""
                SELECT m.message_id, m.chat_id, m.text, m.caption, m.media_type,
                       m.date, m.views, m.forwards,
                       c.title AS chat_title, c.username AS chat_username
                FROM tg_messages m
                JOIN tg_chats c ON c.id = m.chat_id
                WHERE m.sender_id = %s {chat_clause}
                ORDER BY m.date DESC
                LIMIT %s OFFSET %s
            """, params)
            return cur.fetchall()


def count() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM tg_messages")
            return cur.fetchone()["cnt"]
