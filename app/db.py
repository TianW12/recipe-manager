"""Database layer for the recipe app.

This module is the *only* place that knows how recipes are stored. Everything
else (the routes in ``main.py``, the templates) goes through the two functions
below. If we ever swap SQLite for something else, this file is what changes.

Why SQLite?
    - It is a single file on disk (``data/recipes.db``) — no separate database
      server to install, run, or keep alive. Ideal for a small Raspberry Pi.
    - Python ships with the ``sqlite3`` module in the standard library, so there
      are no extra dependencies to install.
    - It comfortably handles a personal collection of thousands of recipes.

Data model — a single ``recipes`` table:
    Rather than splitting ingredients/steps/tags into separate related tables
    (a "normalized" design), we keep everything in one row as plain text. This
    is a deliberate trade-off:
        * ingredients / instructions -> one item per line (split on newlines
          when rendering).
        * tags -> a single comma-separated string (e.g. "dinner, vegetarian").
    This keeps the code tiny and the data trivial to edit, which is exactly what
    a personal recipe box needs. If the app ever grows (per-ingredient scaling,
    a shared multi-user database, etc.) this is the first thing to normalize.
"""

import sqlite3
from pathlib import Path

# Absolute path to the database file. Resolved relative to this source file so
# it works no matter what directory the app is started from. The ``data``
# folder is mounted as a Docker volume in production, so the DB survives
# container rebuilds — back up this one file and you have backed up everything.
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "recipes.db"

# The full schema. ``CREATE TABLE IF NOT EXISTS`` makes init_db() safe to run on
# every startup: it creates the table the first time and is a no-op afterwards.
# Every column has a DEFAULT so partially-filled recipes never break an INSERT.
# created_at / updated_at are stored as ISO-8601 text via SQLite's datetime().
SCHEMA = """
CREATE TABLE IF NOT EXISTS recipes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,  -- unique id, auto-assigned
    title        TEXT NOT NULL,                      -- the only required field
    description  TEXT DEFAULT '',                    -- one-line summary
    servings     TEXT DEFAULT '',                    -- free text, e.g. "4"
    prep_time    TEXT DEFAULT '',                    -- free text, e.g. "20 min"
    cook_time    TEXT DEFAULT '',                    -- free text, e.g. "30 min"
    ingredients  TEXT DEFAULT '',                    -- one ingredient per line
    instructions TEXT DEFAULT '',                    -- one step per line
    notes        TEXT DEFAULT '',                    -- personal modifications
    tags         TEXT DEFAULT '',                    -- comma-separated tags
    source_url   TEXT DEFAULT '',                    -- where the recipe came from
    created_at   TEXT DEFAULT (datetime('now')),     -- set once on insert
    updated_at   TEXT DEFAULT (datetime('now'))      -- refreshed on every edit
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE NOT NULL COLLATE NOCASE, -- login identifier
    username      TEXT DEFAULT '',                     -- optional display name
    password_hash TEXT NOT NULL,                       -- bcrypt, never plaintext
    verified      INTEGER DEFAULT 0,                   -- 1 once email is confirmed
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS email_codes (
    user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    code_hash  TEXT NOT NULL,                 -- sha256 of the 6-digit code
    expires_at TEXT NOT NULL,                 -- code is useless after this
    attempts   INTEGER DEFAULT 0              -- wrong guesses; capped at 5
);
"""


def get_db() -> sqlite3.Connection:
    """Open (and return) a connection to the SQLite database.

    Callers are responsible for ``commit()`` (after writes) and ``close()``.
    A fresh connection per request is fine and simplest for SQLite; there is no
    connection pool to manage.
    """
    # Create the data/ directory on first use so connecting never fails.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # row_factory = Row lets us access columns by name (row["title"]) and use
    # them like dicts in templates, instead of positional tuples.
    conn.row_factory = sqlite3.Row
    # WAL (Write-Ahead Logging) allows reads to happen concurrently with a
    # write, which keeps the UI snappy and reduces "database is locked" errors.
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    """Create the recipes table if it does not exist yet.

    Called once at import time in ``main.py`` so the database is always ready
    before the first request is served.
    """
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
