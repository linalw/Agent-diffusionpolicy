# P68 results — the P67 climb pair **plus** the place-leg wrist hold

Written by the P68 lane. One cell, 2 arms, 2 seeds on the **population cell**
(all-A supply, so every attempt is the left's place leg), plus the no-harm
acceptance and one mixed-supply run for the right arm. Logs
`logs/p68/pop2/{A_77,A_101,B_101}.log` + `logs/p67/B2_77.log` (re-used, the
control's seed 77), numbers `logs/p68/p68_report.txt` +
`logs/p68/mechanism.txt` (`python3 logs/p68/p68_report.py --check` -> PASS).

## Verdict

**No. The wrist hold does not keep the payload — it loses *every* left place leg
(0 of 16 held, 0/8 placed in both seeds, against the pair's 8 of 16 held) — and
the crossing half is not robust either: on the climb form the left's held legs
read +16 .. +54 mm across three branches, with 3 of 9 below the +33 mm floor.**

* **The hold is installed and it is not achieved.** `tasks.py` `_carry` sets
  `arm.hold_quaternion` from the leg's **start** TCP attitude for
  `round(S / CONTROL_DT)` = **120 ticks** (released at `i >= 120`, so 120 of the
  climb's 121 ticks — the unheld tick is the climb's last, which
  `jerk_limited` ends at rest; a 1-tick off-by-one, not the mechanism). It is a
  **full 6-DoF IK constraint** (`ik_step` adds the rotation row to the
  Jacobian), not a soft priority. On the left it is commanded but **not
  tracked**: `hold_drift` **23.8 [20.3 .. 31.4] deg** on 16/16 legs, first
  > 10 deg at tick **78 [67 .. 87]** of the 121-tick climb.
* **The mechanism is the step budget, and it is left-specific.** With the hold
  the IK's per-tick command step sits **exactly at the `FRUIT_CARRY_STEP` cap
  (0.0300 rad/tick) on 16/16 legs**; without it, 0.0136 [0.0088 .. 0.0300] with
  2/16 at the cap. Every leg of **both** arms is at a joint limit
  (`q_margin -0.000`; the *commanded* margin's binding joint is j3 10/16,
  j2 3/16, j7 3/16), i.e. the arm is in the saturated workspace P65/P66 already
  measured — so asking for the attitude
  spends the whole budget fighting the position command and the pads **sweep
  around the payload**: the W8-B loaded slide at 16/16 instead of 8/16, with
  onset spread over rows 3-150 (the control's climb losses cluster at the
  climb's exit, 113-152) — the sweep is there from the leg's first ticks.
* **The same knob on the same run's right arm works.** `mixed_A_77`: the right's
  place legs carry `hold_drift` **0.8 deg** (0.4-0.6 at the hold window's end),
  place **3/3** at `clean_slip` 0.0-0.3 mm and crossing **+43 [+43..+50]** —
  against the no-hold control's right **13/13**, +43 [+34..+105]. So the failure
  is the **left's** inability to hold that attitude, not the knob's arithmetic,
  and the right is **not** harmed by it.
* **The crossing does not clear the floor per leg.** On the climb form the left's
  held legs (the population control at both seeds + the mixed run) read
  **+51, +37, +33, +54, +36, +32, +19, +49, +16 mm** (median +36): **6/9 at or
  above +33, worst +16**. P67's "+33 .. +54, worst +33" was seed 77's five legs;
  the per-leg value is **payload-hang dependent** (P66 §3 said the same from the
  other side), so the +31.5 mm the formula promises is not a per-leg guarantee.
* **Cost of the hold: 0 ticks.** Place legs 512 [478 .. 547] (A) vs
  514 [444 .. 542] (B) in the population cell — the hold is a constraint, not a
  segment. The climb keeps its P67 cost (+136 ticks = +1.13 s).

So the exact 3-knob form is **not** shippable, and neither of the two failures is
the one P67 predicted: the hold does not fail to *hold* (it holds far better on
the right) — it fails on the left because that arm cannot hold the attitude at
this station, and the crossing is not robust to the payload's own hang.

---

## 1. What the knob is, verified at the code (not from the brief)

| layer | site | what it does |
|---|---|---|
| install | `tasks.py` `_carry`, place-leg preamble | `hand_is_jaw and _dynamic_capture_active and name.startswith("place")` and `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S > 0` -> `place_hold_ticks = max(1, round(S / CONTROL_DT))` and `arm.hold_quaternion = tcp_pose()[1].copy()` |
| bind | `control.py` `ik_step` | with `hold_quaternion` set, `error6 = [pos_err, rot_err]` and a **6-row** Jacobian — the wrist is pinned, position and rotation trade in one damped solve |
| release | `tasks.py` carry loop, top of tick | `if place_hold_active and i >= place_hold_ticks: arm.hold_quaternion = None` |
| scope | — | **not side-scoped**: any `place*` leg of the direct presentation on either arm (the mixed run shows the right runs it too) |
| report | `[carry]` row | `hold_drift=<max>deg` + `(no-hold)` when no live hold was seen, `drift_end=` the value at the last tick with a live hold, `drift_on=` the first tick > 10 deg |

**Coverage arithmetic**: `S = 1.0` -> `round(1.0 / (1/120)) = 120` ticks against
a **121**-tick climb, and the release happens *before* tick `i = 120`'s IK call,
so the climb's last sample runs unheld. `jerk_limited` ends that sample at rest,
so this is a 1-tick edge, not the failure: the drift is already 23.8 deg by then.

## 2. The cell (registered; one deviation recorded)

**Population cell** = `logs/p67/run_p67_pop.sh`'s scenario verbatim
(`FRUIT_SUPPLY_GRADES=A:0.96,B:0.02,C:0.02` -> 16/0/0, so **every attempt is the
left**), 8 picks/run, the same instruments (`FRUIT_CARRY_DIAG=1`,
`FRUIT_CARRY_ATTITUDE=1`), checkpoint `moe_v13s` `61da390a`:

| arm | env | runs |
|---|---|---|
| **A** | `FRUIT_LIFT_DZ=-0.08 FRUIT_LIFT_CLIMB=0.18 FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S=1.0` | seeds 77, 101 |
| **B** | `FRUIT_LIFT_DZ=-0.08 FRUIT_LIFT_CLIMB=0.18` | seed 101 new, **seed 77 = `logs/p67/B2_77.log`** |

**Deviation (recorded)**: two extra runs beyond the brief's four — one
single-pick fixture of arm A (`logs/p68/smoke_A.log`, run before the batch to
check the knob was picked up) and one **mixed-supply** arm-A run
(`logs/p68/mixed_A_77.log`, the P67 *registered* cell's scenario: 15 picks,
A:0.375/B:0.375/C:0.25, seed 77) because the population cell's all-A supply has
**no right-arm attempt at all**, so the brief's "the right's invariance" item is
structurally unanswerable there and `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S` is not
side-scoped. Both extra runs are reported separately and never pooled with the
population cell's counts.

## 3. The read

### The population cell, per left place leg

| arm | seed | placed | legs | held (slip<=50) | `hold_drift` max | first >10 deg | onset rows |
|---|---|---|---|---|---|---|---|
| **A** | 77 | **0/8** | 8 | **0** | 26.0 [22.4..26.8] | 75 [71..84] | 4, 67, 70, 93, 99, 101, 136, 150 |
| **A** | 101 | **0/8** | 8 | **0** | 26.0 [20.3..31.4] | 79 [67..87] | 4, 4, 7, 28, 58, 68, 70, 95 |
| B | 77 (P67) | 5/8 | 8 | 5 | no-hold | - | 113, 142, 152 |
| B | 101 | 3/8 | 8 | 3 | no-hold | - | 4, 4, 58, 63, 102 |

* **A loses all 16**: `clean_slip` **881-1224 mm** (median 1069), every one the
  loaded slide (`force@onset` 6.3-26.0 N, median 10.6 = the pinch cap, two
  spikes 22.8/26.0; `force_min 0.00 N`, `loss_row` 4-245, in-hand `vmax`
  1.5-2.4 m/s) — 15/16 with tactile contact at the onset, one never seated.
  **0/16 held** against **8/16** (Fisher two-sided
  **p = 0.0024**, with the clustering caveat: 2 runs x 8 legs per arm, and the
  run-level read is 0/8 vs 5/8 and 3/8).
* **The crossing has no held leg on A**: every A row reads `clr -215..-219 mm@rail`
  (an escaped payload lying on the main belt, P66's excluded class) or
  `no-crossing`. The treatment population cannot answer gate (a) at all.
* **The 1-pick fixture (arm A, run before the batch) has the same signature**: its
  pear lost at slip 1206.7 mm, `hold_drift` 26.0 deg, first > 10 deg at tick 75 —
  i.e. the batch result is not a batch-state artefact.
* **The lift's mediator is untouched** (the hold is place-scoped): left
  `grasp_lift drift_end` **1.3 [0.6..5.2]** (A/77), **0.7 [0.6..6.2]** (A/101),
  **1.1 [0.6..1.2]** (B/77), **0.7 [0.6..5.5]** (B/101) — the same band, and the
  ≤ 2 deg requirement holds on the medians with the control's own 5-6 deg
  outliers. `drift_end` is `n/a` on the control's place legs and a real number on
  A's, which is the instrument confirming the hold is live.
* **Class**: every A failure is `cnp` (grasped, not placed) — the closed
  `SIM_LIMIT.md` loaded-slide class, at 16/16 instead of 8/16.

### The crossing on the climb form (all held left legs, 3 branches)

| branch | held legs | crossing `clr` | window `clr_win` |
|---|---|---|---|
| B, population seed 77 | 5 | +51, +37, +33, +54, +36 | +50, +37, +33, +53, +35 |
| B, population seed 101 | 3 | **+32**, **+19**, +49 | +32, +19, +48 |
| A + hold, mixed supply | 1 (orange) | **+16** | +16 |
| **pooled** | **9** | **median +36, range +16 .. +54, 3/9 < +33** | same |

The floor of record is +33 mm. The *commanded* crossing is +31.5 mm by the
formula (the climb row prints `z_crossing 1.5335 m` on every run); what varies is
the payload's own hang, which P66 §3 also named as the residual on its legs.
**So "the pair clears the crossing" is true on 6 of 9 held legs, not on all** —
the two newest misses are a kiwi at +19 (population seed 101) and an orange at
+16 (mixed), both cleanly held (`clean_slip` 0.1 / 26.3 mm).

### The right arm (mixed supply, the only cell that exercises it)

| arm | right legs | held | placed | crossing | `hold_drift` |
|---|---|---|---|---|---|
| A + hold (`mixed_A_77`) | 3 | 3 | **3/3** | **+43 [+43..+50]** | **0.8 deg** (0.4-0.6 at the window's end) |
| B, no hold (P67 `B_77`) | 13 | 13 | **13/13** | +43 [+34..+105] | no-hold |

**The right is not harmed and the hold is achieved there** — that pair is what
localises the failure to the left's ability to hold the attitude, and it is also
the answer to the brief's invariance item: no right-leg cost is measurable
(n=3 on the treatment branch, because the left's 11 losses changed the arm mix
from 13 right attempts to 3; the read is a per-leg class/geometry statement, not
a rate).

### The ticks

| cell | left place-leg ticks | net |
|---|---|---|
| population A (hold) | 512 [478..547] | **+0** vs B's 514 [444..542] |
| population B | 514 [444..542] | (P67's climb cost: +136 = +1.13 s over the no-climb rung) |
| mixed A / right | 514 [460..548] / 400 [378..421] | branch spread, same order |

The hold adds **no** ticks — it is a constraint on the IK, not a segment.

## 4. What each failing half needs

1. **The hold (keeping the payload)** — it cannot be fixed by a rung of this
   knob: the left is at a joint limit on 16/16 legs and the 6-DoF command
   saturates the step budget, so *any* pinned attitude spends the budget the
   position command needs. The free-wrist hypothesis P67 named is therefore
   **still untested on the left** — this cell tested "pin it" and measured the
   pin to be unachievable, and harmful (0/16 vs 8/16). What it needs is a lever
   that keeps the **left** out of the saturated workspace during the place leg:
   the station/attitude family P62 measured as **azimuth-limited** (no yaw
   removes the belt projection without removing the station), or the transfer
   height (below). Do **not** spend another hold rung (time, magnitude, or a
   side split).
2. **The crossing (the +33 floor)** — a per-leg miss at +16/+19/+32 says the
   +31.5 mm the formula buys is not enough headroom against the payload's hang.
   The 1:1 lever is the **transfer height** (P66 §5(i)/(ii)): a transfer raise or
   a re-shaped transit *after* the lift, which is re-descended by `_place_low`
   before the jaws open, so it may not move the release; the other is
   `FRUIT_OUTPUT_RAILS=outer` (+35 mm by construction, against P30-A's catch-ledge
   trade). **A larger climb is not the answer** (0.175 mm/mm, and it spends the
   carry — P67 §6).

**Combination note for the adoption package**: the *pair alone* (no hold) is the
best-measured form on this tree — 8/16 held, 6/9 crossing legs at or above the
floor, `drift_end` ~1 deg — and its cost is the 8/16 load-loss class plus the
+1.13 s. The hold is a **regression** on top of it, so if the pair is ever
proposed, `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S` must be **explicitly 0** in the
package's environment (it is default-off today, so nothing leaks — but the
before/after labels must not mix).

## 5. No-harm

* `scripts/selfcheck.sh`: **PASS, 0 failures, 1 skipped** (`logs/p68/selfcheck.log`).
* `scripts/accept.sh` (`SKIP_SELFCHECK=1`, every P68 knob unset):
  **6/10 + `fingerprint: matches configs/motion_reference.json`** — the tree's
  recorded pear-on branch; the FAIL is the rate floor only. Its **377/377
  `[fruit]` lines are byte-identical** to `logs/p66/p2/accept_noharm.log` and to
  `logs/p65/accept_noharm_final.log` (md5 `8345af7f...` on the filtered stream).
  Gate output `logs/p68/accept_noharm_gate.txt`, log `logs/p68/accept_noharm.log`.
* **No `src/`, `scripts/` or `configs/` edit** (`git status --porcelain -- src
  configs scripts` empty), no shipped default moved, no commit, **no reference
  re-recorded** (`8a399626` / `2246f83c` untouched).
* The hold knob is **default off** and unset in the acceptance above; the climb
  and dz knobs are likewise opt-in. The hybrid canary has no path to any of them
  (`60_eval_policy.py` never constructs `SortingRLEnv`).

## 6. Pins

`tasks.py` **`e5168578633bf094e86042d5ec54ce0f`** (unchanged this phase),
`rl_env.py` **`d88c3729749bc471bbd769c393701228`**, checkpoint `moe_v13s`
**`61da390a`**, `configs/motion_reference.json` **`8a399626`** and
`configs/motion_reference_twoline.json` **`2246f83c`** untouched, HEAD
**`d6e91c8`** at the batch (`logs/p68/pop2_header.txt` carries the same md5s from
the run's own shell). Evidence files:
`logs/p68/run_p68_pop2.sh` `81e3255f`, `logs/p68/run_p68_extra.sh` `70260990`,
`logs/p68/p68_report.py` `df528ec9`, `logs/p68/mechanism.py` `477892ca`.

Evidence: `logs/p68/{pop2/, smoke_A.log, smoke_rollouts/, mixed_A_77.log,
rollouts_mixed/, pop2_header.txt, pop2_batch.out, extra_batch.out,
p68_report.{py,txt}, mechanism.{py,txt}, accept_noharm.log,
accept_noharm_gate.txt, selfcheck.log}`, and the control
`logs/p67/B2_77.log` + `logs/p67/B_77.log`.


## Addendum (the lane's extra cell): the mixed supply confirms the negative

*Appended by the orchestrator from the lane's post-report cell and corrected here
to the cell's own denominators (the print "1/26" does not correspond to any count
this tree's logs carry; the shipped "0/25" is P66 phase-3's N=5 rung control, a
different cell).*

`logs/p68/mixed_A_77.log` — the general scenario (A:0.375/B:0.375/C:0.25), the
same pair + the hold, 15 picks, seed 77: **the left places 1 of 12 attempts
(8 %)**, and its single held place leg reads `clr +16 mm` — **below the +33 mm
floor**. The same run's **right** places 3/3 at `clr +43 [+43..+50]` with the hold
achieved to 0.8 deg (P67's no-hold right: 13/13, +43 [+34..+105]). So the negative
is **not** an artefact of the all-grade-A population cell: on the general supply
the pair + the hold still loses the left's payload on 11 of 12 legs, the hold is
achieved only on the right, and the one left leg that survives does not clear the
crossing floor.
