# P59 phase 1 — pre-registration: prove the shipped direct supply profile end to end

Written **before any simulator run** (2026-10-28). Phase-1 brief:
`.slim/deepwork/p59-shipped-profile.md`. P58 shipped the direct supply profile
(`FRUIT_FEED_CADENCE` + `FRUIT_SUPPLY_BAND_INTERLOCK`(+`BAND_MAX=4`) +
`FRUIT_DIRECT_FEED` all on with **no env set**, for `presentation == "direct"`).
This phase asks one question only: **is that profile what actually runs, and can
it be shown to the owner?** It is not a rate measurement and not an A/B.

## Scope discipline

* **No `src/` or `configs/` edit. No commit. No default change.** Every run is
  read-only on the tree; the only writes are `logs/p59/`, `/tmp/p59_prof` (the
  recorded store of check 1) and the video output dir.
* One simulator at a time: every run goes through `scripts/154_claim_run.sh`
  (claims the sim, never kills another lane, stall guard).
* The video mp4s stay **untracked** (reported by path, never added to git).

## The tree this is measured on

```
HEAD 7d353e7
rl_env.py     6d7cb329   tasks.py        8ad8ddc8   fruits.py   c7461d41
scene.py      27e3d64a   control.py      9384ff4f   meshes.py  1ad5af0e
policy/trigger.py b09d3cb2
110_rl_rollout.py abd2b5f1   121_policy_video.py d04fc6ae
230_p58_supply_selftest.py 1cdb036e
checkpoint moe_v13s/policy_best.pt 61da390a
configs/motion_reference.json 8a399626 ; ..._twoline.json 2246f83c ; arm_parks.json 42ab4fb7
```

`rl_env.py` / `tasks.py` / `fruits.py` are the P58 pins, so any disagreement
below is the resolver's behaviour, not a stale file.

## The scenario (identical in checks 1, 2, 3 and 4)

The P58/P43 direct scenario, so the demonstration is the measured interface and
not a fresh one:

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_BED_DIAG=1
HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 FRUIT_POLICY_SEED=11
--ckpt checkpoints/moe_v13s/policy_best.pt
```

"**no supply env at all**" (checks 1 and 4) means exactly the three profile
members are unset: `FRUIT_FEED_CADENCE`, `FRUIT_SUPPLY_BAND_INTERLOCK`,
`FRUIT_DIRECT_FEED` (and `FRUIT_SUPPLY_BAND_MAX`, `FRUIT_DIRECT_CONTINUOUS`).
The scenario env above is *not* the supply profile; it is held fixed across all
four checks so the four logs are comparable. `FRUIT_POLICY_TRIGGER_ACQ` and
`FRUIT_ARM_PARK` are also unset everywhere (P54/P43 defaults are `on`/`back` for
`direct`), which is part of what check 1 verifies.

## Check 1 — the profile is what runs (falsifier F1)

```
--episodes 2 --seeds 77 --record --out /tmp/p59_prof
```

Pass requires **all** of:

1. the log prints, byte-for-byte,
   `[supply] direct profile: cadence=on(default) band=on(4)(default) feed=on(default)`
2. **not one** member reads `(explicit)` in that row;
3. `[rl] env ready: ... park=back(default)` (P43's default, still live);
4. the trigger row carries `acq=on(` (P54's default for `direct`);
5. the manifest `supply` block reads `cadence: true`, `band_interlock: true`,
   `direct_feed: true`, `band_max: 4`, `continuous: 0`, and `defaulted` all
   `true` (`cadence`, `band_interlock`, `band_max`, `feed`);
6. the recorded store exists under `/tmp/p59_prof` with `--record`'s files.

**F1: if the profile row or the manifest disagrees with (1)-(5), the flip is not
live — stop and report, do not run checks 2-4.** The two reads are independent
(the row is the resolver's own print, the manifest is what a store carries), so
agreement is evidence the *shipped* path — not a command line — produced it.

## Check 2 — the pre-P58 recipe reproduces the old path (falsifier F2)

```
--episodes 1 --seeds 77   with
FRUIT_FEED_CADENCE=0 FRUIT_SUPPLY_BAND_INTERLOCK=0 FRUIT_DIRECT_FEED=0
```

Pass requires:

1. the profile row reads **every** member `off(explicit)`;
2. the manifest `supply` block reads `cadence/band_interlock/direct_feed`
   **false** and their `defaulted` flags **false**;
3. the `[bed-sel]` rows of this run are recorded as the **pre-profile sample**
   (`on_belt`, `window`), quoted as **one episode, one sample, not a rate** —
   P58 already measured that the control's window count is a post-reset-burst
   instant, so it is a provenance reading here, never a composition bar.

**Pre-run prediction correction (read off `rl_env._resolve_supply_profile`
before any run; no code changed).** The brief predicts "`defaulted` all false",
but `band_max` has its **own** key (`raw_max is None`) and its value is keyed to
`direct`, not to the interlock flag — so this run is predicted to read
`band=off(4)(explicit)` in the row and `band_max: 4` with
`defaulted.band_max: true` in the manifest, while the three members under test
read `off(explicit)` / `false` / `defaulted: false`. That key is **inert** when
the interlock is off (`fruits.py` `_interlock_max` is only consulted under
`if self._band_interlock`), so it is recorded and explained here and is **not**
an F2 fire: F2 keys on the row's three members and on their three flags. If any
of the *three* reads `(default)`/`true`, F2 fires as written.

**F2: if the pre-P58 recipe does not read `off(explicit)` (or the manifest does
not read `defaulted` false), the resolver's precedence is broken — stop.**

## Check 3 — the multi-pick mode is explicit and its summary is pick-level (F3)

```
--episodes 1 --seeds 77 --continuous 10
```

Pass requires:

1. `[cont] enabled: picks_target=10` in the log;
2. **10** per-pick outcome rows (`[rl] episode ... success=...` — one per pick;
   `[cont] pick k/10` rows start at pick 2 by construction, so 9 of those is
   correct, not a shortfall);
3. a **pick-level summary**: `[rl] picks placed k/10 (continuous mode: ...)` and
   `[rl] rollout success k/10 (... unit=pick)` — **not** `0/1`;
4. a statement of whether the per-pick `success=True` rows and the pick count
   agree, and if not, the mechanism.

**F3: if the multi-pick summary still reads `0/1`, the summary fix did not land —
stop.**

## Check 4 — a continuous video at the shipped profile

```
scripts/121_policy_video.py --episodes 1 --continuous 8 --seed 77 \
    --capture-every 2 --out-dir logs/p59/video_shipped
```

No supply env (as defined above), same scenario env. Report:

* the `[cont]` **gap classes** (the distinct `gap_ticks` values and their
  counts, plus the episode's `gap_ticks` mean and list) — the gap is the
  inter-pick belt/selection wait, the quantity the continuous supply object is
  about;
* the **per-pick outcomes** (`[rl] episode` rows: category, success, notes) and
  the pick-level summary;
* whether the belt **stayed stocked** (`[bed-sel] on_belt`/`window` over the
  run, and the `[cont]` "waiting for a candidate" / "no candidate" lines — the
  latter must be absent);
* the four mp4s by path, with their sizes and durations.

## Falsifiers (all of them, and what happens on a fire)

| id | fires when | action |
|---|---|---|
| **F1** | check 1's profile row or manifest disagrees with the six conditions | **stop**, report: the flip is not live |
| **F2** | check 2 does not read `off(explicit)` (or `defaulted` false) | **stop**: the resolver's precedence is broken |
| **F3** | check 3's summary still reads `0/1` | **stop**: the summary fix did not land |
| **F4** | a run wedges (the known renderer freeze / a `154_claim_run` timeout) | **retry once**; a second wedge is reported as a blocked check |

## Reading rules (fixed before the numbers exist)

* **The placed counts in checks 1, 3 and 4 are branches, not rates.** The direct
  loop conditions on rendered frames and is not bit-reproducible (AGENTS §3b),
  and every placed count on this tree carries the closed `cnp` grip class
  (`logs/p42/SIM_LIMIT.md`). No rate, no cross-check count comparison, no
  "profile improves X" claim is made from phase 1. Phase 3 owns the placed
  number (N = 3 x 15, the P43 protocol).
* Check 2 is a **single episode**: its `[bed-sel]` row is one sample.
* Every quoted line is copied from the log file named beside it; the report
  names the log path for each claim.
* The video's own outcomes are the *clip's* outcomes; the annotation overlay is
  a diagnostic allowed in the control loop (camera + fruit pose reads, AGENTS §2
  — not the articulation-link readback).

## Post-run amendment A1 (2026-10-28, after checks 1-4): the check-2 manifest needed its own `--out`

Check 2 was registered above **without** `--out`, so it wrote the shared scratch
path `datasets/rl_rollouts/direct_none_seed77/manifest.json` — and check 3 (also
without `--out`) overwrote it before the manifest could be archived. The evidence
is therefore a **same-command re-run with a private `--out`**
(`logs/p59/p1/02b_pre58_manifest.log`, `/tmp/p59_pre58/...`), which reads the
byte-identical profile row and the identical first selection
(`on_belt=5 window=4 pick=apple@0.642`). **No registered condition changed**:
the pass condition is the row (`off(explicit)` x3) plus the manifest's three
members/flags, and both are read from that run. The rule this adds for the next
phase: *a check that must leave an artefact behind passes `--out`*.
