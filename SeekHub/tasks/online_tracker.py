"""
tasks/online_tracker.py
========================
Periodic job — runs every 5 minutes via PTB job_queue.
For every active online-tracking entry in tg_tracking,
fetches the user's current status via MTProto and:
  • Logs it to tg_online_log
  • Notifies the tracker if status changed to 'online'
"""
import logging
from datetime import datetime, timezone

from db.connection import get_conn
from db.tg_users import log_online

logger = logging.getLogger(__name__)


async def run_online_tracker(context):
    """PTB job callback — context.bot_data['userbot_client'] must be set."""
    userbot = context.bot_data.get("userbot_client")
    if not userbot or not userbot.is_connected:
        return

    # Load active online-tracking entries
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.tracker_user_id, t.target_user_id
                FROM tg_tracking t
                WHERE t.is_active = TRUE
                  AND t.track_type = 'user_online'
                  AND t.target_user_id IS NOT NULL
            """)
            entries = cur.fetchall()

    if not entries:
        return

    for entry in entries:
        target_id = entry["target_user_id"]
        tracker_id = entry["tracker_user_id"]
        entry_id   = entry["id"]

        try:
            from pyrogram.enums import UserStatus
            user = await userbot.get_users(target_id)
            if not user or not user.status:
                continue

            status_map = {
                UserStatus.ONLINE:     "online",
                UserStatus.RECENTLY:   "recently",
                UserStatus.LAST_WEEK:  "last_week",
                UserStatus.LAST_MONTH: "last_month",
                UserStatus.LONG_AGO:   "long_ago",
                UserStatus.OFFLINE:    "recently",
            }
            current_status = status_map.get(user.status, "unknown")
            log_online(target_id, current_status)

            # Notify if online
            if current_status == "online":
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        # Only notify if last notification was > 30 min ago
                        cur.execute("""
                            SELECT last_notified_at FROM tg_tracking
                            WHERE id = %s
                        """, (entry_id,))
                        row = cur.fetchone()
                        last_notified = row["last_notified_at"] if row else None

                now = datetime.now(timezone.utc)
                should_notify = (
                    last_notified is None or
                    (now - last_notified).total_seconds() > 1800
                )

                if should_notify:
                    name = user.first_name or str(target_id)
                    uname = f" (@{user.username})" if user.username else ""
                    try:
                        await context.bot.send_message(
                            chat_id=tracker_id,
                            text=f"🟢 *{name}*{uname} is online now\\!",
                            parse_mode="MarkdownV2",
                        )
                    except Exception:
                        pass

                    with get_conn() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "UPDATE tg_tracking SET last_notified_at = NOW() WHERE id = %s",
                                (entry_id,)
                            )
                        conn.commit()

        except Exception as e:
            logger.debug("online tracker error for user %s: %s", target_id, e)


async def run_name_tracker(context):
    """
    Runs every hour — checks if tracked users changed name/username/bio.
    Notifies the tracker if a change is detected.
    """
    userbot = context.bot_data.get("userbot_client")
    if not userbot or not userbot.is_connected:
        return

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.tracker_user_id, t.target_user_id, t.track_type
                FROM tg_tracking t
                WHERE t.is_active = TRUE
                  AND t.track_type IN ('user_name', 'user_bio', 'user_photo')
                  AND t.target_user_id IS NOT NULL
            """)
            entries = cur.fetchall()

    for entry in entries:
        target_id  = entry["target_user_id"]
        tracker_id = entry["tracker_user_id"]
        track_type = entry["track_type"]

        try:
            from userbot.scraper import index_user_profile
            result = await index_user_profile(userbot, target_id)
            if not result:
                continue

            user = result["user"]

            # Check what changed by looking at history tables
            with get_conn() as conn:
                with conn.cursor() as cur:
                    if track_type == "user_name":
                        cur.execute("""
                            SELECT first_name, last_name FROM tg_name_history
                            WHERE user_id = %s ORDER BY seen_at DESC LIMIT 2
                        """, (target_id,))
                        rows = cur.fetchall()
                        if len(rows) >= 2 and (
                            rows[0]["first_name"] != rows[1]["first_name"] or
                            rows[0]["last_name"]  != rows[1]["last_name"]
                        ):
                            old = f"{rows[1]['first_name'] or ''} {rows[1]['last_name'] or ''}".strip()
                            new = f"{rows[0]['first_name'] or ''} {rows[0]['last_name'] or ''}".strip()
                            await context.bot.send_message(
                                chat_id=tracker_id,
                                text=f"✏️ Name change detected\\!\n`{old}` → `{new}`",
                                parse_mode="MarkdownV2",
                            )

                    elif track_type == "user_bio":
                        cur.execute("""
                            SELECT bio FROM tg_bio_history
                            WHERE user_id = %s ORDER BY seen_at DESC LIMIT 2
                        """, (target_id,))
                        rows = cur.fetchall()
                        if len(rows) >= 2 and rows[0]["bio"] != rows[1]["bio"]:
                            await context.bot.send_message(
                                chat_id=tracker_id,
                                text=f"📋 Bio changed\\!\nNew: `{rows[0]['bio'] or 'empty'}`",
                                parse_mode="MarkdownV2",
                            )

        except Exception as e:
            logger.debug("name_tracker error for %s: %s", target_id, e)
