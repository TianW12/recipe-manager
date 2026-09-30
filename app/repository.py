"""Data access layer: every SQL query for recipes lives here.

Routes never write SQL themselves — they call these functions. That keeps the
SQL in one reviewable place and makes the routes short and readable.
All user input is passed as bound ``?`` parameters (never string-formatted into
the query), which prevents SQL injection.
"""

import sqlite3

from .db import get_db

# Columns a user can set through the add/edit form, in the order the
# create/update functions expect them.
FIELDS = (
    "title", "description", "prep_time", "cook_time", "servings",
    "ingredients", "instructions", "notes", "tags", "source_url",
)


def search_recipes(q: str = "", tag: str = "") -> list[sqlite3.Row]:
    """Return recipes matching a free-text query and/or a tag, newest first."""
    conn = get_db()
    sql = "SELECT * FROM recipes"
    clauses: list[str] = []
    params: list[str] = []
    if q:
        clauses.append(
            "(title LIKE ? OR ingredients LIKE ? OR tags LIKE ? OR description LIKE ?)"
        )
        like = f"%{q}%"
        params += [like, like, like, like]
    if tag:
        clauses.append("tags LIKE ?")
        params.append(f"%{tag}%")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY updated_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def get_recipe(rid: int) -> sqlite3.Row | None:
    """Return one recipe by id, or None if it does not exist."""
    conn = get_db()
    row = conn.execute("SELECT * FROM recipes WHERE id = ?", (rid,)).fetchone()
    conn.close()
    return row


def create_recipe(values: dict[str, str]) -> int:
    """Insert a new recipe and return its new id. ``values`` keys = FIELDS."""
    conn = get_db()
    cur = conn.execute(
        f"INSERT INTO recipes ({', '.join(FIELDS)}) "
        f"VALUES ({', '.join('?' for _ in FIELDS)})",
        tuple(values[f] for f in FIELDS),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def update_recipe(rid: int, values: dict[str, str]) -> None:
    """Overwrite an existing recipe's fields and bump ``updated_at``."""
    conn = get_db()
    assignments = ", ".join(f"{f}=?" for f in FIELDS)
    conn.execute(
        f"UPDATE recipes SET {assignments}, updated_at=datetime('now') WHERE id=?",
        (*(values[f] for f in FIELDS), rid),
    )
    conn.commit()
    conn.close()


def delete_recipe(rid: int) -> None:
    """Remove a recipe permanently."""
    conn = get_db()
    conn.execute("DELETE FROM recipes WHERE id = ?", (rid,))
    conn.commit()
    conn.close()


def all_tags() -> list[str]:
    """Every distinct tag across all recipes, alphabetically.

    Tags are stored as one comma-separated string per recipe, so we split each
    recipe's ``tags`` column and de-duplicate into a set.
    """
    conn = get_db()
    rows = conn.execute("SELECT tags FROM recipes WHERE tags != ''").fetchall()
    conn.close()
    tags: set[str] = set()
    for row in rows:
        for t in row["tags"].split(","):
            t = t.strip()
            if t:
                tags.add(t)
    return sorted(tags, key=str.lower)


# --- users ------------------------------------------------------------------

def get_user_by_email(email: str) -> sqlite3.Row | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row


def get_user_by_id(uid: int) -> sqlite3.Row | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    return row


def create_user(email: str, username: str, password_hash: str) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)",
        (email, username, password_hash),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def mark_verified(uid: int) -> None:
    conn = get_db()
    conn.execute("UPDATE users SET verified = 1 WHERE id = ?", (uid,))
    conn.execute("DELETE FROM email_codes WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()


# --- email verification codes -------------------------------------------------

def set_email_code(uid: int, code_hash: str, minutes: int = 15) -> None:
    """Store (or replace) the pending verification code for a user."""
    conn = get_db()
    conn.execute(
        "INSERT INTO email_codes (user_id, code_hash, expires_at, attempts) "
        "VALUES (?, ?, datetime('now', ?), 0) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "code_hash=excluded.code_hash, expires_at=excluded.expires_at, attempts=0",
        (uid, code_hash, f"+{minutes} minutes"),
    )
    conn.commit()
    conn.close()


def get_valid_email_code(uid: int) -> sqlite3.Row | None:
    """The user's code row, or None if expired / too many wrong attempts."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM email_codes WHERE user_id = ? "
        "AND expires_at > datetime('now') AND attempts < 5",
        (uid,),
    ).fetchone()
    conn.close()
    return row


def bump_code_attempts(uid: int) -> None:
    conn = get_db()
    conn.execute(
        "UPDATE email_codes SET attempts = attempts + 1 WHERE user_id = ?", (uid,)
    )
    conn.commit()
    conn.close()
