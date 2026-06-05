from .connection import get_conn


def count_groups() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM seekhub_groups")
            row = cur.fetchone()
            return row["cnt"] if row else 0


def add_group(group_id: int, title: str, mirror_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO seekhub_groups (id, title, mirror_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title
            """, (group_id, title, mirror_id))
        conn.commit()
