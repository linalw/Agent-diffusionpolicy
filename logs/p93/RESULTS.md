# P93 RESULTS — the re-entry: both red flags are branch artifacts, the third seed refutes the count, the band does not ship

Registrations: `logs/p93/PREREG.md` (md5 `cc6d84da…`, pinned before any run).
Battery: `logs/p93/run_p93.sh` → `logs/p93/diag_driver2.log` (the diagnostics) and
`logs/p93/seed_driver.log` (the four seed cells). Diagnostics readout:
`logs/p93/diag.py` → `logs/p93/diag.txt`. Battery readout:
`logs/p93/p93_report.py` → `logs/p93/p93_report.txt`. Gates:
`logs/p93/gates.sh` → `logs/p93/{C101,T101,C202,T202}.budgets`.

**Verdict in one line: the two red flags are branch artifacts (both are present in
the same-seed control), but the third and fourth seeds refute P92's count - the
band's pooled gain is +7 of 80 (`58/80 -> 65/80`, p = 0.26), one fresh seed
*loses* a placement and gains a `cnp`, and the pre-registered rule therefore
returns NOT ADOPTED; `FRUIT_SUPPLY_X_MAX` stays 0.36 and nothing is
re-recorded.** The one shipped change is the **metadata-only** supply-provenance
block PREREG §6 required before any recollection.

## 0. Admissibility

* The two diagnostic cells reproduce the untraced P92 cells **on the numbers**:
  `D6C` reads leg 1 `|v|max 0.108 / end 10.6 mm` and `D6T` `0.222 / 58.9 mm`,
  i.e. exactly `logs/p92/C6.log` and `logs/p92/T6.log`, and both were run
  **twice** with identical results. So (i) the event is deterministic, (ii) the
  trace is run-neutral at attempt 0, and (iii) the mechanism read below is a
  read of the same branch P92 measured.
* The seed cells carry P92's instrumentation verbatim; the class split is
  `logs/p92/census.py`'s classifier, unchanged.
* Seeds 5 and 6 are P92's committed cells and replay their P91 records
  **1033/1033** and **970/970** (modulo one profile row's origin label, P87's
  own A1 convention). Seeds 101 and 202 are **fresh scenarios**: no record
  exists to replay, so each control is read as its own cell and the table says
  so rather than inventing a reference (P84's rule).

## 1. The diagnostics (PREREG §1)

Both red flags are on the **same attempt** - seed 6, attempt 0, the right arm's
first kiwi. `FRUIT_DYNAMIC_TRACE=1` writes one row per tick for
`descent`/`catchup`/`close`/`carry` (`logs/p93/p1/{D6C,D6T}/trace/`).

### 1a. T6's leg 1 is a **jam onset**, not a chase and not a free-space boundary strain

| read | `D6T` (treatment) | `D6C` (control, same seed) |
| --- | --- | --- |
| target | fixed, open-loop (`intercept=-0.0831`, 88 commanded samples) | fixed (`-0.0828`, 88 samples) |
| `|v|max` / `end=` | **0.222** / **58.9 mm** | 0.108 / 10.6 mm |
| `a_win5` | 4.44 | 1.31 |
| the payload's velocity **at the leg's start** | `(-0.113, -0.262, -0.013)` = **0.286 m/s (2.4x belt)** | `(-0.253, -0.125, +0.034)` = **0.284 m/s (2.4x belt)** |
| the payload's displacement **over the leg** | `dy -90.3 mm` (= 0.123 m/s = belt speed), `dz -0.9 mm` | `dy -63.3 mm`, `dz +2.0 mm` |
| the first tick **after** the leg | `F = 71.13 N`, `contacts = 2`, `sep = 0.097` | `F = 41.80 N`, `contacts = 1`, `sep = 0.095` |
| the catch-up's payload minimum `z` (belt top 1.195) | **0.0052 m** | **0.8182 m** |
| the catch-up's `max |vz|` / `max F` | 4.64 m/s / 323.7 N | 2.66 m/s / 211.4 N |
| the catch-up residual (the log row) | **1169.1 mm** | **480.6 mm** |

**A chase is excluded by construction.** The leg's target is computed before the
leg (`_reach_prepare_aim` caches it; `reach_anywhere` is off), the commanded
profile is the same 88 samples in both cells, and there is no moving target in
the leg to chase.

**The leg does not displace the payload.** Over its 733 ms the fruit moves
90 mm at **exactly the belt speed** (0.123 m/s) and ~0 mm in `z` - it rides
normally.

**What the leg does is arrive on it.** At the first tick after the leg the pads
read **71 N over 2 contacts** with the jaw span already closing
(97 -> 76 mm) around a 62 mm kiwi. From there the payload is driven **down
through the belt**: `z` 1.197 -> 0.032 with a peak `|vz|` of 4.6 m/s, i.e. it
leaves the line rather than being carried (`clr_min = -1172 mm @belt` on the
carry row is the same event seen later).

**The control carries the same event at the same attempt** (41.8 N at the leg's
end, `z` 1.202 -> 0.818, 480.6 mm residual). Both cells' payloads are *already*
at 2.4x belt speed when the leg starts - so the disturbance predates the leg, it
is present in both arms, and the leg is where the pads meet what is already
moving. **PREREG §1a's binary reading cannot be applied as written** (the
`descent` phase is traced **once**, at the leg's start - `tasks.py:11509` emits
the sample before the profiled descent, so there is no per-tick contact read
inside the leg); the two reads that do exist are the ones tabulated above, and
they say "contact made at the leg's end, displacement downstream of it".

**The amplitude is a per-instance draw, not the band's.** The delivered `x` at
that attempt is **0.2507 (T) against 0.2447 (C)** - the treatment's fruit sits
6 mm *further out*, i.e. a per-instance release offset, not the band's mapping
(which compresses `x` by 0.8125 and would move it *in*). And the pre-descent
disturbance (0.284 / 0.286 m/s, ~4.2-4.7 rad/s of spin) is unseparated: no trace
covers the wait/pre-pose window. The leading candidate is the **other arm's
pre-pose transit** through the presentation line - the record already measures
the inter-arm separation at 1.9-2.6 mm minimum with 4.7-8.6 % of samples under
30 mm (`logs/w7`, `logs/w3`) - and it is named as **open**, with its own
instrument.

**→ not a chase; a jam onset with a pre-existing upstream disturbance, carried by
the control too: not a systematic cost of the band (PREREG §1c).**

### 1b. The 419 N / 1313 mm leg is a **bookkeeping artifact with a physical consequence**

All three of PREREG §1b's clauses pass:

| clause | reading | verdict |
| --- | --- | --- |
| (i) `|offset|` is the payload-minus-TCP distance | **1313 mm**, against the hand's own tool scale of **70 mm** (`_pad_standoff` = `FRUIT_FINGER_LEN` 0.060 + `PAD_LIFT` 0.010) and **20-62 mm on every other leg of the batch**; at the catch-up's end the tip sits **1180 mm** from the payload (**1132 mm of it in `-z`**) | PASS |
| (ii) the commanded TCP is > 0.5 m from the measured pads | `centre=[0.1986,-0.518,1.2467]`, `jaw_target=[-0.2838,-1.0006,2.3689]` -> **1313 mm** | PASS |
| (iii) the pads are on the payload at the leg's start | `contacts@onset=1`, `sep@onset=46.6 mm` inside a `dia=61.6 mm` fruit, `force@onset=23.20 N` | PASS |

**The path, read in the code**: `_gripper_offset[side]` is set at the grasp
routine's start to `rot.T @ (spawner.position(sample) - tcp_position())`
(`tasks.py:11047`) - **the payload's position minus the TCP's**, in the tool
frame, which is a *tool* offset only while the pads are on the payload. It is
applied **only** in `_carry`'s **incoherent** branch
(`arm.tcp_target_for_jaw(centre - rot @ offset_tool)`, `tasks.py:5361-5366`),
and that branch - unlike the coherent branch (`:5331`) and the place loop
(`:6079`) - **does not consult `hand_is_jaw`**. So on this hand the artifact is
turned into a commanded jump: with `centre` at the pads and `offset` at
`payload - tcp`, `centre - rot@offset = tcp_stale + (centre - payload)`, i.e.
~1.3 m above the real TCP.

**So: not a payload event.** The payload was never carried; the pinch was a
46.6 mm span on a 61.6 mm fruit with the payload already 1.13 m below the pads.
The 419 N, the 1.545 m/s in-hand peak and the 2361 mm `clean_slip_max` are the
arm flying to that stale target. **A state-integrity defect with a physical
consequence**, and (see 1c) not a cost of the band: the control's own attempt 0
carries the same code path at a smaller amplitude (116 mm offset, `fmax 0.00 N`,
a 380-tick lift leg with `clr_min = -383 mm`).

### 1c. The §1c test, applied

> a red flag is a **systematic cost of the band** iff present in the treatment
> and **absent in the same-seed control**, *or* present in both but **monotone
> in the band across two seeds**.

Both flags are **present in the same-seed control** (§1a, §1b's last line), and
the monotonicity route needs two seeds carrying the event - seeds 5's attempt 0
has no event at all (`5.9 mm` in **both** `C5` and `T5`), so seed 6 is the only
seed that can supply it. **One seed cannot supply monotonicity → branch
artifact, per PREREG §1c.**

Two independent witnesses that this is the scenario's and not the band's:

1. the pre-descent disturbance is present in both arms at 2.4x belt speed;
2. the `x` that attempt 0 actually delivered is 6 mm **further out** in the
   treatment, which is the wrong direction for the band's own mapping.

**So the phase continues to the seeds.** (Had either returned "a systematic
cost", PREREG §1c would have stopped it here.)

## 2. The fresh seeds (PREREG §2)

| seed | arm | placed | `cnp` | never-held | chase | starved polls | diverted | s/attempt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | C | 16/20 | 2 | 2 | 5 | 45 | 1 | 9.50 |
| 5 | **T** | **18/20** | 2 | **0** | 2 | 36 | 0 | 9.50 |
| 6 | C | 12/20 | 7 | 1 | 8 | 37 | 1 | 9.10 |
| 6 | **T** | **18/20** | **1** | 1 | 4 | 20 | 0 | 9.30 |
| 101 | C | **15/20** | 5 | 0 | 6 | 25 | 0 | 9.20 |
| 101 | **T** | **14/20** | **6** | 0 | 5 | 23 | 1 | 9.50 |
| 202 | C | **15/20** | 3 | 2 | 6 | 27 | 1 | 9.00 |
| 202 | **T** | **15/20** | **4** | **1** | 5 | 51 | 0 | 9.70 |
| **pooled** | C | **58/80 (72.5 %)** | **17** | **5** | 25 | 134 | 3 | - |
| **pooled** | **T** | **65/80 (81.3 %)** | **13** | **2** | 16 | 130 | 1 | - |

**The fresh seeds are the phase's headline and they cut both ways.**

* **The class clause passes at every seed and pooled**: never-held
  `2->0`, `1->1`, `0->0`, `2->1`; pooled **5 -> 2**. The mechanism P92 named is
  real at a third and fourth seed in the sense that it never *rises*.
* **The count gain does not reproduce.** Seed 101 reads **15 -> 14**, seed 202
  **15 -> 15**; the pooled **+7 of 80** (72.5 % -> 81.3 %) is **entirely seed
  6's +6** and is not significant: two-sided Fisher **p = 0.2604**. Per seed:
  0.661 / **0.065** / 1.000 / 1.000.
* **The `cnp` class rises at both fresh seeds** (5 -> 6, 3 -> 4), pooled
  `17 -> 13` (**p = 0.544**): the pooled `cnp` falls only because seed 6's 7 -> 1
  does.
* **The controls at fresh seeds are far better than seed 6's**: 15/20 twice
  against 12/20. P92 measured the band against the *worst* of its two control
  branches; against the two fresh ones it is worth -1 and 0 placements.
* The pooled never-held class is **5 -> 2** with two-sided Fisher **p = 0.4426**
  - the class the lever targets is too rare at n = 80 to certify a rate either,
  exactly as P92's §4 said ("informative as a mechanism and not as a rate").

**The delivered side is flat to worse**: pooled interval `10.59 -> 10.13` (seed
5) and `11.08 -> 9.84` (seed 6) but `12.16 -> 13.28` (seed 101) and
`11.53 -> 12.51` (seed 202); window rate `5.66->5.92`, `5.41->6.10`,
`4.93->4.52`, `5.20->4.80` placed/min; `placed/min wall` `2.91->3.15`,
`2.37->3.35`, `2.69->2.57`, `2.90->2.72`. The wall is the harness (the arms'
per-tick cost is unchanged); the interval follows the count, not the band.

## 3. Guards (PREREG §4)

| guard | reading | verdict |
| --- | --- | --- |
| G1 `cnp` must not rise | seed 5 `2->2` PASS; seed 6 `7->1` PASS; **seed 101 `5->6` FAIL**; **seed 202 `3->4` FAIL** | **FAIL** |
| G2 the landing | **123/123** payload-present releases `on_belt=True` across all eight cells (16/18/12/18/15/14/15/15) | PASS |
| G3 the motion budgets | 160 descent legs, **4 over budget**: `C6` leg 12 `0.164/0.160` (+2.5 %, the standing P86/P87/P88 branch leg), `T6` leg 1 `0.222/0.161` (+38 %, §1a), **`C101` leg 9 `0.224/0.160` (+40 %, a CONTROL)**, `T202` leg 14 `0.183/0.161` (+14 %) | **FAIL** |
| G4 no new failure reason | the treatments' note keys stay inside the control set (`fruit did not follow the gripper`); no new key | PASS |
| G5 the control replay | seed 5 **1033/1033**, seed 6 **970/970** (modulo the origin label); seeds 101/202 are fresh scenarios, stated not invented | PASS |
| G6 attempts | **8/8** cells at 20 attempts, **no lost slot**; the `no eligible fruit` poll counts are 20-51 per cell (a wait, not a loss) and there are 4 diversions in 8 cells (a *pool slot* retired after two failures, P92's reading) | PASS |
| G7 the tree is inert with the knob unset | `scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)**; `scripts/accept.sh` **7/10, 9.4 s/attempt, `fingerprint: matches configs/motion_reference.json`, `190: PASS`**, and its **449 `[fruit]` lines are byte-identical (449/449)** to the last recorded acceptance of this branch, `logs/p91/accept_final.log` | PASS |
| G8 the supply audit | `python3 scripts/211_bed_audit.py` **ok (115 checks)** | PASS |

**G3 is the most informative failure in the phase, and its reading is
arm-symmetric.** The four over-budget legs sit **two in controls (`C6`, `C101`)
and two in treatments (`T6`, `T202`)**, at **2.5 % of 160 legs**, and they are
**uncorrelated with the catch-up**: `C101` leg 9 and `T202` leg 14 both run
clean catch-ups (every residual <= 6.0 mm), while `C5`'s two missed catch-ups
(251.0 and 87.6 mm) run descents that are **inside** budget. So the over-budget
descent is a **stochastic branch property of the scenario in either arm**, which
is precisely what AGENTS §2 means by "the ratio has no clean gap and the budget
cannot tell a boundary strain from a real push". The budget was **not** re-tuned.
`C101`'s leg 9 at +40 % is the phase's cleanest single read: **a control cell on
the shipped band produces the same excursion class the treatment was refused
for at seed 6.**

## 4. Verdict (PREREG §5's rule, applied)

The rule: adopt only if (1) the pooled never-held class falls and no seed's
treatment exceeds its control's; (2) no seed's placed count falls below its
control's and the pooled count does not fall; (3) G1-G8 pass; (4) §1 returns
"not a systematic cost".

* (1) **PASS**: pooled `5 -> 2`; per seed `2->0 / 1->1 / 0->0 / 2->1`.
* (2) **FAIL**: pooled `58 -> 65` passes, but **seed 101's placed count falls
  (15 -> 14)**.
* (3) **FAIL**: G1 at seeds 101 and 202; G3 at `T202` leg 14.
* (4) **PASS**: both flags are branch artifacts (§1c).

**→ NOT ADOPTED.** `FRUIT_SUPPLY_X_MAX` stays **0.36**, `src/fruit_sorting/fruits.py`
keeps `SUPPLY_X_MAX = 0.36`, `configs/` is untouched, **no motion reference was
re-recorded and none is owed** (nothing moved), and the measured arm reproduces
as `FRUIT_SUPPLY_X_MAX=0.33` (env only). **PREREG §6's adoption package is
therefore not executed either**: no reference archive, no acceptance/two-line
re-base, no re-baseline note, and **no direct/policy cell** - the interface would
inherit the band through the same `SupplyPlan.from_env` (`two_line=False`), and
measuring it would only price a move the rule has already refused. The frozen
decision ("the supply band's `x_max`") is recorded as **not taken**; the one
thing that did ship is the provenance that would have been its precondition
(§6).

**Why the rule was right to stop it, said plainly.** The band is not a
success-rate lever at four seeds. The two fresh controls read **15/20 twice**
against seed 6's 12/20, so P92's `28 -> 36` was measured against the worst of
the four control branches the tree has; against the two fresh ones the band is
worth **-1 and 0** placements, and it *adds* a `cnp` at both. Its one consistent
effect is on a class that occurs 5 times in 80 control attempts - real as a
mechanism, unmeasurable as a rate. **The count clause was deliberately stricter
than the project's own doctrine** ("a success-rate delta between attractors
measures the attractor", AGENTS §2) and it fires anyway; the doctrinal read
(class counts, per-leg motion, both intervals) says the same thing.

**What would be needed instead.** At an 8.75-point pooled difference the
two-sided 0.05 / 80 %-power sample is **364 attempts per arm** (5-6 times this
phase's), with the **never-held class** as the registered endpoint and the count
as a report. That is the honest power statement, and it is the named next spend
if the owner wants this lever certified rather than explained - not another
two-seed batch.

## 5. What this phase settles that is not about this lever

1. **The 419 N class is a code defect with a named fix and no behaviour change
   yet.** `_carry`'s incoherent branch applies `offset_tool` without consulting
   `hand_is_jaw`, while the coherent branch and the place loop both do. Fixing
   it is a one-line scope (`if hand_is_jaw: arm.tcp_target_for_jaw(centre)`)
   that would change no coherent-path stream - and it is **not** done here: it
   is a `src/` behaviour change on the shipped carry, and the record's rule is
   one variable per phase. It is registered as the next `src/` candidate with
   P92/P93's own A/B (the 419 N leg is reachable only from a lost payload, so
   the fix's evidence is that leg's population, not a rate).
2. **The first presentation at seed 6 is a standing scenario defect**, not this
   phase's: the attempt-0 jam (`480.6 mm` residual in every seed-6 record on the
   tree) is the *control's* never-held event and the source of the seed-6
   branch's `cnp` count. A first-attempt lever is a **scenario** lever with its
   own pre-registration.
3. **The motion-budget gate is arm-symmetric at this scenario** (2 control legs,
   2 treatment legs of 160) - so a future two-seed A/B that fails G3 on one
   treatment leg has measured the branch, not the change. **A single leg is not
   admissible evidence against a scenario change**; the guard needs either five
   seeds or the leg-level diagnostic §1a ran here.

## 6. What shipped: the supply provenance block (PREREG §6)

Metadata only, **no stream effect**: `scripts/accept.sh`'s **449 `[fruit]` lines
are byte-identical (449/449)** to `logs/p91/accept_final.log`, the last recorded
acceptance of the shipped branch before this phase (§3/G7).

* **`assets.supply_provenance(plan)`** - the resolved **band**
  (`x_min`/`x_max`), the **along draws** (`gap_min`/`gap_max`), the two **mixes**
  (`grades`, `classes`) and the **resolved schedule name**
  (`bed > patch > wave > scatter`, else `fixed`). Pure `SupplyPlan` arithmetic.
* **Both manifest writers** call it under the same key `supply.band`
  (`scripts/40_collect_demos.py` and `SortingRLEnv._supply_band_provenance`), so
  a collection store and a direct/rollout store name their band identically (the
  P41 `physics` / P72 `scene` rule). The env's copy is inside a `try/except`: a
  manifest never takes a run down.
* **Why it was needed**: the *collector's* shard manifest already carried
  `supply.x_min`/`x_max` and both mixes (`datasets/v12d_s02/manifest.json` reads
  `x_max: 0.36`), so a collection store was already distinguishable. The
  **direct env's** rollout manifest carried only its P58 profile block - no band,
  no mix - so a direct/rollout store under 0.20-0.33 and one under 0.20-0.36
  were **indistinguishable**. That was the gap, and it is closed.
* **Pinned** in the existing provenance leg: `scripts/239_p72_clr_edge_selftest.py`
  gained a section 6 (the builder's signature and arithmetic, all four branch
  orders, the `SupplyPlan` field set read from the dataclass's own AST, one call
  site per writer, the collector's shard keys).
* A manifest **without** `supply.band` predates P93; the collector's flat
  `x_min`/`x_max` are then the witness.
* **Exercised end to end without a `SimulationApp`** (`logs/p93/manifest_probe.py`
  under the Isaac python, the P72 probe's contract -> `manifest_probe.log`): the
  collector's own writer emits `supply.band.schedule = "wave"`, the two mixes,
  and **`x_max` 0.36 shipped / 0.33 under `FRUIT_SUPPLY_X_MAX=0.33`**, with the
  `scene` block byte-unchanged beside it. So the two stores the prerequisite was
  written for are now distinguishable from their own metadata.

## 7. Pins and files

`src/` change: `assets.py` (`supply_provenance`, +96), `rl_env.py`
(`_supply_band_provenance` + the manifest key, +30);
`scripts/40_collect_demos.py` (`_supply_band_provenance` + `supply.band`, +16);
`scripts/239_p72_clr_edge_selftest.py` (section 6). `tasks.py` **untouched**
(`7ba4bb58`, so `rl_env.TASKS_MD5` stands). `configs/motion_reference*.json`
untouched (`423896f7` / `423896f7` / `8952c320`). New under `logs/p93/`:
`PREREG.md` `cc6d84da`, `PREREG.md5`, `diag.py`, `diag.txt`, `p93_report.py`,
`p93_report.txt`, `run_p93.sh`, `gates.sh`, `header.txt`, the cells
`{D6C,D6T,C101,T101,C202,T202}.{log,stamps,driver}`, `{C101,T101,C202,T202}.budgets`,
`p1/D6C/`, `p1/D6T/` (the traces), `p1/D6C_first_pass*`, `p1/D6T_first_pass*`,
`accept_noharm.{log,driver}`, `manifest_probe.py`, `manifest_probe.log`,
`selfcheck.log`, `diag_driver{,2}.log`, `seed_driver.log`, `watch_d6c.log`.

## 8. Deviations, all recorded

* **D1** the two diagnostic cells' first pass wrote into the shared
  `logs/dynamic_trace/` directory and **overwrote each other**, so `D6C`'s
  attempt-0 trace was lost. Fixed inside the phase by giving each cell its own
  `FRUIT_DYNAMIC_TRACE_DIR`; both cells were then re-run and both reproduce the
  first pass **exactly** (`0.108/10.6`, `0.222/58.9`, `480.6`, `1169.1`), so the
  re-run is a determinism proof, not a second sample. The first-pass logs and
  D6T's first-pass trace are kept at `logs/p93/p1/*_first_pass*`.
  `FRUIT_DYNAMIC_TRACE_DIR` is a file-path env only - no stream effect.
* **D2** PREREG §1a's binary reading (a chase vs a boundary strain, decided by
  the descent's own per-tick rows) is **not applicable as written**: the
  `descent` phase is traced **once**, at the leg's start (`tasks.py:11509` emits
  the sample before the profiled descent). The phase reads the two states either
  side of the leg instead and says so; the verdict (a jam onset, present in both
  arms) does not depend on the missing per-tick read.
* **D3** 40 stale `logs/dynamic_trace_*.json` files from 2026-10-26 were moved
  to `/tmp/opencode/p93_stale_traces/` so they could not be mistaken for this
  phase's (`[]` payloads, 2 bytes each).
* **D4** `p93_report.py` prints the count clause's per-seed verdicts; its
  summary line reads `FAIL` for the pooled-vs-per-seed mix, and §4 above is the
  binding statement of which clause fails.
* **D5** the PREREG's §1c monotonicity route was written for "two seeds"; only
  seed 6 carries the event, so it is unreachable by construction and the
  presence-in-control route is what decides. That is stated rather than glossed.
