#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import Point, box
from shapely.ops import unary_union
import trimesh


ROOT = Path(__file__).resolve().parent
PROTOTYPE_OUTPUT_DIR = ROOT / "board_prototypes"
BOARD_OUTPUT_DIR = ROOT / "boards"

GRID_PITCH_MM = 40.0
COUPON_HOLE_DIAMETERS_MM = (8.25, 8.30, 8.35)
COUPON_THICKNESS_MM = 15.0
COUPON_WALL_MM = 4.0
BOARD_HOLE_DIAMETER_MM = 8.30
BOARD_THICKNESS_MM = 15.0
BOARD_EDGE_MARGIN_MM = 20.0
ARC_SEGMENTS_PER_QUARTER = 32

BOARD_SPECS = (
    (4, 4),
    (5, 5),
)


def circle(center: tuple[float, float], diameter: float):
    return Point(center).buffer(diameter / 2.0, quad_segs=ARC_SEGMENTS_PER_QUARTER)


def extrude(geometry, thickness: float):
    mesh = trimesh.creation.extrude_polygon(geometry, thickness)
    mesh.apply_translation((0.0, 0.0, -thickness / 2.0))
    return mesh


def bounds_xyz(mesh: trimesh.Trimesh):
    mins = mesh.bounds[0]
    maxs = mesh.bounds[1]
    return [
        float(mins[0]),
        float(mins[1]),
        float(mins[2]),
        float(maxs[0]),
        float(maxs[1]),
        float(maxs[2]),
    ]


def size_xyz(mesh: trimesh.Trimesh):
    min_x, min_y, min_z, max_x, max_y, max_z = bounds_xyz(mesh)
    return [max_x - min_x, max_y - min_y, max_z - min_z]


def arranged_mesh(meshes: list[tuple[str, trimesh.Trimesh]], spacing: float = 10.0):
    placed = []
    cursor_x = 0.0
    for name, mesh in meshes:
        current = mesh.copy()
        min_corner = current.bounds[0]
        max_corner = current.bounds[1]
        width = float(max_corner[0] - min_corner[0])
        current.apply_translation((cursor_x - float(min_corner[0]), -float(min_corner[1]), 0.0))
        placed.append((name, current))
        cursor_x += width + spacing
    return trimesh.util.concatenate([mesh for _, mesh in placed]), placed


def coupon_name(index: int, hole_diameter: float) -> str:
    label = f"{hole_diameter:.2f}".replace(".", "p")
    name = f"{index:02d}_board_fit_coupon_hole_{label}_thick_{int(COUPON_THICKNESS_MM)}"
    if abs(hole_diameter - 8.30) < 1e-9:
        name += "_recommended"
    return name


def board_name(index: int, cols: int, rows: int, hole_diameter: float) -> str:
    label = f"{hole_diameter:.2f}".replace(".", "p")
    return f"{index:02d}_pegboard_{cols}x{rows}_hole_{label}_provisional"


def build_fit_coupon(hole_diameter: float) -> trimesh.Trimesh:
    outer_diameter = hole_diameter + 2.0 * COUPON_WALL_MM
    ring = circle((0.0, 0.0), outer_diameter).difference(circle((0.0, 0.0), hole_diameter)).buffer(0)
    return extrude(ring, COUPON_THICKNESS_MM)


def build_fit_coupons():
    return {
        coupon_name(index, hole_diameter): build_fit_coupon(hole_diameter)
        for index, hole_diameter in enumerate(COUPON_HOLE_DIAMETERS_MM, start=1)
    }


def build_boards():
    return {
        board_name(index, cols, rows, BOARD_HOLE_DIAMETER_MM): build_board(cols, rows, BOARD_HOLE_DIAMETER_MM)
        for index, (cols, rows) in enumerate(BOARD_SPECS, start=1)
    }


def build_board(cols: int, rows: int, hole_diameter: float, thickness: float = BOARD_THICKNESS_MM):
    width = (cols - 1) * GRID_PITCH_MM + 2.0 * BOARD_EDGE_MARGIN_MM
    height = (rows - 1) * GRID_PITCH_MM + 2.0 * BOARD_EDGE_MARGIN_MM
    board = box(0.0, 0.0, width, height)

    holes = []
    for row in range(rows):
        for col in range(cols):
            center = (
                BOARD_EDGE_MARGIN_MM + col * GRID_PITCH_MM,
                BOARD_EDGE_MARGIN_MM + row * GRID_PITCH_MM,
            )
            holes.append(circle(center, hole_diameter))

    return extrude(board.difference(unary_union(holes)).buffer(0), thickness)


def write_readme(metadata: dict[str, dict[str, object]]):
    readme = f"""# Board Fit Prototypes

Generated from `generate_pegboard_board.py`.

These are minimal single-hole coupons to calibrate the peg fit for a fully 3D printed backboard before committing to a full board print.

## Best guess

- Peg CAD diameter: `7.72 mm`
- Observed printed peg diameter: about `7.92 mm`
- Coupon thickness: `{COUPON_THICKNESS_MM} mm`
- Coupon wall thickness: `{COUPON_WALL_MM} mm`
- Recommended first test: `{BOARD_HOLE_DIAMETER_MM:.2f} mm`
- Prototype hole diameters: `{", ".join(f"{value:.2f} mm" for value in COUPON_HOLE_DIAMETERS_MM)}`

The board should hold the peg more tightly than the loose-moving play pieces, so this test range is centered lower than the piece-hole test range.
The coupon thickness is set to the same `15 mm` as the intended printed board so the test matches the final board more closely.

Once you pick the winning hole diameter, the same script can generate full printed boards at `{BOARD_THICKNESS_MM} mm` thickness and `{GRID_PITCH_MM} mm` peg spacing.
"""
    (PROTOTYPE_OUTPUT_DIR / "README.md").write_text(readme)
    (PROTOTYPE_OUTPUT_DIR / "dimensions.json").write_text(json.dumps(metadata, indent=2))


def write_boards_notes(metadata: dict[str, dict[str, object]]):
    lines = [
        "# Printable Pegboards",
        "",
        "Generated from `generate_pegboard_board.py`.",
        "",
        "These are the current full-board exports using the present best-guess printed-board hole diameter.",
        "The board-hole size is still provisional until the single-hole coupon test is confirmed physically.",
        "",
        "## Current provisional settings",
        "",
        f"- Hole diameter: `{BOARD_HOLE_DIAMETER_MM:.2f} mm`",
        f"- Board thickness: `{BOARD_THICKNESS_MM} mm`",
        f"- Grid pitch: `{GRID_PITCH_MM} mm`",
        f"- Edge margin: `{BOARD_EDGE_MARGIN_MM} mm`",
        "",
        "## Files",
        "",
        "- `boards/01_pegboard_4x4_hole_8p30_provisional.stl`",
        "- `boards/02_pegboard_5x5_hole_8p30_provisional.stl`",
        "- The `4x4` board is `160 x 160 mm` overall.",
        "- The `5x5` board is `200 x 200 mm` overall.",
        "",
        "If the coupon test later points to a different hole diameter, update `BOARD_HOLE_DIAMETER_MM` in `generate_pegboard_board.py` and regenerate.",
    ]
    (ROOT / "BOARDS_README.md").write_text("\n".join(lines) + "\n")
    (BOARD_OUTPUT_DIR / "board_dimensions.json").write_text(json.dumps(metadata, indent=2))


def main():
    PROTOTYPE_OUTPUT_DIR.mkdir(exist_ok=True)
    BOARD_OUTPUT_DIR.mkdir(exist_ok=True)
    for old_stl in PROTOTYPE_OUTPUT_DIR.glob("*.stl"):
        old_stl.unlink()
    for old_stl in BOARD_OUTPUT_DIR.glob("*.stl"):
        old_stl.unlink()

    coupons = build_fit_coupons()
    boards = build_boards()
    metadata: dict[str, dict[str, object]] = {}
    board_metadata: dict[str, dict[str, object]] = {}

    ordered = []
    for name in sorted(coupons):
        mesh = coupons[name]
        path = PROTOTYPE_OUTPUT_DIR / f"{name}.stl"
        mesh.export(path)
        ordered.append((name, mesh))
        metadata[name] = {
            "file": path.name,
            "overall_xyz_mm": [round(value, 3) for value in size_xyz(mesh)],
            "bounds_xyz_mm": [round(value, 3) for value in bounds_xyz(mesh)],
            "hole_diameter_mm": float(name.rsplit("_hole_", 1)[1].split("_")[0].replace("p", ".")),
            "coupon_thickness_mm": COUPON_THICKNESS_MM,
            "coupon_wall_mm": COUPON_WALL_MM,
        }

    layout_mesh, placed = arranged_mesh(ordered)
    layout_name = "all_board_fit_coupons_layout"
    layout_path = PROTOTYPE_OUTPUT_DIR / f"{layout_name}.stl"
    layout_mesh.export(layout_path)
    metadata[layout_name] = {
        "file": layout_path.name,
        "placements": {
            name: {
                "bounds_xyz_mm": [round(value, 3) for value in bounds_xyz(mesh)]
            }
            for name, mesh in placed
        },
    }

    write_readme(metadata)

    for index, name in enumerate(sorted(boards), start=1):
        mesh = boards[name]
        path = BOARD_OUTPUT_DIR / f"{name}.stl"
        mesh.export(path)
        cols, rows = BOARD_SPECS[index - 1]
        board_metadata[name] = {
            "file": path.name,
            "grid": [cols, rows],
            "overall_xyz_mm": [round(value, 3) for value in size_xyz(mesh)],
            "bounds_xyz_mm": [round(value, 3) for value in bounds_xyz(mesh)],
            "hole_diameter_mm": BOARD_HOLE_DIAMETER_MM,
            "thickness_mm": BOARD_THICKNESS_MM,
            "grid_pitch_mm": GRID_PITCH_MM,
            "edge_margin_mm": BOARD_EDGE_MARGIN_MM,
        }

    write_boards_notes(board_metadata)


if __name__ == "__main__":
    main()
