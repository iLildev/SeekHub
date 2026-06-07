from .connection import get_conn


def give(from_id: int, to_id: int, value: int):
    """Set or update a vote (+1 or -1). One vote per (from_id, to_id) pair."""
    if value not in (1, -1):
        raise ValueError("Aura value must be +1 or -1")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sh_aura (from_id, to_id, amount)
                VALUES (%s, %s, %s)
                ON CONFLICT (from_id, to_id)
                DO UPDATE SET amount = EXCLUDED.amount, created_at = NOW()
            """, (from_id, to_id, value))
        conn.commit()


def remove(from_id: int, to_id: int):
    """Remove a previously cast vote."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM sh_aura WHERE from_id = %s AND to_id = %s",
                (from_id, to_id)
            )
        conn.commit()


def get_vote(from_id: int, to_id: int) -> int | None:
    """Return the current vote (+1, -1) or None if no vote exists."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT amount FROM sh_aura WHERE from_id = %s AND to_id = %s",
                (from_id, to_id)
            )
            row = cur.fetchone()
            return row["amount"] if row else None


def get_score(user_id: int) -> int:
    """Net aura score (positive + negative combined)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM sh_aura WHERE to_id = %s",
                (user_id,)
            )
            return int(cur.fetchone()["total"])


def get_breakdown(user_id: int) -> dict:
    """Return {positive: N, negative: N} counts."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE amount =  1) AS positive,
                    COUNT(*) FILTER (WHERE amount = -1) AS negative
                FROM sh_aura WHERE to_id = %s
            """, (user_id,))
            row = cur.fetchone()
            return {"positive": int(row["positive"]), "negative": int(row["negative"])}


def get_top(limit: int = 10):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.first_name, u.username,
                       COALESCE(SUM(a.amount), 0) AS score
                FROM sh_users u
                LEFT JOIN sh_aura a ON a.to_id = u.id
                GROUP BY u.id, u.first_name, u.username
                ORDER BY score DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
