# P91 PREREG — the take-off validation ramp as a two-line-scoped tick cell

Pinned **before any run of this phase**. `logs/p91/PREREG.md5` is this file's md5
and the battery's `header.txt` records it. The audit that motivates the pick is
`logs/p91/AUDIT.md` (itself offline, from records that predate this phase:
`logs/p87/T5.log`, `logs/p86/C5.log`, `logs/p89/C5.log`).

## 0. The question, and what the owner excluded

The owner wants the **single-pick cycle** faster with the fruit-waiting time
**excluded** ("不包含等果时间"). The shipped cell's per-arm attempt span is
**15.34 s** (`logs/p87/T5.log`; the sum of the eight blocks the P87 table quotes),
decomposed by `[cycle]` into `descent 3.64`, `place 3.14`, `grip 2.36`,
`release 1.70`, `lift 1.68`, `close 1.36`, `hover 0.75`, `prepose 0.71`
(+`return 0.66`, `end 0.03`). `place`, `lift` and `release` are measured
(`logs/p88`, `logs/p89`, `logs/p87`). The other five total **8.82 s = 57 %** and
have never been profiled as levers. P91 owns those five.

## 1. What the audit found (the reason for this cell)

| block | mean | speedable | why |
| --- | --- | --- | --- |
| descent | 3.64 | **0.00** | the block is **schedule-invariant**: the wait exits at `speed*(t_desc+margin)`, so `block = lead/speed − margin`; the profile's 0.74 s of motion is absorbed 1:1 by the wait (`logs/p91/AUDIT.md` §3) |
| **grip** | **2.36** (clean **1.75**) | **0.50** | the only block of the five holding a real profile: the **60-tick** take-off validation ramp over 6 mm. The 54-tick belt-break beside it is the P3 anti-shear constant and is **not** part of this cell. The block's 0.61 s of regrasp tax is **measured, not sped** (P40's cap already at 2) |
| close | 1.36 | 0.20 | the 48-tick post-contact hold; the direction is **contested** (R11-B/P18b measured a *slower* close converting the direct carried class 48 → 27) |
| hover | 0.75 | 0.00 | `move_to` at the IK step cap — no profile to raise; R3's residency (the related lever) is negative |
| prepose | 0.71 | 0.38 | a tuned 45-tick blend + a 20-tick session pump; R3's residency applies |

So the **largest genuinely speedable block of the five is the grip**, and inside
it the largest single profile is the probe ramp. The probe's tick count is a
**1:1** lever on the block, proved on the records' own difference: the single-arm
40-tick probe's clean block is **190 ticks** and the two-line 60-tick probe's is
**210** — Δ 20 = the probe's own 20, with an identical 150-tick remainder
(`logs/p91/AUDIT.md` §4).

## 2. The cell

`PROBE_TWO_LINE_DEFAULT` — `FRUIT_DYNAMIC_PROBE_TICKS` resolved through
`tasks.probe_ticks_resolution(two_line)`:

| env | two-line session | resolves |
| --- | --- | --- |
| unset | yes | the cell **24** ticks (`origin=default`) when the constant is on |
| unset | no | the shipped single-arm **40** (`origin=single`) |
| explicit | any | that value (`origin=explicit`) — the knob's pre-P91 meaning |

**Rate only.** `FRUIT_DYNAMIC_PROBE` (the ramp's height, 6 mm in a two-line
session) and `FRUIT_DYNAMIC_TAKEOFF_MATCH`/`_TRANS` (the belt-break, 0.20+0.25 s)
are read unchanged, so this is the same 6 mm lift over 36 fewer ticks — 0.10 →
0.25 mm/tick, still **3.7x slower** than the 50 mm lift that immediately follows
it in the same grasp (0.93 mm/tick), which is the mechanism argument that the
ramp has rate margin: the payload is lifted 8x faster 0.45 s later without a
documented failure class.

**Why scoped.** The site (`grasp_carry_place`) is shared with the single arm, the
shared-station pipeline and the hybrid canary, none of which this phase measures.
The two-line's 60 was already a `_dynamic_profile` scoped literal, so the flip is
the same kind of literal.

## 3. Prediction (registered before the run)

* **the `grip` block, median over 20 attempts: 2.36 → 2.06 s mean /
  1.75 → 1.45 s clean** = **−36 ticks = −0.300 s** (P1a), band **±0.04 s**
  (the block also holds the fixed belt-break and the tick-boundary rounding).
* **P1b the per-attempt paired read**: for the attempts that are clean in both
  arms (`grip <= 1.9 s`), the delta is **−0.300 s ± 0.02** on every pair. This is
  the branch-free instance; a *mean* across mixed lengths is not (P88 §1, P89 §1).
* **attempt span: −0.300 s**; the cycle excluding the fruit wait
  (15.34 − 2.75 = 12.59 s) improves **2.4 %**; the whole span **2.0 %**.
* **the delivered interval: expect flat** — the pooled interval is
  `attempts/placement x span + idle`, and four prior registers (the place cap,
  the lift cap, the speed union, the fail-fast) all measured the block moving and
  the interval *not* following because the acquisition re-draws at those ticks.
  Registered expectation `Δinterval = −0.4 s ± 0.8` (i.e. **not separable** at
  20 attempts/seed). This is the phase's honest expected value: **the cell can
  deliver at most 2.0 % of the 15.34 s**, and the whole five-block pool is 7.0 %.

## 4. Endpoints

Every delivered endpoint is P80's (`logs/p80/p80lib.py`): a placement is the
attempt's `t1`, the placement window is `t_last_place − t_first_place`, the batch
span is `t_last_end − t_first_start`, the wall comes from the `.stamps` stream.
Nothing is re-derived.

| id | endpoint | PASS |
| --- | --- | --- |
| **P1a** | the `[cycle] grip=` block, **mean and median** over the 20 attempts, per seed | mean and median both fall by **0.30 ± 0.04 s** |
| **P1b** | the **paired** delta over the attempts clean in both arms | **−0.300 ± 0.02 s** on every pair, n >= 4 |
| **P2** | the pooled **interval** (both arms) at **both** seeds | falls at both seeds -> clean pass; flat at both (|Δ| < 0.10 s) -> considered trade; **rises at either -> FAIL** |
| **P3** | the landing (`FRUIT_PLACE_TRACE`, payload present at the release) | `on_belt` on **every** guest trace, in the control's height/impact/bounce band |
| **P4** | the class | no new failure-reason key at either seed after mapping; place-leg escapes <= the control's; `never-grasped` not worse than +2/seed |
| **P5** | **the catch window** (the descent's own guard) | the `dynamic catch-up: residual` median not up by > 1.0 mm; the `[motion] approach … end=` max <= 25 mm; the **grasp rate** >= 14/20 per seed |
| **P6** | the motion gate | every descent inside `105`'s budget (never re-tuned) and `190` PASS on the control against its own 20-attempt reference; the treatment is **DIFFERS-by-construction** (a re-timed presentation) and is gated on **budgets only** |
| **P7** | the guards that make the trim safe | the delivered pinch (`[carry] force_min` median over held legs) stays at the P41 plateau (**>= 9.0 N**, the shipped 9.45-9.93); the `[carry] clean_slip_max` distribution does not worsen (the loaded-slide guard: `force_min == 0.00 N` legs not worse than +2/seed) |
| **P8** | the inertness pair | `FRUIT_BIARM=0 scripts/accept.sh` **raw 346/346** against `logs/p71/accept_rails_none.log` + `fingerprint: matches configs/motion_reference_single.json`; **and** a fresh unset two-line run replays the pre-change record (`logs/p89/T5.log`) on the `[fruit]` stream with only the new `[biarm] take-off profile:` row dropped |
| **P9** | the provenance | `physics.takeoff` in **both** manifest writers (`scene._takeoff_provenance`), the `[biarm] take-off profile:` row naming the resolution, the `250` selfcheck leg |

## 5. Guards (all pre-registered)

1. **The catch window is read before the outcome** (P5) — the descent is the
   block the probe is downstream of, so if the residual or `end=` move, the
   re-timing is implicated and no rate claim is admissible.
2. **The probe's own function**: `grasped` per cell (>= 14/20) and the
   `never-grasped` count — a probe too fast to see a slide would move a failure
   *later* (a `cnp` instead of a `never-grasped`), which the ledger would show.
3. **The force servo's squeeze window** is `FRUIT_DYNAMIC_TAKEOFF_SQUEEZE_S=0.10`
   = 12 ticks and lives **inside** the probe: 24 ticks keeps 12 squeeze + 12
   lift, so the servo's convergence window is unchanged. P7's pinch floor is the
   check that this held.
4. **No reference is re-recorded by a non-flip**: the scripted gate never imports
   `SortingRLEnv`/`_dynamic_profile`, so `accept.sh`'s `fingerprint: matches` is
   an *import guard* on this change (stated as such — P38-M4's near-tautology).
5. **One claim per run** (`scripts/154_claim_run.sh`), wall from `logs/p80/stamp.py`.

## 6. Decision rule

* **ADOPT** iff **P1a ∧ P1b ∧ P2(clean) ∧ P3 ∧ P4 ∧ P5 ∧ P6 ∧ P7 ∧ P8 (both
  halves) ∧ P9**.
* **CONSIDERED TRADE** iff every clause above passes **except** P2, which must
  read *flat at both seeds and rising at neither*; the report then names the
  block delta, the interval and `placed/min wall`, and shipping needs the owner.
  (P87's shape: the block exact, one motion leg over budget → shipped with the
  miss documented.)
* **NOT ADOPTED** for anything else, and `PROBE_TWO_LINE_DEFAULT` stays `False`
  so the shipped tree is inert. The measured arm stays reproducible as
  `FRUIT_DYNAMIC_PROBE_TICKS=24`.
* **No clause may be re-read after the fact**: the four seeds/cells are one
  battery and the verdict is per §6, not per convenient subset.

## 7. Battery

`logs/p91/run_p91.sh`, `ATTEMPTS=20`, the shipped scenario, the shipped
instrumentation (`HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1`, identical on both arms):

| cell | seed | env | is |
| --- | --- | --- | --- |
| `C5` | 5 | `FRUIT_DYNAMIC_PROBE_TICKS=60` | the shipped 60-tick probe (explicit) |
| `T5` | 5 | unset | the cell (24), `PROBE_TWO_LINE_DEFAULT` on in the battery form |
| `C6` | 6 | `FRUIT_DYNAMIC_PROBE_TICKS=60` | the same control, second seed |
| `T6` | 6 | unset | the cell, second seed |
| `N5` | 5 | unset, **constant reverted to False** | must replay `logs/p89/T5.log` (P8's second half) |

then `FRUIT_BIARM=0 scripts/accept.sh` (P8's first half), the final shipped
acceptance, and `scripts/selfcheck.sh`.

## 8. Falsifiers (registered now, so a surprise is reported rather than smoothed)

* **F1** — the block does not move by −0.30 s: either the probe is not the 1:1
  lever §4 claims (then the audit's cross-check is wrong and must be retracted),
  or the site is not the one that runs (then the resolver is not wired).
* **F2** — the block moves and the **class worsens** (`never-grasped` up, or the
  loaded-slide legs up, or the pinch below 9.0 N): the ramp's gentleness was
  load-bearing after all, and the "3.7x slower than the lift beside it" argument
  is wrong. Report it as a *grip-class* finding, not a speed one.
* **F3** — the catch window moves (residual/`end=`/grasp rate): the re-timing is
  implicated and the cell's rate claim is void.
* **F4** — the interval rises at either seed while the block falls: the fourth
  register of the acquisition re-timing absorbing a block delta, and the reason a
  0.30 s block change is not deliverable on this cell.
