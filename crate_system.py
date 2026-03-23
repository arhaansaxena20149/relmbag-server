from __future__ import annotations

import random

import database
from config import CRATE_COST, CREATURES_BY_RARITY, DROP_RATES, RARITY_ORDER
from inventory import get_creature
from sprite_loader import get_sprite_path


class CrateError(ValueError):
    pass


def roll_rarity(rng: random.Random | None = None) -> str:
    generator = rng or random
    return generator.choices(RARITY_ORDER, weights=[DROP_RATES[rarity] for rarity in RARITY_ORDER], k=1)[0]


def grant_creature(user_id: int, creature_key: str, level: int = 1, rng: random.Random | None = None) -> dict:
    from config import CREATURE_CATALOG

    generator = rng or random
    template = CREATURE_CATALOG[creature_key]
    value_roll = round(generator.uniform(0.90, 1.10), 4)
    creature_id = database.insert_creature(
        user_id=user_id,
        creature_key=template["key"],
        creature_name=template["name"],
        rarity=template["rarity"],
        image_path=str(get_sprite_path(template["key"])),
        value_roll=value_roll,
        level=level,
    )
    return get_creature(creature_id)


def open_crate(user_id: int, rng: random.Random | None = None) -> dict:
    database.initialize_database()
    generator = rng or random

    with database.transaction() as connection:
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise CrateError("User not found.")
        if user["tokens"] < CRATE_COST:
            raise CrateError("Not enough tokens.")

        rarity = roll_rarity(generator)
        template = generator.choice(CREATURES_BY_RARITY[rarity])
        value_roll = round(generator.uniform(0.90, 1.10), 4)
        connection.execute("UPDATE users SET tokens = tokens - ? WHERE id = ?", (CRATE_COST, user_id))
        cursor = connection.execute(
            """
            INSERT INTO owned_creatures (
                user_id,
                creature_key,
                creature_name,
                rarity,
                image_path,
                level,
                xp,
                value_roll
            )
            VALUES (?, ?, ?, ?, ?, 1, 0, ?)
            """,
            (
                user_id,
                template["key"],
                template["name"],
                template["rarity"],
                str(get_sprite_path(template["key"])),
                value_roll,
            ),
        )
        creature_id = int(cursor.lastrowid)
        remaining_tokens = user["tokens"] - CRATE_COST

    return {
        "creature": get_creature(creature_id),
        "remaining_tokens": remaining_tokens,
        "crate_cost": CRATE_COST,
    }
