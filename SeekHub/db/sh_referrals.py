from .connection import get_conn


def add(referrer_id: int, referred_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sh_referrals (referrer_id, referred_id)
                VALUES (%s,%s)
                ON CONFLICT (referred_id) DO NOTHING
            """, (referrer_id, referred_id))
        conn.commit()


def exists(referred_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM sh_referrals WHERE referred_id = %s LIMIT 1",
                (referred_id,)
            )
            return cur.fetchone() is not None


def count(referrer_id: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM sh_referrals WHERE referrer_id = %s",
                (referrer_id,)
            )
            return cur.fetchone()["cnt"]
