#!/usr/bin/env python3

from __future__ import annotations

import json
import math
from itertools import combinations
from pathlib import Path

import numpy as np
from shapely import affinity
from shapely.geometry import Point, Polygon
import trimesh
from trimesh.creation import triangulate_polygon


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "gears"

GRID_PITCH_MM = 40.0
HOLE_DIAMETER_MM = 8.45
GEAR_THICKNESS_MM = 6.0
PEG_DIAMETER_MM = 8.0

# Lock the family to the board exactly like the original set.
MODULE_MM = GRID_PITCH_MM / 9.0
TOOTH_COUNTS = (6, 12, 24, 30)

# This keeps the original toy-gear proportions but reduces backlash slightly
# and replaces the straight tooth flanks with gentle convex curves.
ADDENDUM_FACTOR = 0.60
DEDENDUM_FACTOR = 0.80
PITCH_TOOTH_FRACTION = 0.405
TIP_TOOTH_FRACTION = 0.185
ROOT_RELIEF_FRACTION = 0.08
FLANK_BULGE_MM = 0.20
TOOTH_ROUNDING_MM = 0.4
EDGE_BREAK_MM = 0.4

ARC_SEGMENTS_PER_QUARTER = 32
FLANK_SAMPLES = 18
ARC_SAMPLES = 16
HOLE_RING_SAMPLES = 96


def polar(radius: float, angle_rad: float) -> tuple[float, float]:
    return (radius * math.cos(angle_rad), radius * math.sin(angle_rad))


def circle(center: tuple[float, float], diameter: float):
    return Point(center).buffer(diameter / 2.0, quad_segs=ARC_SEGMENTS_PER_QUARTER)


def pitch_radius(teeth: int) -> float:
    return MODULE_MM * teeth / 2.0


def outer_radius(teeth: int) -> float:
    return pitch_radius(teeth) + ADDENDUM_FACTOR * MODULE_MM


def root_radius(teeth: int) -> float:
    return pitch_radius(teeth) - DEDENDUM_FACTOR * MODULE_MM


def quadratic_control_for_midpoint(
    start: tuple[float, float],
    midpoint: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float]:
    return (
        2.0 * midpoint[0] - 0.5 * (start[0] + end[0]),
        2.0 * midpoint[1] - 0.5 * (start[1] + end[1]),
    )


def quadratic_curve_points(
    start: tuple[float, float],
    midpoint: tuple[float, float],
    end: tuple[float, float],
    samples: int,
) -> list[tuple[float, float]]:
    control = quadratic_control_for_midpoint(start, midpoint, end)
    points = []
    for index in range(samples + 1):
        t = index / samples
        one_minus_t = 1.0 - t
        x = (
            one_minus_t * one_minus_t * start[0]
            + 2.0 * one_minus_t * t * control[0]
            + t * t * end[0]
        )
        y = (
            one_minus_t * one_minus_t * start[1]
            + 2.0 * one_minus_t * t * control[1]
            + t * t * end[1]
        )
        points.append((x, y))
    return points


def arc_points(
    radius: float,
    start_angle: float,
    end_angle: float,
    samples: int,
) -> list[tuple[float, float]]:
    points = []
    for index in range(samples + 1):
        angle = start_angle + (end_angle - start_angle) * index / samples
        points.append(polar(radius, angle))
    return points


def add_segment(points: list[tuple[float, float]], segment: list[tuple[float, float]]):
    if not points:
        points.extend(segment)
        return
    points.extend(segment[1:])


def base_outline(teeth: int) -> Polygon:
    tau = 2.0 * math.pi / teeth
    rp = pitch_radius(teeth)
    ro = outer_radius(teeth)
    rr = root_radius(teeth)

    points: list[tuple[float, float]] = []
    for tooth in range(teeth):
        theta = tooth * tau

        root_left_angle = theta - tau / 2.0 + ROOT_RELIEF_FRACTION * tau
        pitch_left_angle = theta - PITCH_TOOTH_FRACTION * tau / 2.0
        tip_left_angle = theta - TIP_TOOTH_FRACTION * tau / 2.0
        tip_right_angle = theta + TIP_TOOTH_FRACTION * tau / 2.0
        pitch_right_angle = theta + PITCH_TOOTH_FRACTION * tau / 2.0
        root_right_angle = theta + tau / 2.0 - ROOT_RELIEF_FRACTION * tau
        next_root_left_angle = theta + tau / 2.0 + ROOT_RELIEF_FRACTION * tau

        left_flank = quadratic_curve_points(
            polar(rr, root_left_angle),
            polar(rp + FLANK_BULGE_MM, pitch_left_angle),
            polar(ro, tip_left_angle),
            FLANK_SAMPLES,
        )
        tip_arc = arc_points(ro, tip_left_angle, tip_right_angle, ARC_SAMPLES)
        right_flank = quadratic_curve_points(
            polar(ro, tip_right_angle),
            polar(rp + FLANK_BULGE_MM, pitch_right_angle),
            polar(rr, root_right_angle),
            FLANK_SAMPLES,
        )
        root_arc = arc_points(rr, root_right_angle, next_root_left_angle, ARC_SAMPLES)

        add_segment(points, left_flank)
        add_segment(points, tip_arc)
        add_segment(points, right_flank)
        add_segment(points, root_arc)

    return Polygon(points).buffer(0)


def rounded_outline(teeth: int) -> Polygon:
    outline = base_outline(teeth)
    return outline.buffer(TOOTH_ROUNDING_MM, join_style=1).buffer(-TOOTH_ROUNDING_MM, join_style=1).buffer(0)


def gear_2d(teeth: int) -> Polygon:
    return rounded_outline(teeth).difference(circle((0.0, 0.0), HOLE_DIAMETER_MM)).buffer(0)


def outer_ring_sample_count(teeth: int) -> int:
    return max(240, teeth * 24)


def resample_closed_ring(coords: list[tuple[float, float]], count: int) -> list[tuple[float, float]]:
    points = np.asarray(coords[:-1], dtype=float)
    segments = np.roll(points, -1, axis=0) - points
    lengths = np.linalg.norm(segments, axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(lengths)])
    total_length = cumulative[-1]

    samples = []
    for sample_index in range(count):
        distance = total_length * sample_index / count
        segment_index = np.searchsorted(cumulative, distance, side="right") - 1
        segment_index = min(segment_index, len(lengths) - 1)
        segment_length = lengths[segment_index]
        local_t = 0.0 if segment_length == 0.0 else (distance - cumulative[segment_index]) / segment_length
        sample = points[segment_index] + segments[segment_index] * local_t
        samples.append((float(sample[0]), float(sample[1])))
    return samples


def signed_area(points: list[tuple[float, float]]) -> float:
    area = 0.0
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def best_shift(
    reference: list[tuple[float, float]],
    candidate: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    reference_array = np.asarray(reference)
    candidate_options = [list(candidate), list(candidate[::-1])]
    best_score = None
    best_aligned = None

    for option in candidate_options:
        candidate_array = np.asarray(option)
        for shift in range(len(option)):
            shifted = np.roll(candidate_array, -shift, axis=0)
            score = float(np.sum((reference_array - shifted) ** 2))
            if best_score is None or score < best_score:
                best_score = score
                best_aligned = [(float(x), float(y)) for x, y in shifted]

    return best_aligned


def append_ring(
    vertices: list[tuple[float, float, float]],
    ring: list[tuple[float, float]],
    z: float,
) -> list[int]:
    start = len(vertices)
    vertices.extend((x, y, z) for x, y in ring)
    return list(range(start, start + len(ring)))


def add_strip(
    faces: list[tuple[int, int, int]],
    lower: list[int],
    upper: list[int],
    invert: bool = False,
):
    count = len(lower)
    for index in range(count):
        a0 = lower[index]
        a1 = lower[(index + 1) % count]
        b0 = upper[index]
        b1 = upper[(index + 1) % count]
        if not invert:
            faces.extend([(a0, a1, b1), (a0, b1, b0)])
        else:
            faces.extend([(a0, b1, a1), (a0, b0, b1)])


def add_cap(
    faces: list[tuple[int, int, int]],
    vertices: list[tuple[float, float, float]],
    outer_ring: list[tuple[float, float]],
    hole_ring: list[tuple[float, float]],
    layer_indices: list[int],
    z: float,
    flip: bool,
):
    polygon = Polygon(outer_ring, holes=[hole_ring])
    vertices_2d, triangles = triangulate_polygon(polygon)
    lookup = {
        tuple(round(value, 6) for value in vertices[index][:2]): index
        for index in layer_indices
    }
    vertex_map: dict[int, int] = {}

    for index, xy in enumerate(vertices_2d):
        point = (float(xy[0]), float(xy[1]))
        key = tuple(round(value, 6) for value in point)
        vertex_index = lookup.get(key)
        if vertex_index is None:
            vertex_index = len(vertices)
            vertices.append((point[0], point[1], z))
            lookup[key] = vertex_index
        vertex_map[index] = vertex_index

    for triangle in triangles:
        a, b, c = [vertex_map[int(vertex)] for vertex in triangle]
        faces.append((c, b, a) if flip else (a, b, c))


def beveled_extrude(geometry: Polygon, teeth: int) -> trimesh.Trimesh:
    inset = geometry.buffer(-EDGE_BREAK_MM).buffer(0)
    if inset.geom_type != "Polygon":
        raise ValueError(f"Edge break created unsupported geometry: {inset.geom_type}")

    outer_full = resample_closed_ring(list(geometry.exterior.coords), outer_ring_sample_count(teeth))
    outer_inset = resample_closed_ring(list(inset.exterior.coords), outer_ring_sample_count(teeth))
    outer_inset = best_shift(outer_full, outer_inset)
    hole_ring = resample_closed_ring(list(geometry.interiors[0].coords), HOLE_RING_SAMPLES)

    if signed_area(outer_full) < 0.0:
        outer_full.reverse()
    if signed_area(outer_inset) < 0.0:
        outer_inset.reverse()
    if signed_area(hole_ring) > 0.0:
        hole_ring.reverse()

    half_height = GEAR_THICKNESS_MM / 2.0
    shoulder_z = half_height - EDGE_BREAK_MM

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []

    outer_bottom = append_ring(vertices, outer_inset, -half_height)
    outer_bottom_mid = append_ring(vertices, outer_full, -shoulder_z)
    outer_top_mid = append_ring(vertices, outer_full, shoulder_z)
    outer_top = append_ring(vertices, outer_inset, half_height)

    hole_bottom = append_ring(vertices, hole_ring, -half_height)
    hole_bottom_mid = append_ring(vertices, hole_ring, -shoulder_z)
    hole_top_mid = append_ring(vertices, hole_ring, shoulder_z)
    hole_top = append_ring(vertices, hole_ring, half_height)

    add_strip(faces, outer_bottom, outer_bottom_mid)
    add_strip(faces, outer_bottom_mid, outer_top_mid)
    add_strip(faces, outer_top_mid, outer_top)

    add_strip(faces, hole_bottom, hole_bottom_mid, invert=True)
    add_strip(faces, hole_bottom_mid, hole_top_mid, invert=True)
    add_strip(faces, hole_top_mid, hole_top, invert=True)

    add_cap(faces, vertices, outer_inset, hole_ring, outer_bottom + hole_bottom, -half_height, flip=True)
    add_cap(faces, vertices, outer_inset, hole_ring, outer_top + hole_top, half_height, flip=False)

    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=float),
        faces=np.asarray(faces, dtype=np.int64),
        process=False,
        validate=False,
    )
    mesh.merge_vertices()
    return mesh


def size_xyz(mesh: trimesh.Trimesh) -> list[float]:
    return [float(v) for v in mesh.extents]


def bounds_xy(mesh: trimesh.Trimesh) -> list[float]:
    mins = mesh.bounds[0][:2]
    maxs = mesh.bounds[1][:2]
    return [float(mins[0]), float(mins[1]), float(maxs[0]), float(maxs[1])]


def arranged_mesh(meshes: list[tuple[str, trimesh.Trimesh]]):
    centers = {
        "01_gear_6t": (58.0, 188.0),
        "02_gear_12t": (188.0, 60.0),
        "03_gear_24t": (188.0, 188.0),
        "04_gear_30t": (74.0, 74.0),
    }
    placed = []
    for name, mesh in meshes:
        current = mesh.copy()
        center_x, center_y = centers[name]
        current.apply_translation((center_x, center_y, 0.0))
        placed.append((name, current))
    return trimesh.util.concatenate([mesh for _, mesh in placed]), placed


def grid_clearance_offsets(teeth: int) -> list[list[int]]:
    blocked_radius = outer_radius(teeth) + PEG_DIAMETER_MM / 2.0
    max_step = math.ceil(blocked_radius / GRID_PITCH_MM)
    blocked = []
    for dx in range(-max_step, max_step + 1):
        for dy in range(-max_step, max_step + 1):
            if dx == 0 and dy == 0:
                continue
            distance = math.hypot(dx * GRID_PITCH_MM, dy * GRID_PITCH_MM)
            if distance < blocked_radius:
                blocked.append([dx, dy])
    return blocked


def mesh_pairs():
    pairs = []
    for teeth_a, teeth_b in combinations(TOOTH_COUNTS, 2):
        center = MODULE_MM * (teeth_a + teeth_b) / 2.0
        step = center / GRID_PITCH_MM
        rounded = round(step)
        if math.isclose(step, rounded, abs_tol=1e-9):
            pairs.append(
                {
                    "pair": [teeth_a, teeth_b],
                    "center_distance_mm": round(center, 3),
                    "peg_steps": int(rounded),
                    "vectors": [[int(rounded), 0], [0, int(rounded)]],
                }
            )
    return pairs


def validate_pairs(gears_2d: dict[int, Polygon]):
    results = []
    intended_pairs = [
        (6, 12, 40.0),
        (12, 24, 80.0),
        (24, 30, 120.0),
        (6, 30, 80.0),
    ]
    for teeth_a, teeth_b, center in intended_pairs:
        gear_a = gears_2d[teeth_a]
        gear_b = gears_2d[teeth_b]
        tau_b = 2.0 * math.pi / teeth_b
        best = None

        for phase_step in range(61):
            phase = tau_b * phase_step / 60.0
            max_intersection = 0.0
            min_gap = float("inf")
            for sample in range(61):
                angle_a = (2.0 * math.pi / teeth_a) * sample / 60.0
                angle_b = phase - angle_a * teeth_a / teeth_b
                rotated_a = affinity.rotate(gear_a, math.degrees(angle_a), origin=(0.0, 0.0))
                rotated_b = affinity.translate(
                    affinity.rotate(gear_b, math.degrees(angle_b), origin=(0.0, 0.0)),
                    xoff=center,
                )
                intersection = rotated_a.intersection(rotated_b).area
                gap = rotated_a.distance(rotated_b)
                max_intersection = max(max_intersection, intersection)
                min_gap = min(min_gap, gap)

            candidate = (max_intersection, -min_gap, phase)
            if best is None or candidate < best:
                best = candidate

        results.append(
            {
                "pair": [teeth_a, teeth_b],
                "center_distance_mm": center,
                "sampled_max_intersection_area_mm2": round(best[0], 4),
                "sampled_min_gap_mm": round(-best[1], 4),
                "suggested_phase_offset_deg": round(math.degrees(best[2]), 3),
            }
        )
    return results


def build_gears_2d():
    return {teeth: gear_2d(teeth) for teeth in TOOTH_COUNTS}


def build_meshes(gears_2d: dict[int, Polygon]):
    return {
        f"{index:02d}_gear_{teeth}t": beveled_extrude(gears_2d[teeth], teeth)
        for index, teeth in enumerate(TOOTH_COUNTS, start=1)
    }


def write_notes(
    metadata: dict[str, dict[str, object]],
    pairs: list[dict[str, object]],
    validation: list[dict[str, object]],
):
    lines = [
        "# Pegboard Gears",
        "",
        "Generated from `generate_pegboard_gears.py`.",
        "",
        "## Key dimensions",
        "",
        f"- Grid pitch: `{GRID_PITCH_MM} mm`",
        f"- Gear hole diameter: `{HOLE_DIAMETER_MM} mm`",
        f"- Gear thickness: `{GEAR_THICKNESS_MM} mm`",
        f"- Module locked to board: `{MODULE_MM:.6f} mm`",
        f"- Tooth counts: `{', '.join(str(t) for t in TOOTH_COUNTS)}`",
        "",
        "## What changed from the original",
        "",
        "This variant keeps the same board-locked tooth counts and overall look, but it",
        "reduces backlash and smooths tooth entry in two ways:",
        "",
        f"- Tooth thickness at pitch circle increased to `{PITCH_TOOTH_FRACTION} * tooth pitch`",
        f"- Tooth tip width increased to `{TIP_TOOTH_FRACTION} * tooth pitch`",
        f"- Root relief kept at `{ROOT_RELIEF_FRACTION} * tooth pitch` to preserve valley clearance",
        f"- Each flank uses a gentle convex quadratic curve with `{FLANK_BULGE_MM} mm` bulge",
        f"- A small in-plane roundover of `{TOOTH_ROUNDING_MM} mm` softens the 2D tooth outline",
        f"- A real 3D edge break of `{EDGE_BREAK_MM} mm` is applied to the top and bottom outer edges",
        f"- Thickness increased to `{GEAR_THICKNESS_MM} mm` to reduce tilt on the peg while turning",
        "",
        "## Intended mesh pairs",
        "",
    ]

    for pair in pairs:
        gear_a, gear_b = pair["pair"]
        lines.append(
            f"- `{gear_a}T` + `{gear_b}T`: `{pair['center_distance_mm']} mm` center distance, use peg-step vectors `{pair['vectors']}`"
        )

    lines.extend(["", "## Sampled Non-Overlap Check", ""])
    for result in validation:
        gear_a, gear_b = result["pair"]
        lines.append(
            f"- `{gear_a}T` + `{gear_b}T`: max sampled overlap `{result['sampled_max_intersection_area_mm2']} mm^2`, min sampled gap `{result['sampled_min_gap_mm']} mm`, phase offset `{result['suggested_phase_offset_deg']}°`"
        )

    lines.extend(
        [
            "",
            "## Pegs to remove around each gear",
            "",
            "Offsets are relative to the gear center hole on the grid. These are conservative keep-clear zones based on the gear outer radius plus peg radius.",
            "",
        ]
    )

    for teeth in TOOTH_COUNTS:
        key = f"{TOOTH_COUNTS.index(teeth) + 1:02d}_gear_{teeth}t"
        lines.append(f"- `{teeth}T`: `{metadata[key]['blocked_offsets']}`")

    (ROOT / "GEARS_README.md").write_text("\n".join(lines) + "\n")
    (OUTPUT_DIR / "gear_dimensions.json").write_text(json.dumps(metadata, indent=2))


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    for old_stl in OUTPUT_DIR.glob("*.stl"):
        old_stl.unlink()

    gears_2d = build_gears_2d()
    validation = validate_pairs(gears_2d)
    meshes = build_meshes(gears_2d)
    metadata: dict[str, dict[str, object]] = {}

    ordered_meshes = []
    for name in sorted(meshes):
        mesh = meshes[name]
        path = OUTPUT_DIR / f"{name}.stl"
        mesh.export(path)
        teeth = int(name.split("_")[2].removesuffix("t"))
        ordered_meshes.append((name, mesh))
        metadata[name] = {
            "file": path.name,
            "teeth": teeth,
            "pitch_radius_mm": round(pitch_radius(teeth), 3),
            "outer_radius_mm": round(outer_radius(teeth), 3),
            "root_radius_mm": round(root_radius(teeth), 3),
            "overall_xyz_mm": [round(v, 3) for v in size_xyz(mesh)],
            "bounds_xy_mm": [round(v, 3) for v in bounds_xy(mesh)],
            "hole_diameter_mm": HOLE_DIAMETER_MM,
            "thickness_mm": GEAR_THICKNESS_MM,
            "blocked_offsets": grid_clearance_offsets(teeth),
        }

    layout_mesh, placed = arranged_mesh(ordered_meshes)
    layout_mesh.export(OUTPUT_DIR / "all_gears_layout.stl")
    metadata["all_gears_layout"] = {
        "file": "all_gears_layout.stl",
        "placements": {
            name: {
                "bounds_xy_mm": [round(v, 3) for v in bounds_xy(mesh)]
            }
            for name, mesh in placed
        },
        "validation": validation,
    }

    write_notes(metadata, mesh_pairs(), validation)


if __name__ == "__main__":
    main()
