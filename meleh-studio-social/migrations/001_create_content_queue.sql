-- Meleh Studio Social Agent -- initial schema
--
-- content_queue is the shared table connecting all three pieces of this
-- system:
--   1. Content Agent   writes new rows here (status starts 'pending')
--   2. Telegram Bot    reads 'pending' rows to send for review, and
--                      updates status based on your Approve/Edit/Reject
--   3. Poster Agent    reads 'approved' rows, publishes them, marks 'posted'
--
-- Status lifecycle:
--   pending   -> just created by Content Agent, waiting on Telegram review
--   approved  -> you approved it, OR the 4-hour review window expired
--               (auto-approve fallback, so nothing gets stuck on you)
--   rejected  -> you rejected it (terminal -- Poster Agent ignores it)
--   posted    -> Poster Agent successfully published it (terminal)
--   failed    -> Poster Agent tried to publish and hit an error

CREATE TABLE IF NOT EXISTS content_queue (
    id              BIGSERIAL PRIMARY KEY,

    -- What it is and where it's going
    platform        TEXT NOT NULL
                        CHECK (platform IN ('instagram', 'tiktok')),
    content_type    TEXT NOT NULL
                        CHECK (content_type IN ('reel', 'static', 'tiktok_video')),

    -- Media for the post. For now these are always placeholders --
    -- see content_agent/products.py and the TODO stubs in poster_agent/.
    -- media_url  : path/URL to a dummy image (used for 'static' and as a
    --              stand-in thumbnail for 'reel'/'tiktok_video')
    -- media_note : plain-text stand-in for formats we can't fake with a
    --              static image yet, e.g. "[video would go here]"
    media_url       TEXT,
    media_note      TEXT,

    caption         TEXT NOT NULL,

    -- Review / publish lifecycle
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected', 'posted', 'failed')),
    review_deadline TIMESTAMPTZ NOT NULL,   -- created_at + 4h; past this, bot auto-approves
    posted_at       TIMESTAMPTZ,

    -- Poster Agent error/retry bookkeeping (built in step b)
    retry_count     INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Poster Agent polls WHERE status='approved'; Telegram bot polls
-- WHERE status='pending' AND review_deadline < now(). Both are frequent,
-- so index the columns they filter on.
CREATE INDEX IF NOT EXISTS idx_content_queue_status ON content_queue (status);
CREATE INDEX IF NOT EXISTS idx_content_queue_review_deadline ON content_queue (review_deadline);

-- Keep updated_at accurate on every UPDATE (handy for debugging queue state).
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_content_queue_updated_at ON content_queue;
CREATE TRIGGER trg_content_queue_updated_at
    BEFORE UPDATE ON content_queue
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
