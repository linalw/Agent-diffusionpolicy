# P35 phase 2 — the manipulation check, corrected before the A/B (measured, not assumed)

Written 2026-10-24, **after the check was exercised on three smoke pairs and before
any A/B run** (no `FRUIT_ARM_PARK` A/B exists at this date: `logs/p35/B_ab/` does not
exist, and no outcome of this phase has been read). It amends `PREREG.md` section 2
only; sections 3-5 (the arms, the endpoints, the decision rule) stand unchanged.

## 1. What the pre-registered check measured on its own instrument

Three 2-episode smokes under the A/B scenario (seed 77, the same env as `PREREG.md`
section 3 plus `FRUIT_PARK_DIAG=1`): `logs/p35/12_smoke2_ready.log` (control) and
`logs/p35/13_smoke2_back.log` (`FRUIT_ARM_PARK=back`). The instrument is the new
default-off `[park]` row (one per episode) and the per-call `[park] call` census
(`rl_env.py`, `_park_note_call`); both read the frame the model call conditioned on.

**M1 as pre-registered (the inactive arm within 0.02 rad of the commanded vector at
the first model call) fails on both arms** — and that is a property of the reset, not
of the park:

| arm | inactive | `m1` (first call) | `m1_band` (first band call) | `q` at the first call |
| --- | --- | --- | --- | --- |
| control | left @ `ready` | 0.038 | 0.042 | -1.463, -0.374, 1.488, 1.315, -1.496, -0.588, 1.559 |
| control | right @ `ready` | 0.027 | 0.032 | +1.519, +0.330, -1.570, +1.269, +1.560, +0.620, -1.566 |
| `back` | left @ `back` | 0.091 | 0.102 | -1.910, -0.978, 1.504, 0.818, -1.498, -0.586, 1.559 |
| `back` | left @ `back` | 0.090 | 0.097 | -1.910, -0.978, 1.504, 0.818, -1.498, -0.586, 1.559 |

The shipped `ready` pose misses its own command by **0.027-0.038 rad**; the park misses
its command by **0.090-0.102 rad**, almost entirely on j1 (-1.910 vs -2.0005). The cause
is `ArmController.teleport_joints`: it writes the pose, steps 30 substeps, then
`sync_command_to_measured()`, so the **command re-bases onto whatever the drive reached**
— a 0.5 rad j1 move is not finished in 30 ticks, and the arm is then held at the
reached pose. So *no* pose in this env can meet a 0.02 rad bar at the first call; the
bar sits below the reset's own teleport accuracy, and the phase-1 hold probe's
0.032 rad at 90 ticks (A_READ section 2) already said so. The residual is **stable**
(`m1` -> `m1_band` moves by <= 0.011 rad) and reproducible (`back` at two episodes:
0.091 / 0.090).

**M2 as pre-registered (the first call whose along is in +0.30..+0.45) does not
discriminate**: it samples the band's *upper* edge, where phase 1's cover profile is
already 0.01 (`A_READ.md` section 2: 0.81 / 0.98 / 0.57 / 0.01 at +0.30 / +0.35 /
+0.40 / +0.45). At +0.449 the control reads `band_rel=1.000 arm_frac=0.092`, i.e. it
would **pass** while the same episode's band census reads `min_rel=0.005 max_frac=2.000`
at +0.373. A first-call-only check would pass the arm that occludes the band.

## 2. The correction (the same questions, read where the mechanism is)

M1 is a **proxy** for "the park was presented"; the sightline itself is measured
directly, so M1 is demoted to a report and replaced by the two readings that carry the
claim:

* **M1' - the park applied, at the pose the mechanism is about.** The inactive arm's
  realized vector at the first band call is **within 0.15 rad of the `back` vector** and
  **at least 0.30 rad from the shipped `ready` vector** (max-abs over the 7 joints, i.e.
  the realized pose is the park, not the shipped pose: measured 0.10 / 0.40) **and** the
  same vector is **stable across the band**: `drift` (max |q_band - q_first|) **<= 0.02
  rad**. A nearest-reference test is used instead of a fixed j1 delta because the park's
  realized j1 is -1.898..-1.910 against the commanded -2.0005, i.e. a j1 bar of 0.40 sits
  *inside* the teleport's own scatter. Both distances are computed from `q_band` by the
  report against `configs/waypoints.json` and `configs/arm_parks.json`.
* **M2' - the sightline in vivo, censused over the whole band** (`+0.30..+0.45`, every
  model call): the parked arm's pixels inside the target's own rendered bbox are
  **< 0.10 x the target's pixels at every call**, **and** the target's mask is
  **>= 0.85 x the episode's own depth-corrected maximum** (`px * d^2`, the `[align]`
  `pfc`/`pcm` normalisation) at every call. This is the pre-registered conjunction
  applied to the band instead of its least-occluding edge.

**Pass bar** (unchanged in spirit): M1' and M2' on **>= 90 % of the treatment's
episodes whose target enters the band**, and **>= 4/5 in each treatment run**; **and
the control must fail M2' on a majority of its band episodes**, or the check is not a
manipulation check and the phase makes no outcome claim.

**Both pre-registered readings stay reported** (`m1`, `m1_ok`, `band_rel`, `arm_frac`,
`m2_ok` are the first-call values; `min_rel`, `max_frac`, `band_all` are the band
census), so a reader can see exactly what the amendment changes.

## 3. What this does not do

It does not touch the outcome, the arms, the endpoints, the pairing or the decision
rule; no A/B has been run at the time of writing, so no outcome data informed it. The
band census rows (`[park] call`) are the provenance for M2' and are written by the same
default-off diag on **both** arms. `FRUIT_ARM_PARK` stays default off; the shipped
`ready` path is unchanged.
