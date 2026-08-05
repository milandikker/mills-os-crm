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
  content_agent/           [step c -- not built yet]
  poster_agent/            [step b -- not built yet]
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

## Next steps

- **(b) Poster Agent** -- build against this schema, test by manually
  inserting a fake `approved` row.
- **(c) Content Agent** -- mock product list + brand-voice captions,
  writes `pending` rows daily.
- **(d) Telegram Review Bot** -- Approve/Edit/Reject + 4h auto-approve.
- **(e) TODO stubs** -- OpenAI image gen, Higgsfield video gen, Meta Graph
  API publishing, TikTok publishing.
