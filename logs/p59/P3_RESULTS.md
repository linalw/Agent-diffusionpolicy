# P59 phase 3 results — the same-tree 45-block control, the cap-5 re-read, the post-profile number

**Verdict.**

1. **Cap 5 is now same-tree comparable.** The control runs on `rl_env.py`
   `1b1e5cdf`, `tasks.py` `8ad8ddc8`, `fruits.py` `c7461d41` — byte-identical to the
   files the phase-2 cap-5 arm recorded in `logs/p59/p2/header.txt` /
   `p2/tree_md5_after.txt`; **all 14 pinned files identical, none moved**.
   (Contrast: the P2
   control A2 differs from this tree on **4/14** files — `rl_env` `ddcb7816`,
   `tasks` `c7eef701`, `fruits` `55921c46`, `110_rl_rollout` `b5d05ea3` — so it
   remains cross-tree and this control replaces it as the foot.)
2. **No behavioural counter differs.** `window==0` **0/45 = 0/45**, `window>=1`
   **45/45 = 45/45**, starved feed rounds **0/42 = 0/42**, and `sel_gap` has the
   **same support and the same total** in both arms (`{139,140,141}` × 42 gaps,
   max 141 < the 169-tick starve threshold). What moves is the depth and three
   counters that ride it: `sel_gap`'s counts *within* that 3-value support
   (4/32/6 vs 8/25/9), `skipped` 24 vs 21, `placed` 26 vs 27.
3. **The post-profile direct number is 26/45 = 57.8 %** — one **branch** of the
   shipped configuration (per seed 11/15, 6/15, 9/15), not a rate; right arm
   **24/25**, left **2/20**; the failure class is `cnp` (carried-not-placed)
   **17 of 19 failures, 100 % left-arm**, plus 2 no-grasp (one per arm).
4. **The hybrid `moe_v12` canary does not read the P58 profile** and cannot: it
   builds its own `FruitSpawner` with no profile kwargs and never constructs
   `SortingRLEnv`, so it runs the **pre-P58 fixed supply** (quoted line in §5).

No default change, no `src/`/`configs/` edit, no commit.

## 1. The control (the shipped profile, nothing explicit)

`logs/p59/run_p3.sh`, 3 seeds × `--episodes 15`, one claim per run, ~9 min each,
28 min total, three clean exits (no wedge, `RUN_LIMIT` 2700 never hit). Scenario
env verbatim the phase-2 one; `FRUIT_DIRECT_CONTINUOUS` / `ACQ` / `ARM_PARK` unset.

| seed | placed | left | right | `window` mean | Σ`window` | `==1` | `==0` | `skipped` (final) | starved | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| 77 | **11/15** | 0/4 | 11/11 | 2.07 | 31 | 5/15 | 0 | 7 | 0/13 | 505.4 s |
| 101 | **6/15** | 1/10 | 5/5 | 2.40 | 36 | 0/15 | 0 | 6 | 0/15 | 530.2 s |
| 202 | **9/15** | 1/6 | 8/9 | 2.47 | 37 | 3/15 | 0 | 11 | 0/14 | 516.6 s |
| **pooled** | **26/45 = 57.8 %** | **2/20** | **24/25** | **2.311** | 104 | **8/45** | **0** | **24** | **0/42** | **34.49 s/pick** |

45 `[bed-sel]` blocks over 3 × 15 picks — the **45-block control** the Oracle's
reopening criterion names. Provenance per run is identical and shipped:
`[supply] direct profile: cadence=on(default) band=on(4)(default) feed=on(default)
target_from=0.35(default)`; `[rl] env ready: … park=back(default) … tasks_md5=8ad8ddc8`;
`[rl] trigger=arrival lead=0.90s lateral=0.160 … acq=on(speed=0.20,margin=0.60,cap=4.50,reach_margin=0.05)`;
`[supply] scatter pool=16 … patch=on … grades=A:0.375,B:0.375,C:0.25`. **Zero
`lateral refuse` rows in all three runs**, so the P38 x-tail refusal class
contributed nothing here. `on_belt` identity (`on_belt = admitted + below +
above`) holds on 45/45 blocks. Feeder releases 174 / 182 / 173.

**Tree pins recorded** (`logs/p59/p3/header.txt`, `tree_md5_after.txt`, stable):

```
1b1e5cdf32f3ccf93d94d8f5835d0a3b  src/fruit_sorting/rl_env.py
8ad8ddc8a13b6f4d9a96e84791dc04bb  src/fruit_sorting/tasks.py
c7461d4104cf2c5f6c5a2daab80fbf32  src/fruit_sorting/fruits.py
61da390a85fa209496b54477a8255d23  checkpoints/moe_v13s/policy_best.pt
```

## 2. Is cap 5 same-tree comparable? — **yes**

`logs/p59/p3_report.py` §1 diffs the control's own pins against the pins the
phase-2 batch wrote, over the 14 files the arm actually reads (`rl_env`, `tasks`,
`fruits`, `scene`, `control`, `meshes`, `trigger`, `runtime`, two `configs/`
references + `arm_parks`, `110`/`113`/`154`):

* current tree, the phase-2 batch (`p2/header.txt` **and** `p2/tree_md5_after.txt`)
  and the phase-3 batch agree on **14/14**; **no file moved**;
* `git diff ee522c1..HEAD -- src configs scripts` is **empty** (that is the tree
  the phase-2 header names), so nothing changed in code between the two batches
  either — the only commits since are docs-only (`500c6de` evidence, `0f3bd6e`
  the P2 corrections);
* the phase-2 header's note ("working tree has the P59 gate-1 provenance-only
  edit") is the same file that is HEAD's `rl_env.py` today — `1b1e5cdf`.

So the cap-5 arm and this control differ by **one environment variable**
(`FRUIT_SUPPLY_BAND_MAX=5` vs unset) and by nothing else. **Caveat that still
applies**: the direct loop is **not reproducible** (rendered frames — AGENTS §3b),
so the two cells are still not a paired draw; what the same-tree control buys is
that the tree is no longer a confounder. That is exactly the precondition the
Oracle named, and no more.

## 3. Does any behavioural counter differ? — **no; only the depth moves**

| counter | control (cap 4) | cap 5 | |
|---|---|---|---|
| `window==0` blocks | **0/45** | **0/45** | **SAME** |
| `window>=1` blocks | **45/45** | **45/45** | **SAME** |
| starved feed rounds (`sel_gap>=169`) | **0/42** | **0/42** | **SAME** |
| `sel_gap` support / total | `{139,140,141}` / 42 | `{139,140,141}` / 42 | **SAME** |
| `sel_gap` counts in the support | 4/32/6 | 8/25/9 | differs within ±1 tick of 140 (8 ms) |
| `skipped` (summed over seeds) | 24 (7/6/11) | 21 (6/11/4) | differs by 3 of 45 |
| `placed` (report only) | 26/45 | 27/45 | differs by 1 |
| `on_belt` mean | 11.24 | 11.82 | differs by 0.58 |
| `window` mean | **2.311** | **2.533** | differs by 0.222 |

The four invariants the reopening criterion names are **identical**. The
counters that move are the depth, the stock it rides (`on_belt`), and three
draw-level counters — and all three sit inside the noise of a loop that is not
reproducible: their per-seed ordering **swaps** (`skipped` C 7/6/11 vs A 6/11/4;
`placed` C 11/6/9 vs A 9/8/10), so no counter is monotone in the cap. The
`sel_gap` support never leaves `{139,140,141}` in either arm: the difference is
which side of the 1-tick rounding a round lands on, not a lost round.

### The depth, and the control cell it has to be read against

| cell | tree | `window` mean | 95 % CI | `==1` | `==0` |
|---|---|---|---|---|---|
| **control C (cap 4, shipped)** | this tree | **2.311** | [2.041, 2.581] | 8/45 | 0 |
| **arm A (cap 5)** | this tree | **2.533** | [2.280, 2.787] | 4/45 | 0 |
| A2 (cap 4, the P2 control) | **cross-tree** | 2.378 | [2.084, 2.672] | 9/45 | 0 |

* depth delta (cap 5 − control) = **+0.222**; two 45-block arms need
  |delta| ≥ **0.37** to separate at 95 % (`P2_RESULTS` §2's own power statement)
  → **does not separate**;
* `window==1` 8/45 vs 4/45, Fisher **p = 0.353** (report only);
* **two control cells of the same configuration differ by 0.067** (2.311 same-tree
  vs 2.378 cross-tree) — ~30 % of the arm effect. The depth mean cannot rank the
  arms at this n, which is what `P2_RESULTS` §2 said and what this control
  confirms on one foot.

**Corrections to the phase-2 record, all from putting the arm on its own foot:**

1. **"non-worse in 3/3 seeds" is a cross-tree statement.** Against A2 the
   per-seed `window==1` reads A 1/2/1 vs A2 2/2/5 → non-worse 3/3. Against the
   same-tree control it reads A 1/2/1 vs C 5/**0**/3 → **2/3**: on seed 101 the
   control drew **zero** marginal blocks and cap 5 drew two, i.e. cap 5 is worse
   there. The direction is still favourable pooled (4/45 vs 8/45) but it is a
   draw, not a per-seed invariant.
2. **"`sel_gap` is the identical multiset" was also a cross-tree coincidence.**
   A2 and cap 5 really do share `{139×8, 140×25, 141×9}`; the same-tree control
   does not (4/32/6). The *support* and *total* match, which is the behavioural
   statement; the multiset equality does not survive.
3. *(units, P2 table only)* `P2_RESULTS`' `wall s/pick` column prints mean **run**
   wall (531.1 / 530.2 / 519.9), not wall per pick — `p2_report.txt` itself reads
   `wall/pick 35.40 / 35.35 / 34.66`. This report quotes per pick: control
   **34.49 s/pick**, cap 5 **35.35 s/pick**.

**The catch-margin question therefore closes the same way, on a better foot.**
The shipped profile's depth has now been measured twice on two branches and reads
**2.311 / 2.378** — not 2.57 and not 2.60, which are the **pre-P58 burst** cell
(a different configuration: the per-episode re-stock the owner rejected). Cap 5
buys +0.222 of depth, below the separation threshold, and buys **no behavioural
change at all**. **Cap 4 stays; E1's 2.57 bar is not met (2.533) and is not
adjudicable at n = 45.** Cap 6 remains predicted flat.

## 4. The post-profile direct number

**26/45 = 57.8 %**, per seed **11/15, 6/15, 9/15** — a **branch** of the shipped
configuration under the P43 protocol (seeds 77/101/202, `--episodes 15`, policy
seed 11, `moe_v13s` `61da390a`, park/ACQ/profile at their shipped defaults). The
loop conditions on rendered frames and is not reproducible, so this is one draw
per seed, not a rate; the three seeds span 40-73 %, which is the loop's own
spread, not a seed effect.

**Decompose it before quoting it** (P37's arm-mix warning):

* **right arm 24/25 = 96 %** (one no-grasp) — consistent with the P43 parked cell's
  `53/56 = 94.6 %` under the pre-P58 profile; **not** a rate, and **not** a profile
  comparison (different supply, one branch each);
* **left arm 2/20 = 10 %** — the whole deficit;
* the pooled 57.8 % is an **arm-mix artifact** (the right takes 25 of 45 attempts,
  and the left takes the grade-A attempts).

**The class is `cnp`, and it is entirely left-arm.** 19 failures = **17
carried-not-placed** (`grasped=True placed=False`) + **2 no-grasp** (one per arm).
All 17 `cnp`s are left-arm: the left's failure set is 17 cnp + 1 no-grasp out of
18. That is the closed grip/hold **loaded-slide** class of
`logs/p42/SIM_LIMIT.md` — the class the P43 park removes on the **right** (by
parking the *inactive left*) and structurally cannot touch on the left (the park
vector is left-only, so a left-arm episode's inactive right arm has no park;
P43's "left 1/21 → 0/19" guard). So the post-profile number **carries the `cnp`
class on the left and nothing else**; the P41 grip profile, the P43 park default
and the P54 ACQ default are all inside this number. Failure notes sit at
`|dx| = 0.9-13.9 cm`, all inside the 0.16 lateral gate → these are close/carry
failures, **not** the P38 refusal tail (0 refusals recorded).

## 5. The `moe_v12` statement — the hybrid canary does not read the P58 profile

The canary (`scripts/accept_policy.sh` → `scripts/60_eval_policy.py`) builds its
**own** spawner and its **own** task, and `_resolve_supply_profile` is
`rl_env`-only, which that harness never constructs — so no canary log has a
`[supply] direct profile` row (0 occurrences in the P41 canary). The line that
decides it is `scripts/60_eval_policy.py:142`:

```python
spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "77")))
```

with no `band_interlock` / `band_max` kwargs, so `fruits.py:951-959` falls back to
the raw environment read whose defaults are **`"0"` and `"3"`** — the interlock
**off**, not P58's on-at-4; and `scripts/60_eval_policy.py:238`,
`hybrid_task = PickAndPlaceTask(scene, spawner, tactile, cfg)`, passes no
`feed_cadence`, so `tasks.py:1150-1153` falls back to `FRUIT_FEED_CADENCE`,
default **`"0"`**. On top of that `accept_policy.sh:80` sets
`scatter=${FRUIT_SUPPLY_SCATTER:-0}`, i.e. the **fixed pre-v9 supply**. **The
canary therefore runs the pre-P58 supply, unchanged: `moe_v12` is not
"untested under the new profile", it is *out of reach of it*, and the statement
the re-baseline rule owes is "no path" — a post-P58 canary number means the same
supply it always did.**

## 6. What this phase changes, and what it does not

* **Changes**: the cap-4 control has a same-tree foot, so the cap-5 verdict is on
  one tree by construction; the shipped profile's depth is re-stated as
  **2.311 (same-tree) / 2.378 (cross-tree)** against cap 5's 2.533; the
  "non-worse in 3/3 seeds" and "identical `sel_gap` multiset" readings are
  **downgraded to cross-tree** (2/3 seeds; same support only); the direct
  interface has a post-profile branch number (**26/45**) with its class named.
* **Does not change**: no shipped default (`BAND_MAX` 4, the clock pair, the
  feeder), no `src/`/`configs/` edit, no motion reference re-recorded, no
  checkpoint. `moe_v12`'s status is unchanged and now explained.
* **Not measured here**: `BAND_MAX` 5-6 as a *behavioural* endpoint (still
  predicted flat), the two-line (its own pump), the handoff presentation, and any
  store recorded under the profile.

## Artifact

`logs/p59/p3_report.py` runs **exit 0** on the six logs (three control + three
cap-5) plus A2, asserts the `[supply] direct profile` row of every arm before it
reads anything (PREREG_P2 rule 5), asserts the `on_belt` identity on every block,
and writes `logs/p59/p3_report.txt`. Evidence: `logs/p59/p3/{C_77,C_101,C_202}.log`,
`p3/{header.txt,tree_md5_after.txt,batch_outer.log}`, `p3_report.{py,txt}`,
`run_p3.sh`.
