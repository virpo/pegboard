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


ROOT = Path(__file__).resolve().parent
ASSETS_DIR = ROOT / "assets"

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
CANVAS_H = 1500
DRAW_SCALE = 2.2


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
    ASSETS_DIR.mkdir(exist_ok=True)


def circle(center: tuple[float, float], diameter: float):
    return Point(center).buffer(diameter / 2.0, quad_segs=boards_gen.ARC_SEGMENTS_PER_QUARTER)


def peg_profile():
    radius = shapes_gen.PEG_DIAMETER_MM / 2.0
    start_x = radius
    end_x = shapes_gen.PEG_LENGTH_MM - radius
    return LineString([(start_x, 0.0), (end_x, 0.0)]).buffer(radius, quad_segs=shapes_gen.ARC_SEGMENTS_PER_QUARTER)


def piece_geometries():
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
        peg_profile(),
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


def arrange_geometries(
    geometries: list[Polygon],
    spacing_mm: float,
    max_row_width_mm: float,
) -> tuple[list[Polygon], tuple[float, float]]:
    placed = []
    cursor_x = 0.0
    cursor_y = 0.0
    row_height = 0.0

    for geometry in geometries:
        min_x, min_y, max_x, max_y = geometry.bounds
        width = max_x - min_x
        height = max_y - min_y
        if cursor_x > 0.0 and cursor_x + width > max_row_width_mm:
            cursor_x = 0.0
            cursor_y += row_height + spacing_mm
            row_height = 0.0
        placed.append(affinity.translate(geometry, xoff=cursor_x - min_x, yoff=cursor_y - min_y))
        cursor_x += width + spacing_mm
        row_height = max(row_height, height)

    max_x = max(geometry.bounds[2] for geometry in placed)
    max_y = max(geometry.bounds[3] for geometry in placed)
    return placed, (max_x, max_y)


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

    processed_sketch = resize_for_repo(ImageOps.exif_transpose(sketch), 1600)
    processed_play = resize_for_repo(ImageOps.exif_transpose(play), 1200)
    processed_sketch.save(ASSETS_DIR / "sketch.jpg", quality=92)
    processed_play.save(ASSETS_DIR / "oliver-playing.jpg", quality=92)

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

    image.resize((logical_w, logical_h), Image.Resampling.LANCZOS).save(ASSETS_DIR / "from-sketch-to-play.jpg", quality=92)


def generate_overview():
    logical_image = Image.new("RGB", (CANVAS_W * UPSCALE, CANVAS_H * UPSCALE), BACKGROUND)
    draw = ImageDraw.Draw(logical_image)

    title_font = load_font(48 * UPSCALE, bold=True)
    section_font = load_font(30 * UPSCALE, bold=True)
    note_font = load_font(21 * UPSCALE)

    draw.text((84 * UPSCALE, 58 * UPSCALE), "what's in this repository", fill=TEXT, font=title_font)
    draw.text(
        (84 * UPSCALE, 118 * UPSCALE),
        "Seven play pieces, one tuned peg, four gears, and two printable pegboards on a 40 mm grid.",
        fill=SUBTLE,
        font=note_font,
    )

    def draw_card(title: str, x: int, y: int, w: int, h: int):
        draw.text((x * UPSCALE, y * UPSCALE), title, fill=TEXT, font=section_font)
        card_y = (y + 56) * UPSCALE
        draw.rounded_rectangle(
            (x * UPSCALE, card_y, (x + w) * UPSCALE, card_y + h * UPSCALE),
            radius=24 * UPSCALE,
            fill=CARD,
            outline=CARD_STROKE,
            width=2 * UPSCALE,
        )
        return x * UPSCALE, card_y, w * UPSCALE, h * UPSCALE

    def draw_arranged_group(
        title: str,
        geometries,
        colors,
        x: int,
        y: int,
        w: int,
        h: int,
        scale: float,
        max_row_width_mm: float,
        spacing_mm: float = 20.0,
        labels: list[str] | None = None,
    ):
        card_x, card_y, card_w, card_h = draw_card(title, x, y, w, h)
        arranged, (content_w_mm, content_h_mm) = arrange_geometries(geometries, spacing_mm=spacing_mm, max_row_width_mm=max_row_width_mm)
        content_w_px = int(content_w_mm * scale * UPSCALE)
        content_h_px = int(content_h_mm * scale * UPSCALE)
        origin_x = card_x + (card_w - content_w_px) // 2
        origin_y = card_y + (card_h + content_h_px) // 2

        def transform(xx: float, yy: float):
            px = origin_x + xx * scale * UPSCALE
            py = origin_y - yy * scale * UPSCALE
            return (px, py)

        for index, geometry in enumerate(arranged):
            draw_geometry(draw, geometry, transform, colors[index % len(colors)])

        if labels:
            for label, geometry in zip(labels, arranged):
                min_x, _, max_x, _ = geometry.bounds
                label_x = origin_x + ((min_x + max_x) / 2.0) * scale * UPSCALE
                draw.text((label_x - 18 * UPSCALE, card_y + card_h - 42 * UPSCALE), label, fill=SUBTLE, font=note_font)

    draw_arranged_group(
        "play pieces",
        piece_geometries(),
        PIECE_COLORS,
        x=84,
        y=180,
        w=1632,
        h=320,
        scale=3.1,
        max_row_width_mm=320.0,
        spacing_mm=20.0,
    )
    draw_arranged_group(
        "gears",
        gear_geometries(),
        GEAR_COLORS,
        x=84,
        y=590,
        w=760,
        h=560,
        scale=1.8,
        max_row_width_mm=300.0,
        spacing_mm=24.0,
    )
    draw_arranged_group(
        "pegboards",
        [board_geometry(4, 4), board_geometry(5, 5)],
        (BOARD_FILL, BOARD_FILL),
        x=876,
        y=590,
        w=840,
        h=560,
        scale=1.75,
        max_row_width_mm=500.0,
        spacing_mm=28.0,
        labels=["4x4", "5x5"],
    )

    logical_image.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS).save(ASSETS_DIR / "overview.png", quality=95)


def main():
    ensure_assets_dir()
    generate_story_image()
    generate_overview()


if __name__ == "__main__":
    main()
