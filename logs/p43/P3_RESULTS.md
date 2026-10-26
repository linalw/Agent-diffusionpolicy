# P43 phase 3 — the arm park re-measured on the P41 grip-profile tree

Measured 2026-10-26 (batch 20:48:52 → 22:02:35, **4423 s = 73.7 min of app wall**,
one claim, **no wedge, no retry**). **No commit. No `src/`, `configs/` or
`datasets/` change.** Tree pinned at HEAD **`53e5ccf`**,
`tasks.py` **`a1b3d673`**, `rl_env.py` **`6324b60b`**,
`control.py` **`9384ff4f`** (the P41 `finger_damp02` profile), `scene.py`
`27e3d64a`; `configs/motion_reference.json` **`8a399626`**,
`..._twoline.json` **`2246f83c`**, `configs/arm_parks.json` **`42ab4fb7`**,
`configs/waypoints.json` `d81c6f1c`; checkpoint
**`checkpoints/moe_v13s/policy_best.pt` `61da390a` on BOTH arms**.

**Verdicts, one line each.**

* **The park's win reproduces on this tree, at the same absolute level as the
  pre-P41 read and from a better baseline.** Right-arm placed
  **32/54 = 0.593 → 53/56 = 0.946**
  (delta **+0.354**, exact non-inferiority p = 8.0e-07, Newcombe one-sided
  95 % lower bound **+0.228**), the right-arm carried class **20/54 = 0.370 →
  0/56 = 0.000**, run level **5/5** (sign p = 0.031), no new failure reason,
  cycle **+0.2 %**. The park arm lands where P35's did (**94.6 % placed vs
  94.0 %**, **0 carried** both times); the *delta* is smaller (+0.354 vs
  +0.489 placed) only because the un-parked control improved (§2), i.e. this is
  the ceiling, not a weakened lever. The registered P0 branch rule fires
  **branch B** (A's un-parked right carried rate is **0.370 < 0.40**), so the
  carried contrast is a **report**, not the gate — and it is overwhelmingly
  directional anyway (**p = 7.3e-08**). **Recommendation: ADOPT as the direct
  env's default**; the flip itself is **Phase 4's** (one scoped line, §7).
* **P0b — the first direct baseline after the P41 grip profile.** The shipped
  un-parked direct env on this tree: **right 32/54 = 59.3 % placed, 20 carried
  (37.0 %)**, **left 1/21 = 4.8 % placed, 20 carried**, **pooled 33/75 = 44.0 %**.
  Against P35's (pre-P41, 4.4 N) `moe_v13s` control — right 23/51 = 45.1 %,
  carried 25 (49.0 %) — the *un-parked* right arm moved **+14.2 pts placed /
  −12.0 pts carried** across the two corpora. **That is a cross-batch
  comparison, not a controlled one** (different tree, different grip profile);
  it is the correct reading of "the baseline moved", nothing more.
* **The check passes exactly, both arms.** B: M1-held **56/56**, M1-applied
  **56/56** on both reads (`q_settled` and `q`), M2a **56/56**, band census
  **0/1364 fully hidden**. A (the control): M1-held 54/54, the shipped-pose
  negative 54/54, M2a **0/54** and **903/1340 = 67.4 %** fully hidden — i.e.
  the pre-treatment state, reproduced.
* **The mechanism is the same one P35/P36 named, on the same class.** The
  right arm's carry legs read `clean_slip_max > 50 mm` on **15/53 (A) → 2/55
  (B)** and `force_min = 0` (payload out) on **16/53 → 2/55**; the retained-leg
  pinch is **9.31 N (A) / 9.74 N (B)**, the P41 profile, against the pre-P41
  direct corpus's **3.57 N** median. The left arm — which has **no park
  vector** — is unchanged (**16/21 → 15/19** lost legs, `clean_slip` median
  268.5 → 253.8 mm): the built-in no-op control.

---

## 1. The design as run (PREREG_DRAFT L3.1, unchanged)

| axis | value |
| --- | --- |
| **arms** | **A = the shipped direct env (no park)**; **B = `FRUIT_ARM_PARK=back`** |
| **checkpoint** | `moe_v13s` **`61da390a`** on **both** arms (`moe_v12`+park remains **untested**, and untestable on the canary: `60_eval_policy.py` never constructs `SortingRLEnv`, PARK_STATUS §1.4/§3) |
| **scenario** | the P35/P36/P37 block verbatim: `FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_DYNAMIC_PICK=1`, camera 240×424 |
| **diagnostics** | `FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_PARK_DIAG=1 FRUIT_RESET_ALIGN_DIAG=1` on **both** arms (the instrument sits inside the contrast) |
| **shape** | **N = 5 runs × 15 episodes per arm**, seeds **77/101/202/303/404**, policy seed **11**, interleaved **A then B** per seed pair, **one claim** (`154_claim_run.sh`, `RUN_LIMIT=25200`) |
| **realised n** | right **54 / 56**, left **21 / 19** (the arm follows the fruit's grade, and the streams diverge with the outcomes: right-arm mix 0.720 → 0.747) |
| **wall** | per run **407-439 s** (mean 421.7 s = 7.0 min); batch **4423 s = 73.7 min** — the pre-registered "measured 1.2-1.4 h" holds, and the 2-3 h envelope was not needed |

The plumbing was checked **before** the batch with two 2-episode runs
(`logs/p43/p3/smoke_{A,B}.log`, not part of the measurement): A 0/2, B 2/2 on
the same two fruits, B's rows reading `park=back m1_hold_ok=1 m1_cmd=+0.088
m2_arm=0.000 arm_px=0`.

## 2. P0 / P0b — the baseline, and what it decides

| arm | right | left | pooled | median cycle |
| --- | --- | --- | --- | --- |
| **A** (shipped) | **32/54 = 59.3 %** placed, **20 carried (37.0 %)**, 2 no-grasp | 1/21 = 4.8 %, **20 carried**, 0 no-grasp | **33/75 = 44.0 %** | 1826 ticks |
| **B** (`back`) | **53/56 = 94.6 %** placed, **0 carried**, 3 no-grasp | 0/19 = 0 %, **18 carried**, 1 no-grasp | **53/75 = 70.7 %** | 1830 ticks |

**P0**: A's right-arm carried rate **20/54 = 0.370 < 0.40** → **branch B**: at
this n a halving from 0.40 is the last resolvable point, so the class contrast
is demoted to a **report** by the pre-registration, and the **placed /
run-level read carries the decision**. The pre-registered branch-B label's
stock sentence ("no class-level evidence at this n") **does not describe this
batch** — the contrast is resolvable and significant (§4); what is true is that
the *gate* did not admit it as a test, because the control's rate landed
0.030 below the threshold. Both facts are recorded rather than reconciled.

**P0b** (published regardless of the outcome, as registered): the numbers in the
table's A row are the first post-P41 direct baseline. The pre-P41 comparators,
for orientation only:

| corpus | checkpoint | arms | right placed | right carried | pooled |
| --- | --- | --- | --- | --- | --- |
| P35 `C_ab` (4.4 N) | `moe_v13s` | A un-parked | 23/51 = 45.1 % | 25/51 = 49.0 % | 24/75 = 32.0 % |
| P36 cell 1 (4.4 N) | `moe_v13s` | control | 7/27 = 25.9 % | 18/27 = **66.7 %** | — |
| **P43 p3 (9.8 N)** | `moe_v13s` | A un-parked | **32/54 = 59.3 %** | **20/54 = 37.0 %** | **33/75 = 44.0 %** |

The grip profile did reach this interface: on the batch's own `[carry]` rows the
**retained** legs carry **9.31 N** (A, n = 37) / **9.74 N** (B, n = 53) and the
onset rows (0 < F < 100 N, i.e. excluding the zeros and one 490 N first-tick
spike) read **10.79 / 10.38 N** medians, against the P37 pre-P41 direct
corpus's **3.57 N** median. So the re-measurement's premise is satisfied: the
park's win is now measured at the shipped 9.8-9.9 N, not at 4.4 N.

## 3. P8 — the check (read before any outcome)

| term | A (control) | B (park) |
| --- | --- | --- |
| banded right-active episodes (inactive = left) | 54 | 56 |
| **M1-held** vs the pose the reset **achieved** (≤ 0.02 rad) | **54/54** (median 0.002) | **56/56** (median 0.004) |
| achieved-vs-commanded residual (median) | 0.037 rad | **0.088 rad** |
| **M1-applied**, P35 read (`q_settled`, nearest reference + drift ≤ 0.02) | — | **56/56** (|q−back| 0.089, |q−ready| 0.602, drift ≤ 0.010) |
| **M1-applied**, P37 read (`q`) | — | **56/56** (|q−back| 0.093) |
| the shipped-pose negative (|q−ready| ≤ 0.15) | **54/54** | — |
| **M2a** the arm term at the band's worst call (< 0.10) | **0/54** (median 99.5) | **56/56** (median 0.000, max 0.000) |
| band census, inactive = left | **903/1340 = 67.4 %** fully hidden, 1340/1340 any arm pixel | **0/1364 = 0.0 %** fully hidden, 0/1364 any arm pixel |

**P8 PASS.** The 0.088 rad achieved-vs-commanded residual is the documented
`teleport_joints` settle property (P35 measured 0.088 for `back` against 0.037
for the shipped `ready`), and it is why the gate is written against the
**achieved** pose: the shipped `ready` reset sits 0.037 from its own command, so
a command-relative bar discriminates nothing. The two instruments agree to the
digit (`logs/p43/p3/P3_park_ab.txt` is the P35 report run on this batch: M1
56/56, M1-applied 56/56, M2a 56/56), and P37's own H2 gate reads the same shape
(44/44 and 49/49). M2b (`rel ≥ 0.85`) reads **39/56 = 69.6 %** and stays what
P35/P37 made it — a report, not a gate (its denominator is a *running* `px·d²`
maximum; the batch's masks are 20-192 px, median 116, so its misses are the
normalisation, not an occluder).

## 4. The endpoints

### P2 — the primary: right-arm placed

| | A | B |
| --- | --- | --- |
| right placed | **32/54 = 0.593** | **53/56 = 0.946** |
| delta | — | **+0.354** (bar ≥ −0.10) |
| exact two-sided Fisher | — | **p = 7.75e-06** |
| exact non-inferiority p at margin 0.10 | — | **8.00e-07** |
| Newcombe one-sided 95 % lower bound | — | **+0.228** |
| standardised to A's weights — species | 0.593 | 0.942 (**+0.349**, coverage 1.00) |
| standardised — diameter tertiles (4.00 / 6.10 cm) | 0.593 | 0.947 (**+0.355**, coverage 1.00) |

**P2 PASS**: the point rule clears, the standardised signs agree with the crude
delta, and the interval's lower bound is **+0.228** — i.e. even the one-sided
95 % bound is a *gain*, not the margin.

### P1 — the right-arm carried contrast (a REPORT in branch B)

`A 20/54 = 0.370` → `B 0/56 = 0.000`, contrast **−0.370**, exact two-sided
Fisher **p = 7.31e-08** (one-sided, B fewer: the same to 4 s.f. — the upper tail
of the hypergeometric is one table here). It is not the registered test in
branch B; it is reported because the branch's premise was "not resolvable at
this n" and that premise is **false** for this batch.

### P3 — the pooled rate, arm-standardised (a REPORT, not a test — P37)

| cut | A | B | delta |
| --- | --- | --- | --- |
| raw pooled | 0.440 (33/75) | 0.707 (53/75) | +0.267 |
| **arm-standardised at 50/50** | **0.320** | **0.473** | **+0.153** |
| arm-standardised at A's mix (0.720 right) | 0.440 | 0.681 | +0.241 |
| per-arm right / left | 0.593 / 0.048 | 0.946 / 0.000 | — |

P37's warning reproduces in direction: the raw pooled number (+0.267) is larger
than the equal-arm standardised one (+0.153) because both realisations are
right-heavy (0.720 / 0.747) and the equal-arm form weights the **left** up from
0.25-0.28 to 0.50 — and the left is the one channel where A is (very weakly)
ahead, 0.048 vs 0.000. **Both exceed the PREREG's +0.10 marker, and neither is
quoted as a test.**

### P4 — the left arm (the park's no-op guard)

`1/21 = 0.048` (A) → `0/19 = 0.000` (B), delta **−0.048** against the bar
**−0.05**: **PASS by one episode**. The left has **no park vector**
(`configs/arm_parks.json` lists the left only, so a right-inactive episode gets
the shipped `ready` — the built-in negative control), and its carried class is
flat in *count* (20 → 18) with the same `clean_slip` signature. At n = 21/19 a
one-episode move is inside the no-op noise P36 measured on the same guard
(0.050 vs 0.119); it is recorded as a pass at the bar's edge, not as a cost.

### P5 — failure reasons

Both arms carry the **same 3** distinct normalised reason sets (`intercept
trigger (…)` alone, `+ fruit did not follow the gripper`, `+ fruit left the
pick station during the close (# mm)`). **NEW in B: none.** The
`fruit left the pick station during the close` note is the *pre-existing*
class on this scenario (it is in A too), not new.

### P6 — the cycle

Pooled median **1826 → 1830 ticks** (+0.2 %, bar ≤ +5 %); right arm only
**1806 → 1790** (−0.9 %). **PASS.**

### P7 — the run level, and the run-stratified test

| seed pair | right placed A | right placed B | carried A → B |
| --- | --- | --- | --- |
| 77 | 4/11 | **10/11** | 6 → 0 |
| 101 | 6/9 | **10/11** | 3 → 0 |
| 202 | 7/12 | **9/9** | 5 → 0 |
| 303 | 6/9 | **9/10** | 3 → 0 |
| 404 | 9/13 | **15/15** | 3 → 0 |

**B better in 5/5 runs** (bar ≥ 4/5), one-sided sign p = **0.0312**;
run-stratified placed **Mantel-Haenszel OR 13.03**, CMH χ² 18.92 (1 df),
**p = 1.36e-05**. The run level and the pooled read agree. (The 113 pair test
over episodes reads p = 0.0193 with 41 of 75 pairs excluded by fruit class —
the weaker pairing AGENTS §2 warns about; the **run level** is the registered
leg.)

## 5. The mechanism, on the same class

From the batch's own `[carry]` rows (`FRUIT_CARRY_DIAG=1` on both arms):

| population | legs | `force_min = 0` (payload out) | `clean_slip_max > 50 mm` | `clean_slip` median | retained-leg pinch |
| --- | --- | --- | --- | --- | --- |
| **A right** (the lever's population) | 53 | **16** | **15** | 0.8 mm | 9.31 N (n = 37) |
| **B right** | 55 | **2** | **2** | 0.0 mm | 9.74 N (n = 53) |
| A left (no-op) | 21 | 16 | 16 | 268.5 mm | 7.52 N (n = 5) |
| B left (no-op) | 19 | 15 | 15 | 253.8 mm | 8.17 N (n = 4) |

So the park removes the **W8-B loaded-slide escapes on the right** (force
collapse 16 → 2, > 50 mm slip 15 → 2) at the shipped 9.3-9.7 N pinch, and it
does nothing on the left — which is exactly the shape P35/P36 measured and
P36's 2x2 attributed to the **image** channel. What this phase does **not**
re-measure is *which image statistic* (the fruit's sightline remains the
leading, unseparated candidate; P35's control still succeeds with the fruit
invisible on 9 of its 23 right-arm successes).

## 6. What this phase does not claim

* **The pooled rate is not a test** (P37 / the Oracle amendment): both the raw
  and the arm-standardised forms are reported, and the decision does not use
  them.
* **P1 is not the gate** (branch B). It is quoted because it is significant at
  7.3e-08; a reader who wants a class-level test should read the contrast, not
  the registered label.
* **The `moe_v12` + park configuration remains untested** — and it has no
  deployment path: the canary (`60_eval_policy.py`) does not construct
  `SortingRLEnv`.
* **The un-parked-baseline change from P35 (45.1 % → 59.3 % placed) is
  cross-batch**, not a controlled grip-profile comparison (different tree,
  different code lineage). It is the honest reading of "the baseline moved
  under P41", not an effect size.
* **The left guard passes by one episode** (1/21 → 0/19); at this n that is
  inside the measured no-op noise.
* **Nothing here re-opens** the grip/seat class (`logs/p42/SIM_LIMIT.md` stands;
  the class **persists** at 9.8 N — 20 right-arm carried in the control), the
  supply density (P1c), the place geometry (P3), the belt speed (R3), the
  cadence or the seat (P42).
* **No cross-scenario transfer** is claimed: this is the P35/P36/P37 patch
  scenario; the two-line has no policy eval harness and the direct interface is
  the only place the park exists.

## 7. The decision, and what the flip costs (Phase 4's, not this phase's)

**ADOPT** (`P8 ∧ P2 ∧ P5 ∧ P7`, plus the branch-B carried report in the
favourable direction and the guards P4/P6 not failing). The exact change, so
Phase 4 has no design work left:

```python
# rl_env.py, in the SortingRLEnv init (currently :991)
_park_default = "back" if presentation == "direct" else ""
self._arm_park = os.environ.get("FRUIT_ARM_PARK", _park_default).strip()
```

**It must be scoped to `presentation == "direct"`**: the current guard raises
for any other presentation (`rl_env.py:994-999`), so an unscoped default would
break `handoff`/scripted constructions. `FRUIT_ARM_PARK=ready` must keep
restoring the shipped pose (the `!= "ready"` short-circuit already does).

**The cost, which belongs in the same commit's note:** the flip **re-baselines
the direct interface** — every quoted direct number (P33, W7-C, W8-A, R9, P35,
P36, P37, P38, P43-p2's F5 pair) becomes a **pre-park** number, and a future
direct A/B must state its park state. The park is also **recordable** (P37
collected 90 episodes under it) and the manifest already carries `arm_park`
(`rl_env.py:1520`), so post-flip stores are identifiable.

## 8. Pins, files, reproduce

**Pins.** HEAD `53e5ccf`; `tasks.py` `a1b3d673`, `rl_env.py` `6324b60b`,
`control.py` `9384ff4f`, `scene.py` `27e3d64a`, `policy/trigger.py`
`b09d3cb2`, `policy/runtime.py` `379ac706`, `meshes.py` `41efc522`,
`fruits.py` `6f65e423`; `configs/arm_parks.json` `42ab4fb7`,
`configs/waypoints.json` `d81c6f1c`, `configs/motion_reference.json`
`8a399626`, `..._twoline.json` `2246f83c`; checkpoint `61da390a`;
`scripts/112_rl_ab.sh` `e0f0db1d`, `scripts/113_rl_report.py` `c27c49b8`,
`scripts/154_claim_run.sh` `1a5adba6`, `logs/p35/park_ab_report.py`
`a796db0b`, `logs/p37/p37_report.py` `50dae91d`, `logs/w7/B_ab_report.py`
`6d60db0a`, `logs/p43/p3/run_batch.sh` `9fb9f461`,
`logs/p43/p3/p3_report.py` **`deaadba0` at batch time → `63740f0f`** after a
**print-only** fix to the branch-B verdict text (two lines of output: the P1
label gains "[a REPORT in branch B]" and the verdict stops repeating the
pre-registration's stock "no class-level evidence" sentence, which is not true
of this batch; the endpoint numbers are unchanged and the report was re-run
from the same logs).

**No-harm.** Phase 3 changed **no code and no `configs/`** (all 8 overlapping
pins in `P3_header.txt` / `P3_tree_md5_after.txt` are identical), so the
phase-2 §6 contract stands on this exact tree (N1 selfcheck PASS, N2 acceptance
byte-identical 377/377 + `fingerprint: matches` 8a399626, N4 `96` PASS, N5
configs/checkpoints unchanged) — re-verified here with `scripts/selfcheck.sh`
**PASS, 0 failures, 1 skipped** (`logs/selfcheck.log`).

```
logs/p43/P3_RESULTS.md              this file
logs/p43/p3/run_batch.sh            the batch (one claim, 10 sessions, A-then-B per seed pair)
logs/p43/p3/p3_report.py            the report (the registered endpoints + --self-test)
logs/p43/p3/P3_header.txt           the pins at run time (git HEAD, 21 md5s, the scenario line)
logs/p43/p3/P3_tree_md5_after.txt   the pins after (identical) + the batch wall
logs/p43/p3/batch_driver.log        the driver rows (per-run rollout success)
logs/p43/p3/batch_outer.log         the driver's own clock (start / claim / done)
logs/p43/p3/{A,B}_{1..5}.log        the 10 sessions (the `[rl] episode`, `[park]`, `[carry]` rows)
logs/p43/p3/smoke_{A,B}.log         the pre-batch plumbing check (2 episodes each, not the measurement)
logs/p43/p3/P3_report.txt           the report's output
logs/p43/p3/P3_park_ab.txt          the P35 report cross-check (M1/M2a/census, same digits)
logs/p43/p3/P3_113.txt              the 113 cross-check (pooled, episode pairs, reasons)
```

Reproduce:

```bash
python3 logs/p43/p3/p3_report.py --self-test
python3 logs/p43/p3/p3_report.py --dir logs/p43/p3 --a A --b B   # -> P3_report.txt
python3 logs/p35/park_ab_report.py --dir logs/p43/p3 --a A --b B  # -> P3_park_ab.txt
python3 scripts/113_rl_report.py logs/p43/p3 --a A --b B          # -> P3_113.txt
```

`logs/` is gitignored (`.gitignore:7`); every file above needs `git add -f`
when Phase 4 commits, the P41/P42 corpus precedent. Nothing in this phase is
committed yet.
