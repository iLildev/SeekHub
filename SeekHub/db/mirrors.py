from .connection import get_conn


def count_mirrors() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM seekhub_mirrors WHERE is_active = TRUE")
            row = cur.fetchone()
            return row["cnt"] if row else 0


def get_mirror_by_owner(owner_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM seekhub_mirrors WHERE owner_id = %s AND is_active = TRUE",
                (owner_id,)
            )
            return cur.fetchone()


def create_mirror(owner_id: int, bot_token: str, bot_username: str = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO seekhub_mirrors (owner_id, bot_token, bot_username)
                VALUES (%s, %s, %s)
                ON CONFLICT (bot_token) DO UPDATE
                    SET owner_id = EXCLUDED.owner_id,
                        bot_username = EXCLUDED.bot_username,
                        is_active = TRUE
                RETURNING *
            """, (owner_id, bot_token, bot_username))
            conn.commit()
            return cur.fetchone()


def delete_mirror(owner_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE seekhub_mirrors SET is_active = FALSE WHERE owner_id = %s",
                (owner_id,)
            )
        conn.commit()
