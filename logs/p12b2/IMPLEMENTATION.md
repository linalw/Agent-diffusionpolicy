# P12-B.2/S4 implementation: the containment bundle (`FRUIT_BELT_CONTAINMENT`) — offline, the battery deferred

Status: **implemented + verified offline** (branch `p-supply`, 2026-10-18; **no simulator run** — the
S3 battery `logs/p12b/90_s3_driver.log` was running throughout and was not touched; see the
provenance note at the end). The scoping record this implements is `logs/p12b/SCENE_OPTIONS.md`
section S4 ("the containment bundle [the mission's (b)/(c), sharpened by the fall path]").

## 1. What was implemented

A new **default-off** knob `FRUIT_BELT_CONTAINMENT` (unset/`0` = the shipped build,
byte-inert; `1` = the keeper + the fences authored in the scene), following the
`FRUIT_CLEATS` / `FRUIT_BELT_KINEMATIC` env-knob convention of `conveyor.py`:

* **`containment_parts(cfg)`** — module-level **pure** geometry (no stage, no pxr): returns the
  three parts as `{path, size, center, colour}` dicts, so the offline stub pins every placement
  and clearance without a simulator.
* **`CleatedBelt.__init__`** — `self.containment = os.environ.get("FRUIT_BELT_CONTAINMENT", "0") == "1"`,
  read **once**.
* **`CleatedBelt.build()`** — `if self.containment: self._build_containment()` (guarded; nothing
  else changed in the shipped path).
* **`CleatedBelt._build_containment()`** — authors the three parts as **static colliders**
  (`CollisionAPI`, metal friction mu 0.40/0.35, restitution 0 — the output-belt side rails'
  convention), resting on the belt top like the main belt's guide rails, and prints an audit
  line with the placements and the binding clearances.

The mechanism (from the scoping's fall-path derivation): the measured fall exit path is the belt
end *within the attempt* — the feeder recycles only at attempt boundaries, so an ejected fruit
rides to the downstream end and drops ~1.17 m to the floor. The keeper catches it at the end
face; it stays on the belt until the next `FruitSpawner.update()` recycles it as `reached_end`
instead of `fell_off`. The fences catch the lateral roll-offs. **Grip-null, outcome-null by
design** — the containment changes where the fruit ends up, not the catch.

## 2. The diff summary

`src/fruit_sorting/conveyor.py`: **+142 lines, 0 deletions** — the only source file touched.
No other `src/` file changed; in particular `tasks.py` is **byte-unchanged**, so the
`rl_env.py` `TASKS_MD5` pin (`810658b802d22bbd63013726fc78af81`) stays valid and `rl_env.py`
needed no edit. `scene.py` is untouched (the containment builds from `CleatedBelt.build()`,
which `scene._add_conveyor` already calls). The `logs/` tree is gitignored, so this file and
the stub are working files (the parent lane force-adds if wanted).

The shipped path at default is byte-inert by construction *and by pin*: with the env unset,
`build()` authors exactly the shipped 9 prims (the stub asserts the full prim set, sizes and
centres — see §4).

## 3. The placements

| part | path | size (x, y, z) [m] | centre [m] | span |
| --- | --- | --- | --- | --- |
| belt-end keeper | `/World/Conveyor/BeltEndKeeper` | 0.460 × 0.020 × 0.050 | (0.34, −0.79, 1.195) | x [0.110, 0.570] = the belt width; y [−0.800, −0.780] (downstream face flush with the belt end); z [1.170, 1.220] (on the belt top) |
| side fence −X | `/World/Conveyor/SideFenceN` | 0.015 × 1.560 × 0.050 | (0.1225, 0.0, 1.195) | x [0.115, 0.130] (inner face 0.130); y [−0.780, +0.780]; z [1.170, 1.220] |
| side fence +X | `/World/Conveyor/SideFenceP` | 0.015 × 1.560 × 0.050 | (0.4375, 0.0, 1.195) | x [0.430, 0.445] (inner face 0.430); y [−0.780, +0.780]; z [1.170, 1.220] |

The fences butt against the keeper's upstream face (y = −0.780) and stop 20 mm short of the
belt's upstream end face (y = +0.780), clear of both pulleys' crowns. The fence inner faces
0.130 / 0.430 are the scoping bound (`x <= 0.13 / >= 0.43`) at its **tight values** — the
innermost positions that clear the open hand's ±0.066 m span across the delivered band.

## 4. The clearance table (every check with its number)

Pinned by `logs/p12b2/check_containment.py` (95 checks; all numbers recomputed from
`SceneConfig`, not copied):

| # | the constraint | the number | the check |
| --- | --- | --- | --- |
| 1 | **despawn lane** (`despawn_y` −0.70) | keeper upstream face −0.780 is **80 mm downstream** of the recycle line; a fruit stops with centre y = −0.780 + r → **−0.745** (r = 35 mm) … **−0.766** (r = 14 mm), i.e. **45–66 mm past** the threshold | the fruit still crosses `along < despawn_y` before contact → the next `update()` recycles it `reached_end`; the keeper takes **no belt length** (downstream face = the end face) |
| 2 | **keeper height vs the fruit** | 50 mm vs the largest fruit's centre 35 mm → **+15 mm** | a roll-off cannot climb the lip; the 40–60 mm scoping band is met |
| 3 | **open hand's ±0.066 m span** (binding budget) | at the band's edges the span reaches **0.134–0.266** / **0.294–0.426**; the fence inner faces clear those by **4 mm / 4 mm** | the catch descends at the fruit's measured x; 4 mm is the scoping's binding clearance |
| 4 | the pick point / pre-pose span | 0.34 ± 0.066 = **0.274–0.406** → **144 / 24 mm** | the static `grasp`/pre-pose poses (x = `pick_x`) clear both fences |
| 5 | **the catch's reach band** (`scripts/174`) | the fences sit **outside** x 0.186–0.386 (0.130 < 0.186; 0.430 > 0.386) | the hand-span check (#3) is the binding one |
| 6 | **the transport lane** (the fruit ride) | band fruit (x 0.20–0.36, r ≤ 35 mm) clear the fences by **35 / 35 mm**; the scatter respawn draws x ∈ [0.20, 0.36] (the `x_jitter` parameter is dead in that branch), the fixed line 0.34 ± 0.005 | no release, prime or ride contact inside the band |
| 7 | the drift tail (measured extreme x = 0.148) | contacts the −X fence for r ≥ **18 mm** | documented residual: containment (the fruit is caught, not lost); a clean pass only for r < 18 mm |
| 8 | **the place paths** — the carry crossing | the carry crosses x = 0.430 at the place waypoint (y = ±0.50, z = 1.53); the payload's lowest ≥ 1.53 − 0.090 − 0.035 = **1.405** vs the fence top **1.220** → **185 mm** | jaw z: `belt_top + 0.28 + 0.08` = place z: `1.35 + 0.10 + 0.08` = 1.53 |
| 9 | the place descent (`_place_low`) | fingertips stop at ≥ `output_belt_top_z + 0.005` = **1.355** vs 1.220 → **135 mm** | the fingers never descend below the fence top at the place |
| 10 | the ready pose | fingertips at `belt_top + 0.20 − 0.0814` = **1.289** vs 1.220 → **69 mm** | the return/ready path |
| 11 | **the two-line stations** (y = 0.00 / −0.10) | the keeper is **0.78 m / 0.68 m downstream** of the two stations; the fences run along Y at a fixed x outside the hand's span (#3) | no y-obstruction by construction (fences are parallel to the stations' sweep) |
| 12 | the pulley crowns | crown at \|y\| = **0.7894** at the belt top vs the fence end 0.780 → **9.4 mm** | the fences stop clear of both pulleys (visual parts) |
| 13 | the main frame rails | −X rail inner face **0.1105** vs the fence outer face 0.115 → **4.5 mm** | no overlap with the frame (visual part) |
| 14 | inside the belt width | the fences [0.115, 0.130] / [0.430, 0.445] sit within [0.110, 0.570] | they stand on the belt, not off it |
| 15 | the keeper's width | 0.460 m = the belt width | the scoping's "the belt's width" |
| 16 | knob-off byte-identity | the build defines exactly the **9 shipped prims** with the pinned sizes/centres; **0** containment prims | §5 check 2 |

Interactions that are *not* clearances, checked and documented:

* a keeper-held fruit (y ≈ −0.75) is outside **every** selection window (the station window's
  floor is ≈ +0.106, the upstream window ends at +0.85), so it is never re-selected;
* `FruitSpawner.enforce_transport` nudges a stopped on-belt fruit at the *next* update and the
  same update recycles it (`along < −0.70`) — no lock-in;
* the cleats (`FRUIT_CLEATS=1`, **default off**) wrap within y ∈ [0.28, 0.64] and x ∈ [0.117,
  0.563], so they pass through the fences' x/z (never the keeper); kinematic-vs-static bodies
  generate no contact and the bars travel parallel to the fences, so the cleat line is unaffected;
* the guide rails (`FRUIT_RAILS=1`, default off) sit at x = 0.1945–0.2095 / 0.4705–0.4855 — clear
  of both fences (25.5 mm on the +X side, 64.5 mm on the −X side);
* the pulleys and frame rails are **visual-only** (no `CollisionAPI`), so the keeper's ~10 mm
  sliver inside the head pulley's crown volume (y ∈ [−0.800, −0.789] at z ∈ [1.170, ~1.182]) is
  cosmetic; the keeper is the real collider;
* up to a few fruit can arrive and stack at the keeper between attempt boundaries (the scoping's
  named risk) — all are recycled at the next `update()`.

## 5. The verification (offline only)

1. `python3 -m py_compile src/fruit_sorting/conveyor.py` — OK; the stub compiles too.
2. **The new stub** `logs/p12b2/check_containment.py` — `python3 logs/p12b2/check_containment.py`
   → **95 checks PASS**. It stubs pxr/isaacsim (the `scripts/172_supply_selftest.py` pattern) and
   runs the **real** `CleatedBelt.build()` against a recording fake stage:
   * knob resolution: unset → off, `0` → off, `1` → on; **read once** (flipping the env after
     construction is inert);
   * knob-off **byte-identity**: the build defines exactly the 9 shipped prims (pinned paths +
     sizes + centres) and zero containment prims;
   * knob-on: the prim set is the shipped 9 + the 3 containment prims; each authored prim matches
     `containment_parts()` exactly and the pinned placements; no shipped prim moved;
   * all 16 clearance checks of §4, recomputed from `SceneConfig` (the pulley crown, the frame
     rail and the belt edges included);
   * source shape: `FRUIT_BELT_CONTAINMENT` is read exactly once in `conveyor.py` and the
     authoring is guarded by `if self.containment:`.
   Deterministic (identical output on repeat runs) and robust to an inherited env.
3. `SELFCHECK_LOG=logs/p12b2/selfcheck.log scripts/selfcheck.sh` → **PASS, 0 failures, 1 skipped**
   (the motion-budget leg needs a run log by design; log: `logs/p12b2/selfcheck.log`). The log was
   redirected under `logs/p12b2/` to keep every write in this lane.

## 6. The md5s

| file | md5 | note |
| --- | --- | --- |
| `src/fruit_sorting/conveyor.py` | **`40b04d2da12a80cb209551916c60cc14`** | new (was `2c1a0620d00e329588a7fd87404ff085`); +142 lines |
| `src/fruit_sorting/tasks.py` | `810658b802d22bbd63013726fc78af81` | **unchanged** — matches the `rl_env.py` `TASKS_MD5` pin |
| `src/fruit_sorting/scene.py` | `ab85dca250cdd09cc7cbd9893c58fca3` | unchanged |
| `src/fruit_sorting/fruits.py` | `d28546d26137d4540421caa7fa34a139` | unchanged |
| `src/fruit_sorting/assets.py` | `c27f7440fc09727e5c32e278e7d7c1f4` | unchanged |
| `src/fruit_sorting/rl_env.py` | `9a2c38721b32f0af91371ca3e8809196` | unchanged (no pin edit needed) |
| `logs/p12b2/check_containment.py` | `00c7156aad8c92e5a4d2e66b29e6404d` | the new stub |

Note for future RL manifests: `rl_env._MANIFEST_SOURCES` includes `conveyor.py`, so any RL run
started on this tree records the new md5 — expected, since the file legitimately changed (the
change is default-inert).

## 7. The battery (deferred — the separate lane)

The S4 arm is `FRUIT_BELT_CONTAINMENT=1` on the same base as the S3 arm (the P12-B.2 prereg
sketch: two-line patch battery, `ATTEMPTS=20`, seeds 11/5/23, Tier A solo). What it would
measure, from the scoping's endpoints:

* the **falls**: the `[motion] carry ... lowest payload point <= -1000 mm` rows (the anchor 14
  pooled) — the keeper converts the belt-end falls into `reached_end` (the feeder's `[belt]`
  lines) and the fences catch the lateral roll-offs;
* the **mechanism** on a trace-on run: the per-tick path of the ejected fruit (the scoping's
  caveat — the fall path is derived, not logged) — the trace settles whether any fall is a
  mid-carry drop over the floor, which the keeper does not catch;
* the **no-harm**: the knob-off A arm must replay the base's records 0-diff; the two-line gate
  via `scripts/190_twoline_gate.sh`.

Not run here: the simulator is owned by the running S3 battery; the S4 battery is a separate
lane's call.

## 8. Provenance note (the running S3 battery)

The battery was **not touched** (no simulator invocation from this lane; all checks above are
offline). Timing, for the record: the `conveyor.py` edits' last write is 18:43:49, the seed-11
and seed-5 shards ran 18:26–18:34 and 18:34–18:44 (their processes started before the edit), and
the seed-23 shard's process started 18:44:43 — i.e. **seed 23 loaded the post-edit module**. The
change is default-inert (`FRUIT_BELT_CONTAINMENT` is unset in the battery env; the stub pins the
identical 9-prim build, no stage calls), so no measured quantity can differ, and the run harness
records no source md5s (grep: 0 md5 lines in the shard logs). The only consequence is the
provenance split above, recorded here so a later reader does not have to reconstruct it.
