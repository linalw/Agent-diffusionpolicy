# P3 PREREGISTRATION: the place-leg shortening screen (the span is now the binding term)

Written before any run. 2026-10-16, branch `p-supply`, after `logs/p2d/RESULTS.md` (P2).

## Why this phase exists

P1/P2 removed the supply as the binding term: at D=1.60 the placement interval is 9.59-11.25 s
against a 9.4-10.2 s attempt span, i.e. the cell now places a fruit essentially every time an
attempt completes. The per-attempt **arm span is constant ~15 s** in every configuration measured,
and its decomposition (the 186 report, the left arm, 10 attempts) is:

| segment | s | share |
| --- | --- | --- |
| prepose + hover | 1.48 | 10 % |
| descent | 2.99 | 20 % |
| close + grip | 2.94 | 20 % |
| lift | 1.77 | 12 % |
| **place + release** | **5.22** | **35 %** |
| return | 0.60 | 4 % |

The place leg is the largest block, and its cost is **distance-proportional**: the measured
`[motion] carry placeN` rows give 45.5 cm at ~6.6 ticks/cm (control) and 48.5 cm at D=1.5 (the
extra 3 cm is the only reason it grows), with **zero IK recoveries** on every place leg. The place
goal is `jaw_target("placeN") -> cfg.output_belt_drop_points[index]` = **(x 0.43, y +-0.50)** while
the arm's station is at x ~ 0.28, y = 0.00 / -0.10: the transfer is therefore dominated by the
**~0.5 m lateral move**, and the output belt's inner edge is at |y| = 0.375
(`output_belt_center_y` 0.5, `output_belt_size` (1.10, 0.25, 0.05)).

So up to **0.125 m of the lateral carry is unnecessary** - the release only has to be *over* the
belt, and the belt carries the fruit away afterwards. That is the bounded lever: a default-off
`FRUIT_PLACE_INNER_SHIFT` that moves the release point toward the body, capped by the belt's half
width so the fruit still lands on it.

## The candidates (all default-off, scoped to the place leg)

| id | candidate | form | expected |
| --- | --- | --- | --- |
| **A** | `FRUIT_PLACE_INNER_SHIFT=0.10` | the release moves 10 cm toward y=0 (inside the belt) | place -0.7 s, arm span -5 % |
| **B** | `FRUIT_PLACE_INNER_SHIFT=0.11` | the cap-adjacent point (the belt's half width is 0.125) | place -0.75 s |
| C | the x-shortening variant (the release toward the belt's near end) | deferred: the arm's reach at the place height is not measured, so the cap is unknown | - |

The screen runs A and B (B is the dose check) on the **adoption candidate branch** (the two-line,
D=1.60), both supplies, with the controls already on disk (`logs/p2d/52_d160.log` patch D=1.60,
`logs/p2d/63_wave_d160.log` wave D=1.60).

## The criteria (pre-registered)

- **Primary**: the **per-attempt arm span** (the 186 report's per-arm `span` column) falls by
  **>= 4 %** with the success rate non-inferior (>= the control minus 1 attempt) and the pooled
  interval correspondingly better. Quoted as the per-arm segment table so the change is attributed
  to the place leg and not to a branch shift.
- **Secondary**: the placement throughput (placed/min) and the interval p90.
- **Fail conditions**: (a) any fruit released off the belt (the `[run] placed=False` count with a
  positive lift - a new class, since the lane's accounting is the placed flag); (b) a new failure
  note; (c) any descent outside its motion budget; (d) the carry cone on the place legs exceeding
  1.5x the budget (the shipped dynamic branch already reports 1.16-1.19x, so the ceiling is set at
  1.5x and the number is quoted per config); (e) a wedge or crash.
- **The no-harm**: the acceptance 9/10 + `fingerprint: matches` and `172` PASS on the final tree
  (the knob is default off, so the shipped streams must stay byte-reproducible); the `105` motion
  gate on every screen run.
- **Determinism**: the winning config gets a double-run bit-identity check.

## What this phase does NOT do

It does not flip any default (the density adoption is already open with the owner, and this knob
is a further scenario change). It produces one number - the achievable arm-span reduction - and the
verdict on whether the place leg is worth attacking further (the descent's documented boundary
shortfall is the next block, and it is a separate item with its own evidence per AGENTS.md).