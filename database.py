from __future__ import annotations

import argparse
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

from config import DATABASE_PATH, ensure_directories


def get_connection() -> sqlite3.Connection:
    ensure_directories()
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    # Lazily ensure schema exists so listing queries don't crash when the app
    # skips calling initialize_database() at startup.
    try:
        has_users_table = (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone()
            is not None
        )
        if not has_users_table:
            _create_schema(connection)
            connection.commit()
    except Exception:
        # If the schema check fails for any reason, let the original callers
        # surface a meaningful DB error later.
        pass
    return connection


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def _create_schema(connection: sqlite3.Connection) -> None:
    # Ensure users table has all required columns first
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            real_name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            tokens INTEGER NOT NULL DEFAULT 0 CHECK(tokens >= 0),
            last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_banned INTEGER NOT NULL DEFAULT 0,
            session_token TEXT
        );
        """
    )
    
    # Backfill missing columns if table already existed (migration)
    user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
    if "is_banned" not in user_columns:
        connection.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0")
    if "session_token" not in user_columns:
        connection.execute("ALTER TABLE users ADD COLUMN session_token TEXT")
    if "password" in user_columns and "password_hash" not in user_columns:
        connection.execute("ALTER TABLE users RENAME COLUMN password TO password_hash")

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS owned_creatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            creature_key TEXT NOT NULL,
            creature_name TEXT NOT NULL,
            rarity TEXT NOT NULL,
            image_path TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1 CHECK(level >= 1),
            xp INTEGER NOT NULL DEFAULT 0 CHECK(xp >= 0),
            value_roll REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            initiator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            initiator_tokens INTEGER NOT NULL DEFAULT 0 CHECK(initiator_tokens >= 0),
            recipient_tokens INTEGER NOT NULL DEFAULT 0 CHECK(recipient_tokens >= 0),
            initiator_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(initiator_confirmed IN (0, 1)),
            recipient_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(recipient_confirmed IN (0, 1)),
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'open', 'completed', 'cancelled', 'declined')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trade_creatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            creature_id INTEGER NOT NULL REFERENCES owned_creatures(id) ON DELETE CASCADE,
            UNIQUE(trade_id, creature_id)
        );

        CREATE TABLE IF NOT EXISTS battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenger_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            opponent_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            challenger_creature_id INTEGER NOT NULL REFERENCES owned_creatures(id) ON DELETE CASCADE,
            opponent_creature_id INTEGER REFERENCES owned_creatures(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'active', 'completed', 'cancelled')),
            state_json TEXT NOT NULL DEFAULT '{}',
            challenger_move TEXT,
            opponent_move TEXT,
            winner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            xp_awarded INTEGER NOT NULL DEFAULT 0 CHECK(xp_awarded IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_owned_creatures_user_id ON owned_creatures(user_id);
        CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
        CREATE INDEX IF NOT EXISTS idx_trade_creatures_trade_id ON trade_creatures(trade_id);
        CREATE INDEX IF NOT EXISTS idx_battles_status ON battles(status);
        CREATE INDEX IF NOT EXISTS idx_battles_challenger_id ON battles(challenger_id);
        CREATE INDEX IF NOT EXISTS idx_battles_opponent_id ON battles(opponent_id);
        """
    )

    # Backfill for older DBs that may have missed columns or used old names.
    user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
    if "last_seen" not in user_columns:
        connection.execute("ALTER TABLE users ADD COLUMN last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")
    if "password" in user_columns and "password_hash" not in user_columns:
        connection.execute("ALTER TABLE users RENAME COLUMN password TO password_hash")
    if "real_name" not in user_columns:
        connection.execute("ALTER TABLE users ADD COLUMN real_name TEXT NOT NULL DEFAULT 'Player'")
    if "is_banned" not in user_columns:
        connection.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0")
    if "session_token" not in user_columns:
        connection.execute("ALTER TABLE users ADD COLUMN session_token TEXT")


def fetch_one(query: str, params: Iterable[Any] = ()) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(query, tuple(params)).fetchone()
    return _row_to_dict(row)


def fetch_all(query: str, params: Iterable[Any] = ()) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(query, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def initialize_database(seed_demo: bool = False) -> None:
    ensure_directories()
    with transaction() as connection:
        _create_schema(connection)

    from sprite_loader import ensure_sprite_assets

    ensure_sprite_assets()
    if seed_demo:
        seed_demo_data()


def get_user_by_id(user_id: int) -> dict | None:
    return fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))


def get_user_by_username(username: str) -> dict | None:
    return fetch_one("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,))


def get_user_by_email(email: str) -> dict | None:
    return fetch_one("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,))


def get_user_by_identifier(identifier: str) -> dict | None:
    # Check for both password and password_hash to handle incomplete migrations.
    user = fetch_one(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE",
        (identifier, identifier),
    )
    if user:
        user_dict = dict(user)
        # Ensure 'password_hash' key exists if the server expects it.
        if "password" in user_dict and "password_hash" not in user_dict:
            user_dict["password_hash"] = user_dict["password"]
        return user_dict
    return None


def list_other_users(current_user_id: int | None = None) -> list[dict]:
    if current_user_id is None:
        return fetch_all("SELECT id, username, tokens FROM users ORDER BY username COLLATE NOCASE")
    return fetch_all(
        "SELECT id, username, tokens FROM users WHERE id != ? ORDER BY username COLLATE NOCASE",
        (current_user_id,),
    )


def list_admin_players(within_seconds: int = 120) -> list[dict]:
    # Use a slightly larger window for 'online' status to account for network lag.
    return fetch_all(
        f"""
        SELECT
            u.*,
            (SELECT COUNT(*) FROM owned_creatures oc WHERE oc.user_id = u.id) AS creature_count,
            CASE
                WHEN u.last_seen IS NOT NULL AND DATETIME(u.last_seen) >= DATETIME('now', '-{within_seconds} seconds') THEN 1
                ELSE 0
            END AS is_online
        FROM users u
        ORDER BY is_online DESC, u.username COLLATE NOCASE
        """
    )


def touch_user_presence(user_id: int) -> None:
    with transaction() as connection:
        connection.execute(
            "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,),
        )


def list_online_users(current_user_id: int, within_seconds: int = 90) -> list[dict]:
    return fetch_all(
        f"""
        SELECT
            u.id,
            u.username,
            u.last_seen,
            COUNT(oc.id) AS creature_count
        FROM users u
        LEFT JOIN owned_creatures oc ON oc.user_id = u.id
        WHERE u.id != ?
          AND DATETIME(u.last_seen) >= DATETIME('now', '-{within_seconds} seconds')
        GROUP BY u.id, u.username, u.last_seen
        ORDER BY u.username COLLATE NOCASE
        """,
        (current_user_id,),
    )


def is_user_online(user_id: int, within_seconds: int = 90) -> bool:
    row = fetch_one(
        f"""
        SELECT
            CASE
                WHEN DATETIME(last_seen) >= DATETIME('now', '-{within_seconds} seconds') THEN 1
                ELSE 0
            END AS is_online
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    )
    return bool(row and row["is_online"])


def insert_user(email: str, real_name: str, username: str, password_hash: str, tokens: int = 0) -> int:
    with transaction() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (email, real_name, username, password_hash, tokens)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email, real_name, username, password_hash, tokens),
        )
        return int(cursor.lastrowid)


def set_user_tokens(user_id: int, tokens: int) -> int:
    if tokens < 0:
        raise ValueError("Token balance cannot be negative.")
    with transaction() as connection:
        connection.execute("UPDATE users SET tokens = ? WHERE id = ?", (tokens, user_id))
    return tokens


def adjust_user_tokens(user_id: int | str, delta: int) -> int:
    with transaction() as connection:
        row = connection.execute("SELECT tokens FROM users WHERE id = ? OR username = ?", (user_id, user_id)).fetchone()
        if row is None:
            raise ValueError("User not found.")
        next_balance = row["tokens"] + delta
        if next_balance < 0:
            raise ValueError("Token balance cannot be negative.")
        connection.execute("UPDATE users SET tokens = ? WHERE id = ? OR username = ?", (next_balance, user_id, user_id))
        return int(next_balance)


def ban_user(user_id: int, is_banned: bool = True) -> None:
    with transaction() as connection:
        connection.execute(
            "UPDATE users SET is_banned = ?, session_token = NULL WHERE id = ?",
            (1 if is_banned else 0, user_id),
        )


def kick_user(user_id: int) -> None:
    with transaction() as connection:
        connection.execute("UPDATE users SET session_token = NULL WHERE id = ?", (user_id,))


def update_user_session_token(user_id: int, session_token: str | None) -> None:
    with transaction() as connection:
        connection.execute("UPDATE users SET session_token = ? WHERE id = ?", (session_token, user_id))


def reset_user_password(user_id: int | str, new_password_hash: str) -> None:
    with transaction() as connection:
        # Determine if we are using an ID or a Username
        if isinstance(user_id, int) or (isinstance(user_id, str) and user_id.isdigit()):
            where_clause = "WHERE id = ?"
        else:
            where_clause = "WHERE username = ? COLLATE NOCASE"

        # Update both possible column names to ensure it sticks regardless of migration state
        user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        if "password_hash" in user_columns:
            connection.execute(f"UPDATE users SET password_hash = ? {where_clause}", (new_password_hash, user_id))
        if "password" in user_columns:
            connection.execute(f"UPDATE users SET password = ? {where_clause}", (new_password_hash, user_id))


def get_creature_by_id(creature_id: int) -> dict | None:
    return fetch_one("SELECT * FROM owned_creatures WHERE id = ?", (creature_id,))


def list_creatures_for_user(user_id: int) -> list[dict]:
    return fetch_all(
        """
        SELECT *
        FROM owned_creatures
        WHERE user_id = ?
        ORDER BY level DESC, rarity DESC, creature_name COLLATE NOCASE
        """,
        (user_id,),
    )


def insert_creature(
    user_id: int,
    creature_key: str,
    creature_name: str,
    rarity: str,
    image_path: str,
    value_roll: float,
    level: int = 1,
    xp: int = 0,
) -> int:
    with transaction() as connection:
        cursor = connection.execute(
            """
            INSERT INTO owned_creatures (
                user_id,
                creature_key,
                creature_name,
                rarity,
                image_path,
                level,
                xp,
                value_roll
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, creature_key, creature_name, rarity, image_path, level, xp, value_roll),
        )
        return int(cursor.lastrowid)


def update_creature_progress(creature_id: int, level: int, xp: int) -> None:
    with transaction() as connection:
        connection.execute(
            "UPDATE owned_creatures SET level = ?, xp = ? WHERE id = ?",
            (level, xp, creature_id),
        )


def transfer_creature(creature_id: int, new_owner_id: int) -> None:
    with transaction() as connection:
        connection.execute(
            "UPDATE owned_creatures SET user_id = ? WHERE id = ?",
            (new_owner_id, creature_id),
        )


def seed_demo_data() -> None:
    from auth import hash_password
    from config import CREATURE_CATALOG
    from sprite_loader import get_sprite_path

    demo_users = [
        {
            "email": "alpha@example.com",
            "real_name": "Alpha Trainer",
            "username": "alpha",
            "password": "DemoPass123!",
            "tokens": 80,
            "creatures": ["sprig", "pyronis", "aetherion"],
        },
        {
            "email": "beta@example.com",
            "real_name": "Beta Trader",
            "username": "beta",
            "password": "DemoPass123!",
            "tokens": 65,
            "creatures": ["voltbit", "umbrix", "nebulon"],
        },
    ]

    for payload in demo_users:
        existing = get_user_by_username(payload["username"])
        if existing is None:
            user_id = insert_user(
                payload["email"],
                payload["real_name"],
                payload["username"],
                hash_password(payload["password"]),
                payload["tokens"],
            )
        else:
            user_id = existing["id"]

        current_creatures = list_creatures_for_user(user_id)
        if current_creatures:
            continue

        for index, creature_key in enumerate(payload["creatures"]):
            template = CREATURE_CATALOG[creature_key]
            insert_creature(
                user_id=user_id,
                creature_key=creature_key,
                creature_name=template["name"],
                rarity=template["rarity"],
                image_path=str(get_sprite_path(creature_key)),
                value_roll=1.0 + (index * 0.03),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the RelmBag database.")
    parser.add_argument("--seed-demo", action="store_true", help="Seed demo users and starter creatures.")
    arguments = parser.parse_args()
    initialize_database(seed_demo=arguments.seed_demo)
    message = f"Database ready at {DATABASE_PATH}"
    if arguments.seed_demo:
        message += " with demo data."
    print(message)


if __name__ == "__main__":
    main()
