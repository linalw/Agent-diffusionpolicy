# P73 phase 1 — the place-transfer height vs the left arm's place-leg loaded slide

**A bounded screen. Registration only, written and md5-pinned BEFORE any
simulator run of this phase. Nothing is adopted, no shipped default moves, no
commit is made, `configs/` is untouched.**

Tree at registration: HEAD `c9a129b`, `tasks.py` **`f61323f2`**, `rl_env.py`
**`92a25c8e`**, `assets.py` **`540406fa`**, `configs/motion_reference.json`
**`8952c320`**, `configs/motion_reference_twoline.json` **`eb697f23`**,
checkpoint `moe_v13s` **`61da390a`**. The only `src/` change this phase makes is
the reporting-only instrument of §3 (added before the first run, so all three
arms carry it identically).

---

## 0. The question, and the hypothesis stated so it can fail

P71 shipped the low direct lift and converted the left arm's **carry**
(`drift_end` 25.1 -> 0.7 deg; left placed 4/20 -> 10/17; loaded-slide legs 15 ->
7). What survives is a **place-leg** class: the payload is held through the
transit and lost in the place leg (`logs/p71/RESULTS.md` §3.1: the 6 surviving
treat losses are all `left place0` at `loss_row` 103-150 against the control's
mostly `loss_row` 1-4).

**Hypothesis (H1).** The left's place leg drags the payload out **because
reaching the output line demands ~75-91 deg of wrist rotation** (the hold is
cleared for exactly that reason, `tasks.py:3676-3683`), and the place
**transfer's height sets how much rotation the reach demands**. Therefore
`FRUIT_OPENARM_TRANSFER_LIFT` 0.08 -> 0.14 -> 0.20 (raising the transfer z) must
**reduce the required rotation** and, through it, **reduce the place-leg slide**
— at the cost of a longer final descent to the release.

**H1 fails** if any of:

* **A** the left's achieved place-leg rotation does not move with the transfer
  height (the height does not set the rotation);
* **B** the slide count does not move while the rotation does (the rotation is
  not the actuator);
* **C** the release/landing class regresses (the longer descent costs more than
  the transit buys) even if the slide count falls.

Any of A/B/C -> **the transfer height is not a lever on this class**, and the
left's place leg closes as a **reach consequence** (the named fix is then a
workstation change, `logs/p69/B_PREREG.md`). That negative is publishable.

---

## 1. What the knob actually is (code facts, not the brief's summary)

`FRUIT_OPENARM_TRANSFER_LIFT` (default `"0.08"`) is read at **two** sites, both
`os.environ.get(...)` per call (never cached): `jaw_target("grasp_lift")`
(`tasks.py:3269`) and `jaw_target("place*")` (`tasks.py:3308`). On the shipped
direct line the two sites do **not** behave alike, because the P71 lift override
wins at the first one:

| arm | `grasp_lift` z | `place*` z | what the knob moves |
|---|---|---|---|
| **left** | `belt_top + 0.28 + lift_dz` = **1.370** (`lift_dz_for` returns `-0.08`; `tasks.py:3261-3263` **bypasses** the env read) | `output_place_z + knob` = `1.450 + knob` | **the place transfer ONLY** — exactly the registered lever |
| **right** | `belt_top + 0.28 + knob` = `1.530 + raise` (`lift_dz_for` returns `None`) | `1.450 + knob` | the lift end **and** the transfer |

So on the cell below the **left is a clean place-only arm**, and the **right is
not invariant by construction**: its lift end rises by the same raise
(1.530 -> 1.590 / 1.650). This is a *registered limitation of the existing
knob*, not a discovery after the fact: the right is therefore read as **"no new
failure class and no placed-count regression"**, never as "unchanged".

Two consequences that are arithmetic, not measurement:

* **The release geometry does not move.** `_place_low` (`tasks.py:12879`)
  descends from wherever the transfer ended to the *measured* fruit-bottom
  clearance (`FRUIT_PLACE_LOW_CLEARANCE` 0.025, floor 1.350), capped by
  `FRUIT_PLACE_LOW_MAX_DROP` 0.30 m and the fingertip floor. The shipped drop is
  **81-134 mm** on the P71 corpus, so a +0.06 / +0.12 raise reads 141-194 /
  201-254 mm — **inside** the 0.30 m ceiling, so the release is expected to stay
  on the belt. The added descent is the cycle cost (§4 prediction P2).
* **The crossing gains 0.825:1** (`z_cross = f*z_transfer + (1-f)*z_lift_end`,
  `f = 0.4125/0.50 = 0.825`; P69-B's ranking): +49 / +99 mm of `clr`, which is
  the one thing this lever buys (P69-B rank 2).

---

## 2. The arms and the cell

Direct presentation, the P66-phase-3 / P71-phase-2 cell **verbatim** (so the C
arm is comparable to the shipped corpus):

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11
FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1
HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1
```

`--presentation direct --episodes 15 --seeds <seed>`, checkpoint `moe_v13s`
`61da390a` on every arm, one claim per run.

| arm | `FRUIT_OPENARM_TRANSFER_LIFT` | place z (left) | lift z (right) |
|---|---|---|---|
| **C** (control) | `0.08` (the shipped default, set explicitly) | 1.530 | 1.530 |
| **T1** | `0.14` | 1.590 | 1.590 |
| **T2** | `0.20` | 1.650 | 1.650 |

**Order: C -> T1 -> T2, seed 77 first. Expansion rule (registered):** run seeds
101 and 202 only if the seed-77 read is a **clear mover** = `|Δ left loaded
slides| >= 2` **or** `|Δ left placed| >= 2` against C. Otherwise the phase
reports one seed and says so (the direct loop is not reproducible - rendered
frames - so one seed is one draw and cannot carry a rate; AGENTS §2).

**Why 15 episodes**: the shipped corpus gives 5-6 left attempts per 15-pick run
(15/17/0.375 supply is grade-A-heavy -> the left arm). That is a **mechanism**
cell; it cannot resolve a rate and is not quoted as one.

---

## 3. The instrument (added before the first run; reporting only)

**Why the existing read is blind.** The only per-leg rotation read today is the
`[attitude]` line (`FRUIT_CARRY_ATTITUDE=1`), printed **once, at the leg's end**.
On the shipped P71 corpus's **17 left place legs** the end tilt is:

| class | n | end `tilt` (deg) |
|---|---|---|
| loaded slide (`clean_slip > 800 mm`) | 6 | 80.8, 81.2, 81.9, 84.6, 88.0, 94.6 |
| everything else | 11 | 87.1, 88.6, 88.7, 88.8, 89.3, 89.8, 89.9, 90.4, 90.4, 91.3, 91.8 |

**The endpoint does not separate the classes, and the right does the same ~90 deg
while slipping 0.0-0.1 mm** (`logs/p71/direct/treat_{77,101,202}.log`, its 22
right place legs: tilt 80.4-93.0, 0 loaded slides). So the ~90 deg is the **place
pose's own kinematics, arm-common** — it is *not* a candidate mediator on its
own. A screen that reported only the end tilt would be structurally blind, and
the brief's falsifier A would fire trivially.

**The addition** (`tasks.py`, inside the existing `if guard_armed:` block, i.e.
`FRUIT_CARRY_DIAG=1` only): the achieved tilt from world `-Z`,
`acos(-rot_now[2,2])` — the **same expression** `[attitude]` uses, and
**`rot_now` is already the block's read** for `clean_slip`, so this is **pure
arithmetic with no new read**. Six fields on the `[carry]` row:

| field | meaning |
|---|---|
| `tilt0=` | the leg's first-tick tilt (deg) |
| `tilt_end=` | the last guarded tick's tilt (the `[attitude]` number, cross-checkable) |
| `tilt_max=` | max over the leg |
| `t45=` / `t75=` | first tick at/above 45 / 75 deg (`-` = never) |
| `tilt_rate=` | the signed max per-tick tilt step, deg/tick, with its tick |

This makes the **rotation schedule** visible (when the wrist turns, and how
fast), which is the mediator H1 actually needs: the slide onsets sit at rows
6-112 of ~400-438-tick legs, i.e. **mid-transit, before the pose is reached**.

**The diag is on in all three arms**, so it cannot confound the comparison (the
project's rule: instrumentation is part of the measurement, so compare arms
inside one instrumented batch). Its established caveat also applies: a
`FRUIT_CARRY_DIAG=1` run is not expected to be byte-identical to a diag-off run.

---

## 4. Endpoints, parsing rules, and the pre-run predictions

### Primary

1. **The left's place-leg loaded-slide legs** — `[carry] left place*` rows with
   `clean_slip_max > 800 mm`.
   * **Blow-up exclusion (registered)**: a row with `in-hand_vmax > 5 m/s` or
     `clean_slip_max > 10 000 mm` is an **instrument blow-up** (the payload was
     recycled/teleported inside the leg), counted and reported **separately**,
     never as a slide. This matters for the baseline: the shipped corpus's
     "6 slides" include exactly one such row (`treat_101`: 117 256.6 mm,
     `in-hand_vmax` 13 354 m/s) — so the honest shipped count is **5 real slides
     + 1 blow-up in 17 left place legs**.
2. **The left's placed count** (`[rl] episode ... arm=left placed=True`).

### Secondary (mechanism + cost)

3. The rotation: `tilt0`, `tilt_end`, `tilt_max`, `t45`, `t75`, `tilt_rate` per
   left place leg, and the **slide onset row against `t45`** (does the payload
   leave *before* or *after* the rotation?).
4. `clr` / `clr_win` / `clr_edge` / `clr_edge_min` on held legs — **must not fall
   below 0**; predicted to *rise* with the transfer (§1).
5. The landing class: `[belt] ... discharged to the tray` (on-belt, successful
   landing) vs `[rl] grasp did not land on the belt; re-running
   carry_and_release` vs `fruit fell off the line`.
6. The cycle: per-episode `ticks=` (median + sum) and the place-leg `ticks=`.
   *(The brief says `[stats]`; the direct path does not emit `[stats]` — the P71
   convention, "sim span s/episode", is the same quantity. Registered so the
   report cannot quote a line that does not exist.)*
7. The **right**: placed count, loaded slides, landing class, and its tilt — read
   as "no new class / no placed regression", with the lift-end change of §1
   named.

### Pre-run predictions (registered; a miss is a result, not a rewrite)

* **P1 (crossing)** `clr` rises by ~0.825 x the raise: +49 / +99 mm, i.e. the
  left's held-leg median from ~+35 to ~+84 / ~+134 mm.
* **P2 (cost)** the place leg lengthens by **+55 .. +140 ticks** (+0.45 .. +1.2 s),
  dominated by the longer `_place_low` descent (+54 / +108 ticks at the measured
  0.9 ticks/mm), and the episode by the same.
* **P3 (the mediator is saturated)** `tilt_end` stays in **~85-95 deg in all
  three arms** — the place pose's kinematics, not the height (see §3: the right
  reaches it too). Therefore the *only* way H1 can be true is through the
  **schedule** (`t45`, `tilt_rate`, `tilt_max`), never through `tilt_end`.
* **P4 (the count)** **no monotone fall** in the left's slide count is expected.
  The prior is explicit: (i) the right does the same rotation and slips 0.04-0.1
  mm; (ii) this is the class `logs/p42/SIM_LIMIT.md` closes (the pads hold, the
  payload walks: `sep@loss`/`sep_end` at the 98 mm stop on the shipped corpus's
  escapes); (iii) every lever that touched the grip or the place path since P66
  measured negative (P66 P4's rail gate, P67's climb, P68's wrist pin, P69-A's
  pad asset). A **positive** would therefore be surprising and would require the
  3-seed expansion before it is called anything.
* **P5 (the right)** no new right failure class; its placed count within the
  branch spread of its 22/28.

### The cheap discriminator (rotation vs acceleration) — conditional

Only if the T arms leave the mechanism **ambiguous**, i.e. exactly when
(tilt moves but slides do not) or (slides move but tilt does not): one
**C arm with the place profile slowed** — `FRUIT_SPEED_PLACE=0.20` (the P44 S1
knob; it drives the same `jerk_limited` place profile through
`speed_cell_defaults()`, `tasks.py:3797`). If the slower place leaves the ~90 deg
rotation **and still loses the payload**, the slide is **kinematic** (a pose
consequence); if it converts, it is **inertial**. This arm is **not run
otherwise** — it is not spent on a read that is already unambiguous.

---

## 5. The decision rule

| outcome | verdict |
|---|---|
| slides fall monotonically with the raise **and** left placed rises **and** landing does not regress **and** the tilt schedule moves monotonically in the "less rotation" direction | **H1 supported** — the transfer height is a lever; a 3-seed confirmation is the next step. Still **not adopted** in this phase (one seed, one draw) |
| slides fall but the tilt schedule does **not** move | falsifier **A**: the height does not set the rotation -> H1 dead as stated |
| the tilt schedule moves but the slides do **not** | falsifier **B**: the rotation is not the actuator -> H1 dead; the class is the closed `SIM_LIMIT.md` loaded slide, and the residual is a workstation item |
| landing regresses (more `did not land` / `fell off`) | falsifier **C**: the longer descent costs more than the transit buys -> not adoptable |
| no endpoint moves | the height is **inert** on this class — a clean negative, and the strongest available statement that the place leg is a **reach** consequence |

**Nothing is adopted either way.** No default changes, `configs/` untouched. If
the screen is favourable, one `scripts/accept.sh` proves the scripted line's
reference does not move (the knob is an `os.environ` read, but the OpenArm
scripted line reads the same `jaw_target` sites, so this must be *verified*, not
assumed — and if the acceptance's fingerprint moves, `configs/motion_reference.json`
must be re-recorded from the shipped-scenario run, not from a T arm).
`scripts/selfcheck.sh` runs at the end of the phase regardless.

---

## 6. What this cell cannot answer (registered up front)

* **The right's inertness** — structurally impossible with this knob (§1).
* **A rate.** 5-6 left attempts per run, one draw; `placed` is one draw of a
  non-reproducible loop.
* **Whether the 90 deg itself is necessary** — that needs the place pose moved
  (a workstation/`output_place_y` change, `logs/p69/B_PREREG.md` rank 2/3), not
  a height.
* **The ledge class** (`logs/p72/RESULTS.md` §6) — untouched; the release point
  does not move.
* **Whether the slide is inertial** unless the §4 discriminator is triggered.
