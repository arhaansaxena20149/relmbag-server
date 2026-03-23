from __future__ import annotations

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover
    import http_client as requests

SERVER_URL = "https://relmbag-server.onrender.com"

from config import CREATURE_CATALOG, RARITY_COLORS, RARITY_INDEX, RARITY_ORDER, slugify
from leveling import calculate_creature_value, scale_stats

import database
from sprite_loader import get_sprite_path


def enrich_creature(creature: dict) -> dict:
    template = CREATURE_CATALOG[creature["creature_key"]]
    stats = scale_stats(template["base_stats"], creature["rarity"], creature["level"])
    unlocked_moves = []
    for move in template["moves"]:
        move_payload = dict(move)
        move_payload["unlocked"] = creature["level"] >= move["unlock_level"]
        unlocked_moves.append(move_payload)

    enriched = dict(creature)
    enriched.update(
        {
            "display_name": creature["creature_name"],
            "theme": template["theme"],
            "stats": stats,
            "moves": unlocked_moves,
            "rarity_color": RARITY_COLORS[creature["rarity"]],
            "rarity_index": RARITY_INDEX[creature["rarity"]],
            "value": calculate_creature_value(creature["rarity"], creature["level"], creature["value_roll"]),
        }
    )
    return enriched


def get_creature(creature_id: int) -> dict | None:
    creature = database.get_creature_by_id(creature_id)
    return enrich_creature(creature) if creature else None


def get_inventory(user_id: int, sort_by: str = "rarity", rarity_filter: str | None = None) -> list[dict]:
    username = str(user_id)
    raw_creatures: list[dict] = []
    try:
        response = requests.get(f"{SERVER_URL}/inventory/{username}", timeout=10)
        if response.ok:
            payload = response.json()
            if isinstance(payload, list):
                raw_creatures = payload
    except Exception:
        raw_creatures = []

    creatures: list[dict] = []
    for index, creature in enumerate(raw_creatures):
        if not isinstance(creature, dict):
            continue
        creature_key = creature.get("creature") or creature.get("creature_key")
        if not creature_key:
            continue

        candidate_key = creature_key
        if candidate_key not in CREATURE_CATALOG:
            candidate_key = slugify(str(candidate_key))
        if candidate_key not in CREATURE_CATALOG:
            continue

        template = CREATURE_CATALOG[candidate_key]
        rarity = creature.get("rarity") or template.get("rarity")
        level = int(creature.get("level", 1) or 1)
        xp = int(creature.get("xp", 0) or 0)
        value_roll = float(creature.get("value_roll", 1.0) or 1.0)

        creature_payload = {
            "id": creature.get("id", index),
            "user_id": user_id,
            "creature_key": template["key"],
            "creature_name": template["name"],
            "rarity": rarity,
            "image_path": str(get_sprite_path(template["key"])),
            "level": level,
            "xp": xp,
            "value_roll": value_roll,
        }
        creatures.append(enrich_creature(creature_payload))

    if rarity_filter and rarity_filter in RARITY_ORDER:
        creatures = [creature for creature in creatures if creature["rarity"] == rarity_filter]

    if sort_by == "value":
        creatures.sort(key=lambda creature: (creature["value"], creature["level"], creature["rarity_index"]), reverse=True)
    elif sort_by == "level":
        creatures.sort(key=lambda creature: (creature["level"], creature["value"], creature["rarity_index"]), reverse=True)
    else:
        creatures.sort(key=lambda creature: (creature["rarity_index"], creature["value"], creature["level"]), reverse=True)
    return creatures


def get_inventory_summary(user_id: int) -> dict:
    creatures = get_inventory(user_id)
    if not creatures:
        return {
            "count": 0,
            "highest_rarity": "None",
            "total_value": 0,
        }

    return {
        "count": len(creatures),
        "highest_rarity": max(creatures, key=lambda creature: creature["rarity_index"])["rarity"],
        "total_value": sum(creature["value"] for creature in creatures),
    }


def admin_inventory_text(user_id: int) -> str:
    creatures = get_inventory(user_id, sort_by="rarity")
    if not creatures:
        return "No creatures yet."

    lines = []
    for creature in creatures:
        lines.append(
            f"{creature['display_name']} | {creature['rarity']} | Lv {creature['level']} | Value {creature['value']}"
        )
    return "\n".join(lines)
