# P18-B L3 stage-N results: the pre-onset load path (C1) on the direct interface (2026-10-19)

Status: **the pre-registered endpoint does not resolve — VERDICT: no measured improvement
(the sign test degenerate).** The raw rate delta is large (A 22/75 = 29 % vs B 39/74 = 53 %) but
the two arms' fruit streams diverge, so 58 of 74 episodes carry no pair and the class mix
confounds the pooled rate. Nothing is adopted; the class-matched re-run is the named next.

## 1. The protocol (and its deviation)

The R11-B's stage-N pre-registration: 5 runs/arm x 15 episodes, seeds [77,101,202,303,404],
sampler seed 11, interleaved A,B; the full stage-N env both arms
(`FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1`); arm A = the shipped checkpoint
(`moe_v13s`), arm B = the same checkpoint + `FRUIT_CLOSE_LOAD_RATE=0.04` (the C1).

The **v1 battery was voided** (the Oracle Gate-2 intercept: the missing env made B ≡ A; the
records are at `logs/p18b/N5_invalid_env/`). The **v2 battery passed its precondition check**
after A run 1: the manifest's `trigger.mode=arrival`, `acq=True`, 27 `[carry]` rows, 15
"intercept trigger" notes, 4/15 in the band (`check_preconditions.py`).

**Deviation:** B run 5 (seed 404) **wedged** at episode 14/15 (82 min for 14 episodes, the known
renderer freeze) and was stopped; its 14 logged episodes are used. The battery therefore reads
A 22/75 vs B 39/74.

## 2. The numbers

| endpoint | A (control) | B (C1=0.04) | reading |
| --- | --- | --- | --- |
| pooled rate | **22/75 (29 %)** | **39/74 (53 %)** | **+24 points raw** — but see the mix confound |
| the sign test (paired) | — | — | **p = 0.5000**, 5 discordant: 3 B-only / 2 A-only; **58/74 excluded** (the fruit class differs) |
| the cycle | 1828 ticks | 1781 ticks | −2.6 % (not slower) |
| failure reasons | the standard set | the same set | **no new reason** |

The class table (the arms' mixes differ because the presentation is behavior-dependent):

| class | A | B | delta |
| --- | --- | --- | --- |
| apple | 2/6 | 8/13 | +28 % |
| kiwi | 2/6 | 4/8 | +17 % |
| lychee | 4/8 | 2/8 | −25 % |
| orange | 1/13 | 2/10 | +12 % |
| peach | 2/9 | 3/7 | +21 % |
| pear | 1/8 | 2/8 | +12 % |
| strawberry | 5/11 | 7/8 | +42 % |
| tomato | 5/14 | 11/12 | +56 % |

## 3. The verdict and the honest read

**The pre-registered endpoint fails**: the paired protocol cannot resolve (58/74 episodes have no
pair because the two arms' streams diverge), so the sign test is uninformative (p = 0.5). The
shipped `113_rl_report.py` verdict stands: **no measured improvement — publish the negative**.

The raw numbers are striking (29 % → 53 %) and the class-standardized deltas are positive on 6 of
8 classes (the two negatives have n = 8-13 at 1-2 episodes). But three confounds keep this
hypothesis-grade, not a result: (1) the **class mix** differs by arm (tomato 5/14 vs 11/12 alone
moves the pooled rate by ~10 points); (2) the **presentation order** is behavior-dependent, so a
better arm sees a different (possibly easier) stream; (3) the pairing is empty. Per the standing
discipline (one sample of a frame-conditioned loop; the outcome quantized), a pooled-rate delta
across divergent streams is not the endpoint.

## 4. THE CORRECTION (2026-10-19, the Oracle Gate-3 re-analysis): the C1's effect IS real

The Oracle's Gate-3 review (`logs/p20/ORACLE_GATE3.md`) re-analysed the same logs by **outcome
class, stratified by fruit class** — the read the episode-pairing protocol aborted. The counts:

| arm | ok | no-contact | carried |
| --- | --- | --- | --- |
| A | 22 | 5 | **48** |
| B | 39 | 9 | **27** |

**The carried class nearly halves (48 → 27) at a +4 no-contact re-draw.** The class-stratified
exact randomization test: observed A = 22 against a stratified null mean of 30.30 (SD 2.82),
**one-sided p = 0.0026**; MH OR (B vs A) 1.79; CMH chi2 = 8.68 (p ≈ 0.003). **Every one of the 5 B
runs beats every one of the 5 A runs on the carried class.** The mix confound the record's
section 3 cites is removed by the stratification (the per-class comparison is within-class); the
failed endpoint was the **episode pairing**, not the lever.

**So the verdict is restated**: the pre-registered episode-pairing endpoint does not resolve (a
protocol weakness), but the lever's outcome-class effect is **significant and run-consistent** —
the first direct-interface lever in the record to move the carried class. The C1 stays
default-off until the confirmation the ranking asks for (the scripted two-line battery, launched:
`logs/p21c1/run_c1_twoline.sh`; and, if that confirms, the direct no-harm).

## 5. The named next

* **The C1 on the scripted two-line** (the Oracle's rank-3, running): the deterministic mass-base
  battery (seeds 11/5/23 + doubles) with `FRUIT_CLOSE_LOAD_RATE=0.04`; the endpoint = the total
  failure mass (nc + carried) + the falls + the census, vs the on-disk controls (45/8/7).
* The class-matched direct re-run stays an OPEN option (the tomato single-species pool collapsed
  to carried 13/15 - a scenario artifact; the strawberry/apple probes are on disk:
  `logs/p18b/20_species_*.log`) — lower priority than the two-line confirmation.

## 6. Provenance

* Runs: `logs/p18b/N5_fix/{A,B}_{1..5}.log` (chain `run_n5_v2.sh`; driver `91_driver_v2.log`);
  the precondition `check_preconditions.py` output above; the void v1 at `logs/p18b/N5_invalid_env/`.
* Pins: `checkpoints/moe_v13s/policy_best.pt` `61da390a`; `tasks.py` `3d88408d`;
  the manifests under `logs/p18b/N5_fix/raw/*/*/manifest.json`.
* The report: `scripts/113_rl_report.py` (the standard read; the pairing exclusions are its own
  rule).
