from __future__ import annotations
from network import safe_request, safe_json
from config import CREATURE_CATALOG, RARITY_COLORS, RARITY_INDEX, RARITY_ORDER, slugify
from leveling import calculate_creature_value, scale_stats
import database
from sprite_loader import get_sprite_path

def enrich_creature(creature: dict) -> dict:
    creature_key = creature.get("creature_key")
    if not creature_key or creature_key not in CREATURE_CATALOG:
        print(f"[ERROR] Cannot enrich creature: key '{creature_key}' not found.")
        return {}
    
    template = CREATURE_CATALOG[creature_key]
    rarity = creature.get("rarity", template.get("rarity", "Common"))
    level = int(creature.get("level", 1) or 1)
    
    stats = scale_stats(template.get("base_stats", {}), rarity, level)
    unlocked_moves = []
    for move in template.get("moves", []):
        move_payload = dict(move)
        move_payload["unlocked"] = level >= move.get("unlock_level", 1)
        unlocked_moves.append(move_payload)

    enriched = dict(creature)
    enriched.update(
        {
            "display_name": creature.get("creature_name", template.get("name", "Unknown")),
            "theme": template.get("theme", "default"),
            "stats": stats,
            "moves": unlocked_moves,
            "rarity_color": RARITY_COLORS.get(rarity, "#FFFFFF"),
            "rarity_index": RARITY_INDEX.get(rarity, 0),
            "value": calculate_creature_value(rarity, level, float(creature.get("value_roll", 1.0) or 1.0)),
        }
    )
    return enriched

def get_creature(creature_id: int) -> dict | None:
    creature = database.get_creature_by_id(creature_id)
    if not creature:
        return None
    return enrich_creature(dict(creature))

def get_inventory(user_id: int | str, sort_by: str = "rarity", rarity_filter: str | None = None) -> list[dict]:
    # Fallback to username if id is None, for old server compatibility
    username = str(user_id)
    raw_creatures: list[dict] = []
    try:
        response = safe_request("get", f"inventory/{username}")
        payload = safe_json(response)
        if isinstance(payload, list):
            raw_creatures = payload
    except Exception as e:
        print(f"[ERROR] Failed to fetch inventory for {username}: {e}")
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
        enriched = enrich_creature(creature_payload)
        if enriched:
            creatures.append(enriched)

    if rarity_filter and rarity_filter in RARITY_ORDER:
        creatures = [creature for creature in creatures if creature.get("rarity") == rarity_filter]

    if sort_by == "value":
        creatures.sort(key=lambda creature: (creature.get("value", 0), creature.get("level", 1), creature.get("rarity_index", 0)), reverse=True)
    elif sort_by == "level":
        creatures.sort(key=lambda creature: (creature.get("level", 1), creature.get("value", 0), creature.get("rarity_index", 0)), reverse=True)
    else:
        creatures.sort(key=lambda creature: (creature.get("rarity_index", 0), creature.get("value", 0), creature.get("level", 1)), reverse=True)
    return creatures

def get_inventory_count(user_id: int | str) -> int:
    """FIX: Added missing helper to prevent NameError in player lists."""
    try:
        username = str(user_id)
        response = safe_request("get", f"inventory/{username}")
        payload = safe_json(response)
        return len(payload) if isinstance(payload, list) else 0
    except Exception as e:
        print(f"[ERROR] Failed to get inventory count for {user_id}: {e}")
        return 0

def get_inventory_summary(user_id: int | str) -> dict:
    """FIX: Added missing helper to prevent NameError in dashboards."""
    try:
        creatures = get_inventory(user_id)
        if not creatures:
            return {"count": 0, "total_value": 0, "highest_rarity": "None"}
        
        total_value = sum(c.get("value", 0) for c in creatures)
        # RARITY_ORDER is assumed to be low -> high (e.g. Common -> Godly)
        highest_rarity = "Common"
        highest_idx = -1
        for c in creatures:
            r = c.get("rarity", "Common")
            idx = RARITY_INDEX.get(r, 0)
            if idx > highest_idx:
                highest_idx = idx
                highest_rarity = r
                
        return {
            "count": len(creatures),
            "total_value": total_value,
            "highest_rarity": highest_rarity
        }
    except Exception as e:
        print(f"[ERROR] Failed to get inventory summary for {user_id}: {e}")
        return {"count": 0, "total_value": 0, "highest_rarity": "None"}


def admin_inventory_text(user_id: int | str) -> str:
    """FIX: Defensive programming for admin panel inventory view."""
    try:
        creatures = get_inventory(user_id, sort_by="rarity")
        if not creatures:
            return "No creatures yet."

        lines = []
        for creature in creatures:
            if not isinstance(creature, dict): continue
            lines.append(
                f"{creature.get('display_name', 'Unknown')} | {creature.get('rarity', 'Common')} | "
                f"Lv {creature.get('level', 1)} | Value {creature.get('value', 0)}"
            )
        return "\n".join(lines)
    except Exception as e:
        print(f"[ERROR] Failed to get admin inventory text for {user_id}: {e}")
        return "Error loading inventory."
