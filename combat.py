from __future__ import annotations

import json
import random

import database
import inventory
from config import CREATURE_CATALOG, LOSER_XP, WINNER_XP
from leveling import grant_experience_to_creature, scale_stats


class CombatError(ValueError):
    pass


def build_combatant(creature: dict) -> dict:
    template = CREATURE_CATALOG[creature["creature_key"]]
    stats = scale_stats(template["base_stats"], creature["rarity"], creature["level"])
    unlocked_moves = [move for move in template["moves"] if creature["level"] >= move["unlock_level"]]
    return {
        "id": creature["id"],
        "owner_id": creature["user_id"],
        "name": creature["creature_name"],
        "rarity": creature["rarity"],
        "level": creature["level"],
        "image_path": creature["image_path"],
        "stats": stats,
        "current_hp": stats["HP"],
        "max_hp": stats["HP"],
        "moves": unlocked_moves,
        "cooldowns": {move["name"]: 0 for move in unlocked_moves},
    }


def _available_moves(combatant: dict) -> list[dict]:
    return [move for move in combatant["moves"] if combatant["cooldowns"].get(move["name"], 0) == 0]


def get_move_options(combatant: dict | None) -> list[dict]:
    if not combatant:
        return []
    return [
        {
            **move,
            "remaining_cooldown": combatant["cooldowns"].get(move["name"], 0),
            "available": combatant["cooldowns"].get(move["name"], 0) == 0,
        }
        for move in combatant["moves"]
    ]


def calculate_damage(attacker: dict, defender: dict, move: dict, rng: random.Random) -> dict:
    raw_power = move["damage"] + (attacker["stats"]["Attack"] * 0.9)
    defense_block = defender["stats"]["Defense"] * 0.55
    base_damage = max(1, raw_power - defense_block)
    crit = rng.random() <= 0.10
    variance = rng.uniform(0.90, 1.10)
    total_damage = int(round(base_damage * variance * (1.5 if crit else 1.0)))
    total_damage = max(total_damage, 1)
    return {"damage": total_damage, "critical": crit}


def _select_move(combatant: dict, move_name: str) -> dict:
    for move in _available_moves(combatant):
        if move["name"] == move_name:
            return move
    raise CombatError("That move is unavailable right now.")


def _mark_cooldown(combatant: dict, move: dict) -> None:
    if move["cooldown"] > 0:
        combatant["cooldowns"][move["name"]] = move["cooldown"] + 1


def _tick_cooldowns(*combatants: dict) -> None:
    for combatant in combatants:
        for move_name, remaining in list(combatant["cooldowns"].items()):
            if remaining > 0:
                combatant["cooldowns"][move_name] = remaining - 1


def _turn_order(challenger: dict, opponent: dict, challenger_move: dict, opponent_move: dict, rng: random.Random) -> list[tuple[str, str, dict]]:
    first_role, second_role = "challenger", "opponent"
    first_move, second_move = challenger_move, opponent_move
    if opponent["stats"]["Speed"] > challenger["stats"]["Speed"]:
        first_role, second_role = "opponent", "challenger"
        first_move, second_move = opponent_move, challenger_move
    elif opponent["stats"]["Speed"] == challenger["stats"]["Speed"] and rng.random() < 0.5:
        first_role, second_role = "opponent", "challenger"
        first_move, second_move = opponent_move, challenger_move
    return [(first_role, second_role, first_move), (second_role, first_role, second_move)]


def initialize_battle_state(challenger_creature: dict, opponent_creature: dict) -> dict:
    challenger = build_combatant(challenger_creature)
    opponent = build_combatant(opponent_creature)
    return {
        "round_number": 0,
        "finished": False,
        "winner_role": None,
        "challenger": challenger,
        "opponent": opponent,
        "last_round": [],
        "reward_summary": [],
        "log": [
            f"Battle started between {challenger['name']} and {opponent['name']}.",
            "Both players select a move each round. Speed decides who attacks first.",
        ],
    }


def resolve_round(state: dict, challenger_move_name: str, opponent_move_name: str, rng: random.Random | None = None) -> dict:
    if state.get("finished"):
        raise CombatError("Battle is already finished.")

    generator = rng or random.Random()
    challenger = state["challenger"]
    opponent = state["opponent"]
    challenger_move = _select_move(challenger, challenger_move_name)
    opponent_move = _select_move(opponent, opponent_move_name)

    state["round_number"] += 1
    round_log = [f"Round {state['round_number']}"]

    for attacker_role, defender_role, move in _turn_order(challenger, opponent, challenger_move, opponent_move, generator):
        attacker = state[attacker_role]
        defender = state[defender_role]
        if attacker["current_hp"] <= 0 or defender["current_hp"] <= 0:
            continue

        damage_info = calculate_damage(attacker, defender, move, generator)
        defender["current_hp"] = max(0, defender["current_hp"] - damage_info["damage"])
        crit_text = " Critical hit!" if damage_info["critical"] else ""
        round_log.append(f"{attacker['name']} used {move['name']} for {damage_info['damage']} damage.{crit_text}")
        _mark_cooldown(attacker, move)
        if defender["current_hp"] <= 0:
            round_log.append(f"{defender['name']} was defeated.")

    _tick_cooldowns(challenger, opponent)
    state["last_round"] = round_log
    state["log"].extend(round_log)

    if challenger["current_hp"] <= 0 or opponent["current_hp"] <= 0:
        state["finished"] = True
        state["winner_role"] = "challenger" if challenger["current_hp"] > 0 else "opponent"

    return state


def _serialize_state(state: dict) -> str:
    return json.dumps(state)


def _deserialize_state(payload: str) -> dict:
    return json.loads(payload or "{}")


def _load_battle(connection, battle_id: int):
    return connection.execute(
        """
        SELECT
            b.*,
            challenger.username AS challenger_username,
            opponent.username AS opponent_username
        FROM battles b
        JOIN users challenger ON challenger.id = b.challenger_id
        JOIN users opponent ON opponent.id = b.opponent_id
        WHERE b.id = ?
        """,
        (battle_id,),
    ).fetchone()


def _participant_role(battle, user_id: int) -> tuple[str, str]:
    if battle["challenger_id"] == user_id:
        return "challenger", "opponent"
    if battle["opponent_id"] == user_id:
        return "opponent", "challenger"
    raise CombatError("You are not part of this battle.")


def _ensure_battle_open(battle) -> None:
    if battle is None:
        raise CombatError("Battle not found.")


def _assert_creature_available(connection, creature_id: int, exclude_battle_id: int | None = None) -> None:
    params: list[int] = [creature_id, creature_id]
    query = """
        SELECT id
        FROM battles
        WHERE status IN ('pending', 'active')
          AND (challenger_creature_id = ? OR opponent_creature_id = ?)
    """
    if exclude_battle_id is not None:
        query += " AND id != ?"
        params.append(exclude_battle_id)

    row = connection.execute(query, tuple(params)).fetchone()
    if row is not None:
        raise CombatError("That creature is already locked in another unresolved battle.")

    trade_row = connection.execute(
        """
        SELECT tc.id
        FROM trade_creatures tc
        JOIN trades t ON t.id = tc.trade_id
        WHERE tc.creature_id = ?
          AND t.status = 'open'
        LIMIT 1
        """,
        (creature_id,),
    ).fetchone()
    if trade_row is not None:
        raise CombatError("That creature is currently locked in an open trade.")


def _get_owned_creature(connection, user_id: int, creature_id: int) -> dict:
    row = connection.execute("SELECT * FROM owned_creatures WHERE id = ?", (creature_id,)).fetchone()
    if row is None or row["user_id"] != user_id:
        raise CombatError("You do not own that creature.")
    return inventory.enrich_creature(dict(row))


def _reward_lines(rewards: dict) -> list[str]:
    winner_creature = rewards["winner"]["creature"]
    loser_creature = rewards["loser"]["creature"]
    lines = [
        f"{winner_creature['creature_name']} gained {WINNER_XP} XP.",
        f"{loser_creature['creature_name']} gained {LOSER_XP} XP.",
    ]
    if rewards["winner"]["levels_gained"] > 0:
        lines.append(
            f"Level up! {winner_creature['creature_name']} gained {rewards['winner']['levels_gained']} level(s)."
        )
    if rewards["loser"]["levels_gained"] > 0:
        lines.append(
            f"Level up! {loser_creature['creature_name']} gained {rewards['loser']['levels_gained']} level(s)."
        )
    return lines


def _attach_rewards(state: dict, winner_creature_id: int, loser_creature_id: int) -> dict:
    rewards = grant_battle_rewards(winner_creature_id, loser_creature_id)
    lines = _reward_lines(rewards)
    state["reward_summary"] = lines
    state["log"].extend(lines)
    return rewards


def _build_snapshot(connection, battle_id: int, viewer_id: int | None = None) -> dict:
    battle = _load_battle(connection, battle_id)
    _ensure_battle_open(battle)

    state = _deserialize_state(battle["state_json"])
    challenger_creature = inventory.get_creature(battle["challenger_creature_id"]) if battle["challenger_creature_id"] else None
    opponent_creature = inventory.get_creature(battle["opponent_creature_id"]) if battle["opponent_creature_id"] else None

    snapshot = {
        "id": battle["id"],
        "status": battle["status"],
        "winner_user_id": battle["winner_user_id"],
        "round_number": state.get("round_number", 0),
        "finished": bool(state.get("finished")) or battle["status"] == "completed",
        "log": state.get("log", []),
        "last_round": state.get("last_round", []),
        "reward_summary": state.get("reward_summary", []),
        "created_at": battle["created_at"],
        "updated_at": battle["updated_at"],
        "challenger": {
            "id": battle["challenger_id"],
            "username": battle["challenger_username"],
            "creature": challenger_creature,
            "combatant": state.get("challenger"),
            "move_submitted": bool(battle["challenger_move"]),
        },
        "opponent": {
            "id": battle["opponent_id"],
            "username": battle["opponent_username"],
            "creature": opponent_creature,
            "combatant": state.get("opponent"),
            "move_submitted": bool(battle["opponent_move"]),
        },
    }

    if viewer_id is not None:
        role, other_role = _participant_role(battle, viewer_id)
        snapshot["your_role"] = role
        snapshot["their_role"] = other_role
        snapshot["your_side"] = snapshot[role]
        snapshot["their_side"] = snapshot[other_role]
        snapshot["your_pending_move"] = battle[f"{role}_move"]
        snapshot["their_move_submitted"] = bool(battle[f"{other_role}_move"])
        snapshot["your_move_options"] = get_move_options(snapshot["your_side"]["combatant"])
        snapshot["can_accept"] = battle["status"] == "pending" and role == "opponent"
        snapshot["can_cancel"] = battle["status"] == "pending"
        snapshot["can_submit_moves"] = battle["status"] == "active" and not snapshot["finished"]
        snapshot["can_forfeit"] = battle["status"] == "active" and not snapshot["finished"]
        snapshot["you_won"] = battle["winner_user_id"] == viewer_id if battle["winner_user_id"] else None

    return snapshot


def list_user_battles(user_id: int) -> list[dict]:
    rows = database.fetch_all(
        """
        SELECT
            b.id,
            b.status,
            b.updated_at,
            b.created_at,
            b.challenger_id,
            b.opponent_id,
            CASE
                WHEN b.challenger_id = ? THEN opponent.username
                ELSE challenger.username
            END AS counterpart_username
        FROM battles b
        JOIN users challenger ON challenger.id = b.challenger_id
        JOIN users opponent ON opponent.id = b.opponent_id
        WHERE b.challenger_id = ? OR b.opponent_id = ?
        ORDER BY
            CASE b.status
                WHEN 'active' THEN 0
                WHEN 'pending' THEN 1
                WHEN 'completed' THEN 2
                ELSE 3
            END,
            b.updated_at DESC
        """,
        (user_id, user_id, user_id),
    )
    for row in rows:
        row["direction"] = "outgoing" if row["challenger_id"] == user_id else "incoming"
    return rows


def list_incoming_battle_requests(user_id: int) -> list[dict]:
    return database.fetch_all(
        """
        SELECT
            b.id,
            b.created_at,
            b.updated_at,
            challenger.username AS from_username
        FROM battles b
        JOIN users challenger ON challenger.id = b.challenger_id
        WHERE b.opponent_id = ?
          AND b.status = 'pending'
        ORDER BY b.updated_at DESC
        """,
        (user_id,),
    )


def create_battle(challenger_id: int, opponent_username: str, challenger_creature_id: int) -> dict:
    database.initialize_database()

    with database.transaction() as connection:
        opponent = connection.execute(
            "SELECT id, username FROM users WHERE username = ? COLLATE NOCASE",
            (opponent_username.strip(),),
        ).fetchone()
        if opponent is None:
            raise CombatError("That opponent does not exist.")
        if opponent["id"] == challenger_id:
            raise CombatError("You cannot battle yourself.")

        existing = connection.execute(
            """
            SELECT id
            FROM battles
            WHERE status IN ('pending', 'active')
              AND (
                  (challenger_id = ? AND opponent_id = ?)
                  OR
                  (challenger_id = ? AND opponent_id = ?)
              )
            LIMIT 1
            """,
            (challenger_id, opponent["id"], opponent["id"], challenger_id),
        ).fetchone()
        if existing is not None:
            raise CombatError("There is already an unresolved battle between these players.")

        _get_owned_creature(connection, challenger_id, challenger_creature_id)
        _assert_creature_available(connection, challenger_creature_id)

        cursor = connection.execute(
            """
            INSERT INTO battles (
                challenger_id,
                opponent_id,
                challenger_creature_id,
                state_json
            )
            VALUES (?, ?, ?, '{}')
            """,
            (challenger_id, opponent["id"], challenger_creature_id),
        )
        return _build_snapshot(connection, int(cursor.lastrowid), challenger_id)


def get_battle(battle_id: int, viewer_id: int | None = None) -> dict:
    with database.get_connection() as connection:
        return _build_snapshot(connection, battle_id, viewer_id)


def accept_battle(battle_id: int, user_id: int, creature_id: int) -> dict:
    with database.transaction() as connection:
        battle = _load_battle(connection, battle_id)
        _ensure_battle_open(battle)
        role, _other_role = _participant_role(battle, user_id)
        if role != "opponent":
            raise CombatError("Only the challenged player can accept this battle.")
        if battle["status"] != "pending":
            raise CombatError("This battle is no longer waiting for acceptance.")

        challenger_creature = _get_owned_creature(connection, battle["challenger_id"], battle["challenger_creature_id"])
        opponent_creature = _get_owned_creature(connection, user_id, creature_id)
        _assert_creature_available(connection, creature_id, exclude_battle_id=battle_id)

        state = initialize_battle_state(challenger_creature, opponent_creature)
        connection.execute(
            """
            UPDATE battles
            SET opponent_creature_id = ?,
                status = 'active',
                state_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (creature_id, _serialize_state(state), battle_id),
        )
        return _build_snapshot(connection, battle_id, user_id)


def cancel_battle(battle_id: int, user_id: int) -> None:
    with database.transaction() as connection:
        battle = _load_battle(connection, battle_id)
        _ensure_battle_open(battle)
        _participant_role(battle, user_id)
        if battle["status"] != "pending":
            raise CombatError("Only pending challenges can be cancelled.")
        connection.execute(
            """
            UPDATE battles
            SET status = 'cancelled',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (battle_id,),
        )


def submit_move(battle_id: int, user_id: int, move_name: str) -> dict:
    with database.transaction() as connection:
        battle = _load_battle(connection, battle_id)
        _ensure_battle_open(battle)
        role, other_role = _participant_role(battle, user_id)
        if battle["status"] != "active":
            raise CombatError("This battle is not active.")

        state = _deserialize_state(battle["state_json"])
        if state.get("finished"):
            raise CombatError("Battle is already finished.")

        _select_move(state[role], move_name)
        my_column = f"{role}_move"
        other_column = f"{other_role}_move"
        other_move = battle[other_column]

        if other_move:
            updated_state = resolve_round(state, move_name if role == "challenger" else other_move, other_move if role == "challenger" else move_name)
            update_params: list = [
                _serialize_state(updated_state),
                None,
                None,
                battle_id,
            ]
            update_sql = """
                UPDATE battles
                SET state_json = ?,
                    challenger_move = ?,
                    opponent_move = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """

            if updated_state.get("finished"):
                winner_role = updated_state["winner_role"]
                loser_role = "opponent" if winner_role == "challenger" else "challenger"
                winner_creature_id = updated_state[winner_role]["id"]
                loser_creature_id = updated_state[loser_role]["id"]
                _attach_rewards(updated_state, winner_creature_id, loser_creature_id)
                winner_user_id = battle["challenger_id"] if winner_role == "challenger" else battle["opponent_id"]
                update_sql = """
                    UPDATE battles
                    SET status = 'completed',
                        state_json = ?,
                        challenger_move = ?,
                        opponent_move = ?,
                        winner_user_id = ?,
                        xp_awarded = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """
                update_params = [
                    _serialize_state(updated_state),
                    None,
                    None,
                    winner_user_id,
                    battle_id,
                ]
            connection.execute(update_sql, tuple(update_params))
        else:
            connection.execute(
                f"""
                UPDATE battles
                SET {my_column} = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (move_name, battle_id),
            )

        return _build_snapshot(connection, battle_id, user_id)


def forfeit_battle(battle_id: int, user_id: int) -> dict:
    with database.transaction() as connection:
        battle = _load_battle(connection, battle_id)
        _ensure_battle_open(battle)
        role, other_role = _participant_role(battle, user_id)
        if battle["status"] != "active":
            raise CombatError("Only active battles can be forfeited.")

        state = _deserialize_state(battle["state_json"])
        if state.get("finished"):
            raise CombatError("Battle is already finished.")

        state["finished"] = True
        state["winner_role"] = other_role
        line = f"{battle[f'{role}_username']} forfeited. {battle[f'{other_role}_username']} wins the battle."
        state["last_round"] = [line]
        state["log"].append(line)

        winner_creature_id = state[other_role]["id"]
        loser_creature_id = state[role]["id"]
        _attach_rewards(state, winner_creature_id, loser_creature_id)
        winner_user_id = battle["challenger_id"] if other_role == "challenger" else battle["opponent_id"]

        connection.execute(
            """
            UPDATE battles
            SET status = 'completed',
                state_json = ?,
                challenger_move = NULL,
                opponent_move = NULL,
                winner_user_id = ?,
                xp_awarded = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (_serialize_state(state), winner_user_id, battle_id),
        )
        return _build_snapshot(connection, battle_id, user_id)


def grant_battle_rewards(winner_creature_id: int, loser_creature_id: int) -> dict:
    winner_result = grant_experience_to_creature(winner_creature_id, WINNER_XP)
    loser_result = grant_experience_to_creature(loser_creature_id, LOSER_XP)
    return {"winner": winner_result, "loser": loser_result}


def award_battle_xp(player_creature_id: int, opponent_creature_id: int, winner: str) -> dict:
    if winner not in {"player", "opponent"}:
        raise ValueError("Winner must be 'player' or 'opponent'.")

    if winner == "player":
        winner_id, loser_id = player_creature_id, opponent_creature_id
    else:
        winner_id, loser_id = opponent_creature_id, player_creature_id

    return grant_battle_rewards(winner_id, loser_id)
