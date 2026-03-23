from __future__ import annotations

import random

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover
    import http_client as requests

SERVER_URL = "https://relmbag-server.onrender.com"

from config import CRATE_COST, CREATURES_BY_RARITY, DROP_RATES, RARITY_ORDER
from inventory import enrich_creature
from sprite_loader import get_sprite_path


class CrateError(ValueError):
    pass


def roll_rarity(rng: random.Random | None = None) -> str:
    generator = rng or random
    return generator.choices(RARITY_ORDER, weights=[DROP_RATES[rarity] for rarity in RARITY_ORDER], k=1)[0]


def grant_creature(user_id: int, creature_key: str, level: int = 1, rng: random.Random | None = None) -> dict:
    from config import CREATURE_CATALOG, slugify

    generator = rng or random
    candidate_key = creature_key
    if candidate_key not in CREATURE_CATALOG:
        candidate_key = slugify(str(candidate_key))
    template = CREATURE_CATALOG[candidate_key]
    value_roll = round(generator.uniform(0.90, 1.10), 4)
    creature_payload = {
        # `id` is only used by UI selection and local/offline systems; server treats identity as username.
        "id": int(generator.random() * 1_000_000_000),
        "user_id": user_id,
        "creature_key": template["key"],
        "creature_name": template["name"],
        "rarity": template["rarity"],
        "image_path": str(get_sprite_path(template["key"])),
        "level": level,
        "xp": 0,
        "value_roll": value_roll,
    }
    return enrich_creature(creature_payload)


def open_crate(user_id: int, rng: random.Random | None = None) -> dict:
    generator = rng or random
    username = str(user_id)

    try:
        response = requests.post(f"{SERVER_URL}/open_crate", json={"username": username}, timeout=10)
    except Exception as error:
        raise CrateError("Could not open crate.") from error

    payload = None
    try:
        payload = response.json()
    except Exception:
        payload = None

    if not response.ok or not isinstance(payload, dict) or payload.get("status") != "success":
        message = ""
        if isinstance(payload, dict):
            message = str(payload.get("error") or payload.get("message") or payload.get("detail") or "")
        message_l = message.lower()
        if response.status_code == 404 or "user" in message_l and "not found" in message_l:
            raise CrateError("User not found.")
        if "not enough tokens" in message_l or ("tokens" in message_l and "not" in message_l and "enough" in message_l):
            raise CrateError("Not enough tokens.")
        raise CrateError(message.strip() or "Could not open crate.")

    rarity = payload.get("rarity")
    creature_key = payload.get("creature")
    level_provided = payload.get("level", None) is not None
    xp_provided = payload.get("xp", None) is not None
    value_roll_provided = payload.get("value_roll", None) is not None

    level = int(payload.get("level", 1) or 1)
    xp = int(payload.get("xp", 0) or 0)
    value_roll = float(payload.get("value_roll", 1.0) or 1.0)
    remaining_tokens = payload.get("remaining_tokens", payload.get("tokens"))

    # If the server doesn't include extra creature stats, fall back to local defaults.
    if not creature_key:
        # If `creature` isn't included, attempt to infer from rarity (best-effort).
        rarity = rarity or roll_rarity(generator)
        template = generator.choice(CREATURES_BY_RARITY[rarity])
        creature_key = template["key"]
        rarity = template["rarity"]

    from config import CREATURE_CATALOG, slugify

    candidate_key = creature_key
    if candidate_key not in CREATURE_CATALOG:
        candidate_key = slugify(str(candidate_key))
    template = CREATURE_CATALOG[candidate_key]

    # If the server omitted creature stats in the crate response, look up the
    # creature in the user's inventory and use the best match we can.
    if not (level_provided and xp_provided and value_roll_provided):
        try:
            inv_resp = requests.get(f"{SERVER_URL}/inventory/{username}", timeout=10)
            inv_payload = inv_resp.json() if inv_resp.ok else None
            if isinstance(inv_payload, list) and candidate_key:
                best_score: tuple[int, int] | None = None
                best_match: dict | None = None
                for item in inv_payload:
                    if not isinstance(item, dict):
                        continue
                    item_key = item.get("creature") or item.get("creature_key")
                    if not item_key:
                        continue
                    item_candidate = item_key if item_key in CREATURE_CATALOG else slugify(str(item_key))
                    if item_candidate != candidate_key:
                        continue
                    item_rarity = item.get("rarity") or CREATURE_CATALOG[candidate_key].get("rarity")
                    if rarity is not None and item_rarity != rarity:
                        continue
                    item_level = int(item.get("level", 0) or 0)
                    item_xp = int(item.get("xp", 0) or 0)
                    score = (item_level, item_xp)
                    if best_score is None or score > best_score:
                        best_score = score
                        best_match = item
                if isinstance(best_match, dict):
                    level = int(best_match.get("level", level) or level)
                    xp = int(best_match.get("xp", xp) or xp)
                    value_roll = float(best_match.get("value_roll", value_roll) or value_roll)
        except Exception:
            pass

    creature_payload = {
        "id": int(generator.random() * 1_000_000_000),
        "user_id": user_id,
        "creature_key": template["key"],
        "creature_name": template["name"],
        "rarity": rarity or template["rarity"],
        "image_path": str(get_sprite_path(template["key"])),
        "level": level,
        "xp": xp,
        "value_roll": value_roll,
    }

    return {
        "creature": enrich_creature(creature_payload),
        "remaining_tokens": int(remaining_tokens) if remaining_tokens is not None else 0,
        "crate_cost": CRATE_COST,
    }
