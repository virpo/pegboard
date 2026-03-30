# Printable Pegboards

Generated from `generate_pegboard_board.py`.

These are the current full-board exports using the present best-guess printed-board hole diameter.
The board-hole size is still provisional until the single-hole coupon test is confirmed physically.

## Current provisional settings

- Hole diameter: `8.30 mm`
- Board thickness: `15.0 mm`
- Grid pitch: `40.0 mm`
- Edge margin: `20.0 mm`

## Files

- `models/boards/01_pegboard_4x4_hole_8p30_provisional.stl`
- `models/boards/02_pegboard_5x5_hole_8p30_provisional.stl`
- The `4x4` board is `160 x 160 mm` overall.
- The `5x5` board is `200 x 200 mm` overall.

If the coupon test later points to a different hole diameter, update `BOARD_HOLE_DIAMETER_MM` in `scripts/generate_pegboard_board.py` and regenerate.
