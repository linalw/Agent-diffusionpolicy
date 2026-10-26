# P41 phase 2 — PREREG **DRAFT**: the `grip_damp02` fidelity profile, its criterion,
# and the class battery that decides whether it ships

Drafted 2026-10-26 from `logs/p41/FIDELITY_SWEEP.md` (phase 1, tree `ae0a579`).
**Draft for the Oracle-1 gate; nothing here is registered as run until the gate
returns it.** No `src/`, `configs/` or ship-default change has been made.

---

## 1. The profile

### 1.1 What phase 1 measured, in the form the profile needs

The delivered pinch on this line is **not** set by the finger drive's stiffness:

| setting | delivered pinch (`close_freeze` median) | wall |
|---|---|---|
| shipped (asset: k = 1e6, c = 100, joint2 a drive-less mimic) | **4.38 N** (22 % of the 10 N/joint cap) | 1.00x |
| asset gains authored on **both** joints (`rho_asset`) | **4.38 N** — and the run is **byte-identical** to shipped (0/102 lines) | 1.00x |
| k = 3e5, asset damping c = 100 (`rho_soft`) | 4.44 N | 1.00x |
| k = 1e3, c = 20 (the drive's own law binds: `k·err` = 4.2 N) | 4.17 N, close **slower** (29/38 ticks) | 1.00x |
| **c/k = 0.02** (the knob's own 2 %-of-k default), k = 5e4…1e6, **six 120 Hz cells** (3 grid + 3 bracket) | **9.75-9.87 N** (50 % of cap) | **1.00-1.01x** |
| `FRUIT_SUBSTEPS=4` (asset gains), 10-attempt battery of record | 9.95 N | **3.08x** (P40) |

Two conditions describe the whole corpus: the pinch is `min(k · err, plateau)`,
where the plateau is ~9.7-10.0 N once **c/k ≳ 3e-3** at 120 Hz (threshold
bracketed: c/k = 0.002 → 7.2 N, 0.0033 → 10.0 N) and is reached at 480 Hz at any
ratio. The mechanism behind the ratio is **not** identified (§6.4 of the sweep);
the collapse is measured, not assumed (`logs/p41/ratio_collapse.txt`).

### 1.2 The profile definition

**Name: `FRUIT_SIM_FIDELITY=grip_damp02`.** It pins the finger drive **and**
nothing else — the physics rate, the contact terms and the friction pair stay
exactly where they ship:

| field | value | source |
|---|---|---|
| `FRUIT_SUBSTEPS` | **1** (120 Hz, the shipped rate) | `common.py:20` |
| `FRUIT_FINGER_STIFFNESS` | **100000 N/m** (joint1 *and* joint2, as `control.py` programs them) | `control.py:170-173` |
| `FRUIT_FINGER_DAMPING` | **2000 Ns/m** — **pinned explicitly**, not left to the `2 % of k` default, because the ratio *is* the mechanism | `control.py:171` |
| `FRUIT_FINGER_COMPLIANCE` / `_CONTACT_DAMPING` | **unset** / 60 (the shipped contact material) | `scene.py:364-389` |
| `FRUIT_FINGER_MU` | 2.0 (shipped default for the OpenArm hand) | `scene.py:363` |
| `FRUIT_FINGER_FRICTION_COMBINE` | **unset** (average) | `scene.py:399` |
| maxForce | unchanged: **10 N on joint1, 0 N on joint2** — the runtime gain call does not move the caps, so the second face is nominally driven and cannot push | measured, `[effort]` banner |

The profile is **one env assignment today** (`FRUIT_FINGER_STIFFNESS`,
`FRUIT_FINGER_DAMPING`); phase 2's code work is the *named* profile plus the
manifest provenance, not a physics change. It is **not** a substeps profile: the
480 Hz lever stays separate (it costs 3.08x wall for the same ~10 N).

Why `k = 1e5` and not the asset's 1e6: at a fixed ratio 0.02 the corpus reads
9.75-9.87 N over a 20x k range, so the choice is not knife-edge; 1e5 measured the
highest median (9.87 N), is the plateau's middle, and its damping (2000 = 20x the
asset's 100) sits inside the measured family's 1000-20000 Ns/m range rather than
at either end. `k = 1e6, c = 20000` (asset stiffness,
damping only) is a measured-equivalent fourth option at 9.85 N and is the
fallback if the gate prefers "do not touch k".

### 1.3 Provenance (phase 2's `write_manifest` fields)

A store recorded under a fidelity profile must be identifiable, because the
contact forces — not the trajectory — change. Required fields, written
unconditionally by `write_manifest`:

```
physics.substeps           1
physics.dt                 0.008333333333333333
physics.finger_gains       {"joint1": {"k": 100000, "c": 2000, "maxForce": 10.0},
                            "joint2": {"k": 100000, "c": 2000, "maxForce": 0.0}}
physics.finger_contact     {"compliance": 0, "contact_damping": 60,
                            "mu": 2.0, "combine": null}
physics.profile            "grip_damp02"   (null on the shipped default)
```

`joint2`'s entry is not decoration: on the shipped tree that joint is a
**drive-less mimic** with a **0.0 N force cap**, and `set_dof_gains` now
programs its gains while the cap stays 0 — so the entry records that the second
face is nominally driven and **cannot push** (phase 1: `rho_asset`, both joints
authored at the asset's gains, is byte-identical to the shipped run). The gain
values must be the **runtime read-back** (`get_dof_gains`), not the env string:
the read-back is what reports the state the env cannot express (gains on a joint
whose cap is 0).

---

## 2. The criterion

### C1 — the mechanical gate (the force is real, free, and enough)

On the **acceptance battery at 10 attempts** (`ATTEMPTS=10 SEED=5`, the shipped
scenario), measured with `FRUIT_GRIP_EFFORT=1` in the same batch as the control:

1. **delivered force**: the median of the profile arm's `close_freeze` tactile
   sums is **≥ 8 N**, i.e. ≥ 1.8x the same-batch control's (predicted 4.3-4.5 N;
   phase 1 read 9.87 N at n = 2 — this re-measures at n ≥ 8 grabs);
2. **cost**: the profile arm's wall is **≤ 1.3x** the same-batch control's wall
   (phase 1: 1.00-1.01x; predicted 1.00x, since the physics rate does not change);
3. **worst-fruit margin**: `mu_eff(0.45) x F_median / 1.66 N >= 2x` — at
   F = 8 N this is 2.17x, at the measured 9.87 N it is 2.68x. (8 N implies the
   2x bar at the worst fruit; both are stated so the two numbers cannot drift
   apart in later documents.)
4. **honesty check**: the profile arm's freeze **jaw span** must be within 2 mm
   of the control's for the same fruit, i.e. the extra force is not extra
   penetration (phase 1: 71.5/75.7 mm vs 71.6/75.6 mm — identical).

C1 is a **fidelity** statement, not a performance one. It may pass on its own
with no class movement; see F2.

### C2 — the class gate (the point of it)

**Endpoint (primary): the left arm's carried-not-placed count on the pear
battery.** The pear battery is P39 phase 3's of record —
`HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_SUPPLY_SPECIES=pear ATTEMPTS=10 SEED=5`
— with the same-tree control run in the **same claim**, interleaved
(`C → P → C → P`), two repeats per arm.

* **PASS** = the profile's pooled left `cnp` over the two repeats is **at least
  3 below** the control's, **and** the profile is **weak-or-better in both
  repeats**
  (no repeat where it is worse), **and** the left `placed` count rises by at least
  the `cnp` fall (no relocation into `no-grasp`: the P39 trap),
  **and** the **left-attempt count is invariant within ±1** between the arms
  (P39 A1.3's evaluability rule — if the arm moves the branch, the battery is a
  **report**, not a verdict).
* **Secondary (report + guard):** the acceptance battery's left census
  (the same 10-attempt run as C1) must be **no worse** than the control's
  composite (`cnp + no-grasp`), and its `placed` must be **≥ control − 1**.
* **Gate on both batteries:** **no new failure reason** (a note string absent
  from the control's set, digit-normalised as `113_rl_report.py` does it) and
  **every descent inside the motion budgets** (`105_motion_regression.py`,
  per run).
* **Power, stated up front:** ~4-6 left attempts per 10-attempt battery, so the
  largest change one pair can show is 4-6; the pooled 2-repeat endpoint has
  ~8-12 left attempts per arm against a control `cnp` share of ~0.5-0.75. A −3
  move is the *smallest* change this design can call; **a null is a null, not a
  small effect**.

**Primary order.** The pear battery is the primary because it is species-locked
(one fruit class, one arm mix) and it is the battery on which the left cnp class
has been measured most often (`P32`/`P39`); the acceptance is the report/guard
because its outcome is a 6/10 branch with a left-attempt count that varies with
the attractor.

### The class battery (3 claims, 4 runs each, arms interleaved)

| battery | scenario | arms | reps | why |
|---|---|---|---|---|
| **pear** (primary) | `FRUIT_SUPPLY_SPECIES=pear ATTEMPTS=10 SEED=5` | C, P | 2 | species-locked left-cnp counts; the P39 protocol |
| **acceptance** (C1 + C2 guard) | `ATTEMPTS=10 SEED=5` | C, P | 2 | the shipped scenario; the force/wall/span read and the motion gate |
| **two-line** (no-harm) | `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=10 SEED=5` | C, P | 2 | the profile is a *global* finger-drive change and the two-line shares one physics tick between two arms; gated by `scripts/190_twoline_gate.sh` (its own reference, floor 0.60) |
| **same-tree control** | the **unset** profile, in the same claim, same session, interleaved | — | 2 each | instrumentation/thermal drift is part of the measurement (AGENTS §3b); no cross-session comparison |

One claim per battery (P39 A1.6); the control arm is **the same tree with the
profile unset**, never a stored log from another branch. **Two reference notes:**
(a) the pear battery pinned here is the **10-attempt** P39 phase-3 protocol, not
the `90`/`91` 18-attempt record every PREREG since P39 has called "the pear
battery" — they are two scenarios and must not be pooled; (b) the two-line
**control** arm must pass `190_twoline_gate.sh` against
`configs/motion_reference_twoline.json` (`d87c3cdf`, the post-P40 record), while
the **profile** arm's fingerprint is expected to `DIFFER` (the contact forces
move) and is therefore read against its own budgets and its same-batch control,
not against the shipped reference.

### Support reads (reported, not gated)

* `F/err` per arm (a ratio, expected ~1.3 kN/m at the plateau vs ~0.4 kN/m
  shipped) and the tact/`proj` agreement (must stay ≤ 1 % — a departure means the
  instrument, not the physics, moved);
* the freeze tick / close ticks (phase 1: 22-23 vs 25/31) and the freeze command
  (66.4/70.4 vs 62.4/66.3 mm) — the "does the close get slower or the fruit get
  pushed" columns;
* the per-leg carry band `in-hand |v|max` (the frame-free P39 §1.2 read), for
  mechanism only;
* `[stats]` sim span and s/attempt (phase 1: identical, 30.1 s at 2 attempts).

---

## 3. Falsifiers (each one alone kills the adoption)

| # | falsifier | status |
|---|---|---|
| **F1** | **No cell reaches 8 N** — the phase-1 reading (9.75-9.87 N) does not reproduce at 10 attempts / ≥ 8 grabs | live (phase 1 refuted it at n = 2 only) |
| **F2** | **The force rises but the class does not move** → **a fidelity record, not an adoption**; the profile still ships as a *documented, provenance-tagged* option but `FRUIT_SIM_FIDELITY` does **not** become the default and no reference is re-recorded for it | live, and the phase-1 sample (0/2 before and after, the same two left peaches) points this way |
| **F3** | **A new failure reason** appears in either arm (any note string absent from the control's set) | live |
| **F4** | **A motion budget fails** — any descent over its `|v|max`/lurch budget on any arm, or the two-line **control** failing `190` | live (phase 1: all cells inside) |
| **F5** | **Wall > 1.3x with no force gain** — i.e. the profile costs wall and buys nothing | live; phase 1 measured 1.00-1.01x with a 2.2x gain, so this would be a reproduction failure |
| **F6** | **Not evaluable**: the left-attempt count moves by > 1 between the arms on the pear battery (P39 A1.3) | live |
| **F7** | **Relocation**: `cnp` falls but the left `placed` does not rise by the fall (the P39 two-line trap) | live |
| **F8** | The named profile cannot be expressed without touching the physics path (i.e. it is only a hand-set env pair) — then it is a measurement, not a shippable profile | live, and it is the phase-2 code item |

**Not a falsifier, but a scope limit:** the profile says nothing about *real*
grip fidelity — P41's anchor (a real-jaw clamp-force measurement) is dropped
(no robot). "2.2x the simulated pinch" is a statement about this simulator's
grip not being the binding term, not about a physical jaw.

---

## 4. What phase 2 must not do

* **No cross-attractor success-rate deltas** (AGENTS §2): the class census is a
  count on a fixed attempt set with the branch named, never a rate comparison.
* **No re-use of a pre-P41 store or checkpoint as a like-for-like** without
  saying it is pre-profile (every store on this tree is; the manifest field of
  §1.3 is what makes a post-profile store identifiable).
* **No motion reference re-record before the verdict** — if F2 fires there is
  nothing to re-record, and `scripts/189_w7a_chain.sh` rewrites the single-arm
  reference, so it must not be run casually (P39 §10).
* **No `configs/` edit inside the measurement claims.**

---

## 5. Cost

| item | runs | wall each | total |
|---|---|---|---|
| pear battery (C, P × 2) | 4 | ~150 s (10 attempts, 120 Hz) | ~10 min |
| acceptance battery (C, P × 2) | 4 | ~150 s | ~10 min |
| two-line battery (C, P × 2) | 4 | ~90 s | ~6 min |
| C1/instrument reads | — | reuse the acceptance logs | 0 |
| offline gates (`105`, `190`, `113`-style reason census) | — | seconds | ~2 min |
| **phase-2 code** (named profile + `write_manifest` fields + a `selfcheck` pin) | — | — | review-sized |

≈ **26 min of claimed simulator time**, three claims, plus the code change and
the Oracle-2 gate.
