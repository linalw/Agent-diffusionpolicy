# P82 METHOD — where the two-line's per-tick wall goes, and whether any of it is removable

Status: **measurement phase**. Nothing adopted, no default changed, no `configs/`
change, no commit. Pins are the shipped P81 tree (`tasks.py` `e8dfa6d8`,
`bimanual.py` `980923a6`, refs `8952c320` / `eb697f23`).

## 0. The object, in one number

P80/P81 measured the cell's wall/sim ratio on this machine:

| arm | wall/sim | share of wall that is *not* the simulated second |
| --- | --- | --- |
| single arm (S20) | 1.38 | 28 % |
| two-line (T20) | 2.57 | 61 % |

and P80 discriminated the scheduler's own per-tick cost on the W6-B same-supply
pair (single 1.25x, two-line 2.32x). So the question is **where the two-line's
extra 1.1-1.2 wall/sim goes**, and whether any of it can be removed without
changing behaviour. P80/P81's throughput numbers are only interpretable once
this is known: `1.87x` of simulated clock is `1.87x` of wall *only if* the
harness cost is the single arm's.

## 1. What is already known about the code path (read, not guessed)

`bimanual.TickRelay` is the arbiter, `bimanual.MainBridge` the main-thread
queue, `bimanual.CoopSession` the patch. From the source, before any measurement:

* **Workers never step physics themselves.** `SimulationManager.step` is patched:
  a call from a registered attempt thread files a request and blocks
  (`TickRelay.request`), so each control tick of each arm is a cross-thread
  round trip.
* **One shared tick per round pair.** `TickRelay.schedule` executes
  `ticks = min(owed)` physics ticks when *every* live attempt has an
  outstanding request, then grants **one** run permit (round-robin via
  `_last_run`). With two arms in a 1-tick control loop that is: A requests →
  schedule (no tick owed yet, or one tick) → grant B; B requests → schedule
  (one shared tick) → grant A. **So ~2 arbiter rounds per shared physics tick,
  and each arm's control work runs alone in its own round.**
* **The main thread polls.** `CoopSession.run` drives `bridge.serve_while(alive)`
  whose body is `relay.schedule()` then `MainBridge.pump(0.005)` — a
  `queue.Queue.get(timeout=0.005)`. The queue only receives *bridged main-thread
  jobs* (`update_app`, a recorder render). A bare `TickRelay.request` does
  **not** put anything on that queue, so when the granted worker is running the
  main thread is blocked in `queue.get` and only notices the worker's request
  when the 5 ms timeout expires (or a job arrives). **Hypothesis H1: the
  arbiter's wake latency has a ~5 ms floor per round, so the two-line pays
  `~2 x 5 ms` of dead wall per shared tick plus the real work.**
* `_tick_frame` renders only if a `frame_callback` or a recorder exists; the
  scripted battery has neither (`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1`
  only), so **hypothesis H2 (render) is predicted to be zero** — measured anyway
  because it is one of the registered buckets.
* The physics step is **shared** between the two arms (one step advances both
  articulations), so **H3 (physics) predicts the two-line to be cheaper per
  shared tick than 2x the single arm's**, and it cannot explain a 1.86x ratio
  unless the step itself is much heavier under two live arms.

## 2. The registered buckets

For each arm, attribute the wall to exactly these, and report the **delta**:

1. the arbiter/relay (`schedule` self time = `schedule_s - physics`, rounds,
   rounds/tick);
2. the two arms' `ik_step`/control (`permit -> next request`, one sample per
   round, per arm);
3. the physics stepping itself (`SimulationManager.step` wall);
4. `RenderingManager.render()` / the camera (`_tick_frame` call count and wall);
5. the fruit/state reads (inside 2, named by py-spy);
6. **dead wall** — the main thread blocked in `queue.get` with both workers
   parked (`pump_s`, and its residual after the granted segment is subtracted);
7. anything else the profile names (driver loop, feed, station waits).

## 3. Instruments — two, and both are a separate profile build

The project's rule (AGENTS §2) is that per-tick work inside `ik_step` changes the
run, so **no instrumentation is added to the shipped control loop**:

* **I1 `cProfile`/`py-spy`** — an *external* sampler (`py-spy record`, 100 Hz,
  speedscope JSON). It adds no Python code to the process, so it cannot shift
  the control loop. Cross-line comparison is at the same sample rate and the
  same entry point.
* **I2 manual timers at the arbiter boundary only** — `logs/p82/timers.py`
  wraps `TickRelay.schedule` / `request` / `MainBridge.pump` /
  `CoopSession.install` (to time `relay.step_fn`) / `SimulationManager.step` /
  `_tick_frame`, i.e. **per round and per step, never per `ik_step`**. Loaded
  only by `logs/p82/profile_20.py` (a wrapper entry), never by a shipped script;
  it writes one JSON per run to `$P82_TIMERS` and prints **nothing** on stdout,
  so the log stays byte-comparable.

Both are *declared profile builds*. Their admissibility test is the branch: a
profile run whose `[fruit]` stream is byte-identical to the canonical record has
not moved the run, so its decomposition is a decomposition *of the recorded
branch*. A profile run that diverges is reported as a separate branch and only
its percentages are quoted.

Also (needed to keep the log comparable): the py-spy launcher replicates
`python.sh`'s env and execs the kit interpreter under `py-spy`, because
`ptrace_scope=1` and no root make attach-to-a-grandchild impossible. That
launcher is byte-checked the same way — its `[fruit]` stream must match too.

## 4. The decision rule for the one optimization

**At most one** change, and only if a bucket in §2 is (a) large, (b) named by
both instruments, and (c) **behaviour-neutral by construction** — i.e. it removes
work whose result nothing reads, or a wait that no state transition depends on.

The registered candidates, in order:

* **O1 (H1)**: the arbiter's wake latency. If the main thread is dead-sleeping
  in `pump`'s 5 ms timeout while the granted worker runs, then waking it on the
  worker's own request is behaviour-neutral: it moves *when* `schedule` is
  called, never *which* tick is stepped, which permit is granted (round-robin
  over `_last_run`) or what any control input is.
* **O2**: a repeated read whose result is already in hand, or a per-round
  allocation, **if** the profile names one.

Adoption test (all must hold, none can be waived):

1. **bit-identity** on the same scenario and seed: the post-change two-line
   `[fruit]` **and** `[biarm]` lines identical line-for-line to the pre-change
   record at the same instrumentation set, plus the `[stats]`/`[cycle]` rows;
2. **wall/sim falls** by more than run-to-run spread, measured on the same
   session with stamps (and confirmed in-process by the timer run);
3. the **single-arm control is byte-unchanged** (`[fruit]` stream vs the P71/P80
   record) — the change must be inert off the two-line path;
4. `scripts/selfcheck.sh` PASS and `scripts/accept.sh` `fingerprint: matches`.

**If no bucket is behaviour-neutral, the answer is "the wall is the harness, here
is the split"** and the code is not touched. That is a complete result: it is
what makes P80/P81's wall columns interpretable.

## 5. The arithmetic to deliver (§4 of the brief)

With the split, report

* `wall/sim` for the two-line before and after (and if nothing is adopted, the
  floor implied by the irreducibles: physics + both arms' control);
* the implied `wall/pick` and `wall placed/min`, and whether the two-line
  crosses the single arm's P80 bar (**1.02x pooled**), stating the arithmetic
  (`60 · placed / wall` with the same counts and the same sim span).

## 6. Runs planned (one simulator, claimed)

| id | arm | instrument | attempts | purpose |
| --- | --- | --- | --- | --- |
| `R1` | two-line `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1` | I2 timers | 20, seed 5 | arbiter split + branch check vs `logs/p80/T20.log` |
| `R2` | single arm | I2 timers (inert: no session) | 20, seed 5 | control; branch check vs `logs/p80/S20.log` |
| `R3` | two-line | I1 py-spy | 20, seed 5 | per-function share, cross-check of R1 |
| `R4` | single arm | I1 py-spy | 20, seed 5 | per-function share, the delta's other half |
| `R5..` | depends on §4 | — | — | the one optimization, if any |

Wall numbers are `[run] attempt 0` -> `[fruit] DONE` on the P80 stamp
instrument (`logs/p80/stamp.py` unchanged), so P80's numbers and P82's are the
same measurement.

## 7. OUTCOME (added after the runs; a post-hoc record, not part of the registration)

H1 is the one that held, and it held as a *wait*, not as Python work: the arbiter's
own cost is 0.024 ms/round (0.2 % of wall), while `MainBridge.pump`'s fixed 5 ms
timeout is 5.03 ms/round for 47,795 rounds. H2 (render) is 0.0 %; H3 (physics) is the
largest single term at 51 % and irreducible; H4 (the second arm) is 15.7 %.

O1 was taken (the arbiter's wake-on-request, `FRUIT_BIARM_WAKE_ON_REQUEST`, default
off) and passed all four adoption tests: bit-identity at two seeds (865/865 and
814/814 `[fruit]` lines), wall/sim 2.59 -> 1.69 with the count and the sim span
unchanged, the single-arm control byte-identical (710/710 and 346/346), and
`selfcheck.sh` PASS + `accept.sh` `fingerprint: matches` + `190` PASS. O2 was not
needed. Wall/pick 25.1 -> 16.4 s; pooled placed/min wall 1.02x -> **1.55x** against
the single arm (`RESULTS.md` §4-§6).

Recorded deviations from the plan in §6: one extra pair was spent on the F2
shared-station scheduler (`F0`/`F1`) because the change lives in code both schedulers
use; the seed-6 pair was added to make the pooled wall rate a two-seed statement; and
the py-spy cells (`R3`/`R4`) carried the knob unset (the pre-change tree), so they are
the *control's* per-function record, with the post-change decomposition coming from
the I2 timers (`W3`) instead.
