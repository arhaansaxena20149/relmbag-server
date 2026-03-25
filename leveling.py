from __future__ import annotations

from config import BASE_VALUES, MAX_LEVEL, RARITY_STAT_MULTIPLIERS


def xp_required_for_level(level: int) -> int:
    return int(40 + (level ** 1.6) * 24)


def apply_experience(level: int, xp: int, gained_xp: int) -> tuple[int, int, int]:
    current_level = level
    current_xp = xp + gained_xp
    levels_gained = 0

    while current_level < MAX_LEVEL:
        required = xp_required_for_level(current_level)
        if current_xp < required:
            break
        current_xp -= required
        current_level += 1
        levels_gained += 1

    if current_level >= MAX_LEVEL:
        current_level = MAX_LEVEL
        current_xp = 0

    return current_level, current_xp, levels_gained


def scale_stats(base_stats: dict, rarity: str, level: int) -> dict:
    # FIX: Defensive dictionary access
    rarity_multiplier = RARITY_STAT_MULTIPLIERS.get(rarity, 1.0)
    hp_scale = 1 + ((level - 1) * 0.06)
    combat_scale = 1 + ((level - 1) * 0.045)

    return {
        "HP": int(round(base_stats.get("HP", 100) * rarity_multiplier * hp_scale)),
        "Attack": int(round(base_stats.get("Attack", 10) * rarity_multiplier * combat_scale)),
        "Defense": int(round(base_stats.get("Defense", 10) * rarity_multiplier * combat_scale)),
        "Speed": int(round(base_stats.get("Speed", 10) * rarity_multiplier * combat_scale)),
    }


def calculate_creature_value(rarity: str, level: int, value_roll: float) -> int:
    # FIX: Defensive dictionary access
    base_val = BASE_VALUES.get(rarity, 100)
    level_multiplier = 1 + ((level - 1) * 0.075)
    return int(round(base_val * value_roll * level_multiplier))


def grant_experience_to_creature(creature_id: int, gained_xp: int) -> dict:
    import database

    creature = database.get_creature_by_id(creature_id)
    if creature is None:
        raise ValueError("Creature not found.")

    # FIX: Defensive dictionary access
    level = creature.get("level", 1)
    xp = creature.get("xp", 0)
    
    new_level, new_xp, levels_gained = apply_experience(level, xp, gained_xp)
    database.update_creature_progress(creature_id, new_level, new_xp)
    updated_creature = database.get_creature_by_id(creature_id)
    return {
        "creature": updated_creature,
        "levels_gained": levels_gained,
        "gained_xp": gained_xp,
    }
