from .connection import get_conn


def get_all():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sh_hide_plans ORDER BY id")
            return cur.fetchall()


def get(plan_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sh_hide_plans WHERE id = %s", (plan_id,))
            return cur.fetchone()


def get_by_name(name: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sh_hide_plans WHERE LOWER(name) = LOWER(%s)", (name,))
            return cur.fetchone()


def get_active_subscription(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.*, p.name AS plan_name, p.features AS plan_features
                FROM sh_hide_subscriptions s
                JOIN sh_hide_plans p ON p.id = s.plan_id
                WHERE s.user_id = %s
                  AND s.is_active = TRUE
                  AND s.expires_at > NOW()
                ORDER BY s.expires_at DESC
                LIMIT 1
            """, (user_id,))
            return cur.fetchone()


def activate_subscription(user_id: int, plan_id: int, payment_charge_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sh_hide_subscriptions
                SET is_active = FALSE
                WHERE user_id = %s AND is_active = TRUE
            """, (user_id,))

            cur.execute("""
                INSERT INTO sh_hide_subscriptions
                    (user_id, plan_id, expires_at, payment_id)
                VALUES (
                    %s, %s,
                    NOW() + INTERVAL '30 days',
                    %s
                )
            """, (user_id, plan_id, payment_charge_id))
        conn.commit()


def record_star_payment(user_id: int, charge_id: str, stars: int, purpose: str, payload: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sh_star_payments
                    (user_id, telegram_payment_charge_id, stars_amount, purpose, payload)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (telegram_payment_charge_id) DO NOTHING
            """, (user_id, charge_id, stars, purpose, payload))
        conn.commit()


def notify_searcher(target_user_id: int, searcher_user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sh_analytics_events
                    (recipient_user_id, event_type, payload)
                VALUES (%s, 'spy_alert', %s::jsonb)
            """, (target_user_id, f'{{"searcher_id": {searcher_user_id}}}'))
        conn.commit()
