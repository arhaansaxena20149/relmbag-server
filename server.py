from flask import Flask, request, jsonify
import sqlite3
import random
import hashlib
import os
import time

app = Flask(__name__)

DB_NAME = "game.db"

# --------------------------
# DATABASE
# --------------------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        real_name TEXT,
        username TEXT UNIQUE,
        password TEXT,
        tokens INTEGER DEFAULT 0
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        creature TEXT,
        rarity TEXT,
        level INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0
    )
    """)
        # 🔴 TRADES TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user TEXT,
        to_user TEXT,
        offer TEXT,
        request TEXT,
        status TEXT DEFAULT 'pending'
    )
    """)

    # 🔴 PRESENCE TABLE (ONLINE STATUS)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS presence (
        username TEXT PRIMARY KEY,
        last_seen INTEGER
    )
    """)

    conn.commit()
    conn.close()

init_db()

# --------------------------
# HELPERS
# --------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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
    data = request.json
    conn = get_db()

    try:
        conn.execute(
            "INSERT INTO users (email, real_name, username, password) VALUES (?, ?, ?, ?)",
            (data["email"], data["real_name"], data["username"], hash_password(data["password"]))
        )
        conn.commit()
        return jsonify({"status": "success"})
    except:
        return jsonify({"status": "error", "message": "User exists"})
    finally:
        conn.close()

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (data["username"], hash_password(data["password"]))
    ).fetchone()

    conn.close()

    if user:
        return jsonify({
            "status": "success",
            "tokens": user["tokens"]
        })

    return jsonify({"status": "error"})

# --------------------------
# ADMIN
# --------------------------
@app.route("/users", methods=["GET"])
def get_users():
    conn = get_db()

    users = conn.execute("SELECT * FROM users").fetchall()
    presence = conn.execute("SELECT * FROM presence").fetchall()

    conn.close()

    presence_map = {p["username"]: p["last_seen"] for p in presence}
    now = int(time.time())

    result = []
    for u in users:
        last_seen = presence_map.get(u["username"], 0)
        online = (now - last_seen) < 10

        result.append({
            "username": u["username"],
            "real_name": u["real_name"],
            "email": u["email"],
            "tokens": u["tokens"],
            "online": online
        })

    return jsonify(result)

@app.route("/add_tokens", methods=["POST"])
def add_tokens():
    data = request.json
    conn = get_db()

    conn.execute(
        "UPDATE users SET tokens = tokens + ? WHERE username=?",
        (data["amount"], data["username"])
    )

    conn.commit()
    conn.close()

    return jsonify({"status": "success"})

# --------------------------
# INVENTORY
# --------------------------
@app.route("/inventory/<username>", methods=["GET"])
def get_inventory(username):
    conn = get_db()

    items = conn.execute(
        "SELECT creature, rarity, level, xp FROM inventory WHERE username=?",
        (username,)
    ).fetchall()

    conn.close()

    return jsonify([dict(i) for i in items])

# --------------------------
# CRATE SYSTEM
# --------------------------
@app.route("/open_crate", methods=["POST"])
def open_crate():
    data = request.json
    username = data["username"]

    conn = get_db()

    user = conn.execute(
        "SELECT tokens FROM users WHERE username=?",
        (username,)
    ).fetchone()

    if not user or user["tokens"] < 10:
        conn.close()
        return jsonify({"status": "error", "message": "Not enough tokens"})

    conn.execute(
        "UPDATE users SET tokens = tokens - 10 WHERE username=?",
        (username,)
    )

    rarity = roll_rarity()
    creature = random.choice(CREATURES[rarity])

    conn.execute(
        "INSERT INTO inventory (username, creature, rarity) VALUES (?, ?, ?)",
        (username, creature, rarity)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "rarity": rarity,
        "creature": creature
    })

# --------------------------
# HEALTH CHECK (IMPORTANT FOR RENDER)
# --------------------------
@app.route("/")
def home():
    return "RelmBag Server Running"

# --------------------------
# TraDING
# --------------------------
@app.route("/create_trade", methods=["POST"])
def create_trade():
    data = request.json

    conn = get_db()
    conn.execute("""
        INSERT INTO trades (from_user, to_user, offer, request, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (
        data["from_user"],
        data["to_user"],
        str(data["offer"]),
        str(data["request"])
    ))
    conn.commit()
    conn.close()

    return jsonify({"status": "success"})

@app.route("/get_trades/<username>", methods=["GET"])
def get_trades(username):
    conn = get_db()

    trades = conn.execute("""
        SELECT * FROM trades
        WHERE to_user=? AND status='pending'
    """, (username,)).fetchall()

    conn.close()

    return jsonify([dict(t) for t in trades])

@app.route("/accept_trade", methods=["POST"])
def accept_trade():
    data = request.json

    conn = get_db()
    conn.execute("""
        UPDATE trades SET status='accepted'
        WHERE id=?
    """, (data["trade_id"],))
    conn.commit()
    conn.close()

    return jsonify({"status": "accepted"})

# --------------------------
# fighting
# --------------------------
@app.route("/fight", methods=["POST"])
def fight():
    data = request.json

    import random
    winner = random.choice([data["player1"], data["player2"]])

    return jsonify({
        "winner": winner
    })
@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.json
    username = data["username"]

    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO presence (username, last_seen)
        VALUES (?, ?)
    """, (username, int(time.time())))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})
# --------------------------
# RUN SERVER (RENDER READY)
# --------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)