from .connection import get_conn


def get_all_active():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM sh_mirrors WHERE is_active = TRUE ORDER BY id"
            )
            return cur.fetchall()


def get_by_owner(owner_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM sh_mirrors WHERE owner_id = %s AND is_active = TRUE",
                (owner_id,)
            )
            return cur.fetchall()


def get_by_bot_id(bot_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sh_mirrors WHERE bot_id = %s", (bot_id,))
            return cur.fetchone()


def create(owner_id: int, bot_token: str, bot_id: int, bot_username: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sh_mirrors (owner_id, bot_token, bot_id, bot_username)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (bot_token) DO UPDATE SET
                    owner_id     = EXCLUDED.owner_id,
                    bot_id       = EXCLUDED.bot_id,
                    bot_username = EXCLUDED.bot_username,
                    is_active    = TRUE
                RETURNING *
            """, (owner_id, bot_token, bot_id, bot_username))
            conn.commit()
            return cur.fetchone()


def deactivate(mirror_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sh_mirrors SET is_active = FALSE WHERE id = %s", (mirror_id,))
        conn.commit()


def increment_query_count(mirror_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sh_mirrors SET query_count = query_count + 1 WHERE id = %s",
                (mirror_id,)
            )
        conn.commit()


def track_mirror_user(mirror_id: int, user_id: int, username: str = None, first_name: str = None):
    """
    Record that a user used this mirror.
    Upserts sh_users first to satisfy the FK constraint.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sh_users (id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (user_id, username or "", first_name or "Unknown"))

            cur.execute("""
                INSERT INTO sh_mirror_users (mirror_id, user_id, last_used, query_count)
                VALUES (%s,%s,NOW(),1)
                ON CONFLICT (mirror_id, user_id) DO UPDATE SET
                    last_used   = NOW(),
                    query_count = sh_mirror_users.query_count + 1
            """, (mirror_id, user_id))
            cur.execute(
                "UPDATE sh_mirrors SET user_count = (SELECT COUNT(*) FROM sh_mirror_users WHERE mirror_id = %s) WHERE id = %s",
                (mirror_id, mirror_id)
            )
        conn.commit()


def log_query(mirror_id: int, query_text: str):
    """Record a search query for top-queries analytics."""
    if not query_text or not query_text.strip():
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sh_mirror_queries (mirror_id, query_text) VALUES (%s, %s)",
                (mirror_id, query_text.strip()[:100])
            )
        conn.commit()


def get_settings(mirror_id: int) -> dict:
    """Return the settings JSONB for a mirror (defaults to {})."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT settings FROM sh_mirrors WHERE id = %s", (mirror_id,))
            row = cur.fetchone()
            return (row["settings"] or {}) if row else {}


def set_setting(mirror_id: int, key: str, value) -> None:
    """Set a single key in the mirror's settings JSONB."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sh_mirrors
                SET settings = COALESCE(settings, '{}'::jsonb) || jsonb_build_object(%s::text, %s::boolean)
                WHERE id = %s
            """, (key, value, mirror_id))
        conn.commit()


def get_mirror_stats(mirror_id: int) -> dict:
    """Return activity stats for a single mirror."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE last_used >= NOW() - INTERVAL '7 days')  AS active_7d,
                    COUNT(*) FILTER (WHERE last_used >= NOW() - INTERVAL '30 days') AS active_30d,
                    COUNT(*) FILTER (WHERE first_used >= CURRENT_DATE)              AS new_today
                FROM sh_mirror_users
                WHERE mirror_id = %s
            """, (mirror_id,))
            return dict(cur.fetchone() or {})


def get_top_queries(mirror_id: int, limit: int = 5) -> list:
    """Return the top searched queries for a mirror in the last 30 days."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT query_text, COUNT(*) AS cnt
                FROM sh_mirror_queries
                WHERE mirror_id = %s
                  AND queried_at >= NOW() - INTERVAL '30 days'
                GROUP BY query_text
                ORDER BY cnt DESC
                LIMIT %s
            """, (mirror_id, limit))
            return cur.fetchall()


def count() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM sh_mirrors WHERE is_active = TRUE")
            return cur.fetchone()["cnt"]
