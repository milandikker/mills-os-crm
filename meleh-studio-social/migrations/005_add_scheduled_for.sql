-- Meleh Studio Social Agent -- scheduled batch publishing
--
-- Supports the weekly-batch workflow: create a week's worth of already-
-- approved content at once, each with its own scheduled_for time.
-- Status stays 'pending' (its meaning shifts from "awaiting AI-draft
-- review" to "scheduled, waiting for its time") -- no enum change
-- needed. The Telegram bot only notifies once scheduled_for arrives,
-- instead of immediately on creation.
--
-- NOTE: migrations only auto-apply to a freshly created Postgres volume
-- (see 001_create_content_queue.sql header and README.md). This
-- project's volume already exists on the VPS, so apply this by hand:
--   docker compose exec -T db psql -U meleh_social -d meleh_social \
--     < migrations/005_add_scheduled_for.sql

ALTER TABLE content_queue ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMPTZ;
UPDATE content_queue SET scheduled_for = created_at WHERE scheduled_for IS NULL;
ALTER TABLE content_queue ALTER COLUMN scheduled_for SET NOT NULL;
ALTER TABLE content_queue ALTER COLUMN scheduled_for SET DEFAULT now();

-- The Telegram bot polls WHERE scheduled_for <= now() every 15s.
CREATE INDEX IF NOT EXISTS idx_content_queue_scheduled_for ON content_queue (scheduled_for);
