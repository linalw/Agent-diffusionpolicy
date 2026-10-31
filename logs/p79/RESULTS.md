# P79 results — the pick half of the clamp: the site proof is exact, the lift's pinch
# converts the *leg state* and not the count, and neither scoped 60 N arm reproduces
# P77's win

**Nothing adopted, no default changed, no commit, `configs/*` untouched.** One
registration (`PREREG.md`, md5 **`0cdfd227`**, pinned before the first cell) plus one
recorded deviation (`A1`, appended after the run; the amended file is `afde5127`).
Direct line, `moe_v13s` `61da390a`, the P66-phase-3 / P71-phase-2 / P73 / P74 / P75 /
P76 / P77 / P78 cell verbatim, 15 picks per cell, one claim each, seeds 77/101/202,
arms interleaved within a seed.

---

## 0. Verdict

| question | answer |
|---|---|
| **can the cap be scoped to the pick's own leg, and does it take effect?** | **Yes, and the site proof is exact.** `FRUIT_FINGER_MAXFORCE_SCOPE=grasp-left` arms a runtime cap on the left arm's single `grasp_lift` leg through P78's machinery unchanged. In-run: one `[drive] left grasp_lift finger cap raise/restore` pair per left lift leg (**7/7, 6/6, 6/6, 3/3, 2/2, 8/8** across the six armed cells), the delivered lift pinch **10.02 -> 30.09 -> 57.48 N** (`fmax` medians, pooled; `force_min` 9.75 -> 29.43 -> 49.14), and **zero** raise/restore rows on any `place*` leg or the right arm (`grep 'finger cap' logs/p79/direct/*.log \| grep -v grasp_lift \| grep -v 'scope:'` = **0**) with the place's own peak unchanged at **10.02 / 10.05 N** against the control's **10.07 N**. The manifest carries `physics.finger_cap_scope.sites = {"left:grasp": <cap>}` and `finger_drive.readback_matches: true` in every armed cell. |
| **does the count come from the pick?** | **No, not at the recorded dose.** Left placed **C 11/20 = 0.550 -> G60 9/17 = 0.529** (Fisher **p = 1.0000**; per-seed deltas **0 / -4 / +2**), i.e. flat, against P77's global **17/20 = 0.850**. The 60 N lift arm's `cnp` is **7 = C's 7** and its `never-held` **1 vs 2** (one episode - not evidence). The registered P1a/P1c fail; the verdict is **NO-PICK**. |
| **does the lift do *anything* measurable?** | **Yes - to the leg state, not to the count.** Left `grasp_lift` legs that **lose a pad** during the leg: **6/20 -> 2/15 (30 N) -> 1/17 (60 N)** (60 N vs C Fisher **p = 0.0975**), `sep_end - gap_start` p50 10.5 -> 9.2 mm. So the pinch's integrity is a function of the cap and *is* fixed; the class that follows from it (`cnp`) is not, at 60 N. |
| **is 30 N the better dose?** | **It is where the direction is, and it is a dose, not a result.** G30 reads left **12/15 = 0.800** (p = 0.163, per-seed +3 / -1 / +1), `cnp` **2**, lost-a-face **2**, place escapes **2/14** - all toward P77 - but it misses P1a's `+3` bar and it is **below** the global arm's dose, so it is not a reproduction of P77's win. P78's place arm at 30 N read the same shape (**12/17 = 0.706**). **60 N does not convert at either site.** |
| **does the dose cost anything?** | **Not on the guarded classes.** Right placed **21/25 -> 26/30 -> 25/28** (non-inferior, p = 0.69), cycle **1751 / 1773 / 1772** ticks (flat), crush guards **0** in all nine cells, and every strawberry leg in the batch was presented to the **right** arm - see §5. |
| **what is the blast radius?** | **Zero, measured with the scope armed.** Scripted acceptance **346/346 `[fruit]` lines byte-identical** to `logs/p76/accept_noharm_full.log` (md5 **`d0079a23`**), `fingerprint: matches`, **0** scope rows printed; two-line **7/10 + `190` PASS** against `eb697f23`. No reference re-recorded. |
| **where does P77's win live, then?** | **In the one leg class no token can reach: the close.** The three controls agree tightly (0.524 / 0.556 / 0.550; pooled **32/59 = 0.542**) and the two scoped 60 N arms bracket them (**0.688** place, **0.529** grasp; pooled 20/33 = 0.606). The global cap is the *only* arm at 0.85, and the only leg it touched that neither scope touches is the **close** - which is not a `_carry` leg, so `place-left` and `grasp-left` cannot reach it *by construction*. P77's `never-held` 3 -> 0 is a *close* class by definition (`fmax == 0` on the carry means contact was never made; no lift force can create contact). Named next: a `close-left` scope at the close's own site. |

## 0.1 The recorded PREREG correction (DEVIATION A1)

`PREREG.md` §4 clause 3 asked for each cell's left `place*` `fmax` median to stay
inside C's band (`<= 11.25 N`). It fired in **1 of 6** armed cells (`G30_202`, 11.37 N)
and the leg behind it **escaped**: `place0 fmax=12.13 N`, `force_min=0.00 N`,
`loss_row=114`, `clean_slip_max=940.1 mm` - a peak **contact transient while the
payload leaves**, at the shipped 10 N drive cap. `fmax` is the leg's peak
instantaneous tactile force and such peaks exceed the drive cap on single legs even
at 10 N (this batch's control reads **35.53 N** on a right `grasp_lift`; P78's read
**79.43 / 134.29 / 155.12 N**), so the clause compared a transient against a *pooled
median* and could not separate a re-clamp from an escape.

P3 is therefore evaluated on what the clause was **for** - the **structural** rows
(zero place-leg/right-arm raise/restore in all six armed cells) and the **pooled**
place force (10.05 vs 10.07) - and the per-cell band is printed beside them. The
deviation is recorded in `PREREG.md` §9 A1 (the pin `0cdfd227` is the pre-run state)
and **no verdict moves**: P1 fails independently.

## 1. The batch and the site proof

Nine cells, 21:47:24 -> 23:11:54, all `exit=0`. The header is
`header.txt` (batch-time pins; the phase-3 run re-wrote `header.txt`, so it is
transcribed with the batch's own start time and the batch-time `selfcheck.sh` md5,
and every other pin is byte-identical to `header_phase3.txt` - the only file that
changed mid-phase was `scripts/selfcheck.sh`, a comment + check label).

| arm | env | left lift `fmax` (pooled) | left place `fmax` | raise/restore rows |
|---|---|---|---|---|
| **C** | scope unset (explicit empty) | 10.02 N | 10.07 N | 0 / 0 |
| **G30** | `SCOPE=grasp-left SCOPED=30` | **30.09 N** | 10.02 N | 15 / 15 |
| **G60** | `...=60` | **57.48 N** | 10.05 N | 17 / 17 |

Every armed cell: the `[drive] finger cap scope: grasp-left x <N> N (runtime,
left:grasp grasp_lift legs ...)` row, one raise + one restore per left `grasp_lift`
leg, read-back equal to the value written, the manifest's `sites` naming
`left:grasp`, and `readback_matches: true` at manifest time - which is a structural
guard, because the manifest is built **after** the last restore (a leaked cap would
read `false` there; it reads `true` everywhere and each joint reads `maxForce 10.0`
/ `0.0` exactly as shipped).

**Wall clock.** ~9.5 min/cell, **85 min** for the nine; the phase-3 pair 9 min.
Cycle per attempt is flat across arms (1751 / 1773 / 1772 ticks).

## 2. The counts (a report, not a rate - PREREG §7)

| arm | n | placed | **left** | right | left `cnp` | left `never-held` |
|---|---|---|---|---|---|---|
| C | 45 | 32 | **11/20** | 21/25 | 7 | 2 |
| G30 | 45 | 38 | **12/15** (p = 0.163) | 26/30 | 2 | 1 |
| G60 | 45 | 34 | **9/17** (p = 1.000) | 25/28 | 7 | 1 |

Per seed, left placed: C **3/6, 6/9, 2/5**; G30 **6/7, 5/6, 1/2**; G60 **3/6, 2/3,
4/8**. The controls reproduce P77's and P78's own control rates to within one
attempt (0.524 / 0.556 / 0.550), so the three batches are measuring the same
scenario.

## 3. Where the win is not

```
left placed, grouped by the leg the cap touched
  shipped 10 N        P77 11/21 .524   P78 10/18 .556   P79 11/20 .550   -> 32/59 = .542
  place* 60 N         P78       11/16 .688   (p = 0.50)                 -> 20/33 = .606
  grasp_lift 60 N     P79        9/17 .529   (p = 1.00)                 ->
  global 60 N         P77       17/20 .850   (p = 0.043)
```

Both scoped halves sit at 0.53-0.69 and the control at 0.54; the global arm is 0.85.
The counts are 15-21 left attempts per arm, so a 0.55-vs-0.85 separation is exactly
the **p = 0.043** P77 reported and nothing smaller is separable - this batch cannot
resolve a 0.55-vs-0.70 difference at all, which is why the 30 N read is published as
a **direction** and the 60 N read as a **null**.

**The mechanism that did move, and did not carry the count.** `lost-a-face` on the
left `grasp_lift` legs (P75/P61's "one pad out of contact" state, the thing the place
leg inherits) fell **6/20 -> 1/17** at 60 N (p = 0.0975) and the lift's `force_min`
went 9.75 -> 49.14 N. That is the H-pick-b path working at the leg level. The class
it is supposed to feed - `cnp` - is unchanged at 60 N (**7 = 7**) and the place's own
escapes even rise (6/18 -> 7/16, p = 0.73) at an unchanged place force (10.05 N), so
that rise is a **branch draw**, not a cap effect. **The lift's pinch integrity is not
the binding term for the placed count.**

## 4. The dose question, stated honestly

Two scoped arms now exist at three doses each, and the ordering is **not monotone**:
30 N reads 0.706 (place) / 0.800 (grasp) and 60 N reads 0.688 / 0.529. A monotone
dose-response would be the minimum evidence that a force was the actuator; there
is none. What the record supports is: the count is **flat to the lift force at 60 N**
(measured twice, this phase and P77's place arm), the scoped 30 N arms are the only
ones that beat the control by more than one attempt, and at n ~ 15-20 per arm that
difference is inside the batch's own branch spread. **"At what force" therefore has
no measured answer above the control's own 10 N** - the force that moves the count
in P77's record is not identified by any single scoped site.

## 5. The guards

* **The place (E5).** The cap cannot reach it and the measurement says so: escapes
  **6/18 -> 2/14 (30 N) -> 7/16 (60 N)**, pries **2 -> 1 -> 3**, place `fmax` p50
  **10.07 / 10.02 / 10.05 N**. The 60 N arm's place is *worse* at an unchanged force.
* **The right (E6).** **21/25 -> 26/30 -> 25/28**; 0 right escapes at 60 N; 3
  never-held right legs at 30 N (a right-arm draw, the left token cannot reach it).
* **The cycle (E7).** 1751 / 1773 / 1772 ticks per attempt, 14.6 / 14.8 / 14.8 s.
* **The strawberry (E8) - a scope limit, not a clean bill.** The crush guards are
  **0 in all nine cells**, and no berry leg shows interference (`sep@loss - dia`
  never below -15 mm on a physical leg; the -28.6 / -27.9 mm rows are recycled-payload
  artifacts with `fmax = 0`). **But every strawberry leg in the batch - 30 of them
  across nine cells, all grade B or C - was presented to the right arm**, because the direct env sets
  the arm from the grade and no A-grade berry was drawn. So **a 60 N pick on a 3.6 cm
  berry was never exercised here**: this batch reads "not exposed", not "safe". P76
  measured that case directly (60 N holds a 36 mm berry at +0.5 mm interference,
  `force_min` 55.4 N) and found no crush - but on the **global** cap, and a real jaw
  at 60 N would bruise that fruit. The left-only token's berry risk is **untested**.

## 6. The blast radius (the deliverable)

With `FRUIT_FINGER_MAXFORCE_SCOPE=grasp-left FRUIT_FINGER_MAXFORCE_SCOPED=60` armed:

| run | read | verdict |
|---|---|---|
| `scripts/accept.sh` | **346/346 `[fruit]` lines byte-identical** to `logs/p76/accept_noharm_full.log`, md5 **`d0079a237202e2f9b0e152655af32a77`**; `fingerprint: matches configs/motion_reference.json` (`8952c320`); **0** scope rows | **PASS** (the FAIL is the standing 6/9 rate-only branch since P71) |
| two-line (`20_pick_place.py`, `FRUIT_BIARM_TWOLINE=1`) | **7/10**, `fingerprint: matches configs/motion_reference_twoline.json` (`eb697f23`), `190_twoline_gate.sh` **PASS** | **PASS** |

No reference was re-recorded. The containment is structural before it is measured -
`resolve_finger_cap_scope` returns `(None, None)` for any presentation but `direct`,
and neither scripted entry constructs `SortingRLEnv` - and the **0 scope rows** is the
measurement of that structure, the same near-tautology P72's manifest block and
P43's import guard are stated as.

## 7. What this means for the register

1. **P77's count win is not the lift's and not the place's.** The place half was
   measured negative at its own site (P78: +1 attempt, p = 0.50) and the pick half is
   measured negative at its own site (here: -2 attempts, p = 1.00). Both are at
   **zero blast radius**, which is the property the global cap lacks.
2. **The remaining candidate is the close**, and it is the one leg class the global
   cap raised that **no `_carry` token can reach** (`_carry` is only ever called with
   `place{i}` and `grasp_lift`). It is also where P77's `never-held` 3 -> 0 must have
   happened: a never-held carry leg has `fmax == 0`, i.e. the pads never touched the
   fruit, and a lift-phase force cannot create contact that the close did not make.
   A `close-left` scope is a **different site** (`_run_impl`'s close/servo window, not
   a carry leg) with its own registration; it is the named next spend, not a result.
3. **The lift's force is still worth having for a different reason**: it fixes the
   leg's pinch integrity (lost-a-face 6 -> 1) at zero blast radius and no cost, which
   is a state the place leg inherits (P75 named 2 of 6 escapes as inherited). That is
   a mechanism, not a count, and at this n it does not convert.
4. **P78's `place-left` stays the only measured count direction** among the scoped
   forms - and it is `+1` attempt at p = 0.50, i.e. not a rate either.

## 8. What this does not claim

Every left number here is a count out of 15-20 attempts, and the direct loop is not
reproducible (rendered frames; a same-configuration replay diverges at episode 2).
`p` values are descriptors; the run level (2/3 seeds) is this design's ceiling at
this n. The 30 N direction is **not** an adoption case: it misses the registered bar,
it is below P77's dose, and P74/P78 both measured that one seed is not a direction.
Nothing is adopted, no default moved, `configs/*` is untouched, and both motion
references (`8952c320` / `eb697f23`) stand.

## 9. Evidence

`PREREG.md` (`0cdfd227` pre-run; `afde5127` with A1 appended) + `PREREG.md5`,
`header.txt` / `header_phase3.txt`, `batch_driver.log` (the nine cells' timings), `run_p79.sh`, `p79_report.py` / `p79_report.txt`
(`--check` exit 0), `direct/` (nine cells), `rollouts/` (nine stores + the smoke),
`smoke_grasp_left_60.log` + `smoke_site_proof.txt` (the 2-episode pre-check, not a
cell), `b1_accept_armed.log` / `.driver`, `b2_twoline_armed.log` / `.gate`,
`selfcheck.log`. Pins: `tasks.py` **`e8dfa6d8`**, `rl_env.py` **`7d26eb5b`**,
`scene.py` **`07d6fdad`**, `scripts/244_p78_scope_selftest.py` **`50fde0fa`**,
`scripts/selfcheck.sh` **`ce338611`** (batch) / **`dd4bf41a`** (after the label
edit), checkpoint `moe_v13s` `61da390a`.
