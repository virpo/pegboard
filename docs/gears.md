# Pegboard Gears

Generated from `generate_pegboard_gears.py`.

## Key dimensions

- Grid pitch: `40.0 mm`
- Gear hole diameter: `8.45 mm`
- Gear thickness: `6.0 mm`
- Module locked to board: `4.444444 mm`
- Tooth counts: `6, 12, 24, 30`

## What changed from the original

This variant keeps the same board-locked tooth counts and overall look, but it
reduces backlash and smooths tooth entry in two ways:

- Tooth thickness at pitch circle increased to `0.405 * tooth pitch`
- Tooth tip width increased to `0.185 * tooth pitch`
- Root relief kept at `0.08 * tooth pitch` to preserve valley clearance
- Each flank uses a gentle convex quadratic curve with `0.2 mm` bulge
- A small in-plane roundover of `0.4 mm` softens the 2D tooth outline
- A real 3D edge break of `0.4 mm` is applied to the top and bottom outer edges
- Thickness increased to `6.0 mm` to reduce tilt on the peg while turning

## Intended mesh pairs

- `6T` + `12T`: `40.0 mm` center distance, use peg-step vectors `[[1, 0], [0, 1]]`
- `6T` + `30T`: `80.0 mm` center distance, use peg-step vectors `[[2, 0], [0, 2]]`
- `12T` + `24T`: `80.0 mm` center distance, use peg-step vectors `[[2, 0], [0, 2]]`
- `24T` + `30T`: `120.0 mm` center distance, use peg-step vectors `[[3, 0], [0, 3]]`

## Sampled Non-Overlap Check

- `6T` + `12T`: max sampled overlap `0.0 mm^2`, min sampled gap `0.2017 mm`, phase offset `15.0°`
- `12T` + `24T`: max sampled overlap `0.0 mm^2`, min sampled gap `0.3021 mm`, phase offset `7.5°`
- `24T` + `30T`: max sampled overlap `0.0 mm^2`, min sampled gap `0.3537 mm`, phase offset `6.0°`
- `6T` + `30T`: max sampled overlap `0.0 mm^2`, min sampled gap `0.2333 mm`, phase offset `6.0°`

## Pegs to remove around each gear

Offsets are relative to the gear center hole on the grid. These are conservative keep-clear zones based on the gear outer radius plus peg radius.

- `6T`: `[]`
- `12T`: `[]`
- `24T`: `[[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]]`
- `30T`: `[[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]]`
