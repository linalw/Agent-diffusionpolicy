# P41 phase 1 — the finger-drive fidelity sweep: the 2.2x force is **free**, and it
# is the drive's *damping*, not its stiffness

Measured 2026-10-26 on the P40-final tree `ae0a579` (clean; `tasks.py` `ec991e5c`,
`control.py` `54e6fb5c`, `scene.py` `988985ef`, `common.py` `2b1c1b71`,
`configs/motion_reference*.json` untouched — `logs/p41/sweep/00_tree_pins.txt`).
**No `src/` change, no `configs/` change, no commit.** All knobs already existed
(`FRUIT_SUBSTEPS` `common.py:20`; `FRUIT_FINGER_STIFFNESS`/`_DAMPING`
`control.py:170-173`; read-back through the P40 default-off `FRUIT_GRIP_EFFORT=1`
instrument, `tasks.py` `2251-2430`).

One claim drove the 8-cell grid sequentially (`logs/p41/claim_sweep.log`,
08:53:06→09:10:38, **1 041 s for eight cells, no wedge, no retry**); five further
claims drove the **12 post-hoc bracket cells** of §3 (`logs/p41/claim_bracket*.log`).
Total simulator wall ≈ 31 min over 20 runs, none wedged.

---

## 0. The answer in one screen

* **The untested half of the P40 finding pays off: 2.2x the delivered pinch at
  ~zero wall cost.** On the acceptance scenario at the shipped 120 Hz physics,
  `FRUIT_FINGER_STIFFNESS` = 300000 / 100000 / 50000 delivers **9.75 / 9.87 /
  9.79 N** (median of the `close_freeze` 5-tick windows, two grabs each) against
  the shipped cell's **4.38 N**, at **72/73/72/72 s** of wall — **1.00-1.01x**.
  `FRUIT_SUBSTEPS=4` reaches the same force for **2.54-2.85x** at this cell size
  (3.08x on the 10-attempt battery of record, `EFFORT_READ` §0). So the free
  lever exists and it beats 480 Hz on both axes.
* **The stated mechanism is wrong, and the measurement says so cleanly.** The
  force step is **not** "a softer drive penetrates less": softening from
  k = 1e6 to 3e5 with the *asset's* damping (c = 100) leaves the pinch at
  **4.44 N** (`rho_soft`), and authoring the asset's own gains (k = 1e6, c = 100)
  on **both** finger joints is **byte-identical to the shipped run** — 0/102
  non-instrument lines differ, and the freeze reads 4.52/4.23 N, the same two
  digits (`rho_asset`; the mimic joint2 gets gains from the same call but keeps
  its **0.0 N cap**, so that half of the knob is inert by construction, and the
  sweep's `maxForce=10.0/0.0N` read-back says so in every cell). What the knob
  changes is the **damping**:
  `control.py`'s default is **2 % of k**, so the same three cells ran at
  c = 6000/2000/1000 Ns/m against the asset's authored **100**.
* **The corpus collapses on the damping ratio c/k, not on k or c** (§3): at a
  fixed c = 1000 Ns/m, k = 1e5 / 3e5 / 1e6 reads **9.81 / 10.00 / 4.49 N**; at a
  fixed ratio 0.02, k = 5e4…1e6 (a 20x range) reads **9.75-9.87 N**. The
  threshold is between c/k = 0.002 (7.2 N) and 0.0033 (10.0 N), and a second,
  independent condition is the drive's own law: at k = 1000 the authored
  `k*err` = 4.2 N is *below* the cap and the pinch delivers exactly that
  (**4.17 N**).
* **Nothing else pays for it.** The close is **3-9 ticks faster** (25/31 shipped
  → 22/23), it freezes at a **4 mm wider** command (62.4/66.3 → 66.4/70.4 mm) and
  the **achieved jaw span is identical** (71.5/75.7 mm) — i.e. the pads stop
  earlier at the same fruit geometry, they do not squeeze deeper. Every cell's
  descents are **inside the motion budgets** and no new failure reason appears.
* **The class did not move at 120 Hz, and that is the honest caveat.** All four
  120 Hz cells land on the *same* two attempts as the shipped cell (left peach
  idx 3, left peach idx 12) and the same outcome **0/2** with the same sim
  windows (7.3-21.2 s, 24.5-40.7 s): the two left carried-not-placed failures
  survived a 2.2x pinch. The 480 Hz cells land elsewhere (2/2, 1/2, 2/2, 1/2 —
  a different attractor, §2) and one of them loses the kiwi with "fruit did not
  follow the gripper". **Two attempts are not a class measurement** — that is
  phase 2's battery — but the first sample does not support "more force converts
  the class", which is exactly the PREREG's falsifier 2.
* **The 8-cell grid alone cannot see the mechanism** — every one of its cells has
  c/k = 0.02 because the damping defaults to 2 % of k — hence the 12 post-hoc
  bracket cells in §3. They are reported separately and never mixed into §2's grid.

---

## 1. The scenario and the read

Every cell: the acceptance scenario (`20_pick_place.py`, `ATTEMPTS=2 SEED=5`,
`HEADLESS=1 FRUIT_MOTION_REPORT=1`) plus the committed default-off instrument
`FRUIT_GRIP_EFFORT=1`. Eight cells, one `154_claim_run.sh` claim, sequential
(`logs/p41/sweep_cells.sh`):

| group | `FRUIT_SUBSTEPS` | `FRUIT_FINGER_STIFFNESS` |
|---|---|---|
| sub1_k0 / k300000 / k100000 / k50000 | 1 (120 Hz) | 0 (asset) / 3e5 / 1e5 / 5e4 |
| sub4_k0 / k300000 / k100000 / k50000 | 4 (480 Hz) | 0 (asset) / 3e5 / 1e5 / 5e4 |

`FRUIT_FINGER_DAMPING` was left unset in all eight so `control.py`'s own default
(**2 % of k**) applies. **The `k=` column of the table is the runtime
read-back** from the `[effort]` banner (`get_dof_gains`), not the env string:
`1000000/0` on the shipped path (joint1 driven, **joint2 the drive-less mimic**)
and `k/k` once the knob is on, because `set_dof_gains` is called on
`finger_dofs` = **both** joints.

Rows read (one line each, `logs/p41/sweep_table.txt`, re-derived by
`logs/p41/sweep_table.py`):

* (a) `[effort] … close_freeze … tact[N]=f0,f1 sum=… | j1: proj[N]=… err[mm]=…`,
  5-tick medians over the first 5 ticks of the post-close hold;
* (b) `[task] dynamic close: sustained contact after N ticks (force=f N,
  span=s mm); freezing the closing command at c mm` — the single-tick force at
  the freeze tick, the closing time and the jaw geometry;
* (c) `[run] attempt i: grasped=… placed=… lift=… force=N N notes=[…] sim=a-bs`
  and the per-attempt summary row `[run] <fruit> arm=… lift=… N=<…> sim=…s` — the
  outcome and the attempt's own **max tactile force** (`N=`, an instrument
  independent of (a));
* (d) `[stats] … sim=… total, …s/attempt` and the cell's measured wall
  (`logs/p41/sweep/wall.tsv`, `date +%s` around the run);
* (e) the notes column and `scripts/105_motion_regression.py`.

---

## 2. The 8-cell table

Force = median of that cell's `close_freeze` tactile sums (n = grabs, each a
5-tick median; **n = 2** — the brief's `ATTEMPTS=2` per cell). `load/cap` =
`|proj[N]| / maxForce[joint1]` = the per-face fraction of the **10 N/joint** cap
(P40's definition). `F/err` = `|proj| / |err|` at the operating point — a ratio,
not a stiffness. `x ship` = that cell's wall over the shipped cell's 72 s.

| cell | k read-back | force [N] | min–max | × shipped force | l/cap | err [mm] | F/err [N/m] | close ticks | `[run]` force [N] | placed | sim [s] | wall [s] | × ship |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **sub1_k0** (shipped) | 1000000/0 | **4.38** | 4.23–4.52 | 1.00x | 0.181 | 4.36 | 416 | 25, 31 | 4.51, 4.41 | 0/2 | 30.1 | **72** | 1.00x |
| sub1_k300000 | 300000/300000 | **9.75** | 9.71–9.78 | **2.22x** | 0.517 | 3.92 | 1322 | 23, 22 | 10.01, 9.79 | 0/2 | 30.1 | 73 | 1.01x |
| sub1_k100000 | 100000/100000 | **9.87** | 9.71–10.02 | **2.25x** | 0.507 | 3.91 | 1297 | 23, 22 | 9.98, 9.59 | 0/2 | 30.1 | 72 | 1.00x |
| sub1_k50000 | 50000/50000 | **9.79** | 9.71–9.86 | **2.23x** | 0.495 | 3.88 | 1276 | 23, 23 | 9.31, 9.75 | 0/2 | 30.1 | 72 | 1.00x |
| sub4_k0 | 1000000/0 | 9.45 | 8.91–9.99 | 2.16x | 0.366 | 4.51 | 812 | 20, 19 | 10.00, 9.79 | 2/2 | 32.2 | 205 | 2.85x |
| sub4_k300000 | 300000/300000 | 5.01\* | 0.00–10.02\* | 1.14x\* | 0.251\* | 2.08\* | 1206\* | 25 | 10.02, **0.00** | 1/2 | 29.3 | 183 | 2.54x |
| sub4_k100000 | 100000/100000 | 10.04 | 10.04–10.05 | 2.29x | 0.338 | 4.95 | 684 | 26, 32 | 10.03, 12.05 | 2/2 | 28.9 | 191 | 2.65x |
| sub4_k50000 | 50000/50000 | 5.01\* | 0.00–10.02\* | 1.14x\* | 0.252\* | 2.08\* | 1210\* | 25 | 10.02, **0.00** | 1/2 | 29.3 | 183 | 2.54x |

\* **The two `0.00` rows are a different attempt, not a weak pinch**: those cells'
second grab is the **kiwi idx 2**, which they *failed to grasp* (`grasped=False
lift=+0.000 m notes=['fruit did not follow the gripper']`), so the freeze window
armed with no contact (`err` 0.21 mm, `kpc` -60 N). The same-grab comparison is
the right read: **left peach idx 3 reads 9.99 / 10.02 / 10.04 / 10.02 N** in
sub4_k0 / k300000 / k100000 / k50000 — flat, and identical to P40's 9.95 N.
Excluding the no-contact row, the two-limb sub4 medians are 9.45 / 10.02 / 10.04
/ 10.02 N.

**Reading the table.**

* **sub1 (120 Hz, the shipped physics rate): the step is 4.38 → 9.8 N, i.e. a
  plateau 2.2x the shipped pinch, at 1.00-1.01x wall.** The three plateau cells
  differ by 0.12 N — inside the grab-to-grab spread (each cell's own two grabs
  differ by 0.07-0.31 N), so **the grid does not resolve k**; it only shows that
  every k in 5e4…3e5 with the 2 % damping default crosses the same step. That is
  what §3 explains.
* **Delivery fraction: 22 % → 50 % of the per-joint cap.** 4.42 N = 2.21 N per
  face = 22.1 % (reproducing `EFFORT_READ` §0's 4.42 N / 0.221 on the same
  scenario at 10 attempts, 4.38 N here at 2); the plateau is **5.0 N per face =
  50 %** — and the physics' own reaction agrees: the plateau cells' `proj` sums
  read **10.00 N** while their tactile reads 9.71-10.02 (tact/proj 0.97-1.00),
  a second instrument at a different buffer.
* **`F/err` is 416 → ~1 280 N/m.** P40 measured 377 (sub1) and 1 045 (sub4). The
  ratio moves 3x while the drive's k moves 2-20x in the *opposite* direction and
  is irrelevant across 5e4…1e6 at a fixed ratio (§3) — so this is an
  operating-point signature, not a stiffness, exactly as `EFFORT_READ` §4 says.
* **The knob programs `joint2` but gives it a 0 N cap**, so it cannot contribute
  force: every plateau cell's banner reads `k=…/… c=…/… maxForce=10.0/**0.0**N`,
  the same caps as shipped. That is *why* `rho_asset` (§3) is byte-identical by
  construction rather than by luck — the only physical change the knob can make
  is **joint1's own k and c**.
* **The force is a level, not a spike.** Four independent reads agree per cell:
  the 5-tick freeze median (9.75-9.87), the single-tick `[task]` freeze force
  (9.77-10.00), the carry legs' medians (9.73-10.02 across `grasp_lift`/`place0`)
  and the attempt's `[run] force=` max (9.31-10.01). The shipped cell reads
  4.22/4.12 (task) vs 4.38 (median) vs 4.51/4.41 (max) by the same four reads.
  **The spread across grabs is the same shape as the shipped cell's** (0.07-0.31 N
  vs 0.29 N), scaled 2.2x: no cell shows a one-grab spike.
* **Close ticks fall, they do not rise:** 25/31 (shipped) → 22/23 in all six
  120 Hz plateau cells. The freeze criterion is "tactile ≥ threshold *and*
  stalled", and
  a firmer pinch reaches the threshold **3-9 ticks (0.03-0.08 s)** earlier. The
  freeze command is correspondingly **~4 mm wider** (62.4/66.3 → 66.4/70.4 mm)
  and the **achieved span unchanged** (71.6/75.6 → 71.5/75.7 mm): the pads stop
  sooner at the same fruit width, so nothing is compressed harder.
* **sub4 is the *other* lever to the same plateau** — at the asset's gain it is
  already 9.45-9.99 N (P40's 9.95), i.e. 480 Hz and the 2 % damping both land on
  ~10 N. The substeps cells cost **2.54-2.85x wall at this 2-attempt cell size**;
  the cost of record is P40's **3.08x at 10 attempts** (266 → 819 s), which is
  the number to quote — a 2-attempt cell's ratio is not comparable to it.
* **Success counts are not comparable here.** The 120 Hz cells are one attractor
  (0/2, the same two left peaches), the 480 Hz cells are three (2/2, 1/2, 2/2,
  1/2) because the physics rate changes the branch. Per AGENTS §2 a count across
  them measures the attractor.

---

## 3. Why the shipped pinch was at 22 % — and what actually moves it

`EFFORT_READ` §4 left the *law* unidentified and called the 4.4 N a timestep
signature. The grid cannot separate k from the damping that travels with it
(`control.py` derives c = 2 %·k), but the brackets can, and they localise it —
and because joint2's cap is **0.0 N** (above), the whole effect must sit in
**joint1's own k and c**:

| cell (post-hoc) | k [N/m] | c [Ns/m] | c/k | force [N] | what it excludes |
|---|---|---|---|---|---|
| shipped (`sub1_k0`) | 1e6 / **0** | 100 / 0 | 1e-4 | **4.38** | — |
| `rho_asset` | 1e6 / 1e6 | 100 / 100 | 1e-4 | **4.38** | **the second joint's drive** (byte-identical to shipped, 0/102 lines) |
| `rho_soft` | 3e5 / 3e5 | 100 / 100 | 3.3e-4 | 5.89 (4.44 / 7.35, two different fruits) | **k alone**: same k as `sub1_k300000`/`k3e5_c1000`, 4.44 N on the shared fruit (left idx 3) |
| `c300` | 1e6 | 300 | 3e-4 | 4.38 | — |
| `c500` | 1e6 | 500 | 5e-4 | 5.61 | — |
| `c1000` (k=1e6) | 1e6 | 1000 | 1e-3 | 2.25† | — |
| `c2000` | 1e6 | 2000 | 2e-3 | 7.21 | — |
| `k3e5_c1000` | 3e5 | 1000 | 3.3e-3 | **9.88** | — |
| `k1e5_c1000` | 1e5 | 1000 | 1e-2 | **9.81** / 14.30‡ | — |
| `k1000` | 1e3 | 20 | 2e-2 | **4.17** | the ratio alone (the law binds: `k*err` = 4.2 N) |
| `sub1_k50000` … `k1000000` (six cells, §2 + brackets) | 5e4…1e6 | 2 %·k | **2e-2** | **9.75-9.87** | **k** across a 20x range |

† that cell's second grab also failed to grasp (`tact 0.00`, `lift +0.000 m`), so
its median is one grab; ‡ second grab is a different, larger fruit (its **max**
tactile force 14.80 N — the plateau is per-fruit, not a fixed 5 N/face).

**The empirical model (two conditions, both measured):**

```
delivered pinch  ≈  min( k · err ,  plateau )
    plateau ≈ 9.7-10.0 N  when  c/k ≥ ~3e-3   (120 Hz)
    plateau ≈ 9.5-10.0 N  whenever the physics runs at 480 Hz (asset gains)
```

* **Below c/k ≈ 5e-4 the drive gives**: 4.2-4.4 N (asset, c300) — the P40 state.
  The transition is bracketed by c/k = 0.002 (7.2 N) and 0.0033 (10.0 N).
* **The decisive pair is one k with three c** — at **k = 3e5**, on the *same*
  fruit (left peach idx 3): c = 100 → **4.44 N**, c = 1000 → **10.00 N**,
  c = 6000 → **9.78 N**. k is fixed, c moves 60x, the delivered pinch moves
  2.25x. **At a fixed c = 1000 Ns/m, on that same fruit, the force follows k**
  (4.49 at k = 1e6, 9.81 at 1e5, 10.00 at 3e5), and **at a fixed ratio it is flat
  over 20x of k**
  (9.75-9.87) — so neither alone is the variable: the collapse is on **c/k**.
  `logs/p41/ratio_collapse.py` → `ratio_collapse.txt` re-derives all three
  statements from the logs.
* **The drive's own law is a second, independent ceiling**: at k = 1000 the
  authored `k*err` = 4.25 N is *below* the 10 N cap and the pinch delivers
  4.17 N — the drive is then force-limited by its own law, and (as
  `GRIP_CENSUS` §332 predicted for a soft drive) the close is **slower**
  (29/38 ticks vs 22/23) because the pads must travel deeper to reach even that
  force (freeze command 62.3/66.2 mm ≈ the shipped 62.4/66.3).
* **Why the ratio and not k** is *not* identified: a plausible reading is that
  PhysX's implicit position drive's damping term enters the step's Jacobian, so
  c/k sets how much of the commanded error survives one 1/120 s step; the
  substeps lever (dt) then acts on the same quantity in a form this corpus does
  not reduce to one dimensionless number (at 480 Hz even c/k = 1e-4 reaches the
  plateau, and the plateau value is the *same* ~10 N at both rates). The
  plateau's rate-independence argues it is a **contact/impulse equilibrium**,
  not a drive artefact — but that is a hypothesis, not a measurement.

**What this does to the P41 hypothesis as written** (§3 of the phase plan): *"the
22 % delivery is a penetration effect — a k = 1e6 drive overshoots 5.6 mm and the
solver cannot push back harder within one step; a softer drive (2e4-1e5) would
deliver the same or more force at no wall cost."* **The prediction is right, the
mechanism is wrong.** The force does rise 2.2x at no wall cost, but:
`rho_asset` (asset k, asset c, both joints) is the shipped run to the byte, and
`rho_soft` (k = 3e5, asset c) stays at 4.44 N — so the stiffness is not the
lever, and the sweep's three k values only worked because the knob's **damping
default** travelled with them.

---

## 4. The best cells by (force ≥ 8 N) / wall

All three 120 Hz plateau cells clear the 8 N bar at 1.00-1.01x, so the ranking is
on the force and on how far the setting departs from the asset:

| rank | cell | force | wall | why |
|---|---|---|---|---|
| **1** | **`FRUIT_FINGER_STIFFNESS=100000`** (c defaults to 2000) | **9.87 N** | **72 s (1.00x)** | highest measured median; k 10x softer than the asset and c = 2000 (20x the asset's 100), i.e. neither end of the measured plateau family (k 5e4 / c 1000 … k 1e6 / c 20000); it also sits on the plateau at 480 Hz (`sub4_k100000` 10.04 N, one of the two sub4 cells that placed 2/2). |
| 2 | `=50000` (c = 1000) | 9.79 N | 72 s | the least damping that still lands on the plateau — the most conservative on the damping term, 20x softer on k. |
| 3 | `=300000` (c = 6000) | 9.75 N | 73 s | nearest the asset's k; more damping than either. |

The choice is **not knife-edge** (0.12 N apart, all inside the grab spread): the
family is `c/k = 0.02`, and §3 shows six k values across 20x landing on
9.75-9.87 N. §3's `k1000000` cell (asset stiffness, c = 20000) is a fourth
equivalent: **9.85 N**, the *minimal stiffness* deviation if a future owner
prefers not to touch k at all.

---

## 5. What did *not* move (no-harm reads, per cell)

* **Motion budgets: every descent inside budget in every cell.** Worst descent
  `|v|max` 0.110 m/s against 0.160-0.161 budgets at both rates; lurch 0.007-0.017
  against 0.29; every leg `ok` (4-5 carry + 2 descent legs per cell;
  `scripts/105_motion_regression.py`, one run per cell, stored in
  `logs/p41/motion_gates/*.txt`). Four of the eight cells exit 1, and in every
  case the only problem is the success floor (a 2-attempt run cannot meet 0.75).
* **No new failure reason.** The notes are empty in 14 of the 16 attempts; the
  two non-empty ones are `fruit did not follow the gripper` (sub4 k300000 /
  k50000, kiwi idx 2 — the documented no-grasp class) and nothing else.
* **Carry cone**: reported, not gated, on the dynamic line — 0.91-1.53x in the
  120 Hz cells (the shipped cell 1.03x; the excursions are the cnp legs
  themselves), and hand speed 0.333 m/s (0/4 legs over 0.45).
* **Span**: 30.1 s in every 120 Hz cell (identical to 0.1 s), 28.9-32.2 s at
  480 Hz (branch moves). The pinch costs **no simulated time**.
* **Wall**: 72-73 s at 120 Hz (the shipped cell 72 s) — the 2.2x force is
  **free**; 183-205 s at 480 Hz.

---

## 6. What the sweep does **not** measure (and what it therefore cannot claim)

1. **The class.** Two attempts per cell, and all four 120 Hz cells land on the
   *same* two attempts — left peach idx 3 and left peach idx 12, both
   carried-not-placed before and after. The 2.2x pinch did **not** convert them,
   and it did not even change the *escape*: idx 12's `place0` leg reports
   `in-hand |v|max` **1.95 / 1.96 / 1.98 / 1.92 m/s** and `trips=38` in the
   shipped / 3e5 / 1e5 / 5e4 cells, with the payload released at
   y = **-0.82 / -0.69 / -0.71 / -0.70 m** against a +0.5 m target — the same
   R11-A force-servo loaded slide, whose `F` still reaches **0.00 N** on a 9.8 N
   baseline. **This is one sample of a quantised outcome and no class
   measurement** — but it is the mechanism pointing the same way as R6-B (a
   drive-saturated pinch, not a force-starved one); the PREREG's C2 is the
   measurement, and its falsifier 2 (*force rises but the class does not move →
   a fidelity record, not an adoption*) is live.
2. **n = 2 grabs per cell.** Read the cell-to-cell differences only where they
   exceed the grab spread (~0.3 N); the three 120 Hz cells' 0.12 N order is not
   resolved.
3. **The joint2-drive question is closed by the cap read, not by a missing
   experiment.** `set_dof_gains` also programs the mimic joint2, but its
   `maxForce` stays **0.0 N** (every plateau cell's `[effort]` banner: `k=…/…
   c=…/… maxForce=10.0/0.0N`), so that drive cannot apply force at all — and
   `rho_asset` (asset gains authored on both joints) is **byte-identical** to
   shipped, which confirms it empirically. The only physical term the knob moves
   is **joint1's own k and c**; `rho_soft` (k = 3e5, c = 100) then excludes k,
   leaving **c**.
4. **The mechanism law.** c/k is the collapse variable *within* one physics rate;
   the substeps lever reaches the same plateau without reducing to it. The
   solver's implicit-drive formulation is the leading hypothesis, unproven.
5. **Long-horizon stability.** The damping term is clipped at the 10 N cap during
   free motion (`c·v` at close speed is hundreds of newtons), unmeasured for
   long runs, the two-line (two arms sharing one physics tick) and the policy
   loop.
6. **Provenance.** Every store and checkpoint on this tree is pre-P41 (asset
   drive). A profile flip changes the contact forces, so a post-flip store is
   identifiable only by new manifest fields (`write_manifest` `substeps`, `dt`,
   **both** joints' gains, the contact terms) — phase 2's item.

---

## 7. Reproduction

```bash
# the 8-cell grid, one claim
RUN_LIMIT=10000 scripts/154_claim_run.sh logs/p41/claim_sweep.log \
    bash logs/p41/sweep_cells.sh
# the post-hoc brackets (same scenario, same 120 Hz physics, separate claims)
RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p41/claim_bracket.log  bash logs/p41/bracket_cells.sh
RUN_LIMIT=900  scripts/154_claim_run.sh logs/p41/claim_bracket_k1e6.log \
    env HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_GRIP_EFFORT=1 ATTEMPTS=2 SEED=5 \
    FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=1000000 scripts/run.sh scripts/20_pick_place.py
RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p41/claim_bracket2.log bash logs/p41/bracket2_cells.sh
RUN_LIMIT=3600 scripts/154_claim_run.sh logs/p41/claim_bracket3.log bash logs/p41/bracket3_cells.sh
RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p41/claim_bracket4.log bash logs/p41/bracket4_cells.sh
# the tables (offline)
python3 logs/p41/sweep_table.py --detail > logs/p41/sweep_table.txt
python3 logs/p41/ratio_collapse.py       > logs/p41/ratio_collapse.txt
```

Evidence: `logs/p41/claim_sweep.log`, `logs/p41/claim_bracket*.log`,
`logs/p41/sweep/*.log` (8 cells + `wall.tsv`), `logs/p41/sweep_bracket/*.log`
(11 bracket cells + `wall2-4.tsv`; the k=1e6 pair cell is `logs/p41/claim_bracket_k1e6.log`), `logs/p41/sweep/wall.tsv`,
`logs/p41/sweep_table.{py,txt}`, `logs/p41/ratio_collapse.{py,txt}`,
`logs/p41/motion_gates/*.txt` (the per-cell `105` verdicts),
`logs/p41/sweep/00_tree_pins.txt`, and the five cell drivers
(`sweep_cells.sh`, `bracket_cells.sh`, `bracket{2,3,4}_cells.sh`).
