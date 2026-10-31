# P74 — the place-profile **speed** vs the left arm's place-leg loaded slide

**A pre-registered 2-arm direction test on the DIRECT line. Registration only,
written and md5-pinned BEFORE any simulator run of this phase. Nothing is
adopted, no shipped default moves, no commit is made, `configs/` is untouched,
and no `src/` file is edited.**

Tree at registration: HEAD `75e980a` (the P73 commit), `tasks.py`
**`adcfd348`**, `rl_env.py` **`157e6d85`**, `assets.py` `540406fa`,
`conveyor.py` `fb2c58c6`, `fruits.py` `c7461d41`, `scene.py` `27e3d64a`,
`configs/motion_reference.json` **`8952c320`**,
`configs/motion_reference_twoline.json` **`eb697f23`**, checkpoint `moe_v13s`
**`61da390a`**.

---

## 0. The question, and the hypothesis stated so it can fail

P73 phase 1 falsified the place-transfer hypothesis in both directions
(`logs/p73/P1_RESULTS.md`): the transfer height **is** a monotone lever on the
achieved place rotation (**+26.5 deg** from C to T2) and on the crossing
clearance (**+108.5 mm**), and it is **inert** on the loaded slide (1/1/1). The
two discriminators it left are:

* **the rotation is not the actuator** — the right reaches a median **107.3 deg**
  and slips 0.0-0.1 mm on **10/10** legs, and **8 of 8** payload losses start
  **before** their leg's 45-deg crossing (onset rows 3-265, `t45` 303-561);
* **the dwell under load is the surviving candidate** — the **slowed** place
  profile (`FRUIT_SPEED_PLACE=0.20`) reads **4 slides in 8 legs (50 %)** against
  C's **1 in 5 (20 %)** with the rotation starting at the **same fraction** of
  the leg (73-78 % vs C's 73-79 %) but **+211 ticks = +1.76 s of absolute
  dwell**, i.e. a 67 % longer leg roughly doubles the escape rate.

**Hypothesis (H2).** The left's place-leg loaded slide is a **time-accumulating
loaded creep**: the payload walks out of a top-down pinch at a rate set by the
pinch's own compliance under lateral load, so the escape probability grows with
**how long the leg spends under load**. Therefore speeding the place profile up
must **reduce** the escape rate — the exact mirror of P73's SLOW arm.

**H2 fails** if any of:

* **A** the slide count does not move while the leg's dwell does (the dwell is
  not the actuator either, and the class is *stochastic given the pinch* —
  P73's C arm holds a leg at **793.3 mm**, just under the 800 mm threshold, at
  the *same* rotation schedule as its 995 mm slide, which is exactly what a
  threshold-and-hazard picture looks like at n = 5);
* **B** the slide count **rises** in S (the class is an **inertial/impact**
  response to the faster profile, i.e. both speed directions are bad and the
  place leg has an interior optimum near the shipped 0.35);
* **C** the acquisition guard or the landing class regresses (the cell spends
  more than the class buys).

Any of A/B/C -> the place-profile speed is **not** a lever on this class, and
what is left of it is the `logs/p42/SIM_LIMIT.md` closed loaded slide plus the
**time** trade P44/P46 already priced. That negative is publishable, and it is
the last unspent direction P73's own text names ("the *speed-up* direction is
the one with a measured contrast").

---

## 1. What the knob is, and which knob actually reaches the DIRECT place leg

### 1.1 The code path (facts, not the brief's summary)

`FRUIT_SPEED_PLACE` is the P44 **S1** cell (`tasks.py:107-200`). It changes no
behaviour by itself: `speed_cell_defaults()` returns the **default strings** for
the per-leg caps, and the place cap is read at

```
tasks.py:3853   place_v = float(os.environ.get("FRUIT_DYNAMIC_PLACE_VMAX",
                                               _speed["place_vmax"]))
```

inside `elif self._dynamic_capture_active:` (the `_carry` motion-profile block,
`tasks.py:3832`). So:

* **the cell is the fallback default of `FRUIT_DYNAMIC_PLACE_VMAX`**, and an
  explicit `FRUIT_DYNAMIC_PLACE_VMAX` wins over it;
* **the direct presentation runs that branch.** `dynamic_pick =
  _dynamic_pick_mode(openarm=True, scripted=False)` is True because the cell
  sets `FRUIT_DYNAMIC_PICK=1`; `dynamic_capture = dynamic_pick and openarm` ->
  True; `direct_capture = dynamic_capture and not scripted` -> True; and
  `self._dynamic_capture_active = dynamic_capture` (`tasks.py:9677`). The
  `[carry]`/`[motion]` rows of the P73 direct arms confirm it in-log.
* **`FRUIT_SPEED_PLACE=0.52` and `FRUIT_DYNAMIC_PLACE_VMAX=0.52` are
  limit-identical on this leg, arithmetically**: the registered value `0.52`
  keeps `place_amax` at the shipped **1.089** (the `place ==
  _SPEED_REGISTERED["place"]` arm of `speed_cell_defaults`), and with the cell
  unset `_speed["place_amax"]` is already `"1.089"` — so both resolve
  `v_max = 0.52`, `a_max = min(2.0, 1.089) = 1.089`, and then
  `limited_by_cone` leaves both alone (the place leg's cone budget is
  **4.273 m/s^2**, P44 §2.4, and `j_max = min(25, 10.89) = 10.89`,
  `v_max = min(0.52, 2.178) = 0.52`).

**The knob used is `FRUIT_SPEED_PLACE=0.52`**, for three reasons: (i) it is the
**P44 S1 registered cell** whose scripted measurement is `place0` **-135.4
ticks** / `place1` -64.2 (`logs/p44/P2_RESULTS.md` §9.1); (ii) it is the **same
env var P73's SLOW arm used** (`=0.20`), so the S arm is the **exact mirror of
the arm the mechanism was inferred from** — same knob, opposite sign; (iii) if
both are set on one line, the direct path resolves the explicit
`FRUIT_DYNAMIC_PLACE_VMAX`, so naming the *cell* is naming the thing that
supplies the value when only it is set (the S arm sets **only**
`FRUIT_SPEED_PLACE`, nothing else).

### 1.2 The proof that it reaches the DIRECT place leg (already measured)

P73's SLOW arm is the manipulated-positive control for this resolution, on this
exact cell, on this tree:

| log | left `place0` leg | `|v|cmd` |
|---|---|---|
| `logs/p73/direct/C_77.log` | 65 cm, **431 ticks** | **0.342** |
| `logs/p73/direct/SLOW_77.log` (same run family, `FRUIT_SPEED_PLACE=0.20`) | 65 cm, **753 ticks** | **0.196** |

`0.342 / 0.35 = 0.977` and `0.196 / 0.20 = 0.980`: `|v|cmd` tracks the cap
through the 2 % duration margin of the profile. **The knob reaches the direct
place leg, and the leg's `|v|cmd` is its in-log signature.**

### 1.3 The prediction is arithmetic, not a guess

`_carry` builds the leg with `jerk_limited(distance, limits)`
(`motion.py:192`), a **time-scaled minimum-jerk quintic**:

```
T = max( 1.875 d / v_max , sqrt(5.774 d / a_max) , cbrt(60 d / j_max) ) * 1.02
|v|cmd = 1.875 d / T
```

With `a_max = 1.089` and `j_max = 10.89` the **velocity term binds for every
`d > 0.41 m` at `v = 0.52`** (and for every `d > 0.19 m` at `v = 0.35`), so

```
ticks_S / ticks_C = 0.35 / 0.52 = 0.673      |v|cmd: 0.343 -> 0.510 (+48.7 %)
```

Evaluated **offline** with the shipped `motion.jerk_limited` (no simulator, no
run) at the six left-place distances the P73 C arm printed:

| d (m) | C ticks | S ticks | Δ ticks | Δ % | `|v|cmd` C -> S | `|a|cmd` C -> S |
|---|---|---|---|---|---|---|
| 0.41 | 270 | 182 | **-88** | -32.6 | 0.343 -> 0.510 | 0.471 -> 1.040 |
| 0.58 | 382 | 257 | **-125** | -32.7 | 0.343 -> 0.510 | 0.332 -> 0.736 |
| 0.60 | 395 | 266 | **-129** | -32.7 | 0.343 -> 0.509 | 0.321 -> 0.710 |
| 0.63 | 415 | 280 | **-135** | -32.5 | 0.342 -> 0.508 | 0.306 -> 0.673 |
| 0.65 | 428 | 288 | **-140** | -32.7 | 0.343 -> 0.510 | 0.296 -> 0.656 |
| 0.66 | 434 | 293 | **-141** | -32.5 | 0.343 -> 0.509 | 0.293 -> 0.644 |

The C column reproduces the **measured** C ticks to 0-3 ticks (431/392/272/416
against 428/395/270/415 at the cm-rounded distances) and `|v|cmd` exactly, so
this is the leg's own profile arithmetic and not a fitted model.

**The place leg is not side-scoped**: the same branch runs for either arm, so
the **right's place legs are expected to shorten by the same 0.673 factor**.
That is a registered property of the knob, not a discovery after the fact; the
right is therefore read as **"no new class and no placed regression"**, never as
"unchanged" (the P73 convention).

---

## 2. The arms and the cell

Direct presentation, the **P66-phase-3 / P71-phase-2 / P73 cell verbatim** (so
the C arm is comparable to the shipped corpus and to P73's C):

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11
FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1
HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1
```

`scripts/110_rl_rollout.py --presentation direct --episodes 15 --seeds <seed>`,
checkpoint `moe_v13s` `61da390a` on both arms, one claim per run.

| arm | place profile | place `v_max` | place `a_max` | the leg's expected `|v|cmd` |
|---|---|---|---|---|
| **C** (control) | shipped | 0.35 | 1.089 | 0.342-0.343 |
| **S** (fast place) | `FRUIT_SPEED_PLACE=0.52` | **0.52** | **1.089** (unchanged) | **0.508-0.510** |

**Order: C -> S at seed 77** (interleaved with nothing else; both arms in the
same stretch of machine time). **Expansion rule (registered):** run seeds 101 and
202 **only** if the seed-77 mechanism read is **consistent with the prediction**
= `Δ left loaded slides <= -1` (i.e. S has at most 0 under the same denominator,
or strictly fewer than C), **and** `Δ left placed >= 0`, **and** the acquisition
guard is clean. Otherwise the phase reports one seed and says so.

**Why 15 episodes**: the shipped corpus gives 5-6 left attempts and 5-8 left
place legs per 15-pick run (the 15/17/0.375 supply is grade-A-heavy -> the left
arm). This is a **mechanism** cell; it cannot resolve a rate and no count here
will be quoted as one.

---

## 3. Instrumentation — **no `src/` change at all**

Every field this phase needs already exists and is default-off:

| read | knob | where |
|---|---|---|
| `[carry] … clean_slip_max`, `onset_row`, `loss_row`, `force@onset`, `sep@onset`, `sep@loss`, `sep_end`, `contacts@onset`, `force_min`, `min_contacts`, `in-hand_vmax`, `clr`/`clr_win`/`clr_edge`/`clr_edge_min`, `ticks` | `FRUIT_CARRY_DIAG=1` | P41/P61/P72 |
| `tilt0`/`tilt_end`/`tilt_max`/`t45`/`t75`/`tilt_rate` (the P73 rotation schedule) | `FRUIT_CARRY_DIAG=1` | P73 (`tasks.py adcfd348`) |
| `[motion] carry place*` → `|v|cmd`, `|a|cmd`, `|v|max`, `|a|max`, `cone=`, `a_win5` | `FRUIT_MOTION_REPORT=1` | shipped |
| `[attitude] <side> <leg>: tilt=` | `FRUIT_CARRY_ATTITUDE=1` | shipped |
| `[task] place low: … need / drop / ticks` | shipped | shipped |

**This phase therefore edits no source file**, which is why it carries no new
selfcheck leg: the instrument-set is P73's, already pinned by `scripts/240`
(tilt schedule) and `scripts/239` (`clr_edge`). The diag is on in **both** arms,
so it cannot confound the comparison (instrumentation is part of the measurement:
compare arms inside one instrumented batch).

---

## 4. Endpoints, parsing rules, and the pre-run predictions

### Primary

1. **The left's place-leg loaded-slide legs** — `[carry] left place*` rows with
   `clean_slip_max > 800 mm` (the P73 threshold, kept for comparability).
   * **Blow-up exclusion (registered, P73's rule)**: `in-hand_vmax > 5 m/s` or
     `clean_slip_max > 10 000 mm` is an **instrument blow-up**, counted and
     reported separately, never as a slide.
   * The **per-place-leg denominator** is the honest one (P73 §2.1: the left's
     *attempt* count moves run to run, so `placed` is a draw, not a rate).
2. **The left's placed count** (`[rl] episode … arm=left placed=True`).

### Secondary (mechanism, cost, guards)

3. **The manipulation proof**: every left place leg's `ticks` and its
   `|motion| carry place*` `|v|cmd` / `|a|cmd`; the `ticks_S/ticks_C` ratio and
   the `|v|cmd` ratio.
4. **`clr` / `clr_win` / `clr_edge` / `clr_edge_min`** on held legs. The profile
   changes **when** the pads are where, not **where** they go: `jerk_limited`
   returns points on the same straight segment between the same two endpoints,
   so the sampled minimum moves only by the sampling grid. **Predicted
   unchanged, |Δ| <= 5 mm**, and no leg below 0. If they move more than that,
   the profile change is not the clean time-scaling of §1.3 and the report must
   say why.
5. **The escape's signature** on any S-arm slide: `contacts@onset`,
   `force@onset`, `force_min`, `sep@onset`/`sep@loss`/`sep_end`.
6. **The rotation schedule** (`tilt0`, `tilt_end`, `t45`, `t75`, `tilt_rate`)
   — predicted **unchanged**, because the place pose and the reach are
   unchanged and only the clock moves. This is the free cross-check that the
   arm differs only in time.
7. **The schedule discriminator (registered)**: for every payload loss,
   `onset_row / ticks` and `loss_row / ticks`. If the escape is
   **path-fixed**, the *fraction* is invariant between arms and the *absolute
   tick* scales with the leg; if it is **time-fixed**, the absolute tick is
   invariant and the fraction moves. Both are printed, so the phase reads the
   mechanism whichever way the count goes.
8. **The class split**: `cnp` (`grasped=True, placed=False`) against the
   **acquisition** class (`grasped=False`, the pre-contact miss) — the guard the
   brief names. **Any new failure reason** is listed verbatim.
9. **The cost**: the left place-leg ticks, the `place low` descent ticks (the
   knob is *transit-only*, so these must **not** move), the episode ticks
   (median + sum), `discharged` / `did not land` / `fell off`.
10. **The right**: placed count, place legs, slides, `|v|cmd`, landing class —
    read as **"no new class / no placed regression"**, with §1.3's
    both-arms-shorten property stated.

### Pre-run predictions (registered; a miss is a result, not a rewrite)

* **P1 (the class falls)** the left's loaded-slide legs fall in S: from C's
  count to **strictly fewer**, ideally 0. Directional, from P73's SLOW arm
  (1/5 -> 4/8 for a 1.67x leg). Registered direction: **down**.
* **P2 (the cost)** the left's place-leg ticks fall to **0.673x** C's
  (**-88 .. -141 ticks** at the measured distances), with `|v|cmd`
  **0.342 -> 0.509** and `|a|cmd` rising to **0.64-1.04** at the unchanged
  1.089 cap. The `place low` descent ticks are **unchanged** (transit-only
  knob), and the episode shrinks by the place legs' saving only.
* **P3 (space is unchanged)** `clr` / `clr_edge` unchanged within **±5 mm**,
  no held leg below 0, `tilt_end`/`t45`/`tilt_rate` unchanged.
* **P4 (no new class)** no new acquisition (`grasped=False`) row beyond the
  control's own draw, no new failure reason, no blow-up, and the landing class
  does not regress (no more `did not land` / `fell off` than C).
* **P5 (the right)** no right slide and no right placed regression, with its
  place legs also ~0.673x.

### Falsifier (registered, verbatim from the brief)

**F1: slides flat in S** -> the dwell is not the actuator either, and the class
is **stochastic given the pinch** (P73's C arm holds a 793.3 mm leg, just under
the threshold, at the same rotation schedule as its 995 mm slide). **F2: slides
rise in S** -> the class is inertial/impact, both speed directions are bad, and
the place leg's optimum is the shipped 0.35. **F3: the acquisition guard or the
landing class regresses** -> the cell spends more than it buys.

---

## 5. The decision rule

| outcome | verdict |
|---|---|
| slides fall **and** the acquisition guard is clean **and** landing does not regress **and** `clr`/`clr_edge`/rotation are unchanged | **H2 supported** — the dwell is a lever; **phase 2 is a new registration** (N = 5 interleaved, see below). Still **not adopted** in this phase |
| slides fall but the acquisition/landing class regresses | the cell is a **trade**, not a fix; not adoptable as stated |
| slides flat | **F1** — the dwell is not the actuator; the class is stochastic given the pinch; the place-leg lane closes |
| slides rise | **F2** — inertial/impact; the shipped 0.35 is the optimum; the place-leg lane closes |
| a new failure reason appears | reported verbatim; no flip either way |

**Nothing is adopted either way.** No default changes, `configs/` untouched,
**no commit**. If the result is a clean, repeatable win, the phase writes the
**phase-2 plan** instead of a flip:

* the **N = 5 interleaved batch** (seeds 77/101/202/303/404, both arms, the
  P43/WS-4.2 convention, the right arm's own read as the non-inferiority leg);
* the **reference question**: this knob is **env-only and default-off**, so the
  scripted line's `configs/motion_reference.json` **does not move** — but not
  because the knob is direct-scoped (**it is not**: the same
  `elif self._dynamic_capture_active:` branch runs on the scripted dynamic line,
  which is exactly why P44 could measure `place0 -135.4 ticks` there). The
  reference is safe because **nothing is flipped**, and this phase **verifies**
  it with one `scripts/accept.sh` run with every P74 knob unset
  (`fingerprint: matches` expected; the scripted `[fruit]` stream must be
  **byte-identical** to the P73 no-harm record `logs/p73/accept_noharm.log`);
* what adoption would **cost**: a *default* flip would reach the scripted
  dynamic line at the same read site, so it would move `place0/place1` there
  too (-135/-64 ticks on P44's own measurement) and would therefore require
  **both** motion references re-recorded from same-batch runs plus every store
  labelled; a **direct-only** flip (a `presentation == "direct"` default) costs
  the re-baseline of every direct number, and its placement cost is the class
  P44/P46 already registered (the faster place re-times which fruit is offered
  at the close, so the *acquisition* class moves) — which is why the phase-2
  gate must include the acquisition guard, not just the slide count.

`scripts/selfcheck.sh` runs at the end of the phase regardless.

---

## 6. What this cell cannot answer (registered up front)

* **A rate.** 5-8 left place legs per run, one draw; the direct loop is not
  reproducible (rendered frames, AGENTS §3b). Every count is a **branch**.
* **The tolerance direction.** If S is clean, the cell says nothing about how
  far the speed can go (0.61 is the census's `a_max`-binding ceiling at the
  shipped shape; 0.52 is the registered cell). A ladder is a phase-2 item.
* **The micro-mechanism of the escape** — the phase measures *whether the dwell
  matters*, and the schedule discriminator (§4.7) names path-fixed vs
  time-fixed, but the pinch's compliance itself is the closed
  `logs/p42/SIM_LIMIT.md` object.
* **The right's own rate** — 7-11 right place legs, and the class is 0 on this
  branch; the right is a no-new-class guard, not a second endpoint.
* **Arm invariance of the knob** — the knob is place-transit-only by code, but
  its *reach* is both arms (§1.3); a right-arm-only read is not available.
