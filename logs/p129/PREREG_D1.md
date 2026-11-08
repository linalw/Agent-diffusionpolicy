# P129 - deviation D1 (registered after the fact, before the tables were read)

**D1 (2026-11-07).**  The **cage3** session of bench B is not evaluable on this
bench's payload: a three-fold ring cannot centre a four-fold face set, and its own
support proof fails (**10 mm -> 5.19 mm** against the registered `<= 0.5 x off0`;
`logs/p129/fixture_ring_cage3.log`).  The session therefore spends no real cell,
and the three-pad claim is taken from P112's own fixture (0.84-0.91 s, `pads == 3`
on 18/30 cells) plus this phase's re-derivation, which reproduces it.  The phase's
question was the four-pad nail; the cage4 cells in `RESULTS.md` section 3 are
unaffected.

The registration's own text (`PREREG.md`, md5 `a8b1e4ed`) is unchanged; this file
is the register entry, by the `PREREG_A1.md` convention.
