"""
SeekHub Central Database Schema
================================
The full schema for the SeekHub indexing system.
All data is collected from public Telegram sources only.
"""

SCHEMA = """
-- ─────────────────────────────────────────────
--  CORE: Telegram Entities
-- ─────────────────────────────────────────────

-- Every known Telegram user (from any public source)
CREATE TABLE IF NOT EXISTS tg_users (
    id              BIGINT PRIMARY KEY,          -- Telegram user ID
    first_name      TEXT,
    last_name       TEXT,
    username        TEXT,                        -- current username
    is_bot          BOOLEAN DEFAULT FALSE,
    is_premium      BOOLEAN DEFAULT FALSE,
    lang_code       TEXT,
    bio             TEXT,
    photo_id        TEXT,                        -- profile photo file_id
    is_verified     BOOLEAN DEFAULT FALSE,
    is_restricted   BOOLEAN DEFAULT FALSE,
    is_deleted      BOOLEAN DEFAULT FALSE,
    first_seen_at   TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tg_users_username ON tg_users(username);
CREATE INDEX IF NOT EXISTS idx_tg_users_last_seen ON tg_users(last_seen_at);

-- Username change history (every rename we ever catch)
CREATE TABLE IF NOT EXISTS tg_username_history (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES tg_users(id) ON DELETE CASCADE,
    username    TEXT NOT NULL,
    seen_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_username_history_user ON tg_username_history(user_id);
CREATE INDEX IF NOT EXISTS idx_username_history_username ON tg_username_history(username);

-- First/last name change history
CREATE TABLE IF NOT EXISTS tg_name_history (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES tg_users(id) ON DELETE CASCADE,
    first_name  TEXT,
    last_name   TEXT,
    seen_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_name_history_user ON tg_name_history(user_id);

-- Bio change history
CREATE TABLE IF NOT EXISTS tg_bio_history (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES tg_users(id) ON DELETE CASCADE,
    bio         TEXT,
    seen_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Profile photo history
CREATE TABLE IF NOT EXISTS tg_photo_history (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES tg_users(id) ON DELETE CASCADE,
    photo_id    TEXT NOT NULL,
    seen_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
--  CORE: Chats (groups + channels + supergroups)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_chats (
    id              BIGINT PRIMARY KEY,          -- Telegram chat ID
    type            TEXT NOT NULL,               -- 'group','supergroup','channel','gigagroup'
    title           TEXT,
    username        TEXT,                        -- public username if any
    description     TEXT,
    invite_link     TEXT,
    member_count    INT,
    is_verified     BOOLEAN DEFAULT FALSE,
    is_restricted   BOOLEAN DEFAULT FALSE,
    is_scam         BOOLEAN DEFAULT FALSE,
    is_fake         BOOLEAN DEFAULT FALSE,
    is_broadcast    BOOLEAN DEFAULT FALSE,       -- is a channel
    linked_chat_id  BIGINT,                      -- channel <-> discussion group link
    lang_code       TEXT,
    first_seen_at   TIMESTAMPTZ DEFAULT NOW(),
    last_indexed_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tg_chats_username ON tg_chats(username);
CREATE INDEX IF NOT EXISTS idx_tg_chats_type ON tg_chats(type);
CREATE INDEX IF NOT EXISTS idx_tg_chats_title ON tg_chats USING GIN (to_tsvector('english', coalesce(title, '')));

-- Chat title/description history
CREATE TABLE IF NOT EXISTS tg_chat_history (
    id          SERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL REFERENCES tg_chats(id) ON DELETE CASCADE,
    title       TEXT,
    description TEXT,
    username    TEXT,
    member_count INT,
    seen_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_history_chat ON tg_chat_history(chat_id);

-- ─────────────────────────────────────────────
--  MEMBERSHIP: Who is in which chat
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_memberships (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES tg_users(id) ON DELETE CASCADE,
    chat_id     BIGINT NOT NULL REFERENCES tg_chats(id) ON DELETE CASCADE,
    status      TEXT DEFAULT 'member',           -- member/admin/creator/left/kicked
    is_admin    BOOLEAN DEFAULT FALSE,
    title       TEXT,                            -- custom admin title
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, chat_id)
);

CREATE INDEX IF NOT EXISTS idx_memberships_user   ON tg_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_chat   ON tg_memberships(chat_id);
CREATE INDEX IF NOT EXISTS idx_memberships_status ON tg_memberships(status);

-- ─────────────────────────────────────────────
--  MESSAGES: Indexed public messages
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_messages (
    id              BIGSERIAL PRIMARY KEY,
    message_id      BIGINT NOT NULL,
    chat_id         BIGINT NOT NULL REFERENCES tg_chats(id) ON DELETE CASCADE,
    sender_id       BIGINT REFERENCES tg_users(id) ON DELETE SET NULL,
    sender_chat_id  BIGINT REFERENCES tg_chats(id) ON DELETE SET NULL, -- forwarded from channel
    text            TEXT,
    caption         TEXT,
    media_type      TEXT,                        -- photo/video/document/sticker/voice/etc.
    file_id         TEXT,
    reply_to_msg_id BIGINT,
    forward_from_id BIGINT,
    forward_date    TIMESTAMPTZ,
    views           INT DEFAULT 0,
    forwards        INT DEFAULT 0,
    reactions_count INT DEFAULT 0,
    is_pinned       BOOLEAN DEFAULT FALSE,
    date            TIMESTAMPTZ NOT NULL,
    indexed_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(chat_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_sender   ON tg_messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat     ON tg_messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_date     ON tg_messages(date);
CREATE INDEX IF NOT EXISTS idx_messages_fts      ON tg_messages USING GIN (to_tsvector('arabic', coalesce(text, '') || ' ' || coalesce(caption, '')));
CREATE INDEX IF NOT EXISTS idx_messages_fts_en   ON tg_messages USING GIN (to_tsvector('english', coalesce(text, '') || ' ' || coalesce(caption, '')));

-- ─────────────────────────────────────────────
--  REACTIONS: Per-message reaction stats
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_reactions (
    id          BIGSERIAL PRIMARY KEY,
    message_id  BIGINT NOT NULL,
    chat_id     BIGINT NOT NULL,
    emoji       TEXT NOT NULL,
    count       INT DEFAULT 1,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(message_id, chat_id, emoji),
    FOREIGN KEY (chat_id, message_id) REFERENCES tg_messages(chat_id, message_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reactions_chat_msg ON tg_reactions(chat_id, message_id);

-- ─────────────────────────────────────────────
--  USER STATS: Aggregated per (user, chat)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_user_chat_stats (
    user_id         BIGINT NOT NULL REFERENCES tg_users(id) ON DELETE CASCADE,
    chat_id         BIGINT NOT NULL REFERENCES tg_chats(id) ON DELETE CASCADE,
    message_count   INT DEFAULT 0,
    media_count     INT DEFAULT 0,
    sticker_count   INT DEFAULT 0,
    forward_count   INT DEFAULT 0,
    reply_count     INT DEFAULT 0,
    first_message_at TIMESTAMPTZ,
    last_message_at  TIMESTAMPTZ,
    PRIMARY KEY (user_id, chat_id)
);

CREATE INDEX IF NOT EXISTS idx_ucstats_user ON tg_user_chat_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_ucstats_chat ON tg_user_chat_stats(chat_id);

-- ─────────────────────────────────────────────
--  INTERACTIONS: Who replied/mentioned whom
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_interactions (
    id              BIGSERIAL PRIMARY KEY,
    from_user_id    BIGINT NOT NULL REFERENCES tg_users(id) ON DELETE CASCADE,
    to_user_id      BIGINT NOT NULL REFERENCES tg_users(id) ON DELETE CASCADE,
    chat_id         BIGINT NOT NULL REFERENCES tg_chats(id) ON DELETE CASCADE,
    interaction_type TEXT NOT NULL,             -- 'reply'/'mention'/'forward'
    count           INT DEFAULT 1,
    last_at         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_user_id, to_user_id, chat_id, interaction_type)
);

CREATE INDEX IF NOT EXISTS idx_interactions_from ON tg_interactions(from_user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_to   ON tg_interactions(to_user_id);

-- ─────────────────────────────────────────────
--  FORWARDS: Track forward chains
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_forwards (
    id                  BIGSERIAL PRIMARY KEY,
    source_chat_id      BIGINT REFERENCES tg_chats(id) ON DELETE SET NULL,
    source_message_id   BIGINT,
    source_user_id      BIGINT REFERENCES tg_users(id) ON DELETE SET NULL,
    dest_chat_id        BIGINT NOT NULL REFERENCES tg_chats(id) ON DELETE CASCADE,
    dest_message_id     BIGINT NOT NULL,
    forwarded_at        TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_forwards_source_chat ON tg_forwards(source_chat_id);
CREATE INDEX IF NOT EXISTS idx_forwards_source_user ON tg_forwards(source_user_id);

-- ─────────────────────────────────────────────
--  TRACKING: Users/chats being watched
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_tracking (
    id              SERIAL PRIMARY KEY,
    tracker_user_id BIGINT NOT NULL,            -- SeekHub user who set the track
    target_user_id  BIGINT REFERENCES tg_users(id) ON DELETE CASCADE,
    target_chat_id  BIGINT REFERENCES tg_chats(id) ON DELETE CASCADE,
    track_type      TEXT NOT NULL,              -- 'user_online','user_name','user_bio','user_photo','chat_member_count','chat_name'
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_notified_at TIMESTAMPTZ,
    CHECK (target_user_id IS NOT NULL OR target_chat_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_tracking_tracker ON tg_tracking(tracker_user_id);
CREATE INDEX IF NOT EXISTS idx_tracking_target_user ON tg_tracking(target_user_id) WHERE target_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tracking_active ON tg_tracking(is_active) WHERE is_active = TRUE;

-- ─────────────────────────────────────────────
--  ONLINE ACTIVITY: Last seen / online snapshots
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_online_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES tg_users(id) ON DELETE CASCADE,
    status      TEXT NOT NULL,                  -- 'online','recently','last_week','last_month','long_ago'
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_online_log_user ON tg_online_log(user_id);
CREATE INDEX IF NOT EXISTS idx_online_log_time ON tg_online_log(recorded_at);

-- ─────────────────────────────────────────────
--  MENTIONS: @username mentions in messages
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_mentions (
    id              BIGSERIAL PRIMARY KEY,
    mentioned_user_id BIGINT REFERENCES tg_users(id) ON DELETE SET NULL,
    mentioned_username TEXT,                   -- raw text in case user not indexed yet
    in_chat_id      BIGINT NOT NULL REFERENCES tg_chats(id) ON DELETE CASCADE,
    message_id      BIGINT NOT NULL,
    by_user_id      BIGINT REFERENCES tg_users(id) ON DELETE SET NULL,
    mentioned_at    TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mentions_mentioned_user ON tg_mentions(mentioned_user_id);
CREATE INDEX IF NOT EXISTS idx_mentions_in_chat        ON tg_mentions(in_chat_id);

-- ─────────────────────────────────────────────
--  PHONE INDEX: Phone → Telegram user mapping
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_phone_index (
    phone       TEXT PRIMARY KEY,               -- normalised E.164 e.g. +79001234567
    user_id     BIGINT NOT NULL REFERENCES tg_users(id) ON DELETE CASCADE,
    indexed_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_phone_index_user ON tg_phone_index(user_id);

-- ─────────────────────────────────────────────
--  SEARCH INDEX: Quick lookup table (denormalized)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tg_search_index (
    id          BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,                  -- 'user' / 'chat'
    entity_id   BIGINT NOT NULL,
    display     TEXT,                           -- "first last @username"
    search_vec  TSVECTOR,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_search_index_vec  ON tg_search_index USING GIN(search_vec);
CREATE INDEX IF NOT EXISTS idx_search_index_type ON tg_search_index(entity_type);

-- ─────────────────────────────────────────────
--  SEEKHUB SYSTEM: Platform users (bot owners/mirror owners)
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sh_users (
    id          BIGINT PRIMARY KEY,             -- same as tg_users.id
    username    TEXT,
    first_name  TEXT,
    joined_at   TIMESTAMPTZ DEFAULT NOW(),
    is_banned   BOOLEAN DEFAULT FALSE,
    plan_id     INT DEFAULT 1,
    plan_expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sh_mirrors (
    id              SERIAL PRIMARY KEY,
    owner_id        BIGINT NOT NULL REFERENCES sh_users(id),
    bot_token       TEXT UNIQUE NOT NULL,
    bot_id          BIGINT UNIQUE,
    bot_username    TEXT,
    display_name    TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    query_count     BIGINT DEFAULT 0,           -- total queries served
    user_count      INT DEFAULT 0,              -- users who used this mirror
    settings        JSONB DEFAULT '{}'::jsonb   -- owner-controlled toggles
);

ALTER TABLE sh_mirrors ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT '{}'::jsonb;

-- Search query log for top-queries analytics
CREATE TABLE IF NOT EXISTS sh_mirror_queries (
    id          BIGSERIAL PRIMARY KEY,
    mirror_id   INT NOT NULL REFERENCES sh_mirrors(id) ON DELETE CASCADE,
    query_text  TEXT NOT NULL,
    queried_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mirror_queries_mirror ON sh_mirror_queries(mirror_id);
CREATE INDEX IF NOT EXISTS idx_mirror_queries_time   ON sh_mirror_queries(queried_at);

CREATE INDEX IF NOT EXISTS idx_sh_mirrors_owner  ON sh_mirrors(owner_id);
CREATE INDEX IF NOT EXISTS idx_sh_mirrors_bot_id ON sh_mirrors(bot_id);

CREATE TABLE IF NOT EXISTS sh_mirror_users (
    mirror_id   INT NOT NULL REFERENCES sh_mirrors(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES sh_users(id) ON DELETE CASCADE,
    first_used  TIMESTAMPTZ DEFAULT NOW(),
    last_used   TIMESTAMPTZ DEFAULT NOW(),
    query_count INT DEFAULT 0,
    PRIMARY KEY (mirror_id, user_id)
);

CREATE TABLE IF NOT EXISTS sh_plans (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    price_crystals  INT NOT NULL DEFAULT 0,
    duration_days   INT NOT NULL DEFAULT 0,     -- 0 = forever (free)
    daily_queries   INT NOT NULL DEFAULT 10,    -- queries per day for mirror users
    max_mirrors     INT NOT NULL DEFAULT 1,
    max_tracking    INT NOT NULL DEFAULT 0,
    can_export      BOOLEAN DEFAULT FALSE,
    can_track_online BOOLEAN DEFAULT FALSE,
    features        JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS sh_crystals (
    user_id     BIGINT PRIMARY KEY REFERENCES sh_users(id),
    balance     INT DEFAULT 0,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sh_crystal_log (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES sh_users(id),
    amount      INT NOT NULL,                   -- positive = earned, negative = spent
    reason      TEXT NOT NULL,                  -- 'referral'/'purchase'/'used_query'/etc.
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sh_aura (
    id          SERIAL PRIMARY KEY,
    from_id     BIGINT NOT NULL REFERENCES sh_users(id),
    to_id       BIGINT NOT NULL REFERENCES sh_users(id),
    amount      INT NOT NULL,
    note        TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sh_referrals (
    referrer_id BIGINT NOT NULL REFERENCES sh_users(id),
    referred_id BIGINT PRIMARY KEY REFERENCES sh_users(id),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
--  DATA COLLECTION: Source tracking
-- ─────────────────────────────────────────────

-- Which bots/userbots are collecting data and from which chats
CREATE TABLE IF NOT EXISTS sh_collectors (
    id          SERIAL PRIMARY KEY,
    type        TEXT NOT NULL,                  -- 'bot' / 'userbot'
    identifier  TEXT NOT NULL,                  -- bot username or phone hash
    is_active   BOOLEAN DEFAULT TRUE,
    added_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sh_collector_chats (
    collector_id    INT NOT NULL REFERENCES sh_collectors(id),
    chat_id         BIGINT NOT NULL REFERENCES tg_chats(id),
    joined_at       TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE,
    last_indexed_at TIMESTAMPTZ,
    messages_indexed BIGINT DEFAULT 0,
    PRIMARY KEY (collector_id, chat_id)
);

-- ─────────────────────────────────────────────
--  SEED DATA: Default plans
-- ─────────────────────────────────────────────

INSERT INTO sh_plans (id, name, price_crystals, duration_days, daily_queries, max_mirrors, max_tracking, can_export, can_track_online, features)
VALUES
    (1, 'Free',    0,    0,  5,   1, 0,  FALSE, FALSE, '{"badge": "⚪"}'::jsonb),
    (2, 'Starter', 200,  30, 20,  1, 2,  FALSE, FALSE, '{"badge": "🔹"}'::jsonb),
    (3, 'Pro',     500,  30, 100, 3, 10, TRUE,  FALSE, '{"badge": "🔷"}'::jsonb),
    (4, 'Elite',   1500, 30, 999, 10,50, TRUE,  TRUE,  '{"badge": "💠"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────────
--  PRIVACY: Hide plans & subscriptions
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sh_hide_plans (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    price_stars   INT  NOT NULL,
    duration_days INT  NOT NULL DEFAULT 30,
    features      JSONB DEFAULT '{}'::jsonb
);

INSERT INTO sh_hide_plans (id, name, price_stars, duration_days, features) VALUES
    (1, 'Ghost',  250, 30, '{"hide_username": true, "hide_all": false, "see_searchers": false, "badge": "👻", "price_display": "$4.99"}'::jsonb),
    (2, 'Shadow', 400, 30, '{"hide_username": true, "hide_all": true,  "see_searchers": false, "badge": "🌑", "price_display": "$7.99"}'::jsonb),
    (3, 'Spy',    750, 30, '{"hide_username": true, "hide_all": true,  "see_searchers": true,  "badge": "🕵️", "price_display": "$14.99"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS sh_hide_subscriptions (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES sh_users(id),
    plan_id     INT    NOT NULL REFERENCES sh_hide_plans(id),
    starts_at   TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    payment_id  TEXT
);

CREATE INDEX IF NOT EXISTS idx_hide_subs_user   ON sh_hide_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_hide_subs_active ON sh_hide_subscriptions(is_active, expires_at);

-- ─────────────────────────────────────────────
--  PAYMENTS: Telegram Stars transactions
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sh_star_payments (
    id                           SERIAL PRIMARY KEY,
    user_id                      BIGINT NOT NULL REFERENCES sh_users(id),
    telegram_payment_charge_id   TEXT UNIQUE,
    stars_amount                 INT  NOT NULL,
    purpose                      TEXT NOT NULL,
    payload                      TEXT,
    created_at                   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_star_payments_user ON sh_star_payments(user_id);

-- ─────────────────────────────────────────────
--  SUBMISSIONS: User-submitted group links
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sh_group_submissions (
    id               SERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL REFERENCES sh_users(id),
    chat_id          BIGINT,
    username         TEXT,
    submitted_at     TIMESTAMPTZ DEFAULT NOW(),
    status           TEXT DEFAULT 'pending',
    crystals_awarded BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_group_submissions_user ON sh_group_submissions(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_group_submissions_chat
    ON sh_group_submissions(chat_id) WHERE chat_id IS NOT NULL AND status != 'rejected';

-- ─────────────────────────────────────────────
--  CHANNEL ANALYTICS: Channels tracked for owners
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sh_channel_analytics (
    channel_id    BIGINT PRIMARY KEY REFERENCES tg_chats(id) ON DELETE CASCADE,
    owner_user_id BIGINT NOT NULL REFERENCES sh_users(id),
    notifications JSONB  DEFAULT '{"member_join": true, "member_leave": true}'::jsonb,
    added_at      TIMESTAMPTZ DEFAULT NOW(),
    is_active     BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_channel_analytics_owner ON sh_channel_analytics(owner_user_id);

-- ─────────────────────────────────────────────
--  ANALYTICS EVENTS: Notification delivery queue
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sh_analytics_events (
    id                BIGSERIAL PRIMARY KEY,
    recipient_user_id BIGINT NOT NULL,
    event_type        TEXT   NOT NULL,
    payload           JSONB  DEFAULT '{}'::jsonb,
    delivered         BOOLEAN DEFAULT FALSE,
    delivered_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_pending
    ON sh_analytics_events(delivered, created_at) WHERE delivered = FALSE;
"""


def get_schema() -> str:
    return SCHEMA
