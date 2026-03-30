#!/usr/bin/env python3

from __future__ import annotations

import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point
from shapely.ops import unary_union
import trimesh


PITCH_MM = 40.0
OUTER_WIDTH_MM = 16.0
THICKNESS_MM = 3.0
HOLE_DIAMETER_MM = 8.45
PEG_DIAMETER_MM = 7.72
PEG_LENGTH_MM = 40.0
PEG_ROUNDOVER_MM = 1.2
ARC_SEGMENTS_PER_QUARTER = 32
REVOLVE_SECTIONS = 128

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "pieces"


def mm(value: float) -> float:
    return float(value)


def circle(center: tuple[float, float], diameter: float):
    return Point(center).buffer(diameter / 2.0, quad_segs=ARC_SEGMENTS_PER_QUARTER)


def buffered_path(points: list[tuple[float, float]]):
    return LineString(points).buffer(OUTER_WIDTH_MM / 2.0, quad_segs=ARC_SEGMENTS_PER_QUARTER)


def arc_points(
    center: tuple[float, float],
    radius: float,
    start_deg: float,
    end_deg: float,
    segments: int,
) -> list[tuple[float, float]]:
    start_rad = math.radians(start_deg)
    end_rad = math.radians(end_deg)
    return [
        (
            center[0] + radius * math.cos(start_rad + (end_rad - start_rad) * i / segments),
            center[1] + radius * math.sin(start_rad + (end_rad - start_rad) * i / segments),
        )
        for i in range(segments + 1)
    ]


def shape_from_path(
    points: list[tuple[float, float]],
    hole_centers: list[tuple[float, float]],
    hole_diameter: float = HOLE_DIAMETER_MM,
):
    outer = buffered_path(points)
    holes = unary_union([circle(center, hole_diameter) for center in hole_centers])
    return outer.difference(holes).buffer(0)


def shape_from_arc(
    center: tuple[float, float],
    radius: float,
    start_deg: float,
    end_deg: float,
    hole_centers: list[tuple[float, float]],
    hole_diameter: float = HOLE_DIAMETER_MM,
):
    points = arc_points(
        center=center,
        radius=radius,
        start_deg=start_deg,
        end_deg=end_deg,
        segments=int(abs(end_deg - start_deg) / 90.0 * ARC_SEGMENTS_PER_QUARTER),
    )
    return shape_from_path(points, hole_centers, hole_diameter=hole_diameter)


def extrude(geometry):
    mesh = trimesh.creation.extrude_polygon(geometry, THICKNESS_MM)
    mesh.apply_translation((0.0, 0.0, -THICKNESS_MM / 2.0))
    return mesh


def rotate_mesh_z(mesh: trimesh.Trimesh, angle_deg: float):
    rotated = mesh.copy()
    rotated.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(angle_deg),
            [0.0, 0.0, 1.0],
        )
    )
    return rotated


def diameter_label(diameter: float) -> str:
    return f"{diameter:.2f}".replace(".", "p")


def build_peg(diameter: float = PEG_DIAMETER_MM):
    radius = diameter / 2.0
    fillet = min(PEG_ROUNDOVER_MM, radius, PEG_LENGTH_MM / 2.0)
    body_length = PEG_LENGTH_MM

    profile = [(0.0, 0.0), (radius - fillet, 0.0)]
    profile.extend(
        arc_points(
            center=(radius - fillet, fillet),
            radius=fillet,
            start_deg=-90.0,
            end_deg=0.0,
            segments=ARC_SEGMENTS_PER_QUARTER,
        )[1:]
    )
    profile.append((radius, body_length - fillet))
    profile.extend(
        arc_points(
            center=(radius - fillet, body_length - fillet),
            radius=fillet,
            start_deg=0.0,
            end_deg=90.0,
            segments=ARC_SEGMENTS_PER_QUARTER,
        )[1:]
    )
    profile.append((0.0, body_length))

    mesh = trimesh.creation.revolve(profile, sections=REVOLVE_SECTIONS)
    mesh.apply_translation((0.0, 0.0, -body_length / 2.0))
    return mesh


def build_pegs():
    label = diameter_label(PEG_DIAMETER_MM)
    name = f"08_peg_{label}x{int(PEG_LENGTH_MM)}_roundover_{str(PEG_ROUNDOVER_MM).replace('.', 'p')}_recommended"
    return {name: build_peg(diameter=PEG_DIAMETER_MM)}


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


def bounds_xy(mesh: trimesh.Trimesh):
    mins = mesh.bounds[0][:2]
    maxs = mesh.bounds[1][:2]
    return [float(mins[0]), float(mins[1]), float(maxs[0]), float(maxs[1])]


def size_xy(mesh: trimesh.Trimesh):
    min_x, min_y, max_x, max_y = bounds_xy(mesh)
    return [max_x - min_x, max_y - min_y]


def arranged_mesh(meshes: list[tuple[str, trimesh.Trimesh]]):
    placed = []
    cursor_x = 0.0
    cursor_y = 0.0
    row_height = 0.0
    max_row_width = 260.0
    spacing = 14.0

    for name, mesh in meshes:
        current = mesh.copy()
        min_corner = current.bounds[0]
        max_corner = current.bounds[1]
        width = float(max_corner[0] - min_corner[0])
        height = float(max_corner[1] - min_corner[1])

        if cursor_x > 0.0 and cursor_x + width > max_row_width:
            cursor_x = 0.0
            cursor_y += row_height + spacing
            row_height = 0.0

        current.apply_translation(
            (
                cursor_x - float(min_corner[0]),
                cursor_y - float(min_corner[1]),
                0.0,
            )
        )
        placed.append((name, current))
        cursor_x += width + spacing
        row_height = max(row_height, height)

    return trimesh.util.concatenate([mesh for _, mesh in placed]), placed


def build_shapes(hole_diameter: float = HOLE_DIAMETER_MM):
    pitch = PITCH_MM
    shapes = {
        "01_straight_2_holes": shape_from_path(
            [(0.0, 0.0), (pitch, 0.0)],
            [(0.0, 0.0), (pitch, 0.0)],
            hole_diameter=hole_diameter,
        ),
        "02_straight_3_holes": shape_from_path(
            [(0.0, 0.0), (2 * pitch, 0.0)],
            [(0.0, 0.0), (pitch, 0.0), (2 * pitch, 0.0)],
            hole_diameter=hole_diameter,
        ),
        "03_rotor_single_hole": shape_from_path(
            [(0.0, 0.0), (pitch, 0.0)],
            [(pitch / 2.0, 0.0)],
            hole_diameter=hole_diameter,
        ),
        "04_diagonal_2_holes": shape_from_path(
            [(0.0, 0.0), (pitch, pitch)],
            [(0.0, 0.0), (pitch, pitch)],
            hole_diameter=hole_diameter,
        ),
        "05_offset_diagonal_2_holes": shape_from_path(
            [(0.0, 0.0), (2 * pitch, pitch)],
            [(0.0, 0.0), (2 * pitch, pitch)],
            hole_diameter=hole_diameter,
        ),
        "06_half_circle_2_holes": shape_from_arc(
            center=(pitch / 2.0, 0.0),
            radius=pitch / 2.0,
            start_deg=180.0,
            end_deg=0.0,
            hole_centers=[(0.0, 0.0), (pitch, 0.0)],
            hole_diameter=hole_diameter,
        ),
        "07_quarter_circle_2_holes": shape_from_arc(
            center=(0.0, pitch),
            radius=pitch,
            start_deg=-90.0,
            end_deg=0.0,
            hole_centers=[(0.0, 0.0), (pitch, pitch)],
            hole_diameter=hole_diameter,
        ),
    }
    meshes = {name: extrude(geometry) for name, geometry in shapes.items()}
    meshes["04_diagonal_2_holes"] = rotate_mesh_z(meshes["04_diagonal_2_holes"], -45.0)
    meshes["05_offset_diagonal_2_holes"] = rotate_mesh_z(
        meshes["05_offset_diagonal_2_holes"],
        -math.degrees(math.atan2(pitch, 2.0 * pitch)),
    )
    return meshes


def write_readme(metadata: dict[str, dict[str, object]]):
    readme = f"""# Pegboard Shapes

Generated from `generate_pegboard_shapes.py`.

## Default dimensions

- Pegboard pitch: `{PITCH_MM} mm`
- Piece width: `{OUTER_WIDTH_MM} mm`
- Piece thickness: `{THICKNESS_MM} mm`
- Peg hole diameter: `{HOLE_DIAMETER_MM} mm`
- Recommended peg diameter: `{PEG_DIAMETER_MM} mm`
- Peg length: `{PEG_LENGTH_MM} mm`
- Peg end roundover: `{PEG_ROUNDOVER_MM} mm`

The hole diameter is intentionally tuned upward because your printer closes printed holes relative to CAD. The recommended peg diameter is tuned downward because your printer makes outside diameters print slightly oversized. If your printer runs tighter or looser later, edit `HOLE_DIAMETER_MM` and `PEG_DIAMETER_MM` in `generate_pegboard_shapes.py` and re-run the script.

The single exported peg is the measured best-fit version: `7.72 mm` CAD diameter, `40.0 mm` length, and `1.2 mm` end roundover.

## Files

Each STL in `pieces/` is a separate printable part. `pieces/all_shapes_layout.stl` contains the seven flat pieces arranged on one virtual plate for quick viewing. The tuned peg is exported into the same folder as its own STL.

Drag any STL directly into Bambu Studio. If you want to inspect or re-export later, keep the Python source file because all dimensions are parametric there.
"""
    (ROOT / "PIECES_README.md").write_text(readme)
    (OUTPUT_DIR / "dimensions.json").write_text(json.dumps(metadata, indent=2))


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    for old_stl in OUTPUT_DIR.glob("*.stl"):
        old_stl.unlink()

    meshes = build_shapes()
    meshes.update(build_pegs())
    metadata: dict[str, dict[str, object]] = {}

    ordered_meshes = []
    for name in sorted(meshes):
        mesh = meshes[name]
        path = OUTPUT_DIR / f"{name}.stl"
        mesh.export(path)
        metadata[name] = {
            "file": str(path.name),
            "overall_xy_mm": [round(value, 3) for value in size_xy(mesh)],
            "overall_xyz_mm": [round(value, 3) for value in size_xyz(mesh)],
            "bounds_xy_mm": [round(value, 3) for value in bounds_xy(mesh)],
            "bounds_xyz_mm": [round(value, 3) for value in bounds_xyz(mesh)],
        }
        if "peg" in name:
            metadata[name]["peg_diameter_mm"] = round(size_xyz(mesh)[0], 3)
            metadata[name]["peg_length_mm"] = PEG_LENGTH_MM
            metadata[name]["peg_roundover_mm"] = PEG_ROUNDOVER_MM
        else:
            metadata[name]["thickness_mm"] = THICKNESS_MM
            metadata[name]["hole_diameter_mm"] = HOLE_DIAMETER_MM
            ordered_meshes.append((name, mesh))

    layout_mesh, placed = arranged_mesh(ordered_meshes)
    layout_mesh.export(OUTPUT_DIR / "all_shapes_layout.stl")
    metadata["all_shapes_layout"] = {
        "file": "all_shapes_layout.stl",
        "placements": {
            name: {
                "bounds_xy_mm": [round(v, 3) for v in bounds_xy(mesh)]
            }
            for name, mesh in placed
        },
    }

    write_readme(metadata)


if __name__ == "__main__":
    main()
