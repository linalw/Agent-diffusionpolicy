# P65 phase 1 pre-registration — where in the lift does the 25 deg come from?

Written **before** the instrument edit and before any run, 2026-10-29.
Branch state on entry: HEAD `1079b82`, `tasks.py` `7a8a163a`, `rl_env.py`
`7c137553`, `control.py` `9384ff4f` (untouched P41 profile), `configs/*`
untouched. **No shipped default change, no controller change, no `configs/`
edit, no commit.**

## 1. The question and the two suspects

P64's screen (§3 item 5, `logs/p64/SCREEN.md`): at the **station** the static
solve tracks its attitude command to **<= 1 deg** in both admissible directions
(`T0` 0.77/0.78, `QDRIFT` 0.78/0.93/0.91), while P63 measured **24.6 deg**
(median, n=11, 22.4-29.4) of `hold_drift` on the left's *failing* carry legs.
So the ~25 deg is **created in the lift**. Two named, code-level suspects:

* `control.py:423` `dq = np.clip(dq * self.gain, -self.max_step, self.max_step)`
  — the per-tick step bound (`FRUIT_IK_MAX_STEP`, default **0.5 rad = 28.65 deg**);
* `control.py:494` `command = np.clip(self._q_cmd + dq, self.arm_lo, self.arm_hi)`
  — the hard joint-limit clip.

Both act on the **commanded** joint vector, so both are readout-able without
touching the controller.

## 2. The instrument (reporting only, `FRUIT_CARRY_DIAG`, default off)

Five new fields on the existing `[carry]` row, immediately after `hold_drift=`:

| field | object | cost |
|---|---|---|
| `q_margin=<rad>@jN` | the **measured** joint-limit margin, `min(min(q-lo, hi-q))` over the 7 arm joints, **minimum over the leg**, N = 1-based binding joint | one `dof_positions()` per guarded tick (the same PhysX reader `ik_step` already calls; **no new pose read**) |
| `q_cmd_margin=<rad>@jN` | the same for the controller's **post-clip command** `arm._q_cmd` (`control.py:494`'s output) | free (numpy attribute) |
| `q_step_max=<rad>` | the largest per-tick `max abs(dq_cmd)` over the leg — the `max_step` suspect's operand (binds only above 0.5) | free |
| `jaw_z=<first>/<max abs>` | the **jaw-opening axis' world z** (`rot_now[:, 1]`, the axis P64's probe re-settled), first tick / max abs | free (`rot_now` already built for the slip frame) |
| `drift_on=<tick>` | first tick `hold_drift > 10 deg` (`None` if never) | free (the existing dot product) |

`None`/off = byte-inert: all of it sits inside `if guard_armed:` whose first
condition is `self._carry_guard_active or self._carry_diag`.

**One new sensor read per guarded tick, zero new pose reads.** The P39
one-read-per-leg rule is honoured on the pose side (jaw_z reuses `rot_now`); the
joint vector is the one addition, and it is the same `get_dof_positions()` call
`ik_step` makes every tick (`control.py:387`), not a novel reader.

## 3. The cell

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1
scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt --presentation direct
                         --episodes 15 --seeds <77|101|202>
```

One claim per run, `logs/p65/p2/C_<seed>.log`, 3 seeds x 15 picks, both arms.
The shipped `direct` profile is left alone (`FRUIT_POLICY_TRIGGER_ACQ` on,
`FRUIT_ARM_PARK=back`), exactly as P63's `logs/p63/p2/D_*.log` — which is the
same-tree **control for the class counts** (not for the new fields).

## 4. Endpoints

* **P1 (instrument).** Every `grasp_lift` row carries all five fields; state the
  `(no-hold)` / missing counts. Fail-closed: a single missing field on a
  `grasp_lift` leg = instrument not validated.
* **P2 (the test).** On the **left's failing (`cnp`) legs**: is the drift
  **coincident with a joint at/near its limit**? Two registered reads:
  (a) `q_margin <= 0.05 rad` at the leg's **end** (or as the leg's minimum), and
  (b) the **`drift_on` tick within +-20 ticks of the tick the margin's minimum
  was taken**.
  Report per leg the binding joint, the margin, the min's tick and the onset.
  **If the margin is healthy (>= 0.15 rad) on the failing legs, the
  `max_step`/clip suspects are REFUTED** (state it) — a clip the arm never
  reaches cannot remove 25 deg of commanded attitude. `q_cmd_margin` and
  `q_step_max` are the same statement on the command side and must agree.
* **P3 (the pads' line).** `|jaw_z|` max per arm: does the **left tip its pads**
  (the P64 `QPREC` class, `|jaw_z| = 0.29`) or do both arms sit flat
  (`|jaw_z| <= ~0.05`)? Compared left vs right as medians over the legs.
* **P4 (class counts, report only).** left/right placed / cnp / never-held;
  the right unchanged; no new failure reason. **No rate claim** (3 seeds of a
  rendered-frame loop, AGENTS §3b).

## 5. Pre-run predictions (scored in P2_RESULTS)

| id | prediction | basis |
|---|---|---|
| **Pa** | 0 `(no-hold)` on `grasp_lift`; 5/5 fields on every one | P63's 45/45 |
| **Pb** | left cnp legs read `q_margin >= 0.15 rad` → **both suspects refuted** | the stationary solve at the station leaves `+0.204..+0.377 @ j2` (P64) and the lift adds no reach demand; a j2-bound arm at 0.2 rad is not clipped |
| **Pc** | `q_step_max <= 0.10 rad/tick` (far under the 0.5 cap) | 25 deg over ~100-180 ticks is <= 0.3 deg/tick; the cap is 28.65 deg/tick |
| **Pd** | `drift_on` fires **early** (< 0.35 of the leg) and the margin's minimum sits **late** (the place-side reach) or nowhere near it | P64: the escape's loaded slide starts at row 60 vs the control's 104.5 on a ~160-tick lift, i.e. the drift is present before the payload moves |
| **Pe** | `|jaw_z|` max <= 0.06 on **both** arms → the pads are flat, and the P64 `QPREC` twist is not what the shipped line does | the command is T0 (P63) and the station achieves 0.020-0.030 at x=0.274-0.340 (P64's `C0` row) |
| **Pf** | the class split reproduces P63's shape (left cnp-majority, right placed-majority) but the counts may move | F3 |

## 6. Falsifiers

* **F1** a run wedges (no `[rl]` summary) -> retry that seed **once**; a second
  failure stops the cell and is reported.
* **F2** the fields are absent / unparseable on a `grasp_lift` row -> **stop**;
  the instrument is not validated and no endpoint may be read.
* **F3** the shipped stream moved vs P63's `D_*.log` (class counts) -> report as
  **instrumentation-or-branch**, quote no delta.

## 7. No-harm gate

`scripts/selfcheck.sh` PASS (including the new `235` leg) and `scripts/accept.sh`
with every knob unset reading **377/377** `[fruit]` lines identical to
`logs/p41/p2/accept_profile.log` + **`fingerprint: matches`**. The scripted line
must be byte-unchanged: the instrument lives inside a branch that requires
`FRUIT_CARRY_DIAG=1` **and** `_dynamic_capture_active`, and the scripted
acceptance sets neither.

## Amendment A1 (written after the runs, before the report)

**P2b is added as a descriptive read, with no decision rule.** The registered P2
asks whether the drift coincides with a joint at its limit; the runs answered it
*and* exposed a confound the registration did not anticipate: the margin is at the
limit on **every** leg (86/86), so "at a limit" is a standing condition and cannot
discriminate. P2b therefore reports the margin per arm x leg type (lift vs place)
and the `drift_on - t_min` ordering over **all** legs, so the reader can see the
degeneracy rather than take P2's literal `SUPPORTED` at face value. It changes no
threshold, no population and no decision: P2's rule stands as registered and is
reported **both** as literal (`SUPPORTED`) and as the causal reading the phase
carries (`refuted by discrimination`). No other endpoint, falsifier or gate is
touched.
