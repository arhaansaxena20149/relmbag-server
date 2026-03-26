from __future__ import annotations
import random
from network import safe_request, safe_json
from config import CRATE_COST, CREATURES_BY_RARITY, DROP_RATES, RARITY_ORDER
from inventory import enrich_creature
from sprite_loader import get_sprite_path

class CrateError(ValueError):
    pass

def roll_rarity(rng: random.Random | None = None) -> str:
    generator = rng or random
    return generator.choices(RARITY_ORDER, weights=[DROP_RATES.get(rarity, 0) for rarity in RARITY_ORDER], k=1)[0]

def grant_creature(user_id: int, creature_key: str, level: int = 1, rng: random.Random | None = None) -> dict:
    from config import CREATURE_CATALOG, slugify

    generator = rng or random
    candidate_key = creature_key
    if candidate_key not in CREATURE_CATALOG:
        candidate_key = slugify(str(candidate_key))
    
    # FIX: Defensive check for creature template
    template = CREATURE_CATALOG.get(candidate_key)
    if not template:
        print(f"[ERROR] Creature key '{candidate_key}' not found in catalog.")
        return {}

    value_roll = round(generator.uniform(0.90, 1.10), 4)
    creature_payload = {
        "id": int(generator.random() * 1_000_000_000),
        "user_id": user_id,
        "creature_key": template.get("key"),
        "creature_name": template.get("name"),
        "rarity": template.get("rarity"),
        "image_path": str(get_sprite_path(template.get("key"))),
        "level": level,
        "xp": 0,
        "value_roll": value_roll,
    }
    return enrich_creature(creature_payload)

def open_crate(user_id: int, rng: random.Random | None = None) -> dict:
    generator = rng or random
    username = str(user_id)

    try:
        print(f"[DEBUG] Attempting to open crate for user: {username}")
        response = safe_request("post", "open_crate", json={"username": username})
        payload = safe_json(response)
    except Exception as error:
        print(f"[ERROR] Failed to open crate for user {username}: {error}")
        raise CrateError("Could not open crate.") from error

    if not payload or payload.get("status") != "success":
        message = ""
        if isinstance(payload, dict):
            message = str(payload.get("error") or payload.get("message") or payload.get("detail") or "")
        message_l = message.lower()
        print(f"[DEBUG] Crate opening failed for user {username}, reason: {message}")
        if response.status_code == 404 or "user" in message_l and "not found" in message_l:
            raise CrateError("User not found.")
        if "not enough tokens" in message_l or ("tokens" in message_l and "not" in message_l and "enough" in message_l):
            raise CrateError("Not enough tokens.")
        raise CrateError(message.strip() or "Could not open crate.")

    print(f"[DEBUG] Crate opened successfully for user: {username}")
    rarity = payload.get("rarity")
    creature_key = payload.get("creature")
    level = int(payload.get("level", 1) or 1)
    xp = int(payload.get("xp", 0) or 0)
    value_roll = float(payload.get("value_roll", 1.0) or 1.0)
    remaining_tokens = payload.get("remaining_tokens", payload.get("tokens"))

    # If the server doesn't include extra creature stats, fall back to local defaults.
    if not creature_key:
        # If `creature` isn't included, attempt to infer from rarity (best-effort).
        rarity = rarity or roll_rarity(generator)
        available_templates = CREATURES_BY_RARITY.get(rarity)
        if not available_templates:
            print(f"[ERROR] No templates found for rarity '{rarity}'.")
            raise CrateError("Failed to determine creature template.")
        template = generator.choice(available_templates)
        creature_key = template.get("key")
        rarity = template.get("rarity")

    from config import CREATURE_CATALOG, slugify

    candidate_key = creature_key
    if candidate_key not in CREATURE_CATALOG:
        candidate_key = slugify(str(candidate_key))
    
    template = CREATURE_CATALOG.get(candidate_key)
    if not template:
        print(f"[ERROR] Creature key '{candidate_key}' not found in catalog.")
        raise CrateError("Failed to load creature details.")

    creature_payload = {
        "id": int(generator.random() * 1_000_000_000),
        "user_id": user_id,
        "creature_key": template.get("key"),
        "creature_name": template.get("name"),
        "rarity": rarity,
        "image_path": str(get_sprite_path(template.get("key"))),
        "level": level,
        "xp": xp,
        "value_roll": value_roll,
    }
    return {
        "creature": enrich_creature(creature_payload),
        "remaining_tokens": remaining_tokens,
    }
