from __future__ import annotations

import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
GENERATED_DIR = ASSETS_DIR / "generated"
SPRITE_OUTPUT_DIR = GENERATED_DIR / "sprites"

# Use environment variable for persistent storage on Render
DATABASE_PATH = Path(os.environ.get("RELMBAG_DB_PATH", BASE_DIR / "game.db"))
# If the above doesn't persist on Render, try using a absolute path to a persistent disk if you have one mounted.
USER_SPRITE_SHEET_PATH = ASSETS_DIR / "sprite_sheet.png"
DEMO_SPRITE_SHEET_PATH = GENERATED_DIR / "demo_sprite_sheet.png"
APP_ICON_PNG = ICONS_DIR / "pebblit_app_icon.png"
APP_ICON_ICNS = ICONS_DIR / "pebblit.icns"
APP_ICON_ICO = ICONS_DIR / "pebblit.ico"

APP_TITLE = "RelmBag Arena"
APP_SUBTITLE = "Creature Crates, Trading, and Tactical Battles"

CRATE_COST = 10
MAX_LEVEL = 50
WINNER_XP = 60
LOSER_XP = 24

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")

RARITY_ORDER = [
    "Common",
    "Uncommon",
    "Rare",
    "Epic",
    "Legendary",
    "Mythic",
    "Godly",
    "Celestial",
    "Multiversal",
    "Ultimate",
]

RARITY_INDEX = {rarity: index for index, rarity in enumerate(RARITY_ORDER)}

DROP_RATES = {
    "Common": 72.0,
    "Uncommon": 18.0,
    "Rare": 6.0,
    "Epic": 2.5,
    "Legendary": 1.0,
    "Mythic": 0.4,
    "Godly": 0.15,
    "Celestial": 0.07,
    "Multiversal": 0.03,
    "Ultimate": 0.01,
}

BASE_VALUES = {
    "Common": 10,
    "Uncommon": 25,
    "Rare": 60,
    "Epic": 150,
    "Legendary": 400,
    "Mythic": 1000,
    "Godly": 2500,
    "Celestial": 6000,
    "Multiversal": 15000,
    "Ultimate": 50000,
}

RARITY_COLORS = {
    "Common": "#9AA0A6",
    "Uncommon": "#58C96B",
    "Rare": "#44A4FF",
    "Epic": "#B064FF",
    "Legendary": "#F2C14E",
    "Mythic": "#E14B4B",
    "Godly": "#F8F2D1",
    "Celestial": "#6E8DFF",
    "Multiversal": "#9F5BFF",
    "Ultimate": "#FF5FC8",
}

RARITY_STAT_MULTIPLIERS = {
    "Common": 1.00,
    "Uncommon": 1.12,
    "Rare": 1.28,
    "Epic": 1.46,
    "Legendary": 1.68,
    "Mythic": 1.96,
    "Godly": 2.28,
    "Celestial": 2.62,
    "Multiversal": 3.00,
    "Ultimate": 3.45,
}

RARITY_DAMAGE_MULTIPLIERS = {
    "Common": 1.00,
    "Uncommon": 1.10,
    "Rare": 1.22,
    "Epic": 1.37,
    "Legendary": 1.58,
    "Mythic": 1.85,
    "Godly": 2.15,
    "Celestial": 2.50,
    "Multiversal": 2.92,
    "Ultimate": 3.40,
}

MOVE_UNLOCK_LEVELS = [1, 5, 10, 20]

THEME_BASE_STATS = {
    "stone": {"HP": 48, "Attack": 11, "Defense": 16, "Speed": 8},
    "nature": {"HP": 42, "Attack": 12, "Defense": 11, "Speed": 12},
    "wind": {"HP": 36, "Attack": 12, "Defense": 9, "Speed": 17},
    "beast": {"HP": 40, "Attack": 15, "Defense": 10, "Speed": 13},
    "water": {"HP": 41, "Attack": 13, "Defense": 12, "Speed": 12},
    "flame": {"HP": 37, "Attack": 16, "Defense": 9, "Speed": 15},
    "electric": {"HP": 35, "Attack": 17, "Defense": 8, "Speed": 18},
    "ice": {"HP": 39, "Attack": 14, "Defense": 12, "Speed": 11},
    "earth": {"HP": 47, "Attack": 13, "Defense": 15, "Speed": 9},
    "shadow": {"HP": 38, "Attack": 17, "Defense": 9, "Speed": 16},
    "dragon": {"HP": 44, "Attack": 18, "Defense": 14, "Speed": 12},
    "light": {"HP": 41, "Attack": 17, "Defense": 12, "Speed": 14},
    "void": {"HP": 39, "Attack": 18, "Defense": 10, "Speed": 15},
    "cosmic": {"HP": 43, "Attack": 17, "Defense": 13, "Speed": 13},
    "time": {"HP": 37, "Attack": 16, "Defense": 11, "Speed": 19},
    "spirit": {"HP": 40, "Attack": 16, "Defense": 13, "Speed": 14},
}

THEME_COLORS = {
    "stone": "#B0A28A",
    "nature": "#52BF60",
    "wind": "#D0F1FF",
    "beast": "#D6925A",
    "water": "#4BB4F6",
    "flame": "#FF7B2E",
    "electric": "#F7D94C",
    "ice": "#93E3FF",
    "earth": "#9B7B45",
    "shadow": "#7A57C8",
    "dragon": "#E4893C",
    "light": "#F5E27A",
    "void": "#77324A",
    "cosmic": "#4A54D6",
    "time": "#58D0D4",
    "spirit": "#F7FAFF",
}

THEME_MOVES = {
    "stone": [("Pebble Shot", 12, 0), ("Granite Bash", 18, 0), ("Fault Line", 28, 1), ("Titan Quake", 40, 2)],
    "nature": [("Vine Whip", 11, 0), ("Seed Volley", 18, 0), ("Thorn Spiral", 27, 1), ("Verdant Surge", 39, 2)],
    "wind": [("Gust Slice", 11, 0), ("Feather Dart", 17, 0), ("Cyclone Ring", 26, 1), ("Sky Tempest", 38, 2)],
    "beast": [("Bite Rush", 12, 0), ("Pounce Clash", 18, 0), ("Savage Howl", 28, 1), ("Alpha Rampage", 39, 2)],
    "water": [("Splash Burst", 11, 0), ("Ripple Lance", 18, 0), ("Tidal Roll", 27, 1), ("Abyss Crash", 39, 2)],
    "flame": [("Ember Swipe", 12, 0), ("Blaze Arc", 18, 0), ("Inferno Burst", 29, 1), ("Solar Scorch", 41, 2)],
    "electric": [("Static Snap", 12, 0), ("Volt Lance", 18, 0), ("Chain Spark", 28, 1), ("Thunder Drive", 40, 2)],
    "ice": [("Frost Nip", 11, 0), ("Crystal Shard", 17, 0), ("Frozen Pulse", 27, 1), ("Absolute Zero", 39, 2)],
    "earth": [("Mud Slam", 12, 0), ("Boulder Toss", 18, 0), ("Terra Spike", 28, 1), ("Titan Rise", 40, 2)],
    "shadow": [("Shade Claw", 12, 0), ("Night Pulse", 18, 0), ("Umbral Rift", 28, 1), ("Eclipse Fang", 40, 2)],
    "dragon": [("Scale Strike", 13, 0), ("Draco Blaze", 20, 0), ("Wing Rupture", 31, 1), ("Prime Cataclysm", 43, 2)],
    "light": [("Radiant Touch", 12, 0), ("Halo Spear", 18, 0), ("Dawnburst", 28, 1), ("Judgment Ray", 40, 2)],
    "void": [("Null Tap", 12, 0), ("Eventide Beam", 18, 0), ("Collapse Orb", 29, 1), ("Blackout Rift", 41, 2)],
    "cosmic": [("Star Flicker", 12, 0), ("Comet Rush", 19, 0), ("Nebula Arc", 29, 1), ("Galaxy Collapse", 41, 2)],
    "time": [("Tick Slash", 12, 0), ("Chrono Drift", 18, 0), ("Time Split", 28, 1), ("Omega Loop", 40, 2)],
    "spirit": [("Aura Tap", 12, 0), ("Soul Pulse", 18, 0), ("Seraph Burst", 28, 1), ("Divine Anthem", 40, 2)],
}

RARITY_CREATURES = {
    "Common": [
        ("Pebblit", "stone"),
        ("Sprig", "nature"),
        ("Fluffo", "wind"),
        ("Niblet", "beast"),
        ("Bloop", "water"),
    ],
    "Uncommon": [
        ("Thornix", "nature"),
        ("Glidera", "wind"),
        ("Emberoo", "flame"),
        ("Voltbit", "electric"),
        ("Frostlet", "ice"),
    ],
    "Rare": [
        ("Pyronis", "flame"),
        ("Aquarion", "water"),
        ("Zephyros", "wind"),
        ("Terradon", "earth"),
        ("Umbrix", "shadow"),
    ],
    "Epic": [
        ("Inferyss", "flame"),
        ("Voltaris", "electric"),
        ("Glacieron", "ice"),
        ("Astryx", "cosmic"),
        ("Vortexa", "wind"),
    ],
    "Legendary": [
        ("Drakonis Prime", "dragon"),
        ("Aetherion", "light"),
        ("Lunaris Rex", "spirit"),
        ("Solarion", "flame"),
        ("Chronyx", "time"),
    ],
    "Mythic": [
        ("Nyxarion", "shadow"),
        ("Eclipzor", "void"),
        ("Vantheon", "earth"),
        ("Voidrex", "dragon"),
        ("Eternyx", "spirit"),
    ],
    "Godly": [
        ("Omnithar", "spirit"),
        ("Devarion", "light"),
        ("Zenthros", "electric"),
        ("Celestara", "light"),
        ("Auralon", "spirit"),
    ],
    "Celestial": [
        ("Nebulon", "cosmic"),
        ("Galaxor", "cosmic"),
        ("Quasarix", "electric"),
        ("Novaelis", "light"),
        ("Pulsaris", "cosmic"),
    ],
    "Multiversal": [
        ("Paradoxon", "time"),
        ("Dimensar", "dragon"),
        ("Riftalon", "void"),
        ("Variantis", "spirit"),
        ("Fractyx", "void"),
    ],
    "Ultimate": [
        ("Omega Zenith", "cosmic"),
        ("Apex Null", "void"),
        ("Infinity Prime", "light"),
        ("Endbringer", "shadow"),
        ("Absolute X", "void"),
    ],
}


def slugify(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return normalized


def build_moves(theme: str, rarity: str) -> list[dict]:
    scale = RARITY_DAMAGE_MULTIPLIERS[rarity]
    built_moves = []
    for index, (move_name, base_damage, cooldown) in enumerate(THEME_MOVES[theme]):
        built_moves.append(
            {
                "name": move_name,
                "damage": int(round(base_damage * scale)),
                "cooldown": cooldown,
                "unlock_level": MOVE_UNLOCK_LEVELS[index],
            }
        )
    return built_moves


def build_creature_catalog() -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    for row, rarity in enumerate(RARITY_ORDER):
        for column, (name, theme) in enumerate(RARITY_CREATURES[rarity]):
            key = slugify(name)
            catalog[key] = {
                "key": key,
                "name": name,
                "rarity": rarity,
                "theme": theme,
                "grid_row": row,
                "grid_column": column,
                "base_stats": THEME_BASE_STATS[theme],
                "moves": build_moves(theme, rarity),
            }
    return catalog


CREATURE_CATALOG = build_creature_catalog()
CREATURES_BY_RARITY = {
    rarity: [CREATURE_CATALOG[slugify(name)] for name, _theme in RARITY_CREATURES[rarity]]
    for rarity in RARITY_ORDER
}


def ensure_directories() -> None:
    for directory in (DATA_DIR, ASSETS_DIR, ICONS_DIR, GENERATED_DIR, SPRITE_OUTPUT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
