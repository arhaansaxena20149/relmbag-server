import bcrypt
import logging
from flask import Flask, request, jsonify
import sqlite3
import random
import time
import os
import uuid
from config import DATABASE_PATH
import database
from database import transaction, _create_schema
import trading
import combat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Use the centralized database path
DB_NAME = str(DATABASE_PATH)

# --------------------------
# DATABASE
# --------------------------
def get_db():
    return database.get_connection()

def init_db():
    database.initialize_database()

init_db()

# --------------------------
# HELPERS
# --------------------------
def hash_password(password):
    return auth.hash_password(password)

def verify_password(password, stored):
    """Robust password verification that handles both bcrypt and plain text (legacy)."""
    if not stored:
        return False
    
    # Strip whitespace to prevent copy-paste errors
    password = password.strip()
    stored = stored.strip()
    
    try:
        # Bcrypt hashes usually start with $2b$, $2a$, or $2y$.
        if stored.startswith('$2b$') or stored.startswith('$2a$') or stored.startswith('$2y$'):
            return bcrypt.checkpw(password.encode('utf-8'), stored.encode('utf-8'))
        # Fallback to plain text for legacy accounts created before bcrypt.
        return password == stored
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

import auth # Import auth after defining helpers to avoid circularity if needed, 
           # but auth.py doesn't import server.py so it's fine.

def roll_rarity():
    rarities = [
        ("Common", 40),
        ("Uncommon", 25),
        ("Rare", 15),
        ("Epic", 8),
        ("Legendary", 5),
        ("Mythic", 3),
        ("Godly", 2),
        ("Celestial", 1),
        ("Multiversal", 0.7),
        ("Ultimate", 0.3),
    ]

    roll = random.uniform(0, 100)
    current = 0

    for rarity, chance in rarities:
        current += chance
        if roll <= current:
            return rarity
    return "Common"

CREATURES = {
    "Common": ["Pebblit", "Sprig", "Fluffo"],
    "Uncommon": ["Thornix", "Glidera", "Emberoo"],
    "Rare": ["Pyronis", "Aquarion"],
    "Epic": ["Inferyss", "Voltaris"],
    "Legendary": ["Drakonis Prime"],
    "Mythic": ["Nyxarion"],
    "Godly": ["Omnithar"],
    "Celestial": ["Nebulon"],
    "Multiversal": ["Paradoxon"],
    "Ultimate": ["Omega Zenith"]
}

# --------------------------
# AUTH
# --------------------------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json or {}
    email = data.get("email")
    real_name = data.get("real_name")
    username = data.get("username")
    password = data.get("password")

    if not all([email, real_name, username, password]):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    try:
        user_id = database.insert_user(email, real_name, username, hash_password(password))
        session_token = str(uuid.uuid4())
        database.update_user_session_token(user_id, session_token)
        logger.info(f"User signed up: {username} (ID: {user_id})")
        
        return jsonify({
            "status": "success",
            "id": user_id,
            "username": username,
            "real_name": real_name,
            "email": email,
            "tokens": 0,
            "session_token": session_token
        })
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Username or email already exists"}), 400
    except Exception as e:
        logger.error(f"Signup failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    identifier = data.get("username")
    password = data.get("password")

    if not identifier or not password:
        return jsonify({"status": "error", "message": "Missing credentials"}), 400

    try:
        user = database.get_user_by_identifier(identifier)
        if user:
            # Check multiple possible fields for the password hash
            stored_hash = user.get("password_hash") or user.get("password")
            logger.info(f"Login Attempt: Found user '{user['username']}'")
            
            if verify_password(password, stored_hash):
                if user.get("is_banned"):
                    logger.warning(f"Login Blocked: User '{user['username']}' is banned.")
                    return jsonify({"status": "error", "message": "Your account has been banned."}), 403
                
                session_token = str(uuid.uuid4())
                database.update_user_session_token(user["id"], session_token)
                database.touch_user_presence(user["id"])
                logger.info(f"Login Success: User '{user['username']}' logged in successfully.")
                return jsonify({
                    "status": "success",
                    "id": user["id"],
                    "username": user["username"],
                    "real_name": user["real_name"],
                    "email": user["email"],
                    "tokens": user["tokens"],
                    "session_token": session_token
                })
            else:
                logger.warning(f"Login Failed: Password mismatch for user '{user['username']}'. Hash starts with: {str(stored_hash)[:10]}...")
        else:
            logger.warning(f"Login Failed: No user found for identifier '{identifier}'")
    except Exception as e:
        logger.error(f"Login Error: {e}")
    
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route("/reset_password", methods=["POST"])
def reset_password():
    data = request.json or {}
    user_id = data.get("user_id")
    new_password = data.get("password")
    
    if not user_id or not new_password:
        return jsonify({"status": "error", "message": "Missing data"}), 400
        
    try:
        hashed = hash_password(new_password)
        database.reset_user_password(user_id, hashed)
        logger.info(f"Password reset for user ID: {user_id}")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Password reset failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/users", methods=["GET"])
def get_users():
    try:
        # Increased threshold to 90s to be more resilient to network lag
        users = database.list_admin_players(within_seconds=90)
        logger.info(f"Fetched {len(users)} users for admin/roster.")
        # Unify online status keys for client compatibility
        for u in users:
            u["online"] = bool(u.get("is_online", False))
            u["is_online"] = bool(u.get("is_online", False))
        return jsonify(users)
    except Exception as e:
        logger.error(f"Failed to fetch users: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/ban_user", methods=["POST"])
def ban_user():
    data = request.json or {}
    user_id = data.get("user_id")
    is_banned = data.get("is_banned", True)
    try:
        database.ban_user(user_id, is_banned)
        action = "banned" if is_banned else "unbanned"
        logger.info(f"User {user_id} {action}")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to ban/unban user {user_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/kick_user", methods=["POST"])
def kick_user():
    data = request.json or {}
    user_id = data.get("user_id")
    try:
        database.kick_user(user_id)
        logger.info(f"User {user_id} kicked")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to kick user {user_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/add_tokens", methods=["POST"])
def add_tokens():
    data = request.json or {}
    amount = data.get("amount")
    user_id = data.get("user_id")

    if amount is None or user_id is None:
        return jsonify({"status": "error", "message": "Invalid data"}), 400

    try:
        # Resolve user by ID or Username
        if isinstance(user_id, int) or (isinstance(user_id, str) and user_id.isdigit()):
            user = database.get_user_by_id(int(user_id))
        else:
            user = database.get_user_by_username(user_id)

        if not user:
             return jsonify({"status": "error", "message": "User not found"}), 404
             
        database.adjust_user_tokens(user["id"], amount)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to add tokens: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --------------------------
# INVENTORY
# --------------------------
@app.route("/inventory/<username>", methods=["GET"])
def get_inventory(username):
    try:
        user = database.get_user_by_username(username)
        if not user:
            return jsonify([]), 404
        items = database.list_creatures_for_user(user["id"])
        return jsonify(items)
    except Exception as e:
        logger.error(f"Failed to fetch inventory: {e}")
        return jsonify([]), 500

# --------------------------
# CRATE SYSTEM
# --------------------------
@app.route("/open_crate", methods=["POST"])
def open_crate():
    data = request.json or {}
    username = data.get("username")

    if not username:
        return jsonify({"status": "error", "message": "Username required"}), 400

    try:
        user = database.get_user_by_username(username)
        if not user or user["tokens"] < 10:
            return jsonify({"status": "error", "message": "Not enough tokens"}), 400

        database.adjust_user_tokens(user["id"], -10)

        # Logic from crate_system.py could be used here if it was integrated
        # For now, keep the simple logic but use database.py schema
        rarity = roll_rarity()
        creature_key = random.choice(CREATURES.get(rarity, ["Pebblit"])).lower().replace(" ", "_")
        creature_name = creature_key.replace("_", " ").title()

        creature_id = database.insert_creature(
            user_id=user["id"],
            creature_key=creature_key,
            creature_name=creature_name,
            rarity=rarity,
            image_path=f"assets/generated/sprites/{creature_key}.png",
            value_roll=random.uniform(0.7, 1.3)
        )

        logger.info(f"Crate opened by {username}: {creature_name} ({rarity})")
        return jsonify({
            "status": "success",
            "id": creature_id,
            "rarity": rarity,
            "creature": creature_name
        })
    except Exception as e:
        logger.error(f"Crate opening failed: {e}")
        return jsonify({"status": "error"}), 500

# --------------------------
# TRADING
# --------------------------
@app.route("/create_trade", methods=["POST"])
def create_trade():
    data = request.json or {}
    initiator_id = data.get("initiator_id")
    recipient_username = data.get("recipient_username")

    if not all([initiator_id, recipient_username]):
        return jsonify({"status": "error", "message": "Missing required data"}), 400

    try:
        snapshot = trading.create_trade(initiator_id, recipient_username)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Trade creation failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/trades/<int:user_id>", methods=["GET"])
def get_trades(user_id):
    try:
        trades = trading.list_user_trades(user_id)
        return jsonify(trades)
    except Exception as e:
        logger.error(f"Failed to fetch trades: {e}")
        return jsonify([]), 500

@app.route("/trade/<int:trade_id>", methods=["GET"])
def get_trade(trade_id):
    user_id = request.args.get("user_id", type=int)
    try:
        snapshot = trading.get_trade(trade_id, user_id)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Failed to fetch trade {trade_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/accept_trade", methods=["POST"])
def accept_trade():
    data = request.json or {}
    trade_id = data.get("trade_id")
    user_id = data.get("user_id")

    try:
        snapshot = trading.accept_trade_request(trade_id, user_id)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Trade acceptance failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/cancel_trade", methods=["POST"])
def cancel_trade():
    data = request.json or {}
    trade_id = data.get("trade_id")
    user_id = data.get("user_id")
    try:
        trading.cancel_trade_request(trade_id, user_id)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Trade cancellation failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/add_creature_to_trade", methods=["POST"])
def add_creature_to_trade():
    data = request.json or {}
    trade_id = data.get("trade_id")
    user_id = data.get("user_id")
    creature_id = data.get("creature_id")
    try:
        snapshot = trading.add_creature_to_trade(trade_id, user_id, creature_id)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Add creature to trade failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/remove_creature_from_trade", methods=["POST"])
def remove_creature_from_trade():
    data = request.json or {}
    trade_id = data.get("trade_id")
    user_id = data.get("user_id")
    creature_id = data.get("creature_id")
    try:
        snapshot = trading.remove_creature_from_trade(trade_id, user_id, creature_id)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Remove creature from trade failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/set_trade_tokens", methods=["POST"])
def set_trade_tokens():
    data = request.json or {}
    trade_id = data.get("trade_id")
    user_id = data.get("user_id")
    token_amount = data.get("token_amount")
    try:
        snapshot = trading.set_trade_tokens(trade_id, user_id, token_amount)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Set trade tokens failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/confirm_trade", methods=["POST"])
def confirm_trade():
    data = request.json or {}
    trade_id = data.get("trade_id")
    user_id = data.get("user_id")
    try:
        snapshot = trading.confirm_trade(trade_id, user_id)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Confirm trade failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/trades_incoming/<int:user_id>", methods=["GET"])
def list_incoming_trade_requests(user_id):
    try:
        trades = trading.list_incoming_trade_requests(user_id)
        return jsonify(trades)
    except Exception as e:
        logger.error(f"Failed to fetch incoming trades: {e}")
        return jsonify([]), 500

# --------------------------
# FIGHTING
# --------------------------
@app.route("/create_battle", methods=["POST"])
def create_battle():
    data = request.json or {}
    challenger_id = data.get("challenger_id")
    opponent_username = data.get("opponent_username")
    creature_id = data.get("creature_id")

    try:
        snapshot = combat.create_battle(challenger_id, opponent_username, creature_id)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Battle creation failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/battle/<int:battle_id>", methods=["GET"])
def get_battle(battle_id):
    user_id = request.args.get("user_id", type=int)
    try:
        snapshot = combat.get_battle(battle_id, user_id)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Failed to fetch battle {battle_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/battles/<int:user_id>", methods=["GET"])
def list_user_battles(user_id):
    try:
        battles = combat.list_user_battles(user_id)
        return jsonify(battles)
    except Exception as e:
        logger.error(f"Failed to fetch battles for {user_id}: {e}")
        return jsonify([]), 500

@app.route("/accept_battle", methods=["POST"])
def accept_battle():
    data = request.json or {}
    battle_id = data.get("battle_id")
    user_id = data.get("user_id")
    creature_id = data.get("creature_id")

    try:
        snapshot = combat.accept_battle(battle_id, user_id, creature_id)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Battle acceptance failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/cancel_battle", methods=["POST"])
def cancel_battle():
    data = request.json or {}
    battle_id = data.get("battle_id")
    user_id = data.get("user_id")
    try:
        combat.cancel_battle(battle_id, user_id)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Battle cancellation failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/battles_incoming/<int:user_id>", methods=["GET"])
def list_incoming_battle_requests(user_id):
    try:
        battles = combat.list_incoming_battle_requests(user_id)
        return jsonify(battles)
    except Exception as e:
        logger.error(f"Failed to fetch incoming battles: {e}")
        return jsonify([]), 500

@app.route("/submit_move", methods=["POST"])
def submit_move():
    data = request.json or {}
    battle_id = data.get("battle_id")
    user_id = data.get("user_id")
    move = data.get("move")
    try:
        snapshot = combat.submit_move(battle_id, user_id, move)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Submit move failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/forfeit_battle", methods=["POST"])
def forfeit_battle():
    data = request.json or {}
    battle_id = data.get("battle_id")
    user_id = data.get("user_id")
    try:
        snapshot = combat.forfeit_battle(battle_id, user_id)
        return jsonify(snapshot)
    except Exception as e:
        logger.error(f"Forfeit battle failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.json or {}
    username = data.get("username")
    session_token = data.get("session_token")

    if not username:
        return jsonify({"status": "error"}), 400

    try:
        user = database.get_user_by_username(username)
        if user:
            if user.get("is_banned"):
                return jsonify({"status": "error", "message": "banned"}), 403
            
            # Enforce session token if one is active on the server.
            # This allows the 'kick' functionality to work by clearing the token on the server.
            server_token = user.get("session_token")
            if server_token and session_token != server_token:
                 return jsonify({"status": "error", "message": "kicked"}), 401

            database.touch_user_presence(user["id"])
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Heartbeat failed: {e}")
        return jsonify({"status": "error"}), 500

@app.route("/migrate", methods=["GET", "POST"])
def manual_migrate():
    try:
        with transaction() as connection:
            _create_schema(connection)
        return jsonify({"status": "success", "message": "Database migration triggered."})
    except Exception as e:
        logger.error(f"Manual migration failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/debug", methods=["GET"])
def debug():
    try:
        tables = database.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        return jsonify({
            "status": "success",
            "tables": [t["name"] for t in tables],
            "database_path": str(DATABASE_PATH)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/")
def home():
    # Show version 2.2 to confirm this exact code is live
    return "RelmBag Server Running - v2.2"

# --------------------------
# RUN SERVER
# --------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    logger.info(f"Starting server on port {port}...")
    app.run(host="0.0.0.0", port=port)