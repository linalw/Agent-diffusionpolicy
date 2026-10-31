# P78 results — a **site-scoped** clamp force: the containment is total, the dose is
# mechanism-equivalent to P77, and the count is a direction, not a rate

**Nothing adopted, no default changed, no commit, `configs/*` untouched.** Two
registrations: `PREREG.md` (**`01077e1a`**, the knob + the ladder + the blast-radius
gate, pinned before any run) and `PREREG_EXT.md` (**`4a3b8081`**, the scoped **60 N**
extension at seeds 101/202, pinned after the S30 three-seed read and before those cells
ran). Direct line, `moe_v13s` `61da390a`, the P66-phase-3 / P71-phase-2 / P73 / P74 / P75 /
P76 / P77 scenario verbatim, 15 picks per cell, one claim each.

---

## 0. Verdict

| question | answer |
|---|---|
| **can the finger drive's `maxForce` be written at runtime, and does it take effect?** | **Yes, and it is provable three ways.** `Articulation.set_dof_max_efforts` routes to the tensor backend's `set_dof_max_forces`, which writes the **live** model's `joint_effort_limit` and notifies the solver's `JOINT_DOF_PROPERTIES` (`isaacsim.physics.newton/.../articulation_view.py:1364-1385`, `:108-114`). In-run: the per-leg `[drive]` read-back follows (`10.00 -> 60.00`, readback `60.00`), the **delivered** force follows (place-leg peak 29.75 / 44.99 / 56.08 N at caps 30 / 45 / 60 against the control's 10.69), and the **pick** in the same run stays at the shipped cap (`grasp_lift force_min` 9.10-9.97 N). This is the runtime mutator `scene.apply_finger_maxforce`'s own docstring names ("only `set_dof_gains` / `set_dof_max_efforts` act on a live view"). |
| **does the scoped form move anything it should not?** | **No - zero blast radius.** With the scope **armed**, the scripted acceptance is **346/346 `[fruit]` lines byte-identical** to `logs/p76/accept_noharm_full.log` (md5 **`d0079a23`**) with `fingerprint: matches`, and the two-line reads **7/10 + `190: PASS`** against `eb697f23`. Neither run prints a single scope row: the scripted/collector/two-line/canary paths never construct `SortingRLEnv`, so the knob cannot be read there. |
| **does P77's count win reproduce at a site-scoped dose?** | **As a direction, yes; as a rate, no.** Left placed **C 10/18 (55.6 %) -> S30 12/17 (70.6 %)** and **-> S60 11/16 (68.8 %)**; Fisher p = 0.49 and 0.50, per-seed +1/-2/+2 at 60 N. P77's global 60 N read 11/21 -> 17/20 (p = 0.043) - the **same direction, larger magnitude, not significant here**. The **mechanism** reproduces P77 exactly: pries **3/36 -> 0/32 (30 N) / 1/31 (60 N)** and escapes **8/36 -> 4/32 / 4/31 (50 %, not the <= 1/3 bar)** against P77's T (4/38 -> 1/40 pries, 7 -> 3 escapes = 43 %). |
| **does the dose have a cost?** | **The two doses fail different guards, and only one failure is dose-attributable.** S30 loses **3 right placements** (25/27 -> 22/28) with no crush; S60 keeps the right (25/29) but its cell carries **one crush-guard leg** - a **3.88 cm strawberry on the RIGHT arm's `grasp_lift`**, at the **shipped 10 N cap** the scope never touches (`sep@loss` 22.9 mm, `fmax` 32.07 N, `grasped=False`). So the crush is **not** the scoped force's doing; it fires the registered per-cell guard anyway, and with one event in ten cells it is a draw. |
| **what does that say about where P77's win lives?** | The extension's **P5** predicted that a scoped-60 count failure would mean "the win lived in the **grasp**". It **did not fire**: the place-leg-only cap, which cannot touch the pick, still moves the left count in P77's direction. So the **place leg carries the direction**; only the magnitude is unresolved at this n. |

## 0.1 The recorded PREREG correction (the manipulation statistic)

`PREREG.md` §1 criterion (2) asked for the leg's `force_min` to land in P76/P77's **85-99 %**
of the requested cap. It does not, at 45/60 N (`place*` fmin medians 36.07 / 46.74 N = 80 %
/ 78 %), and the reason is the **statistic**, not the write: `force_min` is the leg's
**minimum** tactile force, i.e. its weakest moment (a contact transient while the pads
reseat), and P76/P77 quoted it over **all** legs of a **global** arm, where lift legs share
the raised cap. Under a leg-scoped cap the leg **maximum** is the clamp read, and it tracks
the cap: **29.75 / 44.99 / 56.08 N at 30 / 45 / 60** (99 / 100 / 93 %), against a control of
10.69 N. The condition's **intent** - "did the physics move, not just the attribute" - is
met with a 3x-5x margin, and **F2 does not fire** (the force nowhere "stays at the shipped
~9.7 N"). The report prints both statistics and gates on `fmin >= 75 % AND fmax <= 110 %`
of the cap; this correction is recorded here rather than silently applied.

## 1. The batch and the manipulation check

Seed-77 cells shown (the three-seed values are in §3 and in `p78_report.txt` §0):

| arm | env | `place*` fmin / fmax (medians) | `grasp_lift` fmin | raise/restore rows |
|---|---|---|---|---|
| **C** (shipped 10 N) | scope unset (explicit empty) | 9.90 / 10.69 | 9.33 | 0 / 0 |
| **S30** | `SCOPE=place-left SCOPED=30` | 29.65 / 29.75 | 9.10 | 3 / 3 |
| **S45** | `...=45` | 36.07 / 44.99 | 9.52 | 5 / 5 |
| **S60** | `...=60` | 46.74 / 56.08 | 9.97 | 4 / 4 |

Across all nine scoped cells the `place*` medians are **28.22-54.35 N (fmin)** and
**29.75-59.25 N (fmax)** at caps 30/45/60, against the control's 9.75-9.99 / 10.02-11.25,
with `grasp_lift` at **8.35-9.97 N** in every one of them.

Every armed cell: a `[drive] finger cap scope: place-left x <N> N` row, one **raise** and
one **restore** per left `place*` leg with the read-back equal to the value written, the
manifest's `physics.finger_cap_scope` naming `left`, and
`physics.finger_drive.readback_matches: true` at manifest time - the last one is a real
structural guard, because the manifest is built **after** the last restore, so a leaked cap
would read `false` there (it reads `true` in every armed cell, and each joint reads
`maxForce 10.0` / `0.0` exactly as shipped).

**Wall clock.** Ladder 19:04:33 -> 19:57:37 (53 min, 4 cells; S60 was the outlier at ~24 min
against ~9.5 min, a wall artifact of a branch, not of the cap - its per-episode ticks are
1787 vs 1750). Blast radius 20:07 -> 20:16 (9 min). Phase 2 (S30, seeds 101/202) 20:16 ->
20:54. Extension (S60, seeds 101/202) 21:00 -> 21:15. No claim overlapped, every driver
reports `fail=0`.

## 2. The ladder at seed 77 (PREREG §3)

| arm | left placed | left escapes | left pried | right placed | cycle ticks | D1-D5 |
|---|---|---|---|---|---|---|
| C (10 N) | 3/5 | 2 | 1 | 9/10 | 1750 | - |
| **S30** | 3/4 | **0** | **0** | 8/11 | 1790 | `+++++` |
| **S45** | 3/6 | 2 | 1 | 8/9 | 1780 | `+-+++` (D2) |
| **S60** | 4/4 | **0** | **0** | 9/11 | 1787 | `+++++` |

Two rungs passed the registered screen, so the economical rule picked the **lower** (S30)
for the confirmation seeds - and **the single-seed screen did not hold** (P74's lesson,
again): at three seeds S30's escape count is **4/32 = 50 %** of C's 8/36, not a third, and
its right loses three placements. S45 is the one rung the screen rejects, on the same
statistic that then fails for the others - a reminder that at 6-16 left legs a single seed
cannot rank escape counts.

**The S45 cell carries one useful negative**: its two escapes are the **same two pears** C
loses, and the first is a **radial pry at `sep_max` 95.6 mm under a delivered 46.05 N clamp**
- i.e. **more than four times the shipped force did not stop that instance's radial pry**,
which is the P76/P77 statement that force reduces the class rather than deleting it. Its
second pear escaped **axially** at `+9.4 mm` beyond its width, the shallow mode of §4.

## 3. The three-seed reads (the extension, and the economical rung)

| pooled, seed 77/101/202 | C (10 N) | S30 (scoped 30 N) | S60 (scoped 60 N) |
|---|---|---|---|
| left placed | 10/18 = 55.6 % | **12/17 = 70.6 %** (p = 0.49) | **11/16 = 68.8 %** (p = 0.50) |
| left escapes (legs) | 8/36 = 22 % | 4/32 = 12.5 % (**50 %** of C) | 4/31 = 12.9 % (**50 %**) |
| left pried (legs) | 3/36 = 8.3 % | **0/32** | **1/31 = 3.2 %** |
| left never-held | 0 | 0 | 1 |
| right placed | 25/27 = 92.6 % | 22/28 = 78.6 % | 25/29 = 86.2 % |
| cycle (median of medians) | 1774 | 1804 (+1.7 %) | 1789 (+0.8 %) |
| crush legs (C1/C2) | 0 | 0 | **1** (right arm, shipped cap - §5) |

**The registered rule, evaluated.** S30 fails **D2** (escapes at 50 %) and **D4** (right
-3); S60 fails **D2** (escapes at 50 %, pries pass at exactly 3 <= 3*3) and **D3** (one
crush leg, on a leg the scope cannot reach - §5). The extension's `G2/G4/G5/G6` pass,
**`G3` fails** (the same half, at the same 50 %) and **`G7` fails** on that same right-arm
crush leg. **No rung meets its own bar, so nothing is adopted and no rate is claimed.**

**What is quotable, and it is the mechanism**: at both doses the **pry** is essentially
deleted (3/36 -> 0 and 1/31) and the **escape** halves but does not close - the exact shape
P77 measured for the global 60 N (4/38 -> 1/40 pried, 7 -> 3 escaped at 43 %), and the
shape `logs/p42/SIM_LIMIT.md` predicts for a loaded slide that force cannot delete.

## 4. The mode split (`sep_max - dia`), the discriminator P77 named

The **left** arm only (the scoped arm); `radial` = the pads reached >= +13 mm past the
fruit's own width (an expulsion through an opening gap), `axial` = <= +10 mm (the pads
closed on it and the payload walked out along the tool axis).

| arm / seed | left escapes | radial | axial | between | range |
|---|---|---|---|---|---|
| C 77 | 2 | 1 | 0 | 1 | +10.3 .. +29.8 |
| C 101 | 3 | 3 | 0 | 0 | +26.0 .. +31.3 |
| C 202 | 3 | 2 | 0 | 1 | +12.2 .. +24.2 |
| **C pooled** | **8** | **6** | **0** | **2** | +10.3 .. +31.3 |
| S30 77 | 0 | - | - | - | - |
| S30 101 | 2 | 2 | 0 | 0 | +13.5 .. +21.5 |
| S30 202 | 2 | **0** | **2** | 0 | **+5.7 .. +9.9** |
| **S30 pooled** | **4** | **2** | **2** | **0** | +5.7 .. +21.5 |
| S60 77 | 0 | - | - | - | - |
| S60 101 | 3 | 2 | 1 | 0 | +8.8 .. +25.6 |
| S60 202 | 1 | 0 | 1 | 0 | +2.7 |
| **S60 pooled** | **4** | **2** | **2** | **0** | +2.7 .. +25.6 |

**The mode does migrate, and it migrates the way P77 measured.** The control's escapes are
**radial or borderline and never axial (0 of 8)**; at both doses **half the residue is
axial (2 of 4)** - the shallow exit through a nearly-closed gap that P77 saw on 2 of its 3
T escapes, and the geometry `logs/p42/SIM_LIMIT.md` / P61 measured (payload out along the
tool axis). So the dose **does** change *how* the payload leaves even though it does not
delete the class: **the radial pry is what force removes, the axial walk is what survives.**
The three radial survivors are named in §2.

## 5. The smallest fruit, and the one crush-guard leg

Every **held** strawberry leg is placed at both doses; the single guard fire is on the right
arm at the **shipped** cap.

| arm | strawberry legs | placed | `sep_max - dia` (held ones) | verdict |
|---|---|---|---|---|
| C (3 seeds) | 6 | 6 | +1.6 .. +8.9 | held |
| S30 | 5 | 3 real (2 never-held, `fmax 0.00`) | **+2.7 / +3.6 / +8.8** | held, no crush |
| S60 | 4 | 3 real (1 the crush leg below) | +1.1 / +3.7 / +5.0 | held at the left, no crush |

The **3.6-3.9 cm** berry is held at **+1 to +9 mm** beyond its own width at both doses.

**The crush leg (S60/101), attributed.** A **3.88 cm strawberry, `right` `grasp_lift`**:
`sep@loss` **22.9 mm** against `dia` 38.8 = **-15.9 mm** of interference (C1 fires),
`fmax` **32.07 N**, `force_min` 0.00 N, `loss_row` **9**, `clean_slip_max` 474.7 mm, and the
episode is **`grasped=False placed=False`** - the close squeezed the fruit out and the lift
never took it. **The scope cannot reach that leg** (right arm, `grasp_lift`), so the event is
the **shipped** close's own squeeze-out, not a dose effect; the ten cells draw it once and
the control's three seeds did not draw it at all, so it is a **draw, not a rate**. It is
reported as a fail because the registered D3/G7 wording is per cell and per arm-agnostic -
a registered guard doing its job on an event it did not cause. The `-28.8 / -14.0 / -14.6 mm`
`sep@loss - dia` values in the S30 cells are the **never-held artifact** class
(`fmax = 0.00 N`, slips of 181 997 / 251 284 mm, P76 A3) and are excluded by the guards' own
`never_held` term; they are listed so the exclusion is visible, exactly as P77 §3 did.

## 6. The right arm, the reasons, the landing class

* **Right**: 25/27 (C) -> 22/28 (S30) / 25/29 (S60), **no new right failure reason in any
  arm**, landing class unchanged (`fell off the line` C 1, S30 1, S60 1-2). One **right**
  escape appears at S30/101 (lychee 3.7 cm, `grasp_lift`, `sep_max` 98.5 mm, `fmax` 30.03 N)
  and one at S60/101 (no pry) - both at the **right** arm, which the scope cannot touch;
  the shipped path produces the same class (P77 §5, `logs/p71/twoline/none.log`).
* **No new reason anywhere**: the only reason string on a failure in any arm is
  `fruit fell off the line` (the supply class). Every other non-placed episode is the
  reason-less `cnp` class (`grasped` and not `placed`), read from the flags.

## 7. The blast radius (the phase's main deliverable) - PASS

| check | result |
|---|---|
| **B1** scripted `accept.sh`, scope **armed** | **346/346 `[fruit]` lines, md5 `d0079a23`** - byte-identical to `logs/p76/accept_noharm_full.log`; `fingerprint: matches configs/motion_reference.json` (`8952c320`); the only rate clause is the standing **6/9 vs the 75 % floor** (this tree's P32 branch, exit 1 for that reason only); **no scope row printed** - the scripted line never reads the knob |
| **B2** two-line, scope **armed** | **7/10 = 70 %** at the 0.60 floor, **`fingerprint: matches configs/motion_reference_twoline.json`** (`eb697f23`), **`190: PASS`**, 5 reported (non-gating) carry-cone warnings; **no scope row** |
| **B3** `configs/` | `motion_reference.json` **`8952c320`**, `..._twoline.json` **`eb697f23`** - both unchanged; **no reference re-recorded** |
| **B4** resolution table | pinned by the new selfcheck leg `scripts/244_p78_scope_selftest.py` (45 checks): non-`direct` -> `(None, None)` **before any value is read**, an explicit global `FRUIT_FINGER_MAXFORCE` wins, `place-left` -> `{"left": cap}`, every strict raise; the `place*`-only / per-side scope; the `try`/`finally` wrapper (the leg inside the try, the restore in the finally); one live-view write site; the restore target is the **read** cap, never a hard-coded 10 N |

**Honest framing of B1/B2**: they are **import/structure guards** - the scripted entry
points never construct `SortingRLEnv`, so "no leak" is true by construction as well as by
measurement. The **substantive** proof that the write is real and site-limited is §0/§1's
direct-line evidence (the read-back, the delivered force by leg class, the manifest). Both
statements are needed and neither substitutes for the other.

## 8. Deviations and notes

1. **The manipulation statistic** (§0.1): `force_min` is a leg minimum, not a clamp read
   under a leg-scoped cap; the report now gates on `fmin >= 75 % AND fmax <= 110 %` and
   prints both. Recorded, not silently applied.
2. **A single-seed screen ranked doses wrongly** (§2): S30 and S60 both passed, S30 was run
   at three seeds as the economical choice, and its 6-leg "0 escapes" became 4/32. This is
   P74's lesson reproduced exactly; the phase's conclusion rests on the **three-seed**
   pooled reads, never on the seed-77 cell.
3. **`scripts/237_p67_climb_selftest.py` re-pinned**: P78 renames the carry-leg body to
   `_carry_leg` (`_carry` is now the scoped-force wrapper) and the leg located the body by
   its `def` line - the locator follows the body, **every assertion is unchanged** and still
   reads the thing it was written for.
4. **`rl_env.TASKS_MD5` metadata-only follow** `9d5824ef -> b1464c43` (three selftest legs
   pin it; nothing behavioural).
5. **`logs/p36/offline_obs_diff.txt`** is **regenerated** by the selfcheck's `218` leg and
   therefore now names the new `rl_env.py` md5. It is a generated md5 index, not a claim
   change, and the tree is left uncommitted by design.
6. **Wall outlier**: the S60/77 cell took 24 min against 9.5 min for its neighbours at the
   same tick count - a rendering/branch artifact, recorded so the batch's duration is not
   read as a cost of the cap.

## 9. What this phase did and did not establish

* **Established**: a runtime, per-leg finger-drive force cap is writable on this stack and
  takes effect in physics (**read-back + delivered force + the pick untouched in the same
  run**); it can be scoped to one arm's `place*` legs with a `try`/`finally` restore; and
  **armed, it moves no reference and no scripted stream** (346/346 + two fingerprints +
  `configs/` unchanged). The scoped cap reproduces P77's **pry reduction** (3/36 -> 0 and
  1/31) and its **escape ratio** (50 % vs P77's 43 %), migrates the mode toward the axial
  exit (0/8 -> 2/4), and moves the left count in P77's direction **without** the grasp
  half - so the place leg carries the direction.
* **Not established**: a rate, a dose recommendation, or a shippability decision. The
  **escape class still halves rather than closes** at both doses (the `SIM_LIMIT.md`
  loaded slide), the 30 N dose pays **three right placements**, the 60 N cell drew **one
  crush-guard leg on a right-arm, shipped-cap leg** (not dose-attributable), and
  `configs/` holds no adoption.
* **The owner's decision** is therefore a real one and this phase's job was to make its
  price **zero**: a +2 placement left direction (12/17 at 30 N, 11/16 at 60 N against 10/18)
  with a 2-3x pry reduction, a mode shift, and **no motion-reference, scripted, two-line or store cost** is now shippable as a
  `direct`-only default if the owner accepts a count that has not reached significance
  here. The 30 N vs 60 N choice is a documented trade (right placements vs a slightly
  larger count) and the phase does not recommend either.

## 10. Evidence and pins

```
logs/p78/PREREG.md / .md5            the rule, pinned before any run   (01077e1a)
logs/p78/PREREG_EXT.md / .md5        the scoped-60 extension            (4a3b8081)
logs/p78/header.txt                  the batch's md5 pin block
logs/p78/run_p78.sh                  the driver (phases 1/2/3)
logs/p78/p1_driver.log, p32_driver.log, p4_ext_driver.log   the three batches
logs/p78/direct/<arm>_<seed>.log     10 cells (C x3, S30 x3, S45 x1, S60 x3)
logs/p78/rollouts/<arm>_<seed>/      the manifests (the physics block read-back)
logs/p78/smoke_60.log                the 2-pick feasibility smoke
logs/p78/b1_accept_armed.log/.driver the scripted blast-radius run (346/346 + matches)
logs/p78/b2_twoline_armed.log/.gate  the two-line blast-radius run (7/10 + 190 PASS)
logs/p78/p78_report.py / p78_report.txt   the per-leg tables and the rules
logs/p78/selfcheck.log               the close-out self-check
scripts/244_p78_scope_selftest.py    the new selfcheck leg (45 checks)
```

**Pins**: `tasks.py` **`b1464c43`**, `rl_env.py` **`5c7322d2`**, `scene.py`
**`fbd7e2bb`** (the `scope=` kwarg + the `finger_cap_scope` block), `control.py`
`9384ff4f`, `assets.py` `540406fa`, `fruits.py` `c7461d41`, `policy/trigger.py`
`b09d3cb2`, `scripts/244_p78_scope_selftest.py` **`aadea2d3`**, `scripts/selfcheck.sh`
**`ce338611`**, `scripts/237_p67_climb_selftest.py` **`6a6b18bf`** (the locator re-pin),
`configs/motion_reference.json` **`8952c320`**,
`configs/motion_reference_twoline.json` **`eb697f23`** (both untouched), checkpoint
`moe_v13s` **`61da390a`**. The batch's own md5 block is `logs/p78/header.txt`.
