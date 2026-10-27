# P45 PREREG (draft) — the mass × speed battery

**Status: DRAFT for Oracle gate 1. Not yet registered; nothing has been edited or
run.** Registered-against tree: HEAD `1bae811` (P44 amend), clean working tree,
`fruits.py` `6f65e423`, `meshes.py` `41efc522`, `tasks.py` `b6de439c`,
`control.py` `9384ff4f`, `grasp.py` `6417e1d2`; refs `8a399626` / `2246f83c`.

Evidence: `logs/p45/MASS_CENSUS.md` (+ `mass_census.py`, `MASS_CENSUS_out.txt`),
`.slim/deepwork/p45-mass-and-frontier.md`, `logs/p44/CAP_CENSUS.md`,
`logs/p44/P2_RESULTS.md` §9, `logs/p9/FRICTION_AUDIT.md`,
`logs/w8/B_RESULTS.md`, `logs/p42/SEAT_CENSUS.md`, `logs/p21/RELEASE_DESIGN.md`.

---

## 0. What the census changed (this section is the reason to read the rest)

The owner's hypothesis: the faster cells fling the fruit because the fruit is
heavy; scale the mass down and the speed becomes safe.

The census says the premise is **half inverted**, and that both halves must be
measured:

| term | what a 0.25x mass does | is it the class? |
| --- | --- | --- |
| the **translational slip ratio** `r = m|a+g|/(mu·N)` | **improves 4x** (0.370 → 0.093) — `N` is grip-set, `mu·N` is a constant in `m`, so `r ∝ m` | **no** — `logs/p9` measures escapes at 0.10-0.78 (med 0.36) against held legs at 0.37: the ratio **does not separate** the classes |
| the **fling** `v = J/m` | **worsens 2x-4x** (2.67-5.34 m/s on the anchor impulse) | **yes** — the ejection *is* an impulse, and the pool's lightest fruit owns the corpus's worst ejection (1.34 m/s) |
| the **roll-out** `alpha = 2.5·mu·N/(m R)` | **worsens 2x-4x** | plausibly — `logs/p9` §5.2 names the rotational mode as the residual and says a force-cone test cannot capture it |
| the **timing** | **cannot move** — every leg is tick-clocked by its profile, not by inertia | n/a |

So the registered prediction is **negative on the class and positive on the
harm**: a lighter fruit should leave the carry class where it is, and make any
ejection worse. The battery exists to convert that from an argument into a
measurement, and to say **which term the faster cells actually touch**.

> **The one sentence this phase must not get wrong.** "Mass-independent" is the
> *weight-set* case (`N = m g / mu`, the textbook model, and what
> `motion.accel_budget` assumes). This cell's `N` is **grip-set** — a finger-drive
> preload of 9.75-9.9 N (`control.py:63-64, :86-103, :234-236`) against a close
> depth from geometry (`tasks.py:9768-9771`) — so `r` is **proportional to m**.
> Verified four ways in `MASS_CENSUS.md` §3.1.

---

## 1. The item

### 1.1 The knob

**`FRUIT_MASS_SCALE=<x>`** — a new, **default-off** env knob. `1.0` (and unset)
= the shipped tree.

* **Resolver**: `mass_scale()` in `src/fruit_sorting/meshes.py`, beside
  `fruit_density` (`meshes.py:399-410`), reading `FRUIT_MASS_SCALE` **once at
  import** like the P12-A switches (`meshes.py:355-358`), returning `1.0` when
  unset. A value `<= 0` is a hard error at import (a zero-mass body is not a
  scenario).
* **Applied at exactly two sites**, both in `fruits.py`:
  `:977` (create) and `:1039` (`rescale`, the recycled fruit — **the site that is
  easy to miss**: a respawned fruit would silently return to full mass and every
  later attempt in a shard would be a different experiment).
* **Unset skips the multiply entirely** (`if scale != 1.0:`), so the shipped
  float path is byte-identical by construction rather than by `×1.0`.
* **The inertia needs no code**: no fruit authors `physics:diagonalInertia`
  (`fruits.py:980-981`, `:1063` — mass only; grep confirms the only
  `diagonalInertia` prims in the tree are the OpenARM links), so PhysX derives
  the tensor from the collider's volume at the authored mass and `I` scales with
  it **exactly**. The site comment must say so, or the next reader will look for
  a second attribute.
* **The size does not move.** No change to `fruit_dimensions`, the mesh, the
  collider, `sample.diameter`, `pinch_width` or `PAD_LIFT`. That is the whole
  experiment: the mass is the only variable. A size change would move the pinch
  span and therefore the geometry the class lives in (`MASS_CENSUS.md` §5).
* **One banner when set** (`[physics] mass x0.25 (sizes unchanged)`), so a log
  names its physics — the P41 lesson. Unset prints nothing (byte-identity).
* **A selfcheck leg** (`scripts/227_p45_mass_selftest.py`): unset = no multiply;
  the resolution table; both mass sites pinned by AST; no other module reads the
  knob; and the "inertia is derived, not authored" property asserted against
  `fruits.py`.

### 1.2 The cells

`S` below is the P44 union, `FRUIT_SPEED_ALL=1` (place 0.52 / lift 0.36 / release
1). It is used as the *speed* arm because it is the only cell that passed P44's
E4 guard; it is **not adopted** and stays default off.

| arm | env | what it answers |
| --- | --- | --- |
| **C** | *(unset)* | the same-tree control; must replay the P44 C stream |
| **M50** | `FRUIT_MASS_SCALE=0.5` | half mass, shipped speed |
| **M25** | `FRUIT_MASS_SCALE=0.25` | quarter mass, shipped speed |
| **S** | `FRUIT_SPEED_ALL=1` | the speed cell alone (P44's pass-E4 arm) |
| **M50S** | `FRUIT_MASS_SCALE=0.5 FRUIT_SPEED_ALL=1` | does half mass make the speed cell safe? |
| **M25S** | `FRUIT_MASS_SCALE=0.25 FRUIT_SPEED_ALL=1` | the strongest form of the hypothesis |

Instrumentation on **every** arm, identical (the P44 rule: the instrument sits
inside the contrast): `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
FRUIT_RELEASE_DEBUG=1 FRUIT_CARRY_DIAG=1`. The first three are proven
row-neutral on these scenarios (`logs/p44/P2_RESULTS.md` §9); `CARRY_DIAG` was
proven run-neutral there too (`amend_*`: 83/81/83 core rows identical). If a
cheaper first pass is wanted, drop `CARRY_DIAG` from the *timing* arms and keep
it on the *walk* arms — but then do not compare `clean_slip` across them.

### 1.3 What is *not* run

* **No policy / hybrid / direct arm.** The indexed and policy close budgets are
  **mass-proportional** (`clip(m·g·100, 25, 60) N` at `tasks.py:11003` and
  `grasp.py:223`; `clip(m·g·60, 20, 40) N` at `tasks.py:11029`), so the knob
  would silently move the *grip* on that path. The scripted dynamic line has no
  mass term in its control path, which is why this experiment is clean there and
  only there.
* **No two-line battery.** The two-line's scheduler and its park/clearance
  behaviour are a different scenario; if the mass ever matters it must get its
  own reference (`scripts/190_twoline_gate.sh`) and its own registration.
* **No collection, no store, no checkpoint.** A store recorded under a mass
  scale is a different physics and its manifest must say so: if a collection is
  ever run, the P41 `physics` block (`scene.finger_physics_provenance`) gains a
  `mass_scale` field **first**, and the two-line/W8-A rule applies — a
  park/no-park-style store must not be mixed with a mass-scaled one.
* **No `configs/` write.** A mass change moves every carry leg's `|v|max` and
  cone, so the fingerprint **differs by construction**: the moved arms are gated
  on the budgets and the per-leg reads, never on a reference, and **no reference
  is re-recorded from this battery.**

---

## 2. Batteries

The P44 grid, same command shape (`logs/p44/p2/run_batch.sh`), interleaved
inside one claim per battery, strictly sequential (one simulator):

| battery | scenario | seeds |
| --- | --- | --- |
| **A** | the acceptance (shipped scattered supply), 10 attempts | **5** |
| **B** | the acceptance, 10 attempts | **6** |
| **C** | the species-locked pear (`FRUIT_SUPPLY_SPECIES=pear`), 10 attempts | 5 |

One `scripts/154_claim_run.sh` claim per run; `HEADLESS=1 ATTEMPTS=10
FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 SEED=<n>`. Battery **C** exists
because the pear is the branch P44's own seed-6 E2 fail was *not* about, and
because it is the one class where the acceptance and the pear disagree on the
control arm.

---

## 3. Endpoints

| # | endpoint | pass | fail |
| --- | --- | --- | --- |
| **E1** | **`placed`** per battery | **≥ C − 1** in every battery (the P44 E2 rule) | a fall of ≥ 2 |
| **E2** | **the fling**: the release payload's **peak \|v\| on payloads still in the hand at the release** (`FRUIT_RELEASE_DEBUG=1` `release trace:` row, restricted to attempts whose `place trace` reads `on_belt=True` / `release_bottom ≥ 0`); the endpoint is the arm's **max and median** of those peaks, arm-vs-control per battery | **max not above C + 0.10 m/s** | **≥ 1.41x C** (§4 F2) |
| **E3** | **the walk**: `clean_slip` on carried legs, arm-vs-control (`FRUIT_CARRY_DIAG=1`), plus the `force_min == 0` leg count | not worse than C | worse than C on **both** instruments |
| **E4** | **the cycle**: `s/attempt`, the `[cycle]` block means, **and every leg's tick count** | `s/attempt` within C's branch spread **and every leg tick count identical to C** | **any** leg tick count moves (it is exact — §4 F3) |
| **E5** | the guard + reasons | no new `fruit did not follow the gripper` row and no new failure reason | either |

Two notes that decide how E2 and E4 are read:

* **E2 must be restricted to in-hand payloads.** On the P44 C arm the release
  trace reads **0.771-0.932 m/s** on the **6 placed attempts**, **~0.12 m/s** on
  the 2 whose payload never moved (an acquisition miss, `events=0`), and
  **4.78/4.81 m/s** on the 2 that were already lost — the latter is free fall
  from the place height, not an ejection. An unrestricted peak would let a cell
  that *converts* losses read as an improvement. The comparison is therefore
  **per-arm max (and median) of the in-hand peaks**: pass = the arm's max not
  above C's max **+ 0.10 m/s** (C's own within-arm spread is 0.16 m/s, so a
  tighter bar would fail the control).
* **E4 is an exact null, not a tolerance.** The profiles are pure kinematics
  (`logs/p44/CAP_CENSUS.md` rule 1 reproduces every leg to ±1.4 % from its cap),
  so a mass change **cannot** move a leg's duration. A moved tick count means the
  mass reached a control path — the finding would be an implementation defect,
  not a physics result.

---

## 4. Falsifiers

Registered **before any run**. Each one names what it would mean.

* **F1 — the class does not move.** `cnp` (carried-not-placed) is not reduced by
  ≥ 2 on **any** battery, in the mass arms or the crossed arms.
  → **the mass is not the term.** The carry class is the contact-state/geometry
  path (`logs/p9`, `logs/p42/SIM_LIMIT.md`) and the speed cells' losses are not
  inertial. The honest close: report the null, keep the mass knob default off and
  out of the model, and the named next spend reverts to the P44 list (S3-v/S1
  clean cells, the two-line union) plus the acquisition class (W7-B).
* **F2 — it worsens the fling.** At 0.25x the in-hand release peak rises
  **≥ 1.41x** the control's (the `v ∝ 1/√m` energy-limited floor; the impulse
  limit is 2x, `MASS_CENSUS.md` §4.2).
  → **the mass cut is a physics cheat that buys nothing and costs ejection.** It
  would also *confirm* the mechanism (the ejection is `J/m`), which is the useful
  half. Any future "make it lighter" argument is then closed on the record.
* **F3 — it changes nothing at all.** The fling, the walk, the placed counts and
  every leg tick count are identical to C.
  → **the mass is not in this rig at all** (the knob did not apply, the
  derived inertia defeated it, or the contact never sees the payload's mass).
  This is an *implementation* finding first: check the banner, the build line's
  mass, and one `get_mass` readback before reading it as physics.
* **F4 — the crossed cell is worse than S alone on `placed`.** Mass and speed
  interact adversely (a lighter fruit + a faster release = more ejection).
  → the mass is not a speed *enabler* even where the class is untouched, and the
  owner's hypothesis is answered "no" in the only direction that mattered.
* **F5 — a new failure reason** (the P44 E6 rule; `113_rl_report.py`
  digit-normalises notes, so any new note is a new reason).

**Pre-registered expectation (for the record, not a gate):** F1 and F2 both fire;
E1/E3/E4 hold. If that is what happens, the phase's answer is "a lighter fruit
improves a margin that was never binding and worsens the two channels that are".

---

## 5. N, cost, and the staged design

* **Stage 1 — does the mass act at all?** Battery **A** only, arms
  `{C, M50, M25, S, M50S}` = 5 runs ≈ **25-30 min** of simulator (P44: ~5 min per
  10-attempt run), one claim each. Stage 1 is sufficient to answer the owner's
  question if it draws F2 or F3 or a clean E4 null.
* **Stage 2 — the grid.** Battery **A** `{M25S}` + battery **B** `{C, M50, M25,
  S, M50S, M25S}` + battery **C** `{C, M25, M25S}` ≈ 12 runs → **≈ 60-70 min**.
  Run it only for the arms that fired **no** falsifier in stage 1 (the P44 rule:
  a cell that fires a falsifier is stopped, not carried on) — and always with its
  own control on the same battery.
* **N**: the scripted line is deterministic per configuration per mode, so a
  same-configuration repeat is a determinism check, not a variance estimate. The
  *cells* are therefore one draw each; the 2 acceptance seeds + the pear exist to
  catch a branch that swings, exactly as in P44.
* **What may be claimed**: the per-leg tick deltas (exact), the per-block cycle
  times, the in-hand release peak per attempt, `clean_slip` per leg, and the
  `placed` count **per battery as that battery's count** — never a
  cross-attractor rate (AGENTS §2), and never "the mass fixed/worsened the grip"
  without the class split (`logs/p44/P2_RESULTS.md` §5: the note is a *closure*
  test, not a slip test).

---

## 6. Confounds register (each one is a way to fool ourselves)

1. **`FRUIT_PHYSICS_REAL_MASS` must be unset in every arm.** It is a *different*
   mass table (9.4-147.3 g, +36 % on the strawberry, −1 % on the apple) and would
   change what "0.25x" means. It is also the wrong direction (heavier).
2. **The size must not move.** Verify from the log: the build line's mass and one
   `[supply]`/`[task] target <fruit> (grade, d cm)` diameter per arm. If a cell
   shows a different diameter distribution, the arm is a size experiment.
3. **The indexed/policy close budget is mass-proportional** (§1.3) — the cells are
   scripted-dynamic-only, and a policy arm needs its own registration.
4. **The release metric must be restricted to in-hand payloads** (§3, note 1).
5. **The `[bed]`/`[supply]` census rows and the light-vs-heavy class mix.** The
   pool's mass range is 1:16 inside one scenario (8.0 vs 132.5 g), and the
   selection is grade-then-position, so the *class mix per arm* can differ simply
   because the branch differs. Any per-class read must be standardised (the
   P1/P2 `200_composition_audit.py` lesson) or reported as counts.
6. **A mass change moves the belt transport's own noise floor.** The transport is
   frictional (the ratio is mass-independent) but a lighter fruit responds more to
   depenetration kicks and cleat contacts, so the delivered positions at the
   station can drift. Register the selection sequence (fruit classes selected in
   order) beside every placed count, so a changed selection is visible.
7. **No reference re-record, no `configs/` write, no commit in phase 2** beyond the
   knob + its selfcheck leg. `scripts/189_w7a_chain.sh` is **not** run.

---

## 7. Adoption rule

A fixed-size mass scale is **not a candidate default**: 0.25x is 205-225 kg/m³
(cork) and, read as a hollow shell, a 1.93 mm rind (`MASS_CENSUS.md` §5). So:

* **the mass cells can never be adopted as shipped defaults**, whatever their
  numbers, and this is registered now so a good-looking result cannot be read as
  an adoption candidate later;
* the phase's deliverable is the **mechanism answer** — *does the mass term touch
  the class the speed cells lose? yes/no* — plus a closed record on "make the
  fruit lighter";
* the only physical version of a "lighter fruit" is a **smaller fruit**, which is
  a **new scenario** (new pinch spans, new supply, new recollection, its own
  references), owner-gated, and out of scope here.

## 8. Gate-1 question for the Oracle

Is the census's **premise correction** (grip-set `N` ⇒ `r ∝ m`, so a lighter
fruit *does* buy ratio — but the ratio is the non-discriminative quantity)
accepted as the framing, and is the **restricted fling endpoint** (§3 E2) the
right instrument rather than the release block's unrestricted peak?
