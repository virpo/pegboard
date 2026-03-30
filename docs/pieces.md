# Pegboard Shapes

Generated from `generate_pegboard_shapes.py`.

## Default dimensions

- Pegboard pitch: `40.0 mm`
- Piece width: `16.0 mm`
- Piece thickness: `3.0 mm`
- Peg hole diameter: `8.45 mm`
- Recommended peg diameter: `7.72 mm`
- Peg length: `40.0 mm`
- Peg end roundover: `1.2 mm`

The hole diameter is intentionally tuned upward because your printer closes printed holes relative to CAD. The recommended peg diameter is tuned downward because your printer makes outside diameters print slightly oversized. If your printer runs tighter or looser later, edit `HOLE_DIAMETER_MM` and `PEG_DIAMETER_MM` in `scripts/generate_pegboard_shapes.py` and re-run the script.

The single exported peg is the measured best-fit version: `7.72 mm` CAD diameter, `40.0 mm` length, and `1.2 mm` end roundover.

## Files

Each STL in `models/pieces/` is a separate printable part. `models/pieces/all_shapes_layout.stl` contains the seven flat pieces arranged on one virtual plate for quick viewing. The tuned peg is exported into the same folder as its own STL.

Drag any STL directly into Bambu Studio. If you want to inspect or re-export later, keep the Python source file because all dimensions are parametric there.
