# P42 phase 2 — the bounded pre-close centring (`FRUIT_SEAT_CENTRE`): the
# command is issued, the close re-aims it away, and the seat does not move

Measured 2026-10-26 on `c2760bf` + this phase's (uncommitted) `tasks.py` /
`rl_env.py` change. **No commit, no `configs/` change** (both references still
read **8a399626** and **2246f83c**). **Two claimed runs** (~9 min of simulator
wall), sequential through `scripts/154_claim_run.sh`, plus `scripts/selfcheck.sh`.
Scope: the scripted single-arm moving catch (`20_pick_place.py`); the two-line,
the direct/policy handover and the hybrid canary were **not** run this phase
(the knob is not armed on those paths, §1).

Script: `logs/p42/p3/run_p3.sh` (the driver log `logs/p42/p3/driver.log`).
Read-out: `logs/p42/p3/CENTRE_READ.txt` (`logs/p42/p3/centre_compare.py`).

---

## 0. The short answer

* **The lever acts and is then absorbed.** One `ik_step` of
  `clip(-d_xy, +-m)` is commanded on every grip (n = 10 per run, |c| **2.99 mm**
  median on the pear and **2.91 mm** on the acceptance, range 2.30-4.02, the
  10 mm clamp **never binding**). At the close freeze 18-22 ticks later the seat
  is back where the shipped line puts it: paired per grip the freeze `|d_xy|`
  changes by **+0.00 mm** median on the pear (`[-0.1, +0.9]`, n = 6 pairs) and
  **+0.01 mm** on the acceptance (`[-1.2, +0.4]`, n = 10 pairs), against the
  control's own medians (pear 1.83 vs 1.83 mm, acceptance 2.13 vs 2.17 mm).
* **Why: the close is coherent, and the PREREG's premise was not.** The close's
  own local `coherent` flag - the one that gates the per-tick `ik_step` - reads
  **True on 20/20 grip closes**, so the close re-aims the jaw at the fruit's
  live centre every tick and the one-shot correction is overwritten. PREREG §2
  read the **carry bookkeeping's** `self._coherent[side]` (False on 60/60 legs,
  reproduced here) and took it for the close's flag: **two different
  variables**. By the registration's own mandatory evaluability clause ("if any
  leg reads `coherent=True` ... that leg is not evaluable") **P1/P2/P3 are not
  evaluable on this tree**, and F2 fired by its letter for a reason other than
  the one it names.
* **The class does not move on an evaluable comparison, and the counts that do
  differ are a moved branch.** Pear: control **6/10** (left 2/6, right 4/4,
  4 cnp) vs lever **7/10** (left **1/4**, right 6/6, 3 cnp) - **the left attempt
  count changed 6 -> 4, so F5 fires and P3 is a report, not a verdict**.
  Acceptance: **6/10 in both**, left 1/5 and right 5/5 in both, span 15.0 s in
  both, but `fingerprint` **DIFFERS** (leg 3 `|v|max` 0.109 vs 0.108) while the
  same-tree control reads `matches` - the jog moved the attractor by one leg's
  peak speed and swapped one attempt between the classes (attempt 0 peach
  cnp -> placed, attempt 2 kiwi placed -> cnp).
* **The ceiling is ~2-3 mm against a 100-350 mm walk.** `|d_pre|` 2.30-4.02 mm
  is the entire available correction and it is removed again before the freeze;
  the escapes still walk **38-120 mm** at the lift's 99 % sample and
  **304-339 mm** by the place leg's first ticks, with **2/3 and 3/3** of the
  samples one-sided. Nothing about the walk changed.
* **A sub-millimetre-scale sensitivity, for the record.** On the acceptance the
  *same* peach whose freeze seat reads 2.63 mm (control 2.62 mm, +0.01) lifted
  266.2 mm of `slip_max` in the control and 27.5 mm in the lever run: the seat
  at the freeze is the same, the class is not. The escape is decided by the
  contact history *through* the close and the lift, not by the seating offset -
  which is the census's conclusion arrived at from the other side.

---

## 1. The lever, as built (`tasks.py` **3e6ea4cf**)

| piece | where | what |
|---|---|---|
| `self._seat_centre` | `__init__`, beside `FRUIT_SEAT_DIAG` | one env read; `FRUIT_SEAT_CENTRE=<m>`, unset/empty/unparseable/`<= 0` = **off**; `m = min(value, 0.020)` and a value above the bound prints one `clamped to the registered bound` note |
| `_seat_centre_step()` | beside `_seat_read`/`_seat_arm` | the one read + one command + the `[seat] centre` row |
| the call site | the dynamic close, **after** the catch-up loop's last tick and **before** `live_squeeze` / the close ramp | one `ik_step` of `clip(-d_xy, +-m)`, x/y only, no re-measure, no re-approach |

```python
pads = grippers[side].pad_centre(); fruit = spawner.position(sample)   # one read
corr = clip(-(pads - fruit)_xy, -m, +m)                                # x/y only
arm.ik_step(arm.tcp_target_for_jaw(pads + corr))                       # one command
```

* **z is excluded by construction**: `dz` at the freeze is the *commanded*
  standoff (`+69.3..+71.7 mm` = `_pad_standoff(True, sample)`), i.e. a grip-plane
  question, and D2a is measured negative (`logs/r8/A_RESULTS.md`). Nothing here
  re-opens it.
* **Scope**: `dynamic_capture and not direct_capture` and `not two_line_enabled()`,
  as registered (scripted OpenArm moving catch only). The direct/policy handover
  and the two-line scheduler never reach it; with the knob unset the site is one
  float comparison per close and `__init__` one `getenv`.
* **The print** (one per grip, when it acts):

  ```
  [seat] centre right idx=8 d=(-3.3,+0.6)mm applied=(+3.3,-0.6)mm m=10.0mm coherent=True
  ```

  `d=` is the offset it read (pads - fruit, the value it corrects), `applied=`
  the commanded correction, `m=` the resolved clamp, and `coherent=` the
  close's own flag - printed because it decides whether the command survives
  (§2). No `unavailable` row occurred in either run.
* **No-harm on the shipped default**: the knob-off path is unchanged code (the
  same false test the phase-1 instrument takes); the phase-1 control
  `logs/p42/p2/seat_accept.log` - recorded on this code path with the knob
  unset - still reads `fingerprint: matches configs/motion_reference.json`.
  **No knob-unset re-run was spent** (this phase's budget is the two runs below);
  the identity claim for the unset knob is structural plus that control, and is
  labelled as such rather than measured again.

---

## 2. Evaluability: the close is coherent, and two different variables were conflated

`CENTRE_READ.txt` §1, both runs:

| read | value | what it means |
|---|---|---|
| the close's own `coherent` (printed by `[seat] centre`) | **True 10/10** pear, **True 10/10** acceptance | the close calls `ik_step` on the fruit's live centre **every tick** (`tasks.py`, `if coherent:` in the ramp) |
| the carry's `[diag] carry-assist ... coherent=` (`self._coherent[side]`) | **False 60/60** pear, 60/60 acceptance | what PREREG §2 quoted |

These are not the same flag. `self._coherent[arm_name]` is set `True` only on the
`pad_error <= FRUIT_COHERENT_FALLBACK (20 mm)` branch and is **never** set `False`
on the OpenArm's "closing anyway" branches; on the first attempt it starts
`False`, and because the OpenArm's pre-grasp `pad_error` exceeds 20 mm the dict
keeps that value for the whole session - so it reads `False` on every leg while
the close's local `coherent` (assigned `openarm or ...` and only reset in the
non-OpenArm fallbacks) is `True`. The registration's premise ("the close runs
non-coherent, so the pre-close re-aim *is* the close's aim") therefore does not
hold on this tree, and the mandatory clause makes the lever's own legs **not
evaluable**.

This is structural, not a property of these two runs: `coherent` is set
`False` in exactly two places (`tasks.py`, the axis-error and fingertip-error
fallbacks) and **both are guarded by `if openarm: ... else:`**, so with the
OpenArm hand - the only hand this line runs - the close can never take the
non-coherent branch. A pre-close one-shot command on this hand is always
re-aimed away, which is exactly what the seat read shows: a 2.3-4.0 mm jog, and
a freeze seat identical to the control's to 0.01 mm.

---

## 3. The correction, the seat, and the class

### 3.1 Pear battery (`FRUIT_SUPPLY_SPECIES=pear ATTEMPTS=10 SEED=5`)

Control `logs/p42/p2/seat_pear.log`, lever `logs/p42/p3/pear_centre010.log`
(both with `FRUIT_SEAT_DIAG=1 FRUIT_CARRY_DIAG=1`, so the control is the census's
own instrumented run and the instrument is proven free, `logs/p42/p2/identity.txt`).

| read | control | lever |
|---|---|---|
| commands issued | - | 10, \|c\| median **2.99** mm [2.30, 4.02], clamp not binding |
| `\|d_pre\|` at the correction instant | - | median 2.99 mm [2.30, 4.02] |
| freeze `\|d_xy\|`, pooled median [range] | 1.81 [1.4, 4.7] mm | **1.83** [1.3, 4.8] mm |
| freeze `\|d_xy\|`, paired per grip (n = 6) | - | **+0.00** mm median [-0.1, +0.9] |
| freeze `asym` pooled median | 0.10 | 0.09 |
| class | **6/10 placed, 4 cnp**; left **2/6**, right 4/4 | **7/10 placed, 3 cnp**; left **1/4**, right 6/6 |
| span | 15.7 s/attempt (157.1 s) | **15.5 s/attempt** (155.4 s) |
| failure notes | none | none |
| the walk, `placed@3` \|drift\| median | 40.0 mm | 44.9 mm |
| the walk, `escape@3` \|drift\| median [range] | **194.8** [104.3, 276.0] mm, 4/4 one-sided | **101.4** [38.6, 119.8] mm, 2/3 one-sided |
| the walk, `escape@4` \|drift\| median [range] | 352.6 [302.7, 374.9] mm, 4/4 one-sided | 324.8 [303.8, 339.4] mm, 3/3 one-sided |

**The class count is one draw of a moved branch, not a verdict.** The first
physics difference is attempt 0's `[motion] carry grasp_lift` row (164 -> 165
ticks, `slip_max` 45.3 -> 45.6 mm); attempts 0-4 then select and place
identically (attempt 4 selects the same pear A on lane 0 and escapes in both),
and **attempt 5 selects a different fruit** (control pear A lane 0, lever pear B
lane 1) - after which the left takes 2 and the right 6 attempts instead of 6 and
4. **F5 fired**: the left attempt count is not invariant, so P3 is a report.

### 3.2 The acceptance (`ATTEMPTS=10 SEED=5`)

Control `logs/p42/p2/seat_accept.log`, lever `logs/p42/p3/accept_centre010.log`.

| read | control | lever |
|---|---|---|
| commands issued | - | 10, \|c\| median **2.91** mm [2.50, 3.64] |
| freeze `\|d_xy\|` pooled median [range] | 2.17 [1.6, 3.5] mm | **2.13** [1.3, 3.9] mm |
| paired per grip (n = 10) | - | **+0.01** mm median [-1.2, +0.4] |
| class | 6/10 (left 1/5, right 5/5), 4 cnp | 6/10 (left 1/5, right 5/5), 4 cnp |
| span | 15.0 s/attempt | 15.0 s/attempt |
| escapes by attempt | 0, 1, 3, 9 | 1, 2, 3, 9 |
| `105_motion_regression.py` | **`fingerprint: matches`**, rate-only FAIL 6/10 | **`fingerprint: DIFFERS`** (leg 3 `|v|max` 0.109 vs 0.108), rate-only FAIL 6/10 |

The rate, the per-arm split, the span and the `cnp` count are identical; the
*identity of the escaping attempt* is not, and the fingerprint differs by one
leg's peak speed. Per AGENTS §2 the two runs are different attractors: the
6/10-vs-6/10 agreement measures nothing, and the fingerprint item of P5
**FAILS** on the lever arm while the same-tree control passes it.

Attempt 0 is the sharpest single row: the same peach, seat 2.63 mm vs 2.62 mm
(+0.01) at the freeze, `slip_max` **266.2 mm (cnp)** in the control and
**27.5 mm (placed)** in the lever run. A 3.5 mm jog that is fully re-aimed away
by the freeze still changes the close's *approach history* enough to flip that
attempt - and the kiwi at attempt 2 flips the other way. That is a statement
about the class's sensitivity, not about the lever.

---

## 4. Endpoints, as registered (`logs/p42/PREREG.md` §3)

| # | endpoint | rule | measured |
|---|---|---|---|
| **P1** | mechanism | paired freeze `\|d_xy\|` median falls >= 50 % relative (pear) | **FAIL**: +0.00 mm (0 %), median 1.83 vs 1.83 mm. Not evaluable anyway (§2: `coherent=True` 10/10) |
| **P2** | secondary | freeze `asym` median falls >= 20 % relative | **FAIL**: pooled 0.10 -> 0.09 (the pair's escape sets differ, n = 4 vs 3); not evaluable |
| **P3** | class | left cnp falls, **left attempt count invariant** | **not a verdict**: left cnp 2 -> 1 of 4, but the left attempt count moved 6 -> 4 (**F5**) |
| **P4** | cost | span <= +0.2 s/attempt | **PASS**: 15.7 -> 15.5 s (pear), 15.0 -> 15.0 s (acceptance) |
| **P5** | no-harm | knob unset -> byte-identical; fingerprint matches; selfcheck PASS; `configs/**` unchanged | unset: structural + the phase-1 control `matches` (no re-run spent); **lever arm: fingerprint DIFFERS**; `scripts/selfcheck.sh` **PASS** (0 failures, 1 skipped); `configs/**` **untouched** |

Falsifiers: **F1** fired in phase 1 (the seat is already <= 2 mm on the pear
escapes). **F2 fired** by its letter (P1's median does not fall) - but not by its
named mechanism (the pick pose's reach boundary): the arm executes the command
and the close removes it (§2). **F3** clear (no failure note in either arm, 40/40
`notes=[]`). **F4** clear (the catch-up residuals are the shipped 5.6-6.0 mm on
all 40 attempts in both pairs and no selection changed *at the correction*; the
later selection change is the branch move). **F5 fired** on the pear.

---

## 5. What this phase settles

1. **The seat is not the term, measured from the lever side too.** The largest
   correction the registration allows is ~3 mm on these corpora; it is issued,
   removed again by the shipped close before the freeze, and the class's
   mechanism (a 100-350 mm mid-lift walk with the contact going one-sided) is
   untouched.
2. **An evaluability defect in PREREG §2** - the close's `coherent` is not
   `self._coherent[side]`, and on this tree the close is coherent on every
   measured grip, which is the *opposite* of what §2 assumed. Any future
   pre-close command on this line has to reckon with the per-tick re-aim (either
   by scoping to a non-coherent path or by registering against the coherent one,
   e.g. a per-tick aim offset rather than a one-shot).
3. **The class is decided inside the lift, not at the seat** - the phase's own
   sharpest row is a 266 mm escape and a 27 mm clean lift on the *same* fruit at
   the *same* freeze seat to 0.01 mm, i.e. the outcome is not a function of the
   seating geometry. This is the B record's core, `logs/p42/SIM_LIMIT.md`.

**Recommendation: no adoption, no default change.** `FRUIT_SEAT_CENTRE` stays
default **off** and is a measurement interface with a documented null. The lane
is closed - the next step is B (the sim-limit record), not a second lever arm, a
z variant or a bigger clamp (§5 of the registration forbids all three).

---

## 6. Limits

* **One pair per corpus**, single branches. Nothing here is a rate; the pear's
  counts differ on a branch that moved at attempt 5 and the acceptance's counts
  agree across two different attractors.
* **The pear's paired seat read is n = 6 of 10** because the branch move leaves
  four grips with no same-key control grip; the unpaired pooled medians (1.81 vs
  1.83) are quoted beside it.
* **The knob-unset byte identity was not re-measured this phase** (§1) - the
  claim rests on the unchanged code path and the phase-1 control, which still
  matches the shipped reference.
* The two-line, the direct/policy handover and the hybrid canary were not run:
  the knob is not armed on those paths, and the class statements above are the
  scripted single-arm line's.

---

## 7. The runs

```bash
scripts/selfcheck.sh                                        # PASS, 0 failures
scripts/154_claim_run.sh logs/p42/p3/pear_centre010.log \
    ATTEMPTS=10 SEED=5 FRUIT_SUPPLY_SPECIES=pear \
    FRUIT_SEAT_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_MOTION_REPORT=1 \
    FRUIT_SEAT_CENTRE=0.010 scripts/run.sh scripts/20_pick_place.py
scripts/154_claim_run.sh logs/p42/p3/accept_centre010.log \
    ATTEMPTS=10 SEED=5 \
    FRUIT_SEAT_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_MOTION_REPORT=1 \
    FRUIT_SEAT_CENTRE=0.010 scripts/run.sh scripts/20_pick_place.py
python3 logs/p42/p3/centre_compare.py logs/p42/p2/seat_pear.log \
    logs/p42/p3/pear_centre010.log                  > logs/p42/p3/CENTRE_READ.txt
python3 logs/p42/p3/centre_compare.py logs/p42/p2/seat_accept.log \
    logs/p42/p3/accept_centre010.log               >> logs/p42/p3/CENTRE_READ.txt
python3 scripts/105_motion_regression.py logs/p42/p2/seat_accept.log \
    --fingerprint configs/motion_reference.json     # matches
python3 scripts/105_motion_regression.py logs/p42/p3/accept_centre010.log \
    --fingerprint configs/motion_reference.json     # DIFFERS (leg 3, 0.109 vs 0.108)
```

Code: `src/fruit_sorting/tasks.py` **3e6ea4cf** (the knob + `_seat_centre_step` +
the call site), `src/fruit_sorting/rl_env.py` **b4d4accc** (`TASKS_MD5`
metadata-only follow `e34e0f58 -> 3e6ea4cf`). `configs/*` untouched
(**8a399626** / **2246f83c**). Evidence `logs/p42/p3/` (`pear_centre010`,
`accept_centre010`, `CENTRE_READ.txt`, `centre_compare.py`, `run_p3.sh`,
`driver.log`), `logs/selfcheck.log`.
