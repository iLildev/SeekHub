import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS seekhub_users (
                    id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    joined_at TIMESTAMPTZ DEFAULT NOW(),
                    is_banned BOOLEAN DEFAULT FALSE
                );

                CREATE TABLE IF NOT EXISTS seekhub_mirrors (
                    id SERIAL PRIMARY KEY,
                    owner_id BIGINT REFERENCES seekhub_users(id),
                    bot_token TEXT UNIQUE NOT NULL,
                    bot_username TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE
                );

                CREATE TABLE IF NOT EXISTS seekhub_groups (
                    id BIGINT PRIMARY KEY,
                    title TEXT,
                    mirror_id INT REFERENCES seekhub_mirrors(id),
                    added_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS seekhub_points (
                    user_id BIGINT PRIMARY KEY REFERENCES seekhub_users(id),
                    crystals INT DEFAULT 0,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS seekhub_aura (
                    id SERIAL PRIMARY KEY,
                    from_user_id BIGINT REFERENCES seekhub_users(id),
                    to_user_id BIGINT REFERENCES seekhub_users(id),
                    amount INT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS seekhub_plans (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    price_crystals INT NOT NULL,
                    duration_days INT NOT NULL,
                    features JSONB DEFAULT '{}'::jsonb
                );

                CREATE TABLE IF NOT EXISTS seekhub_referrals (
                    id SERIAL PRIMARY KEY,
                    referrer_id BIGINT REFERENCES seekhub_users(id),
                    referred_id BIGINT REFERENCES seekhub_users(id),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(referred_id)
                );
            """)
        conn.commit()
