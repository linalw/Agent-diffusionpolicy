# P51 phase 2 — pre-registration: the combination battery (`C / U / O / OU`)

**Status: REGISTERED, NOT EXECUTED.** Phase 1 (`logs/p51/COMBO_MAP.md`) measured the
falsifier **F1** before any simulator time: the speed/mass cells' acquisition rows are
**not** the release-offset tail (1 tail of 5 cell-attributable events; the other 4 are
mid/upper-band and **converged**, i.e. the closed grip class). Under §4's own rule the
battery is therefore **not to be spent**; this file is kept as the registration and its
pre-run prediction, the practice of P47/P48/P49. If the owner overrides, everything below is
ready to run unchanged.

Written 2026-10-27, **before any run**. Tree: HEAD **`f61a00b`**, `tasks.py` `b6de439c`,
`fruits.py` `e81051c1`, `rl_env.py` `93e35ef7`, `configs/motion_reference.json` `8a399626`,
`..._twoline.json` `2246f83c`, tables `release_offsets_accept_s5.json` `aa11e8c3` /
`..._pear_s5.json` `451dcef3`. No `src/` edit is needed: **all four arms are env-only**
(`FRUIT_SPEED_ALL` and `FRUIT_RELEASE_OFFSET`/`_TABLE` are shipped knobs, both default off).

## 1. The question and the hypothesis

**H1.** The P44/P46 speed cells' cost is the **pre-contact acquisition class**, and P48
showed that class is the **delivered-x tail** (`|x| >= 0.390` -> 6/6 failed). If the cells'
rows are the tail, then the P50 per-instance release-offset compensation **plus** the speed
union (`O + U`) is **class-clean** at the speed gain, and the `+7-11 %` becomes adoptable.

**H0.** The cells' rows are not the tail (mid-band and/or a second mechanism), and `O`
changes nothing about them.

**Measured in phase 1, against H1:** 1 of 5 cell events is the tail; 4 of 5 are non-tail and
all four are converged closes (residual 5.5-6.0 mm). **F1 fired.**

## 2. The arms (exact env) and the scenarios

| arm | env | what it is |
| --- | --- | --- |
| **C** | *(unset)* | the shipped tree — the control of record |
| **U** | `FRUIT_SPEED_ALL=1` | the P44 union: place `v_max` 0.35 -> 0.52, lift 0.30 -> 0.36 (+a 1.0 -> 1.9), release dwell 20 -> 0 with the pad/finger settle 3 -> 2 |
| **O** | `FRUIT_RELEASE_OFFSET=1 FRUIT_RELEASE_OFFSET_TABLE=configs/release_offsets_<pool>.json` | the P50 compensation (`x_spawn = planned_x - offset(instance)`), table **per pool** |
| **OU** | both of the above | the combination under test |

Scenarios (each arm on each):

1. **acceptance seed 5** — `HEADLESS=1 ATTEMPTS=10 SEED=5`, the shipped scattered supply.
   Table: `release_offsets_accept_s5.json` (coverage **16/16**).
2. **acceptance seed 6** — same with `SEED=6`. **Its pool is a different instance set
   (12 instance names: apple 6.9, lychee 3.6/3.7, orange 6.3/6.6, peach 6.6, pear 6.8/6.9,
   strawberry 3.1/3.4, tomato 6.1/6.6) and no table covers it** — only 3 of its 12 names
   coincide with seed-5 entries (`orange6.6`, `pear6.8`, `tomato6.6`), which P50's per-pool
   rule does not license. O at seed 6 with the seed-5 table would print `src=miss` on 9-12 of
   its 12 instances and `instances=3/12` at best — a null, not a measurement. **Precondition
   for this cell: a seed-6 table (phase 2a below).** If the owner declines 2a, seed 6 runs
   **C and U only** and its O/OU cells are recorded as *not evaluable* (never as a bias-free
   null).
3. **pear seed 5** — `FRUIT_SUPPLY_SPECIES=pear` (the P44 battery C shape). Table:
   `release_offsets_pear_s5.json`, which is **identity** (every offset 0.00 mm), so O must be
   **bit-identical** here: that is E6, an inertness control, not a lever test.

Order: **C -> U -> O -> OU inside each scenario**, one `scripts/154_claim_run.sh` claim per
run, strictly sequential (one simulator). The interleave is *inside* each scenario so the
compared pair shares the session.

**Instrumentation (identical on every arm, inside the contrast — AGENTS §3b):**
`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1` (row-neutral on these scenarios, P43/P44) plus
`FRUIT_RELEASE_OFFSET_DIAG=1`, whose `[offset] release ... planned= spawn= off_mm= src=`
rows are **print-only and neutral by construction** (P50 M2-C replays the reference's
physics stream 377/377 with it on). `FRUIT_CARRY_DIAG=1`/`FRUIT_PLACE_TRACE=1` are added only
to the acceptance cells if E2's row classes need the never-held signature — and then on **all
four arms**, with the run-neutrality check repeated against the recorded no-diag logs (P46
§2's pattern).

## 3. The endpoints

**E1 — the tail (powered).** The count of **delivered x outside [0.180, 0.390]**. The
powered form is the **P50 M1/M1b isolated-cell census**, not the acceptance count: 16 instances
x 3 x-columns x 2 passes = **96 cells per arm** (untreated 8/96, P50; compensated 0/96). The
battery's own release census (the `[offset]` rows: ~58-62 releases/arm/run at the acceptance,
~68 at the pear) is reported as a **secondary, underpowered** read (P50's power statement:
~1 event of exposure per arm). Decision quantity: **cells outside the band, per arm**, with
the O-vs-C and OU-vs-U contrasts.

**E2 — the acquisition rows (OU vs U).** The count of `nograsp` attempts and of the log's own
`fruit did not follow the gripper` rows, per arm, each classified by P48's split
(**residual > 6 mm = distance class; <= 6 mm = converged close**) and by the delivered x
(tail / mid). Endpoint: **no new row of the distance class in OU that U does not draw**, and
the converged-class count **not** increased.

**E3 — the placed.** Placed count per arm (10 attempts), **OU vs U and vs C**. Report-only as
a rate (AGENTS §2: one deterministic branch, and the pool recycles), but the *direction* is a
gate: OU must not be below U (§4's F3).

**E4 — `s/attempt`.** The `[stats]` span / attempts, per arm: OU must keep U's gain (the
union's own measured -1.45 s/attempt P44, -0.76 s pooled P46) within **0.20 s** — i.e. the
compensation must cost ≈ nothing (it is one dict lookup and one subtraction per spawn).

**E5 — no new reason.** The failure-reason sets (`scripts/141`-style digit-normalised notes)
of OU minus U minus C must be empty.

**E6 — the pear inert.** The pear's two arms (C, O) and (U, OU) must be **bit-identical on the
physics `[fruit]` stream** (P50 M3's 378/378 pattern), and O's release rows must read
`off_mm=+0.00 src=table` on 100 % of releases (identity table) — the knob's own proof that it
did nothing.

## 4. The falsifiers (registered before the run)

| # | fires when | consequence |
| --- | --- | --- |
| **F1** | the cells' acquisition rows are **not** the tail — fewer than half of the cell-attributable events at `x >= 0.390`, or any non-tail row present | **the hypothesis fails; do not spend the battery.** *Measured in phase 1: 1 tail of 5, four non-tail — FIRED.* |
| **F2** | OU is not class-clean: any new distance-class row, or a converged-class count above U's | no adoption of OU; the combination is closed |
| **F3** | OU's placed **< U's** (by any count; the design has ~0.10 s.d. per 10-attempt arm, so this is a stop, not a rate) | no adoption |
| **F4** | a new failure reason appears in OU (E5 non-empty) | no adoption |
| **F5** | a budget fails: any descent outside its profile's speed/lurch budget on a moved arm, or a release that does not land (`FRUIT_PLACE_TRACE` off-belt), or the pear's E6 identity breaks | no adoption; the arm is repaired or dropped |

Decision rule: adopt `O + U` **only if** E1's O arm clears the band on the powered cell
count, **and** E2/E3/E4/E5 pass, **and** E6 is byte-identical, **and** no falsifier fires.
Anything less is published as the negative with the mechanism named.

## 5. The N and the cost

| block | runs | wall (measured analogues) |
| --- | --- | --- |
| **2a** the seed-6 table (precondition for the seed-6 O/OU cells) | 3 claimed probe runs | ~15 min (the P50 phase-1 `offset_probe/live/wake` shape) |
| **2b** the battery: 4 arms x 3 scenarios | **12** claimed runs | ~4.3 min/run at the acceptance (P50: 7 runs / 30 min) -> **~55-70 min** |
| powered E1 cells (M1/M1b) | 2 probe modes (C and OU) | ~10-15 min |
| offline re-derivation | 0 | `logs/p51/combo_map.py`-style reader, minutes |

One Oracle gate (gate 2). No `configs/` reference is written: a speed arm moves every
fingerprint by construction (P44 §9.3) and the compensation moves the release x, so the
moved arms are gated on the **budgets** and on the pear's byte-identity, never on a
reference file. Nothing ships unless the decision rule passes, and then it needs both
references re-recorded plus the collector's manifest field.

## 6. What this phase would not claim

* No **rate**: every placed count is one draw of one attractor (AGENTS §2); the two-line's
  `s/attempt` is a batch span over two concurrent arms; the acceptance's 10 attempts cannot
  resolve a 1.5-3 % release tail (P50 §7's own power statement).
* No mechanism for **E4's displacement** (the 480.6 mm / 379 mm cross-belt event, P48 §2.2's
  two unseparated candidates) — it is shared with the control and out of the compensation's
  scope.
* Nothing about the **two-line pools' offsets**: no table exists for them, and P50's
  per-pool rule needs its own probe (the s5 pool's 8 names *are* the seed-5 instance set, so
  that table would be cheap to measure — but it is still owed a probe, and it would only
  touch the two rows the two-line **control** already draws). The two-line's acquisition rows
  are excluded from E2's decision quantity unless a two-line table is measured first.
* Nothing about the **direct/policy** interface: it reads the *delivered* x, so it would
  inherit a working compensation for free, but its A/B is its own pre-registration (and since
  P43 it carries the park default, which re-baselines every pre-P43 direct number).

## 7. The phase-1 pre-run prediction (what the battery would have read)

Recorded so the registration is falsifiable even though it is not executed:

| endpoint | predicted | basis |
| --- | --- | --- |
| E1 (powered cells) | O **0/96**, OU **0/96**, C 8/96, U 8/96 — a **tie between U and OU**, so no discrimination of the combination | P50 M1: the compensation is exact for its pool; the speed cells do not move the release x (P38: transport contributes 0.000 mm) |
| E2 (rows, OU vs U) | **one convertible event at most** (the kiwi `+44.8 mm` instance, if the branch draws it), everything else unchanged | phase 1: 1 of 5 cell events is the distance class, and it is that instance |
| E3 (placed) | OU ≈ U within one attempt, both a branch draw against C | P44/P46: the count is branch-bound and the compensation does not touch the grip |
| E4 (`s/attempt`) | OU = U to ~0.01 s | one lookup + one subtraction per spawn (P50 M2: 15.0 -> 15.1 s with the knob on) |
| E5 (reasons) | unchanged | no new site is touched |
| E6 (pear) | **bit-identical**, 0.00 mm shift on 100 % of releases | P50 M3: 378/378 identical |

So even on its best case the battery's headline would have been "the compensation is inert on
the speed cells' cost, and the speed gain is unchanged" — which is why phase 1 stops here
rather than spending ~70 minutes of claim wall to publish a predicted null.
