# P89 - the lift raise as a two-line-scoped default (pre-registration)

Frozen before the first P89 run. The md5 of this file is pinned in
`logs/p89/PREREG.md5`; `logs/p89/header.txt` pins the tree the battery ran on.
Nothing here is amended after looking at an outcome - a deviation, if one is
needed, is recorded as a numbered amendment in `RESULTS.md` with the time it was
written and no verdict changes on it unless the amendment says so **and** was
pinned before the run it governs.

Phase: **P89**, the third and last profile block of the shipped cell. **The
shipped cell is the two-line with P87's release trim** (`FRUIT_BIARM=1
FRUIT_BIARM_TWOLINE=1` by default, `FRUIT_SPEED_RELEASE` on inside a two-line
session; `logs/p87/RESULTS.md`, `docs/THROUGHPUT.md`). No commit is made by this
phase; a flip happens only if the gate below passes.

---

## 0. Why the lift, and what changes

The per-arm attempt span decomposes into three profile blocks. Shipped (P87's
`[cycle]` record): **place 3.14-3.19 s / release 1.70 s (was 2.35) / lift 1.65 s**.
P85's union re-pricing put the caps at **place -0.84 s, release -0.72 s, lift
-0.13 s**; P87 has shipped the release and P88 measured the place and did not
ship it. **The lift is therefore the last unspent block, and it is also a class
site**: `logs/p75/RESULTS.md` measured that **2 of 6 place-leg escapes fire at
the END of the lift** (the place leg then *starts* with one face at `0.00 N` and
the jaws at 85-98 mm), and the lift leg's own window is where the payload is
seated. So the phase answers two questions at once: **does the last block buy
anything, and does its clock touch the escape class?**

| | before P89 | after P89 (if the gate passes) |
| --- | --- | --- |
| `FRUIT_SPEED_LIFT` unset, **two-line session** | off (0.30 / 1.0) | **on (0.37 / 1.0)**, `origin=default` |
| unset, single arm / shared station / canary / direct / collector `single` | off | **off** (`origin=scope-off`) - unchanged |
| `=0` / `off` / `false` / `no` (explicit) | off | off, on **every** path including the two-line |
| `=0.37` (the S3-v value) | 0.37 / **1.9** | 0.37 / **1.0** - the measured arm, one knob |
| `1` / `on` / any other speed | 0.36 / 1.9 (S3) | **same** (the S3/S13 pair is not moved) |
| `FRUIT_SPEED_ALL=1` | 0.36 / 1.9 (S13) | **same**; an explicit `=0` still beats the union |
| `FRUIT_SPEED_LIFT_AMAX` | pins `a_max` | same |

One resolver (`tasks.lift_speed_resolution`), the same three consumers the other
two cells use: `speed_cell_defaults(self.two_line_enabled())` at `_carry_leg` (the
`grasp_lift` branch), the row
`[biarm] lift profile: FRUIT_SPEED_LIFT=0.37(default) scope=two-line v_max=0.37
a_max=1.0 (136 ticks at 0.21 m; shipped 162, saved 26)` printed only inside
`run_bimanual`, and the manifest's
`physics.lift={v_max,a_max,ticks,shipped_ticks,saved_ticks,reference_distance_m,
profile,origin,two_line,label}` written by both writers (`scene._lift_provenance`).
A manifest **without** the key predates P89.

**The cell is P44's S3-v, verbatim** (`logs/p44/P2_RESULTS.md` §9): `v_max` 0.30
-> **0.37** with the shipped **`a_max` 1.0**. The acceleration is **not** raised:
the phase-2 S3 pair (0.36 **and** 1.9) measured a `lift` block of 1.59 s against
S3-v's 1.57 s, so the acceleration bought **0.00 s** and only spent grip transient
(its `grasp_lift` worst cone 1.42x against S3-v's 1.19x). That is why the two are
separate resolutions here and why `FRUIT_SPEED_LIFT=0.37` means 0.37/1.0 while
`=1`/the union keep S3's measured 0.36/1.9.

## 1. The arithmetic, before any run

The `grasp_lift` leg is one `jerk_limited` profile. At the read site the chain is
`TrajectoryLimits.from_env` (j 25) -> the lift cap -> `limited_by_cone` keeps
`j = min(25, max(10*a, 1)) = 10`, `v = min(v_max, 2a)`, `a = min(1.0, 1.962) = 1.0`
(the vertical cone budget). `motion.jerk_limited` takes
`T = 1.02 * max(1.875 d/v, sqrt(5.774 d/a), (60 d/j)^(1/3))`, rounds up to whole
ticks and emits `steps + 1` samples, which is the tick count
`[motion] carry grasp_lift` prints.

* **The two regimes switch at d = 5.774 v²/(1.875² a)**: **0.148 m** shipped
  (0.30) and **0.225 m** raised (0.37). The record's legs are **0.05-0.22 m**
  (median 0.21), so most shipped legs are **speed-limited** and most raised ones
  are **acceleration-limited** - the saving is therefore *not* the 1.233x speed
  ratio, it is the ratio of the two binding terms.
* At the reference **d = 0.21 m**: **162 -> 136 ticks = -26 ticks = -0.217 s**
  (this is what `physics.lift` records, at the named distance).
* The block is the leg plus a **constant remainder**: `[cycle] lift=` is the
  `grasp_lift` `_carry_leg` call, and on the shipped two-line record
  `block - ticks/120` reads **0.412-0.422 s** (median 0.416, i.e. one tick of
  spread) on 40/40 legs of `logs/p88/{T5,T6}.log`.

Predicting **per attempt** (each control attempt's own `grasp_lift` distance
re-generated at 0.37/1.0, its own remainder kept - the cell touches nothing else),
from those two records:

| seed | control `lift` median | predicted median | delta | control mean | predicted mean | **predicted mean delta** |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 1.755 s | 1.547 s | **-0.204 s** | 1.680 s | 1.506 s | **-0.174 s** |
| 6 | 1.730 s | 1.523 s | **-0.200 s** | 1.739 s | 1.562 s | **-0.177 s** |

The prediction's own resolution is the printed centimetre: re-running it at the
**shipped** cap reproduces those legs' printed ticks to a **median of +0.0 / +0.5
ticks (max |4|)**, and the remainder is constant to one tick - so **P1's band is
±0.08 s on the mean**, which is P88's lesson applied (a block that depends on the
distance is **not** branch-free at the median; the mean and the per-leg read are).

## 2. The battery

`ATTEMPTS=20`, **seeds 5 and 6**, the shipped scenario, one claim per run
(`scripts/154_claim_run.sh`), wall from `logs/p80/stamp.py`:

| cell | env | what it is |
| --- | --- | --- |
| **C5** | `FRUIT_SPEED_LIFT=0`, seed 5 | the shipped lift cap (0.30), P87's clock |
| **T5** | unset, seed 5 | the scoped default (0.37 / 1.0) |
| **C6** | `FRUIT_SPEED_LIFT=0`, seed 6 | the shipped lift cap |
| **T6** | unset, seed 6 | the scoped default |

The release cell is **unset on all four cells** (its own two-line default) and the
place cell is unset (its default is off), so the comparison is the lift alone.
Instrumentation is identical on both arms - `FRUIT_MOTION_REPORT=1
FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1` - so a class or
landing difference cannot be an instrument difference (AGENTS §3b). No `src/`,
`configs/`, `datasets/` or checkpoint write happens inside a cell.

## 3. Endpoints, in the order the project requires

* **P1 the `[cycle] lift=` block (the mechanism).**
  * **P1a** the block **mean** falls in **every** arm-seed cell and lies within
    **±0.08 s** of the prediction of §1 for that seed (the median is reported
    beside it, never gated - the legs are 0.05-0.22 m and a median across them is
    mix-sensitive).
  * **P1b** the cell **materialised on every treatment lift leg**, read leg-by-leg
    (so the short legs cannot fail a cap clause they never reached):
    **(i)** the leg's tick count is within **3 ticks (median)** of the profile
    re-generated at 0.37/1.0 from that leg's own printed distance;
    **(ii)** its `|v|cmd` matches that profile's own peak `1.875 d / ((ticks-1)/120)`
    to **<= 0.02 m/s on every leg** (the leg-relative form of P88's peak check:
    the peak is `min(v_max, 1.875 d/T)`, so a 0.05 m leg peaks at 0.14 and a
    0.22 m one at 0.36 - a fixed number would be wrong for one of them);
    **(iii)** the remainder `block - ticks/120` stays inside the control's own
    **0.41-0.43 s** on every treatment leg.
    A cell that resolved but did not reach the cap fails here even if the block
    moved.

  *Reading P1a when the leg mix moves*: the prediction of §1 is built from the
  **control's** legs, and the treatment draws its own (the lift distance is
  0.05-0.50 m). If the mean misses the ±0.08 s band **while P1b is exact and the
  treatment's own `block = ticks/120 + remainder` holds on every leg**, the miss
  is the **leg mix**, not the cell - that is P88's P1a finding, registered here in
  advance; the clause is still judged **on its letter**.
* **P2 the interval.** The **pooled** inter-placement interval does not rise at
  **either** seed; the per-arm interval is reported for all four arm-seed cells
  (a 20-attempt two-line arm's per-arm count is a branch draw, so only the pooled
  direction is gated). The **placement count and the window span travel with
  it** - the interval *is* `window/(n-1)`, so a count change is quoted beside it
  and never as the lever's (P88's read rule).
* **P3 the landing.** Every payload present at the release
  (`release_bottom >= 0` in `FRUIT_PLACE_TRACE`) lands `on_belt`, in **both**
  arms, at both seeds. The upstream-lost rows (`release_bottom < 0`) are the
  known lost-payload class and are reported separately, never counted as a
  landing failure.
* **P4 the loaded-slide class - the phase's real guard, and the phase has a
  prediction.** Read from the `[fruit] [carry]` rows, per arm and per leg class,
  on **both** arms: `escaped` = `clean_slip_max > 100 mm` **with a pinch**
  (`fmax > 0`; P74's mechanism count - the `> 800 mm` threshold is not
  speed-invariant and is reported, never gated), `never-held` = `fmax == 0`, and
  the W8-B guard `force_min == 0`.
  * **The question, named before the runs**: P44's S3-v **dropped** the
    `force_min == 0` legs (**5 vs the control's 7**) and added no failure row on
    the single arm, while P75 measured that the lift's **end** is a firing site
    for place-leg escapes (2 of 6). So the two registered readings are **"the
    class improves" (P44)** and **"the class moves" (P75)** - and the phase
    separates them by reading the escape **onset leg**, not only the totals.
  * **P4a** no **new failure-reason key** in either treatment cell.
  * **P4b** the **lift-leg** escape count (pooled over both seeds) does not rise
    over the control's, and the **place-leg** escapes stay **<= 3** of ~32
    (control: 1 pooled in P88's cells).
  * **P4c** the all-leg escaped count, pooled, does not rise by **>= 5** over the
    control's.
  * **A class regression - any of P4a/P4b/P4c - ends the phase regardless of the
    interval.**
* **P5 throughput (reported, never gated).** `placed/min` on **both**
  denominators (placement window and batch span) and **`placed/min wall`**; the
  placement count itself. One draw of a rendered-frame loop: a count difference
  is a branch draw, not the lever's (P80's rule).
* **P6 the descent budgets, per leg.** Every descent leg is judged by `105`'s
  own per-leg budget (the shipped profile's 1.10x peak) and lurch bound; the
  budget is **not** re-tuned. Tiering, P87's precedent: **0 legs over** at both
  seeds = clean; **exactly one** leg over at one seed = **CONSIDERED TRADE**
  (documented as that branch's property, ship); **> 1 leg, or a leg at both
  seeds** = **FAIL** (a pattern, i.e. a cost). The lift is not a descent, so a
  budget excursion here can only arrive through the re-timed attempt boundary.

## 4. Admissibility

* **G0 - the tree is unchanged, and the control is the shipped cell.** `C5` must
  be **byte-identical to `logs/p88/T5.log`** and `C6` to `logs/p88/T6.log` on the
  `[fruit]` stream with the diag rows and the **three** profile rows dropped
  (`logs/p89/p89_report.py --same`). This proves the resolver is inert when off,
  so any treatment difference is the cell's.
* **G1 - motion.** The 20-attempt two-line references in `logs/` are **pre-P87
  clock** records, so no post-P87 run of this scenario can match them (P87
  recorded exactly that for its own cells; P88 registered it as its A2). The arms
  are therefore read the same way: `scripts/190_twoline_gate.sh` on every cell
  against its same-seed 20-attempt reference is **recorded** (a treatment is
  DIFFERS by construction), and the substantive motion check is **P6's per-leg
  budget** via `105 --min-success-rate 0.0`.
* **G2 - the scope's inertness** (the P87/P88 template, run on the **final**
  tree, i.e. after the verdict's flip):
  * **(a)** `FRUIT_BIARM=0 scripts/accept.sh` (ten attempts) must be **raw
    `[fruit]` 346/346 byte-identical** to `logs/p71/accept_rails_none.log` with
    `fingerprint: matches configs/motion_reference_single.json` - the single arm
    has no session, so the lift cell is `scope-off` and **no profile row prints**.
  * **(b)** the shared-station pair (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0`, 4
    attempts, unset vs `FRUIT_SPEED_LIFT=0`) must be identical with `--same` and
    `--profile`: **the row's `origin` label may differ** (`0.30(scope-off)` vs
    `0.30(explicit)`), **the clock must not** (v_max 0.30, a_max 1.0, 162 ticks).
  * **(c)** a fresh **unset** 20-attempt run (N5) on the final tree must replay
    `C5` - that is what makes "the shipped default is the shipped clock" a fact
    after the flip.

## 5. Verdict rule

The gate **passes** iff, at **both** seeds: **P1a**, **P2**, **P3**, **P4a/b/c**
all pass, **P1b** passes, and **P6** is clean or a single-leg CONSIDERED TRADE
(never a pattern). P5 is reported and is **not** a clause.

* **If it passes**: ship the scoped default (it is the code as written - the
  unset resolution), re-record `configs/motion_reference.json` and
  `configs/motion_reference_twoline.json` from the same-batch shipped-scenario
  runs, archive both pre-P89 files under `logs/p89/`, leave
  `configs/motion_reference_single.json` untouched, and update `AGENTS.md`
  (§1 supersede note + a P89 paragraph), `docs/THROUGHPUT.md` and `WORKLOG.md`
  with the re-baseline.
* **If it fails**: say which clause, do not flip, and publish the measurement.
  A class regression (P4) ends the phase; a budget pattern (P6) ends it; a
  mechanism miss (P1) means the cell did not do what it is priced to do.

## 6. The honest risk, stated up front

**A null or a marginal read is the likely and acceptable answer.** P85's union
re-pricing put the lift's share of its -1.00 s at **-0.13 s**, this phase's own
arithmetic says **-0.17 s** of a 15 s cycle (a ~1.1 % span saving), and the
delivered interval on this cell has three terms (`attempts/placement`, the span,
the idle) of which the lift touches one. **The record is the deliverable**: with
the release shipped (P87), the place measured negative (P88) and the lift
measured here, the profile-block table is **closed** - every block priced, the
mechanism named, and the read rules that bound the next claim in
`docs/THROUGHPUT.md`.

The class side is the part that could still surprise: P44 measured S3-v as the
**only** single cell that drew no grip row and dropped the `force_min == 0` legs,
while P75 measured the lift's end as a place-escape site. If the class moves
rather than improves, that is a finding about the site (and P4 ends the phase).

## 7. Not measured / out of scope

A third seed; a two-line **collection** shard under the cell (the collector
inherits it and would record `physics.lift`); the hybrid canary (it never builds
a `CoopSession`, so the cell has no path there); a saturated machine; the
`grasp_lift` leg's own `|a|max`/cone (P44 §9 measured the acceleration raise as
0.00 s and this cell does not raise it); a **global** `FRUIT_SPEED_LIFT` default
(measured only as the S3/S13 pair on the single arm, P44).
