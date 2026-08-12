-- Meleh Studio Social Agent -- step (e): record the real published post ID
--
-- NULL until the Poster Agent actually publishes a row for real (or for
-- anything published by the old stub, which never had a real ID).
--
-- NOTE: migrations only auto-apply to a freshly created Postgres volume
-- (see 001_create_content_queue.sql header and README.md). This
-- project's volume already exists on the VPS, so apply this by hand:
--   docker compose exec -T db psql -U meleh_social -d meleh_social \
--     < migrations/006_add_platform_post_id.sql

ALTER TABLE content_queue ADD COLUMN IF NOT EXISTS platform_post_id TEXT;
