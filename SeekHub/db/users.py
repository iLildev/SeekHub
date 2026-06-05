from .connection import get_conn


def upsert_user(user_id: int, username: str, first_name: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO seekhub_users (id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                    SET username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name
            """, (user_id, username, first_name))
        conn.commit()


def get_user(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM seekhub_users WHERE id = %s", (user_id,))
            return cur.fetchone()


def count_users() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM seekhub_users WHERE is_banned = FALSE")
            row = cur.fetchone()
            return row["cnt"] if row else 0


def is_banned(user_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT is_banned FROM seekhub_users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return bool(row and row["is_banned"])
