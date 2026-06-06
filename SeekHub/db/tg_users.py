"""
Telegram users — core index table + history tables.
Called by collectors whenever a user is seen.
"""
from .connection import get_conn


def upsert(user_id: int, first_name: str = None, last_name: str = None,
           username: str = None, is_bot: bool = False, is_premium: bool = False,
           lang_code: str = None, bio: str = None, photo_id: str = None,
           is_verified: bool = False, is_deleted: bool = False):
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Fetch current record to detect changes
            cur.execute("SELECT username, first_name, last_name, bio, photo_id FROM tg_users WHERE id = %s", (user_id,))
            existing = cur.fetchone()

            cur.execute("""
                INSERT INTO tg_users
                    (id, first_name, last_name, username, is_bot, is_premium,
                     lang_code, bio, photo_id, is_verified, is_deleted, last_seen_at, last_updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                ON CONFLICT (id) DO UPDATE SET
                    first_name      = COALESCE(EXCLUDED.first_name, tg_users.first_name),
                    last_name       = COALESCE(EXCLUDED.last_name,  tg_users.last_name),
                    username        = COALESCE(EXCLUDED.username,   tg_users.username),
                    is_premium      = EXCLUDED.is_premium,
                    lang_code       = COALESCE(EXCLUDED.lang_code,  tg_users.lang_code),
                    bio             = COALESCE(EXCLUDED.bio,        tg_users.bio),
                    photo_id        = COALESCE(EXCLUDED.photo_id,   tg_users.photo_id),
                    is_verified     = EXCLUDED.is_verified,
                    is_deleted      = EXCLUDED.is_deleted,
                    last_seen_at    = NOW(),
                    last_updated_at = NOW()
            """, (user_id, first_name, last_name, username, is_bot, is_premium,
                  lang_code, bio, photo_id, is_verified, is_deleted))

            # Record username change
            if existing and username and existing["username"] != username:
                cur.execute(
                    "INSERT INTO tg_username_history (user_id, username) VALUES (%s, %s)",
                    (user_id, username)
                )
            elif not existing and username:
                cur.execute(
                    "INSERT INTO tg_username_history (user_id, username) VALUES (%s, %s)",
                    (user_id, username)
                )

            # Record name change
            if existing and (existing["first_name"] != first_name or existing["last_name"] != last_name):
                cur.execute(
                    "INSERT INTO tg_name_history (user_id, first_name, last_name) VALUES (%s,%s,%s)",
                    (user_id, first_name, last_name)
                )
            elif not existing:
                cur.execute(
                    "INSERT INTO tg_name_history (user_id, first_name, last_name) VALUES (%s,%s,%s)",
                    (user_id, first_name, last_name)
                )

            # Record bio change
            if existing and bio and existing["bio"] != bio:
                cur.execute(
                    "INSERT INTO tg_bio_history (user_id, bio) VALUES (%s,%s)",
                    (user_id, bio)
                )

            # Record photo change
            if existing and photo_id and existing["photo_id"] != photo_id:
                cur.execute(
                    "INSERT INTO tg_photo_history (user_id, photo_id) VALUES (%s,%s)",
                    (user_id, photo_id)
                )

            # Update search index
            display = " ".join(filter(None, [first_name, last_name, f"@{username}" if username else None]))
            cur.execute("""
                INSERT INTO tg_search_index (entity_type, entity_id, display, search_vec, updated_at)
                VALUES ('user', %s, %s, to_tsvector('simple', %s), NOW())
                ON CONFLICT (entity_type, entity_id) DO UPDATE SET
                    display    = EXCLUDED.display,
                    search_vec = EXCLUDED.search_vec,
                    updated_at = NOW()
            """, (user_id, display, display))

        conn.commit()


def get(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM tg_users WHERE id = %s", (user_id,))
            return cur.fetchone()


def get_by_username(username: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM tg_users WHERE lower(username) = lower(%s)",
                (username.lstrip("@"),)
            )
            return cur.fetchone()


def get_username_history(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, seen_at FROM tg_username_history WHERE user_id = %s ORDER BY seen_at DESC",
                (user_id,)
            )
            return cur.fetchall()


def get_name_history(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT first_name, last_name, seen_at FROM tg_name_history WHERE user_id = %s ORDER BY seen_at DESC",
                (user_id,)
            )
            return cur.fetchall()


def get_bio_history(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT bio, seen_at FROM tg_bio_history WHERE user_id = %s ORDER BY seen_at DESC",
                (user_id,)
            )
            return cur.fetchall()


def get_chats(user_id: int, limit: int = 20):
    """All chats/groups a user has been seen in."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.type, c.title, c.username, m.status, m.first_seen_at, m.last_seen_at
                FROM tg_memberships m
                JOIN tg_chats c ON c.id = m.chat_id
                WHERE m.user_id = %s
                ORDER BY m.last_seen_at DESC
                LIMIT %s
            """, (user_id, limit))
            return cur.fetchall()


def get_mutual_chats(user_id_a: int, user_id_b: int):
    """Chats that both users have been seen in."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.type, c.title, c.username
                FROM tg_memberships ma
                JOIN tg_memberships mb ON ma.chat_id = mb.chat_id
                JOIN tg_chats c ON c.id = ma.chat_id
                WHERE ma.user_id = %s AND mb.user_id = %s
                ORDER BY c.title
            """, (user_id_a, user_id_b))
            return cur.fetchall()


def get_top_interactions(user_id: int, limit: int = 10):
    """Users this person interacts with most."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    CASE WHEN i.from_user_id = %s THEN i.to_user_id ELSE i.from_user_id END AS other_id,
                    u.first_name, u.last_name, u.username,
                    SUM(i.count) AS interactions
                FROM tg_interactions i
                JOIN tg_users u ON u.id = CASE WHEN i.from_user_id = %s THEN i.to_user_id ELSE i.from_user_id END
                WHERE i.from_user_id = %s OR i.to_user_id = %s
                GROUP BY other_id, u.first_name, u.last_name, u.username
                ORDER BY interactions DESC
                LIMIT %s
            """, (user_id, user_id, user_id, user_id, limit))
            return cur.fetchall()


def get_message_stats(user_id: int):
    """Aggregated message stats across all chats."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    SUM(message_count) AS total_messages,
                    SUM(media_count)   AS total_media,
                    COUNT(DISTINCT chat_id) AS chat_count,
                    MIN(first_message_at) AS first_seen,
                    MAX(last_message_at)  AS last_seen
                FROM tg_user_chat_stats
                WHERE user_id = %s
            """, (user_id,))
            return cur.fetchone()


def search(query: str, limit: int = 10, offset: int = 0):
    """Full-text search across user display names and usernames."""
    clean = query.lstrip("@").strip()
    if not clean:
        return []
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.first_name, u.last_name, u.username, u.is_verified, u.is_premium
                FROM tg_search_index si
                JOIN tg_users u ON u.id = si.entity_id
                WHERE si.entity_type = 'user'
                  AND si.search_vec @@ plainto_tsquery('simple', %s)
                ORDER BY ts_rank(si.search_vec, plainto_tsquery('simple', %s)) DESC
                LIMIT %s OFFSET %s
            """, (clean, clean, limit, offset))
            return cur.fetchall()


def count() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM tg_users")
            return cur.fetchone()["cnt"]


def log_online(user_id: int, status: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tg_online_log (user_id, status) VALUES (%s, %s)",
                (user_id, status)
            )
        conn.commit()
