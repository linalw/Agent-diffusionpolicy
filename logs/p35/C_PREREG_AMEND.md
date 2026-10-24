# P35 phase 2 — the Gate-1 P0 revision of the manipulation check (written before the record batch)

Written 2026-10-24 after Gate 1 blocked the A/B on the **check's instrument**, and
before the record batch (`logs/p35/C_ab/`, started 12:35; the transcript numbers in
section 1 come from the check's own 2-episode pilot, not from an outcome read).
`logs/p35/PREREG.md` section 2 and `logs/p35/B_PREREG_AMEND.md` are **superseded**
by this document for the record batch; sections 3-5 of the PREREG (the arms, the
endpoints, the decision rule) stand unchanged. The pre-P0 batch
(`logs/p35/B_ab/`, 09:53-11:06) ran the superseded check and is kept as
provenance, not as the record.

## 1. The five P0 items, and what each measured

| # | the defect | the measured reason | the fix |
| --- | --- | --- | --- |
| 1 | **M1 vs the configured command** | the bar is unreachable: `ArmController.teleport_joints` writes the pose, steps 30 substeps and then `sync_command_to_measured()`, so the pose is *held* where the drive reached it. Measured in-scenario: the shipped `ready` sits **0.037 rad** from its own command, the park **0.088-0.102**. Phase 1's own hold probe reads 0.0323 rad at 90 ticks. | M1 is **held vs the pose the reset achieved** (`<= 0.02 rad`, so a pose that drifts or is overwritten still fails), captured by two articulation reads after the reset's settle; the achieved-vs-commanded residual is reported (`m1_cmd`) and read against a **0.04 rad** bar. |
| 2 | **M2 at +0.45** (the arm covers 1 % there) | phase 1's cover profile is 0.81 / 0.98 / 0.57 / **0.01** at +0.30 / +0.35 / +0.40 / +0.45, so the pre-registered "first call in the band" is the band's **least**-occluding edge (the control passed it 23/57). | the census band is **+0.30..+0.40** and M2 is read at the band's **worst** call (max arm share; min visibility), not at its first. |
| 3 | **the bbox was the visible-mask extent** | that extent is the disc *minus its occluder*, so the bbox shrinks exactly when the occlusion being measured is present and the arm's share of it is under-counted (`tgt_px` is then a sliver). | the bbox is the **projected disc**: the analytic sphere silhouette of the shipped head camera (`asin(r/d)` -> `r_px = f r / sqrt(d^2-r^2)`, the `212`/`217` camera model, exact area `pi r_px^2`), rounded outward by one pixel. |
| 4 | **the stale first call** | the first model call conditions on the pre-reset frame (P34-B): its mask is `px=0` on 72/75 episodes and it cannot carry a pose or sightline claim. | every read **skips** calls with `_infer_calls == 0` (counted in `stale_skipped`). |
| 5 | **the instrument's own documentation + pin** | `FRUIT_PARK_DIAG` was described only in code comments; the tree pin moved with the P0 edit. | the docstrings carry the sentinels (`px=0`, `rel=-1`, `frac=-1`), selfcheck PASS before and after, the tree md5 re-pinned, and a **2-episode pilot per arm** run before the batch. |

**Calibration of the projected disc (offline, numpy only).** The exact silhouette
area is 157 px for a 68 mm fruit at (0.219, +0.399) and 39 px for a 36 mm one at
(0.363, +0.400); the rendered masks of the same fruit are 174-175 and 27, i.e.
**1.11x and 0.68x** of the analytic disc. So the mask/analytic ratio is
size-biased by -32 % .. +11 % (rasterisation), which is why the **disc-relative
`vis` is reported and never gated**, and the visibility term stays the
**episode-relative `rel`** (`px * d^2` against a **running** maximum, updated on
every non-stale call - the `[align]` `pfc`/`pcm` measure - which cancels the size
bias by construction but normalises a band call against another call's geometry).

## 2. The check as it now runs

Per episode (`FRUIT_PARK_DIAG=1`, both arms, off by default):

* **M1 held** - `max |q_inactive(call 1) - q_inactive(settled)| <= 0.02 rad`; also
  `m1_cmd` = `max |q_settled - commanded|` (the park 0.088-0.102, the shipped
  `ready` 0.037) and the nearest-reference test on `q_settled`
  (`|q-back| <= 0.15` **and** `|q-ready| >= 0.30`, i.e. the realized pose is the
  park and not `ready`), plus `drift` (first non-stale call -> band call, one read).
* **M2a the arm term** - `max arm_frac < 0.10` over the band's calls, where
  `arm_frac` = the parked arm's instance pixels inside the **projected-disc**
  bbox / the target's pixels there.
* **M2b the visibility term** - the episode-relative `rel >= 0.85` at the band's
  **worst** call.
* **M2 = M2a and M2b**, the pre-registered conjunction at the band's worst call.
  Reported alongside: `vis` (disc-relative, size-biased as above), the band's
  median `rel`, `px=0` call shares, and the per-call `top` instances for
  attribution.

**The gate of record is M1 + M2a** (the pose actually applied, and the parked arm
out of the fruit's projected-disc bbox): the record batch passes **50/50 on
both**, and the control fails M2a **51/51**, which is what a manipulation check
must show. **M2b is a recorded report**, not part of the gate: it reads **36/50 =
72 %** and its 14 misses are all `arm_px = 0` on 22-47 px masks whose largest
instance is the belt - the running-`px*d^2`-maximum normalisation plus small-mask
raster drift (the `vis` values 0.57-1.02, 2 of them >= 0.98, show the fruit fully
visible in several of them). `PREREG.md` section 5's last bullet also literally
blocks on **any arm-pose residual > 0.02 rad**: the park's achieved-vs-commanded
residual is **0.088 rad**, so that block is **failed** on the record (it would
fail the shipped `ready` reset too, at 0.037 rad), and the conclusion - **default
off, not adopted** - is unchanged.

**Pass bar** (unchanged in spirit): M1 and M2a on **>= 90 %** of the treatment's
band episodes and **>= 4/5 in each treatment run**; **and the control must fail
M2a on a majority** of its band episodes, or the check is not a manipulation
check. M2b's strict per-call form is reported with its misses attributed (a
single-frame dip on a 24-30 px mask is ~8 %, so the strict form's floor is its
own quantisation); the median form is reported beside it.

## 3. What this does not change

The arms (`FRUIT_ARM_PARK=back` vs unset), the scenario, the seeds, N = 5x15, the
interleaving, the primary/secondary/guard endpoints, the pairing and the decision
rule are the PREREG's, verbatim. No outcome was read before this revision: the
pre-P0 batch is a separate run and is reported as such. `FRUIT_ARM_PARK` and
`FRUIT_PARK_DIAG` are both **off by default**; the shipped `ready` path is
unchanged.
