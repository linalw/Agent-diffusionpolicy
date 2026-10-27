# P45 phase 2 — the mass × speed battery

Measured 2026-10-27. **No commit, no `configs/` change.** The knob ships
**default off** (`FRUIT_MASS_SCALE` unset = the shipped tree), and the phase's
answer is a **mechanism** answer, not a candidate default (PREREG §7: at a fixed
size 0.25x is a 205-225 kg/m³ design density — cork — so it can never ship).

Evidence: `logs/p45/p2/*.log` (the ten battery runs, `driver_{A,B}.log`,
`batch_header.txt`), `logs/p45/p2/P2_report.txt` (the run of
`logs/p45/p2/p45_report.py`), `logs/p45/p2/run_batch.sh` + `run_arms.sh`,
`logs/p45/p2/smoke_m25.log` (a 1-attempt pre-battery smoke that proved the
banner, the read-back and the arm wiring before 25 minutes were spent on them).
Registration: `logs/p45/PREREG_DRAFT.md` §1.2/§1.3/§3/§4/§6. Census:
`logs/p45/MASS_CENSUS.md`.

Pins (every one measured-then-unchanged: the battery's own
`batch_header.txt` and the final tree agree): `fruits.py` **`dff684b1`**,
`meshes.py` **`1ad5af0e`**, `tasks.py` **`b6de439c`** (untouched),
`control.py` `9384ff4f`, `scene.py` `27e3d64a`, `rl_env.py` `93e35ef7`,
`configs/motion_reference.json` **`8a399626`** and
`..._twoline.json` **`2246f83c`** (both untouched),
`scripts/227_p45_mass_selftest.py` **`d58f9d18`**, `scripts/selfcheck.sh`
**`b60b5bc1`**, `logs/p45/p2/p45_report.py` **`fbd34cde`**. HEAD `1bae811`
(P44 amend), **working tree dirty with the knob + selftest + selfcheck leg only**.

---

## 1. The knob — `FRUIT_MASS_SCALE=<x>`, default off, a **physics change**

| | |
| --- | --- |
| resolver | `meshes.mass_scale()`, parsed **once at import** (`_parse_mass_scale`); `1`/`1.0`/unset/blank = the shipped `1.0`; `0`, a negative, `inf`, `nan` and a non-number are **hard errors at import** (a silent fallback would let a typo read as the control arm) |
| applied | `fruits.py` **exactly two sites**: `_create_fruit` (the pool build, `mass *= scale`) and `rescale` (the recycled fruit, `sample.mass *= scale` — the site that silently returns a respawned fruit to full mass if missed). Both behind `if scale != 1.0:`, so **unset skips the multiply entirely** (byte-identity by construction, not by `×1.0`) |
| inertia | **no second attribute to keep in sync**: no fruit authors `physics:diagonalInertia`, so PhysX derives the tensor from the collider's volume at the authored mass and `I` scales with it. **Measured, not asserted** — §2 |
| size | untouched: the knob is named in `meshes.py` only (one `os.environ.get`), and `assets.py` / `scene.py` / `tasks.py` do not read it. Diameter, mesh, collider, `sample.diameter`, `pinch_width` and the pad standoff are unchanged |
| build print | `[physics] FRUIT_MASS_SCALE=0.25: mass_scale=0.25 (mass x0.25 and, by PhysX's derivation, the inertia x0.25; sizes/meshes/colliders unchanged - a physics experiment, not a fidelity claim; P45)` — **unset prints nothing** |
| pinned by | `scripts/227_p45_mass_selftest.py`, a new `selfcheck.sh` leg: the resolution table, both guarded mass sites, the single env read, the untouched size paths, "inertia is derived, not authored", and the read-back's gating. `scripts/selfcheck.sh` → **PASS, 0 failures** (`logs/selfcheck.log`; the battery's own header pins `scripts/227_p45_mass_selftest.py` `d58f9d18`) |
| confound, registered | the indexed/policy close budget is mass-proportional (`tasks.py` `clip(m·g·100, 25, 60) N`, `grasp.py:223`), so the cells are **scripted-dynamic only**; no policy arm was run (PREREG §1.3) |

### The default-off proof (on the acceptance, exactly as asked)

Both batteries' **C** arms were run with the new code and every instrument on,
then diffed against their P44 same-scenario records:

* **acceptance, seed 5** — `logs/p45/p2/accept_s5_C.log` is **704/704 `[fruit]`
  lines IDENTICAL** to `logs/p44/p2/amend_F_C.log` (`diff` empty). That record is
  itself `logs/p44/p2/accept_s5_C.log` plus instrument rows with **0 core rows
  changed**, so the acceptance's shipped stream is unchanged *and* replays P44.
* **pear battery, seed 5** — `logs/p45/p2/pear_s5_C.log` is **388/388 core rows
  identical** to `logs/p44/p2/pear_s5_C.log` after excluding the instrument rows
  that the P44 run did not have (`[carry]`, `release trace:`, `release event`,
  `place trace`, `[task] release:`, `[carry]`-assist `[diag]`).
* `configs/motion_reference.json` **`8a399626`** and
  `configs/motion_reference_twoline.json` **`2246f83c`** are **untouched**
  (`batch_header.txt`), `tasks.py` stays **`b6de439c`**, and
  `scripts/189_w7a_chain.sh` was **not** run.

---

## 2. The mass/inertia read-back — census §9's named open item, now measured

`logs/p45/MASS_CENSUS.md` §1.4 said the fruit authors `mass` only, so PhysX
derives `I` from the collider volume at that mass and a mass scale *is* an
inertia scale — a **documented derivation, never measured**, because nothing ever
read the tensor back. `FruitSpawner._probe_mass_inertia` is that read: one
`get_masses`/`get_inertias` tensor call per fruit, **once**, at the rig-handle
refresh before the attempt loop, gated on the knob (so the shipped stream gets no
line and no extra call):

```
A  M50  mass=4.73-61.41 g (/ 0.5  = 9.46-122.82 g unscaled), I/m=7.967e-05-4.490e-04 m^2, I/m / (2/5)R^2 = 0.60-1.04
A  M25  mass=2.37-30.70 g (/ 0.25 = 9.46-122.82 g unscaled), I/m=7.967e-05-4.490e-04 m^2, I/m / (2/5)R^2 = 0.60-1.04
B  M50  mass=37.05-64.60 g (/ 0.5  = 74.09-129.21 g unscaled), I/m=3.255e-04-4.961e-04 m^2, I/m / (2/5)R^2 = 0.96-1.07
B  M25  mass=18.52-32.30 g (/ 0.25 = 74.09-129.21 g unscaled), I/m=3.255e-04-4.961e-04 m^2, I/m / (2/5)R^2 = 0.96-1.07
```

Three things are measured here, not inferred:

1. **The mass applied, exactly.** The authored range divides back to the
   unscaled pool range to the last digit, per battery, at 0.5x and 0.25x.
2. **`I` follows the mass exactly.** `I/m` is **identical to five significant
   figures** between the 0.5x and 0.25x arms of a battery — so the inertia
   scaled by the same factor as the mass, with no second attribute involved.
3. **The size did not move.** `I/m / (2/5)R²` is a per-fruit constant of the
   *hull's shape* (`1.00` = a sphere): **0.60-1.04** on the 8-class pool and
   **0.96-1.07** on the pear pool, and **the same interval at both scales** — the
   spread is the pear/apple/strawberry hull, not the scale. Read from physics,
   not from the config.

---

## 3. The battery

One `scripts/154_claim_run.sh` claim **per battery** (stronger than P44's
per-arm claim: no other lane can slip a simulator between two arms), arms
interleaved **C → M50 → M25 → M50S → M25S**, strictly sequential, one simulator:

| arm | env |
| --- | --- |
| **C** | *(unset)* |
| **M50** | `FRUIT_MASS_SCALE=0.5` |
| **M25** | `FRUIT_MASS_SCALE=0.25` |
| **M50S** | `FRUIT_MASS_SCALE=0.5 FRUIT_SPEED_ALL=1` |
| **M25S** | `FRUIT_MASS_SCALE=0.25 FRUIT_SPEED_ALL=1` |

Battery **A** = the acceptance (shipped scattered supply, seed 5, 10 attempts),
wall **1356 s**. Battery **B** = the species-locked pear
(`FRUIT_SUPPLY_SPECIES=pear`, seed 5, 10 attempts; `[supply] … classes=pear:16`),
wall **1395 s**. Ten runs, **254-288 s each, no wedge, no retry** (every arm
`exit=0` on its first attempt).

**Identical instrumentation on every arm** — the P44 rule, the instrument sits
inside the contrast: `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
FRUIT_CARRY_DIAG=1 FRUIT_RELEASE_DEBUG=1 FRUIT_PLACE_TRACE=1`. `PLACE_TRACE` is
the one addition to the PREREG's four, and it is **necessary**: E2's "still in
hand" restriction is read from the `place trace` `on_belt=` / `release_bottom=`
fields, which that knob produces. `CARRY_DIAG`'s neutrality on this scenario was
already measured in P44 (`amend_F_C.log` = 0 core rows changed), and the C arms
above re-prove the whole instrument set is row-additive.

---

## 4. The endpoints

Compact table (the full per-arm blocks are in `P2_report.txt`; `fling` is the
**in-hand** release peak — `place trace on_belt=True` or `release_bottom>=0`;
`F0` = carry legs whose `force_min == 0`; `esc` = legs with
`clean_slip_max > 50 mm`):

```
BATTERY A — the acceptance, seed 5
arm     mass  placed  cnp  s/att  fling_max  fling_med  n   slip_p50  esc>50   F0
C        1.0    6/10    4  15.00      0.932      0.851  6        0.1    7/20  7/20
M50      0.5    6/9     3  15.40      0.920      0.870  6        5.7    5/18  5/18
M25     0.25    4/10    6  15.30      0.887      0.786  4      228.0   12/20 13/20
M50S     0.5    5/10    5  13.40      0.897      0.780  5       25.6   10/20 10/20
M25S    0.25    5/10    5  13.50      0.872      0.801  5        1.4    9/20  9/20

BATTERY B — the pear battery, seed 5
arm     mass  placed  cnp  s/att  fling_max  fling_med  n   slip_p50  esc>50   F0
C        1.0    6/10    4  15.70      0.886      0.831  6        4.1    8/20  8/20
M50      0.5    7/10    3  15.60      0.939      0.845  7        0.1    5/20  5/20
M25     0.25    7/10    3  15.50      0.959      0.833  7        0.1    6/20  6/20
M50S     0.5    7/10    3  13.70      0.835      0.762  7        0.1    6/20  6/20
M25S    0.25    6/10    4  13.80      0.821      0.764  6        0.2    6/20  6/20
```

### E1 — `placed ≥ C − 1` per battery

**Bar = 5 in both batteries.**

* **A**: M50 **6 ≥ 5 PASS** · M25 **4 < 5 FAIL** · M50S **5 PASS** · M25S **5 PASS**.
* **B**: M50 **7**, M25 **7**, M50S **7**, M25S **6** — all **PASS**.

`cnp` (carried-not-placed, the W8-B class) is the complementary read:
**A** C 4 · M50 3 · M25 6 · M50S 5 · M25S 5; **B** C 4 · M50 3 · M25 3 · M50S 3 ·
M25S 4. No arm reaches C − 2 anywhere → **F1 fires** (§5).

The acceptance arms' class mixes differ (confound #5), so the class-standardised
read is quoted beside the count (`p45_report.py`'s `standardised_cnp`, over the
classes the arm actually attempted):

| arm | per class (attempts/cnp) | class-standardised Δcnp |
| --- | --- | --- |
| C | apple 1/0 kiwi 1/0 lychee 2/1 orange 1/1 peach 2/2 pear 1/0 strawberry 2/0 | — |
| M50 | kiwi 2/1 lychee 1/0 peach 2/2 pear 2/0 strawberry 1/0 tomato 1/0 | **−0.6 attempts** (8 common) |
| M25 | kiwi 1/0 lychee 2/2 peach 4/3 pear 1/0 strawberry 1/1 tomato 1/0 | **+3.1 attempts** (8 common) |
| M50S | apple 1/0 kiwi 1/1 lychee 1/1 orange 1/1 peach 2/2 pear 2/0 strawberry 2/0 | **+2.0 attempts** (10 common) |
| M25S | apple 2/0 lychee 2/2 orange 1/0 peach 1/1 pear 1/0 strawberry 1/0 tomato 2/2 | **+0.0 attempts** (9 common) |

Two facts survive standardisation: the **peach carries the class independent of
mass** (10 of 11 peach attempts are carried-not-placed across all five arms), and
**M25 is genuinely worse** (+3.1) while **M50 is a wash** (−0.6). Battery B has
no mix to standardise — one class, 10 attempts — and reads C 4 → M50 3 → M25 3 →
M50S 3 → M25S 4, i.e. **at most one attempt** in three of four arms.

### E2 — the fling, restricted to in-hand payloads

**Bar = C's max + 0.10 m/s** (A `1.032`, B `0.986`). C's own within-arm spread is
0.16 m/s, which is why the bar is not tighter.

* **A**: C **0.932** (n=6, median 0.851) → M50 **0.920** · M25 **0.887** ·
  M50S **0.897** · M25S **0.872**. Every arm **PASS**, every arm **below** C.
* **B**: C **0.886** (n=6, median 0.831) → M50 **0.939** · M25 **0.959** ·
  M50S **0.835** · M25S **0.821**. Every arm **PASS** (worst 0.959 vs 0.986).

Ratios to the control: **0.93-1.08x**, i.e. the fling is **mass-invariant** — the
quarter-mass arm is the *slowest* ejection on the acceptance (0.887) and the
fastest on the pear (0.959, +8 %). **F2's 1.41x is nowhere near.**

**Why the restriction matters, and the trap it caught.** The *unrestricted*
release peaks include the free-fall class — a payload lost upstream of the
release reads up to `4.5-4.8 m/s` from the place height, and M25's acceptance arm
adds a **1.418 m/s** row that the in-hand restriction removes (its `place trace`
reads `release_bottom=-184.3mm on_belt=False`: the payload was already out of the
hand, lost at `grasp_lift`'s `loss_row=123`). Unrestricted, M25 would read as
*worse* on a number that is gravity, which is exactly the failure mode
MASS_CENSUS §4.3 registered.

**Mechanism, and a correction to the census.** `v = J/m` predicts 2x at 0.5x and
4x at 0.25x *only if `J` is fixed*. The release is **displacement-controlled**
(the pads open on a commanded ramp — the census's own premise: "the pads are
kinematic and position-driven, so `∫(kδ + cδ̇)dt` is set by the ramp, not the
payload"), and under a displacement-controlled ramp `J` **scales with** `m`, so
`v` is **independent of m**. The measurement agrees with the displacement
reading (0.94-1.08x), not with the fixed-impulse reading. The census's §4.2 took
the ramp premise and then drew the fixed-impulse conclusion — the one
inconsistent step in that document; §9 of this file records it.

### E3 — the walk

Two instruments, as registered: `clean_slip_max` (the escape count is the sharp
one — W8-B separates clean legs at **0.02-1.43 mm** from escapes at
**17.9-957 mm**, with no overlap, so the 50 mm cut is unambiguous) and the
`force_min == 0` leg count (the loaded-slide signature).

* **A**: C `7/20` escapes + `7/20` F0 legs →
  **M50 5/18 + 5/18 (better on both, PASS)** ·
  **M25 12/20 + 13/20 (worse on both, FAIL)** ·
  **M50S 10/20 + 10/20 (worse on both, FAIL)** ·
  **M25S 9/20 + 9/20 (worse on both, FAIL)**.
  `clean_slip_max` p50: C **0.1 mm** · M50 5.7 · M25 **228.0** · M50S 25.6 ·
  M25S 1.4 mm; the maxima (1.2-3.8 m) are the same class everywhere.
* **B**: C `8/20` + `8/20` → every mass arm `5-6/20` + `5-6/20`,
  p50 0.1-0.2 mm. **All four arms better on both, PASS.**

So **the walk is the one channel the mass touches, and it moves the wrong way
where it moves at all**: on the mixed pool M25 raises the escape legs **7 → 12 of
20** and the zero-force legs **7 → 13 of 20** with the slip p50 going from
0.1 mm to 228 mm — a 2280x change in a quantity whose clean band is
sub-millimetre. On the single-class pear pool the same cell is *better* than a C
arm that was itself having a bad day (8/20 lost legs). The honest read is
therefore **branch- and class-dependent, never a gain**: nothing here says a
lighter fruit holds better, and the one battery with a true mix says it holds
*worse*.

### E4 — the cycle

`s/attempt`, the `[cycle]` means, and the leg-tick null.

* **`s/attempt` inside C's spread — PASS for the mass arms.** C's own per-attempt
  `[cycle] total` spans **13.91-16.46 s** (A) and **14.91-16.45 s** (B). The mass
  arms read A: M50 **15.40** (+0.36), M25 **15.30** (+0.24); B: M50 **15.60**
  (−0.11), M25 **15.50** (−0.21) — all inside C's own spread. The `[cycle]`
  blocks move the same order (`place` 3.35 → 3.49/3.76, `descent` 2.75 → 3.01/
  2.81), i.e. the geometry the mass perturbs, not a profile.
* **The S arms are faster by the cell's own amount, not by the mass:**
  A M50S **13.40**, M25S **13.50**; B M50S **13.70**, M25S **13.80** — against
  P44's `S13` alone on the same scenario (`logs/p44/p2/accept_s5_S13.log`
  **13.5 s/attempt**, pear `pear_s5_S13.log` **13.8 s**). **The mass adds 0.0-0.1 s
  of the 1.5-1.6 s**; the saving is the P44 speed cell's (P44 measured −1.45 s).
* **The exact leg-tick null FAILS as registered — 0 of 44 matched attempts carry
  an identical leg-tick tuple** (A: 0/5 M50, 0/4 M25, 0/1 M50S, 0/1 M25S;
  B: 0/9, 0/8, 0/8, 0/8). **The inference "a moved tick count ⇒ an implementation
  defect" is refuted by the data**: a leg's tick count is a function of its own
  carried **distance** as well as its profile, and the mass moves where the fruit
  is picked by 1-3 cm. Measured on `place0` (the leg with enough spread to fit a
  slope): **C 7.0 ticks/cm, M50 7.0 ticks/cm** (C 51 cm→333 t, 61 cm→403 t;
  M50 50 cm→328 t, 58 cm→384 t) — the same profile, a shorter leg. Sample pairs
  follow the slope exactly: attempt 1 C 51 cm/333 t vs M50 50 cm/**328 t**;
  attempt 2 C 59 cm/390 t vs M50 60 cm/**392 t**.
* **The implementation-defect test that does hold, and it passes:** every leg's
  **commanded speed ceiling** is unchanged on the mass arms — `grasp_lift`
  0.292-0.294, `place0` 0.342-0.343, `place1` 0.343 (identical to C within
  5 mm/s on all three legs, both batteries), while the **S arms move exactly the
  cell's amounts**: `grasp_lift` **+0.059** (0.30 → 0.36), `place0`/`place1`
  **+0.165/+0.166** (0.35 → 0.52). No mass value reaches a control path; the
  P44 cells do, and only where registered.

### E5 — the guard

**PASS.** `fruit did not follow the gripper` **0** in all ten arms, every attempt
row reads `notes=[]`, and no new reason appears in any arm. The one line-manager
counter that does move is the reject chute (`diverted`): A C 0 · M50 0 · **M25
2** · M50S 1 · M25S 1; B C 0 · M50 0 · M25 0 · M50S 0 · M25S 1. It is a
consequence of repeated attempts on one fruit, not a per-attempt failure reason,
and it is quoted rather than hidden.

---

## 5. The falsifiers

| # | registered | measured |
| --- | --- | --- |
| **F1** the class does not move (`cnp` not down ≥ 2 on any battery) | **FIRES** — the largest reduction anywhere is **1** (pear −1 in three of four arms; acceptance M50 −0.6 class-standardised), and the acceptance's M25 is **+3.1** |
| **F2** the fling rises ≥ 1.41x | **does not fire** — max **1.08x** (pear M25), min 0.93x; the quarter-mass arm is the *lowest* on the acceptance |
| **F3** nothing changes at all | **does not fire** — placed, the walk and the leg tick counts all move |
| **F4** the crossed cell is worse than S alone on `placed` | **not adjudicable** — the battery's registered arm list (5 arms) omits the S-alone cell; P44's `S13` alone reads 6/10 at 13.5 s on the same scenario vs M50S 5/10 at 13.40 and M25S 5/10 at 13.50: **one attempt on a moved attractor**, which AGENTS §2 forbids reading as a delta |
| **F5** a new failure reason | **does not fire** |

The PREREG's pre-registered expectation was "F1 and F2 both fire". **Half of it
did**: F1 fires, F2 does not, and the reason F2 does not is itself the useful
result (§4 E2: the release is displacement-controlled, so `v` is mass-invariant).

---

## 6. The owner's question

**A lighter fruit does not let the cell go fast — it makes the walk worse and
leaves the fling alone.** The speed is entirely the P44 cells' (`s/attempt`
15.0 → 13.4-13.5 with `FRUIT_SPEED_ALL`, the same 15.0 → 13.5 P44 measured with
no mass change; the mass contributes 0.0-0.1 s of it), and the mass cells buy
**nothing on the placed count** (acceptance C 6, M50 6/9, M25 **4/10**, M50S 5,
M25S 5; pear C 6, M50 7, M25 7, M50S 7, M25S 6 — and on the pear, the
composition-free battery, the class-standardised `cnp` gain is exactly **one
attempt**, i.e. F1's null). The **fling does not get worse**, which is the one
prediction the census got the mechanism wrong on: the in-hand release peak is
**0.93-1.08x** of the control at 0.25x mass (acceptance M25 0.887 vs C 0.932,
pear M25 0.959 vs C 0.886), because the release is a **displacement-controlled
pad ramp** — the exit speed is set by the pad face motion and the 47-68 mm
placement drop, not by a fixed impulse, so `v = J/m` never applies here. What
*does* get worse is the **walk**, and only on the mixed pool: at 0.25x the
acceptance's escape legs go **7/20 → 12/20**, the zero-force (loaded-slide) legs
**7/20 → 13/20**, and `clean_slip_max` p50 **0.1 mm → 228 mm** — the loaded-slide
class is not mass-starved (it holds 4-5 N on one face while the payload walks),
so taking mass away does not give the grip more to hold, it gives the contact
less to resist; on the single-class pear the same cell reads *better* than a C
arm that lost 8/20 legs, which is the branch, not the mass. **Verdict: the mass
term is not the term the faster cells lose, and the record on "make the fruit
lighter" closes negative on the class and neutral on the fling** (the exact
opposite of the hoped-for mechanism, and the reason the fix is geometry — a
smaller *real* fruit is a new scenario with new pinch spans, `MASS_CENSUS` §5 —
not a density change).

---

## 7. What this does not claim

* **No rate.** A scripted configuration is one draw of a deterministic branch;
  the `placed` counts are **that battery's count** (AGENTS §2). No
  cross-attractor delta is read anywhere.
* **No adoption, and none possible.** `FRUIT_MASS_SCALE` is default **off** and
  PREREG §7 registers now that a fixed-size mass scale can never be a shipped
  default (0.25x = 205-225 kg/m³, or a 1.93 mm rind). The deliverable is the
  mechanism answer.
* **No inertia *measurement of the tensor's consistency*** beyond `I/m`: the
  readback confirms `I ∝ m` and `I/m` is the hull's shape constant; it does not
  cross-check PhysX's tensor against a hand-computed one (the census's §1.4
  arithmetic is the reference).
* **No two-line, policy, hybrid or direct arm.** The indexed/policy close budget
  is mass-proportional, so a policy arm of the same experiment would move the
  grip — a different registration (PREREG §1.3).
* **No claim that the pear battery's C is a fair control.** Its C arm lost 8/20
  carry legs, which is a bad draw; the pear arms are 5-6/20. That asymmetry is
  reported as measured, and it is why the pear's "better than C" is *not* read as
  an improvement.
* **No `configs/` write and no reference re-record** — a mass change moves every
  carry leg by construction, so the moved arms are gated on budgets and per-leg
  reads, never on a fingerprint (PREREG §1.3).
* **No commit.** The knob, its selftest and its `selfcheck.sh` leg are
  uncommitted working-tree changes; phase 3 owns the commit and the docs.
