"""
Who is in which chat — membership tracking.
"""
from .connection import get_conn


def upsert(user_id: int, chat_id: int, status: str = "member",
           is_admin: bool = False, title: str = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tg_memberships (user_id, chat_id, status, is_admin, title, last_seen_at)
                VALUES (%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (user_id, chat_id) DO UPDATE SET
                    status       = EXCLUDED.status,
                    is_admin     = EXCLUDED.is_admin,
                    title        = COALESCE(EXCLUDED.title, tg_memberships.title),
                    last_seen_at = NOW()
            """, (user_id, chat_id, status, is_admin, title))
        conn.commit()


def bulk_upsert(rows: list[dict]):
    """
    rows: list of {user_id, chat_id, status, is_admin, title}
    Used when indexing a full member list from a group.
    """
    if not rows:
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute("""
                    INSERT INTO tg_memberships (user_id, chat_id, status, is_admin, title, last_seen_at)
                    VALUES (%s,%s,%s,%s,%s,NOW())
                    ON CONFLICT (user_id, chat_id) DO UPDATE SET
                        status       = EXCLUDED.status,
                        is_admin     = EXCLUDED.is_admin,
                        title        = COALESCE(EXCLUDED.title, tg_memberships.title),
                        last_seen_at = NOW()
                """, (r["user_id"], r["chat_id"], r.get("status","member"),
                      r.get("is_admin", False), r.get("title")))
        conn.commit()


def mark_left(user_id: int, chat_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tg_memberships SET status='left', last_seen_at=NOW() WHERE user_id=%s AND chat_id=%s",
                (user_id, chat_id)
            )
        conn.commit()


def record_interaction(from_id: int, to_id: int, chat_id: int, itype: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tg_interactions (from_user_id, to_user_id, chat_id, interaction_type, count, last_at)
                VALUES (%s,%s,%s,%s,1,NOW())
                ON CONFLICT (from_user_id, to_user_id, chat_id, interaction_type) DO UPDATE SET
                    count   = tg_interactions.count + 1,
                    last_at = NOW()
            """, (from_id, to_id, chat_id, itype))
        conn.commit()
