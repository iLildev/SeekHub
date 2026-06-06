from .connection import get_conn

SUBMISSION_CRYSTALS = 8


def already_submitted(chat_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM sh_group_submissions
                WHERE chat_id = %s AND status IN ('accepted', 'pending')
                LIMIT 1
            """, (chat_id,))
            return cur.fetchone() is not None


def user_submission_today(user_id: int) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS cnt FROM sh_group_submissions
                WHERE user_id = %s
                  AND submitted_at > NOW() - INTERVAL '24 hours'
                  AND status != 'rejected'
            """, (user_id,))
            return cur.fetchone()["cnt"]


def submit(user_id: int, username: str, chat_id: int = None) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if chat_id:
                cur.execute("""
                    SELECT 1 FROM sh_group_submissions
                    WHERE chat_id = %s AND status IN ('accepted', 'pending')
                    LIMIT 1
                """, (chat_id,))
                if cur.fetchone():
                    return {"status": "duplicate", "crystals": 0}

            cur.execute("""
                INSERT INTO sh_group_submissions (user_id, chat_id, username, status)
                VALUES (%s, %s, %s, 'pending')
                RETURNING id
            """, (user_id, chat_id, username.lstrip("@")))
            row = cur.fetchone()
        conn.commit()
        return {"status": "pending", "id": row["id"], "crystals": SUBMISSION_CRYSTALS}


def mark_accepted(submission_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sh_group_submissions
                SET status = 'accepted', crystals_awarded = TRUE
                WHERE id = %s
            """, (submission_id,))
        conn.commit()


def mark_rejected(submission_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sh_group_submissions SET status = 'rejected' WHERE id = %s
            """, (submission_id,))
        conn.commit()


def get_pending(limit: int = 20):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.*, u.username AS owner_username
                FROM sh_group_submissions s
                LEFT JOIN sh_users u ON u.id = s.user_id
                WHERE s.status = 'pending'
                ORDER BY s.submitted_at ASC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
