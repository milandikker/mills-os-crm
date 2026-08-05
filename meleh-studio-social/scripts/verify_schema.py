"""
One-off sanity check for step (a): confirms the content_queue table exists
and shows its columns + current row count.

Run from the meleh-studio-social/ directory, after `docker compose up -d`:

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python scripts/verify_schema.py

(If you enabled the commented-out port mapping in docker-compose.yml, this
also works run directly on the VPS host, not just inside a container.)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from shared.db import get_connection  # noqa: E402


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'content_queue'
                ORDER BY ordinal_position
                """
            )
            rows = cur.fetchall()
            if not rows:
                print(
                    "content_queue table not found. "
                    "Did `docker compose up -d` run and apply the migration?"
                )
                return

            print("content_queue columns:")
            for name, dtype, nullable in rows:
                print(f"  {name:<18} {dtype:<25} nullable={nullable}")

            cur.execute("SELECT count(*) FROM content_queue")
            print(f"\nRow count: {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
