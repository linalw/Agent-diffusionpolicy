# P130 - the ring with the close freeze off: the lead is real (+28.7 points), the ring still loses

P129 named the cell: `cage4` + `FRUIT_DYNAMIC_CLOSE_FREEZE=0` + the shipped pad
material, because its fixture showed the **freeze** - not friction - is what
denies the enclosure. This phase ran it: single arm (the cage hand refuses a
`CoopSession`), 20 attempts x seeds 5/6, `FRUIT_CAGE_PROBE=1` and the P108
instrumentation; the controls are the same seeds' `cage4` cells from P108
(`B_s5`, `B_s6`, freeze on).

**No `src/` or `configs/` change; the knob is the shipped `FRUIT_DYNAMIC_CLOSE_FREEZE`.**

| cell | freeze | placed | clean enclosure | jam | over-closure | no contact |
| --- | --- | --- | --- | --- | --- | --- |
| `B_s5` (P108) | on | 3/18 | 1 | 0 | 8 | 2 |
| `B_s6` (P108) | on | 3/14 | 1 | 0 | 2 | 3 |
| **pooled control** | on | **6/32 = 18.8 %** | **2/32** | 0 | 10 | 5 |
| `F5` | **off** | 9/20 | 2 | 0 | 11 | 4 |
| `F6` | **off** | 10/20 | 6 | 0 | 11 | 5 |
| **pooled treatment** | off | **19/40 = 47.5 %** | **8/40** | 0 | 22 | 9 |

* **The rate: 19/40 against 6/32 - +28.7 points, Fisher p = 0.0135.** The freeze
  was costing the ring a quarter of its rate, exactly as P129's fixture
  predicted (the first-contact freeze held an aperture `2 delta` too wide).
* **The clean enclosure: 8/40 against 2/32 - p = 0.169, not converted.** The
  dominant failure is now **over-closure** (22/40: the measured aperture is
  below `dia - 4 mm`, i.e. the ring drives its pads inside the fruit), which is
  the closure law's defect P108 measured, not the freeze.
* **The ring still loses to the shipped hand**: 47.5 % against the two-line's
  **58/80 = 72.5 %** (four seeds). The gap is the over-closure plus the moving
  arrival.

**Verdict: the freeze is a real term for the ring, and the ring is still not
shippable.** The lane stays opt-in; the next named term is the **closure law**
(the ring closes to `0.98 x` the widest extent; the small/narrow fruits are
driven through), which is P108's `FRUIT_GRIPPER_SQUEEZE` family - already
measured negative at 0.94 on the old aperture - and the moving arrival (P108's
56 mm), which no closure law fixes.

## Files

`logs/p130/{F5,F6}.log`, `report.py` -> `report.txt` (P110's jam/over-closure/
clean split joined to the approach's `end=`), this file. No `src/` or `configs/`
change; the references are the shipped `30fb99f8` / `30fb99f8` / `8952c320`.
