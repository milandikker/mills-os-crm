"""
Poster Agent.

Job: check the queue for rows with status 'approved', publish them
(currently stubbed -- see poster_agent/publishers/), and mark them
'posted'. If publishing raises an error, record it and put the row back
in the queue for a retry on the next run, up to POSTER_MAX_RETRIES times.

Run modes:
  python -m poster_agent.main          loop forever, one pass per
                                        POSTER_INTERVAL_SECONDS (default 1h)
  python -m poster_agent.main --once   run a single pass and exit
                                        (useful for manual testing, cron,
                                        or a one-off invocation)
"""
import argparse
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from poster_agent.publishers import meta, tiktok
from shared.db import dict_cursor, get_connection

load_dotenv()

MAX_RETRIES = int(os.environ.get("POSTER_MAX_RETRIES", 3))
INTERVAL_SECONDS = int(os.environ.get("POSTER_INTERVAL_SECONDS", 3600))

# Which stub publisher handles which platform. TODO(step e): once real
# publishing is wired up, this dispatch stays the same -- only the
# functions inside meta.py / tiktok.py change.
PUBLISHERS = {
    "instagram": meta.publish,
    "facebook": meta.publish,
    "tiktok": tiktok.publish,
}


def fetch_approved_rows(conn, limit=10):
    """Grab a batch of approved rows, oldest first.

    FOR UPDATE SKIP LOCKED means if two poster runs ever overlapped,
    they'd naturally split the work instead of double-publishing the
    same row -- cheap insurance for a system that's meant to run
    unattended.
    """
    with dict_cursor(conn) as cur:
        cur.execute(
            """
            SELECT * FROM content_queue
            WHERE status = 'approved'
            ORDER BY created_at ASC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (limit,),
        )
        return cur.fetchall()


def mark_posted(conn, row_id, platform_post_id=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE content_queue
            SET status = 'posted', posted_at = now(), platform_post_id = %s
            WHERE id = %s
            """,
            (platform_post_id, row_id),
        )


def mark_failed(conn, row_id, error_message, prior_retry_count):
    """Record the failure. If we're still under the retry budget, put the
    row back to 'approved' so the next hourly run tries again; otherwise
    leave it 'failed' for good (a human can requeue it manually if needed).
    """
    new_retry_count = prior_retry_count + 1
    next_status = "approved" if new_retry_count < MAX_RETRIES else "failed"
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE content_queue
            SET status = %s, retry_count = %s, last_error = %s
            WHERE id = %s
            """,
            (next_status, new_retry_count, str(error_message), row_id),
        )
    return next_status, new_retry_count


def publish(row):
    """Look up the right publisher for this row's platform and call it.
    Raises ValueError for a platform with no publisher registered.
    Returns the platform's real post ID (str), or None if unavailable
    (e.g. a still-stubbed platform).
    """
    publisher = PUBLISHERS.get(row["platform"])
    if publisher is None:
        raise ValueError(f"No publisher registered for platform: {row['platform']}")
    return publisher(row)


def run_once():
    """Process every currently-approved row once. This is the function to
    call directly for manual testing."""
    print(f"[poster_agent] run started at {datetime.now(timezone.utc).isoformat()}")
    with get_connection() as conn:
        rows = fetch_approved_rows(conn)
        if not rows:
            print("[poster_agent] no approved rows to publish")
            conn.commit()
            return

        for row in rows:
            print(
                f"[poster_agent] publishing id={row['id']} "
                f"platform={row['platform']} content_type={row['content_type']}"
            )
            try:
                platform_post_id = publish(row)
                mark_posted(conn, row["id"], platform_post_id=platform_post_id)
                conn.commit()
                print(f"[poster_agent] id={row['id']} -> posted (platform_post_id={platform_post_id})")
            except Exception as exc:
                next_status, new_retry_count = mark_failed(
                    conn, row["id"], exc, row["retry_count"]
                )
                conn.commit()
                print(
                    f"[poster_agent] id={row['id']} publish failed "
                    f"(retry {new_retry_count}/{MAX_RETRIES}): {exc} "
                    f"-> {next_status}"
                )


def main():
    parser = argparse.ArgumentParser(description="Meleh Studio Poster Agent")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single pass and exit instead of looping forever.",
    )
    args = parser.parse_args()

    if args.once:
        run_once()
        return

    print(f"[poster_agent] starting loop, interval={INTERVAL_SECONDS}s")
    while True:
        run_once()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
