from .connection import get_conn


def add_referral(referrer_id: int, referred_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO seekhub_referrals (referrer_id, referred_id)
                VALUES (%s, %s)
                ON CONFLICT (referred_id) DO NOTHING
            """, (referrer_id, referred_id))
        conn.commit()


def count_referrals(referrer_id: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) as cnt FROM seekhub_referrals WHERE referrer_id = %s",
                (referrer_id,)
            )
            row = cur.fetchone()
            return row["cnt"] if row else 0
