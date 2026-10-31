# P70 — the output line's side rails and belt height (the owner's ledge directive)

Owner's directive: **remove the output belts' side rails (the "ledges") on both
sides, and lower the output belt's height as appropriate.** Scripted line first,
then the direct line; no `configs/` edit, no default change, no commit.

Tree **as measured**: `tasks.py` **`7c00e5`**, `assets.py` **`9e9804`**,
`conveyor.py` **`fb2c58`**, `rl_env.py` **`588669`** (the `TASKS_MD5`
metadata-only follow), `fruits.py` `c7461d41`, `scene.py` `27e3d64a`;
`configs/motion_reference.json` **`8a399626`** and `..._twoline.json` `2246f83c`
**untouched**; checkpoint `moe_v13s` `61da390a`. At that tree rails `both` at
1.35 was still the default; **a concurrent P71 lane has since flipped
`FRUIT_OUTPUT_RAILS` to `none` and the low direct lift on this phase's numbers**
— see `logs/p70/TREE.md` for the timeline and the file states. P70 itself
**adopted nothing**: it added the `FRUIT_OUTPUT_BELT_TOP_Z` knob (default 1.35)
and fixed the clearance report, and it made no commit.

---

## 0. Verdict

**The rails are the lever and the height is not: removing both rails clears the
crossing 1:1 (+35 mm, one step) and is behaviourally inert on this scenario;
lowering the belt is a 0.175:1 lever whose biggest admissible dose (+7 mm) costs
the entire under-slab audit and is the only arm that loses placements. The ledge
class is not exercised on this scenario, so nothing was traded for it.**

1. **Removing the rails clears the crossing by the full proud height, 1:1.** The
   same fruit, the same arm, the same tick: the record's marginal leg (the
   **5.6 cm kiwi on the left arm**, `+30 mm @rail / t275`) reads **`+65 mm @obelt
   / t275`** in cell A — **+35.0 mm at an identical crossing tick**, which is
   exactly the rail box's `0.05 - 0.015` proud height. The held population goes
   **`clr` +30..+120 → +65..+156 mm** and
   **`clr_win` +29..+96 → +64..+113 mm**, i.e. the worst leg goes from 4 mm
   *below* the +33 convention to **31 mm above it**, and 51 mm above the measured
   contact boundary (`+7, +14] mm`, `logs/p69/G0_RESULTS.md`).
2. **It costs nothing measurable on this scenario.** The same placed count as the
   same-tree control (6 in both; A from 9 attempted slots, one starved), fewer
   loaded slides (3/9 vs 4/10), the same discharge count
   within the run's window (4 vs 5 of 6 placed), `diverted=0`, no `fell off`
   line, and **no contact signature** (place-leg `|a|max` 4.21-4.98 m/s² against
   the 18-20 m/s² rail-contact signature of `logs/p30a` A4). The `[fruit]`
   streams are **identical through the first place leg** with only the clearance
   field differing (the divergence that follows is the scene's shape set moving
   the solver ordering at the 1e-4 m level, P30-A's own precedent).
3. **Lowering the belt does help the crossing — the sign is positive — and it is
   still not worth it.** The derivation (§2): the payload descends `f = 0.825` of
   the transfer's drop while the obstacle descends 1:1, so **`d clr / d(belt top)
   = 0.175`** — 40 mm of lowering buys **+7.0 mm**, one fifth of what the rails
   buy in one step, and it spends **1:1** of the slab-underside audit (40 mm at
   the shipped top; at 1.31 the print reads `0.006 m` nominal and **`0.000 m` at
   the 1.07 instance scale**). Cell B is the only arm whose count falls by the
   F5 corroborator's margin (**4/10 vs the control's 6/10**) and its place legs
   are 6.8 % longer (333 vs 312 ticks/leg) for the 40 mm deeper descent. **The
   recommendation is therefore 0 mm**: the rails already clear the floor, and if
   the belt is wanted lower for another reason, **1.33** (−20 mm, +3.5 mm
   crossing, 20 mm of audit kept) is the conservative pick and **1.31** is the
   lever's endpoint.
4. **The ledge class is not exercised here, so the decision P30-A registered
   never came up.** Of the 16 releases that were actually *in hand* across the
   three arms, **16/16 sit 116-122 mm outboard of the slab's inner edge**; **0**
   are in the rail's top-face band (0.400-0.425) and **0** are inboard of 0.400.
   The 2.3 %-of-10 195 class (`logs/p30a/RESULTS.md` §7.3) is a property of the
   *pooled* release population, not of this scenario's. And with the rail gone
   that band has **no surface under it at all** (the slab starts at 0.425 and the
   main belt is 180 mm below), so a release landing there falls instead of
   parking on the fence: the class would go from a `placed` score to a lost
   placement, which is the cost to watch in any scenario that does land releases
   there.
5. **On the low direct lift the removal is necessary and still not sufficient**,
   which is the one place this phase does not close its question. With
   `FRUIT_LIFT_DZ=-0.08` and no rails, the left's ten held place legs cross at
   `−1..+54 mm` against the belt plane — **had the rail been there, 9 of the 10
   would have been at or below its top face** (6 of them 9-36 mm inside the box),
   which is the mechanism P66/P67 kept losing payloads to. Removing it leaves the
   **slab's inboard edge** as the binding object at **+3 mm on the worst leg**
   (5 of 10 below the +33 convention, no contact measured: `|a|max 0.98`), so the
   rung is better off and still not certified — and the height lever cannot buy
   the rest (`0.175 mm/mm`, capped at +7 mm by the under-slab audit).

---

## 1. Task 1 — the knob, and every consumer of `output_belt_top_z`

**`FRUIT_OUTPUT_BELT_TOP_Z`, default `1.35`, byte-inert.** A
`field(default_factory=lambda: float(os.environ.get(...)))` in
`assets.SceneConfig`, exactly the shape `output_rail_height` uses, so the shipped
scene is constructed by the same float and the build print is unchanged
(`scripts/238_p70_belt_top_selftest.py` pins the factory form, the default, an
explicit value and a hard error on a non-number).

The read-site census (AST, `238` pins the **eleven** scopes so a new consumer has
to be declared):

| site | what moves with the belt top | sign |
|---|---|---|
| `SceneConfig.output_place_z` | `T + output_place_clearance` — the **place transfer** pose, and through it the place target (`jaw_target` adds the hand's 0.08) | 1:1 |
| `tasks._place_low` (`floor = T`) | the release's descent floor, and the **released height above the surface** stays `clearance` (0.025) | net invariant |
| `tasks._place_trace_report` (`floor = T`) | the landing trace's release/impact/bounce reference | 1:1 |
| `tasks._grasp_carry_place_impl` | the `over the output belt: ... top=` print, the release-debug's `support_z`, and `FRUIT_RELEASE_SUPPORT`'s `floor` | 1:1 |
| `SceneConfig.on_output_belt` | the z test that defines **`placed`** (`z >= T - margin`) | 1:1 |
| `SceneConfig.on_output_discharge` | the discharge envelope's **top** (`z <= T + 0.05`); the tray floor (0.92) and the chute's end z (1.12) are absolute **and do not move** | 1:1 (top only) |
| `SceneConfig.output_chute_top` | the chute's upper edge = `T - 0.006` (the seam) | 1:1 |
| `SceneConfig.output_chute_bottom` | the run `(T - 1.12)/tan(55°)`: **shorter**, the angle and the lower edge unchanged | run only |
| `conveyor.OutputBelt.__init__` | the slab's centre z (the slab, and its kinematic body) | 1:1 |
| `conveyor.OutputBelt.build` | the rails' bottom (`T - OUTPUT_RAIL_INSET`), the support legs' height, and the four audit prints | 1:1 |
| `tasks._payload_clearance` | the surface the `clr`/`clr_win`/`clr_min` report measures against (§3) | 1:1 |

Downstream, `rl_env.py` sees it **only** through `output_place_z` (the
`lift_climb` row's `transfer`, and `_goal`'s place z), and `fruits.py` only
through `on_output_belt` / `on_output_discharge` / `on_output_tray` — both
asserted by `238`.

**One consumer that is a knob in its own right and is now shared**: the rail's
bottom inset. `OUTPUT_RAIL_INSET = 0.015` is a module constant read by the builder
(`conveyor.py`, bit-identically) **and** by the new `SceneConfig.output_rail_proud`
= `output_rail_height - OUTPUT_RAIL_INSET`. That property is what closes the
instrument defect below.

**Two out-of-tree consumers of the number** (probes, re-run only by hand):
`scripts/212_occlusion_map.py` hard-codes `OUT_TOP_Z = 1.35`, and
`scripts/461_release_probe.py:93` builds `rim = floor + 0.035`. Neither is on a
shipped path; both would need the config if the belt height is ever armed.
`fruits._free_sample`'s **bed-only** "not on the main belt" cut is
`belt_top_main + 0.10 = 1.27`, which a placed fruit still clears by ≥55 mm at
1.31 (the smallest class' centre is 1.324), so that guard does not bind at 1.31.

---

## 2. Task 2 — the arithmetic, derived (the sign, not assumed)

The scripted place leg is a **straight line** from the lift's end to the transfer
pose, and the payload crosses the inner rail's centreline at
`f = 0.4125 / 0.50 = 0.825` of its `|y|` span (`tasks._output_rail_y`; the
identical derivation `rl_env._lift_climb_row` prints). So

```
z_crossing(T) = f * transfer(T) + (1 - f) * lift_end
transfer(T)   = T + output_place_clearance (0.10) + the hand's add (0.08) = T + 0.18
lift_end      = main belt top (1.170) + 0.28 + 0.08                     = 1.530   [independent of T]
```

* `z_crossing(1.35) = 1.5300 m` (the transfer itself — the shipped leg is
  horizontal), `z_crossing(1.31) = 1.4970 m` (−33.0 mm).
* **With the rails gone, the surface at the crossing is the slab's inboard top
  edge**, i.e. the belt top plane `T`. The crossing *sample* (`|y| = 0.4125`) is
  in fact over a **void** — the slab starts at 0.425 — so the honest reading is
  the slab's top edge that the body must clear across the rest of the window
  (0.425-0.460); the main belt below it is 180 mm lower still. `clr` therefore
  reports against `T` (`@obelt`) instead of against `T + 0.035` (`@rail`), which
  is **+35 mm, 1:1, for free**.
* **Lowering the belt by `d`**: the payload at the crossing falls `0.825 d`
  (the transfer moved), the obstacle falls `d` ⇒

  ```
  d(clr) / d(T) = f - 1 = -0.175     ->  lowering by d raises clr by 0.175 d
  ```

  **the sign is positive**: 40 mm → **+7.0 mm**. Measured corroboration is the
  population (A's worst window +64 → B's worst +91) but A→B is a *moved branch*
  (the fruit sequence diverges from attempt 1), so **the +7.0 is the
  arithmetic's number and the population only agrees in sign**.
* **Why 40 mm is the endpoint**: the same 1 mm of lowering spends 1 mm of the
  slab-underside audit over the main belt (`conveyor.OutputBelt.build`'s print:
  `0.130 / 0.046 / 0.040 / 0.014 m` at 1.35 → `0.090 / 0.006 / 0.000 / −0.026 m`
  at 1.31, the third being the tallest pear at the 1.0706 instance scale), so the
  admissible dose is **40 mm** and B spends all of it.
* **Rails vs height, per mm**: **1.00 mm/mm** (the obstacle moves, the trajectory
  does not) against **0.175 mm/mm** (the obstacle moves 1:1 but the payload moves
  0.825 of it too). The rails are 5.7x the lever, and their whole travel (35 mm)
  is a single setting.

**The instrument this depends on** (`tasks._payload_clearance`, print-only):
it hard-coded `rail = belt_top + 0.035`, so it was blind to
`FRUIT_OUTPUT_RAIL_HEIGHT` **and** to a removed rail — cell A would have printed
the shipped +30 while the true clearance was +65 (P69 `B_PREREG.md` §2.3 named
this as the cell's precondition). It now reads
`output_rail_keep[0]` and `belt_top + output_rail_proud`; at the shipped geometry
the reported surface is the same to **1e-12 m** (the row prints mm), and with no
inner rail it falls through to the belt top. The `@rail`/`@obelt` code in every
row says which surface was used, which is why the cells are readable.

---

## 3. Task 3 — the cells (scripted line, 10 attempts, one claim each)

`scripts/20_pick_place.py`, `ATTEMPTS=10`, `HEADLESS=1`,
`FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1`, `scripts/154_claim_run.sh`
(`logs/p70/run_cells.sh`; C → A → B, ~4.7 min each).

| arm | env | attempts | placed | s/attempt | held place legs | **`clr`** | **`clr_win`** | loaded slide (>800 mm) | place ticks |
|---|---|---|---|---|---|---|---|---|---|
| **C** | shipped `both`, 1.35 | 10 | **6/10** | 15.00 | 6 | **+30..+120** @rail | **+29..+96** | 4/10 | 3121 (312/leg) |
| **A** | `RAILS=none`, 1.35 | 10 slots, 9 attempted (1 starved) | **6 placed** (6/9) | 14.80 | 6 | **+65..+156** @obelt | **+64..+113** | 3/9 | 2759 (307/leg) |
| **B** | `RAILS=none`, **1.31** | 10 | **4/10** | 15.20 | 4 | **+126..+167** @obelt | **+91..+108** | 6/10 | 3333 (333/leg) |

**The 1:1 proof, leg by leg.** Attempt 2 is the **same 5.6 cm kiwi** on the same
left arm in C and A, and it crosses at the **same tick**:

| leg | C (rails) | A (no rails) | Δ |
|---|---|---|---|
| ep2 left `place0` kiwi | `clr=+30@rail/t275`, `clr_win=+29@rail/t270` | `clr=+65@obelt/t275`, `clr_win=+64@obelt/t270` | **+35 / +35** |
| ep4 right `place1` lychee | `+99@rail/t133` / `+84@rail/t152` | `+136@obelt/t135` / `+107@obelt/t191` | +37 / +23 (the tick moved: branch) |
| ep5 right `place1` strawberry | `+112@rail/t176` / `+95` | `+135@obelt/t178` / `+110` | +23 / +15 |
| ep6 right `place1` pear | `+120@rail/t169` / `+96` | `+155@obelt/t169` / `+100` | +35 / +4 |
| ep7 (C) → ep8 (A), strawberry | `+109@rail/t136` / `+95` | `+156@obelt/t168` / `+113` | +47 / +18 |
| ep8 (C) → ep9 (A), apple | `+90@rail/t153` / `+75` | `+126@obelt/t152` / `+93` | +36 / +18 |

Only ep2 has both a matching tick *and* the same fruit, and it reads exactly the
rail's proud height; the others differ because the branch moved *inside the leg*
(a climbing window minimum lands at a different tick).

**The classes and the cost.** Every arm's escapes are the closed left loaded-slide
class (`logs/p42/SIM_LIMIT.md`): `clean_slip` 979-1454 mm, `contacts@onset` 0-2,
`force_min=0.00 N`, `loss_row` 2-114, i.e. the payload was never seated or left in
the first ticks — the same signature in C (4 legs: `loss_row` 2/3/3/104) and A (3) and B
(6), and B's left is **0/6 held** against C's 1/5 and A's 1/4 (three draws of the
same class, not a new one). The right arm holds every leg in all three arms
(C 6/6, A 6/6, B 4/4); its crossing moves with the surface only.

**Motion.** `scripts/105_motion_regression.py` on each log: the worst descent is
`|v|max 0.1100 m/s` against a `0.160-0.161` budget and `lurch 0.017 m/s/tick`
against `0.291` — **identical in all three arms, no budget violation**; the
`FAIL` each log reports is the standing **rate floor** (C 6/10, A 6/9, B 4/10 - all
below 75 %, the tree's recorded branch since P32). **C's fingerprint `matches
configs/motion_reference.json`**, A and B are different attractors (`leg 6
[90, 0.109]` vs the reference `[90, 0.108]`) — the scene's shape set moves the
solver ordering, exactly P30-A's finding, which is why no count here is a rate.

**Tray and despawn**: `diverted=0`, `recirculated=0`, `gate_open=0.0 s`,
`queue_peak=0` in all three; `discharged` (the `[belt] ... to the tray` rows)
**C 5, A 4, B 4** out of 6/6/4 placed — the remainder are fruit still on the belt
when the run ends (the belt needs ~17 s to the tray). **No `fell off` event line
in any arm.** The spawner's `fell_off` counter prints only inside a starvation
census row; A prints one (17 of 23 released) because its slot 7 starved and C/B
never print it, so it is not comparable across arms — and it is not a rail effect
(the slab's underside sits 130 mm above the tallest main-belt fruit at 1.35 and 90 mm at 1.31, its own build print).

**No-harm.** Cell C is the **same-batch control on this tree** and its 457
`[fruit]` lines are **byte-identical to the P69 G0 control** (`logs/p69/g0/
t080.log`), i.e. the new scene knob and the instrument fix are byte-inert on the
scripted line, and `accept.sh`'s fingerprint still matches.

---

## 4. The release-ledge census (where the 2.3 % would go)

Each attempt's `[task] target` row gives the species and diameter, and the
`[task] over the output belt` row the payload's own `(x, y, z)` at the start of
the release block — so the release's lateral position is measured, not assumed.

| arm | release rows | **in hand** | over the slab | **centre in the ledge band (0.400-0.425)** | inboard of 0.400 | margin to the slab's inner edge |
|---|---|---|---|---|---|---|
| C | 10 | 6 | 6/6 | **0** | **0** | **+0.117..+0.122 m** |
| A | 9 | 6 | 6/6 | **0** | **0** | **+0.117..+0.122 m** |
| B | 10 | 4 | 4/4 | **0** | **0** | **+0.116..+0.122 m** |

The other 14 rows are payloads already on the main belt (`z = 1.19-1.20`, the
left's escaped class), not releases.

**So: no release in this batch lands on a ledge, and none lands where a ledge
would be needed.** The delivered place point is `|y| ≈ 0.542-0.547` — the
commanded 0.50 plus the arm's outward overshoot at its reach boundary — i.e.
**~12 cm outboard** of the fence. The 2.3 % class of P30-A's ledger is a property
of the pooled population (10 195 releases across many configurations, including
the low-transfer arms), and it is not this scenario's.

**Where the 2.3 % would go with no rail:** nowhere good — the band
`0.400 < |y| < 0.425` has **no authored surface** once the box is gone (the slab
starts at 0.425, the main belt is 180 mm below), so a release whose centre lands
there falls to the main belt and is scored `placed=False` (`on_output_belt`
requires `z >= T - 0.06`). With the rail it lands on the fence's 25 mm top face,
**35 mm above the belt**, and scores `placed=True` — that is a *box test*, not a
delivery: a fruit parked on a static fence 35 mm above the belt surface cannot be
carried by the belt, so P30-A's "96.6 % placed" is a `placed` score, not a
`discharged` count, and this corpus does not separate the two (the runs discharge
4-5 of their 6 placed). **The ledge's real delivered value is therefore at most
its `placed`-minus-`discharged` gap, and it is unmeasured on this interface**;
what is measured is that removing the rail costs **0 of 16** in-hand releases
*here* because none of them is in the band.

---

## 5. Task 4 — the direct line, the low lift

The low lift (`FRUIT_LIFT_DZ=-0.08`, lift end 1.370 m) is the only measured lever
that fixes the left's 25 deg carry rotation (P66 phase 3: left placed 0/25 → 14/25
at N = 5), and it failed the crossing at the rail (`+5 / +0 mm`, P66 phase 4). So
the question is whether the rail's removal is what lets it ship. Two arms, one
seed, the P66 phase-4 scenario verbatim (all-A supply, so every episode is a left
place leg), 15 episodes, `moe_v13s`, `FRUIT_MOTION_REPORT=1` on **both** arms (the
`|a|max` contact channel), ~520 s wall each:

| arm | env | placed | classes | place legs | held | `clr` (own surface) | **at the slab's inboard edge** | counterfactual `@rail` |
|---|---|---|---|---|---|---|---|---|
| **D0** | rails `both` + low lift | **6/15** | 6 cnp-loaded-slide, 2 cnp-other, 1 never-held | 14 | **3** | +7, +16, +17 @rail | +11, +20, +21 | — |
| **D1** | rails `none` + low lift | **10/15** | 3 cnp-loaded-slide, 2 never-held | 13 | **10** | **−1..+54** @obelt | **+3..+58** | **−36..+19** |

**The removal is exactly what the low lift needed, and it is not enough.**

* **The object the low lift was hitting is gone.** D1's ten held legs cross at
  `clr` −1..+54 mm against the *belt top plane*; had the rail been authored, the
  same ticks would read **35 mm less — −36..+19 mm**, i.e. **9 of 10 legs at or
  below the rail's top face** (6 of them 9-36 mm below it, inside the box) and
  9 of 10 inside G0's contact band (`clr <= +7`). The one clean leg (+19) is the
  only one that never needed the room. That is the quantitative statement of why
  P66/P67 kept losing payloads on this rung: the low lift's crossing population
  sits *inside* the rail.
* **The residual is the slab's inboard edge, at +3 mm on the worst leg.** Adding
  the transit's own slope (`(1.530 − 1.370)/0.50 = 0.32` m of z per m of y, i.e.
  **+4.0 mm** over the 12.5 mm from the rail's centreline to the slab's edge, an
  estimate from the straight-line leg and conservative because the body that
  actually overhangs the edge is higher than the payload's lowest point), the
  population is **+3..+58 mm** and **5 of the 10 legs are below the +33
  convention**. The worst leg (ep8, `clr −1`, edge ~+3) shows **no contact**
  (`|a|max 0.98 m/s²`, `slip 0.4 mm`, `force_min 8.11 N`) — so it is a graze, not
  a hit — but by G0's bracket (`contact at clr <= +7`) it is inside the band the
  instrument cannot certify, and there is nothing left in the belt height to buy
  it (`0.175 mm/mm`; the audit caps the dose at 40 mm = +7 mm).
* **The counts are two draws, not an effect.** D0 6/15 and D1 10/15 are two
  samples of a loop that is not bit-reproducible, and D0's 11 of 14 place legs
  never reached the crossing at all (payload lost at or before the lift), so its
  3 held legs are a *selected* population — the pair cannot support "the removal
  adds four placements". It is consistent with "no harm", which is all that is
  claimed.
* **The right arm is not exercised by this cell.** P67's all-A supply makes every
  episode a left leg (`rl_env` sets `arm = left if grade == A`), and
  `resolve_lift_dz` emits `{"left": dz}` only — so "the right unchanged" is read
  on the **scripted** cells, where the right holds every leg (C 6/6, A 6/6, B
  4/4) and its crossing moves only with the surface (+35 mm), and structurally
  from the left-only resolver. A same-fork right-arm read at the low lift needs
  P66 phase 4's mixed supply (right `clr +50 [+33..+79]` there) and was **not
  run**.

**Verdict for the low lift**: the rail's removal is the piece it was missing
(it deletes the object 9 of 10 legs were crossing at or below), and the rung is
still **not certified** — the marginal clearance moved from the rail's 25 mm
shelf to the slab's inboard edge at **+3 mm** on the worst leg. The named lever
that remains is P69-B's **option 2a** (a place-only raised transfer, `0.825:1`:
+36 mm needs 1.530 → 1.566, i.e. the place *target* over the left's reach
boundary, unmeasured).

---

## 6. What this does not measure, and the named residuals

* **One draw per arm.** Every count above is a quantised outcome of a moved
  branch (P30-A's precedent, reproduced here: the `carry-assist` command diverges
  at the 1e-4 m level from attempt 1). The *geometric* quantities — the crossing
  `clr`/`clr_win`, the release's `|y|`, the build print — are one-leg/one-scene
  measurements and do not need a rate.
* **The ledge class is untested, not measured-zero.** This scenario's releases
  are 12 cm outboard of the fence; a scenario that lands releases in
  `0.400-0.425` would exercise it, and there the rail's absence is a
  fall-vs-park difference. `logs/p69/B_PREREG.md` §8's G2 fixture
  (`FRUIT_PLACE_LOW=0 FRUIT_OUTPUT_PLACE_Y=0.4125`) is the instrument for it and
  was **not run** (it needs a forced release point, a different scenario).
* **The height change is only bounded, not recommended.** At 1.31 the underside
  audit reads `0.000 m` at the instance scale: a tallest-instance pear on the
  main belt would touch the slab. Nothing in this batch shows a supply
  disturbance attributable to it (A's and B's starvations differ), but one draw
  cannot rule it out, and the same-instant census that would is a different cell.
* **The two-line and the hybrid canary share the `SceneConfig`** and were not run
  with either knob; a lowered belt would move their geometry identically.
* **The rail height knob (`FRUIT_OUTPUT_RAIL_HEIGHT`) was left alone.** G0's
  measured dose for contact-freedom is 0.037-0.039 (+11-13 mm, 22-24 mm of lip
  kept); with the rails *removed* that question is moot at the crossing, but it
  is the smaller change if the ledge must be kept (P69-B's registered option 1).
* **`clr_win` has no upper `|y|` bound** (`tasks.py`: it is the minimum from the
  rail's inner face to the *end of the leg*), so with the rail gone a negative
  `clr_win` read **inboard of 0.425 is not a contact** — there is no surface
  there. Read `clr_win` against the surface code each row prints, and for the
  no-rail case read the **slab's edge** (the `+4 mm` estimate §5 uses), not the
  window minimum.
* **The direct pair straddles a source change** (a concurrent P71 lane adopted
  the rails' default between D0 and D1). Both arms' *geometry* is explicit and
  proved from inside each log, but they are not a same-source pair:
  `logs/p70/TREE.md`.
* **The direct line's systematic sag is what keeps the low lift marginal**: on
  D1's held legs `dz_end` is **−25..−32 mm** and `res_end` **28-34 mm**, i.e. the
  arm holds 25-32 mm *below* the commanded height at the place leg's end. Those
  30 mm are most of the 35 mm the rail's removal frees, which is why the slab's
  edge lands at +3 mm on the worst leg.

---

## 7. Pins and reproduce

```bash
bash logs/p70/run_cells.sh                      # C -> A -> B, one claim each (~14 min)
python3 logs/p70/p70_report.py --check logs/p70/{C,A,B}.log > logs/p70/p70_report.txt
bash logs/p70/run_direct.sh                     # D0 -> D1 (~18 min)
python3 logs/p70/p70_direct_report.py --check logs/p70/direct/{D0,D1}.log
scripts/selfcheck.sh                            # the 238 leg
```

**A concurrent lane adopted part of this while it was being written**, so read
these pins together with `logs/p70/TREE.md`: a **P71** session flipped
`FRUIT_OUTPUT_RAILS`' default to `none` and `LIFT_DZ_DIRECT_DEFAULT` to `-0.08`
at 08:58-09:07, i.e. **between the direct pair's two arms** (both arms set the
lift explicitly and the rails explicitly/at the then-default, which each log
proves from inside via `@rail` vs `@obelt`). `run_cells.sh` and `run_direct.sh`
now pin `FRUIT_OUTPUT_RAILS=both` for their control arms, and `238` names the rail
mode explicitly, so all four cells re-run unchanged after P71.

**Pins as measured** (md5 first 6; `logs/` is gitignored — `git add -f` at the
close-out): `logs/p70/C.log` **`de8c73`**, `A.log` `62e280`, `B.log` `9f3391`,
`direct/D0.log` **`9455bd`**, `direct/D1.log` **`fabe21`**, `p70_report.py`
`3cf531`, `p70_report.txt` `bb01a6`, `p70_direct_report.py` `5006c5`,
`p70_direct_report.txt` `01ab48`, `run_cells.sh` `c60fdd` at batch time / **`0754a9b5`** now (it also names C's
rail mode), `run_direct.sh` **`0a05028d`**, `header.txt` `befae7`, `TREE.md`
`fddc2e`;
`src/fruit_sorting/tasks.py` **`7c00e5`** (the whole diff is P70's
`_payload_clearance`), `assets.py` **`9e9804`** (P70's knob + inset + proud
property; **`e9fd7410` after P71's default flip**), `conveyor.py` `fb2c58` (the
shared inset), `rl_env.py` `588669` (**`cb686f5e` after P71** — the P70 change
there is the `TASKS_MD5` metadata-only follow);
`scripts/238_p70_belt_top_selftest.py` **`2cccebb3`** (P70 as delivered),
`scripts/selfcheck.sh` `5a31a0`. `configs/motion_reference.json` **`8a399626`** and
`configs/motion_reference_twoline.json` **`2246f83c`** untouched; checkpoint
`moe_v13s` **`61da390a`**. **P70 adopted nothing, moved no default, re-recorded
no reference and made no commit**; the default moved afterwards in P71's lane,
and `scripts/selfcheck.sh` is PASS with both lanes' edits (the `238` leg names
the rail mode explicitly so it survives the flip).
