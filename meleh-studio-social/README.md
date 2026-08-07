# Meleh Studio Social Agent

A social media content-creation and posting system for Meleh Studio
(melehstudio.com), built as two agents connected by a shared Postgres
queue, with a Telegram bot as the human-review step in between.

This project is **fully independent**: its own git history (lives in this
repo on its own branch/folder), its own `.env`, its own Docker Compose
stack, its own dedicated Postgres instance. It does not read from, write
to, or assume the existence of Jarvis or any other system on the VPS. It
can be wired into Jarvis later via a clean API, but runs completely
standalone until then.

## Architecture

```
Content Agent (daily)  --writes-->  content_queue (Postgres)  <--reads--  Poster Agent (hourly)
                                          ^      |
                                          |      v
                                     Telegram Review Bot
                                (Approve / Edit / Reject, or
                                 auto-approve after 4h silence)
```

- **Content Agent** -- generates draft posts on a schedule. Decides
  platform + format, writes a placeholder-media row with a brand-voice
  caption, status `pending`.
- **Poster Agent** -- runs hourly, publishes rows with status `approved`
  (currently stubbed -- logs what it *would* post), marks them `posted`,
  handles errors/retries.
- **Telegram Review Bot** -- sends each `pending` draft to you for
  Approve/Edit/Reject. If you don't respond within 4 hours, it
  auto-approves so the queue keeps moving without you.

## Directory layout

```
meleh-studio-social/
  docker-compose.yml     own Postgres service (this project only)
  .env.example            copy to .env and fill in
  migrations/              SQL schema (applied automatically on first `up`)
  shared/                  db.py -- connection helper used by all agents
  scripts/                 one-off utility/verification scripts
  Dockerfile               shared image; each service just runs a
                           different module (see docker-compose.yml)
  content_agent/           [step c -- not built yet]
  poster_agent/            polls for 'approved' rows, stub-publishes,
                           marks 'posted', retries on failure (step b)
  telegram_bot/             [step d -- not built yet]
  BRAND_VOICE.md            [step c -- brand voice guide, editable by you]
```

## Status: step (a) complete -- queue schema + migration

The `content_queue` table (see `migrations/001_create_content_queue.sql`)
is the single source of truth both agents and the Telegram bot read/write.

| column          | type        | notes                                             |
|-----------------|-------------|----------------------------------------------------|
| id              | bigserial   | primary key                                       |
| platform        | text        | `instagram` \| `tiktok`                           |
| content_type    | text        | `reel` \| `static` \| `tiktok_video`               |
| media_url       | text        | path/URL to placeholder image (nullable)          |
| media_note      | text        | e.g. `"[video would go here]"` (nullable)         |
| caption         | text        | brand-voice caption                               |
| status          | text        | `pending` \| `approved` \| `rejected` \| `posted` \| `failed` |
| review_deadline | timestamptz | created_at + 4h; past this, bot auto-approves     |
| posted_at       | timestamptz | set when Poster Agent successfully publishes      |
| retry_count     | integer     | Poster Agent error/retry bookkeeping (step b)     |
| last_error      | text        | most recent publish error, if any                 |
| created_at      | timestamptz | default now()                                     |
| updated_at      | timestamptz | auto-updated on every row change (trigger)        |

### Try it

```sh
cd meleh-studio-social
cp .env.example .env
# edit .env: set a real POSTGRES_PASSWORD at minimum

docker compose up -d
docker compose logs db   # confirm it started cleanly and ran the migration
```

Verify the schema landed correctly:

```sh
docker compose exec db psql -U meleh_social -d meleh_social -c "\d content_queue"
```

Or, from a Python virtualenv (this also proves `shared/db.py` works, which
every later agent depends on):

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# uncomment the `ports:` mapping in docker-compose.yml first, or run this
# script inside a container on meleh_social_net -- see comment in that file
python scripts/verify_schema.py
```

Expect to see all the columns above listed, and `Row count: 0`.

**Note on future schema changes:** the `migrations/*.sql` files only
auto-run the first time the Postgres volume is created (empty data dir).
If we add a `002_*.sql` file later against a volume that already exists,
it won't run automatically -- apply it by hand with
`docker compose exec -T db psql -U ... -d ... < migrations/002_....sql`.
This project's schema is fully specified up front, so we don't expect to
need this, but it's documented in case a later step calls for a tweak.

## Status: step (b) complete -- Poster Agent

`poster_agent/main.py` polls for `status = 'approved'` rows and, for each
one, calls a stub publisher (`poster_agent/publishers/meta.py` for
Instagram, `tiktok.py` for TikTok) that just logs what it *would* post.

Error handling / retries:
- Publish succeeds -> row marked `posted`, `posted_at` set.
- Publish raises -> `last_error` recorded, `retry_count` incremented,
  and the row goes back to `approved` so the *next* hourly run retries
  it -- up to `POSTER_MAX_RETRIES` (default 3) attempts, after which it's
  left `failed` for good (the agent stops picking it up; a human can
  requeue it by hand later if needed).
- `FOR UPDATE SKIP LOCKED` on the fetch query means two overlapping runs
  would split the work instead of double-publishing the same row.

Run modes: `python -m poster_agent.main` loops forever (one pass every
`POSTER_INTERVAL_SECONDS`, default 3600s); `python -m poster_agent.main
--once` runs a single pass and exits -- that's what docker-compose isn't
using yet (the service runs the loop), but it's the easiest way to test
by hand.

### Try it

```sh
cd meleh-studio-social
docker compose up -d --build   # now also builds & starts poster_agent

# insert a fake approved row to see it get picked up
docker compose exec db psql -U meleh_social -d meleh_social -c "
INSERT INTO content_queue (platform, content_type, media_url, caption, status, review_deadline)
VALUES ('instagram', 'static', '/media/placeholder.jpg', 'Test caption', 'approved', now() + interval '4 hours');
"

docker compose logs -f poster_agent
```

Within one interval (or restart the container to trigger an immediate
pass: `docker compose restart poster_agent`) you should see a log line
like `[meta stub] Would publish static to Instagram | ...` followed by
`id=1 -> posted`. Confirm in the DB:

```sh
docker compose exec db psql -U meleh_social -d meleh_social -c \
  "SELECT id, status, posted_at FROM content_queue;"
```

I verified this exact flow locally before pushing: happy-path publish
marks a row `posted`; a forced failure correctly cycles a row through
`approved -> retry 1 -> retry 2 -> failed` and then the agent stops
touching it.

## Status: step (c) v1 complete -- Content Agent (manual dashboard)

Meta/TikTok API approval is pending, so nothing can auto-publish for
real yet. Rather than build the originally-planned automated daily
generator first, step (c) v1 is a small web dashboard
(`content_agent/app.py`, Flask) so posting can start now, by hand:

- Write a caption, upload media (or paste a URL), save as a draft
  (`pending`).
- Review drafts in the dashboard, copy the caption, publish it yourself
  in the Instagram/TikTok app.
- Come back and click "Mark posted" (or "Reject").

Deliberately never touches `approved` -- the Poster Agent polls for
`approved` rows and will (stub-)"publish" and mark them `posted` on its
own within the hour. If this dashboard used `approved` for "ready to
post", a row would flip to `posted` before you'd actually posted it
anywhere real. So `approved` stays reserved for later, when an automated
generator + Telegram review step feed the real Poster Agent.

Basic-auth protected (`CONTENT_STUDIO_USERNAME` / `_PASSWORD` in `.env`).
Bound to `127.0.0.1:8000` only, same pattern as n8n on this VPS -- not
exposed publicly by default.

### Try it

```sh
cd meleh-studio-social
docker compose up -d --build   # now also builds & starts content_agent
```

View it by tunneling from your own machine (don't expose 8000 publicly):

```sh
ssh -L 8000:127.0.0.1:8000 root@<server-ip>
```

Then open `http://127.0.0.1:8000` in your browser and log in with the
`CONTENT_STUDIO_USERNAME` / `CONTENT_STUDIO_PASSWORD` from `.env`.

I built and manually verified this whole flow locally before pushing:
auth-gates every route (401 without credentials), draft creation via
both pasted URL and file upload, the uploaded file is served back
correctly, empty-caption submissions are rejected without creating a
row, and "Mark posted" updates `status`/`posted_at` in the database.

## Status: step (d) complete -- Telegram Review Bot

`telegram_bot/main.py` is a mobile-friendly companion to the Content
Studio dashboard -- same `content_queue` rows, reachable from your phone
without needing the SSH tunnel the dashboard requires.

- The moment a draft is created (`pending`, not yet sent), the bot
  messages you the caption + media with **Posted** / **Reject** buttons.
- Tapping a button updates the database directly and edits the message
  to show the outcome.
- If you haven't responded by `review_deadline` (4h after creation), it
  sends exactly one reminder ping -- never an automatic status change.

Same safety rule as the dashboard: it never touches `approved`, for the
same reason -- the Poster Agent polls for `approved` rows and would
stub-"publish" and mark one `posted` on its own, which would race ahead
of you actually posting anything real.

Requires two new nullable columns (`telegram_message_id`,
`telegram_reminded_at`) added in
`migrations/002_add_telegram_columns.sql` -- since the VPS's Postgres
volume already exists, this migration needs to be applied by hand (see
"Try it" below and the note in the migration file itself).

### Try it

1. Create a bot: message [@BotFather](https://t.me/BotFather) on
   Telegram, `/newbot`, follow the prompts -- it gives you a token.
2. Message your new bot once (anything), then find your chat ID via
   [@userinfobot](https://t.me/userinfobot) or the `getUpdates` API.
3. Add both to `.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
4. Apply the new migration (only needed once, since the volume already exists):
   ```sh
   docker compose exec -T db psql -U meleh_social -d meleh_social \
     < migrations/002_add_telegram_columns.sql
   ```
5. `docker compose up -d --build` (now also builds & starts telegram_bot)
6. Create a draft via the dashboard (or `docker compose exec db psql ...`
   an insert like earlier steps) and confirm it lands in Telegram within
   `TELEGRAM_POLL_INTERVAL_SECONDS` (default 60s), with working buttons.

I verified the database-side logic (send-once dedup, reminder dedup,
button actions updating status correctly, double-click safety, and
chat-ID authorization) locally against a real Postgres with the
Telegram API calls mocked out, since that doesn't require a live bot
token. The actual Telegram send/receive round-trip needs your real bot
token and chat ID to test, which only you can set up -- steps above.

## Next steps

- **(e) TODO stubs** -- OpenAI captions, Runway image/video gen (chosen
  over Higgsfield -- reliability issues seen using Higgsfield via
  ChatGPT), Meta Graph API publishing (`poster_agent/publishers/meta.py`),
  TikTok publishing (`poster_agent/publishers/tiktok.py`). Once Meta/TikTok
  approval comes through and these go live, the dashboard's/bot's "Mark
  posted" step can be retired in favor of the real automated Poster Agent.
