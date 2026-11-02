# P94 PREREG — the `_gripper_offset` jump: bound the reading, don't re-calibrate the carry

Pinned **before any run of this phase**. md5 in `logs/p94/PREREG.md5`.
Tree: `b9fa64b`, `tasks.py` `7ba4bb58`, `rl_env.py` `2849ad84`, the three motion
references `423896f7` / `423896f7` / `8952c320` (all untouched by this phase).

## 0. The defect, from the code (P93 §1b)

`_gripper_offset[side]` is written **once per grasp**, at the grasp routine's
entry, as `rot.T @ (spawner.position(sample) - arm.tcp_position())`
(`tasks.py:11047`) — the payload's position minus the tool point, in the tool
frame. It is a **tool offset only while the pads are on the payload**; when the
fruit is far out at the entry it is the payload's *distance*.

It is applied at exactly **one** unguarded site — `_carry`'s assisted branch,
`arm.tcp_target_for_jaw(centre - rot @ offset_tool)` (`tasks.py:5361-5366`, the
`else` of `if coherent:`). The other three consumers all guard it with
`hand_is_jaw`:

| site | code | guarded? |
| --- | --- | --- |
| `_carry` coherent branch | `arm.tcp_target_for_jaw(centre)` when `hand_is_jaw` (`:5326-5330`) | yes |
| `_carry` **assisted** branch | `centre - rot @ offset_tool` (`:5361-5366`) | **no** |
| `_carry` tail (30-tick settle) | `placed if hand_is_jaw else placed - rot @ offset_tool` (`:6087`) | yes |
| `_place_low` lowering ramp | `if hand_is_jaw: ik_step(jaw0 …) else: … if follow_arm: … offset_tool` (`:14258-14287`) | yes |
| `_release_lower` (v2 release ordering, off on the raised line) | `follow_arm` refuses when `|target0 - tcp| >= FRUIT_RELEASE_ARM_TRACK` (`:14052-14058`) | by a 0.20 m bound |

Two facts make the site live on the shipped line rather than a corner case:

1. **The shipped hand takes the assisted branch on every leg.** `coherent` in
   `_carry` is `self._coherent[side]` (`:4966`), and `self._coherent[arm_name]`
   is only set `True` when the pre-close fingertip-to-fruit error is
   `<= FRUIT_COHERENT_FALLBACK` (20 mm). On the OpenArm hand the fallback branch
   prints `openarm fingertips <N> mm from the fruit; closing anyway`
   (`:11292-11299`) and **does not set the flag**, so the flag keeps its
   previous value (initially `False`). Measured: `p92/C5` prints
   `fingertip-to-fruit = 59.4-61.8 mm` on 20/20 attempts and **1638/1638**
   `[diag] carry-assist` rows across the P9x corpus read `coherent=False`.
2. **The dead-code reset.** The `if not coherent: self._gripper_offset[...] =
   [0, 0, wrist_back]` block (`:11609-11622`) sits **inside `if coherent:`**
   (`:11054`), so it never executes; the raw payload-minus-TCP value is what the
   carry reads. (Reported, **not** repaired here: moving it would itself change
   every leg — see §7.)

Measured consequence (P93): one seed-6 right-arm leg with `|offset| = 1313 mm`
— 18.8x the hand's own tool scale `_pad_standoff = FRUIT_FINGER_LEN 0.060 +
PAD_LIFT 0.010 = 70 mm` — commanded the arm to a point **1313 mm** from the
measured pads and produced a **419 N / 1.545 m/s / 2361 mm-slip** flight. The
same-seed control carried the same code path at 116 mm.

## 1. The fix (one shape, one site)

On the jaw hand the offset may be applied only while it **is a plausible tool
offset**. Past the pad/arm-relation bound the branch falls back to the coherent
command, i.e. the same `hand_is_jaw` guard the reference sites use, conditioned
on the reading's own validity:

```
issued jaw target = centre - rot @ offset_tool     if  |offset_tool| <= BOUND
                    centre                          if  hand_is_jaw and |offset_tool| > BOUND
```

* `BOUND = FRUIT_CARRY_OFFSET_MAX`, **default `0` = off = the pre-P94 path bit
  for bit.** The phase measures `= 0.20`; the flip (if it ships) changes only
  the default.
* **The bound is not a new constant**: `0.20 m` is the tree's own pad/arm
  relation threshold, already in code at `_release_lower`
  (`FRUIT_RELEASE_ARM_TRACK`, `:14052-14058`), used there to decide that the
  pad/arm relation is broken and the arm must not be commanded at all.
* Scope: **jaw hand only** (`hand_is_jaw`). The kinematic-pad hand keeps the
  offset in every case — for it the number really is a tool offset.
* **Do not change** the coherent branch, the tail, `_place_low` or the release
  path. They are the reference behaviour.
* The diag row keeps its text; on a guarded leg `jaw_target` now equals
  `cmd_centre` (the applied jump is 0), so the census reads **both** the reading
  (`|offset|`, unchanged) and the **applied jump** (`|jaw_target - cmd_centre|`)
  from the records of either arm, with no new field.

**The invariant it restores.** *The carry never commands the arm to a point more
than `BOUND` away from the pads it is carrying.* Before the fix the applied jump
equals the reading, and the reading is unbounded (measured 11-117 mm on the
shipped legs, 350 mm and 1313 mm on the defective ones). After it, the applied
jump is `min(|offset|, BOUND)` and is exactly `0` on every guarded leg.

## 2. Why a bound and not the unconditional guard (the falsifier that decides it)

The unconditional `hand_is_jaw` guard would change **every** leg by its own
reading (11-117 mm), i.e. re-calibrate the carry on all 80 attempts. That is not
"the defect's removal and nothing else", and it cannot be attributed on a
20-attempt cell.

**F1 (the registered falsifier).** *A leg whose `|offset| <= BOUND` must be
unchanged*: its applied jump must still equal its reading to print precision, and
its row must be identical to the control's. If any non-guarded leg moves, the
registered form is **not the fix**: report NOT ADOPTED and do not ship.

**F2.** The **prefix identity**: a treatment cell's `[fruit]` stream must be
**line-for-line identical to its same-seed control** up to the first
`[diag] carry-assist` row whose `|offset| > BOUND` (the first leg the guard
acts on). The guard is inert before that line, so any earlier difference is
attributable to the tree, not the fix.

## 3. Cells, seeds and controls

`ATTEMPTS=20`, the shipped two-line default (P85), one claim per run, the P92/P93
instrumentation verbatim: `HEADLESS=1 FRUIT_MOTION_REPORT=1
FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1`.

| tag | seed | env | status |
| --- | --- | --- | --- |
| `T5` | 5 | `FRUIT_CARRY_OFFSET_MAX=0.20` | **new run** |
| `T6` | 6 | `FRUIT_CARRY_OFFSET_MAX=0.20` | **new run** |
| `T101` | 101 | `FRUIT_CARRY_OFFSET_MAX=0.20` | **new run** |
| `T202` | 202 | `FRUIT_CARRY_OFFSET_MAX=0.20` | **new run** |
| `N5` | 5 | unset | **new run** — the tree check; must replay `logs/p92/C5.log` |

Controls are the **same seeds' pre-fix records**: `logs/p92/C5.log`,
`logs/p92/C6.log` (seeds 5, 6) and `logs/p93/C101.log`, `logs/p93/C202.log`
(seeds 101, 202 — the two seeds P93 introduced as *fresh*, i.e. no earlier phase
had drawn them). **No control branch is reused within this phase** and no
treatment reuses another treatment's seed; the four seeds are the four distinct
branches the tree has, two of them fresh since P93 (P93 §2/§3's rule). After the
flip (if it ships) one further unset cell at seed 5 (`P5`) must replay `T5`.

Randomisation: the guard changes one command on one leg; it draws no RNG, so a
treatment cell is the control's own scenario up to that leg (F2).

## 4. Endpoints

**E1 — the commanded-jump census (primary).** Per leg, from the `[diag]
carry-assist` rows of every cell: the reading `|offset|` and the **applied jump**
`|jaw_target - cmd_centre|`. Report the distribution (n, min, p50, p90, max, and
the count above `BOUND`) per cell and per arm, before vs after, plus the per-leg
table (`logs/p94/leg_table.txt`). The invariant: **applied jump `<= BOUND` on
every leg of every cell** and **`applied == 0` on every guarded leg**.

**E2 — the class counts.** `cnp` (split by onset leg) and `never-held`, with
`logs/p92/census.py`'s classifier unchanged (`logs/p94/census.py` imports it),
plus `fell_off` / `diverted` / starved polls. Per seed and pooled.

**E3 — the placed count.** Per seed, treatment vs control, and pooled. Quote each
seed; do not pool before reading the per-seed column (P93: a pooled gain hid a
per-seed loss).

**E4 — the delivered side.** The inter-placement interval (pooled **and** per
arm), both denominators (placement window and batch span), and `placed/min wall`
from the per-line stamps. **Report, not a gain**: with one guarded leg per ~40
attempts the count cannot move systematically, and this phase claims no gain.

**E5 — the motion budgets.** `scripts/105_motion_regression.py <log>
--min-success-rate 0.0` on every cell (`logs/p94/gates.sh`); count of descents
over their per-leg budget. The fingerprint clause is recorded, never gated (every
20-attempt two-line reference predates P87's release clock; P91/P92/P93's
convention).

**E6 — the scripted line (shared path).** The carry code is **shared**, not
two-line-only: the scripted single arm runs the same assisted branch (measured:
`logs/p83/D5.log` prints 114 `carry-assist` rows, all `coherent=False`, readings
11-44 mm). So the read is the acceptance's stream identity:
`scripts/accept.sh` (two-line, the shipped cell) is compared against
`logs/p93/accept_noharm.log`, and `FRUIT_BIARM=0 scripts/accept.sh` (single arm)
against `logs/p71/accept_rails_none.log` (346/346) with `fingerprint: matches
configs/motion_reference_single.json`.

The **pre-run census** of the scripted corpora (48 logs with the row, 950
readings, all `coherent=False`) reads p50 **26 mm**, p99 **81 mm**, max **351 mm**,
with **2 readings above 0.20 m** (`p83/F5` 351 mm, `p44/amend_F_S2` 343 mm) and
two more above 0.12 m (`r11/B_PX_patch_diag` 155 mm, `p44/amend_E_S1` 132 mm) —
so the scripted acceptance is **expected** to be inert (a 10-attempt cell draws
~9 carry legs, ~1 % of scripted readings are above the bound) but it is **not
guaranteed**. The rule is therefore the prefix form, not bit-identity: the
acceptance's stream must be identical **or** differ first at a carry leg whose
reading exceeds `BOUND`, shown by a `FRUIT_CARRY_DIAG=1` repeat at the same seed
(the diag is run-neutral on the two-line: `logs/p84/D5.log` replays
`logs/p80/T20.log` 865/865 with the diag rows dropped).

**E7 — no new failure reason** (note keys inside the control set).

## 5. Decision rule (ship / do not ship)

Ship **iff all** of:

* **(a)** E1's invariant holds on **every leg of every cell** — no applied jump
  above `BOUND`, `0` on every guarded leg — **and** F1 holds (no non-guarded leg
  moves).
* **(b)** **no seed's placed count falls below its control's** (E3). A pooled
  gain is not required and will not be claimed.
* **(c)** no class rises beyond the pre-fix spread (E2: `cnp` and `never-held`
  each `<= the control's + the four-cell control spread`), and no new reason
  (E7).
* **(d)** the budgets do not regress (E5): no treatment cell has more
  over-budget descents than its own control **plus one**, and no over-budget leg
  is a guarded leg.
* **(e)** the acceptance **and** the single arm are unchanged (E6): byte-identical
  to their records, or differing only at/after a carry leg whose reading exceeds
  `BOUND` (E6's prefix rule) with no placement lost (the acceptance's own floors
  still apply: 0.60 two-line, 0.75 single arm, and neither record is above its
  floor's headroom — 7/10 and 6/9 — so "no placement lost" is read as
  `successes >= the record's`).
* **(f)** F2's prefix identity holds for every treatment cell.

**A correctness fix needs no gain to ship, but it may not lose one either.**
Because the guard acts on ~1-2 legs per 80, the phase's own power statement is
stated up front: **it cannot measure a rate gain, and it does not claim one.** What
it certifies is that a 1.3 m / 419 N commanded jump can no longer be issued from a
non-tool reading, and that nothing else moved.

If the flip ships: default `FRUIT_CARRY_OFFSET_MAX = 0.20` (`=0` restores the
pre-P94 path), one unset cell at seed 5 replays `T5`, and a selfcheck leg pins
the resolver table, the single site, the jaw-hand scope and the arithmetic.

## 6. Re-baseline / provenance

The fix is **carry-path only** and default-**off** in the measured tree. If it
ships: every direct/policy number and every carry-touching store recorded before
P94 is a **pre-P94 carry-command** number, restored by
`FRUIT_CARRY_OFFSET_MAX=0`; no motion reference is re-recorded (the scripted
stream is proven identical), and the manifest's `physics` block gains the bound
only if the flip ships (P41/P72/P87's rule: provenance before any recollection).

## 7. Named, registered, NOT run here

1. **The unconditional guard** (Form A): `hand_is_jaw` → `centre` on every leg.
   It is the structurally consistent form (it is what the tail at `:6087` already
   commands), and it is refused here only because it re-calibrates 80/80 legs
   and this phase must isolate the defect. If F1 fails it is the named
   replacement, with its own registration.
2. **The dead-code reset** (`:11609-11622`, inside `if coherent:`): moving it out
   would set the assisted offset to `[0, 0, wrist_back]` on the jaw hand, i.e.
   Form A by another route. Reported, not repaired.
3. `_release_lower`'s own 0.20 m `follow_arm` refusal is the bound's precedent and
   is left exactly as it is.
