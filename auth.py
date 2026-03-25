from __future__ import annotations
import bcrypt
from config import EMAIL_PATTERN, USERNAME_PATTERN
from network import safe_request, safe_json

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
        response = safe_request("get", "users")
        payload = safe_json(response)
        if not isinstance(payload, list):
            return None
        username_norm = username.strip().lower()
        for user in payload:
            if isinstance(user, dict) and str(user.get("username", "")).strip().lower() == username_norm:
                return user
    except Exception as e:
        print(f"[ERROR] Failed to fetch user by username: {e}")
        return None
    return None

def _fetch_user_meta_by_email(email: str) -> dict | None:
    try:
        response = safe_request("get", "users")
        payload = safe_json(response)
        if not isinstance(payload, list):
            return None
        email_norm = email.strip().lower()
        for user in payload:
            if isinstance(user, dict) and str(user.get("email", "")).strip().lower() == email_norm:
                return user
    except Exception as e:
        print(f"[ERROR] Failed to fetch user by email: {e}")
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
        print(f"[DEBUG] Attempting to sign up user: {clean_username} at {clean_email}")
        response = safe_request(
            "post",
            "signup",
            json={
                "email": clean_email,
                "real_name": clean_real_name,
                "username": clean_username,
                "password": clean_password,
            },
        )
        print(f"[DEBUG] Signup response status: {response.status_code}")
        payload = safe_json(response)
        
        if not payload or payload.get("status") != "success":
            message = _parse_server_message(payload, response)
            print(f"[DEBUG] Signup failed for user: {clean_username}, reason: {message}")
            message_lower = message.lower()
            if "email" in message_lower and ("already" in message_lower or "registered" in message_lower or "exists" in message_lower):
                raise AuthError("That email is already registered.")
            if any(word in message_lower for word in ("username", "user")) and any(
                word in message_lower for word in ("taken", "already", "exists")
            ):
                raise AuthError("That username is already taken.")
            raise AuthError(message or "Could not create the account.")

        print(f"[DEBUG] Signup successful for user: {clean_username}")
        
        # Fallback to username if id is missing (old server compatibility)
        user_username = payload.get("username") or clean_username
        user_id = payload.get("id") or user_username
        return {
            "id": user_id,
            "username": user_username,
            "real_name": payload.get("real_name", clean_real_name),
            "email": payload.get("email", clean_email),
            "tokens": int(payload.get("tokens", 0) or 0),
            "session_token": payload.get("session_token"),
        }
    except AuthError:
        raise
    except Exception as error:
        print(f"[ERROR] An unexpected error occurred during signup: {error}")
        if "Connection" in str(error) or "Timeout" in str(error):
            raise AuthError("Could not reach the server. Check your connection.") from error
        raise AuthError(f"Could not create the account: {error}") from error

def login_user(identifier: str, password: str) -> dict:
    clean_identifier = identifier.strip()
    clean_password = password.strip()
    if not clean_identifier or not clean_password:
        raise AuthError("Enter your username or email and password.")

    try:
        print(f"[DEBUG] Attempting to log in user: {clean_identifier}")
        
        response = safe_request(
            "post",
            "login",
            json={"username": clean_identifier, "password": clean_password},
        )
        payload = safe_json(response)

        if not payload or payload.get("status") != "success":
            print(f"[DEBUG] Login failed for user: {clean_identifier}")
            raise AuthError("Invalid credentials.")

        print(f"[DEBUG] Login successful for user: {payload.get('username')}")
        
        # Fallback to username if id is missing (old server compatibility)
        user_username = payload.get("username") or clean_username
        user_id = payload.get("id") or user_username
        return {
            "id": user_id,
            "username": user_username,
            "real_name": payload.get("real_name", ""),
            "email": payload.get("email", ""),
            "tokens": int(payload.get("tokens", 0) or 0),
            "session_token": payload.get("session_token"),
        }
    except AuthError:
        raise
    except Exception as error:
        print(f"[ERROR] An unexpected error occurred during login: {error}")
        # Be more descriptive about network errors
        if "Connection" in str(error) or "Timeout" in str(error):
            raise AuthError("Could not reach the server. Check your connection.") from error
        raise AuthError("Invalid credentials.") from error
