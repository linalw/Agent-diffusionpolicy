# P71 — the adoption package: the output rails removed, the low lift as the direct default

Owner-authorized package (方案 b, `logs/p70/RESULTS.md`'s verdict): **remove the
output belts' side rails** (1:1 with the crossing, 35 mm) and **keep the belt
height at the shipped 1.35** (the height is a 0.175:1 lever that costs
placements). The low direct lift - the only measured lever that fixes the left
arm's 25 deg carry rotation (`logs/p66/P3_RESULTS.md`: left 0/25 -> 14/25 at
N = 5) - failed its own rail-crossing gate (`+5 mm` against the +33 floor),
which is why it had been reverted at P66 P4.

**Verdict: both flips are live.** The rail flip is behaviourally inert on the
scripted line's *classes* (same placed count, no contact signature) and moves
its motion reference; the lift flip resolves as the direct presentation's
default and the left's carried-not-placed class converts at the population level
**4/20 -> 10/17 placed (one-sided Fisher p = 0.018), loaded-slide legs 15 -> 7
(p = 0.039)** - a weaker read than P66's N = 5 (0/25 -> 14/25), and the right's
placed count is unchanged (22 in both arms). **The crossing clears the obstacle
that remains, not the one the clause was written against**: the low lift passes
35 mm *below* where the rail top was (so P66's `+33 at the rail` gate fails
0/10 and always would have), and **+14..+50 mm above the slab's top edge**, the
surface it actually crosses - median +35, 8/10 at or above the convention,
against the pre-P71 line's **+24..+45** to its rail. **There is no contact
signature in either arm** (`|a|max` 0.31-8.69 m/s² against G0's 14.9-32.7 m/s²
contact population; max held slip 20.3 mm). Both motion references were
**re-recorded** from the same-batch shipped-scenario runs; the control arms
replay the archived pre-P71 files byte-identically, so the moves are the flips'.

Tree: `tasks.py` **`7c00e5`**, `assets.py` **`e9fd74`** (the rails default),
`conveyor.py` `fb2c58`, `rl_env.py` **`cb686f5`** (the lift default),
`fruits.py` `c7461d41`, `scene.py` `27e3d64a`; checkpoint `moe_v13s`
`61da390a`. Refs: `motion_reference.json` `8a399626` -> **`8952c320`**,
`motion_reference_twoline.json` `2246f83c` -> **`eb697f23`**.

---

## 0. The two flips

| # | knob | before | **after (shipped)** | restore | scope |
|---|---|---|---|---|---|
| 1 | `FRUIT_OUTPUT_RAILS` (`assets.SceneConfig`) | `both` | **`none`** | `FRUIT_OUTPUT_RAILS=both` | every path that builds the scene (scripted, two-line, collector, hybrid, direct) |
| 2 | `FRUIT_LIFT_DZ` (`rl_env.LIFT_DZ_DIRECT_DEFAULT`) | `+0.08` (= 0.36 m) | **`-0.08`** (= 0.20 m) | `FRUIT_LIFT_DZ=+0.08` | `direct` presentation, **left arm only** |

Both are the measured values, not new behaviour:

* **The rail flip is P70's cell A** (`logs/p70/RESULTS.md` §3): the same 5.6 cm
  kiwi on the same arm at the same tick reads `+30 @rail / t275` ->
  `+65 @obelt / t275`, **+35.0 mm**, and its held population `clr` +30..+120 ->
  +65..+156 with the same placed count (6) and no contact signature.
* **The lift flip is P66's phase-3 rung** (`logs/p66/P3_RESULTS.md`): `drift_end`
  25.1 -> 0.7 deg and left placed 0/25 -> 14/25 at N = 5, with the crossing at
  `+5 mm` **at the rail**. P66 P4 reverted the default because of that gate; P71
  removes the gate's *obstacle* instead of paying for it with a place-leg
  re-shape (P67's climb clears the crossing and drops 8/16 payloads).

**Why 0.20 and not 0.24**: the two rungs are not separable (40.0 vs 56.0 %,
Fisher ~0.28) and 0.24 was the "economical" pick - but the *only* reason P66 P4
rejected 0.20 was the rail crossing, and with the rail gone 0.20's crossing is
the shallower of the two problems. The record's reference rung (`L2`, the one
measured at N = 5 for the drift and the crossing) is **0.20**, so the package
ships the rung the evidence is about; `-0.04` stays available as an explicit arm.

Both defaults are pinned by the offline checks (`scripts/236_p66_lift_selftest.py`
now asserts `LIFT_DZ_DIRECT_DEFAULT == -0.08` and `resolve_lift_dz("direct",
None) == ({"left": -0.08}, True)`; `scripts/238_p70_belt_top_selftest.py`
asserts the `none` default through the env-read `default_factory`, that an unset
config reads exactly like an explicit `none`, and that `=both` restores the pair).
`scripts/selfcheck.sh` PASS, 0 failures.

---

## 1. Phase 1a — the scripted acceptance (10 attempts, one claim per arm)

`scripts/accept.sh` (`FRUIT_MOTION_REPORT=1`, `HEADLESS=1`); the control sets the
pre-P71 geometry explicitly so the pair is same-batch and same-tree.

| arm | env | attempts | placed | s/attempt (sim) | `[fruit]` lines | `configs/motion_reference.json` |
|---|---|---|---|---|---|---|
| **ctrl** | `FRUIT_OUTPUT_RAILS=both` | 10 | **6/10 = 60 %** | 15.0 (150.5 s) | **377** | **`fingerprint: matches`** |
| **treat** | (default `none`) | 9 (1 slot starved) | **6/9 = 67 %** (6/10 slots) | 14.8 (133.6 s) | **346** (344 + 2 build prints) | **DIFFERS** -> re-recorded (§5) |

* **The control is byte-identical to the pre-P71 archive and to P70's same-tree
  cell C**: its 377 `[fruit]` lines are 377/377 identical to
  `logs/p66/p2/accept_noharm.log`, and its **357 non-clearance `[fruit]` lines are
  357/357 identical to `logs/p70/C.log`** (P70's rails-on control, same tree, same
  10 attempts, `FRUIT_CARRY_DIAG` on - its stream is a superset by the diag rows),
  with the same **6/10** placed. It also matches the archived reference
  `logs/p71/motion_reference_single_pre_p71.json` (`8a399626`). So the new tree is
  **inert with the old geometry restored**, and everything the treatment shows is
  attributable to the flip.
* **The treatment moves the branch, by 8 mm.** After dropping the two build
  prints (`[fruit] output belt rails P/N: ... authors 0/2 ... inner ... REMOVED`)
  and the report-only clearance rows, the first difference is a **release y**
  0.595 -> 0.603 m (8 mm) at stripped line 121, i.e. the scene's collider set
  moving the solver ordering - P30-A's own precedent for a geometry edit of this
  size. 171 of 326 stripped lines are identical at the same index; the 31-line
  count difference is the ninth attempt (one slot starved) plus the two prints.
* **Every report-only clearance row shifts by exactly the rail's proud height**:
  e.g. `-219 mm to the output rail` -> `-184 mm to the output belt` (+35).
* **Motion is unchanged**: worst `|v|max` 0.1100 m/s (budget 0.160-0.161), lurch
  0.017 m/s/tick (budget 0.291) **identically in both arms**; the `FAIL` each log
  reports is the standing rate floor (6/10 is below 75 %, the tree's recorded
  branch since P32). `diverted=0`, `gate_open=0.0 s`, `queue_peak=0` in both.
* The two-line and the acceptance both ran with the *same* `SceneConfig`, so the
  scripted path is **not** inert to flip 1 - only flip 2 is (it is `rl_env`-only,
  the scripted entry points never construct `SortingRLEnv`). That is why the
  identity check that used to serve as an "import guard" (P40/P41's 377/377) now
  **has to move**, and it does: see §5.

---

## 2. Phase 1b — the two-line (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`, 10 attempts)

| arm | placed | left / right | s/attempt (sim) | `diverted` | `190_twoline_gate.sh` |
|---|---|---|---|---|---|
| **ctrl** `RAILS=both` | **8/10** | 4/5, 4/5 | 9.8 (98.0 s) | 0 | **PASS**, `fingerprint: matches` `2246f83c` |
| **treat** (default) | **7/10** | 4/5, 3/5 | 9.2 (92.4 s) | 1 | **PASS** after re-record (`matches` `eb697f23`) |

The treat arm's fingerprint moved on **legs 3, 4, 5, 7, 8, 10** by 1-3 ticks and
0.002-0.004 m/s (the reference's `[samples, |v|max]` pairs), i.e. the same
"scene shape set moves the solver ordering" effect, not a corpus change. Both
arms are at or above the 0.60 two-line floor; they are **different attractors**,
so the 8 vs 7 is not a rate comparison (AGENTS §2).

The two-line's own clearance report (the `[motion] carry … clearance` leg
minima) shows the geometric shift directly: the ctrl's tightest place leg reads
**`+32 mm output rail`** (just under the +33 convention) while the treat's
same-family rows read **`+63..+101 mm output belt`**.

---

## 3. Phase 2 — the direct line, both flips in effect, N = 3 seeds x 15 picks per arm

The registered cell for this lever, verbatim from P66 phase 3
(`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`,
`FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25`, `FRUIT_POLICY_TRIGGER=arrival`
lead 0.9, `FRUIT_DYNAMIC_PICK=1`, policy seed 11, `FRUIT_BED_DIAG`,
`FRUIT_CARRY_DIAG`, `FRUIT_CARRY_ATTITUDE`), **plus** `FRUIT_MOTION_REPORT=1` on
both arms for the G0 contact channel (a reporting read; it is identical in both
arms, so it cannot confound the pair). Seeds 77/101/202, interleaved
ctrl -> treat, one claim per run, `moe_v13s` `61da390a` on both arms.

The flip is proven in-log by the `[grasp] lift_dz:` row: treat reads
**`dz=-0.0800(default) -> 1.3700 m`**, ctrl reads
**`dz=+0.0800(explicit) -> 1.5300 m`**; both print
`park=back(default)` (P43) and `tasks_md5=7c00e555`.

### 3.1 Outcomes

| arm | placed | **left** | right | loaded slides (>800 mm) | never-held | sim span |
|---|---|---|---|---|---|---|
| **ctrl** (rails both, 0.36 lift) | 26/45 = 58 % | **4/20 = 20 %** | 22/25 = 88 % | **16**/42 place legs | 3 | 15.08 s/episode |
| **treat** (P71 defaults) | 32/45 = 71 % | **10/17 = 59 %** | 22/28 = 79 % | **6**/39 place legs | 6 | 14.78 s/episode |

Per seed (left placed): 77 **2/8 -> 4/5**; 101 **2/6 -> 2/6**; 202 **0/6 -> 4/6**
(2 of 3 improved, 1 tie - run-level sign p = 0.25). Pooled one-sided Fisher:
**left placed p = 0.018**, **left loaded-slide legs 15 -> 7, p = 0.039**,
overall placed 32/45 vs 26/45 p = 0.135.

* **The right's placed count is unchanged** (22 in both arms). The treat arm has
  3 more right attempts (28 vs 25) and the 3 extra failures are
  **`fruit fell off the line`** - right-arm kiwis (6.3 cm) and a 4.0 cm
  strawberry that were **never grasped** and rode to the main belt's end
  (`grasped=False`, `decision = ticks`). That is the recorded supply tail
  (already in `logs/p66/p3/C20_77.log`, 2 instances), not a grip/place class,
  and it is the *left's* faster cadence re-timing the shared feeder, not the
  flip's arm.
* **No new failure class**: the ctrl's failures are all the intercept-trigger
  note + carried-not-placed; the treat adds only the 3 supply-tail rows above.
* **The surviving treat losses are later in the leg**: the treat's 6 loaded
  slides are all `left place0` with `loss_row` **103-150** (payload held through
  the transit, lost in the place leg) while most of the ctrl's 16 are
  `loss_row` **1-4** (never seated). So the package does not just delete legs
  from the class, it moves the survivors to the closed `SIM_LIMIT.md` place
  phase.
* The **P70 D0/D1 pair** - the same all-A cell, seed 77, one run each, the
  **rails** isolated at the low lift with no other change - reads
  **6/15 -> 10/15 left placed**, loaded slides **6 -> 3**, and the crossing
  `+3..+13 mm @rail` (clr_win, rails on) -> `-6..+50 mm @obelt` (rails off),
  i.e. the removed rail's 35 mm plus a ~20 mm population shift between the two
  branches' fruits. That is the rail flip's own attribution on the carry class.

### 3.2 The crossing: the +33 mm access clause against the obstacle that exists

The clause (`logs/p30a/RAILS_DESIGN.md`, reused by P66's gate (a)) is **+33 mm at
the rail's centreline**, measured against the **rail top** (`belt_top + 0.035`).
Two facts have to be kept apart:

1. **Removing the rail does not raise the payload.** The same trajectory reports
   **35 mm higher** because the reference surface dropped by the rail's proud
   height. So the low lift's left legs read **`clr` +14..+50 mm against the belt
   top** and would have read **-21..+15 mm at the rail top** - which is exactly
   P66 P4's `+5 / +0` and P70 D0's `+7 / +16 / +17`. **The clause at the rail top
   is failed by the low lift on 0/10 legs, and no geometry change can make it
   pass; only a higher lift or a higher transfer can, and both were measured
   negative** (P66 P4, P67/P68).
2. **The rail is gone, so the obstacle it measured is gone too.** The surface that
   remains at the crossing is the slab's inboard top edge (the belt-top plane),
   and against *that* the package's margin is the number that matters.

Measured on the **held** place legs (`logs/p71/p71_report.txt`):

| arm | arm | n | `clr` to its own obstacle (range / >= +33) | `clr_win` (range / >= +33) | at the rail top >= +33 |
|---|---|---|---|---|---|
| ctrl (rail top) | **left** | 4 | +24..+45 / **2/4** | +23..+43 / **1/4** | 2/4 |
| ctrl (rail top) | right | 22 | +36..+58 / 22/22 | +35..+58 / 22/22 | 22/22 |
| treat (belt top) | **left** | 10 | +14..+50 / **8/10** | +10..+45 / **4/10** | **0/10** |
| treat (belt top) | right | 22 | +69..+138 / 22/22 | +69..+119 / 22/22 | 22/22 |

* **The package's left margin to the obstacle that exists is the +33 clause's own
  order**: `clr` median **+35**, 8/10 at or above it (the window minimum `clr_win`
  reads +10..+45, median **+30.5**, 4/10) - against the pre-P71 line's **+24..+45,
  median +31, 2/4** to *its* obstacle. The two configurations sit at the same
  margin; the package has 2.5x more held left legs to show it on (10 vs 4), which
  is the carry conversion, and its minimum is lower (+14 vs +24) because its
  population is bigger.
* **The clause as briefed literally fails**: 2/10 left legs read `clr` +14 / +26
  and 6/10 read `clr_win` below +33. The reason is not a regression - the same
  band is what the shipped line's own left legs occupy (+24..+45) - but it means
  **the crossing is at the convention, not above it**, and the named fix for a
  literal margin is a slab-edge instrument, not a re-signed floor (§6).
* **No contact in either arm**: the held legs' `|a|max` reads **0.31-8.69** (treat)
  and **1.36-6.21** (ctrl) m/s² against G0's measured contact population of
  **14.9-32.7 m/s²** (with 27-76 mm of displacement); the largest held-leg
  `clean_slip` is **20.3 mm** (treat, seed 77 ep13) and 15.9 mm (ctrl). In the
  package's frame G0's contact boundary (`clr <= +7 mm` at the rail top) sits at
  **-28 mm**, so the worst held leg (+14) is 42 mm above it.
* The treat's negative `clr_win` (-6) belongs to a leg that **placed** with
  0.4 mm slip and 0.98 m/s²: at that tick the payload's centre was 12.5-25 mm
  inboard of the slab's edge (a void), which the instrument charges as if the
  plane were there. It is conservative by construction.

**So: the package's crossing clears contact with margin and sits at the +33
convention against the remaining surface (median +35, 8/10); it fails the clause
at the rail top on 0/10 - as it must, since the payload passes 35 mm below where
the rail top was - and the pre-P71 line only meets it on 2 of its own 4 left
legs.** If a literal +33 at the rail top is required, the shipped 0.36 lift is
the only measured configuration that gives it (P70 cell A: +65..+156) and it is
the one that carries the left at 0/25. That trade is the whole of P66-P71.

---

## 4. What moved, and why (the attribution ledger)

| run | what changed | why |
|---|---|---|
| acceptance ctrl vs archive | **nothing** (377/377 identical, fingerprint matches) | flip is inert with `RAILS=both` |
| acceptance treat vs ctrl | 8 mm release y at stripped line 121; +35 mm on every clearance row | the collider set moved the solver ordering (P30-A precedent) + the new surface |
| two-line ctrl vs archive | **nothing** (fingerprint matches) | same |
| two-line treat vs ctrl | legs 3,4,5,7,8,10 by 1-3 ticks | same |
| direct treat vs ctrl | left 4/20 -> 10/17 placed, 15 -> 7 loaded-slide legs | the low lift's attitude hold (P66) |
| direct ctrl `|a|max` vs treat | 1.36-6.21 vs 0.31-8.69 m/s² (both non-contact) | the rail is not an obstacle in either arm on these legs |

---

## 5. Re-records, archives, and what is now pre-P71

**Both motion references were re-recorded from this batch's shipped-scenario
runs** (the control arms' matches prove the move is the flip's, not the tree's):

| file | pre-P71 (archived) | **shipped now** | source |
|---|---|---|---|
| `configs/motion_reference.json` | `8a399626` -> `logs/p71/motion_reference_single_pre_p71.json` | **`8952c320`** | `logs/p71/accept_rails_none.log` (6/9, budgets pass, rate-only fail) |
| `configs/motion_reference_twoline.json` | `2246f83c` -> `logs/p71/motion_reference_twoline_pre_p71.json` | **`eb697f23`** | `logs/p71/twoline/none.log` (7/10, `190` PASS) |

The single-arm reference now carries **9** legs (the treatment's starved slot), so
a pre-P71 10-attempt log cannot match it - gate such a log against the archive
explicitly (`--fingerprint logs/p71/motion_reference_single_pre_p71.json`).

**Re-baseline.** Every pre-P71 number is a `both`-rails + **0.36 m lift** number.
To reproduce one, restore both: `FRUIT_OUTPUT_RAILS=both` (scene, all paths) and
`FRUIT_LIFT_DZ=+0.08` (direct only), composed with the earlier restores
(`FRUIT_ARM_PARK=ready` for pre-P43, `FRUIT_POLICY_TRIGGER_ACQ=0` for pre-P54,
`FRUIT_FEED_CADENCE=0 FRUIT_SUPPLY_BAND_INTERLOCK=0 FRUIT_DIRECT_FEED=0` for the
pre-P58 burst supply). Stores recorded under either geometry must not be mixed
with a pre-P71 one: the rail set is part of the scene's collider graph (a
manifest has no field for it - **named gap**, the `physics` block covers the
finger drive only) and the direct lift already carries its own
`lift_dz`/`defaulted` manifest fields.

**No-hybrid-path claim**: `accept_policy.sh` / `60_eval_policy.py` build their own
`SceneConfig`, so the **hybrid canary inherits the rail flip** (it shares the
scene) and **not** the lift flip (that is `SortingRLEnv`-only). The canary was
not re-run in this phase - its shipped scenario is the pre-v9 fixed supply and its
recorded spread is 5-8/10, which the rail flip does not move by any measured
mechanism; that is a **smoke owed**, not a measurement made.

---

## 6. What this does not measure, and the named residuals

* **One draw per arm** for every count here (the direct loop conditions on
  rendered frames; the scripted line is deterministic only per configuration).
  The p-values above are population contrasts inside one batch, not rates; the
  P66 N = 5 read (0/25 -> 14/25) and this N = 3 read (4/20 -> 10/17) are the same
  direction at different magnitudes, and per-seed one of three is a tie.
* **The +33 clause has no measured contact boundary in the new frame.** G0's
  calibration is against the rail top; the slab's inboard top **edge** is a
  corner, not a face. The named instrument is a `clr_edge` sample at
  `|y| = 0.425` (report-only, same per-tick pair) - it would replace the
  conservative plane reading at the crossing.
* **The ledge class is untested, not measured-zero**: with the rail gone, a
  release whose centre lands in `0.400 < |y| < 0.425` has no surface under it and
  falls (P70 §4). No release in the two scripted batches lands there (16/16
  in-hand releases are 116-122 mm outboard), and the G2 fixture that would force
  one (`FRUIT_PLACE_LOW=0 FRUIT_OUTPUT_PLACE_Y=0.4125`) was again **not run**.
* **The belt height stays at 1.35** by P70's verdict (0.175:1 and it spends the
  40 mm under-slab audit); nothing here re-tests it.
* **Wall cost**: the direct batch's wall is 503.9-518.6 s (ctrl) vs
  530.4-548.2 s (treat) per 15 picks at a **lower** sim span (15.08 -> 14.78
  s/episode) - a harness cost (more live bodies/placements), reported, not gated
  (P58's convention).
* The **collector/two-line-camera** paths were not re-collected: a post-P71 store
  is a new scene and needs its own A/B (`logs/p37/`'s rule).
* **Two out-of-tree probes read the output geometry by hand** and are stale until
  re-run with the config: `scripts/212_occlusion_map.py` (hard-codes
  `OUT_TOP_Z = 1.35`) and `scripts/461_release_probe.py:93` (`rim = floor + 0.035`,
  i.e. the rail). Neither is on a shipped path; with the rail gone the second one's
  `rim` is a phantom surface.

---

## 7. Reproduce, gates and pins

Gates on the final tree: **`scripts/selfcheck.sh` PASS, 0 failures** (one skip, the
motion-budget leg which needs a logged run); **`scripts/211_bed_audit.py` ok, 115
checks**; **`scripts/106_index_audit.py` OK** (every index matches its files);
**`scripts/107_collect_merge_test.py` PASS, 21 checks**; the two motion gates read
`fingerprint: matches` / `190 PASS` against the re-recorded references.

```bash
bash logs/p71/run_p71.sh                     # phase 1 (scripted) + phase 2 (direct)
python3 logs/p71/p71_report.py --check logs/p71/direct/{ctrl,treat}_*.log \
    > logs/p71/p71_report.txt
python3 logs/p71/accept_diff.py logs/p71/accept_rails_both.log \
    logs/p71/accept_rails_none.log --ref logs/p66/p2/accept_noharm.log
scripts/190_twoline_gate.sh logs/p71/twoline/{both,none}.log
python3 scripts/211_bed_audit.py
scripts/selfcheck.sh
```

Pins (md5 first 6; `logs/` is gitignored - `git add -f` at the close-out):
`logs/p71/accept_rails_both.log` **`5bbda1`**, `accept_rails_none.log`
**`0352e0`**, `twoline/both.log` **`da011f`**, `twoline/none.log` **`127241`**,
`direct/{ctrl,treat}_{77,101,202}.log` **`d9c807`/`a101e3`/`7cbfc0`** and
**`fe18b6`/`18ec13`/`024c98`**, `p71_report.py` **`2d5326`**, `p71_report.txt`
**`c04272`**, `run_p71.sh` **`73b3da`**, `header.txt` `dcdbc8`;
`src/fruit_sorting/assets.py` **`e9fd74`**, `rl_env.py` **`cb686f5`**,
`tasks.py` `7c00e5`, `conveyor.py` `fb2c58`;
`scripts/236_p66_lift_selftest.py` **`e6547e`**, `scripts/238_p70_belt_top_selftest.py`
**`2ccceb`**, `scripts/selfcheck.sh` **`9f7ee1`**; `configs/motion_reference.json`
**`8952c320`**, `configs/motion_reference_twoline.json` **`eb697f23`**; checkpoint
`moe_v13s` **`61da390a`**.
