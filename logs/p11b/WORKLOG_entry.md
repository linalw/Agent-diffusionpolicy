### P11-B (2026-10-18): the squeeze probe - the ejection is a kinematic wedge of the jaws' arrival (the plow reading WITHDRAWN per the Oracle R1 - the probe's plow ran a rise-and-return, not the shipped descent; the corrected re-run pending), insensitive to the contact parameters

**The probe** (`scripts/210_squeeze_probe.py`, new; 8 sweep runs): the shipped cell, one fruit
per class, the left arm at the calibrated grasp seed, a stopped belt, no task loop; groups
`belt` (close from open, then the sweep), `air` (held, then the sweep), `plow` (the shipped
re-seat geometry: the jaws at the gap descending 40 mm onto the fruit), `drop`, `baseline`;
delta in {-15..+15} mm, 3 repeats. **The pads stop at the fruit's surface** (link span
62.1-62.7 mm vs the 51.0 mm tomato; 75.6 vs 64.5 mm apple) and the response is **bit-identical
across 20 mm of commanded interference** - the sub-width command beyond the surface is not
realized. **The escape is group-specific: `belt` 0/3 and `air` 0/3 at every delta; `plow` 3/3
at every delta >= -5** (v_esc 0.176 m/s tomato / 0.170-0.186 apple, displacement 35.8 mm, then
the fall) - even a gap EQUAL to the extent ejects; a 15 mm-wider gap does not. **The parameter
sensitivity: substeps=4, finger k 30000->4000, the fruit-side compliant contact and the
restitution 0.5 all leave the escape unchanged; the pad-lift -10 mm (standoff 70->50) is the
ONLY variant that removes it (0/3).** The drop baseline reproduces 4.823 m/s (theory 4.791) -
the log falls are free fall, confirmed. **Readings:** (1) the ejection is a kinematic wedge of
the tapered descending fingers, not a stiffness-driven squirt; (2) the physics-side compliance
options do not fix it (the audit's caveat, now measured); (3) the control-side fix needs a
**standoff** floor (`live_extent + margin`), not "extent - margin", and/or a re-seat descent
geometry change - the grip and the squeeze themselves never eject (the `belt`/`air` groups).
