# P72 — the canary smoke, the corner instrument, the new-frame boundary, the scene manifest

The four residuals `logs/p71/RESULTS.md` §5/§6 named, in the brief's order: the
hybrid canary's owed smoke, the missing `clr_edge` instrument at the output
slab's inboard edge, the boundary question the +33 mm convention no longer has
a surface for, and the scene's collider set having no manifest field. **No
`configs/` edit, no default change, no commit.**

Tree as measured: `tasks.py` **`f61323f2`** (the `clr_edge` instrument),
`assets.py` **`540406fa`** (`scene_provenance`), `rl_env.py`
**`92a25c8e`** (the `scene` block + the `TASKS_MD5` metadata-only follow),
`scripts/40_collect_demos.py` **`86b3d6ba`** (the shard's `scene` block),
`scripts/239_p72_clr_edge_selftest.py` **`c3027c4f`**,
`scripts/236_p66_lift_selftest.py` / `scripts/238_p70_belt_top_selftest.py`
re-pinned (below), `scripts/selfcheck.sh` **`cb4365d2`**;
`configs/motion_reference.json` **`8952c320`** and
`configs/motion_reference_twoline.json` **`eb697f23`** untouched; checkpoint
`moe_v13s` **`61da390a`**.

---

## 0. Verdict

1. **The hybrid canary is inside its recorded spread and the rail flip is not
   implicated.** `SKIP_SELFCHECK=1 scripts/accept_policy.sh` reads **8/10 =
   80 %** (floor 60 %, PASS) with **2 grip losses** (`fruit did not follow the
   gripper`) and **0 grasped-not-placed**; no failure reason is outside the
   recorded baseline set. The run **does** inherit the rail flip - its build
   print names it - and **cannot** see the lift flip (it never constructs
   `SortingRLEnv`; there is no `[grasp] lift_dz:` row). 8/10 is the **top of
   the interface's recorded 5-8/10 spread**, so it is a **sample, not a rate**,
   and it is not evidence of a rail effect in either direction.
2. **The corner instrument exists and reads on the shipped package, with no
   contact signature.** `clr_edge`/`clr_edge_min` are on the `[carry]` row under
   the same `FRUIT_CARRY_DIAG` flag, sampled at the output slab's **own inboard
   edge (0.425 m)** rather than at the removed rail's frame (0.400/0.4125). The
   shipped package's held place legs read `clr_edge` **+26..+109 mm (n = 10,
   median +77.5; the left's two legs +38 and +26)** and `clr_edge_min`
   **+26..+104 mm**, all against `@obelt`; every held leg's `|a|max` (max 4.49
   m/s²) sits below G0's 14.9 m/s² contact floor and every `clr_edge` is
   **> 0**.
3. **The new-frame boundary is a bracket, not a calibrated floor.** With no
   rail the binding surface is the slab's top plane **and its inboard edge**, so
   contact requires `clr_edge <= 0`; the one sub-zero *plane* sample on record
   (P70 D1 ep8, `clr = -1 mm @obelt / t247`) is taken **25 mm inboard of the
   surface** and carries no contact signature (`|a|max` 0.98 m/s², `sep_end`
   69.9 mm, slip 0.4 mm), while G0's measured **contact** population is
   14.9-32.7 m/s². The +33 mm convention was calibrated against a raised rail
   top and **has no counterpart surface** after P71. The shipped statement is
   `clr_edge > 0`, measured minimum **+26 mm**, with no contact.
4. **The scene's collider set now has a manifest field**, in both writers: a
   `scene` block (`output_rails` + the resolved `rail_keep` pair, `rail_height`
   / `rail_proud` / `rail_inset`, `output_belt.{top_z,y,size,inboard_edge_y}`,
   and the direct lift rung `lift = {dz, defaulted}` / `null` on a scripted
   shard). A pre-P72 store is identifiable by the key's **absence**; behaviour
   is unchanged (metadata only).

---

## 1. The hybrid canary smoke (the interface of record)

```bash
SKIP_SELFCHECK=1 scripts/accept_policy.sh        # logs/p72/canary_rails_none.log
```

The gate of record: `60_eval_policy.py`, `checkpoints/moe_v12/policy_best.pt`,
the pre-v9 **fixed** supply (`accept_policy.sh` sets `FRUIT_SUPPLY_SCATTER=0`),
ten episodes. It builds its **own** `SceneConfig`, so it inherits
`FRUIT_OUTPUT_RAILS=none`; it never constructs `SortingRLEnv`, so it does not
see `FRUIT_LIFT_DZ`. Both are proven in-log rather than assumed:

* the build print reads **`output belt rails P: FRUIT_OUTPUT_RAILS=none authors
  0/2 (inner y=+0.4125 REMOVED), height 0.050 m (top +1.3850, shipped)`** (and
  the same for the `N` belt), so the canary ran **the P71 scene**;
* there is **no `[grasp] lift_dz:` row** and no `[rl] env ready` row, i.e. the
  direct env was never constructed - the canary's lift is the hand's own add.

| # | fruit | d | bin | result | note |
|---|---|---|---|---|---|
| 0 | lychee | 3.1 cm | 1 | **ok** | |
| 1 | peach | 6.8 cm | 1 | **ok** | |
| 2 | pear | 6.5 cm | 1 | **ok** | |
| 3 | strawberry | 4.4 cm | 1 | **ok** | |
| 4 | lychee | 3.4 cm | 1 | **ok** | |
| 5 | kiwi | 5.1 cm | 1 | ok (slot 0) | |
| 6 | tomato | 6.5 cm | 0 | **FAIL** | grip loss (`fruit did not follow the gripper`) |
| 7 | apple | 6.8 cm | 0 | ok (slot 0) | |
| 8 | orange | 6.8 cm | 0 | ok (slot 0) | |
| 9 | peach | 6.5 cm | 0 | **FAIL** | grip loss (`fruit did not follow the gripper`) |

**8/10 = 80 %**, floor 60 % → **PASS**, and the gate's own reason clause reads
*"only baseline failure reasons"*. The two failures are the pre-existing
acquisition/grip class (both `grasped=False`, `lift=-0.0 cm`, no novel note);
nothing in the run names a rail, a ledge or an output surface.

**Inside the spread.** The interface's recorded samples are **5-8/10**
(`moe_v11` 8, `moe_v12` 6, P2b 5 and 6, P32 D0 5, P41 p4 7). 8/10 ties the top
of that range and is `moe_v12`'s best recorded sample, which is **why it must
be read as one draw**: the loop conditions on rendered frames and is not
bit-reproducible (`AGENTS.md` §3b), the ten targets are the same but the
outcomes are not. **No rail-flip hypothesis is needed**: the failures are
upstream of the output line (both are pick-side grip losses) and the placed
episodes land on the slab, whose top plane is 25 mm *below* where the removed
rail's face used to be - the rail was never the surface a release targets.

---

## 2. `clr_edge` - the corner-band sample

### 2.1 Why the threshold is 0.425 and not the 0.400 switch

`tasks._payload_clearance` switches surfaces at a **literal** `|y| = 0.40`
(main belt below, output belt top above). That number is not the slab's edge: it
is the **removed inner rail's inner face**. The rail box is authored 25 mm thick
with its bottom `OUTPUT_RAIL_INSET` (0.015) inside the slab, so on the shipped
geometry it spans **0.400..0.425 m**, and `assets.SceneConfig.output_rail_keep`'s
own docstring says its **outer face is flush with the slab's inner edge,
`|y| = output_belt_y - width/2`**:

| | value | what it is |
|---|---|---|
| `rail_inner` (`clr_win`'s threshold) | **0.400** | the rail's robot-side face - the switch's literal |
| `rail_centre` (`clr`'s threshold) | **0.4125** | the crossing of record for the +33 mm convention |
| `output_belt_edge` (`clr_edge`'s threshold) | **0.425** | the slab's inboard edge - **where the surface begins** |

So the band 0.400-0.425 m is **inboard of the surface**: a payload there is over
the main belt (1.17 m), 180 mm below the raised slab, and the plane charge at
1.35 is conservative by construction. That is exactly the leg P71 flagged
(`clr_win = -6 mm` on a leg that **placed** with 0.4 mm slip) and the reason the
sample has to move: `clr_edge` is the first tick the payload's own `|y|` reaches
**0.425**, i.e. the tick its lowest point is **over the slab** rather than over
the void. The 12.5 mm difference from `clr`'s threshold also slightly *reduces*
the lift's leverage there (§3).

### 2.2 The field, and what pins it

`[carry] <side> <leg>: ... clr=<rail centreline> clr_win=<rail footprint min>
clr_min=<leg min> clr_edge=<first sample past 0.425> clr_edge_min=<min over the
same band> ...`, all through the existing `_clearance_field` (`+Nmm@obelt/tT`, or
`n/a`):

* **reporting only**: the two trackers live inside `if guard_armed:` (whose first
  condition is `_carry_guard_active or _carry_diag`, and `FRUIT_CARRY_DIAG`
  defaults to `"0"`), so the diag-off path executes **nothing** new and its row
  is **byte-identical**; with the diag on they consume the `(clearance, where,
  i)` triple and the `_abs_y` the leg already computes - **no new read**
  (`_payload_clearance`, `pad_centre`, `tcp_pose`, `spawner.position` are all
  absent from the tracker body, and the leg asserts it);
* **derived, not hardcoded**: `_output_belt_edge_y()` =
  `|output_belt_y| - output_belt_size[1]/2` (0.425 shipped); the leg executes
  that body on stub configs (a wider or further-out slab moves the edge 1:1) and
  asserts the edge method contains **no** rail constant (`0.0125`);
* **a distinct sample**: the edge is 25 mm outboard of `rail_inner` and 12.5 mm
  outboard of the centreline, so `clr_edge` is a *later tick* than `clr`/
  `clr_win` - it is not a rename of either;
* **the leg**: `scripts/239_p72_clr_edge_selftest.py` (new selfcheck leg, the
  `231`/`233`/`235` precedent) pins all of the above plus the parse-back form and
  the `scene` block (§4). `scripts/selfcheck.sh` runs it as
  **"P72 clr_edge + scene"**.

Re-pins the field forced (all mechanical, each test's meaning kept):
`236`'s tracker-init list and its `rail_inner = ... = edge_y = inf` assertion
(the init line grew one name), `236`'s print-containment check (a character
budget → the file's own `indented_body_contains`), `236`'s "one construction
site" count (my `scene_provenance` call also passes `lift_dz=`, so the check is
now scoped to the `PickAndPlaceTask(` call itself), and `238`'s
`output_belt_top_z` read census, which **declared the new consumer**
(`assets.py:scene_provenance`) - the census working as designed.

### 2.3 The shipped package's read (one direct run, seed 77, 15 episodes)

```bash
HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 \
FRUIT_NO_SLEEP=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 \
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival \
FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 \
FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1 \
scripts/run.sh scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
  --presentation direct --episodes 15 --seeds 77 --out logs/p72/rollouts
```

the P66 phase-3 / P71 phase-2 cell verbatim (so the numbers are comparable to
`logs/p71/direct/treat_77.log`), **one run** - a sample, not a rate. The lift
rung and the park prove the shipped defaults in-log (`dz=-0.0800(default) ->
1.3700 m`, `park=back(default)`).

| leg | arm | `clr` (rail centreline) | `clr_edge` (slab edge) | `clr_edge_min` | `\|a\|max` | `sep_end` | slip |
|---|---|---|---|---|---|---|---|
| ep0 | left | +33 @t329 | **+38 @t335** | +38 @t335 | 2.79 | 70.8 mm | 0.0 mm |
| ep2 | right | +76 @t261 | +77 @t267 | +77 @t267 | 2.39 | 69.5 mm | 0.0 mm |
| ep3 | right | +98 @t230 | +97 @t235 | +97 @t246 | 2.94 | 38.1 mm | 0.0 mm |
| ep6 | left | +22 @t297 | **+26 @t303** | +26 @t303 | 0.44 | 70.9 mm | 0.0 mm |
| ep8 | right | +74 @t292 | +74 @t298 | +74 @t298 | 2.57 | 71.9 mm | 0.0 mm |
| ep10 | right | +85 @t208 | +84 @t213 | +84 @t227 | 3.82 | 63.6 mm | 0.0 mm |
| ep11 | right | +78 @t323 | +78 @t329 | +78 @t329 | 1.61 | 72.2 mm | 0.0 mm |
| ep12 | right | +110 @t194 | +109 @t198 | +104 @t227 | 4.49 | 43.1 mm | 0.0 mm |
| ep13 | right | +74 @t219 | +74 @t224 | +74 @t233 | 4.24 | 80.6 mm | 0.0 mm |
| ep14 | right | +93 @t271 | +93 @t277 | +93 @t279 | 1.81 | 45.0 mm | 0.1 mm |

**`clr_edge`: n = 10, min +26, median +77.5, max +109 mm; `clr_edge_min`:
n = 10, min +26, median +77.5, max +104 mm; `<= 0` on 0/10.** Every value is
`@obelt` (no rail surface exists), every held leg's `|a|max` is below the G0
contact floor of 14.9 m/s² (max **4.49**), and no leg's slip exceeds 0.1 mm -
i.e. **the corner sample is positive with no contact signature on all ten**.

* **The arm split is the branch, and it is thin for the left**: this draw put
  13 place legs on the **right** (8 held, +74..+109) and only 2 held on the
  **left** (+38, +26). The left is the arm the package targets, so its
  population here is **n = 2** - the minimum of the whole table (+26, ep6) is a
  left leg, but the left's *distribution* is not measured by this run. P71's
  same-seed treatment drew the mirror image (10 held left / 4 right, `clr`
  +14..+50); the two runs are different branches of the same cell.
* **The left's corner sits 4-5 mm above its centreline sample** (ep0 +33 -> +38,
  ep6 +22 -> +26) while the right's sits ~0-1 mm below it: the left's transit is
  still descending across the 12.5 mm band, the right's is flat. So P71's
  left `clr` +14..+50 maps to roughly **+18..+55 mm** at the corner by that
  measured delta - an inference from two legs, flagged as such, not a second
  measurement.
* **P70's hand estimate is confirmed to 1 mm where the two runs share a leg.**
  `logs/p70/direct/D1.log` ep0 and this run's ep0 are the same leg (same
  `clr = +33 @t329`, `clr_win = +29 @t323`, 430 ticks, `res_end` 31.6 mm);
  P70 printed `edge~+37` from a slope model (`clr + 4 mm`) and the measured
  `clr_edge` is **+38**. One leg, but it is the leg the whole `edge~` column was
  built on.
* Outcome mix (not a rate): 10/15 placed, 3 carried-not-placed (loaded slide),
  2 never-held (`fruit fell off the line`, the supply tail).


---

## 3. The new-frame boundary: `clr_edge > 0`, and it is a bracket

### 3.1 The surface algebra (derived from the code, not assumed)

With `FRUIT_OUTPUT_RAILS=none`, `SceneConfig.output_rail_keep` returns
`(False, False)`, so `_payload_clearance`'s rail branch (`if y <= 0.46 and
cfg.output_rail_keep[0]`) is never entered and the report can only return
`main belt` or `output belt`. The **only** surface a place transit can clip is
therefore the output slab: its **top plane** (1.35 m) and its **inboard edge**
(0.425 m). Contact requires both halves at once -

* the payload's lowest point horizontally **over the slab** (`|y| >= 0.425` for
  the support point the instrument computes), and
* that point **below the top plane** (`clearance < 0`),

which is exactly `clr_edge <= 0`. No raised surface exists, so no `+N mm`
convention can be inherited from the rail frame: the rail's floor was a *ledge*
(its 25 mm top face), and a ledge's clearance requirement is a property of the
ledge.

### 3.2 The bracket that already exists

| read | frame | value | contact signature |
|---|---|---|---|
| P70 D1 ep8 (left, held) | `clr` @obelt, \|y\| = 0.4125 | **-1 mm @ t247** (`edge~+3` was P70's **hand estimate**, `clr + 4 mm`) | **none**: `\|a\|max` 0.98 m/s², `sep_end` 69.9 mm, slip 0.4 mm |
| P70 D1 held population | `clr` @obelt | +10..+54 | none (`|a|max` 0.31-9.92) |
| G0 contact population | `clr` @rail (the rail top) | `clr <= +7` | **14.9-32.7 m/s²**, 27-76 mm displacement, `sep_end` 97.5-98.3 on 4/5 |
| G0 clean population | `clr` @rail | `clr >= +14` | 2.6-5.7 m/s², 0.0-0.1 mm slip, `sep_end` 41-78 |

The -1 mm leg is the reason the bar cannot simply be "`clr <= 0` is a contact":
it is a **plane** sample taken 25 mm inboard of the surface, in the void. The
same leg read the *measured* corner value in this phase (§2.3), which is what
the P72 field replaces the estimate with.

**No dose ladder was spent, and none can close the gap anyway.** The crossing
height is `z_cross = f·z_transfer + (1-f)·z_lift_end` with `f = 0.825` (the rail
centreline over the 0.50 m place span; **0.85** at the 0.425 edge), and

* `z_transfer = output_place_z + hand_add = belt_top + 0.10 + hand` moves **1:1
  with the belt top**, i.e. with the obstacle, while
* `z_lift_end = main_belt_top + 0.28 + dz` is anchored to the **main** belt and
  does not move with the output belt at all,

so `d clr / d(dz) = +(1-f) = +0.175` and `d clr / d(belt top) = f - 1 = -0.175`
(0.15 each at the edge sample). The lift lever that fixes the carry rotation
therefore buys 17.5 % of its travel at the crossing, and the belt-height lever
spends the 40 mm under-slab audit for +7 mm (P70 §2, P66 P4 - both measured
negative on the count). **The two levers cannot be swept to a zero crossing
without paying the placements**, which is why this phase measures the boundary
instead of dosing it.

### 3.3 The honest shipped statement

**The floor in the new frame is `clr_edge > 0`; the package's measured minimum
is **+26** mm with no contact signature; the +33 mm convention was
calibrated against a raised rail and has no counterpart surface now.** This is a
**bracket, not a calibrated floor**: the shipping evidence is one leg below zero
on the *plane* instrument with a clean signature (D1 ep8) plus the measured
corner values of §2.3, not a contact-calibrated boundary at the corner. To
calibrate one would need a forced descent into the slab's edge band (the G2-style
fixture) and a contact read - named, not run.

---

## 4. The scene's collider set as a manifest field

`assets.scene_provenance(cfg, lift_dz=None, lift_dz_defaulted=False)` - pure
`SceneConfig` arithmetic, so it imports without the simulator and the offline leg
executes it - is the one builder both writers call (the P41 `physics` rule):

| writer | call | `lift` |
|---|---|---|
| `scripts/40_collect_demos.py` (`write_manifest`) | `scene_provenance(cfg)` | **`null`** (a scripted shard has no lift rung) |
| `src/fruit_sorting/rl_env.py` (`_build_manifest`) | `scene_provenance(self.cfg, lift_dz=self._lift_dz, lift_dz_defaulted=self._lift_dz_defaulted)` | `{dz: {left: -0.08}, defaulted: true}` shipped |

The block, on the shipped tree:

```json
"scene": {
  "output_rails": "none",
  "rail_keep": {"inner": false, "outer": false},
  "rail_height": 0.05, "rail_proud": 0.035, "rail_inset": 0.015,
  "output_belt": {"top_z": 1.35, "y": 0.55, "size": [1.1, 0.25, 0.05],
                  "inboard_edge_y": 0.425},
  "lift": null
}
```

* **Why each field**: `output_rails`/`rail_keep` are the two inner boxes P71
  removed (the pair is what the builder reads, the string is what a human set);
  `rail_height`/`rail_proud`/`rail_inset` reconstruct a pre-P71 clearance row
  (`rail_proud` is the number `_payload_clearance` reports a kept rail against);
  `output_belt.top_z` is P70's height knob (1.35 kept) and `inboard_edge_y` is the
  P72 corner the payload crosses.
* **Behaviour is unchanged**: nothing reads the block, both writers wrap the call
  in `try/except` (a reported state, never a failed run), and the block is a pure
  read of the config - proven by the collector probe below, which writes a
  manifest with **no** simulator and leaves every other field to its shipped path.
* **A pre-P72 store has no key** (`arm_park.defaulted`'s convention): absent =
  either geometry, present = identified. `lift: null` is explicitly *"not a
  direct run"*, not "the 0.36 m rung".

Evidence: `logs/p72/manifest_probe.py` (run under the simulator's python - it
imports `isaacsim`, so it is not an offline leg) writes both geometries and
prints the blocks (`manifest_probe.log`): `output_rails` `none` → `rail_keep`
both false, `=both` → both true, `lift` `null` in both. The offline leg (`239`)
pins the builder's signature and values, both call sites and their arguments,
the `1-arg` form on the collector path (so its `lift` stays `null`), and the
`except Exception` wrappers.

---

## 5. What this does not measure

* **The canary is one sample** (the loop is not bit-reproducible) and 8/10 is the
  top of a 5-8/10 spread: it says the shipped tree still passes the gate of
  record and that no novel reason appeared. It says **nothing** about the rail
  flip's effect on the policy, which no mechanism here predicts.
* **`clr_edge` is one tick per leg** (the entry into the edge band) plus the band
  minimum. A corner contact by the payload's **outboard overhang** while its
  centre is still inboard of 0.425 is not separable with this instrument; the
  bound is the overhang's height difference over ≤ 29 mm of radius (single-digit
  mm at this roundness), and the `clr_edge_min` reduction covers the band it
  enters.
* **The boundary is a bracket** (§3.3): no forced-contact calibration exists at
  the corner, and the +33 convention is retired rather than re-signed.
* **One direct run**, so the §2.3 distribution is a **sample of the branch**; it
  is quoted as an n and a range, never as a rate.
* The **collector was not re-collected**: a post-P72 store is a new manifest
  *field*, not a new scene, but nothing was recorded to prove the field's
  end-to-end presence on a shard (the probe calls the real `write_manifest`; the
  direct env's own manifest was written by the run in §2.3).
* The **ledge class stays untested, not zero** (P70 §4's fixture still not run)
  and the belt height stays 1.35 by P70's verdict.

---

## 6. Reproduce, gates and pins

```bash
SKIP_SELFCHECK=1 scripts/accept_policy.sh            # §1 (the canary smoke)
python3 scripts/239_p72_clr_edge_selftest.py         # the new selfcheck leg
python3 logs/p72/p72_report.py --check logs/p72/direct/treat_77.log
python3 logs/p72/manifest_probe.py                   # under the simulator python
python3 logs/p72/p72_scope.py                        # §3's arithmetic
scripts/selfcheck.sh
```

Gates on the final tree: **`scripts/selfcheck.sh` PASS, 0 failures** (1 skip, the
motion-budget leg, which needs a logged run); the canary **PASS at 80 %** with
only baseline reasons; `p72_report.py --check` PASS (a corner sample on every
held leg, no rail surface reported, no negative corner with a contact signature).

Pins (md5 first 6; `logs/` is gitignored - `git add -f` at the close-out):
`logs/p72/canary_rails_none.log` **`fd4c9172`**,
`logs/p72/direct/treat_77.log` **`fb588810`**,
`logs/p72/p72_report.py` **`0c5efea4`**, `p72_report.txt` **`882eec0b`**,
`logs/p72/manifest_probe.log` **`ceb0f616`**;
`src/fruit_sorting/tasks.py` **`f61323f2`**, `assets.py` **`540406fa`**,
`rl_env.py` **`92a25c8e`**,
`scripts/40_collect_demos.py` **`86b3d6ba`**,
`scripts/239_p72_clr_edge_selftest.py` **`c3027c4f`**,
`scripts/236_p66_lift_selftest.py` **`1161d2ce`**,
`scripts/238_p70_belt_top_selftest.py` **`1d6f603c`**,
`scripts/selfcheck.sh` **`cb4365d2`**;
`configs/motion_reference.json` `8952c320` / `..._twoline.json` `eb697f23`
untouched; checkpoint `moe_v13s` `61da390a`.
