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


def track_mirror_user(mirror_id: int, user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
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


def count() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM sh_mirrors WHERE is_active = TRUE")
            return cur.fetchone()["cnt"]
