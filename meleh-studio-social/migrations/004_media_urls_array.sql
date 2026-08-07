-- Meleh Studio Social Agent -- multi-photo/carousel support
--
-- Replaces the single `media_url` column with `media_urls TEXT[]`, so a
-- post can carry more than one photo (a carousel) instead of exactly
-- one. A single-photo or single-video post just has a one-element
-- array; a text-only post (media_note only) has an empty array.
--
-- NOTE: migrations only auto-apply to a freshly created Postgres volume
-- (see 001_create_content_queue.sql header and README.md). This
-- project's volume already exists on the VPS, so apply this by hand:
--   docker compose exec -T db psql -U meleh_social -d meleh_social \
--     < migrations/004_media_urls_array.sql

ALTER TABLE content_queue ADD COLUMN IF NOT EXISTS media_urls TEXT[] NOT NULL DEFAULT '{}';

UPDATE content_queue
SET media_urls = ARRAY[media_url]
WHERE media_url IS NOT NULL AND media_url <> '' AND media_urls = '{}';

ALTER TABLE content_queue DROP COLUMN IF EXISTS media_url;
