# P43 phase 4 — integration: the park default, the naming, the pinned drivers

Measured/edited 2026-10-26. Oracle Gate 3 = **accept the adoption with four
amendments (A1-A4)**; this phase is the code + docs + commits.

## A1 — the state is named everywhere (code)

`src/fruit_sorting/rl_env.py`:

* the default lives in one module function, `resolve_arm_park(presentation,
  env_value) -> (name, defaulted)`: `back` on `presentation == "direct"`, `""`
  elsewhere, the env wins when set;
* `[rl] env ready:` now prints the resolved state — `park=back(default)` with the
  env unset, `park=ready(explicit)` for the escape hatch, `park=ready(shipped)`
  for a non-direct construction;
* the `[park]` row prints the name, its origin **and the per-arm resolution**:
  `park=back(default)[left:back,right:ready]`. The old row printed only the name,
  so the phase-3 B logs read `park=back` on a **right-inactive** episode whose
  right arm sat at `ready` (the config's vector is left-only). The token stays
  whitespace-free, so the pinned P35/P43 `[park]` parsers still read new logs;
* the manifest's `arm_park` block gains **`defaulted: true|false`** (absent =
  pre-P43), so a post-flip store, an explicit `=back` arm and a pre-P43 store are
  distinguishable.

Verified end to end with two one-episode direct rollouts (same seed, the
P35/P36/P37 patch scenario, `moe_v13s` `61da390a`):

| run | `[rl] env ready` | `[park]` row (band call) | manifest | outcome |
| --- | --- | --- | --- | --- |
| `A1_default.log` (unset) | `park=back(default)` | `arm_px=0 band_px=184 m2_ok=1` | `arm_park{name: back, defaulted: true}` | **1/1** |
| `A1_ready.log` (`=ready`) | `park=ready(explicit)` | `arm_px=234 band_px=52 m2_ok=0` | `arm_park: null` | 0/1 |

One episode each: a smoke that the wiring and the mechanism are live, **not a
rate** (the phase-3 numbers are the measurement).

## A2 — the pre-flip reproductions are pinned

`FRUIT_ARM_PARK=ready` is now explicit, with a comment, in the A arms of
`logs/p43/p3/run_batch.sh`, `logs/p35/run_p35b_ab.sh`,
`logs/p35/run_p35c_ab.sh`, and in `scripts/219_p36_cells.sh` cells **1 and 4**
(`ready`/`ready` and `ready`/park-proprio). Without it those batches would run
**A == B** after the flip. B/park arms unchanged; `scripts/223_p37_ab.sh` needed
nothing (its park is in `AB_EXTRA_ENV`, both arms).

## A3 — the wording the documents carry

* P4 (the left guard) is **"not failed", not "PASS"**: 1/21 -> 0/19 clears the
  -0.05 bar by 0.0024 = one episode; the informative read is the left's carried
  20 -> 18 (the built-in no-op).
* **P1 and P2 are one 3-way outcome counted twice** (`placed = n - carried -
  no-grasp`); the independent legs are P7/P8/P5/P6, and 5/5 at five runs has
  p = 0.031 as its **minimum attainable**, so P7 is the design's ceiling.
* **"0 carried" is 0/56** (<= ~5 % at 95 % by the rule of three) and **2 residual
  `force_min = 0` legs survive** (~8x reduced, not deleted).
* the band census's 1364 calls are ~56 clustered episodes => **"0 in 56
  episodes"**.
* **"94.6 %" is one draw of a non-reproducible loop** (CI ~0.85-0.99), not a rate.
* the **re-baseline rule**: every direct/policy number from now on is
  park-default; to reproduce a pre-P43 direct arm set
  **`FRUIT_ARM_PARK=ready`**; no park/no-park store mixing (P37's transfer
  confound); **no motion reference re-recorded** (the scripted gate never imports
  `rl_env`, so `fingerprint: matches` is an **import guard** — the P38-M4
  precedent, stated as a near-tautology).

## Verification

* `scripts/selfcheck.sh` -> `logs/p43/selfcheck.log`: **PASS, 0 failures, 1
  skipped**; the P43 leg is now `P43 selector + park` and pins the default/scope
  offline (direct -> `back`, handoff -> none, `=ready` restores, the guard and
  both label sites).
* `python3 scripts/96_motion_check.py`: all motion checks passed.
* `scripts/accept.sh` on the flipped default (`SKIP_SELFCHECK=1`) ->
  `logs/p43/accept_p4.log`: **6/10, 15.0 s/attempt, `gate_open=0.0 s`,
  `fingerprint: matches configs/motion_reference.json`**; its **377 filtered
  `[fruit]` lines are IDENTICAL** to `logs/p41/p2/accept_profile.log`, i.e. the
  scripted line is byte-unchanged (the exit=1 is the expected rate-only FAIL at
  the 75 % dynamic floor, the P32/P41/P42 state).
* No `configs/` file moved: `motion_reference.json` **8a399626**,
  `..._twoline.json` **2246f83c**, `arm_parks.json` `42ab4fb7`.

## Pins

`tasks.py` **`a1b3d673`**, `rl_env.py` **`0cefb13d`**, `control.py` `9384ff4f`,
`scene.py` `27e3d64a`, `policy/trigger.py` `b09d3cb2`, `policy/runtime.py`
`379ac706`, `meshes.py` `41efc522`, `fruits.py` `6f65e423`;
`scripts/224_p43_selftest.py` `2edd81de`, `scripts/selfcheck.sh` `58ec6862`,
`scripts/219_p36_cells.sh` `0efdcbbe`, `logs/p35/run_p35b_ab.sh` `02b1ddfe`,
`logs/p35/run_p35c_ab.sh` `ef59696c`, `logs/p43/p3/run_batch.sh` `79c3fb02`;
checkpoint `moe_v13s` `61da390a`.

## Files

```
logs/p43/p4/NOTES.md      this file
logs/p43/p4/A1_default.log  the flipped-default one-episode rollout (1/1)
logs/p43/p4/A1_ready.log    the =ready one-episode rollout (0/1), arm_park null
logs/p43/p4/raw/            the two rollouts' manifests + windows (small)
logs/p43/selfcheck.log      PASS, 0 failures, 1 skipped
logs/p43/accept_p4.log      the acceptance on the flipped default + the gate
```
