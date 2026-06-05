from .connection import get_conn


def upsert(user_id: int, username: str, first_name: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sh_users (id, username, first_name)
                VALUES (%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    username   = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
            """, (user_id, username, first_name))
        conn.commit()


def get(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.*, p.name AS plan_name, p.daily_queries, p.max_mirrors,
                       p.max_tracking, p.can_export, p.can_track_online,
                       p.features AS plan_features
                FROM sh_users u
                LEFT JOIN sh_plans p ON p.id = u.plan_id
                WHERE u.id = %s
            """, (user_id,))
            return cur.fetchone()


def is_banned(user_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT is_banned FROM sh_users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return bool(row and row["is_banned"])


def count() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM sh_users WHERE is_banned = FALSE")
            return cur.fetchone()["cnt"]


def ban(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sh_users SET is_banned = TRUE  WHERE id = %s", (user_id,))
        conn.commit()


def unban(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sh_users SET is_banned = FALSE WHERE id = %s", (user_id,))
        conn.commit()
