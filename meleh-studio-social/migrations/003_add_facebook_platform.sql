-- Meleh Studio Social Agent -- add Facebook as a platform option
--
-- Facebook posts (Reels/static) publish through the same Meta Graph API
-- as Instagram (see poster_agent/publishers/meta.py), just to the Page
-- instead of the IG Business account -- no new content_type needed.
--
-- NOTE: migrations only auto-apply to a freshly created Postgres volume
-- (see 001_create_content_queue.sql header and README.md). This
-- project's volume already exists on the VPS, so apply this by hand:
--   docker compose exec -T db psql -U meleh_social -d meleh_social \
--     < migrations/003_add_facebook_platform.sql

ALTER TABLE content_queue DROP CONSTRAINT IF EXISTS content_queue_platform_check;
ALTER TABLE content_queue ADD CONSTRAINT content_queue_platform_check
    CHECK (platform IN ('instagram', 'tiktok', 'facebook'));
