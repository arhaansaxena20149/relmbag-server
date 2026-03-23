from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from config import (
    CREATURES_BY_RARITY,
    DEMO_SPRITE_SHEET_PATH,
    RARITY_COLORS,
    RARITY_ORDER,
    SPRITE_OUTPUT_DIR,
    THEME_COLORS,
    USER_SPRITE_SHEET_PATH,
    ensure_directories,
)

CELL_WIDTH = 220
CELL_HEIGHT = 220
SPRITE_SIZE = 128
COMPOSITE_LEFT_COLUMNS = [(97, 209), (220, 329), (342, 450), (462, 571), (583, 691)]
COMPOSITE_RIGHT_COLUMNS = [(754, 865), (881, 992), (1008, 1118), (1134, 1245), (1261, 1370)]
COMPOSITE_ROWS = [(14, 101), (105, 194), (198, 288), (291, 381), (384, 474), (477, 568)]
COMPOSITE_RARITY_POSITIONS = {
    "Common": ("left", 0),
    "Uncommon": ("left", 1),
    "Rare": ("left", 2),
    "Epic": ("left", 3),
    "Legendary": ("left", 4),
    "Mythic": ("left", 5),
    "Godly": ("right", 2),
    "Celestial": ("right", 3),
    "Multiversal": ("right", 4),
    "Ultimate": ("right", 5),
}


def _hex_to_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4)) + (alpha,)


def _draw_motif(draw: ImageDraw.ImageDraw, bounds: tuple[int, int, int, int], theme: str, accent: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = bounds
    center_x = (left + right) // 2
    center_y = (top + bottom) // 2
    width = right - left
    height = bottom - top
    light = (255, 255, 255, 220)
    shadow = (20, 22, 34, 140)

    if theme == "stone":
        draw.polygon(
            [
                (center_x, top + 8),
                (right - 18, top + 48),
                (right - 32, bottom - 20),
                (left + 32, bottom - 20),
                (left + 18, top + 48),
            ],
            fill=accent,
            outline=light,
            width=4,
        )
    elif theme == "nature":
        draw.ellipse((left + 30, top + 35, center_x + 10, bottom - 22), fill=accent, outline=light, width=4)
        draw.ellipse((center_x - 10, top + 18, right - 26, bottom - 48), fill=accent, outline=light, width=4)
        draw.line((center_x, bottom - 20, center_x, top + 26), fill=light, width=5)
    elif theme == "wind":
        for offset in (16, 36, 56):
            draw.arc((left + 18, top + offset, right - 18, bottom - 10 + offset), 190, 350, fill=accent, width=6)
    elif theme == "beast":
        draw.ellipse((center_x - 28, top + 26, center_x + 28, top + 82), fill=accent, outline=light, width=4)
        for paw_x in (left + 36, left + 70, right - 70, right - 36):
            draw.ellipse((paw_x - 14, top + 6, paw_x + 14, top + 32), fill=accent, outline=light, width=3)
    elif theme == "water":
        draw.polygon(
            [
                (center_x, top + 10),
                (right - 36, center_y + 20),
                (center_x, bottom - 12),
                (left + 36, center_y + 20),
            ],
            fill=accent,
            outline=light,
            width=4,
        )
    elif theme == "flame":
        draw.polygon(
            [
                (center_x, top + 8),
                (right - 38, center_y),
                (center_x + 12, bottom - 10),
                (center_x - 4, center_y + 10),
                (left + 42, bottom - 14),
                (left + 52, center_y - 10),
            ],
            fill=accent,
            outline=light,
            width=4,
        )
    elif theme == "electric":
        draw.polygon(
            [
                (center_x - 8, top + 10),
                (right - 44, center_y - 10),
                (center_x + 2, center_y - 10),
                (right - 62, bottom - 14),
                (center_x - 4, center_y + 8),
                (left + 40, center_y + 8),
            ],
            fill=accent,
            outline=light,
            width=4,
        )
    elif theme == "ice":
        draw.line((center_x, top + 10, center_x, bottom - 10), fill=light, width=5)
        draw.line((left + 30, center_y, right - 30, center_y), fill=light, width=5)
        draw.line((left + 44, top + 34, right - 44, bottom - 34), fill=accent, width=5)
        draw.line((right - 44, top + 34, left + 44, bottom - 34), fill=accent, width=5)
    elif theme == "earth":
        draw.polygon([(left + 20, bottom - 18), (center_x - 18, top + 26), (center_x + 8, bottom - 18)], fill=accent, outline=light, width=4)
        draw.polygon([(center_x - 4, bottom - 18), (right - 20, top + 20), (right - 6, bottom - 18)], fill=shadow, outline=light, width=4)
    elif theme == "shadow":
        draw.ellipse((left + 28, top + 26, right - 28, bottom - 26), fill=accent, outline=light, width=4)
        draw.ellipse((center_x - 16, center_y - 10, center_x + 16, center_y + 10), fill=light)
    elif theme == "dragon":
        draw.polygon([(center_x, top + 8), (right - 24, center_y + 6), (center_x + 8, center_y - 12), (right - 40, bottom - 20)], fill=accent, outline=light, width=4)
        draw.polygon([(center_x, top + 8), (left + 24, center_y + 6), (center_x - 8, center_y - 12), (left + 40, bottom - 20)], fill=accent, outline=light, width=4)
        draw.line((center_x, center_y - 10, center_x, bottom - 14), fill=light, width=5)
    elif theme == "light":
        draw.ellipse((left + 24, top + 20, right - 24, bottom - 24), outline=light, width=8)
        draw.line((center_x, top + 8, center_x, bottom - 10), fill=accent, width=6)
        draw.line((left + 22, center_y, right - 22, center_y), fill=accent, width=6)
    elif theme == "void":
        draw.ellipse((left + 18, top + 18, right - 18, bottom - 18), fill=shadow, outline=accent, width=6)
        draw.ellipse((left + 54, top + 54, right - 54, bottom - 54), fill=(8, 8, 14, 255), outline=light, width=3)
    elif theme == "cosmic":
        draw.ellipse((center_x - 40, center_y - 40, center_x + 40, center_y + 40), fill=accent, outline=light, width=4)
        for star_x, star_y in ((left + 44, top + 44), (right - 38, top + 56), (right - 50, bottom - 46), (left + 58, bottom - 56)):
            draw.line((star_x - 8, star_y, star_x + 8, star_y), fill=light, width=3)
            draw.line((star_x, star_y - 8, star_x, star_y + 8), fill=light, width=3)
    elif theme == "time":
        draw.polygon([(left + 40, top + 20), (right - 40, top + 20), (center_x + 12, center_y - 10), (center_x - 12, center_y - 10)], fill=accent, outline=light, width=4)
        draw.polygon([(center_x - 12, center_y + 10), (center_x + 12, center_y + 10), (right - 40, bottom - 20), (left + 40, bottom - 20)], fill=accent, outline=light, width=4)
    elif theme == "spirit":
        draw.ellipse((center_x - 24, center_y - 28, center_x + 24, center_y + 24), fill=accent, outline=light, width=4)
        draw.polygon([(center_x, top + 8), (right - 22, center_y + 6), (center_x + 22, center_y + 6)], fill=accent, outline=light, width=4)
        draw.polygon([(center_x, top + 8), (left + 22, center_y + 6), (center_x - 22, center_y + 6)], fill=accent, outline=light, width=4)
    else:
        draw.ellipse((left + 22, top + 22, right - 22, bottom - 22), fill=accent, outline=light, width=4)


def generate_demo_sprite_sheet(sheet_path: Path = DEMO_SPRITE_SHEET_PATH) -> Path:
    ensure_directories()
    sheet = Image.new("RGBA", (CELL_WIDTH * 5, CELL_HEIGHT * len(RARITY_ORDER)), (18, 20, 32, 255))
    draw = ImageDraw.Draw(sheet)

    for row, rarity in enumerate(RARITY_ORDER):
        rarity_fill = _hex_to_rgba(RARITY_COLORS[rarity], 70)
        for column, creature in enumerate(CREATURES_BY_RARITY[rarity]):
            x1 = column * CELL_WIDTH
            y1 = row * CELL_HEIGHT
            x2 = x1 + CELL_WIDTH
            y2 = y1 + CELL_HEIGHT
            accent = _hex_to_rgba(THEME_COLORS[creature["theme"]], 235)

            draw.rounded_rectangle((x1 + 8, y1 + 8, x2 - 8, y2 - 8), radius=22, fill=(28, 30, 46, 255), outline=rarity_fill, width=5)
            draw.rounded_rectangle((x1 + 18, y1 + 18, x2 - 18, y2 - 18), radius=18, fill=rarity_fill, outline=None)
            _draw_motif(draw, (x1 + 42, y1 + 42, x2 - 42, y2 - 42), creature["theme"], accent)

    sheet.save(sheet_path)
    return sheet_path


def _source_sprite_sheet() -> Path:
    if USER_SPRITE_SHEET_PATH.exists():
        return USER_SPRITE_SHEET_PATH
    if not DEMO_SPRITE_SHEET_PATH.exists():
        generate_demo_sprite_sheet()
    return DEMO_SPRITE_SHEET_PATH


def _build_sprite(cell: Image.Image) -> Image.Image:
    cell.thumbnail((SPRITE_SIZE, SPRITE_SIZE), Image.Resampling.LANCZOS)
    sprite = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    offset_x = (SPRITE_SIZE - cell.width) // 2
    offset_y = (SPRITE_SIZE - cell.height) // 2
    sprite.paste(cell, (offset_x, offset_y), cell)
    return sprite


def _slice_standard_grid(sheet: Image.Image) -> dict[str, Image.Image]:
    sprite_map: dict[str, Image.Image] = {}
    cell_width = sheet.width / 5
    cell_height = sheet.height / len(RARITY_ORDER)

    for row, rarity in enumerate(RARITY_ORDER):
        for column, creature in enumerate(CREATURES_BY_RARITY[rarity]):
            left = int(round(column * cell_width))
            top = int(round(row * cell_height))
            right = int(round((column + 1) * cell_width))
            bottom = int(round((row + 1) * cell_height))
            cell = sheet.crop((left, top, right, bottom))

            inner_left = int(cell.width * 0.08)
            inner_top = int(cell.height * 0.08)
            inner_right = int(cell.width * 0.92)
            inner_bottom = int(cell.height * 0.82)
            cropped = cell.crop((inner_left, inner_top, inner_right, inner_bottom))
            sprite_map[creature["key"]] = _build_sprite(cropped)

    return sprite_map


def _slice_composite_sheet(sheet: Image.Image) -> dict[str, Image.Image]:
    sprite_map: dict[str, Image.Image] = {}

    for rarity in RARITY_ORDER:
        side, row_index = COMPOSITE_RARITY_POSITIONS[rarity]
        columns = COMPOSITE_LEFT_COLUMNS if side == "left" else COMPOSITE_RIGHT_COLUMNS
        top, bottom = COMPOSITE_ROWS[row_index]

        for column_index, creature in enumerate(CREATURES_BY_RARITY[rarity]):
            left, right = columns[column_index]
            cell = sheet.crop((left, top, right, bottom))
            inner_left = int(cell.width * 0.15)
            inner_top = int(cell.height * 0.30)
            inner_right = int(cell.width * 0.88)
            inner_bottom = int(cell.height * 0.90)
            cropped = cell.crop((inner_left, inner_top, inner_right, inner_bottom))
            sprite_map[creature["key"]] = _build_sprite(cropped)

    return sprite_map


def slice_sprite_sheet(force: bool = False) -> dict[str, Path]:
    ensure_directories()
    source_path = _source_sprite_sheet()
    if force:
        for child in SPRITE_OUTPUT_DIR.glob("*.png"):
            child.unlink(missing_ok=True)

    existing = {sprite.stem: sprite for sprite in SPRITE_OUTPUT_DIR.glob("*.png")}
    if len(existing) == sum(len(creatures) for creatures in CREATURES_BY_RARITY.values()) and not force:
        return existing

    sheet = Image.open(source_path).convert("RGBA")
    if sheet.width > sheet.height:
        sprite_images = _slice_composite_sheet(sheet)
    else:
        sprite_images = _slice_standard_grid(sheet)

    sprite_map: dict[str, Path] = {}
    for creature_key, sprite in sprite_images.items():
        output_path = SPRITE_OUTPUT_DIR / f"{creature_key}.png"
        sprite.save(output_path)
        sprite_map[creature_key] = output_path

    return sprite_map


def ensure_sprite_assets(force: bool = False) -> dict[str, Path]:
    ensure_directories()
    if not DEMO_SPRITE_SHEET_PATH.exists() and not USER_SPRITE_SHEET_PATH.exists():
        generate_demo_sprite_sheet()
    return slice_sprite_sheet(force=force)


def get_sprite_path(creature_key: str) -> Path:
    sprite_map = ensure_sprite_assets()
    return sprite_map[creature_key]


if __name__ == "__main__":
    ensure_sprite_assets(force=True)
    print(f"Sprites ready in {SPRITE_OUTPUT_DIR}")
