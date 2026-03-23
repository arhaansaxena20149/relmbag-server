from flask import Flask, request, jsonify
import sqlite3
import random
import hashlib

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

# Example creature pools
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
        return jsonify({"status": "error", "message": "User already exists"})
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
    users = conn.execute("SELECT username, real_name, email, tokens FROM users").fetchall()
    conn.close()

    return jsonify([dict(u) for u in users])

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

    # deduct tokens
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
# RUN SERVER
# --------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)