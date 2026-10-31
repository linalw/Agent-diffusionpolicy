# P81 PREREG — separate the two-line's scheduler from its supply package

Registered 2026-11-01, **before any run**, on the P80-final tree (HEAD `4a25b3d`,
clean worktree; the only diff from P80's measured tree `0de4d35` is `logs/p80/`,
`AGENTS.md` and `WORKLOG.md` - the code md5s match P80's `header.txt` exactly:
`tasks.py` `e8dfa6d8`, `bimanual.py` `980923a6`, `assets.py` `540406fa`,
`conveyor.py` `fb2c58c6`, `scene.py` `07d6fdad`, `rl_env.py` `7d26eb5b`,
`fruits.py` `c7461d41`, `control.py` `9384ff4f`,
`configs/motion_reference.json` `8952c320`,
`configs/motion_reference_twoline.json` `eb697f23`).

Owner's cell. **Measurement only: nothing adopted, no default changed, no commit,
`configs/` untouched.** The phase answers one question P80 left open and spends
two 20-attempt runs on it.

## 0. The question, and what P80 already fixed

`logs/p80/RESULTS.md` measured the two-line's first run on the shipped tree:
**16/20, 9.70 s/attempt, 5.57 window / 4.96 batch placed/min (2.48x / 2.38x)**
against the shipped single arm's **12/19, 15.10 s/attempt, 2.25 / 2.08**, and
decomposed the batch ratio as **2.38x = 1.88x clock x 1.27x count**:

* the **clock** is `batch sim span / executed attempt` - `18.20 / 9.67 = 1.88x`
  (`S20` / `T20`) and `18.06 / 9.66 = 1.87x` (`S6` / `T6`). It is not the
  `s/attempt` ratio (15.10 / 9.70 = 1.56): the two-line's *attempt* is the single
  arm's (15.0-15.6 s); it **overlaps** two attempts and so spends fewer idle +
  attempt seconds per pick.
* the **count** is the two-line's own **supply package** - the W3 dense-sheet
  schedule (`wave=on size=5 gap=0.10-0.16 sep=0.09-0.12 grades=A:0.375,B:0.375,
  C:0.25`) plus its pure grade routing - and the left arm's 1/7 -> 9/10. It is
  **not stable**: pooled over the two seeds the two lines place the same amount
  (26/40 vs 25/38), so the count factor swings 1.27x -> 0.73x.

**What P80 §8 did not spend, and this phase does:** is the **1.88x clock** the
scheduler's own property (any supply), or does it need the package too? The
record's prior points one way: the v9-era bimanual on the shipped scattered
supply was **structurally starved** - 74 % of its station slots reported no
eligible fruit (AGENTS §2's supply paragraph) - which is exactly the scenario
this cell runs on today's tree.

**The held-fixed variable, stated up front.** The cell disables the **supply
schedule and mix** (`FRUIT_SUPPLY_WAVE=0`, hence the shipped 50/30/20), not the
**routing**: pure grade routing (left = A, right = B, C recycled) is the V2
scheduler's station policy and stays on. So a "package-required" verdict below is
a verdict about the **W3 dense-sheet supply + balanced mix** at fixed routing; a
"routing-required" question is a different cell and is not claimed here.

**The predicted direction (recorded, not assumed).** With the wave off, the mean
along-gap rises 0.125 -> 0.225 m at the same belt speed (a fruit every 1.04 ->
1.875 s) and the grade mix goes 6/6/4 -> 8/5/3 over the 16-fruit pool, so B
arrivals at the right station fall **2.25x** (3/m -> 1.33/m) and A arrivals at
the left **1.35x** (3/m -> 2.22/m). Both arms should wait longer, the right more;
if the idle grows enough to stop the attempts overlapping, the clock ratio falls.
**D1 below is the reading that would falsify this prior.**

## 1. Arms

Every run: `HEADLESS=1 ATTEMPTS=20`, one `scripts/154_claim_run.sh` claim (one
simulator), `RUN_LIMIT=2400`, the same instrumentation set on both arms:
`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1` (the P80/P44 convention, proven
run-neutral on these scenarios). Wall is stamped per line through a `tee` with
`logs/p81/stamp.py` (**a byte copy of `logs/p80/stamp.py`**, md5
`fae805cd...`), so the plain log stays canonical and the wall column is measured.

| arm | env on top of the set above | what it is |
| --- | --- | --- |
| **Tp5** | `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_WAVE=0`, `SEED=5` | the two-line **scheduler + routing** on the **single arm's shipped scattered supply** |
| **Tp6** | the same, `SEED=6` | the second seed (P80's pair convention; the count is not a direction at one seed) |

**Controls are read, not re-run** (the task's own instruction, and P80's records
are on the identical tree md5s above):

* `logs/p80/S20.log` / `S6.log` - the shipped single arm at seeds 5 / 6;
* `logs/p80/T20.log` / `T6.log` - the two-line **with** its package at seeds
  5 / 6 (the package-on control for the same scheduler).

**No `FRUIT_SUPPLY_GRADES` is set**, deliberately: the 50/30/20 must come from
the shipped default, not from a hand-typed mix. There is no A:B:C file in the
tree - the balanced mix is code (`fruits.SUPPLY_GRADES_BALANCED`, selected by
`balanced = (wave or patch or bed) and FRUIT_BIARM_TWOLINE == "1"`), and with
`wave=0` (and no patch/bed) that predicate is **False**, so
`fruits.SUPPLY_GRADES = A:0.5,B:0.3,C:0.2` is used. The runtime proof is the
`[supply]` banner, which must read:

```
[fruit] [supply] scatter pool=16 seed=<n> ... wave=off grades=A:0.5,B:0.3,C:0.2 ...
```

and `A:0.375` must appear **nowhere** in the log. If it does, the arm is void
(F1).

**Motion gate.** `scripts/190_twoline_gate.sh` needs a reference of the **same
attempt count**; P80's `logs/p80/motion_reference_twoline_p80_20.json` is the
20-attempt file, but it was recorded on the **package-on** supply. Tp5/Tp6 are a
different scenario by construction (the supply schedule changes the fruit
sequence, hence the per-descent `(samples, |v|max)` list), so the fingerprint
comparison is **expected to DIFFER and is recorded as such, not forced**; the
**motion budgets** (descent speed, single-tick lurch, reported carry cone) are
judged separately by `105` with no fingerprint and no rate floor. **No new
reference is written** - there is no second same-scenario arm to gate, and
writing a log's own fingerprint would be a tautology. `configs/` is never
touched.

## 2. Endpoints (the metric set is P80's, which is W6/P33's)

| # | endpoint | source |
| --- | --- | --- |
| **E0** | the package-off proof: the `[supply]` row, `wave=off grades=A:0.5,B:0.3,C:0.2`, no `A:0.375` anywhere | the log |
| **E1** | `s/attempt` (within-attempt clock) and the per-arm span | `[biarm] ... pipelined slots` |
| **E2** | inter-placement interval, per-arm and pooled: mean / p50 / p90 | `186` |
| **E3** | **placed/min on both denominators**: placement window (`60 / pooled interval mean`) and batch span (`60 * placed / (t_last_end - t_first_start)`) | `186` / `p80lib` |
| **E4** | **lock-on** (previous attempt end -> station acquired), with retry polls | `186` / `p80lib` |
| **E5** | **idle fraction** per arm (active span outside attempts) | `186` / `p80lib` |
| **E6** | `[cycle]` block decomposition | `186` |
| **E7** | the class split, the **starved polls** (`[biarm] <arm>: no eligible fruit`), the per-slot starvation and the steady-state split | `175` + `p80lib` |
| **E8** | **wall vs sim**: wall/pick, sim/pick, wall/sim from the per-line stamps | `logs/p81/*.stamps` |
| **E9** | the motion budgets | `105` (budgets only) + `190` (recorded) |
| **E10** | the **clock ratio**: `(batch_span / executed attempts)_S / (...)_Tp`, at each seed and pooled | `p80lib` |

**Definitions fixed here** (so the number cannot drift after the fact):

* a **placement** is the attempt's `t1` (186's convention); the **window** is
  `t_last_place - t_first_place`; the **batch span** is
  `t_last_end - t_first_start`; a rate without its denominator is a defect.
* the **clock ratio** is the P80 1.88 identity: batch sim span per **executed
  attempt**, `S / Tp`. It is **not** `s/attempt_S / s/attempt_Tp` (that ratio is
  1.56 on P80's pair and measures the attempt, not the overlap).
* a **starved poll** is one `[biarm] <arm>: no eligible fruit` line (the worker
  re-polls every ~0.5 s and parks); P80's package-on arm has **44** of them
  (left 25 + right 19) at seed 5 and **33** (16 + 17) at seed 6, with **zero lost
  slots**. So "starved polls > 0" is **already true on the control** and cannot
  discriminate by itself; it is reported literally and the discriminating form
  is pre-registered in D2 as **polls per executed attempt**.
* **wall** is the per-line stamp's `[run] attempt 0` (or the first station
  acquisition on a two-line run) -> `[fruit] DONE`; **sim** over the same
  interval is the batch span; the ratio is reported, never gated.

## 3. Read rules (binding)

* **R0 - no cross-arm counts as a rate.** A placed count is one draw of a
  deterministic branch; two arms in different attractors are different
  scenarios. The **clock/interval** endpoints are the claim; counts and class
  splits are **reported** with their mechanism.
* **R1 - both denominators and the wall column, always.** Window and batch
  placed/min are printed side by side; the wall rate comes from the stamps, not
  from an app clock.
* **R2 - >= 2 seeds for any throughput claim.** Tp5 and Tp6 are both spent; a
  one-seed read is labelled a sample.
* **R3 - Tp is a different scenario from T20/T6** (its supply is the single
  arm's). Its motion fingerprint is expected to differ; budget and rate are the
  comparable quantities, and the supply row is the scenario pin.
* **R4 - the starvation mechanism is read against the control, not against
  zero.** The two-line worker always polls: 44/33 starved polls on the
  package-on arm are its design, and only a **rise** is the supply's cost.

## 4. Decision rule (the one table this phase owes - fixed before any run)

Let `R_clk = (batch_span/attempts)_S / (batch_span/attempts)_Tp` at the same
seed, and let the single arm's window rate be `S_w` (2.246 at seed 5, 2.297 at
seed 6).

**D1 - the clock is the scheduler's own** iff **both** seeds satisfy all of:

1. `s/attempt(Tp) <= 11.0 s` (the two-line's band: T20/T6/T10 = 9.70/9.70/9.20);
2. pooled interval mean `<= 12.0 s` **or** `<=` the same-seed package-on
   control's value. *Why the second form:* the seed-6 control itself reads
   19.34 s (T6's count collapse), so the literal 12 s bar is unsatisfiable at
   seed 6 by any arm with that count; both numbers are printed. (Seed 5 control
   10.77 s.)
3. `R_clk` in **[1.75, 2.00]** - the measured band is 1.87-1.88; the window is
   that band with a +/-0.05 instrument allowance so a one-tick shift cannot flip
   the verdict;
4. window `placed/min(Tp) > S_w` at the same seed (the task's "stays above the
   single arm's").

**D2 - the package is required** iff D1 fails at either seed, **or** either
starvation clause fires at either seed:

* **S-poll**: starved polls per executed attempt `>= 1.25x` the same-seed
  package-on control's (control 2.20 at seed 5, 1.65 at seed 6; bars 2.75 /
  2.06);
* **S-idle**: either arm's idle fraction `>= 1.5x` the same-seed control's
  (control left/right 18 %/21 % at seed 5, 19 %/30 % at seed 6; bars 27 %/31.5 %
  and 28.5 %/45 %).

**Verdict.** D1 -> **scheduler-only**: the 1.88x clock is the scheduler's on any
supply, and P80's count half is the only thing the package buys. D2 -> **package
required**: name every firing clause and publish it as such. **Both answers are
publishable; the rule is not softened after the fact.** If D1 holds while S-poll
or S-idle fires, the verdict is still D2 and the report says the clock number
survived but the starvation mechanism did not - that is the mixed reading, not
a third verdict.

## 5. Falsifiers (what would void the phase)

* **F1** - the `[supply]` row does not read `wave=off grades=A:0.5,B:0.3,C:0.2`
  or `A:0.375` appears anywhere: the package was not disabled; the arm is void
  and no interpretation is offered.
* **F2** - a run wedges (renderer freeze) or exits non-zero: re-run that arm
  **once**; a second failure is recorded as a missing arm, never inferred.
* **F3** - Tp5/Tp6 differ in any env other than `SEED`: the pair is void.
* **F4** - the P80 control logs are missing or their tree md5s do not match the
  header above: no cross-arm claim is made (the records stand alone).
* **F5** - the 20-attempt reference `logs/p80/motion_reference_twoline_p80_20.json`
  is missing: the `190` record is skipped with that reason, and only the `105`
  budgets are quoted.

## 6. What is NOT run, and why

* No shipped default, no `configs/` write, no new motion reference, no commit.
* No supply knob beyond `FRUIT_SUPPLY_WAVE=0`; no patch/bed/density/grade env -
  the point is the **single arm's shipped** supply, not a tuned one.
* No speed union, no policy, no store, no checkpoint.
* No single-arm or package-on re-run: P80's S20/S6/T20/T6 are on the identical
  tree md5s and are the controls by the task's own registration.
* `scripts/accept.sh` is run **once at the end** as a branch/no-harm probe (the
  tree is unchanged; P80's G-S10 already matched `8952c320` with 346/346
  `[fruit]` lines byte-identical), then `scripts/selfcheck.sh`.
