from __future__ import annotations

import database
from inventory import enrich_creature


class TradeError(ValueError):
    pass


def _load_trade(connection, trade_id: int):
    return connection.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()


def _participant_side(trade, user_id: int) -> tuple[str, str, int]:
    # FIX: Defensive dictionary access
    if not trade:
        raise TradeError("Trade data is missing.")
        
    if trade.get("initiator_id") == user_id:
        return "initiator_tokens", "initiator_confirmed", trade.get("recipient_id")
    if trade.get("recipient_id") == user_id:
        return "recipient_tokens", "recipient_confirmed", trade.get("initiator_id")
    raise TradeError("You are not part of this trade.")


def _assert_trade_open(trade) -> None:
    if trade is None:
        raise TradeError("Trade not found.")
    if trade.get("status") != "open":
        raise TradeError("This trade is no longer open.")


def _assert_trade_pending(trade) -> None:
    if trade is None:
        raise TradeError("Trade not found.")
    if trade.get("status") != "pending":
        raise TradeError("This trade request is no longer pending.")


def _reset_confirmations(connection, trade_id: int) -> None:
    connection.execute(
        """
        UPDATE trades
        SET initiator_confirmed = 0,
            recipient_confirmed = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (trade_id,),
    )


def _validate_trade_state(connection, trade) -> None:
    initiator_id = trade.get("initiator_id")
    recipient_id = trade.get("recipient_id")
    
    participants = connection.execute(
        "SELECT id, tokens FROM users WHERE id IN (?, ?)",
        (initiator_id, recipient_id),
    ).fetchall()
    balances = {row["id"]: row["tokens"] for row in participants}
    
    if balances.get(initiator_id, 0) < trade.get("initiator_tokens", 0):
        raise TradeError("Initiator no longer has enough tokens.")
    if balances.get(recipient_id, 0) < trade.get("recipient_tokens", 0):
        raise TradeError("Recipient no longer has enough tokens.")

    offered = connection.execute(
        """
        SELECT tc.user_id, tc.creature_id, oc.user_id AS owner_id
        FROM trade_creatures tc
        JOIN owned_creatures oc ON oc.id = tc.creature_id
        WHERE tc.trade_id = ?
        """,
        (trade.get("id"),),
    ).fetchall()

    for row in offered:
        if row["user_id"] != row["owner_id"]:
            raise TradeError("One of the creatures in this trade is no longer owned by the offering player.")


def _calculate_trade_totals(initiator_creatures: list[dict], recipient_creatures: list[dict], trade: dict) -> dict:
    initiator_value = sum(creature.get("value", 0) for creature in initiator_creatures) + trade.get("initiator_tokens", 0)
    recipient_value = sum(creature.get("value", 0) for creature in recipient_creatures) + trade.get("recipient_tokens", 0)
    high = max(initiator_value, recipient_value, 1)
    delta = abs(initiator_value - recipient_value) / high
    if delta <= 0.10:
        fairness = {"label": "Fair", "color": "#5ED36E"}
    elif delta <= 0.25:
        fairness = {"label": "Close", "color": "#F2C14E"}
    else:
        fairness = {"label": "Unfair", "color": "#F06363"}
    fairness["delta_percent"] = round(delta * 100, 1)
    fairness["initiator_value"] = initiator_value
    fairness["recipient_value"] = recipient_value
    return fairness


def _trade_snapshot(connection, trade_id: int, viewer_id: int | None = None) -> dict:
    trade_row = _load_trade(connection, trade_id)
    if trade_row is None:
        raise TradeError("Trade not found.")

    initiator_id = trade_row.get("initiator_id")
    recipient_id = trade_row.get("recipient_id")

    initiator = connection.execute(
        "SELECT id, username FROM users WHERE id = ?",
        (initiator_id,),
    ).fetchone()
    recipient = connection.execute(
        "SELECT id, username FROM users WHERE id = ?",
        (recipient_id,),
    ).fetchone()
    
    if initiator is None or recipient is None:
        raise TradeError("Trade participants not found.")

    offered = connection.execute(
        """
        SELECT tc.user_id AS offered_by_user_id, oc.*
        FROM trade_creatures tc
        JOIN owned_creatures oc ON oc.id = tc.creature_id
        WHERE tc.trade_id = ?
        ORDER BY oc.level DESC, oc.creature_name COLLATE NOCASE
        """,
        (trade_id,),
    ).fetchall()

    initiator_creatures = [
        enrich_creature(dict(row))
        for row in offered
        if row["offered_by_user_id"] == initiator_id
    ]
    recipient_creatures = [
        enrich_creature(dict(row))
        for row in offered
        if row["offered_by_user_id"] == recipient_id
    ]
    fairness = _calculate_trade_totals(initiator_creatures, recipient_creatures, dict(trade_row))

    snapshot = {
        "id": trade_row.get("id"),
        "status": trade_row.get("status"),
        "initiator": {
            "id": initiator.get("id"),
            "username": initiator.get("username"),
            "tokens": trade_row.get("initiator_tokens", 0),
            "confirmed": bool(trade_row.get("initiator_confirmed")),
            "creatures": initiator_creatures,
        },
        "recipient": {
            "id": recipient.get("id"),
            "username": recipient.get("username"),
            "tokens": trade_row.get("recipient_tokens", 0),
            "confirmed": bool(trade_row.get("recipient_confirmed")),
            "creatures": recipient_creatures,
        },
        "fairness": fairness,
        "created_at": trade_row.get("created_at"),
        "updated_at": trade_row.get("updated_at"),
    }

    if viewer_id is not None:
        initiator_data = snapshot.get("initiator")
        recipient_data = snapshot.get("recipient")
        
        if initiator_data and initiator_data.get("id") == viewer_id:
            viewer_role = "initiator"
            snapshot["your_side"] = initiator_data
            snapshot["their_side"] = recipient_data
        elif recipient_data and recipient_data.get("id") == viewer_id:
            viewer_role = "recipient"
            snapshot["your_side"] = recipient_data
            snapshot["their_side"] = initiator_data
        else:
            raise TradeError("You are not part of this trade.")
        snapshot["viewer_role"] = viewer_role
        snapshot["can_accept"] = trade_row.get("status") == "pending" and viewer_role == "recipient"
        snapshot["can_decline"] = trade_row.get("status") == "pending" and viewer_role == "recipient"
        snapshot["can_cancel_request"] = trade_row.get("status") == "pending" and viewer_role == "initiator"
        snapshot["can_edit_offer"] = trade_row.get("status") == "open"
        snapshot["can_confirm"] = trade_row.get("status") == "open"

    return snapshot


def list_user_trades(user_id: int) -> list[dict]:
    rows = database.fetch_all(
        """
        SELECT
            t.id,
            t.status,
            t.initiator_id,
            t.recipient_id,
            t.initiator_confirmed,
            t.recipient_confirmed,
            CASE
                WHEN t.initiator_id = ? THEN recipient.username
                ELSE initiator.username
            END AS counterpart_username,
            t.updated_at
        FROM trades t
        JOIN users initiator ON initiator.id = t.initiator_id
        JOIN users recipient ON recipient.id = t.recipient_id
        WHERE t.initiator_id = ? OR t.recipient_id = ?
        ORDER BY
            CASE
                WHEN t.status = 'pending' AND t.recipient_id = ? THEN 0
                WHEN t.status = 'open' THEN 1
                WHEN t.status = 'pending' THEN 2
                WHEN t.status = 'completed' THEN 3
                ELSE 4
            END,
            t.updated_at DESC
        """,
        (user_id, user_id, user_id, user_id),
    )
    for row in rows:
        row["direction"] = "outgoing" if row["initiator_id"] == user_id else "incoming"
    return rows


def list_incoming_trade_requests(user_id: int) -> list[dict]:
    return database.fetch_all(
        """
        SELECT
            t.id,
            t.created_at,
            t.updated_at,
            initiator.username AS from_username
        FROM trades t
        JOIN users initiator ON initiator.id = t.initiator_id
        WHERE t.recipient_id = ?
          AND t.status = 'pending'
        ORDER BY t.updated_at DESC
        """,
        (user_id,),
    )


def create_trade(initiator_id: int, recipient_username: str) -> dict:
    database.initialize_database()
    recipient = database.get_user_by_username(recipient_username.strip())
    if recipient is None:
        raise TradeError("That user does not exist.")
    if recipient["id"] == initiator_id:
        raise TradeError("You cannot trade with yourself.")

    with database.transaction() as connection:
        existing = connection.execute(
            """
            SELECT id
            FROM trades
            WHERE status IN ('pending', 'open')
              AND (
                  (initiator_id = ? AND recipient_id = ?)
                  OR
                  (initiator_id = ? AND recipient_id = ?)
              )
            LIMIT 1
            """,
            (initiator_id, recipient.get("id"), recipient.get("id"), initiator_id),
        ).fetchone()

        if existing is not None:
            trade_id = existing.get("id")
        else:
            cursor = connection.execute(
                """
                INSERT INTO trades (initiator_id, recipient_id, status)
                VALUES (?, ?, 'pending')
                """,
                (initiator_id, recipient.get("id")),
            )
            trade_id = int(cursor.lastrowid)
        return _trade_snapshot(connection, trade_id, initiator_id)


def get_trade(trade_id: int, viewer_id: int | None = None) -> dict:
    with database.get_connection() as connection:
        return _trade_snapshot(connection, trade_id, viewer_id)


def accept_trade_request(trade_id: int, user_id: int) -> dict:
    with database.transaction() as connection:
        trade = _load_trade(connection, trade_id)
        _assert_trade_pending(trade)
        if trade.get("recipient_id") != user_id:
            raise TradeError("Only the recipient can accept this trade request.")
        connection.execute(
            """
            UPDATE trades
            SET status = 'open',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (trade_id,),
        )
        return _trade_snapshot(connection, trade_id, user_id)


def decline_trade_request(trade_id: int, user_id: int) -> None:
    with database.transaction() as connection:
        trade = _load_trade(connection, trade_id)
        _assert_trade_pending(trade)
        if trade.get("recipient_id") != user_id:
            raise TradeError("Only the recipient can decline this trade request.")
        connection.execute(
            """
            UPDATE trades
            SET status = 'declined',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (trade_id,),
        )


def set_trade_tokens(trade_id: int, user_id: int, token_amount: int) -> dict:
    if token_amount < 0:
        raise TradeError("Token offers cannot be negative.")

    with database.transaction() as connection:
        trade = _load_trade(connection, trade_id)
        _assert_trade_open(trade)
        token_column, _confirm_column, _other_user_id = _participant_side(trade, user_id)
        user = connection.execute("SELECT tokens FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise TradeError("User not found.")
        if token_amount > user.get("tokens", 0):
            raise TradeError("You do not have that many tokens.")

        connection.execute(
            f"UPDATE trades SET {token_column} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (token_amount, trade_id),
        )
        _reset_confirmations(connection, trade_id)
        return _trade_snapshot(connection, trade_id, user_id)


def add_creature_to_trade(trade_id: int, user_id: int, creature_id: int) -> dict:
    with database.transaction() as connection:
        trade = _load_trade(connection, trade_id)
        _assert_trade_open(trade)
        _participant_side(trade, user_id)

        creature = connection.execute("SELECT * FROM owned_creatures WHERE id = ?", (creature_id,)).fetchone()
        if creature is None or creature["user_id"] != user_id:
            raise TradeError("You do not own that creature.")

        in_open_trade = connection.execute(
            """
            SELECT tc.id
            FROM trade_creatures tc
            JOIN trades t ON t.id = tc.trade_id
            WHERE tc.creature_id = ?
              AND t.status = 'open'
              AND tc.trade_id != ?
            LIMIT 1
            """,
            (creature_id, trade_id),
        ).fetchone()
        if in_open_trade is not None:
            raise TradeError("That creature is already locked in another open trade.")

        in_open_battle = connection.execute(
            """
            SELECT id
            FROM battles
            WHERE status IN ('pending', 'active')
              AND (challenger_creature_id = ? OR opponent_creature_id = ?)
            LIMIT 1
            """,
            (creature_id, creature_id),
        ).fetchone()
        if in_open_battle is not None:
            raise TradeError("That creature is currently locked in an unresolved battle.")

        duplicate = connection.execute(
            "SELECT id FROM trade_creatures WHERE trade_id = ? AND creature_id = ?",
            (trade_id, creature_id),
        ).fetchone()
        if duplicate is not None:
            raise TradeError("That creature is already in this trade.")

        connection.execute(
            """
            INSERT INTO trade_creatures (trade_id, user_id, creature_id)
            VALUES (?, ?, ?)
            """,
            (trade_id, user_id, creature_id),
        )
        _reset_confirmations(connection, trade_id)
        return _trade_snapshot(connection, trade_id, user_id)


def remove_creature_from_trade(trade_id: int, user_id: int, creature_id: int) -> dict:
    with database.transaction() as connection:
        trade = _load_trade(connection, trade_id)
        _assert_trade_open(trade)
        _participant_side(trade, user_id)

        deleted = connection.execute(
            """
            DELETE FROM trade_creatures
            WHERE trade_id = ? AND user_id = ? AND creature_id = ?
            """,
            (trade_id, user_id, creature_id),
        )
        if deleted.rowcount == 0:
            raise TradeError("That creature is not in your offer.")
        _reset_confirmations(connection, trade_id)
        return _trade_snapshot(connection, trade_id, user_id)


def _execute_trade(connection, trade) -> None:
    _validate_trade_state(connection, trade)
    initiator_id = trade["initiator_id"]
    recipient_id = trade["recipient_id"]

    connection.execute(
        """
        UPDATE users
        SET tokens = CASE
            WHEN id = ? THEN tokens - ? + ?
            WHEN id = ? THEN tokens - ? + ?
            ELSE tokens
        END
        WHERE id IN (?, ?)
        """,
        (
            initiator_id,
            trade["initiator_tokens"],
            trade["recipient_tokens"],
            recipient_id,
            trade["recipient_tokens"],
            trade["initiator_tokens"],
            initiator_id,
            recipient_id,
        ),
    )

    initiator_offers = connection.execute(
        "SELECT creature_id FROM trade_creatures WHERE trade_id = ? AND user_id = ?",
        (trade["id"], initiator_id),
    ).fetchall()
    recipient_offers = connection.execute(
        "SELECT creature_id FROM trade_creatures WHERE trade_id = ? AND user_id = ?",
        (trade["id"], recipient_id),
    ).fetchall()

    for row in initiator_offers:
        connection.execute(
            "UPDATE owned_creatures SET user_id = ? WHERE id = ?",
            (recipient_id, row["creature_id"]),
        )
    for row in recipient_offers:
        connection.execute(
            "UPDATE owned_creatures SET user_id = ? WHERE id = ?",
            (initiator_id, row["creature_id"]),
        )

    connection.execute(
        """
        UPDATE trades
        SET status = 'completed',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (trade["id"],),
    )


def confirm_trade(trade_id: int, user_id: int) -> dict:
    with database.transaction() as connection:
        trade = _load_trade(connection, trade_id)
        _assert_trade_open(trade)
        _validate_trade_state(connection, trade)
        _token_column, confirm_column, _other_user_id = _participant_side(trade, user_id)
        connection.execute(
            f"UPDATE trades SET {confirm_column} = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (trade_id,),
        )

        updated_trade = _load_trade(connection, trade_id)
        if updated_trade["initiator_confirmed"] and updated_trade["recipient_confirmed"]:
            _execute_trade(connection, updated_trade)
        return _trade_snapshot(connection, trade_id, user_id)


def cancel_trade(trade_id: int, user_id: int) -> None:
    with database.transaction() as connection:
        trade = _load_trade(connection, trade_id)
        if trade is None:
            raise TradeError("Trade not found.")
        _participant_side(trade, user_id)
        if trade["status"] not in {"pending", "open"}:
            raise TradeError("This trade can no longer be cancelled.")
        connection.execute(
            "UPDATE trades SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (trade_id,),
        )
