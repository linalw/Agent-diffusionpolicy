# P59 phase 1 — demonstration: the shipped direct supply profile

**What was shipped (P58):** with **no supply env set**, a `direct` run resolves
`FRUIT_FEED_CADENCE` + `FRUIT_SUPPLY_BAND_INTERLOCK` (cap 4) + `FRUIT_DIRECT_FEED`
**on**. This phase proves that the profile is what actually runs, that the old
path is still recoverable, that the multi-pick mode is explicit and reports per
pick, and that the belt stays stocked on a filmed run.

Pre-registration (written before any run): `logs/p59/PREREG.md`. Driver:
`logs/p59/run_p1.sh`. One claim per run (`scripts/154_claim_run.sh`), one
simulator at a time. Tree pins unchanged before and after (HEAD `7d353e7`,
`rl_env.py` `6d7cb329`, `tasks.py` `8ad8ddc8`, `fruits.py` `c7461d41`,
`moe_v13s` `61da390a`, `configs/*` `8a399626`/`2246f83c`); **no `src/` or
`configs/` file and no checkpoint was edited, nothing was committed, no default
changed.** The runs wrote only their own artefacts (the gitignored
`datasets/rl_rollouts` scratch manifest included — see check 2). `git status`
shows only the pre-existing `logs/p36/offline_obs_diff.txt` modification that was
there at entry.

Scenario (identical in all four checks, not part of the supply profile):
W6-A patch sheet, balanced A:B:C `0.375/0.375/0.25`, trigger `arrival` lead 0.9,
`FRUIT_DYNAMIC_PICK=1`, `FRUIT_BED_DIAG=1`, camera `240,424`, policy seed 11,
`moe_v13s`. `FRUIT_POLICY_TRIGGER_ACQ` and `FRUIT_ARM_PARK` are **unset**
everywhere (P54/P43 defaults must be the ones that resolve).

## Verdicts

| check | verdict | falsifier |
|---|---|---|
| 1 the profile is what runs (2 eps, `--record --out /tmp/p59_prof`) | **PASS** | F1 not fired |
| 2 the pre-P58 recipe recovers the old path (1 ep) | **PASS** (one predicted, inert exception — below) | F2 not fired |
| 3 `--continuous 10` is explicit and its summary is pick-level | **PASS** | F3 not fired |
| 4 the continuous video at the shipped profile (8 picks) | **PASS** (4 mp4s, no starvation) | F4 not fired (no wedge, so no retry) |

## 1. The profile is what runs — `logs/p59/p1/01_profile.log`

```
[fruit] [rl] env ready: presentation=direct ablate=none dagger=off park=back(default) camera=240,424 tasks_md5=8ad8ddc8
[fruit] [rl] trigger=arrival lead=0.90s lateral=0.160 reach=0.20 finger=0.040 frame=station encoder=on present=off acq=on(speed=0.20,margin=0.60,cap=4.50,reach_margin=0.05)
[fruit] [supply] direct profile: cadence=on(default) band=on(4)(default) feed=on(default)
```

* the row is byte-for-byte the expected string, **all three members `(default)`**;
  the log contains **zero** occurrences of `explicit`;
* `park=back(default)` (P43) and `acq=on(...)` (P54) are the defaults, not
  something the command line asked for;
* the recorded manifest `/tmp/p59_prof/direct_none_seed77/manifest.json`:

```json
"supply": { "cadence": true, "band_interlock": true, "band_max": 4,
            "direct_feed": true, "continuous": 0,
            "defaulted": { "cadence": true, "band_interlock": true,
                           "band_max": true, "feed": true } }
```

  `arm_park.name = "back"` / `defaulted = true`; `trigger.acq = true`;
* the store exists: `rollout_00000.npz` (11.8 MB), `rollout_00001.npz` (13.5 MB),
  `index.json`, `manifest.json`.

Outcomes of this 2-episode sample (`[rl] rollout success 1/2`, run wall 69.5 s =
34.8 s/pick, the same order as P58's 35.40): pear/left carried-not-placed,
lychee/right placed. One sample of a non-reproducible loop — see "reading rules".

## 2. The pre-P58 recipe still reproduces the old path — `logs/p59/p1/02_pre58_recipe.log`

Run with `FRUIT_FEED_CADENCE=0 FRUIT_SUPPLY_BAND_INTERLOCK=0 FRUIT_DIRECT_FEED=0`:

```
[fruit] [supply] direct profile: cadence=off(explicit) band=off(4)(explicit) feed=off(explicit)
```

```
"supply": { "cadence": false, "band_interlock": false, "band_max": 4,
            "direct_feed": false, "continuous": 0,
            "defaulted": { "cadence": false, "band_interlock": false,
                           "band_max": true, "feed": false } }
```

**The one exception is predicted and inert (pre-registered in PREREG §check 2
before the run).** `band_max` has its own `defaulted` key (`FRUIT_SUPPLY_BAND_MAX`
is unset) and its value is keyed to `direct`, not to the interlock flag, so it
reads `4` / `true` while the three members under test read `off(explicit)` /
`false` / `defaulted: false`. It cannot act: `fruits.py` consults `_band_max` only
under `if self._band_interlock` (`_interlock_max`), and the interlock is off here.
F2 as written keys on the row's three members, which are all `off(explicit)` —
**F2 did not fire**. (If the owner wants the manifest to be unambiguously
pre-profile, the value could be `null` when the interlock is off; that would be a
`src/` edit and is out of scope for this phase.)

**The pre-profile sample (one episode, one selection — not a rate):**

```
[fruit] [bed-sel] attempt 0 t=1.88 live=5 on_belt=5 admitted=5 window=4 pick=apple@0.642 ...
```

This is exactly P58's control reading: one feed at reset, so the **first**
selection sees a fresh burst (`window=4`, `on_belt=5`) and the episode then ends —
the profile's counterpart (`window=2` at attempt 0) is lower at that instant but
stays non-zero for ten picks (`window` 2/2/2/2/2/3/4 over eight picks in check 4).
Compare the *distribution* (P58: `window` mean 2.38 over 45 blocks, 0 starved
rounds), never these two single instants.

Side effect to record: this run wrote the default manifest path
`datasets/rl_rollouts/direct_none_seed77/manifest.json` (gitignored scratch dir;
it previously held only a manifest from an earlier non-record run). No tracked
file was touched — **but that path is shared with every non-`--out` run, so
check 3 overwrote check 2's manifest before it could be archived.** The evidence
is therefore a **same-command re-run with a private `--out`**
(`logs/p59/p1/02b_pre58_manifest.log`, `/tmp/p59_pre58/direct_none_seed77/manifest.json`):
the profile row is byte-identical, the first selection is identical
(`on_belt=5 window=4 pick=apple@0.642`) and the manifest reads exactly the block
above. The registered run (`02_pre58_recipe.log`) remains the one whose
`[bed-sel]` sample is quoted; nothing else about check 2 changed. A check that
must leave a manifest behind has to pass `--out` — that is a lesson for the next
phase, not a defect in the resolver.

## 3. `--continuous 10` is explicit and its summary is pick-level — `logs/p59/p1/03_continuous10.log`

```
[fruit] [supply] direct profile: cadence=on(default) band=on(4)(default) feed=on(default)
[fruit] [cont] enabled: picks_target=10 feed=on(implied) bed_diag=1 (one reset per episode, one episode per n picks)
...
[fruit] [cont] episode 9: picks=10/10 placed=7 reward=6.759200 ticks=18483 gap_ticks=66.7 gaps=[80, 50, 80, 50, 80, 50, 50, 80, 80]
[fruit] [rl] picks placed 7/10 (continuous mode: the unit is the pick, not the episode)
[fruit] [rl] rollout success 7/10 (presentation=direct, ablate=none, seeds=[77], unit=pick)
```

* `[cont] enabled: picks_target=10` — the mode is explicit, and `feed=on(implied)`
  says the feeder it needs is on;
* **10** per-pick outcome rows (`[rl] episode 0..9`, one per pick) and **9**
  `[cont] pick k/10` rows — the transition rows start at pick 2 **by
  construction** (pick 1 begins at `reset`, so it has no "next pick" row); the
  15-pick P58 log shows the same 14-for-15 shape. 10 picks, 10 outcome rows;
* the summary is **pick-level**: `picks placed 7/10` and
  `rollout success 7/10 (... unit=pick)` — **not `0/1`** (F3 did not fire);
* **the per-pick `success` rows and the pick count agree exactly**: 7
  `success=True` of 10 rows, `placed=True` on the same 7, `placed=7/10` from the
  summary. The three failures are all left-arm `grasped=True placed=False`
  (pear 6.1 cm, tomato 5.3 cm, pear 6.8 cm) — the closed carried-not-placed
  class (`logs/p42/SIM_LIMIT.md`), not a supply event;
* one honest residue: `[rl] seed 77: 1/1 success` still prints the **episode**
  counter (here the last pick succeeded, so it reads 1/1; when the last pick
  fails it reads 0/1). **Read the `picks placed` / `unit=pick` lines** — that is
  the P58 finding, and this run confirms the fix: the pick-level line says 7/10
  while the episode-level line says 1/1.

Wall: 358.6 s for 10 picks = **35.9 s/pick**, the P58 profile-era order
(35.40); the sim span is flat (`ticks` 18.5 k).

## 4. The continuous video at the shipped profile — `logs/p59/p1/04_video_shipped.log`

`scripts/121_policy_video.py --episodes 1 --continuous 8 --seed 77 --capture-every 2`
with **no supply env** (all three knobs and `BAND_MAX`/`CONTINUOUS` unset);
the video dir's manifest confirms the shipped profile
(`cadence/band_interlock/direct_feed: true`, `band_max: 4`, `continuous: 8`,
`defaulted` all true).

**The belt stays stocked.** Per-selection census (`[bed-sel] attempt ...`), the
catchable `window` never reaches 0, and the one-sided class that ends a
continuous episode early never appears (zero `waiting for a candidate`, zero
`no candidate ... 40 feed rounds`):

| attempt | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| `on_belt` | 4 | 13 | 14 | 13 | 13 | 11 | 11 | 13 |
| `window` | 2 | 2 | 2 | 2 | 2 | 2 | 3 | 4 |

`on_belt` is the belt population, **not** a catch count (P58: at cap 4 the
below-station share is ~54 % of candidate rows); the catchable read is `window`,
which stays 2-4.

**`[cont]` gap classes:** only **50** and **80** ticks —
`gaps=[80, 50, 80, 80, 50, 50, 50]`, mean **62.9 ticks (0.52 s)** per transition;
3x80, 4x50, and **no 110** (P56's worst class) and **no ≥169 starved round**
(P58's loss counter). Every gap is the belt-side selection round, not arm travel:
8 picks ran back to back at 50-80 ticks of transition each.

**Per-pick outcomes** (`[rl] episode` rows; `placed` follows `success` 1:1):

| pick | fruit | arm | success | ticks |
|---|---|---|---|---|
| 1 | pear 6.1 cm | left | **False** (carried-not-placed) | 1884 |
| 2 | lychee 3.4 cm | right | True | 1826 |
| 3 | apple 6.3 cm | right | True | 1697 |
| 4 | peach 5.8 cm | left | **False** (`grasp did not land on the belt; re-running carry_and_release`) | 1837 |
| 5 | strawberry 3.6 cm | right | True | 1706 |
| 6 | peach 6.0 cm | right | True | 1820 |
| 7 | strawberry 4.3 cm | right | True | 1871 |
| 8 | orange 6.0 cm | right | True | 1872 |

`[cont] episode 7: picks=8/8 placed=6 ... gap_ticks=62.9`; the right arm 6/6, the
left 0/2 (both failures the closed left grip class).

**One limitation of the video entry script, recorded rather than fixed:** its
`video.json` `episodes` array holds one record per `--episodes` (here one: the
**last** pick, `orange`, success=True), and its final line reads
`[video] outcome 1/1 success` — an **episode**-level counter, not a pick-level
one. In continuous mode the per-pick truth is the log's 8 `[rl] episode` rows and
the `[cont] episode` summary; `121` has no `picks placed` line (that is `110`'s).
This is the P58 summary-fix scope (110/136), and it is why check 3 uses `110`.

**Files (untracked; `logs/` is gitignored, so nothing here was added or
committed):**

| file | frames / length | size |
|---|---|---|
| `logs/p59/video_shipped/observer.mp4` (annotated whole cell) | 1686 frames / 112.4 s @ 15 fps | 6.0 MB |
| `logs/p59/video_shipped/head.mp4` (policy's own camera) | 1686 / 112.4 s | 3.0 MB |
| `logs/p59/video_shipped/gripper.mp4` (pick-station close-up) | 1686 / 112.4 s | 5.4 MB |
| `logs/p59/video_shipped/side_by_side.mp4` (observer + head) | 1686 / 112.4 s | 11.1 MB |
| `logs/p59/video_shipped/video.json` + `direct_none_seed77/manifest.json` | provenance | — |

## What the owner should look at in the video

1. **The belt's continuity**, not the arm: from the first frame the belt carries
   fruit behind *and* ahead of the pick station (4 bodies at the first selection,
   then 11-14 for the rest of the clip) and it is still carrying fruit when the
   arm is placing — there is no "empty belt, arm waiting" stretch. The observer
   overlay shows the elapsed time and the policy step, so the absence of a wait
   is visible as picks that follow each other with no pause.
2. **The arm's back-to-back picks**: after a release the arm returns to the
   pre-pose and the next fruit is already inside the catch floor — the 50/80-tick
   transitions. Watch the right arm do six in a row (picks 2, 3, 5, 6, 7, 8).
3. **The two failures are the grip, not the supply**: pick 1 (left pear) and pick
   4 (left peach) both close on the fruit and lose it during the carry/place;
   nothing about them is a missing fruit. That is the closed carried-not-placed
   class and it is the left arm's.

## Reading rules (the honest part)

* **The placed counts above are branches, not rates.** The direct loop renders
  frames and is not bit-reproducible (AGENTS §3b), and every placed count on
  this tree carries the closed `cnp` grip class. `1/2`, `7/10`, `6/8` are three
  single-episode samples on three different branches (different fruit order,
  different left-arm draws); **no rate claim, no cross-check comparison, and no
  "the profile improves X" statement is made here.** Phase 3 owns the placed
  number (N = 3 x 15, the P43 protocol, the shipped profile).
* **Check 2 is one episode and one selection.** Its `window=4` is a post-reset
  burst instant, the same artefact P58 named; it is provenance, never a target.
* The wall numbers are harness costs (P58: 0.0194 s/tick at 12 live bodies vs
  0.0162 at 6), reported, not gated, and never attributed to the policy.
* Every line quoted above is copied verbatim from the named log; the profile row
  is byte-identical in checks 1, 3 and 4, which is the end-to-end claim: the same
  shipped default produced the demo (`--record`), the 10-pick run and the film.

## Files written by this phase

* `logs/p59/PREREG.md` (before any run), `logs/p59/DEMO.md` (this file),
  `logs/p59/run_p1.sh` (the driver), `logs/p59/verify_demo.py` (re-checks every
  line quoted here from the logs: **32/32 assertions PASS**).
* `logs/p59/p1/01_profile.log`, `02_pre58_recipe.log`, `02b_pre58_manifest.log`
  (the check-2 re-run that preserves the manifest), `03_continuous10.log`,
  `04_video_shipped.log`.
* `/tmp/p59_prof/direct_none_seed77/` (the 2-episode recorded store),
  `/tmp/p59_pre58/direct_none_seed77/` (the pre-profile manifest),
  `logs/p59/video_shipped/` (4 mp4s + `video.json` + manifest).

## P59 gate 1 corrections (Oracle, applied)

* **The film is 6 placed of 8** (`04_video_shipped.log:568`: `picks=8/8 placed=6`),
  right 6/6, left 0/2 - the earlier "7" in the gate summary was check 3's number.
* **The gap histogram is 3x80 + 4x50** (the list is `[80,50,80,80,50,50,50]`,
  mean 62.86); the prose said 4x80/3x50. `verify_demo.py` asserted the list, not
  the histogram, so its 32/32 stands - the error was prose only.
* **The film is one seed** (`--seed 77`). The phase plan's "2 seeds" was narrowed
  at registration time and never recorded; counts are branch-labelled anyway.
* **The profile row has a new token** (`target_from=0.35(default)`), so the four
  phase-1 logs carry the **pre-fix** row. The row's cap provenance was also
  fixed (P59 gate 1's bounded item): the cap now names its own default/explicit
  state and is printed **only when the interlock is on**, so a phase-2 arm with
  `FRUIT_SUPPLY_BAND_MAX=5` reads `band=on(5(explicit))(default)` instead of
  masquerading as the shipped default.
* **If phase 2 moves the cap default, this film becomes a pre-phase-2 artefact**
  and must be re-shot (`logs/p59/run_p1.sh 4`, ~6 min); if no default moves it
  stands as the shipped-profile demonstration.
