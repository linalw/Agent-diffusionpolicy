# P40 PREREG — the grip load phase, the drive-effort readout, and the arrival-wait discriminator

Registered 2026-10-26, **before any edit or run**, on the P39-final tree `1790b87`
(`scene.py` `988985ef`, `tasks.py` `112d2cb1`, `rl_env.py` `238e90a4`,
`configs/motion_reference.json` `25ade92b`, `configs/motion_reference_twoline.json`
`d0326030`; working tree clean). Evidence: `logs/p40/GRIP_CENSUS.md`,
`logs/p40/RATE_CENSUS.md`, `logs/p40/LIT_REVIEW.md`.

## 0. What the diagnosis changed about the plan

The owner's two asks were "raise friction or grip force to stop the drops" and
"speed the rate up / close the action loop". The census **falsifies the first
framing and narrows the second**:

* **Friction is already screened** (`FRUIT_FINGER_FRICTION_COMBINE=max` +
  `FRUIT_FINGER_MU=8.0` read 6/10 against a 7/10 control; "friction breaks A4").
  Do not re-run it.
* **The force does not discriminate the class**: 12 619 pooled attempts give a
  placed median of **4.43 N** and a carried-not-placed median of **4.36 N**
  (identical p75 4.51), and 85 % of the load-taking escapes are **single-sided**
  at onset. More squeeze at the same contact is not the lever.
* **But the delivered force may be mis-measured.** The close freezes **6.8 mm
  short of its own clamp** and the pads stall at 4.5 N while the drive
  (k = 1e6 N/m, 6.4-26.4 mm of position error, **maxForce 10 N**) should be
  saturated at 10 N - a **2.2x discrepancy** with no second sensor in the build.
  If the tactile `value` is a 0.44x scaling, every friction margin doubles and the
  whole "raise N" family is already at the actuator's limit.
* **Rate**: place+release (34 %) is swept and geometry-closed, the arrival wait
  (14-17 %) is belt-bound (P1c), and the policy cadence is 30 Hz of sim time by
  construction. The only rate lever that is both large and unattacked is
  **retention** (37-39 % of arm time places nothing; a failing attempt's `grip`
  segment is 5.1-5.4 s against 1.7-2.0 s healthy), plus two unexplained residuals:
  the two-line's `release` (2.39 s vs the single arm's 0.68 s) and the un-tabulated
  **selection-commit vs arrival** tick pair.

So this pre-registration spends on **two measurements and one lever**, not on a
friction/grip-force sweep.

## 1. The items

| # | item | form | scope |
|---|------|------|-------|
| **G0** | **drive-effort readout** (measurement, default off) | `FRUIT_GRIP_EFFORT=1` prints, at the close freeze and at each carry leg's start/end, the finger dofs' **applied effort** beside the tactile `N` (one read per event) | scripted + direct, reporting only |
| **G1** | **post-freeze load phase** (the lever) | after the close freeze (the fruit is already between the pads and the catch window is over) close **slowly and boundedly** until the force reaches a target or the clamp is reached, then hold: `FRUIT_GRIP_LOAD_AFTER_FREEZE` (0 = off), `_RATE` (face speed, default 0.04 m/s - the C1 rate), `_TARGET_N` (default 8.0 N), `_MAX_DEPTH` (default 4.0 mm), `_SETTLE_TICKS` (default 12) | scripted + direct; **never** touches the pre-close window |
| **R1** | **arrival-wait discriminator** (offline) | tabulate, per attempt, the **selection-commit tick** against the **fruit-arrival tick** (both already printed on both lines) across the existing batteries; classify supply-bound vs arm-bound | offline, no run |
| **R2** | **the two-line release residual** (offline + one run if needed) | explain the 2.39 s two-line `release` against the single arm's 0.68 s; localise it in the code before any lever | offline first |

**Not run** (already measured, with the record): friction combine/`mu` (6/10 vs
7/10), the relief cap (force unchanged), the compliant pad body (D2's A2
falsifier not met), the scoop/groove/grip plane (R8-A), the tip delta (P39), the
place geometry (P3), the supply-density and single-arm arrival levers (P1c), the
control-rate increase (30 Hz by construction).

## 2. The branch, decided before the run

**G0 runs first, alone (one claimed acceptance run).** Its reading decides G1:

* **Branch A - the tactile is the real normal force** (|effort| ≈ 4-5 N, i.e.
  well under the 10 N cap, and the drive is *position*-limited rather than
  force-limited): G1 is live; run the lever.
* **Branch B - the tactile is a scaled or partial reading** (|effort| ≈ 8-10 N at
  the cap while `N` reads 4.4 N): **G1 is withdrawn** (the force family is already
  at the actuator's limit) and the lane reports the metric correction instead; the
  class work then falls back to the *geometry/closed-loop* residue the census
  names (single-sided contact at onset) with no new spend in this phase.
* **Branch C - the effort read fails** (the accessor is unavailable and the
  `drive_target - position` fallback cannot be formed): G1 runs anyway, but its
  primary endpoint becomes the *span* only, and the force claim is marked
  unmeasured.

This branch is the reason the prereg exists: it prevents spending a battery on a
force lever that the effort read would have closed.

## 3. Endpoints

### 3.1 Primary (mechanism, G1) - measured on the acceptance + pear batteries, 10 attempts each, same-tree control C

| # | endpoint | pass |
|---|----------|------|
| M1 | close-freeze force (median) | **>= 7.5 N** from the C arm's 4.2-4.5 N |
| M2 | achieved-vs-commanded span at the freeze (the `[acq]` bias) | **<= 3.0 mm** from 6.8 mm |
| M3 | the added load's cost | attempt span **<= C + 0.3 s** (median) |
| M4 | no new failure reason, and no gated motion budget worse than C | both |

### 3.2 Secondary (class, staged - only if M1-M4 pass)

The **direct interface**, the WS-4.2 protocol of record: **N = 5 runs x 15
episodes per arm**, interleaved C vs L8, seeds 77/101/202/303/404, one claim.
Primary class endpoint = the **paired carried-not-placed** conversion (the
6-0 edge at N=5 is p <= 0.05); report the pooled placed count and the cycle as
secondary. The scripted class census (pear + acceptance) is reported but is
**not** the decision - P39 showed its left sample is 2-6 attempts.

## 4. Falsifiers (each stops the item, not the phase)

| # | falsifier | reading |
|---|-----------|---------|
| **F-1** | M1 fails with an honest effort read (Branch A) | the close cannot deliver force at this contact; the force family closes |
| **F-2** | M3 fails (> +0.3 s with no force gain) | the load phase costs cycle time for nothing |
| **F-3** | the load phase moves the *pre-close* window (any `[fruit]` line before the freeze differs from C) | the scope is wrong; stop (it is supposed to act after the freeze only) |
| **F-4** | a new failure reason, or a worse motion budget | not eligible |
| **F-5** | the effort read shows the drive at the cap **and** `N` at 4.4 N (Branch B) | this is a *finding*, not a failure: record the metric correction and withdraw G1 |

## 5. N, claims, and the cost

* **G0**: one claim, the acceptance scenario, `ATTEMPTS=10`, `SEED=5`, effort print
  on, C arm only (~4 min wall).
* **G1 mechanism**: one claim per battery, arms **C -> L8 -> L12** (`_TARGET_N`
  8.0 and 12.0) on the acceptance and the pear battery (~35-45 min wall).
* **G1 class** (only if M1-M4 pass): the direct A/B, ~3 h wall (`112_rl_ab.sh`).
* **R1/R2**: offline, no simulator.

## 6. What is deliberately not claimed

* No cross-attractor success-rate comparison; a moved fingerprint is expected for
  a lever that changes the contact and is recorded, not adjudicated.
* The scripted class census cannot certify the lever at its n; only the direct
  N=5 protocol can, and only if the mechanism passes.
* A null here does **not** close the hardware form: the real hand's clamp force is
  not this sim's drive.

---

## Amendment A1 (2026-10-26, Oracle gate 1, **before any edit or run**)

Gate 1 verdict: AMEND - **G1 is already in the record**, so the phase shrinks to
one measurement, one metric correction and one rate read.

**A1.1 - G1 (the post-freeze load phase) is WITHDRAWN.** `logs/p11b/B_EJECTION_PROBE.md`
§4/§6.3 already measures the same saturated stop at **4.5 N with
`FRUIT_SUBSTEPS=1` and 10.0-10.3 N with `FRUIT_SUBSTEPS=4`** - the drive is at its
10 N/joint cap and the pads stop at the fruit's surface with 20 mm of extra
command bit-identical ("the force-capped drive makes the extra depth inert",
§0/§5 row 1). A post-freeze push acts on the frozen `cmd` (`tasks.py:9515-9517`,
which bypasses the `live_extent` clamp) and is therefore *new timing*, but its
actuator is the same saturated drive: it is the §2.5 null with the task loop
attached. `_TARGET_N=12` is also above the per-joint cap, so the L8/L12 cells were
never distinguishable. The 3 h direct A/B is cancelled with it.

**A1.2 - friction is closed a second time, and not by a marginal read.**
`logs/p9/FRICTION_AUDIT.md` §1/§5: the carry load sits at **0.10-0.78 of the
available friction on 29/31 escape legs** and the required normal force is
1.8-3.4 N against 4.4 N delivered. The escape is therefore **not a friction
slide**; the `p3face` screens (`max` 6/10, `mu 8` 6/10 vs a 7/10 control) agree.
No friction cell is left to run.

**A1.3 - G0 is kept, narrowed, and re-purposed as a metric correction.** One
claimed acceptance run with the default-off `FRUIT_GRIP_EFFORT=1`, printing per
finger (a) the tactile `value`, (b) each finger joint's **applied effort** and
(c) `target - position`, as a **5-tick median** (the pool's contact `Fmax`
reaches 612 N, so one sample is a spike) at the freeze and at each carry leg.
Control: **no new C run** - the shipped acceptance is already archived
(`logs/p32/D1_accept_pear.log`: 376/376 `[fruit]` lines, 6/10,
`fingerprint: matches` `25ade92b`). The run also repeats the substeps comparison
(shipped vs `FRUIT_SUBSTEPS=4`) to re-base every force number the project quotes.
Known accessor caveat: `openarm_left_finger_joint2` is a **drive-less mimic**
(`PhysxMimicJointAPI:rotY`, USD ~3838) - its effort is a constraint reaction, not
a drive force; `joint1` is the only actuator (k = 1e6, maxForce 10, USD
3803-3812), so the force claim rests on `joint1` + the substeps pair.

**A1.4 - R2 (the two-line release residual) is DROPPED - instrument mismatch.**
The two-line's `[cycle] release` 2.39 s compares against the single arm's own
`[cycle] release` **2.31 s** (`logs/g/20_rate_single_1.log`); the 0.68 s figure is
the `place low` *leg row*, not the cycle segment. The residual is ~0.08 s.

**A1.5 - the class arm, if it is ever run, is LEFT-LANE ONLY.** The loss is left
(33/33 cnp, `logs/p33/51_phase2_read.md` §1.2); a pooled two-arm endpoint dilutes
it ~2x, and the left base (~16/18 not-ok) is the better-powered cell at the same
cost. Also verify the fire path first: the freeze is gated on `dynamic_capture`
(`tasks.py:9562`), so a hook inside that branch is inert on the default direct
loop (the P38/RESEED failure mode: 137 scans, 0 candidates).

**A1.6 - the added item (the Oracle's "measurement the plan does not force"):
the regrasp yield.** Parse `dynamic regrasp: re-seated on the moving fruit`
against each attempt's outcome over the existing logs; the question is whether
`FRUIT_REGRASPS` (default 3, `tasks.py:10343`) ever rescues an attempt. If no
rescue is attributable, bounding it is **free rate**: a failing attempt's `grip`
segment is 5.14-5.44 s against 1.72-2.02 s healthy, i.e. the largest
controllable block on the failed cycle, with no success-rate claim attached.

**A1.7 - wording fixes.** (i) "single-sided at onset" is the **loss tick**, not a
seating state (the same logs read >= 2 contacts in the median for both held and
escape legs) - the plan may not say the seating is single-sided. (ii) The lever
arm **never** re-records a motion reference, and `scripts/189_w7a_chain.sh` must
not run (it rewrites `configs/motion_reference_twoline.json`). (iii) The effort
print's neutrality is argued from the archived 376/376 stream, not from "one read
per event". (iv) M3's +0.3 s is a **per-leg** cost across a moved branch.

**Batch of record after A1: G0 = 2 claimed runs (shipped substeps, substeps 4)
with the effort print; the regrasp-yield parse offline; the class arm withheld;
no lever shipped.**

