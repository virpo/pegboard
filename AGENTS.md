# AGENTS.md

This repository is intentionally easy for coding agents to extend.

The models are parametric Python generators, not hand-authored CAD files. If you want to change the toy, edit the generators and re-export the STLs.

## Source of truth

- `scripts/generate_pegboard_shapes.py`
  Flat play pieces and the tuned peg.
- `scripts/generate_pegboard_gears.py`
  Smooth gears that mesh on the peg grid.
- `scripts/generate_pegboard_board.py`
  Board-fit coupons and full printable pegboards.
- `scripts/generate_repository_assets.py`
  README images.

## Current calibrated defaults

- Grid pitch: `40.0 mm`
- Piece hole diameter: `8.45 mm`
- Gear hole diameter: `8.45 mm`
- Peg: `7.72 mm` diameter, `40.0 mm` long, `1.2 mm` end roundover
- Printed board hole diameter: `8.30 mm` for now, still provisional

## Output folders

- `models/pieces/`
  Final play pieces and the tuned peg.
- `models/gears/`
  Final gears.
- `models/boards/`
  Full printable pegboards using the current provisional board-hole size.
- `models/board_prototypes/`
  Single-hole fit coupons for board calibration.
- `docs/`
  Supporting notes and README assets.

## Rules for agents

- Do not hand-edit STL meshes. Change the Python generators and regenerate.
- Keep canonical outputs stable unless the user is intentionally changing the defaults.
- If you are testing alternatives, create clearly named prototypes or variant folders instead of silently replacing the main set.
- If you change any canonical dimension, update the relevant README files.
- Keep the `40 mm` pitch unless the user explicitly asks to change the system scale.
- Preserve the fit-tuning story. This repo is built around real print-and-test iteration, not just geometry in the abstract.

## Good requests to try

- Make a `6x6` pegboard.
- Make the pegs longer or shorter.
- Create new pieces that connect different peg combinations.
- Scale the whole toy system down or up.
- Make tighter or looser board-fit coupons and export a new test plate.

## Regenerate

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_pegboard_shapes.py
python scripts/generate_pegboard_gears.py
python scripts/generate_pegboard_board.py
python scripts/generate_repository_assets.py
```
