# P66 phase 4 results — the place leg's rail-crossing clearance (gate (a) of phase 3)

Written by the phase-4 lane. Two runs, one seed, the phase-3 scenario verbatim
(`logs/p66/p4/run_p4.sh`, logs `logs/p66/p4/{control,L2}_77.log`; the numbers are
`logs/p66/p4_report.txt`, `python3 logs/p66/p4_report.py --check` -> PASS).

## Verdict

**MARGINAL, at the bottom of the band, on the arm the lever exists for — gate (a)
FAILS its +33 mm floor and the lever is not certified.** On the 0.20 m rung the
left's one held place leg enters the output rail's footprint **level with the rail
top (window minimum `+0 mm`, tick 333)** and crosses the rail's centreline at
**`+5 mm` (tick 340)**; the shipped 0.36 m rung's own left leg reads
**`+30 / +29 mm`** on the same scenario. **No held leg goes negative in either
arm (0 of 16)**, so there is **no contact and no re-shape is forced** — but the
0.20 m rung spends **25 mm of the 30 mm the shipped rung had**, i.e. it consumes
the rail's entire remaining margin.

**The rung ladder cannot buy this back.** The place leg is a straight line from
the lift end to the transfer pose, and the crossing sits at 82.5 % of that leg's
`y` span, so `dz_crossing = 0.175 x dz_lift` — the 0.24 rung (40 mm higher) buys
**+7 mm**, not +40. Only the **transfer** height is 1:1 with the crossing (the
record's arithmetic), and the transfer height is not what this lever changes.

---

## 1. The instrument: the reduction, not new data

`logs/p66/P3_RESULTS.md` gate (a) named the defect precisely: `clr=` printed the
leg's **minimum** clearance to the highest surface under the payload, which
includes the phase where the payload is still over the *input* belt, so it read
`@rail -18/-24`, `@belt -3/-7`, `@obelt -182` on escaped payloads and could not
answer "does the lowered lift clip the output rail **at the crossing**".

**The change (`src/fruit_sorting/tasks.py`, `1296bd44`), print-only:**

| field | reduction | carries |
|---|---|---|
| `clr=` | the **sample** at the **first** tick whose `\|payload y\|` reaches the rail's **centreline** | surface + tick (`+5mm@rail/t340`) |
| `clr_win=` | the **minimum** over the ticks inside the rail's **25 mm footprint** (the transfer segment) | surface + tick (`+0mm@rail/t333`) |
| `clr_min=` | the **leg minimum** — P3's field, unchanged, same spelling | surface (`+29mm@rail`) |

* **Where the crossing comes from**: `_output_rail_y()` derives *(inner face,
  centreline)* from the scene config — `output_belt_y - (output_belt_size[1]/2 +
  0.0125)`, the expression `conveyor.OutputBelt.build` authors the rail with —
  giving **0.400 / 0.4125 m** on the shipped geometry, i.e. exactly the
  `y = 0.4125` crossing of the record (`logs/p30a/RAILS_DESIGN.md`). A selfcheck
  leg asserts the two numbers and that they are derived, not hardcoded.
* **No new read**: the crossing detection needs the payload's `y`, and the loop
  **already** takes it every tick (`fruit = spawner.position(sample)`, the slip
  bookkeeping) together with `clearance, where = self._payload_clearance(...)`.
  The reduction is two float comparisons on those two existing values —
  `abs(float(fruit[1])) >= rail_centre` (latched at the first tick) and
  `>= rail_inner` (min). Nothing else is read: no `tcp_pose()`, no
  `pad_centre()`, no second `spawner.position()`.
* **Print-only, twice over**: the trackers sit **inside `if guard_armed:`** (the
  same flag that prints the row), so with `FRUIT_CARRY_DIAG` unset the loop runs
  no extra work at all, and the thresholds are `+inf` off a place leg, so a
  `grasp_lift` leg takes neither branch and prints `n/a`. `_clearance_field` is a
  pure formatter.
* **The invariant is asserted on every row**: `clr_min <= clr_win <= clr` (the leg
  contains the window contains the crossing sample). It is also the reason the
  window field exists: on a *climbing* leg the binding point is the footprint's
  **inner edge**, not the centreline (`+0` at `t333` vs `+5` at `t340`).
* `scripts/236_p66_lift_selftest.py` (`e3d3bc31`) pins all three fields in the
  row, the two constants, the "no read" set, the gating, the latch, the window
  reduction, and the formatter's spellings (incl. `n/a` and the exact
  pre-phase-4 leg-min spelling).

## 2. The cell, and why the control is explicit

Seed 77, 15 picks, `FRUIT_CARRY_DIAG=1`, the phase-3 scenario env verbatim
(`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_ATTITUDE=1`), the shipped direct
profile, `moe_v13s` `61da390a`.

**`FRUIT_LIFT_DZ` is explicit in both arms** (`+0.08` = the shipped 0.36 m,
`-0.08` = the 0.20 m rung). The brief's "unset control" is no longer the control:
the phase-3 package made the `direct` presentation's **default** the 0.20 m rung
(`rl_env.LIFT_DZ_DIRECT_DEFAULT`), so unset *is* the treatment — the same
units/labels slip phase 3 recorded as `DEVIATION.md` D4/D5. Both arms print
`(explicit)` and their own heights from their own rows:

| arm | `dz` | lift end (row) | episodes | placed | cnp | never-held | lift / place legs |
|---|---|---|---|---|---|---|---|
| control | `+0.08 (explicit)` | **1.530 m** | 15 | 7 | 6 | 2 | 13 / 13 |
| L2 | `-0.08 (explicit)` | **1.370 m** | 15 | 10 | 3 | 2 | 15 / 13 |

The counts are **branch draws, not a comparison**: the direct loop conditions on
rendered frames and is not reproducible (AGENTS §2/§3b), and the *same* phase-3
cell at the same seed read 11/15 (control) and 12/15 (C20). Only the clearance
geometry is the object here.

## 3. The read

Every place leg, the two reductions and the leg minimum (`logs/p66/p4_report.txt`
§1 has the full table). **`held`** = `clean_slip_max <= 50 mm` (P61's escape
convention) **and** the payload was still in the hand at the crossing tick
(`loss_row is None or loss_row >= crossing tick`); an escaped payload reads the
belt, not the hand.

### The gate population (held legs)

| arm | side | held n | **crossing** | **window min** | leg min | verdict |
|---|---|---|---|---|---|---|
| control (0.36) | left | 1 | **+30** | **+29** | +29 | MARGINAL |
| control (0.36) | right | 6 | +50 [+35..+60] | +50 [+35..+60] | +50 | CLEAR |
| **L2 (0.20)** | **left** | **1** | **+5** | **+0** | **+0** | **MARGINAL (bottom)** |
| L2 (0.20) | right | 8 | +50 [+33..+79] | +50 [+32..+74] | +50 | -1 mm vs the floor |

* **Negative held legs: 0 / 16** across both arms. Nothing clips.
* **The pair that decides it** — same species (pear), both placed, both clean
  grips, no contact loss:
  * control `left place0` ep13: `clr=+30mm@rail/t290 clr_win=+29mm@rail/t284`,
    `clean_slip 0.9 mm`, `force_min 9.79 N`, `loss_row None`;
  * L2 `left place0` ep0: `clr=+5mm@rail/t340 clr_win=+0mm@rail/t333`,
    `clean_slip 0.1 mm`, `force_min 9.97 N`, `loss_row None`.
  The difference, **-25 mm**, is within 3 mm of the geometry's `-28 mm` (§4); the
  residual is the two legs' achieved-`z` and payload-hang difference, which this
  instrument does not separate. The absence of a jolt in the L2 leg
  (`in-hand_vmax 0.066`, steady 9.97 N) says the 0 mm is a *geometric* graze, not
  a contact.
* **The right arm is the same configuration in both arms** (`resolve_lift_dz`
  emits only `{'left': dz}`; `lift_dz_for` returns `None` for the right), so its
  two columns are the reading's own **branch noise**: worst **+35** (control) vs
  **+32** (L2), on 14 held legs spanning +32..+79. That is the scale against
  which the left's -25 mm is read.
* **The 0.20 m rung's window on the left opens at the rail's inner edge**, not at
  the centreline: the leg is *climbing* (the transfer is 160 mm above the lift
  end), so the footprint's first tick is the tightest one. The +33 mm floor of
  record comes from **place-leg minima** on the scripted line (`logs/p30a`: no
  place leg in four arms closer than +33 mm), and those legs are flat, so their
  minimum *is* the rail band; on a climbing leg the inner edge is tighter by the
  climb over the 12.5 mm of `y` between the two ticks (~4 mm here).
* **Corroboration on phase 3's own logs** (same tree minus this print change, same
  scenario, other branch): the C20 seed-77 arm's five left place legs read leg
  minima of **+3 / +3 / +4 / +5 / +8 mm @rail** — each a lower bound on that
  leg's crossing, all in this phase's band, none negative.

### What is *not* evidence (excluded, with the reason)

* control left: 5 legs `escaped(slip)` reading `-217/-218 mm@rail` — a payload
  already lying on the **main belt** under the output line
  (`1.170 - 1.385 = -215`), plus 1 `no-crossing` (`-10 mm@belt`, lost at tick 61);
* L2 left: 1 `escaped(slip)` (`+2 / -22`, `clean_slip 126 mm`, `loss_row 293`
  < crossing 363 — a body that left the grip before the rail and then
  intersected the rail box by 22 mm), 3 `no-crossing` (two escapes at ticks
  109/146 and one carry that ended **178.8 mm short** of its target, `dz_end
  -68.7`, so the payload never reached the rail).

**Read `[carry]` rows by leg and by class.** A negative `@rail`/`@belt` row is an
escaped payload, never a clip.

## 4. Why the rung cannot buy the margin back (derived)

The place target is `(0.43, +-0.50, 1.530)` (transfer `1.45 + 0.08`) and the leg
is a straight line from the lift end. With the crossing at `y = 0.4125`:

```
z_crossing = transfer - 0.175 * (transfer - lift_end)
control  1.530 -> 1.530   (+0 mm)
L2       1.370 -> 1.502   (-28 mm)
```

So **raising the lift end by 160 mm buys 28 mm at the crossing** (17.5 % of it),
while **lowering the transfer by 1 mm costs 1.00 mm** — the record's 1:1
arithmetic is the *transfer's*, not the lift end's. Consequence for phase 3's
open question "does 0.24 match 0.20 at half the cost": at the crossing, 0.24 is
**+7 mm** over 0.20 — the rung ladder cannot restore +33 mm at any rung.

## 5. What this means for the flip

1. **Gate (a) FAILS as registered** (+0 mm vs the +33 mm floor of record) — the
   lever is **not certified**, and this is the second of phase 3's three gates to
   land non-passing (the first was the right-arm invariance at N=4).
2. **It is not a contact**: 0/16 held legs negative, no jolt, no force signature.
   So the honest reading is **"the lowering spends the rail's margin"**, not "the
   lowering drags the rail". Context, and it is thin: the control's *one* held
   left place leg reads +29..+30 on this scenario, i.e. below the scripted
   acceptance's +31..+55 over 42 legs — the direct scenario's left carry is a
   worse-gripped population (`logs/p42/SIM_LIMIT.md`), so its nominal clearance
   starts lower.
3. **If the margin is wanted back, the lever must be re-shaped — and the shape is
   a transit waypoint, not a higher rung:**

   * **(i) lift, then transfer** — make the place leg's first segment a vertical
     raise to the shipped transfer height at the lift's own `y`, then the lateral
     move. That restores the full +29..+30 mm by construction (the crossing is
     then at 1.53). Cost: one extra vertical segment of ~0.16 m at the place
     profile (~0.6-0.9 s/attempt, i.e. the P44 S1 cell's scale, against the
     lever's 3.35 s place block). **Open and unmeasured**: whether a raise *after*
     the lift reinstates the 25 deg drift. P64/P66 located the drift's creation
     **in the lift** and the mediator is `drift_end` at the lift's end, so a
     post-lift raise *should* be outside the mechanism — that is a hypothesis,
     and it needs its own pre-registration and its own `drift_end` read.
   * **(ii) keep the low lift and lower/remove the inner rail**
     (`FRUIT_OUTPUT_RAILS=outer`, P30-A): +35 mm of clearance by construction,
     against P30-A's measured trade — the rail is a **catch ledge** (releases
     landing on its 25 mm top face are placed **96.6 %** of the time, inboard of
     it **47.6 %**, n=786). That is a place-path change, not a margin change, and
     needs its own registration too.
   * **(iii) do not try a rung**: §4 — 0.24 buys +7 mm at the crossing.

## 6. Caveats

* **n = 1 held left place leg per arm.** That is the arm's own state on this
  scenario (most left place legs escape at the lift, `logs/p42/SIM_LIMIT.md`), not
  a sampling choice. The reading is a **geometric** quantity set by the
  trajectory and the payload's hang — one *clean* leg (`clean_slip 0.1 mm`)
  measures it — but it is one branch and one seed; phase 3's leg minima
  (+3..+8 @rail) are the independent corroboration, and they sit in the same band.
* The print rounds to 1 mm, so `+0 mm` is `-0.5..+0.5 mm`. The leg's own pair
  (`+0` at the inner edge, `+5` at the centreline, 12.5 mm of `y` apart, with a
  derived climb of 4 mm there) is internally consistent to 1 mm.
* **The replay check is not available**: the direct loop is not bit-reproducible
  (rendered frames), so this phase's control is *not* `[fruit]`-identical to
  phase 3's — it reads 477 vs 502 `[fruit]` lines on a different branch. The
  print-only claim rests on construction (§1) plus the scripted identity in §7.
* One blemish in the record: `run_p4.sh`'s header echo used backticks inside
  double quotes, so the header's `# crossing:` / `# floor:` lines printed empty
  parentheses (bash ran the words). The script was fixed after the batch
  (`e43817fe`); the two logs carry the defect in their headers only — nothing in
  the data or the read depends on those lines.

## 7. No-harm

* `scripts/selfcheck.sh` **PASS, 0 failures** (the P66 leg included, extended).
* `scripts/accept.sh`: **6/10 + `fingerprint: matches configs/motion_reference.json`**
  — the tree's recorded pear-on branch; the FAIL is the rate floor only, as it
  has been since P32 phase B. Its **377/377 `[fruit]` lines are byte-identical**
  to `logs/p66/p2/accept_noharm.log` (and to `logs/p65/accept_noharm_final.log`),
  i.e. the scripted line is untouched — which is what "print-only" means here,
  since `FRUIT_CARRY_DIAG` is never set on that path.
* No `configs/` edit, no default moved, no commit. `TASKS_MD5` is the
  metadata-only follow `40e196e8 -> 1296bd44` (the P43/P62/P64/P65 precedent).

## 8. Pins

`tasks.py` **`1296bd448ecf59df1dd885b9ddd807fe`** (the `clr` reduction +
`_clearance_field` + `_output_rail_y`), `rl_env.py` **`cedaa3b4`** (`TASKS_MD5`
follow only), `scripts/236_p66_lift_selftest.py` **`e3d3bc31`**,
`logs/p66/p4_report.py` **`43aea82b`**, `logs/p66/p4/run_p4.sh` **`e43817fe`**
(post-fix; the batch ran the same script before its two header-echo lines
were de-backticked, which is why the two logs' headers print empty parentheses
there), `configs/motion_reference.json` **`8a399626`** and
`configs/motion_reference_twoline.json` **`2246f83c`** both untouched, checkpoint
`moe_v13s` **`61da390a`**, HEAD **`6010276`**.

Evidence: `logs/p66/p4/{control,L2}_77.log`, `logs/p66/p4/{header,batch}.txt|out`,
`logs/p66/p4_report.{py,txt}`, `logs/selfcheck.log`, `logs/accept.log`,
`logs/p66/p4/smoke.log` (a 1-pick fixture check of the field before the claims).
