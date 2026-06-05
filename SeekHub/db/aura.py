from .connection import get_conn


def get_aura(user_id: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM seekhub_aura WHERE to_user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            return int(row["total"]) if row else 0


def add_aura(from_user_id: int, to_user_id: int, amount: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO seekhub_aura (from_user_id, to_user_id, amount)
                VALUES (%s, %s, %s)
            """, (from_user_id, to_user_id, amount))
        conn.commit()


def get_top_aura(limit: int = 10):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.first_name, u.username, COALESCE(SUM(a.amount), 0) as total
                FROM seekhub_users u
                LEFT JOIN seekhub_aura a ON a.to_user_id = u.id
                GROUP BY u.id, u.first_name, u.username
                ORDER BY total DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
