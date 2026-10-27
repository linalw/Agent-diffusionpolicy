# P54 phase 1 - pre-registration: the shipped direct configuration (ACQ off) vs ACQ=1

Written **before** the battery's first arm finished (`logs/p54/p1/P1_header.txt` is
timestamped at the batch start; this file is committed only as evidence and changes
nothing the batch reads). Tree at registration: HEAD `c717de0` (P53 close); `configs/`
untouched, `src/` untouched by this phase.

## 1. The gap being measured

The direct interface's post-park baseline - **right 94.6 % placed (53/56), left 4.8 %
(1/21)** - is an **ACQ=1** number: every park-era batch (P35/P36/P37/P43/P53) runs
`FRUIT_POLICY_TRIGGER_ACQ=1` in its scenario block (`logs/p52/MODEL_CENSUS.md` §4-§5,
PREREG S2 there). The **shipped** default is ACQ **off** (W7-B; R5 decision 4 keeps the
knob default-off, `src/fruit_sorting/policy/trigger.py:167`), and `60_eval_policy.py`
(the hybrid canary) never runs the direct trigger at all. **So the shipped direct
configuration has never been measured.**

Mechanically the knob is a fire-time change: `acquisition_window()` extends the lead
`0.90 s` by `acq_margin 0.60 + |jaw-station| / acq_speed 0.20` (cap `4.5 s`) and raises
the reach gate with it, so ACQ=1 fires earlier and from farther away (a logged fire
reads `lead=2.14s/reach=0.31` instead of `lead=0.90s/reach=0.20`). It is **env-only**:
`trigger.py:167` is the only reader, unset = `"0"`, no `presentation` guard and no
`configs/` field.

## 2. The battery (the P43 protocol verbatim, one variable changed)

`checkpoints/moe_v13s/policy_best.pt` (`61da390a`) on **both** arms, the W6-A/W8-A
patch sheet (`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`, balanced A:B:C
0.375/0.375/0.25), `FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
FRUIT_DYNAMIC_PICK=1`, the park **default** (`back`, P43), **N = 3 runs x 15 episodes**
per arm, seeds **77/101/202**, policy seed 11, interleaved **A then B** per seed, one
`154_claim_run.sh` claim for the whole batch, no `--record` (nothing in this phase's
endpoints reads a store).

| arm | meaning | env |
| --- | --- | --- |
| **A** | **the shipped config** | `FRUIT_POLICY_TRIGGER_ACQ` **unset** |
| **B** | the measured config (the 94.6 % number) | `FRUIT_POLICY_TRIGGER_ACQ=1` |

Instruments on **both** arms (AGENTS §3b: the instrument sits inside the contrast):
`FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_PARK_DIAG=1`.
Manipulation check, from the logs themselves: `[rl] trigger=...` prints `acq=on(...)`
in B and nothing in A, and the fire notes carry `lead=`/`reach=` per arm.

## 3. Endpoints

**E1 - the shipped config is not worse than ACQ=1 on the right arm (the open
question).** The primary is the **right-arm placed rate pooled over 3x15**, delta =
`rate_A - rate_B`, bar **>= -0.10** (the P37/P43 non-inferiority margin). Reported
beside it: the per-seed pair (all three), the paired sign test on discordant
`(run, episode)` pairs with the same fruit class (`scripts/113_rl_report.py`), and the
pooled placed with the left arm as its own row.

*Power is a stated limit, not a discovery:* at ~40-50 right-arm episodes per arm a
0.10 point rule is ~1.2-1.4 sd at a 0.6-0.9 base, and P38 phase 2's H3 measured what a
single event does to an arm-level key. So a delta inside the bar is read as
**non-inferior at this n**, never as equal, and a delta outside it is reported with its
per-seed spread before any conclusion.

**E2 - does ACQ=1 reduce the pre-contact acquisition class?** Two registered readouts:
(a) the **never-held class** (`grasped=False`) as a count and a rate, per arm and per
side, split into trigger-path vs policy-gate fires (the knob cannot reach a gate fire);
(b) the mechanism, from the `[acq]` rows: the **catch-up residual** `res=` (mm, median
and max, and the share above the 6 mm tolerance) and the **close-start tip-fruit
offset** |y| (the W7-B endpoint: left no-contact 9 -> 1, close-start median 88.8 ->
1.4 mm). E2 is read as **mechanism first**: if the residual / close-start distribution
moves, the class should follow; if it does not, the knob did not act on this interface.

**E3 - no new failure reason.** `113_rl_report.py`'s digit-normalised note keys; a key
that appears in the arm that is *not* the baseline is "new". Baseline = A for this
direction (A is the shipped configuration), so the reported set is `B - A` **and**
`A - B` (both are printed; whichever is non-empty is named).

**The left arm** is reported and is **not** an endpoint: 94.7-95.2 % of its failures are
carried-not-placed (the closed grip class, `logs/p42/SIM_LIMIT.md`), and
`configs/arm_parks.json` has a left-only park vector so the park never moves it (the P43
no-op guard).

**No rate claim beyond this interface.** The direct loop conditions on rendered frames
and is not bit-reproducible (AGENTS §3b), so every count here is one draw of a
configuration; the per-leg/per-episode mechanism rows are the measurement.

## 4. Falsifiers (written before the run)

1. **F1** - if A's `[rl] trigger=` line carries `acq=on`, the arm did not resolve the
   shipped default and the battery is void (a knob typo would read as a null).
2. **F2** - if the fire `lead=` distribution is identical between arms, the knob did
   not fire and E2 is **not evaluable** (report that, not a null).
3. **F3** - if the A arm reads a rate outside the 5-8/10 canary spread's neighbourhood
   *and* its right-arm count is below A's P43 control by more than the right arm's own
   run-to-run spread, the shipped default is a **regression to report**, not a lever to
   tune - the phase would then hand the question to the owner (R5-4 is a decision, not a
   measurement).
4. **F4** - a wedge (the known renderer freeze) that stops an arm mid-run is recorded as
   a missing run, not replaced by a silent retry; the batch continues.
