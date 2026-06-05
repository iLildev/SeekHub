from .connection import get_conn


def get_score(user_id: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(amount),0) AS total FROM sh_aura WHERE to_id = %s",
                (user_id,)
            )
            return int(cur.fetchone()["total"])


def give(from_id: int, to_id: int, amount: int, note: str = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sh_aura (from_id, to_id, amount, note) VALUES (%s,%s,%s,%s)",
                (from_id, to_id, amount, note)
            )
        conn.commit()


def get_top(limit: int = 10):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.first_name, u.username,
                       COALESCE(SUM(a.amount),0) AS score
                FROM sh_users u
                LEFT JOIN sh_aura a ON a.to_id = u.id
                GROUP BY u.id, u.first_name, u.username
                ORDER BY score DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
