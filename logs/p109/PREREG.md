# P109 pre-registration - can the descent margin be spent?

Written 2026-11-03, **before any cell of this phase was run**. Its md5 is pinned
in `logs/p109/PREREG.md5` at that same moment; `PREREG.md` is not edited after a
cell is read (a correction goes into `RESULTS.md` as a deviation, the P75/P76
convention).

The owner's item is P108's ①: `FRUIT_DYNAMIC_DESCEND_MARGIN` **0.15 -> 0**.
P108 priced the along-belt arrival as the binding window (payload **83 mm**
upstream at the descent's start, 83-89 % along-belt, the pads entering the
payload's band **14.5 mm** in with the fruit still **55.8 mm** upstream) and
named "18 mm of the 83 is the descend margin alone" as the one cheap actuator on
that term. This phase measures whether removing it is worth anything, and - the
guard that comes first - whether **the catch itself survives**.

## 0. What the knob is, read off the code (two sites, no scope)

`tasks.py:9198` and `tasks.py:12900`, both
`float(os.environ.get("FRUIT_DYNAMIC_DESCEND_MARGIN", "0.15"))`:

1. `_dynamic_pick_lead()` = `min(speed*(overhead + t_desc + margin) + lead_margin, 0.80)`
   - the **handover point**: how far upstream of the station the moving catch
   hands over. `margin` 0.15 -> 0 moves it **18 mm** closer at 0.12 m/s.
2. the hover wait's break condition, `deadline = speed*(t_desc + margin)`:
   the descent starts when the fruit is **`deadline`** upstream of the aim.
   0.15 -> 0 makes it start **18 mm later**.

and, by construction, it also moves the **selector floor**:
`_dynamic_select_floor() = _dynamic_pick_lead() + speed*select_s + select_margin`
(`tasks.py:9119`), so the floor falls by the same 18 mm. That is a **branch
risk** (a different fruit can become eligible), and it is registered as such in
§3 E0 - it is the reason a count difference is not a lever difference here.

**Scope.** The knob is **not** scoped to the single arm. Both sites are read on
every dynamic-catch path, so a flip would move:
* the scripted **single arm** (measured here),
* the **two-line** session's catch (`tasks.py:12900` is the same wait loop; the
  two-line's catch point is `station + _two_line_catch_lead()`, but `deadline`
  is measured against `grip[1]`, so the 18 mm applies there too) - **not
  measured here**,
* the **direct/policy** handover when `FRUIT_DYNAMIC_PICK=1` (opt-in; the
  shipped canary runs the indexed primitive, so `60_eval_policy.py` has no path
  to it).

So a shipped flip owes **both** motion references, the acceptance re-base and
every store. Nothing ships in this phase (§5).

## 1. The mechanism, and the endpoint the code cannot give

`[task] dynamic descent:` prints `fruit dy`, and P108 read it as "the arrival
offset". **It is algebraically invariant to this knob**, and the derivation is
in the code: the row prints `dy_now = fruit_now[1] - intercept_y` with
`intercept_y = clip(fruit_now[1] - speed*t_desc, catch_y +- 0.03)`. In the
unclipped regime (`|shift| <= 30 mm`, every attempt of the P108 corpus reads
+17.1..+18.0 mm)

    fruit dy  ==  speed * t_desc

with **no margin term at all** - both `fruit_now` and `intercept_y` carry it and
cancel. So `fruit dy` cannot fall, and a phase that registered it as its only
mechanism endpoint would report a null that means nothing.

**The quantity the margin actually sets** is the descent-start gap *relative to
the aim* (the aim is the station, `_dynamic_aim` returns `station_y`, verified
`tasks.py:9542-9580`):

    g0  =  fruit_y - grip_y  at the descent's start
        =  fruit dy + shift                       (the row's own two prints; measured)
        =  deadline - (0..1 tick)                 (the command it breaks on, quantised
                                                   by the 1 mm/tick break test)

with `deadline = speed*(t_desc + margin)`, so the command carries the 18 mm
exactly and `g0` carries it to the tick quantum.

M0 predicts `g0` = 100.2-104.0 mm, M0.5 91.5-95.5, M1 82.8-86.0 - the 18 mm step
is the whole phase. Because the descent is a **static, open-loop profiled leg at
a fixed target** (the station) and the belt speed is measured at 1.00x
(`[task] intercept handover ... ratio 1.00x`), the whole descent window shifts by
the same 18 mm: the band-entry offset P108 measured falls 55.8 -> ~37.8 mm
**by arithmetic**, and the fruit's position relative to the aim **at the descent's
end** goes from `g0 - speed*descent_ticks`

    M0   100.8 - 0.12*88  =  +12.8 mm   (fruit already 13 mm past the aim)
    M1    82.8 - 0.12*88  =   -5.2 mm   (fruit 5 mm short of the aim)
    M0.5  91.8 - 0.12*88  =   +3.8 mm

- i.e. the margin is a **cushion against the descent over-running its own
  duration estimate** (the leg takes 88-91 ticks against the 0.68-0.69 s the
  estimate prices: a systematic +0.04..0.06 s = 5-7 mm of unmodelled fruit
  travel). **`g0` is registered as the mechanism endpoint**; the end-of-descent
  arrival error is a **derived** column (belt speed x the leg's own `steps=`),
  labelled derived, never measured.

## 2. Arms, cells, instrumentation

| arm | env | margin |
|---|---|---|
| **M0** | *(unset)* | 0.15 (shipped) |
| **M0.5** | `FRUIT_DYNAMIC_DESCEND_MARGIN=0.075` | 0.075 (secondary: the dose axis) |
| **M1** | `FRUIT_DYNAMIC_DESCEND_MARGIN=0` | 0 |

**Cells**: the **scripted single arm** (`FRUIT_BIARM=0`), `ATTEMPTS=20`, seeds
**5, 6** (the two the record reuses) **and 101, 202** (P93's fresh-seed rule: two
seeds reuse the tree's two control branches and over-state a gain), one claim
each, three arms x four seeds = **12 cells**. Every cell carries the *same*
instrumentation - `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_PLACE_TRACE=1` - so the arms are compared inside one instrumented batch.

**Controls.** `logs/p108/S_s5.log` / `S_s6.log` are the shipped hand at the
shipped margin on this tree (P108 changed no `src/`), but they carry **no**
`FRUIT_CYCLE_REPORT`, so they are not byte-comparable to this phase's cells as
they stand. They are used the way P95's rule requires: **M0 at seeds 5/6 is
re-run in this batch**, and the re-run is compared line for line with the P108
record **with the phase's `[cycle]` rows dropped**. That single comparison
proves three things at once - the tree is inert since P108, the P108 control is
admissible, and `FRUIT_CYCLE_REPORT` is run-neutral. If it does **not** replay,
the divergence is reported and M0 is the control of record (the same-batch rule),
and the P108 record is downgraded to "a different branch".

## 3. Endpoints, in this order

**E0 - the branch (reported first, never gated).** The selected sequence per
attempt (`[task] target <species> (grade ...)`, `fruit_x`, `fruit_y` at the
handover) against M0's. The selector floor moves 18 mm by construction, so a
moved sequence is expected on some seeds; when it moves, the count endpoints
(E4) are a **branch draw** and the class endpoints (E3) carry the phase.

**E1 - the arrival offset (the mechanism).**
* **E1a (`fruit dy`, p50/p90)** - reported, and **predicted to be invariant**
  (§1: `= speed*t_desc`). If it moves by more than ~2 mm between arms, §1's
  algebra is wrong and that is a result, not noise.
* **E1b (registered mechanism) `g0 = deadline = fruit dy + shift`**, p50/p90 per
  seed; the registered win clause is on this number.

**E2 - the aim quality.** The descent's `[motion] approach ... end=` (mm,
p50/p90) - the TCP shortfall against the commanded aim, the standing P32 defect,
**not re-tuned**; and the `[task] dynamic catch-up: residual` (p50, and the
count above its 6 mm tolerance, which is P47/P92's no-grasp signature), plus the
derived end-of-descent arrival error (§1).

**E3 - the guard: the catch succeeds.** Per seed: the **no-grasp class**
(`[run] attempt ... grasped=False`), the **never-held** subset (`[carry] ...
fmax=0.00N`, the pads closing on air), and the residual-above-tolerance count.

**E4 - the delivered count.** `placed=True` per seed, and pooled; `[stats]`
success rate.

**E5 - the landing.** `place trace ... on_belt=True` for **every payload present
at the release** (`release_bottom >= 0`; the `-184 mm` rows are the upstream-lost
class, reported separately, P86's rule).

**E6 - the budgets, not re-tuned.** Per cell: the descent `|v|max` against 105's
per-leg budget (`scripts/105_motion_regression.py <log>
--min-success-rate 0`), the lurch, and the carry cone (reported, not gated on
this line). AGENTS §2: a budget is never moved to admit a configuration.

## 4. The decision rule

**A win (-> a candidate, the owner decides, nothing ships here) needs all three,
in this order:**

1. **E1b falls**: `g0` p50 falls by **>= 12 mm** (at least 2/3 of the 18 mm
   predicted) at **every** seed, M1 vs M0;
2. **E3 does not rise**: the no-grasp class is **not higher than M0 at any
   seed** (M1 <= M0 per seed, and pooled);
3. **E4 holds**: `placed` does **not fall by more than one per seed**, and the
   pooled count does not fall.

**Anything else is a report, not a lever.** A degradation at M1 with M0.5 clean
is reported as "half the margin is free" (still no default change). A rise in
the no-grasp class at M1 means the margin is **load-bearing**, the remaining
levers on that term are P108's precondition (aperture) and a **centring guide**
(option 1), and the lane stops.

**The acceptance is a gate, not a rate claim** (§5): if M1's acceptance reads
below the two-line 0.60 floor or leaves a descent over budget, M1 is not a
candidate whatever the cells say.

## 5. The acceptance A/B (the catch's own gate)

`scripts/accept.sh`, ten attempts, twice, in this batch:

* **unset** - the shipped 0.15. Must read **8/10 + `fingerprint: matches`
  `30fb99f8`** and replay `logs/p108/accept_noharm.log` (this tree's branch).
* **M1 armed** (`FRUIT_DYNAMIC_DESCEND_MARGIN=0`) - its own reading. The
  fingerprint **DIFFERS by construction** (the knob moves every attempt's
  arrival), so the arm is gated on the **rate** (`190`'s 0.60 floor) and the
  **budgets**, and that is stated in the report rather than read as a break.

`scripts/accept.sh`'s shipped session is the **two-line** (P85), so this A/B is
the one place the phase measures the two-line's catch under the knob (as a
rate, 10 attempts, one draw). **A shipped flip would owe**: `configs/
motion_reference.json` and `configs/motion_reference_twoline.json` re-recorded
from same-batch 10-attempt runs, the acceptance re-based, and every store
re-baselined (the knob moves every dynamic catch on every path, §0). **No
`configs/` file is touched in this phase.**

## 6. Deviations, if any

Recorded in `RESULTS.md` against this file, with the reason and the time - the
P75/P76/P78 convention (a deviation pinned *before* the runs it governs is an
amendment and gets its own md5; anything after is a deviation).
