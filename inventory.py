from __future__ import annotations

from config import CREATURE_CATALOG, RARITY_COLORS, RARITY_INDEX, RARITY_ORDER
from leveling import calculate_creature_value, scale_stats

import database


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
    creatures = [enrich_creature(creature) for creature in database.list_creatures_for_user(user_id)]
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
