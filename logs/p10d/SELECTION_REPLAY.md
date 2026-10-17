# P10-D SELECTION_REPLAY: the two-line selection-allocation offline replay (Task A)

Status: Tier C, offline, **no simulator run** (the two live batteries - `accept.sh` and
the P10-C.1 seeds chain - were never touched; every command in this file is text
parsing). Written 2026-10-17 under `logs/p10d/`; read-only elsewhere.

Evidence base (all complete at final generation; the seeds chain finished
17:50:05):

| log | scenario | role |
| --- | --- | --- |
| `logs/p10c/10_armA_diag.log` | seed 5, monitor off | P10-C control (== P10-A record modulo reporting rows) |
| `logs/p10c/20_armB_1.log`, `21_armB_2.log`, `22_armB_diag.log` | seed 5, monitor on | P10-C treatment (bit-identical pair + diag) |
| `logs/p10c/50_seed11_A.log`, `51_seed11_B.log` | seed 11 | P10-C.1 seeds chain (A/B) |
| `logs/p10c/52_seed23_A.log`, `53_seed23_B.log` | seed 23 | P10-C.1 seeds chain (A/B; the chain completed 17:50:05) |

Tools: `logs/p10d/replay_common.py` (parser; validates every reconstructed selection
to <= 0.0001 m arithmetic closure), `logs/p10d/selection_replay.py` (this replay).
Raw output: `logs/p10d/10_selection_replay.txt`.

---

## 1. The premise correction: the shipped two-line rule IS nearest-first

The task brief described the two-line selector as "per-arm farthest-upstream-within-lane".
That is the **single-arm** moving-catch rule, not the two-line one. The shipped
two-line selector is **nearest-usable-above-the-floor**:

* Code path (`src/fruit_sorting/tasks.py`, tree pinned `tasks.py 09c920c9...`, the
  same md5 the P10-C battery pins): the worker calls
  `select_target(..., prefer_lane=bin_index, lane=None, ...)`; under pure grade
  routing (`pure_grade = prefer_lane is not None and self._pure_grade_routing()`,
  default on) the function ends at `usable.sort(key=lambda item: item[0]); ...
  if pure_grade: return usable[0][1]` - the **min-along** candidate above
  `_dynamic_select_floor()` (lines 3833-3851). The farthest-upstream rule
  (`_balance_arm`, `ordered[-1]`) is reached only when both `lane` and `prefer_lane`
  are `None` - the single-arm line (lines 3935-3964). The selector's own comment
  says so: "A lane selection (bimanual) takes the nearest usable fruit so the
  station is held for the shortest hover; the single-arm selection keeps the
  farthest-upstream rule".
* The candidate window is exactly `[station + 0.399, station + 0.85]`: floor =
  `_dynamic_pick_lead()` (0.189 printed) + `0.12*1.5` + 0.03 margin, with
  `_biarm_lead_args` returning `(1.4, None)` shipped so `max(1.5, 1.4) = 1.5` binds.
  The `FRUIT_STATION_FIRST` station window (`[0.10, 0.18]` left / `[0.00, 0.08]`
  right) sits entirely **below** the moving-catch floor, so it never fires on this
  line; the effective candidate set is the upstream window only.

Three independent log checks agree with nearest-first (all 8 logs, 160 attempts):

1. **Headroom** `y_sel - floor` (chosen fruit's position at selection minus the
   floor, reconstructed from its own wait rows + the attempt's `[cycle]`
   pre-pose/hover marks, `y_sel = y_wait0 + 0.12*(prepose+hover)`, closure
   <= 0.0001 m): pooled mean **0.163 m**, per-log means 0.134-0.184 m, p50
   0.150-0.188, min 0.001, max 0.379. Nearest-first predicts the gap from the
   floor to the next lane arrival (~half a lane spacing); **farthest-first
   predicts the chosen fruit near the window top** (headroom 0.30-0.45 m), with
   small-headroom cases impossible unless the window held a single candidate.
2. **Wait-loop duration** (wait entry -> handover, from the `fruit at pick point
   ... after N steps` row): per-log means **1.39-1.77 s**, max 3.42 s.
   Farthest-first would need ~4 s of hover wait per attempt
   (`(0.85-0.19-0.18)/0.12`) whenever a farther candidate existed.
3. **Handover queue** (`queue=` counts main-belt fruit in
   `[pick_y-0.05, pick_y+0.45]`, the chosen fruit included): mean 2.80-3.05,
   i.e. **1.8-2.05 other main-belt fruit in the station window** at handover,
   present in 15-17 of every 20 attempts. The clean counterexamples: seed-5 A
   slot 2 (left lychee, headroom **0.039 m**, queue 4) and slot 4 (left orange,
   headroom **0.045 m**, queue 6) - the arm picked the floor-bound candidate
   while 3-5 other fruit sat in the window. (Caveat: `queue` counts all grades;
   under the 0.375/0.375/0.25 mix ~3/8 of the others are same-lane, so a queue of
   4-6 implies ~1-2 other same-lane candidates with high probability, not
   certainty.)

So the allocation-refit comparison starts from: **shipped = SPT/nearest-first**;
the ETH robust-optimum pair's "SPT" component is already implemented, and its
"FIFO" component is the untested delta (with the caveat in section 4).

## 2. The measured selection geometry (per log)

Raw per-attempt tables are in `10_selection_replay.txt` (slot, arm, fruit, t0,
`y_sel`, floor, headroom, queue, wait, travel-to-handover, placed). Pooled:

| quantity | value |
| --- | --- |
| attempts reconstructed | 160 (8 logs x 20) |
| headroom (selection, above floor) | mean 0.163 m; per-log 0.134-0.184 |
| downstream distance at handover | **the lead, 0.188-0.190 m upstream of the station, constant across attempts and arms** (the handover is a fixed point; what varies is the travel to reach it) |
| selection-to-handover travel | 0.14-0.51 m (`travel = y_sel - y_handover`, exact; = 1.2-4.2 s of belt travel) |
| wait-loop duration | mean 1.39-1.77 s/log, max 3.42 s |
| starved polls | seed 5 A **41** (left 19 / right 22); seed 5 B **51** (18/33); seed 11 A **42** (35/7); seed 11 B **48** (26/22); seed 23 A **13** (13/0); seed 23 B **19** (19/0) |

The starvation burst structure (seed 5 A, `10_selection_replay.txt`): 8 bursts,
the largest 10 polls / 5.0 s (left, 87.9-92.4 s) and 9 polls / 4.5 s (right,
48.6-52.6 and 74.6-78.6 s). Bursts are the arm waiting for the next same-lane
fruit to enter the window: each poll is a 60-tick (0.5 s) step loop, and the
acquisition stream during a burst is exactly 0.5 s apart.

**The starvation split is a draw, not a fixed arm property**: across the three A
runs the split is (19,22) / (35,7) / (13,0) - the same scenario, a different
seed (the B runs: (18,33) / (26,22) / (19,0)). This is the P9-D re-draw
discipline applied to the starvation metric.

## 3. The measurement limit: the exact candidate set is NOT reconstructible

The logs print positions only for the **selected** fruit. Fruit that are never
selected (grade C under pure routing, or lane fruit that pass while the arm is
busy) have no logged position, and the feeder's backlog release spawns fruit
**mid-belt at virtual positions** (`fruits.py` `_pump_supply`: "places each due
fruit at the position it would have reached by now"), so backward propagation
from a later pick does not prove presence at an earlier instant.

The soundness test makes this concrete: a later pick of the **same lane**
propagated back to a starved instant must land outside that instant's window (the
arm would have taken it). It fires on **19/41** (seed 5 A), 19/51 (seed 5 B),
20/42 (seed 11 A), 18/48 (seed 11 B), 10/13 (seed 23 A), 10/19 (seed 23 B)
starved polls - i.e. ~50-60 % of the starved instants had a same-lane fruit
spawned in between. The `[fruit]` rows carry no other position source; `queue=`
is a count, not a set.

**Consequence for the replay**: rule evaluation cannot be run on position-resolved
candidate sets from these logs. What *is* measurable: the chosen fruit's exact
geometry, the count of other fruit present (`queue`), the starvation structure,
and the structural properties of each rule (section 4). The instrument for a
future exact-set measurement is one run with `FRUIT_SUPPLY_DIAG=1` (per-pump
released/refused rows) **and** `FRUIT_BIARM_LEAD_DIAG=1` (per-selection candidate
along-position + floor; W8-R3 L2, pure reporting) - both default-off, no control
input. Until that run exists, any fill-rate number for a cross-lane rule is an
estimate, not a measurement.

## 4. The rule evaluation (ranked)

Metrics per rule on the same logged material. "Starvation" = the starved-poll
count; "travel/wait" = the selection-to-handover cost; "interval" = the bounded
reading, with the coupling caveat that a different pick re-phases everything
downstream (P9-D) and is **not** claimed as measured.

| rank | rule | starvation | travel / wait | interval (bounded) | verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | **shipped nearest-first** (== SPT, min-along above floor) | baseline (41/51/42/48/13/19) | minimal: floor-bound, mean headroom 0.163 m | baseline | **keep** - weakly optimal within the lane |
| 2 | SPT / nearest-first (ETH robust optimum component) | identical | identical | identical | already shipped - no delta |
| 3 | FIFO / farthest-upstream | can be *lower* (the wait moves inside the attempt) | **+0 .. +0.45 m** travel (mean +0.17 m => ~+1.4 s hover wait; hard bound +3.75 s) | next attempt start = `max(t1+delta, next arrival) >= shipped` | dominated: trades a wait relocation for a weakly worse interval |
| 4 | [SPT; FIFO] asymmetric pair (Jermann) | as FIFO within the lane | +FIFO cost | as FIFO | **form inapplicable**: the ETH pair shares one object stream; our lanes are grade-disjoint, so the FIFO half cannot buy coverage |
| 5 | primary-then-conditional (BiDexGrasp #74) / V2 cross-lane fallback | the **only** rule that can fill a starved poll | nearest any-grade | ~0 interval gain; the starved spin is ~5 % of arm time and moves into the attempt | owner-gated (W3 pure routing): the fill is a **sort error** (the fruit lands in the wrong lane) and the fill rate is not measurable from these logs |

**Why within-lane reordering cannot move throughput** (the structural argument,
each piece measured or code-verified):

* Starvation = an empty candidate window; all within-lane rules see the *same*
  window, so an empty window stays empty - within-lane reordering cannot create a
  candidate.
* Nearest-first is the wait-minimal choice: the floor guarantees the setup
  (1.5 s) fits before the fruit arrives, and any farther fruit only arrives later
  - the attempt's handover is `max(setup_end, arrival)`, so the chosen fruit's
  arrival is the binding term and the nearest above the floor minimizes it.
* FIFO does not "bank" fruit for later: the arm's cycle is ~15-18 s and the
  window traverses in 3.75 s, so a fruit left in the window is 1.8-2.2 m
  downstream by the next selection - gone. FIFO's only visible effect is the
  *metric mix*: fewer starved polls, longer attempt spans, next start
  `>= shipped`. The starved-poll count is therefore a **phase-coupled metric**
  (P9-D); it must not be used as a primary endpoint for this lever family.
* The cross-lane fallback's ceiling is small and known: the starved spin is
  `polls x 0.5 s` = 20.5 s (seed 5 A) = **5.4 % of the batch's 382.6
  arm-seconds**, 25.5 s (seed 5 B), 21 s (seed 11 A), 24 s (seed 11 B), 6.5 s
  (seed 23 A), 9.5 s (seed 23 B) - and filling it costs the sort mix 1:1 (the
  arm picks a cross-grade fruit; the own-lane fruit that arrives while it is
  busy passes uncaught).

## 5. The falsifier check

Pre-registered L2 kill: *"replay changes < 5 % of selections, or the
starvation/interval count does not move in the replay."*

**Result: the falsifier fires for every within-lane rule, and no logged rule
dominates the shipped one.**

* The starvation count does not move for any within-lane rule (section 4,
  first bullet) - the second clause fires. The selection *identity* would change
  (the handover queue shows 1.8-2.05 other main-belt fruit in the window on
  15-17/20 attempts, so a FIFO rule would often pick a different fruit), but the
  metric does not, which is exactly the "selections change, nothing else does"
  outcome the kill exists to catch.
* The only rule that moves the starvation count is the cross-lane fallback; it is
  outside the pure-routing semantics (owner-gated, R5/W3) and its fill rate is
  not measurable from the existing logs (section 3). Its throughput ceiling is
  ~5 % of arm time with a 1:1 mix cost.
* `[SPT; FIFO]` does not transfer: the ETH asymmetry presumes one shared object
  stream; our two arms' lanes are grade-disjoint, and under pure routing the
  cross-arm `exclude`/`protected_indices` mechanism is provably inert (the left
  protects A-grade indices, the right selects only B; the sets cannot intersect).

**Answer to "is there a rule that dominates the shipped one on the logged
candidate sets?" - No.** The shipped nearest-first is weakly optimal within the
lane; the alternatives tie (SPT), are dominated (FIFO, [SPT; FIFO]), or are a
semantics change whose fill rate is unmeasured (cross-lane conditional). KB row
2 / L2 step 0 closes **negative for the in-scope (within-lane) refit**.

## 6. Pre-registration sketch for the best rule (the only one with a mechanism)

> **P10-E-CANDIDATE (cross-lane conditional fill, measurement first).**
> *Question*: at a starved poll, is there a usable candidate of the other grade
> in the starved arm's own window, and what does filling it cost the sort mix?
> *Step 0 (Tier A, one run, both instruments pure-reporting)*: the W6-A patch
> scenario + `FRUIT_SUPPLY_DIAG=1 FRUIT_BIARM_LEAD_DIAG=1` - the supply diag pins
> every release (position + index + grade), the lead diag prints each selection's
> candidate along-position and floor, so the starved instants' true candidate
> sets become measurable for the first time (they are not reconstructible from
> the existing logs, section 3). *Step 1 (only if step 0 shows fills)*: arms
> A = shipped / B = `FRUIT_GRADE_ROUTING=fallback` restricted to *starved* slots
> only (the V2 rule takes the nearest any-grade when the own lane has none; the
> new knob would scope it to the no-candidate branch so the primary lane choice
> is byte-unchanged), N >= 3 patch batteries + the dense re-record, interleaved.
> *Endpoints*: primary = the interval (NOT the starved-poll count - it is
> phase-coupled, section 4) and the per-lane **class mix** of placements
> (A/B/C x arm), secondary = the starved-spin share and lock-on. *Kills*: no
> interval movement; the mix shift exceeds the pre-registered band; any new
> failure reason; the two-line gate fails; **and the owner's sign-off on the
> semantics is a precondition, not an endpoint** - the fill is a documented sort
> error (cross-lane note class, R2). *Honest expectation*: the interval effect is
> bounded by the ~5 % starved-spin share and is likely ~0 (the arm is
> cycle-bound, not supply-bound); this is an owner-decision item, not a
> throughput lever.

## 7. What this changes for the KB

* BIMANUAL.md row 2 (selection-allocation refit): step 0 is now **done** and
  negative in scope. The row should be demoted to "measurement instrument only
  (supply-diag + lead-diag), owner-gated semantics" with this file as the
  evidence; the Jermann/BiDexGrasp transfer claims should carry the correction
  that SPT is already shipped and the FIFO half does not transfer to disjoint
  lanes.
* The starvation metric discipline: quote the starved-poll count only with its
  phase-coupling caveat (this file's section 4 and the P9-D phase-coupling note).
* No shipped default changed; no `src/` change; nothing written outside
  `logs/p10d/`.

## 8. Provenance

```bash
# parser + replay (no simulator; reads logs only)
python3 logs/p10d/selection_replay.py \
    logs/p10c/10_armA_diag.log logs/p10c/20_armB_1.log logs/p10c/21_armB_2.log \
    logs/p10c/22_armB_diag.log logs/p10c/50_seed11_A.log logs/p10c/51_seed11_B.log \
    logs/p10c/52_seed23_A.log logs/p10c/53_seed23_B.log \
    > logs/p10d/10_selection_replay.txt
# the 186 cross-check of the starvation/lock-on counts (offline)
python3 scripts/186_w6_report.py --label p10d logs/p10c/10_armA_diag.log ... > logs/p10d/00_186_A_B.txt
```

Tree pins (read-only): `src/fruit_sorting/tasks.py` **09c920c9...** (== the P10-C
battery pin in `logs/p10c/C_RESULTS.md`), `fruits.py` f5671a65..., belt speed
0.12 m/s (confirmed by the wait-row slope, 0.0010 m/tick at 120 Hz). Logs
touched: none (read-only). Files written: this file, `replay_common.py`,
`selection_replay.py`, `explore.py`, `10_selection_replay.txt`, `00_186_A_B.txt`,
`01_186_seeds.txt`, `20_lockon_attribution.txt`, `LOCKON_ATTRIBUTION.md`,
`WORKLOG_entry.md`.

## 9. Caveats

1. One scenario family (W6-A patch sheet, balanced mix, seeds 5/11/23), one
   deterministic branch per log; the double runs (seed 5 B1/B2/B-diag) are
   bit-identical and their per-log tables are printed separately - the pooled
   rows include all eight logs as listed, so the seed-5 B branch appears three
   times (a convenience sum, not a weighted sample; the per-log rows are the
   primary record).
2. All eight logs are complete (the seeds chain finished 17:50:05); re-running
   the command in section 8 regenerates the tables. A killed or partial log
   simply contributes fewer attempts (the parser rejects missing blocks
   gracefully).
3. The headroom reconstruction assumes the fruit rides at the belt speed
   between selection and wait entry; the <= 0.0001 m closure across all 160
   attempts validates it.
4. The starvation instants are the acquisitions paired with the following
   `no eligible` row; the pairing is unambiguous because each arm runs one
   attempt at a time and the acquisition precedes the selection in the same
   run-permit segment.
