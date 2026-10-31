# P78 pre-registration — a **site-scoped** clamp force (left `place*` legs) and its dose

**Pinned before any run.** Nothing is adopted, no default changes, `configs/*` is not
touched. Written after `logs/p77/RESULTS.md` and before the first simulator run of this
phase; the md5 of this file is in `PREREG.md5`.

## 0. Why this phase exists

P77 measured the owner-chosen 60 N cell: **left placed 11/21 -> 17/20** (Fisher
**p = 0.043**, 3/3 seeds, class-standardised 0.524 -> 0.927, left `cnp` 7 -> 3, right not
worse, cycle -0.5 %). It also measured the price of the *global* form: the cap is a
per-joint drive property written at build time on **both arms of every presentation**, so
a flip moves the scripted acceptance at **attempt 0** (`fingerprint: DIFFERS`, 378 vs 346
`[fruit]` lines), moves the two-line (`190` FAIL on the fingerprint alone), and therefore
owes **both motion references, a scripted re-baseline and every store's provenance**.

And P77 §2 measured the class's **site**: every escape and every pry, in both arms, is a
**left `place0`** leg (C 7/38 escaped, 4/38 pried; T 3/40 and 1/40; **right 0 and 0 on
43/45 legs**). A site, not a whole-cell property. So the question this phase asks is
mechanical: **can the clamp be raised for one arm's place legs only, and does the dose
behave the same way there?**

## 1. Step 1 — feasibility of a **runtime** cap write (a stop condition, not a result)

The build-time writer is `scene.apply_finger_maxforce`, whose own docstring states the
constraint: it runs **before** `start()` creates the `Articulation`, "writing the USD
after the articulation view exists would be inert (only `set_dof_gains` /
`set_dof_max_efforts` act on a live view)".

* Static read (done before this file was pinned): `Articulation.set_dof_max_efforts`
  (`isaacsim.core.experimental.prims`) has a **tensor-backend** branch that calls
  `view.set_dof_max_forces`, which writes the **live** model's `joint_effort_limit` and
  then `notify_model_changed(JOINT_DOF_PROPERTIES)` — i.e. a runtime mutator, not a USD
  authoring call. `PickAndPlaceTask.arms[side].robot` **is** that `Articulation`
  (`scene.py: robot = Articulation("/World/OpenArm")`), and this build runs the tensor
  backend with PhysX (`scene.start`: `set_backend("torch")`,
  `switch_physics_engine("physx")`).
* **Empirical criteria** (a 2-pick smoke, `logs/p78/smoke_60.log`), all three required:
  1. the per-leg `[drive]` row's **read-back** equals the requested cap while the leg
     runs, and equals the shipped `10.00` after it;
  2. the leg's **delivered** `force_min` on a `place*` leg is in P76/P77's **85-99 %** of
     the requested cap band, i.e. the *physics* moved, not just the attribute;
  3. a `grasp_lift` leg in the *same* run reads ~**9.7 N** — the shipped cap — which is
     the site-scoping proof (the lift keeps the shipped grip, so the pick does not move).
* **If (1) or (2) fails the phase stops** and reports that the only form is the global
  one, whose price P77 §7 already measured. If (1) holds and (2) fails, the write is
  attribute-only (inert) and the same conclusion follows. **F1/F2** below.

## 2. Step 2 — the knob, and its resolution table (strict, P44/P45/P52/P53 precedent)

```
FRUIT_FINGER_MAXFORCE_SCOPE   unset/empty = off | "place-left" = the scoped form
FRUIT_FINGER_MAXFORCE_SCOPED  the scoped cap in N (default 60.0), strict parse, > 0
FRUIT_FINGER_MAXFORCE         the existing GLOBAL knob: an explicit non-empty value
                              WINS, and the scope then resolves to None
```

| presentation | `..._SCOPE` | `FRUIT_FINGER_MAXFORCE` | resolved |
|---|---|---|---|
| any but `direct` | anything | anything | `None` (the shipped `PickAndPlaceTask(finger_cap_scope=None)` path, no write, no read) |
| `direct` | unset/empty | any | `None` |
| `direct` | `place-left` | **set** | `None` (+ a named note: the global path wins) |
| `direct` | `place-left` | unset/empty | `{"left": <cap>}` |
| `direct` | anything else | — | **raises** (a typo must not read as a null) |

Scope of the write: **`left` only**, **`place*` legs only**, applied by a pure resolver
`tasks.finger_cap_scope_for(scopes, side, name)` at the leg's start, and **restored to
the cap the leg found** in a `finally` (a `_carry` wrapper around the leg body), so an
exception cannot leave the cap raised. `grasp_lift` is never in scope, so the **pick** is
always taken at the shipped 10 N — the P77 P1 difference at attempt 0 was a *grasp*
difference (`lift=+0.411 m / 60.05 N` vs `+0.138 m / 9.98 N`), and it cannot occur here.

`direct`-scoping is a **design decision of this registration**, not an accident: the
phase's deliverable is a direct-line win with **zero blast radius**, and every direct-only
knob on this tree (P43 park, P54 ACQ, P58 supply profile, P66 lift) is scoped the same
way. The scripted line, the collector, the two-line scheduler and the hybrid canary
**never construct `SortingRLEnv`**, so they never resolve this knob at all — the blast-
radius measurement of §4 exists to prove that (it is an import/structure guard, stated as
such, plus the in-log proof that the write is real on the direct line).

## 3. Step 3 — the dose ladder (direct line, seed 77 first)

Four cells, the P66-phase-3 / P71-phase-2 / P73 / P74 / P75 / P76 / P77 scenario
**verbatim**, `moe_v13s` `61da390a`, 15 picks each, one claim each, in one stretch,
interleaved by dose ascending so the control is read first and adjacent:

| arm | env | cap on left `place*` |
|---|---|---|
| **C** | `FRUIT_FINGER_MAXFORCE_SCOPE=` (explicit empty) | 10 N (the shipped asset cap) |
| **S30** | `..._SCOPE=place-left FRUIT_FINGER_MAXFORCE_SCOPED=30` | 30 N |
| **S45** | idem `=45` | 45 N |
| **S60** | idem `=60` | 60 N |

Endpoints per cell (all read off the `[carry]` rows, `FRUIT_CARRY_DIAG=1` +
`FRUIT_MOTION_REPORT=1`): **left placed / `cnp` / never-held**; **escape**
(`clean_slip_max > 100 mm` with a pinch, P74's mechanism count); **pry**
(`sep_max >= 95 mm` of the 98.1 mm stop); **the mode split** `sep_max - dia`
(P77's radial-vs-axial discriminator: `>= +13 mm` radial, `<= +10 mm` axial);
**the strawberry legs** (the binding class) with the crush guards
(`sep@loss - dia <= -15 mm`, `force_min >= 35 N` on an escape); **the right** (placed,
escapes, new reasons); **cycle ticks**. Also per leg *name*: `force_min` on `place*`
(the manipulation check's behavioural leg) and on `grasp_lift` (must stay ~9.7 N).

**A rung dominates** iff, against C in the same batch:

```
D1  left placed        S >= C                      (the count is not lost)
D2  left escapes       S * 3 <= C    AND  pried S * 3 <= C   (P77's M1/M2 bar)
D3  crush guard        zero legs on S
D4  right              placed S >= C - 1 and no new right reason
D5  cycle              median ticks S <= C * 1.05
```

D6 is a **descriptor, not a gate**: the `sep_max - dia` split on S's escape legs (P77's
T was 2 axial + 1 radial; a rung that is axial-only is the same residuum, not a new
class). **A 15-pick single seed is one draw of a non-reproducible branch** (P74's lesson:
a single seed produced a 15-point false positive; P77 §1's replay check: 2/15 episodes
identical on a same-configuration re-run) — so the ladder's counts are a **screen** and
its *mechanism* rows are the claim. Seeds 101/202 are run **only** for the rung that
satisfies D1-D5, plus C; if more than one rung passes, the **lowest passing rung** is the
economical dose (P66's `0.24` precedent) unless a higher rung's escape count is strictly
lower **and** its pry count is not worse. If no rung passes, **no seed is added** and the
phase reports a negative ladder.

## 4. Step 4 — the blast-radius proof (the phase's main deliverable)

With the scope **armed** (`FRUIT_FINGER_MAXFORCE_SCOPE=place-left
FRUIT_FINGER_MAXFORCE_SCOPED=60`) on the *same tree*:

```
B1  scripted acceptance   scripts/accept.sh  ->  the 346 [fruit] lines md5 d0079a23
                          (== logs/p76/accept_noharm_full.log) and "fingerprint: matches"
B2  two-line             FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1, ATTEMPTS=10 ->
                          scripts/190_twoline_gate.sh PASS against eb697f23
B3  configs/             every md5 unchanged (motion_reference.json 8a399626,
                          ..._twoline.json eb697f23)
B4  resolution table     the new selftest leg pins §2's table, the restore, and that
                          exactly one `_carry` call site and one write site exist
```

**If B1 or B2 fails the form is not shippable** and the phase reports that (the write
leaked, or `direct`-scoping is not enough). B1's byte-identity is an **import guard** on
this change and is stated as one (the scripted line never constructs `SortingRLEnv`); the
*substantive* proof that the write is real and leg-scoped is the direct line's own
manipulation check (§3's `force_min` by leg name).

## 5. Falsifiers (a fired falsifier is a finding, not a failure to hide)

```
F1  the live read-back does not follow the write            -> stop; only the global form
F2  the read-back follows but `place*` force_min stays      -> stop; the write is inert in
    at the shipped ~9.7 N                                      physics; global form only
F3  B1 or B2 moves (a stream line, or the fingerprint)      -> not shippable
F4  a restore row reads != 10.00, or a `grasp_lift` leg in  -> not shippable (the cap
    a scoped run reads force_min > 15 N                        leaks out of the site)
F5  a rung's left placed falls below C's                    -> that rung is refused even if
                                                               its escapes fall
```

## 6. What this phase will and will not claim

It **may** claim: a runtime per-leg cap write works (with the read-back and the delivered
force); the scoped form's dose response; and that the scoped form moves no reference (B1-B3).
It **may not** claim: a rate (one seed's count is a draw), a shippability decision (owner),
or anything about fruit quality — the P77 honesty frame stands unchanged: **this
simulator has no bruise, damage or flesh-compliance model**, so a clean read is about
**geometry and retention**.
