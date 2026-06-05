from .connection import get_conn


def get_crystals(user_id: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT crystals FROM seekhub_points WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            return row["crystals"] if row else 0


def add_crystals(user_id: int, amount: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO seekhub_points (user_id, crystals)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE
                    SET crystals = seekhub_points.crystals + EXCLUDED.crystals,
                        updated_at = NOW()
            """, (user_id, amount))
        conn.commit()


def deduct_crystals(user_id: int, amount: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT crystals FROM seekhub_points WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            if not row or row["crystals"] < amount:
                return False
            cur.execute(
                "UPDATE seekhub_points SET crystals = crystals - %s, updated_at = NOW() WHERE user_id = %s",
                (amount, user_id)
            )
        conn.commit()
        return True
