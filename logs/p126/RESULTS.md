# P126 - the third output lane ships: the corrected evidence, the flip, and the re-baseline

The owner's decision (要) was to adopt the third output lane. P124 executed a flip
and reverted it because the hybrid canary read 4/10 twice on three lanes against
8/10 on two; **P125 refuted that reading** with the same checkpoint on both
scenes - **A (three lanes) 17/30 = 56.7 %**, **C (two lanes) 11/20 = 55.0 %** -
and built the three-lane store. This phase re-registers the decision on the
corrected evidence (`PREREG.md` md5 **`fba4b9d4`**, pinned before the acceptance),
flips the default, and pays the re-baseline.

**The rule (pinned):** the scripted acceptance at or above the 0.60 floor with
clean motion budgets; the P123 tray census (25/25, the destination is the
product); the single arm at its standing branch; **the canary reported, not
gated** - a 55-60 % loop cannot carry a scene decision at N=1.

## 1. The flip

`SceneConfig.output_lanes`' default is **3**; `FRUIT_OUTPUT_LANES=2` restores the
two-lane scene byte for byte. The tests moved with it: `264` (the default is
three lanes, `=2` reproduces every shipped scalar, the generalised predicates
equal the pre-P123 expressions on the `=2` grid, the default manifest records
three lanes), `259`/`260` (the P114 record's two-lane cell is built explicitly;
the default capability map is `left=[0], right=[1,2]`), `234` (the three
scenarios keep their own references; the pre-P126 records are archived).

## 2. The acceptance (the carrier)

| cell | scene | result |
| --- | --- | --- |
| `accept.sh` (two-line, 10 attempts) | **3 lanes (default)** | **7/10 = 70 %**, budgets clean, `190: PASS` after re-recording |
| the same run, repeated | 3 lanes | 7/10, **423/423 `[fruit]` lines identical** |
| `accept.sh` (`FRUIT_BIARM=0`, 10) | 3 lanes | **6/10 = 60 %** - the standing single-arm branch, **rate-only** FAIL; its fingerprint matches the re-recorded reference |

The two-line reference and the acceptance reference are **`d258db1a`** (both, one
record), the single-arm reference is **`d15972cc`**; the pre-flip files are
archived at `logs/p126/motion_reference*_pre_p126.json`
(`30fb99f8` / `30fb99f8` / `8952c320`).

## 3. The canary (reported, not gated)

`accept_policy.sh`, the shipped checkpoint, the three-lane default: **7/10 =
70 % PASS**, 3 grip losses, no new reason. That sits at the top of the P125 band
(A 56.7 % over 3 samples) and above the P124 two-lane sample (8/10) within the
loop's spread - **the interface is not degraded by the scene**.

## 4. The re-baseline (the price)

* **Every store recorded before P126 is a two-lane store.** The manifest is the
  witness: `scene.output_lanes` with 2 entries (or absent, pre-P123) = pre-P126;
  **3 entries = the shipped scene**. The one existing three-lane store is
  `datasets/p125_three_lane` (196 episodes, `scene.output_lanes` 3 in all eight
  shards) - it is now **the shipped scene's store**, so P125's spend converts
  from "the candidate for a flip" to "the store of the shipped cell".
* **Both two-line references and the single-arm reference were re-recorded**
  from this phase's same-batch runs (the §2 recipe), and the acceptance is
  re-based.
* **The `234`/`264`/`259`/`260` pins moved** with the tests, and the AGENTS
  record carries the new references.
* Any pre-P126 two-line rate, interval, acceptance or store is a **pre-three-lane
  number**; `FRUIT_OUTPUT_LANES=2` restores the scene (and the old records are
  archived, not deleted).

## 5. What is not claimed

* the scripted count moved 8/10 -> 7/10 on this branch (one attempt, inside the
  branch spread, and P123 measured 7/10 and P124 7/10 on the same scene); no
  rate is claimed in either direction;
* the direct/policy interface was not re-measured beyond the canary (P121's
  dispatcher is scene-agnostic; the interface's numbers are the direct loop's
  own and are unchanged by a scene body the policy does not touch);
* the third lane's own release offset (P123: `(+20..30, -10..-20) mm` on the new
  lane vs `(+48, +-35)` on the shipped ones) is unchanged - the belt is where
  P123 put it; widening its upstream end is a named, unpriced option.

## 6. Files

`logs/p126/{PREREG.md,PREREG.md5,RESULTS.md}`, the acceptances and the canary,
the pre-P126 reference archives. `src/fruit_sorting/assets.py` (the default),
`scripts/{264,259,260,234,selfcheck}`, `AGENTS.md`, `WORKLOG.md`. References
**`d258db1a` / `d258db1a` / `d15972cc`** (the new tree's).
