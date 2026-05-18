"""Schema migrations. Each entry is applied once in order; persisted version in KV."""

MIGRATIONS = [
    {
        "id": 1,
        "name": "001_init",
        "sql": """
            CREATE TABLE IF NOT EXISTS dnd_campaigns (
                id BIGSERIAL PRIMARY KEY,
                discord_srv_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                party_name TEXT,
                system TEXT NOT NULL DEFAULT 'D&D 5e',
                description TEXT,
                timezone TEXT NOT NULL DEFAULT 'UTC',
                owner_user_id BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','paused','archived')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_dnd_camp_srv_status
                ON dnd_campaigns (discord_srv_id, status);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_dnd_camp_srv_name
                ON dnd_campaigns (discord_srv_id, LOWER(name))
                WHERE status <> 'archived';

            CREATE TABLE IF NOT EXISTS dnd_campaign_settings (
                campaign_id BIGINT PRIMARY KEY
                    REFERENCES dnd_campaigns(id) ON DELETE CASCADE,
                default_day_of_week SMALLINT
                    CHECK (default_day_of_week BETWEEN 0 AND 6),
                default_time_local TEXT,
                announce_channel_id BIGINT,
                recap_channel_id BIGINT,
                reminder_channel_id BIGINT,
                dm_role_id BIGINT,
                player_role_id BIGINT,
                reminder_offsets_minutes INT[] NOT NULL DEFAULT '{1440,120,15}',
                rsvp_required BOOLEAN NOT NULL DEFAULT FALSE,
                maybe_allowed BOOLEAN NOT NULL DEFAULT TRUE,
                alternate_times_allowed BOOLEAN NOT NULL DEFAULT FALSE,
                recap_draft_first BOOLEAN NOT NULL DEFAULT TRUE,
                quest_log_public BOOLEAN NOT NULL DEFAULT TRUE,
                npc_default_visibility TEXT NOT NULL DEFAULT 'public'
                    CHECK (npc_default_visibility IN ('public','partial','dm_only')),
                ping_on_reminders BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS dnd_sessions (
                id BIGSERIAL PRIMARY KEY,
                campaign_id BIGINT NOT NULL
                    REFERENCES dnd_campaigns(id) ON DELETE CASCADE,
                discord_srv_id BIGINT NOT NULL,
                session_number INT,
                title TEXT,
                notes_for_players TEXT,
                starts_at TIMESTAMPTZ NOT NULL,
                duration_minutes INT NOT NULL DEFAULT 240,
                status TEXT NOT NULL DEFAULT 'scheduled'
                    CHECK (status IN ('scheduled','cancelled','completed')),
                announce_channel_id BIGINT,
                announce_message_id BIGINT,
                series_id BIGINT REFERENCES dnd_sessions(id) ON DELETE SET NULL,
                recurrence_rule JSONB,
                next_reminder_due_at TIMESTAMPTZ,
                reminder_offsets_sent INT[] NOT NULL DEFAULT '{}',
                created_by_user_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_dnd_sess_camp_time
                ON dnd_sessions (campaign_id, starts_at);
            CREATE INDEX IF NOT EXISTS idx_dnd_sess_srv_upcoming
                ON dnd_sessions (discord_srv_id, starts_at)
                WHERE status = 'scheduled';
            CREATE INDEX IF NOT EXISTS idx_dnd_sess_reminder_due
                ON dnd_sessions (next_reminder_due_at)
                WHERE next_reminder_due_at IS NOT NULL AND status = 'scheduled';
            CREATE INDEX IF NOT EXISTS idx_dnd_sess_series
                ON dnd_sessions (series_id)
                WHERE series_id IS NOT NULL;

            CREATE TABLE IF NOT EXISTS dnd_session_rsvps (
                session_id BIGINT NOT NULL
                    REFERENCES dnd_sessions(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN ('attending','maybe','unavailable')),
                note TEXT,
                responded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (session_id, user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_dnd_rsvp_user
                ON dnd_session_rsvps (user_id);

            CREATE TABLE IF NOT EXISTS dnd_session_attendance (
                session_id BIGINT NOT NULL
                    REFERENCES dnd_sessions(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                attended BOOLEAN NOT NULL,
                note TEXT,
                logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (session_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS dnd_recaps (
                id BIGSERIAL PRIMARY KEY,
                session_id BIGINT NOT NULL UNIQUE
                    REFERENCES dnd_sessions(id) ON DELETE CASCADE,
                campaign_id BIGINT NOT NULL
                    REFERENCES dnd_campaigns(id) ON DELETE CASCADE,
                discord_srv_id BIGINT NOT NULL,
                title TEXT,
                summary TEXT NOT NULL,
                highlights TEXT,
                loot TEXT,
                cliffhanger TEXT,
                dm_notes TEXT,
                status TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','posted')),
                posted_channel_id BIGINT,
                posted_message_id BIGINT,
                author_user_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                posted_at TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS idx_dnd_recap_camp_posted
                ON dnd_recaps (campaign_id, posted_at DESC)
                WHERE status = 'posted';

            CREATE TABLE IF NOT EXISTS dnd_quests (
                id BIGSERIAL PRIMARY KEY,
                campaign_id BIGINT NOT NULL
                    REFERENCES dnd_campaigns(id) ON DELETE CASCADE,
                discord_srv_id BIGINT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','completed','failed','abandoned')),
                visibility TEXT NOT NULL DEFAULT 'public'
                    CHECK (visibility IN ('public','dm_only')),
                added_by_user_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_dnd_quest_camp_status
                ON dnd_quests (campaign_id, status);

            CREATE TABLE IF NOT EXISTS dnd_quest_updates (
                id BIGSERIAL PRIMARY KEY,
                quest_id BIGINT NOT NULL
                    REFERENCES dnd_quests(id) ON DELETE CASCADE,
                update_text TEXT NOT NULL,
                author_user_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_dnd_quest_updt_quest
                ON dnd_quest_updates (quest_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS dnd_npcs (
                id BIGSERIAL PRIMARY KEY,
                campaign_id BIGINT NOT NULL
                    REFERENCES dnd_campaigns(id) ON DELETE CASCADE,
                discord_srv_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                role TEXT,
                location TEXT,
                public_notes TEXT,
                secret_notes TEXT,
                visibility TEXT NOT NULL DEFAULT 'public'
                    CHECK (visibility IN ('public','partial','dm_only')),
                added_by_user_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_dnd_npc_camp
                ON dnd_npcs (campaign_id, visibility);

            CREATE TABLE IF NOT EXISTS dnd_party_members (
                campaign_id BIGINT NOT NULL
                    REFERENCES dnd_campaigns(id) ON DELETE CASCADE,
                user_id BIGINT NOT NULL,
                character_name TEXT,
                character_class TEXT,
                character_level INT,
                joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                PRIMARY KEY (campaign_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS dnd_dm_notes (
                id BIGSERIAL PRIMARY KEY,
                campaign_id BIGINT NOT NULL
                    REFERENCES dnd_campaigns(id) ON DELETE CASCADE,
                discord_srv_id BIGINT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                author_user_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_dnd_notes_camp
                ON dnd_dm_notes (campaign_id, updated_at DESC);
        """,
    },
]
