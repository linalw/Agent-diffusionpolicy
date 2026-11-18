# P220 result - the small-fruit handover runs inside a continuous episode

The continuous loop's `_finalize` starts the next pick when `FRUIT_DIRECT_CONTINUOUS` is
set. The question was whether the scripted skill's finalize does the same. **It does.**

**Lychee-only, one continuous episode, 6 picks, seed 808, `FRUIT_SMALL_HANDOVER=1`:**

| pick | fruit | result | ticks | decisions |
|---|---|---|---|---|
| 1 | 3.1 cm lychee | fail | 1261 | 0 |
| 2 | 3.1 cm lychee | placed | 1746 | 0 |
| 3 | 3.1 cm lychee | placed | 1657 | 0 |
| 4 | 3.0 cm lychee | placed | 1665 | 0 |
| 5 | 3.1 cm lychee | placed | 1930 | 0 |
| 6 | 3.0 cm lychee | placed | 2031 | 0 |

**`[cont] episode 5: picks=6/6 placed=5 ... ticks=10290 gap_ticks=76.0 gaps=[100,70,70,70,70]`**
- **5/6 placed in one continuous episode**, vs the learned continuous P204 **2/6**.
- The `[cont] pick k/6` rows run 2..6, so the scripted skill's finalize **does** return to
  the next pick; every small attempt is `decision=0` (no policy).
- 10,290 ticks = 85.8 s sim for 6 picks = **15.3 s/pick**; the gaps are 70-100 ticks.

**Mixed continuous is not delivered.** A mixed 6-pick run at seed 505 started pick 2/6
(orange placed, kiwi learned) and then **wedged** in the learned post-close phase after
12+ min, the known continuous-mode renderer/learned-path wedge (the lychee-only all-scripted
episode completes). The handover is not the cause; the learned large path is. The mixed
**per-episode** cell is 5/6 at seed 303 (P219).

**Verdict: the small-fruit handover is continuous-ready; the mixed continuous loop still
inherits the learned path's wedge.** The scripted small skill is the 5/6 carrier; the
learned large path needs the timeout-guarded/chunked runner or the P145b post-close fix
before a mixed continuous demo is a stable deliverable. No source change: the continuous
`_finalize`/`_begin_next_pick` path already does this.
