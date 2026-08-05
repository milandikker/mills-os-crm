"""
Shared Postgres connection helper.

The Content Agent, Poster Agent, and Telegram Bot all talk to the same
content_queue table, so they all go through this one module to connect --
one place that knows the connection details, one place to fix if they
ever change.
"""
import os

import psycopg2
import psycopg2.extras


def get_connection():
    """Open a new connection to the Meleh Studio social-agent database.

    Reads connection details from environment variables (see .env.example).
    Use it as a context manager so the connection always gets closed:

        with get_connection() as conn:
            ...
    """
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def dict_cursor(conn):
    """Return a cursor that yields rows as dict-like objects (keyed by
    column name) instead of plain tuples -- much easier to read/write in
    agent code than tuple indexing."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
