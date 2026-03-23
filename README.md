# RelmBag Arena

RelmBag Arena is a two-app desktop system built with Python, PyQt5, SQLite, Pillow, and bcrypt:

- `game.py` is the player game app.
- `admin.py` is the separate admin panel app.

The system includes:

- secure signup and login with hashed passwords
- visually richer summon screen with visible rarity odds and base values
- inventory sorting and rarity filtering
- online-player trading with request notifications plus accept and decline flow
- player-to-player Pokemon-style combat with battle requests, one-creature selection, simultaneous move locking, and XP rewards
- a private admin panel for token control and user lookup
- sprite-sheet slicing with a generated demo sheet fallback

## Project Files

- `auth.py`
- `database.py`
- `admin.py`
- `game.py`
- `crate_system.py`
- `inventory.py`
- `trading.py`
- `combat.py`
- `leveling.py`
- `sprite_loader.py`
- `config.py`
- `ui_shared.py`

## Setup

1. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

2. Initialize the database:

```bash
python3 database.py
```

3. Optional: seed demo accounts and starter creatures for testing trades and battles:

```bash
python3 database.py --seed-demo
```

Demo accounts created by the seed command:

- `alpha` / `DemoPass123!`
- `beta` / `DemoPass123!`

Admin login:

- `admin` / `admin123`

## Run The Apps

Player app:

```bash
python3 game.py
```

Admin panel:

```bash
python3 admin.py
```

## PvP Battle Flow

1. Open two player app windows and log in as two different users.
2. In the first window, go to `Fighting`, pick one of your creatures, and click `Battle` beside an online player.
3. In the second window, open `Fighting`, select the incoming challenge, choose a creature, and accept it.
4. Both players pick one move per round. The move is locked in until the other player submits theirs.
5. When both moves are locked, the round resolves automatically using speed order, damage variance, crit chance, and cooldown rules.
6. When one creature reaches `0 HP`, the battle ends and XP is awarded automatically.

You can also cancel pending challenges or forfeit active battles.

## Trading Flow

1. Open two player app windows and log in as two different users.
2. In `Trading`, browse the online player list on the left and click `Trade` on the target player.
3. The recipient gets a trade request notification with `Accept` and `Decline`.
4. After acceptance, both players add creatures or tokens, watch the value comparison, and confirm the trade.

## Sprite Sheet Handling

The system expects a single sprite sheet at:

```text
assets/sprite_sheet.png
```

Expected layout:

- 10 rows, one per rarity
- 5 columns, one creature per rarity row

If no custom sheet is found, the app automatically generates a demo sprite sheet and slices it into individual sprites under:

```text
assets/generated/sprites/
```

`sprite_loader.py` slices the sheet evenly and crops the inner area of each cell so labels and borders are ignored as much as possible.

## Notes

- real name and email stay out of the player app and only appear in the admin panel
- tokens are only changed through admin controls or trade execution
- trade changes reset confirmations automatically
- creatures cannot enter unresolved battles and open trades at the same time
- all key gameplay mutations go through validated backend logic instead of direct UI writes
