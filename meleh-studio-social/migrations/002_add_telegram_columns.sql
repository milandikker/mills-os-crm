-- Meleh Studio Social Agent -- step (d): Telegram Review Bot columns
--
-- telegram_message_id  : the Telegram message ID a draft was sent as, so
--                         the bot can edit it (remove buttons, show the
--                         outcome) after you tap Posted/Reject, and so
--                         it never sends the same draft twice.
-- telegram_reminded_at : set once a single reminder ping has gone out
--                         past review_deadline, so you get nudged but
--                         never spammed -- and nothing is auto-actioned
--                         just because time passed.
--
-- NOTE: migrations only auto-apply to a freshly created Postgres volume
-- (see 001_create_content_queue.sql header and README.md). This
-- project's volume already exists on the VPS, so apply this by hand:
--   docker compose exec -T db psql -U meleh_social -d meleh_social \
--     < migrations/002_add_telegram_columns.sql

ALTER TABLE content_queue ADD COLUMN IF NOT EXISTS telegram_message_id BIGINT;
ALTER TABLE content_queue ADD COLUMN IF NOT EXISTS telegram_reminded_at TIMESTAMPTZ;
