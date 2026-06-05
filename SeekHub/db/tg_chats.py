"""
Telegram chats (groups, supergroups, channels) — index + history.
"""
from .connection import get_conn


def upsert(chat_id: int, type_: str, title: str = None, username: str = None,
           description: str = None, member_count: int = None,
           is_verified: bool = False, is_scam: bool = False, is_fake: bool = False,
           is_broadcast: bool = False, linked_chat_id: int = None, lang_code: str = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT title, username, description, member_count FROM tg_chats WHERE id = %s", (chat_id,))
            existing = cur.fetchone()

            cur.execute("""
                INSERT INTO tg_chats
                    (id, type, title, username, description, member_count,
                     is_verified, is_scam, is_fake, is_broadcast,
                     linked_chat_id, lang_code, last_indexed_at, last_updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                ON CONFLICT (id) DO UPDATE SET
                    title           = COALESCE(EXCLUDED.title,       tg_chats.title),
                    username        = COALESCE(EXCLUDED.username,     tg_chats.username),
                    description     = COALESCE(EXCLUDED.description,  tg_chats.description),
                    member_count    = COALESCE(EXCLUDED.member_count, tg_chats.member_count),
                    is_verified     = EXCLUDED.is_verified,
                    is_scam         = EXCLUDED.is_scam,
                    is_fake         = EXCLUDED.is_fake,
                    is_broadcast    = EXCLUDED.is_broadcast,
                    linked_chat_id  = COALESCE(EXCLUDED.linked_chat_id, tg_chats.linked_chat_id),
                    last_indexed_at = NOW(),
                    last_updated_at = NOW()
            """, (chat_id, type_, title, username, description, member_count,
                  is_verified, is_scam, is_fake, is_broadcast, linked_chat_id, lang_code))

            # History snapshot if anything changed
            if existing:
                changed = (
                    existing["title"] != title or
                    existing["username"] != username or
                    existing["description"] != description or
                    (member_count and existing["member_count"] != member_count)
                )
                if changed:
                    cur.execute("""
                        INSERT INTO tg_chat_history (chat_id, title, description, username, member_count)
                        VALUES (%s,%s,%s,%s,%s)
                    """, (chat_id, title, description, username, member_count))
            else:
                cur.execute("""
                    INSERT INTO tg_chat_history (chat_id, title, description, username, member_count)
                    VALUES (%s,%s,%s,%s,%s)
                """, (chat_id, title, description, username, member_count))

            # Update search index
            display = " ".join(filter(None, [title, f"@{username}" if username else None]))
            cur.execute("""
                INSERT INTO tg_search_index (entity_type, entity_id, display, search_vec, updated_at)
                VALUES ('chat', %s, %s, to_tsvector('simple', %s), NOW())
                ON CONFLICT (entity_type, entity_id) DO UPDATE SET
                    display    = EXCLUDED.display,
                    search_vec = EXCLUDED.search_vec,
                    updated_at = NOW()
            """, (chat_id, display, display))

        conn.commit()


def get(chat_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tg_chats WHERE id = %s", (chat_id,))
            return cur.fetchone()


def get_by_username(username: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM tg_chats WHERE lower(username) = lower(%s)",
                (username.lstrip("@"),)
            )
            return cur.fetchone()


def get_history(chat_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM tg_chat_history WHERE chat_id = %s ORDER BY seen_at DESC",
                (chat_id,)
            )
            return cur.fetchall()


def get_members(chat_id: int, limit: int = 50, offset: int = 0):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.first_name, u.last_name, u.username,
                       u.is_verified, u.is_premium,
                       m.status, m.is_admin, m.title, m.first_seen_at, m.last_seen_at
                FROM tg_memberships m
                JOIN tg_users u ON u.id = m.user_id
                WHERE m.chat_id = %s
                ORDER BY m.is_admin DESC, m.last_seen_at DESC
                LIMIT %s OFFSET %s
            """, (chat_id, limit, offset))
            return cur.fetchall()


def get_top_posters(chat_id: int, limit: int = 10):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.first_name, u.last_name, u.username,
                       s.message_count, s.media_count,
                       s.first_message_at, s.last_message_at
                FROM tg_user_chat_stats s
                JOIN tg_users u ON u.id = s.user_id
                WHERE s.chat_id = %s
                ORDER BY s.message_count DESC
                LIMIT %s
            """, (chat_id, limit))
            return cur.fetchall()


def search(query: str, type_filter: str = None, limit: int = 10):
    with get_conn() as conn:
        with conn.cursor() as cur:
            type_clause = "AND c.type = %s" if type_filter else ""
            params = [query, query]
            if type_filter:
                params.append(type_filter)
            params.append(limit)

            cur.execute(f"""
                SELECT c.id, c.type, c.title, c.username, c.member_count,
                       c.is_verified, c.is_scam
                FROM tg_search_index si
                JOIN tg_chats c ON c.id = si.entity_id
                WHERE si.entity_type = 'chat'
                  AND si.search_vec @@ plainto_tsquery('simple', %s)
                  {type_clause}
                ORDER BY ts_rank(si.search_vec, plainto_tsquery('simple', %s)) DESC,
                         c.member_count DESC NULLS LAST
                LIMIT %s
            """, params)
            return cur.fetchall()


def count() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM tg_chats")
            return cur.fetchone()["cnt"]
