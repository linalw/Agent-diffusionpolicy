# P38 — The delivered-x drift tail + the harness's no-re-selection (the S3-class cleanup)

Started 2026-10-25 (owner: "继续", the P37 Gate-2's named next). Full delegated
authority; an Oracle gate per phase.

## 1. The facts (P37 Gate 2)

- The supply's **delivered** lateral x is **0.148-0.364 m** (p10 0.205, p50
  0.279, p90 0.348; `logs/v1/12b_supply_after_free.log:409`) against the
  designed spawn band 0.20-0.36: a ~5 cm downward drift tail.
- The trigger's lateral gate 0.16 (the arrival, the station 0.333) admits
  **x >= 0.173** -> the tail **0.148-0.173 (~2.5 cm)** is systematically
  unfirable (~1 %/episode; the P37 S3 event 1/92 right-arm at x=+0.159).
- **Do not widen the gate**: the reach residual at x=0.160 is 8.3 mm (the
  handover tolerance 6 mm) - marginal, not a flail; widening trades a no-fire
  for a grip-quality failure (`logs/v3/60_station_reach_edge.log:378-379`).
- The harness: on a lateral refusal the env does not re-select -> the
  **1500-tick timeout class** (`rl_env.py:2668-2674`); a mechanical rule with no
  severity weight, which will keep producing S3-style false positives in every
  direct A/B.

## 2. The levers (to measure, not assume)

1. **The harness's re-selection** on a lateral refusal (pick another eligible
   fruit) and/or an explicit **"no eligible fruit"** outcome class instead of the
   timeout - the direct fix; the outcome-class change needs its own
   pre-registration.
2. **The supply/transport drift tail**: the release x band's floor / the
   transport's lateral control so the delivered x stays inside the reachable
   band (a scene change; the references re-recorded).

## 3. The plan

| # | Phase | Deliverable | Owner | Gate |
|---|-------|-------------|-------|------|
| 1 | The measurement + the pre-registration | **DONE 2026-10-25**: `logs/p38/P1_RESULTS.md` (the delivered-x tables per scenario, the mechanism, the S3 census) + `logs/p38/PREREG.md` + `drift_census.py`/`probe_drift.py` | @general | Oracle 1 |
| 2 | The lever A/B | the chosen lever(s) + the endpoints (the S3-class elimination, the rate non-inferiority, the no-harm) | @general | Oracle 2 |
| 3 | The integration/adoption | the docs/commits; the adoption recommendation | @general + orchestrator | Oracle 3 |

Oracle budget: 3 gates (1 initial + up to 2 re-reviews each).

## 4. The risks

- The drift tail is small (~1 %); the harness's re-selection changes the outcome
  classes (the new "no eligible" class); the supply x-band changes the scenario
  (the references).
- The S3 gate's severity (the P37 lesson: a mechanical rule with no severity).
- The direct loop's variance; the N.

## 5. The log

- 2026-10-25: the file; the plan; Phase 1 dispatched.
- 2026-10-25 (phase 1, done): **the measurement + the PREREG.**
  - `logs/p38/drift_census.py` -> `logs/p38/drift_census.txt`: the delivered-x
    per scenario (scripted attempts deduped against bit-identical replays; the
    direct band census per episode), the per-arm admission floor, and the S3
    census over 549 direct-loop logs.
  - `logs/p38/probe_drift.py` + 5 claimed runs: **the transport's lateral
    contribution is exactly 0.000 mm over 475 transits**; the release/settle is
    the only stage that moves x, as a **fixed per-instance offset**
    (-35.9..+69.2 mm across the two seeds' pools); the belt/cleat/friction/
    rolling drift hypothesis is **falsified**.
  - The S3 class on the shipped interface is **2/3103 = 0.06 %** (one kiwi at
    x=+0.159 the P37 event, one peach unrecorded; both below the right floor
    0.1730; the left floor is **0.1800**), plus one low-x episode that ended as
    `fruit fell off the line` (x=+0.162). The opt-in guard's 2/120 are the
    *high*-x refusals. At 0.06 % no A/B at WS-4.2 N can measure the class.
  - `logs/p38/PREREG.md`: the harness lever (attribution + terminal class +
    bounded same-lane re-selection), four default-off direct-only knobs, three
    arms, four scenarios (M1 forced band / M2 mixed band / M3 shipped-band
    safety / M4 scripted no-harm), seven endpoints, six falsifiers, and the
    `no firable fruit` rule (still a failure in the rate denominator -
    attribution, not elimination).
  - The supply lever is arithmetic'd and **deferred to P38b** (floor >= 0.237
    with the ceiling >= 0.38; three references + the acceptance + both
    two-line gates + every store), with the better form named: per-instance
    settle-offset compensation at `respawn`.
  - AGENTS.md paragraph + WORKLOG entry written. No `src/`, `configs/` or
    default change (pins in `logs/p38/MD5.txt`).
- 2026-10-25 (phase 2, done): **the harness lever, measured - attribution + the
  terminal class hold, the re-selection is structurally inert, the shipped band
  saw one refusal and it fell in the control arm.**
  - `PREREG_A1.md` (the Gate-1 amendment, pre-data): H1 the terminal class is a
    *measured joint closure* (the trigger refuses + `x` frozen + the learned
    close never fired through the fruit's departure) because the lateral gate
    has never bound `policy_close`; H2 the registered supply bands are **not**
    bands (a 4 cm lane depenetrates: delivered 0.117-0.191, 12 % above the
    floor; envelope 0.080-0.529) so M1/M2 force the refusal with the **gate**
    (`LATERAL=0` / `0.06`) on the shipped supply; H3 P4/P6 are run-level
    unanimity gates; A2d splits P2 into correctness (gated) and supply
    (reported); A5 makes P5 symmetric at the note level.
  - The four knobs implemented (`trigger.py` `b09d3cb2`, `rl_env.py`
    `f25f6b61`), default off, direct-only, byte-inert unset (M4: 376/376
    `[fruit]` identical, fingerprint matches, selfcheck PASS).
  - M1 (forced, SEED=5): **15/15 refused in A/B/C**, P3 `no_firable` 10/15 and
    9/15 at median **562/510 ticks vs 1335**, C 54 scans / **0 adopted**, and
    **5-6/15 episodes still picked by the learned close (3 placed)** - H1
    confirmed empirically.
  - M2 (mixed `0.06`): refused **62 % (A) / 47 % (C)**, terminals `fell-off`
    23 + close 5 (A) vs `no_firable` 19 + close 2 (C); **83 scans, 0
    candidates** → the re-selection is inert because the **feeder is frozen
    inside an episode** (the amendment's starvation hypothesis superseded).
  - M3 (the patch band): **1 refusal in 150 (0.67 %)**, in **A** (x = 0.157);
    P4 **+0.039 [-0.138, +0.220]** PASS, P6 **-2.0 %** PASS, **P5 FAIL** on
    that single episode's two notes → the pre-registered rule reads **not
    adopted**, with no harm evidence attached.
  - Recommendation: DIAG as the direct diagnostic, END as the measurement
    interface (a B-arm safety batch first), RESEED not adopted. Record
    `logs/p38/P2_RESULTS.md`; docs `AGENTS.md` + WORKLOG "P38 phase 2".
- 2026-10-25 (Gate-2, applied): **the two conditions the batch left open are
  closed by measurement - and H1 comes back negative.**
  - `logs/p38/G2/` (one claim, `bash scripts/225_p38_batch.sh g2`): the
    **DIAG=0/1 pair** on the M1 band, 15 episodes each, `G2_diag0` with no knob
    and `G2_diag1` with DIAG only. `rl_env.py` `dba80de6` (one `[refuse]
    close:` print, DIAG-gated, no control read), `225` `eae2d89a`.
  - **H1: falsifier #1 FIRES.** The close tick's `dy`: ep 2 `+0.071`, ep 9
    **`-0.074`** (after the departure - the jaw chased 7.4 cm past the station
    and closed, then lost the grip), ep 13 `+0.314`. So C3 is not a total
    closure: the class is "no close **before** the departure", it over-claims on
    1/15 of the forced band, and a flip needs a re-registered definition or a
    post-departure grace window. The shipped-band readout is owed in the B-arm
    batch.
  - **H4: the pair measured, the claim withdrawn.** `diag0` 2/15 placed,
    `diag1` 0/15, class agreement 9/15 (fruit 6/15); the **DIAG=1 vs DIAG=1**
    repeat reads 14/15 (12/15), so the loop's own agreement is not constant and
    one pair cannot demonstrate neutrality at n=15. "A behaves as the control"
    is replaced by the pair + the construction argument (no control input).
  - Carried corrections: P5's structural false-fail; M4's near-tautology +
    `accept_policy.sh` omitted (the knobs raise off `direct`); the 39.2 %
    right-arm base (the left drags the *pooled* rate); the direct loop's
    non-reproducibility as the arm-mix cause; A's M1 "ends at the horizon" as a
    recorded deviation (12/15 fell-off, 0 timeouts) with the END's strength
    re-stated; the low-edge-only envelope; A1's C2 note-vs-row. Three latent
    defects named (protect leak, station-vs-jaw frame, END-before-fire +
    per-episode gap). `p2_report.py --g2`; `P2_report.txt` regenerated.
