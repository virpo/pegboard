# Board Fit Prototypes

Generated from `generate_pegboard_board.py`.

These are minimal single-hole coupons to calibrate the peg fit for a fully 3D printed backboard before committing to a full board print.

## Best guess

- Peg CAD diameter: `7.72 mm`
- Observed printed peg diameter: about `7.92 mm`
- Coupon thickness: `15.0 mm`
- Coupon wall thickness: `4.0 mm`
- Recommended first test: `8.30 mm`
- Prototype hole diameters: `8.25 mm, 8.30 mm, 8.35 mm`

The board should hold the peg more tightly than the loose-moving play pieces, so this test range is centered lower than the piece-hole test range.
The coupon thickness is set to the same `15 mm` as the intended printed board so the test matches the final board more closely.

Once you pick the winning hole diameter, the same script can generate full printed boards at `15.0 mm` thickness and `40.0 mm` peg spacing.
