# P51 phase 1 — the combo map: are the speed cells' acquisition rows the release-offset tail?

Offline phase: **no simulator, no `src/` edit, no commit, no `configs/` change.** Tree read
clean at HEAD **`f61a00b`**; `tasks.py` **`b6de439c`**, `fruits.py` **`e81051c1`** (P50),
`rl_env.py` `93e35ef7`, `configs/release_offsets_accept_s5.json` **`aa11e8c3`**,
`..._pear_s5.json` `451dcef3`, `configs/motion_reference.json` **`8a399626`**,
`..._twoline.json` **`2246f83c`**. Reader: `logs/p51/combo_map.py` (imports the P49 parsers
so the per-attempt attribution is the same object) -> `logs/p51/combo_map_out.txt`.

**The one-line answer, and it stops the phase.** Of the **5 acquisition events the speed
cells can be charged with**, **1 is the tail** and **4 are not** — one at the upper band edge
(0.380) and three firmly mid-band (0.224 / 0.231 / 0.334), and **all four non-tail rows are
*converged* closes** (residual 5.5-6.0 mm against the 6 mm tolerance), i.e. the closed
grip/hold class, not a lateral acquisition miss. The P50 table moves 2 of the 5 rows into
the band **interior**, and is predicted to **prevent one** (the single distance-class tail
row). A `O + U` battery cannot be class-clean on this corpus: **F1 fires, so the phase-2
battery is not to be spent** (`logs/p51/PREREG.md` keeps the registration and its pre-run
prediction as the record).

---

## 1. Every acquisition row, by arm

A row is an attempt that ends `nograsp` and/or prints the log's own
`fruit did not follow the gripper` note; `x` is the attempt's delivered lateral position
(the first `wait step=0 fruit_x=` sample, the same read P49 exercises — the attempt-0 block
of `d0_accept_A_s5` shows it is the selection-time x to printing precision, and P38 measured
the transport's lateral contribution at exactly 0.000 mm). `res.cls` is P48's split:
**residual > 6 mm = the distance class; <= 6 mm = a converged close** (the fingertip reached
the target and the payload was not retained).

| corpus | arm (cell) | scenario | attempts | placed | rows | the rows: species/dia, arm, x, residual, end=, class |
| --- | --- | --- | --- | --- | --- | --- |
| P44 speed | **C** | accept_s5 | 10 | 6 | **0** | — |
| P44 speed | **S1** (place 0.52) | accept_s5 | 10 | 6 | **1** | kiwi 5.6 left **x=0.3802** resid 5.5 end 8.8 **converged** |
| P44 speed | **S2** (release floor) | accept_s5 | 10 | 6 | **1** | kiwi 5.6 left **x=0.3969** resid **219.6** end 15.3 **distance / TAIL** |
| P44 speed | **S3** (lift 0.36+a1.9) | accept_s5 | 10 | 8 | **1** | lychee 3.0 left **x=0.2239** resid 6.0 end 10.0 **converged** |
| P44 speed | **S13** (the union) | accept_s5 | 10 | 6 | **0** | — |
| P44 speed | C | accept_s6 | 10 | 8 | 1 | strawberry 3.1 right x=0.3162 resid 5.8 converged |
| P44 speed | S13 (the union) | accept_s6 | 10 | **5** | 1 | the **same** strawberry row (shared) |
| P44 amend | E_C / F_C | accept_s5 | 10 / 10 | 6 / 6 | **0** | — |
| P44 amend | E_S1 (S1 + diag) | accept_s5 | 10 | 6 | 1 | the S1 kiwi reproduced (x=0.3802, identical) |
| P44 amend | E_S3v (lift 0.37 only) | accept_s5 | 10 | 6 | **0** | the clean single cell draws nothing |
| P44 amend | F_S2 (S2 + diag) | accept_s5 | 10 | 7 | 1 | the S2 kiwi on another branch (x=0.3966, resid 245.8, distance) |
| P44 speed | C / S13 | pear_s5 | 10 / 10 | 6 / 6 | **0** | — |
| P44 two-line | C | twoline_s5 | 10 | 8 | **2** | kiwi 5.4 left x=0.3908 resid 251.0 **TAIL**; peach 6.9 right x=0.2395 resid 5.9 converged |
| P44 two-line | S13 (the union) | twoline_s5 | 10 | 8 | 2 | the **same two rows** (shared) |
| P45 mass | C, M25, M50, M25S, M50S | accept_s5 | 10 each | 6/4/6/5/5 | **0** | — |
| P45 mass | C, M25, M50, M25S, M50S | pear_s5 | 10 each | 6/7/7/6/7 | **0** | — |
| P46 two-line | C | twoline_s5 | 10 | 8 | 2 | the P44 s5 pair, replayed (shared with U) |
| P46 two-line | U (the union) | twoline_s5 | 10 | 8 | 2 | the same two rows |
| P46 two-line | C | twoline_s6 | 10 | **9** | **1** | kiwi 6.2 right x=0.2730 resid **480.6** (the cross-belt displacement) |
| P46 two-line | U (the union) | twoline_s6 | 10 | **7** | **3** | **peach 6.6 left x=0.3343** resid 6.0 converged **(new)**; peach 6.6 right **x=0.2306** resid 6.0 converged **(new)**; the C kiwi (shared) |
| shipped | accept_C / accept_preprofile | accept_s5 | 10 / 10 | 6 / 5 | 1 / 1 | orange 6.4 left x=0.2155 resid 5.8 converged (one event, two logs) |
| shipped | accept_profile / pear_profile / pear_C | accept_s5 / pear_s5 | 10 / 10 / 9 | 6 / 6 / 6 | **0** | — |

Every attempt's x in these corpora: **n=170 unique**, min 0.193, p50 0.281, p90 0.347,
max 0.397, `>= 0.390` **2 (1.2 %)**. No placed attempt anywhere in the map is delivered past
**0.3714** (deduped 0.3710) — so the empirical no-placement edge is ~0.371, and the
registered tail threshold (0.390) is the conservative end of the same cliff.

## 2. The distinct events: shared with the control, or the cells' own

A row that the arm's **own control** also draws is the scenario's event, not the cell's (P46
§8 established this for the s6 kiwi; the 1133 s battery's C/U pair is bit-identical on s5).

| event | x | residual (class) | rows | arms | status |
| --- | --- | --- | --- | --- | --- |
| accept_s5 kiwi 5.6 left | **0.3969 / 0.3966** | 219.6 / 245.8 (distance) | 2 | S2, F_S2 | **new** (one instance, two branches) |
| accept_s5 kiwi 5.6 left | **0.3802** | 5.5 (converged) | 2 | S1, E_S1 | **new** |
| accept_s5 lychee 3.0 left | **0.2239** | 6.0 (converged) | 1 | S3 | **new** |
| twoline_s6 peach 6.6 left | **0.3343** | 6.0 (converged) | 1 | U | **new** |
| twoline_s6 peach 6.6 right | **0.2306** | 6.0 (converged) | 1 | U | **new** |
| twoline_s5 kiwi 5.4 left | 0.3908 | 251.0 (distance) | 4 | C, S13, U | shared |
| twoline_s5 peach 6.9 right | 0.2395 | 5.9 (converged) | 4 | C, S13, U | shared |
| twoline_s6 kiwi 6.2 right | 0.2730 | 480.6 (distance) | 2 | C, U | shared |
| accept_s6 strawberry 3.1 right | 0.3162 | 5.8 (converged) | 2 | C, S13 | shared |
| accept_s5 orange 6.4 left | 0.2155 | 5.8 (converged) | 2 | accept_C, accept_preprofile | shipped baseline |

**5 cell-attributable events; the same-battery controls draw 4 of their own** (plus the
shipped tree's baseline row). Note what the mass cells do: **zero** acquisition rows in 100
attempts across ten arms — their cost is entirely `cnp` (P45's escape/walk class), which is a
different object from this phase's question.

## 3. The counterfactual: would the P50 table have moved the row inside [0.18, 0.39]?

`x_comp = x_delivered - offset(species|diameter)`, the P50 rule. A table is **per pool**
(P50's own scope rule), and the map's coverage check is decisive for what an `O` arm can
even be run on:

| scenario | instances seen | table for this pool | covered |
| --- | --- | --- | --- |
| accept_s5 | 16 | `release_offsets_accept_s5.json` | **16/16** |
| pear_s5 | 8 (of the table's 16) | `release_offsets_pear_s5.json` (**identity**) | 8/8 (all 0.00 mm) |
| **accept_s6** | 12 | **none** — a different instance set (apple 6.9, lychee 3.6/3.7, orange 6.3/6.6, peach 6.6, pear 6.8/6.9, strawberry 3.1/3.4, tomato 6.1/6.6) | **0/12** measured; **3/12** of the names coincide with seed-5 entries (`orange6.6`, `pear6.8`, `tomato6.6`) — a licence question, not a measurement |
| **twoline_s5** | 8 | **none**, but its 8 instance names are **the seed-5 set** (kiwi 5.4/5.6, peach 6.5/6.9, pear 6.1/6.8, strawberry 3.7, tomato 6.2) | **0/8** measured; **8/8** name-covered |
| **twoline_s6** | 8 | **none** (apple 6.9, kiwi 6.2, kiwi 6.4, orange 6.6, peach 6.6, pear 6.9, strawberry 3.1/3.4) | **0/8** measured; **1/8** name-covered (`orange6.6`) |

P50's rule is that an offset is a **live per-pool** quantity (13/16 were x-independent at the
three spawn columns, the three rollers 1-3 discrete modes 11-20 mm apart), so a name match is
*not* a licence to reuse the number. It is still worth recording what the name match would
predict: the twoline_s5 kiwi 5.4 at 0.3908 -> **0.3558** (inside the band, from `kiwi|53.8`
+34.992) and the twoline_s5 peach 6.9 at 0.2395 -> 0.2330 — **but both of those rows are the
control's own events** (shared with C), so they do not enter the cell count. The cells' own
two-line rows are the s6 peaches at **0.2306 / 0.3343**, and `peach 6.6` has **no** entry in
either table even by name.

| cell event | x | offset (mm) | x_comp | inside band? | predicted prevention |
| --- | --- | --- | --- | --- | --- |
| accept_s5 kiwi 5.6 (**tail**) | 0.3969 | **+44.805** (`kiwi\|55.8`) | **0.3521** | **yes** | **yes** — the row's own mechanism is the lateral tail past the reach edge (residual 219.6, `end=` 15.3, the corpus maximum) |
| accept_s5 kiwi 5.6 (upper band) | 0.3802 | +44.805 | 0.3354 | yes | **no** — converged (5.5 mm), the close/hold class; the compensation moves the geometry but does not touch the failure |
| accept_s5 lychee 3.0 | 0.2239 | −2.820 (`lychee\|29.6`) | 0.2267 | yes (already) | no — deep mid-band, and converged at 6.0 mm |
| twoline_s6 peach 6.6 left | 0.3343 | no table (pool out of scope) | n/a | — | no — a converged close at 6.0 mm; and no offset of the measured magnitude can turn a mid-band row into a tail (the compensation only *lowers* x, and the band interior is where it already is) |
| twoline_s6 peach 6.6 right | 0.2306 | no table | n/a | — | no — same |

**So: the table is predicted to prevent 1 of the 5 cell events**, and that one is the only
distance-class row the cells own. The P50 table's largest offsets are kiwi
(+44.8 / +35.0 mm) and strawberry/orange (−28.9 / −26.9 mm) — the tail is a **positive-offset,
kiwi-bound** phenomenon (P38/P48), so the mid-band rows at 0.224-0.334 are outside its reach
by construction, not by table quality.

## 4. The second-mechanism census (the four non-tail rows)

What they share, and what separates them from the placements:

1. **They are converged close losses, not distance misses.** Residual **5.5 / 6.0 / 6.0 / 6.0**
   against the 6 mm tolerance; the catch-up ran to its break, so the fingertip was at the
   target. P48 §5 measured this class across the corpus: nothing pre-close separates it
   (residual, x0, dy0, close span all inside the placed population); what separates it is the
   aftermath — every single-arm member prints **2 `dynamic regrasp: re-seated` rows** (0/159
   placed attempts do) and, where `FRUIT_CARRY_DIAG` was on, `contacts@onset=0`,
   `min_contacts=0`, `force_min=0.00 N`.
2. **The carry signature does not separate them from the tail either.** Where the diag was
   on, *every* row of this map is never-held (`nh=3` legs on E_S1, F_S2, the two U peaches;
   `nh=1` on the twoline s5/s6 rows). "Never held" is what both classes look like from the
   hand; the difference is upstream (arrival vs retention).
3. **The `end=` shortfall is inside the successful range for all four** (8.5-10.0 mm against
   the placed population's 8.1-10.4) — P48's one pre-close signal (`end= >= 11.0 mm`,
   specific to the two 0.3966-0.3969 rows at 15.3/14.8 mm) does **not** fire on them.
4. **One is small, three are not**: the lychee 3.0 is small; the kiwi 5.6 and the two P46
   peaches (6.6) are full size. So there is no size rule to point at, and the corpus's
   **own control** draws the same class (strawberry 3.1 at 0.3162, converged). The one
   force-side reading in the record (`logs/p48` §5) is the close either completing its ramp
   around air (span 27-42 mm) or meeting the payload too hard and too early (35.85 N on the
   s6 strawberry; 60 ticks on the S3 lychee against the placed maximum of 49).
5. **This is the closed family.** `logs/p42/SIM_LIMIT.md` records it: the pads hold and the
   payload leaves, it is geometry/hardware-bounded, and the bounded levers (guard, relief,
   seat, mass, substeps, finger profile) all read negative or null. **No supply-x
   compensation can reach it.**

## 5. The control's own rows (the corpus baseline)

Same-battery controls (`C` of P44/P45/P46): **4 distinct events**, of which **1 is the tail**
(the twoline_s5 kiwi 5.4 at 0.3908) and 3 are not (strawberry 3.1 converged 0.3162; peach 6.9
converged 0.2395; kiwi 6.2 the 480.6 mm cross-belt **displacement** at 0.2730 — the corpus's
only cross-belt drift row, P48 §2.2). The shipped tree's baseline (`p39/p3/accept_C`,
`p41/p2/accept_profile` + `accept_preprofile`, `pear_*`) draws **1** event: the orange 6.4 at
0.2155, converged, on the pre-profile log (the P41 profile arm draws none).

So the controls draw the **same mix** as the cells, including a tail row of their own — the
cells' rows are not a new class of failure.

## 6. The counts, and the read

| | rows | distinct events | tail (>= 0.390) | mid/upper (< 0.390) | distance (> 6 mm) | converged (<= 6 mm) |
| --- | --- | --- | --- | --- | --- | --- |
| P44 speed (single, 5 arms × 2 seeds) | 5 | 4 | 1 | 3 | 1 | 3 |
| P44 amend (5 arms) | 2 | 2 | 1 | 1 | 1 | 1 |
| P44 two-line (2 arms) | 4 | 2 | 1 | 1 | 1 | 1 |
| P45 mass (10 arms) | **0** | **0** | — | — | — | — |
| P46 two-line (4 arms) | 8 | 5 | 1 | 4 | 2 | 3 |
| shipped (5 logs) | 2 | 1 | **0** | 1 | 0 | 1 |
| **cell-attributable** | — | **5** | **1** | **4** | **1** | **4** |
| **control (same battery)** | — | **4** | **1** | **3** | **2** | **2** |

**The Fisher-ish read.** The tail share is **1/5 in the cells and 1/4 in their own controls**
(p0 = 0.556, two-sided = 1.000): the two mixes are the same object, so the tail is **not** a
cell-specific signature. The pooled 2x2 reproduces P48 on this corpus — **tail 6/6 fail vs
below 15/325 (p0 = 2.4e-8)** — i.e. the tail is a real failure mode, it is simply not what the
speed cells add.

**Where the cells' *count* cost actually sits** (`x of the acq rows` = the per-arm class
split, §5 of the reader). This is the decisive table for the phase-2 design:

| battery | control | union/cell | where the placements went |
| --- | --- | --- | --- |
| P44 accept_s5 | 6 placed / 4 cnp / 0 nograsp | S1 6/3/1, S2 6/3/1, S3 **8**/1/1 | **no count loss at all** at seed 5 (S3 is +2) |
| P44 accept_s6 | 8 placed / 1 cnp / **1** nograsp | S13 **5**/4/**1** | **+3 cnp** — carried-not-placed; the acquisition row is *identical* in both arms |
| P46 twoline_s6 | 9 placed / 0 cnp / **1** nograsp | U **7**/0/**3** | +2 nograsp, **both converged** (prevention: no) |
| P45 mass | 6 placed / 4 cnp | M25 4/6, M50 6/3, M25S 5/5, M50S 5/5 | cnp only, 0 acquisition rows |

The union's own measured regression (P44's E2 at seed 6, 8 -> 5 placed) is **`cnp`**, not an
acquisition row: no release-offset compensation is an object for it. And the two-line's -2
(P46) are two converged closes, which `SIM_LIMIT.md` closes.

## 7. The verdict

**F1 (PREREG) fires: the speed cells' acquisition rows are not the tail.** The count is
1 tail of 5 cell-attributable events (4 of 5 are non-tail, and every non-tail row is a
converged close, i.e. the grip class). Two consequences the phase must state plainly:

1. **`O + U` cannot be class-clean**, which was the whole point of the combination: the one
   convertible event per seed-5 acceptance *draw* is not the class the count loss is in, and
   the acceptance's own measurement of the tail is 0/10 in both P50 arms (its power statement:
   ~60 releases/arm ~ 1 event of exposure).
2. **The speed gain stands separately** (P44: -1.45 s/attempt on the union; P46: -0.76 s
   pooled, -10.7 % on the seed-5 branch) and its cost is measured as branch-draw `cnp`
   (single arm) and converged closes (two-line) — **not** a supply-x object.

**Recommendation: stop. Do not spend the phase-2 battery.** Its registered endpoints would
read: E1 (the tail) 0 convertible events per run at the acceptance's exposure, E2 (the
acquisition rows) a null by construction, E3 (placed) a branch draw with ~0.10 s.d. per run,
E4/E6 (the speed and the pear) already measured. The registration is kept in
`logs/p51/PREREG.md` with its pre-run prediction, per this project's practice (P47/P48/P49).

**What this map does not claim.** No rate: every count is one deterministic branch's count
(AGENTS §2) and the cell rows are branch draws — the same cell (S13) draws **0** rows at seed
5 and the shared strawberry at seed 6. No claim that the tables are wrong, only that their
object (the release x) is not this corpus's cost. No claim about the direct/policy interface
(a different presentation, P43's park default) or about the two-line pools' offsets (no table
exists; P50's scope rule needs a per-pool measurement). E4's displacement (480.6 mm, 379 mm
cross-belt) stays P48's unseparated two-candidate event.

Evidence: `logs/p51/combo_map.py` (the reader — the P49 parsers imported, so the attribution
is not a re-derivation), `logs/p51/combo_map_out.txt` (its full output: the row tables, the
event dedup, the counterfactual arithmetic, the coverage check, the per-arm class split, the
Fisher reads). Every log cited is an existing artefact of P39/P41/P44/P45/P46/P50.
