from .connection import get_conn


def get_balance(user_id: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM sh_crystals WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            return row["balance"] if row else 0


def add(user_id: int, amount: int, reason: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sh_crystals (user_id, balance)
                VALUES (%s,%s)
                ON CONFLICT (user_id) DO UPDATE SET
                    balance    = sh_crystals.balance + EXCLUDED.balance,
                    updated_at = NOW()
            """, (user_id, amount))
            cur.execute(
                "INSERT INTO sh_crystal_log (user_id, amount, reason) VALUES (%s,%s,%s)",
                (user_id, amount, reason)
            )
        conn.commit()


def deduct(user_id: int, amount: int, reason: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM sh_crystals WHERE user_id = %s FOR UPDATE", (user_id,))
            row = cur.fetchone()
            if not row or row["balance"] < amount:
                return False
            cur.execute(
                "UPDATE sh_crystals SET balance = balance - %s, updated_at = NOW() WHERE user_id = %s",
                (amount, user_id)
            )
            cur.execute(
                "INSERT INTO sh_crystal_log (user_id, amount, reason) VALUES (%s,%s,%s)",
                (user_id, -amount, reason)
            )
        conn.commit()
        return True


def get_log(user_id: int, limit: int = 20):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT amount, reason, created_at FROM sh_crystal_log WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit)
            )
            return cur.fetchall()
