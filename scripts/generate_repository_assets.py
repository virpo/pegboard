#!/usr/bin/env python3

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

import generate_pegboard_board as boards_gen
import generate_pegboard_gears as gears_gen
import generate_pegboard_shapes as shapes_gen


ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "docs" / "assets"

SKETCH_SOURCE = Path.home() / "Downloads" / "IMG_7132.jpeg"
PLAY_SOURCE = Path.home() / "Downloads" / "IMG_7198 2.jpeg"

BACKGROUND = "#f4efe8"
TEXT = "#34271f"
SUBTLE = "#8d7b6a"
CARD = "#fbf8f3"
CARD_STROKE = "#e5dbcf"
PIECE_COLORS = ("#E58A5E", "#F1C27D", "#4D6FA9", "#D97B57", "#93B0A7", "#F2B8A0", "#6B86B9")
GEAR_COLORS = ("#D6865B", "#F0BF66", "#6A88B6", "#A4B597")
BOARD_FILL = "#E6D7C3"
BOARD_HOLE = "#6D5747"

UPSCALE = 2
CANVAS_W = 1800
CANVAS_H = 1180


def load_font(size: int, bold: bool = False):
    font_candidates = [
        "/System/Library/Fonts/Supplemental/Avenir Next.ttc",
        "/System/Library/Fonts/Supplemental/Futura.ttc",
        "/System/Library/Fonts/Supplemental/HelveticaNeue.ttc",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for candidate in font_candidates:
        try:
            return ImageFont.truetype(candidate, size=size, index=1 if bold else 0)
        except OSError:
            continue
    return ImageFont.load_default()


def ensure_assets_dir():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def circle(center: tuple[float, float], diameter: float):
    return Point(center).buffer(diameter / 2.0, quad_segs=boards_gen.ARC_SEGMENTS_PER_QUARTER)


def peg_profile():
    radius = shapes_gen.PEG_DIAMETER_MM / 2.0
    start_x = radius
    end_x = shapes_gen.PEG_LENGTH_MM - radius
    return LineString([(start_x, 0.0), (end_x, 0.0)]).buffer(radius, quad_segs=shapes_gen.ARC_SEGMENTS_PER_QUARTER)


def play_piece_geometries():
    pitch = shapes_gen.PITCH_MM
    return [
        shapes_gen.shape_from_path([(0.0, 0.0), (pitch, 0.0)], [(0.0, 0.0), (pitch, 0.0)]),
        shapes_gen.shape_from_path(
            [(0.0, 0.0), (2.0 * pitch, 0.0)],
            [(0.0, 0.0), (pitch, 0.0), (2.0 * pitch, 0.0)],
        ),
        shapes_gen.shape_from_path([(0.0, 0.0), (pitch, 0.0)], [(pitch / 2.0, 0.0)]),
        affinity.rotate(
            shapes_gen.shape_from_path([(0.0, 0.0), (pitch, pitch)], [(0.0, 0.0), (pitch, pitch)]),
            -45.0,
            origin=(0.0, 0.0),
        ),
        affinity.rotate(
            shapes_gen.shape_from_path([(0.0, 0.0), (2.0 * pitch, pitch)], [(0.0, 0.0), (2.0 * pitch, pitch)]),
            -math.degrees(math.atan2(pitch, 2.0 * pitch)),
            origin=(0.0, 0.0),
        ),
        shapes_gen.shape_from_arc(
            center=(pitch / 2.0, 0.0),
            radius=pitch / 2.0,
            start_deg=180.0,
            end_deg=0.0,
            hole_centers=[(0.0, 0.0), (pitch, 0.0)],
        ),
        shapes_gen.shape_from_arc(
            center=(0.0, pitch),
            radius=pitch,
            start_deg=-90.0,
            end_deg=0.0,
            hole_centers=[(0.0, 0.0), (pitch, pitch)],
        ),
    ]


def gear_geometries():
    return [gears_gen.gear_2d(teeth) for teeth in gears_gen.TOOTH_COUNTS]


def board_geometry(cols: int, rows: int):
    width = (cols - 1) * boards_gen.GRID_PITCH_MM + 2.0 * boards_gen.BOARD_EDGE_MARGIN_MM
    height = (rows - 1) * boards_gen.GRID_PITCH_MM + 2.0 * boards_gen.BOARD_EDGE_MARGIN_MM
    board = box(0.0, 0.0, width, height)
    holes = []
    for row in range(rows):
        for col in range(cols):
            center = (
                boards_gen.BOARD_EDGE_MARGIN_MM + col * boards_gen.GRID_PITCH_MM,
                boards_gen.BOARD_EDGE_MARGIN_MM + row * boards_gen.GRID_PITCH_MM,
            )
            holes.append(circle(center, boards_gen.BOARD_HOLE_DIAMETER_MM))
    return board.difference(unary_union(holes)).buffer(0)


def draw_geometry(draw: ImageDraw.ImageDraw, geometry, transform, fill):
    if isinstance(geometry, MultiPolygon):
        for polygon in geometry.geoms:
            draw_geometry(draw, polygon, transform, fill)
        return

    if not isinstance(geometry, Polygon):
        return

    exterior = [transform(x, y) for x, y in geometry.exterior.coords]
    draw.polygon(exterior, fill=fill)
    for interior in geometry.interiors:
        hole = [transform(x, y) for x, y in interior.coords]
        draw.polygon(hole, fill=BACKGROUND)


def fit_image(image: Image.Image, size: tuple[int, int]):
    return ImageOps.fit(ImageOps.exif_transpose(image), size, method=Image.Resampling.LANCZOS)


def resize_for_repo(image: Image.Image, width: int):
    ratio = width / image.width
    return image.resize((width, int(image.height * ratio)), Image.Resampling.LANCZOS)


def save_jpeg(image: Image.Image, path: Path, quality: int = 86):
    image.save(
        path,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
        subsampling="4:2:0",
    )


def framed_photo(image: Image.Image, size: tuple[int, int], radius: int, padding: int):
    base = Image.new("RGB", size, CARD)
    fitted = ImageOps.contain(ImageOps.exif_transpose(image).convert("RGB"), (size[0] - 2 * padding, size[1] - 2 * padding), Image.Resampling.LANCZOS)
    offset = ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2)
    base.paste(fitted, offset)

    mask = Image.new("L", size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)

    result = Image.new("RGB", size, BACKGROUND)
    result.paste(base, mask=mask)
    return result


def generate_story_image():
    if not SKETCH_SOURCE.exists() or not PLAY_SOURCE.exists():
        return

    sketch = Image.open(SKETCH_SOURCE)
    play = Image.open(PLAY_SOURCE)

    processed_sketch = resize_for_repo(ImageOps.exif_transpose(sketch), 1200)
    processed_play = resize_for_repo(ImageOps.exif_transpose(play), 1000)
    save_jpeg(processed_sketch, ASSETS_DIR / "sketch.jpg", quality=86)
    save_jpeg(processed_play, ASSETS_DIR / "oliver-playing.jpg", quality=86)

    logical_w = 1800
    logical_h = 920
    image = Image.new("RGB", (logical_w * UPSCALE, logical_h * UPSCALE), BACKGROUND)
    draw = ImageDraw.Draw(image)
    photo_y = 92 * UPSCALE
    card_size = (760 * UPSCALE, 720 * UPSCALE)
    gap = 88 * UPSCALE
    left_x = 96 * UPSCALE
    right_x = left_x + card_size[0] + gap
    radius = 28 * UPSCALE

    for x in (left_x, right_x):
        draw.rounded_rectangle(
            (x - 10 * UPSCALE, photo_y - 10 * UPSCALE, x + card_size[0] + 10 * UPSCALE, photo_y + card_size[1] + 10 * UPSCALE),
            radius=radius + 10 * UPSCALE,
            fill=CARD,
            outline=CARD_STROKE,
            width=3 * UPSCALE,
        )

    image.paste(framed_photo(sketch, card_size, radius, padding=18 * UPSCALE), (left_x, photo_y))
    image.paste(framed_photo(play, card_size, radius, padding=18 * UPSCALE), (right_x, photo_y))

    save_jpeg(
        image.resize((logical_w, logical_h), Image.Resampling.LANCZOS),
        ASSETS_DIR / "from-sketch-to-play.jpg",
        quality=84,
    )


def generate_overview():
    logical_image = Image.new("RGB", (CANVAS_W * UPSCALE, CANVAS_H * UPSCALE), BACKGROUND)
    draw = ImageDraw.Draw(logical_image)

    def draw_card(x: int, y: int, w: int, h: int):
        draw.rounded_rectangle(
            (x * UPSCALE, y * UPSCALE, (x + w) * UPSCALE, (y + h) * UPSCALE),
            radius=24 * UPSCALE,
            fill=CARD,
            outline=CARD_STROKE,
            width=2 * UPSCALE,
        )
        return (x * UPSCALE, y * UPSCALE, w * UPSCALE, h * UPSCALE)

    def draw_centered(geometry, center_x: float, center_y: float, scale: float, fill: str):
        scaled = affinity.scale(geometry, xfact=scale * UPSCALE, yfact=scale * UPSCALE, origin=(0.0, 0.0))
        min_x, min_y, max_x, max_y = scaled.bounds
        placed = affinity.translate(
            scaled,
            xoff=center_x * UPSCALE - (min_x + max_x) / 2.0,
            yoff=center_y * UPSCALE - (min_y + max_y) / 2.0,
        )
        draw_geometry(draw, placed, lambda x, y: (x, y), fill)

    draw_card(84, 64, 1632, 360)
    draw_card(84, 488, 760, 608)
    draw_card(876, 488, 840, 608)

    pieces = play_piece_geometries()
    piece_layout = [
        (pieces[6], PIECE_COLORS[6], 290, 180, 2.95),
        (pieces[4], PIECE_COLORS[4], 720, 164, 2.85),
        (pieces[5], PIECE_COLORS[5], 1295, 166, 3.15),
        (pieces[1], PIECE_COLORS[1], 420, 326, 3.05),
        (pieces[0], PIECE_COLORS[0], 905, 326, 3.05),
        (pieces[3], PIECE_COLORS[3], 1275, 312, 2.95),
        (pieces[2], PIECE_COLORS[2], 1530, 326, 3.05),
    ]
    for geometry, color, center_x, center_y, scale in piece_layout:
        draw_centered(geometry, center_x, center_y, scale, color)

    gears = gear_geometries()
    gear_layout = [
        (gears[3], GEAR_COLORS[3], 286, 690, 1.62),
        (gears[0], GEAR_COLORS[0], 208, 1010, 1.95),
        (gears[1], GEAR_COLORS[1], 360, 975, 1.80),
        (gears[2], GEAR_COLORS[2], 588, 942, 1.72),
    ]
    for geometry, color, center_x, center_y, scale in gear_layout:
        draw_centered(geometry, center_x, center_y, scale, color)

    board_4x4 = board_geometry(4, 4)
    board_5x5 = board_geometry(5, 5)
    draw_centered(board_4x4, 1125, 725, 1.62, BOARD_FILL)
    draw_centered(board_5x5, 1450, 705, 1.45, BOARD_FILL)

    peg = peg_profile()
    peg_vertical = affinity.rotate(peg, 90.0, origin=(0.0, 0.0))
    peg_color = "#DD825A"
    peg_scale = 2.1
    peg_gap = shapes_gen.PEG_DIAMETER_MM * peg_scale
    peg_step = 2.0 * peg_gap
    peg_row_center_x = 1296.0
    peg_row_y = 980.0
    peg_first_x = peg_row_center_x - peg_step * 4.5
    peg_layout = [(peg_first_x + index * peg_step, peg_row_y) for index in range(10)]
    for center_x, center_y in peg_layout:
        draw_centered(peg_vertical, center_x, center_y, peg_scale, peg_color)

    logical_image.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS).save(ASSETS_DIR / "overview.png", quality=95)


def main():
    ensure_assets_dir()
    generate_story_image()
    generate_overview()


if __name__ == "__main__":
    main()
