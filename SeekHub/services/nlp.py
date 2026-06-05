"""
services/nlp.py
===============
NLP analysis built on top of indexed messages — no external ML models needed.
Uses SQL aggregation + Python for:
  • Word frequency per user
  • Most-used reactions per user
  • Activity heatmap (hour of day)
  • Top mentioned users
  • Vocabulary richness score
"""
import re
import logging
from collections import Counter
from db.connection import get_conn

logger = logging.getLogger(__name__)

# Common stop-words (Arabic + English) to filter out
STOP_WORDS = {
    # Arabic
    "في","من","على","إلى","عن","مع","هذا","هذه","هو","هي","أن","كان","كانت",
    "لا","ما","كل","قد","أو","إذا","أنا","أنت","نحن","هم","لكن","بل","حتى",
    "فقط","وأن","وفي","وهو","وهي","وكان","ومن","وإلى","وعلى","وعن","ولا",
    # English
    "the","a","an","is","are","was","were","be","been","being","have","has",
    "had","do","does","did","will","would","could","should","may","might",
    "i","you","he","she","it","we","they","this","that","and","or","but",
    "in","on","at","to","for","of","with","by","from","not","no","so",
}


def get_word_frequency(user_id: int, limit: int = 20) -> list[tuple[str, int]]:
    """
    Top words used by a user across all indexed public messages.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT text, caption
                FROM tg_messages
                WHERE sender_id = %s
                  AND (text IS NOT NULL OR caption IS NOT NULL)
                LIMIT 5000
            """, (user_id,))
            rows = cur.fetchall()

    word_counts: Counter = Counter()
    for row in rows:
        content = (row["text"] or "") + " " + (row["caption"] or "")
        words = re.findall(r"[\w\u0600-\u06ff]{3,}", content.lower())
        for w in words:
            if w not in STOP_WORDS:
                word_counts[w] += 1

    return word_counts.most_common(limit)


def get_reaction_stats(user_id: int) -> list[dict]:
    """
    Most-used reactions by a user (based on messages in chats where reactions are indexed).
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.emoji, SUM(r.count) AS total
                FROM tg_reactions r
                JOIN tg_messages m ON m.chat_id = r.chat_id AND m.message_id = r.message_id
                WHERE m.sender_id = %s
                GROUP BY r.emoji
                ORDER BY total DESC
                LIMIT 10
            """, (user_id,))
            return [dict(row) for row in cur.fetchall()]


def get_activity_heatmap(user_id: int) -> dict[int, int]:
    """
    Message count per hour of day (0-23) — activity heatmap.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXTRACT(HOUR FROM date)::int AS hour, COUNT(*) AS cnt
                FROM tg_messages
                WHERE sender_id = %s AND date IS NOT NULL
                GROUP BY hour
                ORDER BY hour
            """, (user_id,))
            rows = cur.fetchall()

    heatmap = {i: 0 for i in range(24)}
    for row in rows:
        heatmap[row["hour"]] = row["cnt"]
    return heatmap


def get_top_mentioned(user_id: int, limit: int = 10) -> list[dict]:
    """
    Users most mentioned by this user.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    m.mentioned_username,
                    u.first_name,
                    u.id AS user_id,
                    COUNT(*) AS mention_count
                FROM tg_mentions m
                LEFT JOIN tg_users u ON u.id = m.mentioned_user_id
                WHERE m.by_user_id = %s
                GROUP BY m.mentioned_username, u.first_name, u.id
                ORDER BY mention_count DESC
                LIMIT %s
            """, (user_id, limit))
            return [dict(row) for row in cur.fetchall()]


def vocabulary_score(user_id: int) -> dict:
    """
    Vocabulary richness: unique words / total words ratio.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT text, caption FROM tg_messages
                WHERE sender_id = %s
                  AND (text IS NOT NULL OR caption IS NOT NULL)
                LIMIT 2000
            """, (user_id,))
            rows = cur.fetchall()

    all_words  = []
    for row in rows:
        content = (row["text"] or "") + " " + (row["caption"] or "")
        words = re.findall(r"[\w\u0600-\u06ff]{3,}", content.lower())
        all_words.extend([w for w in words if w not in STOP_WORDS])

    total  = len(all_words)
    unique = len(set(all_words))
    score  = round((unique / total) * 100, 1) if total > 0 else 0

    return {"total_words": total, "unique_words": unique, "richness_pct": score}


def format_heatmap(heatmap: dict[int, int]) -> str:
    """Render activity heatmap as a text bar chart."""
    if not heatmap or max(heatmap.values()) == 0:
        return "_No activity data_"

    peak = max(heatmap.values())
    bars = []
    for hour in range(24):
        count = heatmap.get(hour, 0)
        filled = int((count / peak) * 8) if peak > 0 else 0
        bar = "█" * filled + "░" * (8 - filled)
        bars.append(f"`{hour:02d}h` {bar} {count}")

    return "\n".join(bars)
