from .connection import get_conn


def register_channel(channel_id: int, owner_user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sh_channel_analytics (channel_id, owner_user_id)
                VALUES (%s, %s)
                ON CONFLICT (channel_id) DO UPDATE SET
                    owner_user_id = EXCLUDED.owner_user_id,
                    is_active     = TRUE
            """, (channel_id, owner_user_id))
        conn.commit()


def deactivate_channel(channel_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sh_channel_analytics SET is_active = FALSE WHERE channel_id = %s
            """, (channel_id,))
        conn.commit()


def get_owner(channel_id: int) -> int | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT owner_user_id FROM sh_channel_analytics
                WHERE channel_id = %s AND is_active = TRUE
            """, (channel_id,))
            row = cur.fetchone()
            return row["owner_user_id"] if row else None


def get_all_active():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ca.*, c.title, c.username
                FROM sh_channel_analytics ca
                LEFT JOIN tg_chats c ON c.id = ca.channel_id
                WHERE ca.is_active = TRUE
            """)
            return cur.fetchall()


def queue_event(recipient_user_id: int, event_type: str, payload: dict):
    import json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sh_analytics_events (recipient_user_id, event_type, payload)
                VALUES (%s, %s, %s::jsonb)
            """, (recipient_user_id, event_type, json.dumps(payload)))
        conn.commit()


def pop_pending_events(limit: int = 50):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sh_analytics_events
                SET delivered = TRUE, delivered_at = NOW()
                WHERE id IN (
                    SELECT id FROM sh_analytics_events
                    WHERE delivered = FALSE
                    ORDER BY created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING *
            """, (limit,))
            rows = cur.fetchall()
        conn.commit()
        return rows
