from __future__ import annotations

import sqlite3

import bcrypt

import database
from config import EMAIL_PATTERN, USERNAME_PATTERN


class AuthError(ValueError):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def signup_user(email: str, real_name: str, username: str, password: str) -> dict:
    database.initialize_database()

    clean_email = email.strip().lower()
    clean_real_name = real_name.strip()
    clean_username = username.strip()
    clean_password = password.strip()

    if not EMAIL_PATTERN.match(clean_email):
        raise AuthError("Enter a valid email address.")
    if not clean_real_name:
        raise AuthError("Real name is required.")
    if not USERNAME_PATTERN.match(clean_username):
        raise AuthError("Username must be 3-20 characters and use letters, numbers, or underscores.")
    if len(clean_password) < 8:
        raise AuthError("Password must be at least 8 characters.")

    try:
        user_id = database.insert_user(
            clean_email,
            clean_real_name,
            clean_username,
            hash_password(clean_password),
        )
    except sqlite3.IntegrityError as error:
        message = str(error).lower()
        if "users.email" in message:
            raise AuthError("That email is already registered.") from error
        if "users.username" in message:
            raise AuthError("That username is already taken.") from error
        raise AuthError("Could not create the account.") from error

    database.touch_user_presence(user_id)
    return database.get_user_by_id(user_id)


def login_user(identifier: str, password: str) -> dict:
    database.initialize_database()

    clean_identifier = identifier.strip()
    clean_password = password.strip()
    if not clean_identifier or not clean_password:
        raise AuthError("Enter your username or email and password.")

    user = database.get_user_by_identifier(clean_identifier)
    if user is None or not verify_password(clean_password, user["password_hash"]):
        raise AuthError("Invalid credentials.")
    database.touch_user_presence(user["id"])
    return user
