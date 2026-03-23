from __future__ import annotations

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover
    import http_client as requests

SERVER_URL = "https://relmbag-server.onrender.com"

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


def _parse_server_message(payload: dict | None, response) -> str:
    if payload:
        message = payload.get("error") or payload.get("message") or payload.get("detail")
        if isinstance(message, str) and message.strip():
            return message
    return getattr(response, "text", "") or ""


def _fetch_user_meta_by_username(username: str) -> dict | None:
    try:
        response = requests.get(f"{SERVER_URL}/users", timeout=10)
        if not response.ok:
            return None
        payload = response.json()
        if not isinstance(payload, list):
            return None
        username_norm = username.strip().lower()
        for user in payload:
            if isinstance(user, dict) and str(user.get("username", "")).strip().lower() == username_norm:
                return user
    except Exception:
        return None
    return None


def _fetch_user_meta_by_email(email: str) -> dict | None:
    try:
        response = requests.get(f"{SERVER_URL}/users", timeout=10)
        if not response.ok:
            return None
        payload = response.json()
        if not isinstance(payload, list):
            return None
        email_norm = email.strip().lower()
        for user in payload:
            if isinstance(user, dict) and str(user.get("email", "")).strip().lower() == email_norm:
                return user
    except Exception:
        return None
    return None


def signup_user(email: str, real_name: str, username: str, password: str) -> dict:
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
        response = requests.post(
            f"{SERVER_URL}/signup",
            json={
                "email": clean_email,
                "real_name": clean_real_name,
                "username": clean_username,
                "password": clean_password,
            },
            timeout=10,
        )
        payload = None
        try:
            payload = response.json()
        except Exception:
            payload = None

        payload_dict = payload if isinstance(payload, dict) else None
        status_value = payload_dict.get("status") if isinstance(payload_dict, dict) else None

        # Some servers return HTTP 200 but `{status: "error"}`.
        if not response.ok or status_value != "success":
            message = ""
            if isinstance(payload_dict, dict):
                message = str(
                    payload_dict.get("message")
                    or payload_dict.get("error")
                    or payload_dict.get("detail")
                    or payload_dict.get("reason")
                    or ""
                )
            message = (message or _parse_server_message(payload, response)).lower()

            if "email" in message and ("already" in message or "registered" in message or "exists" in message):
                raise AuthError("That email is already registered.")
            if any(word in message for word in ("username", "user")) and any(
                word in message for word in ("taken", "already", "exists")
            ):
                raise AuthError("That username is already taken.")
            if "exists" in message:
                # Ambiguous duplicate (email or username).
                raise AuthError("That username is already taken.")

            print(
                f"[auth] /signup failed status={getattr(response, 'status_code', None)} payload_status={status_value!r} message={message!r}"
            )
            raise AuthError("Could not create the account.")

        tokens = 0
        if isinstance(payload, dict):
            tokens = int(payload.get("tokens", 0) or 0)

        return {
            "id": clean_username,
            "username": clean_username,
            "real_name": clean_real_name,
            "email": clean_email,
            "tokens": tokens,
        }
    except AuthError:
        raise
    except Exception as error:
        raise AuthError("Could not create the account.") from error


def login_user(identifier: str, password: str) -> dict:
    clean_identifier = identifier.strip()
    clean_password = password.strip()
    if not clean_identifier or not clean_password:
        raise AuthError("Enter your username or email and password.")

    try:
        username = clean_identifier
        meta: dict | None = None

        # Server login endpoint accepts username only, but UI supports username or email.
        if "@" in clean_identifier and EMAIL_PATTERN.match(clean_identifier.lower()):
            meta = _fetch_user_meta_by_email(clean_identifier)
            if meta is None:
                raise AuthError("Invalid credentials.")
            username = meta.get("username")
            if not isinstance(username, str) or not username.strip():
                raise AuthError("Invalid credentials.")

        response = requests.post(
            f"{SERVER_URL}/login",
            json={"username": username, "password": clean_password},
            timeout=10,
        )

        payload = None
        try:
            payload = response.json()
        except Exception:
            payload = None

        if not response.ok or not isinstance(payload, dict) or payload.get("status") != "success":
            print(
                f"[auth] /login failed status={getattr(response, 'status_code', None)} message={_parse_server_message(payload, response)!r}"
            )
            raise AuthError("Invalid credentials.")

        tokens = int(payload.get("tokens", 0) or 0)

        if meta is None:
            meta = _fetch_user_meta_by_username(username)

        real_name = meta.get("real_name") if isinstance(meta, dict) else ""
        email_value = meta.get("email") if isinstance(meta, dict) else ""

        return {
            "id": username,
            "username": username,
            "real_name": real_name,
            "email": email_value,
            "tokens": tokens,
        }
    except AuthError:
        raise
    except Exception as error:
        raise AuthError("Invalid credentials.") from error
