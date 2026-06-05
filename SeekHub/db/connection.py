import os
import psycopg2
from psycopg2.extras import RealDictCursor
from db.schema import get_schema

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(get_schema())
        conn.commit()
