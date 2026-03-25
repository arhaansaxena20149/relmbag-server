from __future__ import annotations
from network import safe_request, safe_json

def get_users() -> list[dict]:
    """
    Fetches a list of all users from the server.
    Returns an empty list on failure.
    """
    try:
        response = safe_request("get", "users")
        payload = safe_json(response)
        if isinstance(payload, list):
            return payload
        print(f"[WARNING] /users endpoint returned non-list payload: {type(payload)}")
        return []
    except Exception as e:
        print(f"[ERROR] Failed to fetch users: {e}")
        return []

# --- Trading API ---
def create_trade(initiator_id: int, recipient_username: str) -> dict:
    try:
        response = safe_request("post", "create_trade", json={
            "initiator_id": initiator_id,
            "recipient_username": recipient_username
        })
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to create trade: {e}")
        return {}

def list_user_trades(user_id: int | str) -> list[dict]:
    try:
        # Fallback to username if id is None, for old server compatibility
        endpoint = f"get_trades/{user_id}"
        response = safe_request("get", endpoint)
        return safe_json(response) or []
    except Exception as e:
        print(f"[ERROR] Failed to list trades for {user_id}: {e}")
        return []

def get_trade(trade_id: int, user_id: int | str) -> dict:
    try:
        # Old server might not have get_trade endpoint, or it might be different.
        # For now, let's keep it but handle the case where it might fail.
        response = safe_request("get", f"trade/{trade_id}", params={"user_id": user_id})
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to get trade {trade_id}: {e}")
        return {}

def accept_trade_request(trade_id: int, user_id: int) -> dict:
    try:
        response = safe_request("post", "accept_trade", json={
            "trade_id": trade_id,
            "user_id": user_id
        })
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to accept trade {trade_id}: {e}")
        return {}

def cancel_trade(trade_id: int, user_id: int) -> None:
    try:
        safe_request("post", "cancel_trade", json={
            "trade_id": trade_id,
            "user_id": user_id
        })
    except Exception as e:
        print(f"[ERROR] Failed to cancel trade {trade_id}: {e}")

def add_creature_to_trade(trade_id: int, user_id: int, creature_id: int) -> dict:
    try:
        response = safe_request("post", "add_creature_to_trade", json={
            "trade_id": trade_id,
            "user_id": user_id,
            "creature_id": creature_id
        })
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to add creature to trade: {e}")
        return {}

def remove_creature_from_trade(trade_id: int, user_id: int, creature_id: int) -> dict:
    try:
        response = safe_request("post", "remove_creature_from_trade", json={
            "trade_id": trade_id,
            "user_id": user_id,
            "creature_id": creature_id
        })
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to remove creature from trade: {e}")
        return {}

def set_trade_tokens(trade_id: int, user_id: int, token_amount: int) -> dict:
    try:
        response = safe_request("post", "set_trade_tokens", json={
            "trade_id": trade_id,
            "user_id": user_id,
            "token_amount": token_amount
        })
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to set trade tokens: {e}")
        return {}

def confirm_trade(trade_id: int, user_id: int) -> dict:
    try:
        response = safe_request("post", "confirm_trade", json={
            "trade_id": trade_id,
            "user_id": user_id
        })
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to confirm trade: {e}")
        return {}

def list_incoming_trade_requests(user_id: int | str) -> list[dict]:
    try:
        # For old server, this might be get_trades
        response = safe_request("get", f"get_trades/{user_id}")
        return safe_json(response) or []
    except Exception as e:
        print(f"[ERROR] Failed to list incoming trades for {user_id}: {e}")
        return []

# --- Combat API ---
def create_battle(challenger_id: int, opponent_username: str, creature_id: int) -> dict:
    try:
        response = safe_request("post", "create_battle", json={
            "challenger_id": challenger_id,
            "opponent_username": opponent_username,
            "creature_id": creature_id
        })
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to create battle: {e}")
        return {}

def list_user_battles(user_id: int | str) -> list[dict]:
    try:
        # Fallback to username for old server compatibility
        endpoint = f"list_user_battles/{user_id}"
        response = safe_request("get", endpoint)
        return safe_json(response) or []
    except Exception as e:
        print(f"[ERROR] Failed to list battles for {user_id}: {e}")
        return []

def get_battle(battle_id: int, user_id: int | str) -> dict:
    try:
        # Old server endpoint: get_battle
        response = safe_request("get", f"get_battle/{battle_id}", params={"user_id": user_id})
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to get battle {battle_id}: {e}")
        return {}

def accept_battle(battle_id: int, user_id: int, creature_id: int) -> dict:
    try:
        response = safe_request("post", "accept_battle", json={
            "battle_id": battle_id,
            "user_id": user_id,
            "creature_id": creature_id
        })
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to accept battle {battle_id}: {e}")
        return {}

def cancel_battle(battle_id: int, user_id: int) -> None:
    try:
        safe_request("post", "cancel_battle", json={
            "battle_id": battle_id,
            "user_id": user_id
        })
    except Exception as e:
        print(f"[ERROR] Failed to cancel battle {battle_id}: {e}")

def list_incoming_battle_requests(user_id: int | str) -> list[dict]:
    try:
        # For old server, this might be list_user_battles
        response = safe_request("get", f"list_user_battles/{user_id}")
        battles = safe_json(response) or []
        # Old server might return all battles, so filter for pending
        if isinstance(battles, list):
            return [b for b in battles if b.get("status") == "pending" and b.get("opponent_id") == user_id]
        return []
    except Exception as e:
        print(f"[ERROR] Failed to list incoming battles for {user_id}: {e}")
        return []

def submit_move(battle_id: int, user_id: int, move_name: str) -> dict:
    try:
        response = safe_request("post", "submit_move", json={
            "battle_id": battle_id,
            "user_id": user_id,
            "move": move_name
        })
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to submit move: {e}")
        return {}

def forfeit_battle(battle_id: int, user_id: int) -> dict:
    try:
        response = safe_request("post", "forfeit_battle", json={
            "battle_id": battle_id,
            "user_id": user_id
        })
        return safe_json(response) or {}
    except Exception as e:
        print(f"[ERROR] Failed to forfeit battle: {e}")
        return {}

# --- Admin API ---
def ban_user(user_id: int, is_banned: bool = True) -> bool:
    try:
        response = safe_request("post", "ban_user", json={
            "user_id": user_id,
            "is_banned": is_banned
        })
        payload = safe_json(response)
        return payload and payload.get("status") == "success"
    except Exception as e:
        print(f"[ERROR] Failed to ban/unban user {user_id}: {e}")
        return False

def kick_user(user_id: int) -> bool:
    try:
        response = safe_request("post", "kick_user", json={
            "user_id": user_id
        })
        payload = safe_json(response)
        return payload and payload.get("status") == "success"
    except Exception as e:
        print(f"[ERROR] Failed to kick user {user_id}: {e}")
        return False

def add_tokens(user_id: int | str, amount: int) -> bool:
    try:
        response = safe_request("post", "add_tokens", json={
            "user_id": user_id,
            "amount": amount
        })
        payload = safe_json(response)
        return payload and payload.get("status") == "success"
    except Exception as e:
        print(f"[ERROR] Failed to add tokens for user {user_id}: {e}")
        return False

def reset_password(user_id: int | str, new_password: str) -> bool:
    try:
        # Fallback to ensure we have a valid identifier
        if user_id is None:
            print("[ERROR] Cannot reset password: user_id is None")
            return False
            
        response = safe_request("post", "reset_password", json={
            "user_id": user_id,
            "password": new_password
        })
        # If the new endpoint returns 404, it means the server hasn't been updated yet.
        if response.status_code == 404:
            print("[ERROR] Reset password failed: Server endpoint /reset_password not found. Please push changes to Render.")
            return False
            
        payload = safe_json(response)
        return payload and payload.get("status") == "success"
    except Exception as e:
        print(f"[ERROR] Failed to reset password for user {user_id}: {e}")
        return False

