# P40 phase 3 — R-R (the regrasp cap) and R-S (the selector's over-commit)

Measured 2026-10-26 on the P39-final tree `1790b87` + two default-off changes:
the P40-G0 `FRUIT_GRIP_EFFORT` instrument (kept, `tasks.py` `34275f07` before
this phase) and the phase-3 R-S selection knob added here. **No shipped default
changed, no `configs/` file touched, no commit, `scripts/189_w7a_chain.sh` not
run.**

| pin | value |
|---|---|
| HEAD | `1790b87` |
| `src/fruit_sorting/tasks.py` | **`a5cfb6d8`** (was `34275f07`: +the R-S knob and its comment) |
| `src/fruit_sorting/rl_env.py` | `c88a2107` — `TASKS_MD5` metadata-only follow `34275f07 -> a5cfb6d8` (+ a scope comment; no behaviour) |
| `src/fruit_sorting/scene.py` | `988985ef` (untouched) |
| `configs/motion_reference.json` | `25ade92b` (untouched) |
| `configs/motion_reference_twoline.json` | `d0326030` (untouched; never re-recorded here) |

Tree md5s before the batteries: `logs/p40/p3/tree_md5_before.txt`. The offline
self-check is `PASS: 0 failures, 1 skipped` on this tree.

Oracle gate 2 (the phase-3 input) **CUT the substeps pear test** (the force is
already measured: `EFFORT_READ.md` §0-§4), **amended R-R** (add the gate item and
the scope statement) and **proceeded R-S**. Nothing here re-runs a force or
friction cell, and no "shorter setup" and no floor value was tested
(`ARRIVAL_SPLIT.md` §5: the arm block is fully overlapped, 0 s additive).

---

## R-R — `FRUIT_REGRASPS=2`, measured

`FRUIT_REGRASPS` caps the probe/regrasp loop at `tasks.py:10629`
(`for _regrasp in range(int(os.environ.get("FRUIT_REGRASPS", "3")))`; **phase 4
replaced that literal with the resolved `regrasp_cap`** - 2 on the dynamic line,
3 on the indexed/policy path, an explicit env value winning on both, now
`tasks.py:10640-10645`; see `P4_RESULTS.md` §A). The
question `REGRASP_YIELD.md` left open is whether bounding `3 -> 2` is free: over
109 attempts the corpus has **one** conversion on the *second* probe and **0/17**
on the third, at **1.24 s (two-line) / 1.50 s (single arm)** per failed probe.
`=2` keeps probes 1 and 2 and removes only the third.

### (a) the two-line battery — `logs/p40/p3/regrasp2_twoline.log`

| | control `logs/p39/p3/twoline_C.log` | `FRUIT_REGRASPS=2` |
|---|---|---|
| placed | **6/10** (left 3/5, right 3/5) | **7/10** (left 4/5, right 3/5) |
| batch sim span | 90.2 s | **88.2 s** |
| s/attempt / placed/min | 9.0 / 3.99 | **8.8 / 4.76** |
| placement window | 56.3 s -> 5.33/min | 55.6 s -> 6.47/min |
| pooled interval (n) | 11.26 s (5) | 9.27 s (6) |
| per-arm interval left/right | 17.95 / 28.15 s | 16.87 / 27.15 s |
| lock-on left/right | 3.55 / 3.25 s | 3.12 / 4.25 s |
| idle left/right | 16 % / 15 % | 15 % / 20 % |
| re-seat rows printed | **13** | **5** |
| `diverted` | 0 | 1 |

**`placed/min`, `s/attempt` and the interval above are NOT a rate claim.** The
two arms are in different attractors (`diverted` 0 vs 1), so with a fixed attempt
count and a flat cadence every headline throughput number is a **monotone
transform of the count**: `4.76 placed/min` is `60 x 7 / 88.2` and the `9.27 s`
pooled interval is `60 / 6.47` — both move only because the count moved 6 -> 7 on
a moved branch (the P1/P2 lesson, `AGENTS` §2 "Do not quote the ladder as a
throughput result"). The same holds for the single-arm row below. **This table's
rate columns stay out of `AGENTS.md`.** The clean reads are the same-attempt
ones:

* **The first differing filtered line is the third re-seat row printed in the
  batch** (filtered line 92 of 427 vs 430: the control prints
  `dynamic regrasp: re-seated in place (gap 52.3 mm kept)` there and the
  treatment goes straight to the carry's `re-anchoring` row): everything before
  it — the first close, the approach motion row and two re-seat rows — is
  byte-identical, so the knob's only causal entry into the stream is the probe it
  removes.
* **The two capped attempts are the control's own `k=3` attempts** (same slot,
  same arm, same fruit index: right peach `idx 12`, left kiwi `idx 13`) and they
  end **identically** — `grasped=False`, `lift=+0.003 / +0.000 m`, note
  `['fruit did not follow the gripper']`, `force=3.98 / 0.00 N`. Only the time
  moves:

  | slot | fruit | `[cycle] grip` control | treatment | delta | span control -> treatment |
  |---|---|---|---|---|---|
  | 0 | right peach idx 12 | **5.45 s** (k=3) | **3.93 s** (k=2) | **-1.52 s** | 14.9 -> 13.1 s |
  | 1 | left kiwi idx 13 | **5.42 s** (k=3) | **4.00 s** (k=2) | **-1.42 s** | 15.1 -> 13.8 s |

  i.e. the **measured k=3 tax is 1.42-1.52 s** on these two attempts (the corpus
  mean per failed probe is 1.24 s; these two probes were the slow ones), and the
  third probe again converted nothing.
* The `[cycle] grip` -> `k` map closes exactly against the printed rows
  (**sum k = 13** on the control, **= 5** on the treatment; the rows cannot be
  attributed positionally — `REGRASP_YIELD.md` §2), `logs/p40/p3/k_map.py` ->
  `logs/p40/p3/k_map.txt`.
* **`=2` does not exhibit a rescue here, and the `k=1` row it creates is not
  one.** Treatment slot 2 (right pear `idx 9`, grip 3.23 s, span 15.3 -> 16.8 s)
  is `placed=True`, but the **control placed that same fruit on its first try**
  (slot 2: `k=0`, grip 1.77 s, span 15.3 s) — so the treatment's second probe is
  a **new two-probe attempt** on a fruit the control never needed a re-seat for
  (+1.5 s of grip on a success), not the corpus's conversion path. The corpus
  rescue (`twoline_C` slot 4, a right peach whose second probe held after the
  first failed, `REGRASP_YIELD.md` §3) has **no counterpart in this battery**.
  The path is preserved *by construction* (`=2` keeps probes 1 and 2, so any
  `k=1` attempt is still attempted twice) — this run does not demonstrate it.
* `scripts/186_w6_report.py` re-derives every interval/lock-on number above.

### (b) the single-arm acceptance — `logs/p40/p3/regrasp2_accept.log`

| | control `logs/p39/p3/accept_C.log` | `FRUIT_REGRASPS=2` |
|---|---|---|
| placed | **6/10** | **5/9** (attempt 7 `no eligible fruit`) |
| `[stats] sim` (= sum of attempt spans) | 150.2 s | **133.0 s** |
| s/attempt | 15.0 | **14.8** |
| placed/min | 2.40 | 2.26 |
| re-seat rows | 3 | **2** |
| motion gate | 6/10 + `fingerprint: matches` (rate only) | 5/9 + `fingerprint: DIFFERS` (rate **and** fingerprint) |

**The mechanism is clean and the count is not.** Attempts 0-2 reproduce the
control line by line (same fruit, spans 13.9/16.2/14.6 s, waits 0.42/2.35/0.93 s
— all identical), and **attempt 3 is the corpus's `k=3` orange, whose span falls
14.1 -> 12.6 s (-1.5 s, the predicted 1.50 s)** with the identical terminal
(`grasped=False`, `lift=+0.001`, note `['fruit did not follow the gripper']`) —
the third probe produced nothing for the third recorded time. From attempt 4 the
1.5 s shift re-rolls the fruit sequence (the control's orange/apple/lychee tail
becomes strawberry/`no eligible fruit`/strawberry/apple), so the batch lost one
attempt and one placement: **5 < 6 fails the pre-registered `>= C`
non-inferiority by the letter**, in a moved attractor where the countable
mechanism (1.5 s on 1 of 10 attempts) is confirmed.

### (c) the two-line gate — `logs/p40/p3/190_regrasp2_twoline.txt`

`bash scripts/190_twoline_gate.sh logs/p40/p3/regrasp2_twoline.log` (the brief's
`python3 ...` line is a typo: 190 is a shell script):

* **rate PASS** — 7/10 = 70 % against the two-line floor 0.60;
* **motion budgets PASS** — all 10 descents inside budget (worst `|v|max`
  0.110 vs 0.160-0.161; lurch 0.018 vs 0.291; `a_win5` 0.84 is a
  carrying-number warning on a descent, not a budget); worst held-grip cone
  3.29x **reported** (the dynamic line's cone is reported, `--strict-cone` is the
  old rule), 4/18 legs above 0.45 m/s hand speed also reported;
* **fingerprint DIFFERS** from `configs/motion_reference_twoline.json`
  (`d0326030`) — the expected moved branch for a timing lever, recorded and not
  adjudicated (AGENTS §2). The gate therefore FAILs on the fingerprint item
  alone, and it must: a re-recorded reference is a phase-4 decision, not this
  battery's.

### Scope of the bound, and the re-seat interaction

* **The bound applies to the shared primitive, not just this line.** The loop
  lives inside `_grasp_carry_place_impl` (`tasks.py:8331`), which is the body of
  `grasp_carry_place` — so the indexed primitive, the policy handover and the
  scripted dynamic line all read `FRUIT_REGRASPS`. **On the indexed/policy
  paths nothing prints**: both re-seat rows sit inside
  `if self._dynamic_capture_active:` (and `if verbose:`), the direct/policy
  handover is `scripted=False` so `_dynamic_capture_active` is False, and
  `DirectSortEnv` runs `verbose=False`; the third probe's only other row
  (`recovery: re-grasped`) is behind the default-off `FRUIT_REGRASP_REOPEN`.
  **So this battery says nothing about that path** — no published number here
  covers the direct loop, and a direct-path claim needs its own A/B.
* **Each re-seat is a control event, not bookkeeping**: the block calls
  `_force_servo_reset(arm_name)` and re-seats the pads on the fruit's *measured*
  centre with `follow_centre(...)`, then squeezes 3 mm harder next iteration. So
  removing the third probe also removes one servo reset + pad re-centre and one
  squeeze step from every capped attempt — that is *part of* the measured
  1.42-1.52 s, not a separate lever.
* **`FRUIT_REGRASP_REOPEN` keys off `FRUIT_REGRASPS - 1`** (`tasks.py:10923`), so
  under `=2` the last-resort open/re-seat/close recovery would attach to the
  *second* probe instead of the third. It is default **off**, and every number
  above is the reopen-off path; with it on the cap would delete the third
  probe's reopen slot, which is a different (untested) configuration.

---

## R-S — the single-arm selector's over-commit

`logs/p40/ARRIVAL_SPLIT.md` §5 measured the single arm's commit 0.04-0.33 m
**beyond its own `_dynamic_select_floor()`** (the shipped rule takes the
*farthest-upstream* eligible fruit, `_balance_arm` -> `ordered[-1]`) and priced
that distance as 0.3-2.8 s of belt travel per attempt paid as waiting, with the
arm-side block fully overlapped (0 s additive). The lever is therefore the
*choice among floored fruit*, not the floor, the setup or the aim.

### The change (default off, single-arm line only)

```python
if os.environ.get("FRUIT_SELECT_NEAREST_ABOVE_FLOOR", "0") == "1":
    near_floor = floor + float(os.environ.get("FRUIT_SELECT_NEAREST_MARGIN", "0.0"))
    near = [item for item in usable if item[0] >= near_floor]
    if near:
        return _chosen(near[0][1])
    ...  # diag row, then the shipped rule
return _chosen(self._balance_arm(usable))
```

* site: `select_target`'s single-arm return (`tasks.py:5417-5449`). `usable` is
  the already-floored candidate list, sorted ascending, so `near[0]` is the
  **nearest** floored fruit. Scope is structural: the two-line selector
  (`prefer_lane` set, `lane=None`) and the shared-station worker (`lane` set)
  return from their own branches **above** this line, so neither can reach it;
  `_dynamic_select_floor`, `_dynamic_aim` and the windows are untouched.
  **The direct/policy environment's episode selection is not excluded** — it
  calls `select_target(..., reach_anywhere=False)` with no lane
  (`rl_env.py:1647`), so a direct-loop use of this knob is a *new configuration*
  that needs its own A/B. It is unset everywhere in this tree (its own reseed
  path passes `lane`, so that one is excluded).
* `FRUIT_SELECT_NEAREST_MARGIN` (default **0.0 m**) raises the near rule's own
  floor and falls back to the shipped rule if it would empty the set - a margin
  experiment, not a new floor. It is not exercised here.
* `rl_env.py`'s `TASKS_MD5` is a metadata-only follow of the edit (the
  provenance guard, not a behaviour switch).

### Byte-identity of the unset path (proved, not argued)

`logs/p40/p3/nearest_off.log` - the same tree, the same command, knob unset,
first arm of the same stretch (01:25:36-01:30:02) - is **376/376 filtered
`[fruit]` lines IDENTICAL** to `logs/p39/p3/accept_C.log`
(`filter_stream.py --diff` exit 0), with the same 6/10, `sim=150.2 s`,
15.0 s/attempt and `fingerprint: matches configs/motion_reference.json`
(`25ade92b`). The unset path is the shipped stream, not "equivalent to" it.

### The readout (`logs/p40/p3/nearest_accept.log`, 10 attempts, SEED=5)

| | C (knob unset) | `=1` | delta |
|---|---|---|---|
| **arrival wait, mean (median)** | **1.41 s** (1.20) | **0.97 s** (0.63) | **-0.44 s** |
| arrival wait min / max | 0.42 / 2.48 | 0.24 / 2.49 | |
| loop-entry `dy0`, mean | 0.358 m | **0.305 m** | -0.053 m |
| attempt span, mean (median) | 15.01 s (14.60) | 14.64 s (14.60) | -0.37 s |
| **s/attempt** (`[stats]`) | **15.0** | **14.6** | **-0.4 s** |
| **placed** | **6/10** | **7/10** | **+1** |
| carried / no-grasp | 3 / 1 | 2 / 1 | |
| re-seat rows | 3 | 3 | 0 |
| `discharged` (tray rows) | 4 | 5 | +1 |
| `recirculated` / `diverted` | 0 / 0 | 0 / 0 | 0 |
| attempts (`no eligible fruit`) | 10 (0) | 10 (0) | 0 |
| motion gate | rate-only FAIL, fp **matches** | rate-only FAIL (7/10 < 75 %), fp **DIFFERS** | moved branch |

The printed recycle counters on this supply are the `[belt] ... discharged to the
tray` rows (4 -> 5) and `recirculated=` / `diverted=` in `[stats]` (0/0 both);
**`reached_end` and `supply_skipped` are not printed** here (they belong to the
bed stock census and to a `no eligible fruit` row, which neither arm produced),
so the "skip" readout is: **no attempt skipped in either arm**.

Per-attempt arrival wait (`after N steps` / 120 s; `p3_report.py`):

```
att  C wait  =1 wait   C fruit / =1 fruit
 0    0.42    0.42     peach / peach        (only one floored candidate: unchanged)
 1    2.35    0.40     peach / strawberry
 2    0.93    0.36     kiwi  / kiwi
 3    1.03    0.24     orange / orange
 4    2.48    1.39     lychee / lychee
 5    0.57    2.49     strawberry / strawberry
 6    0.68    0.63     pear  / pear
 7    1.20    1.23     orange / orange
 8    2.27    0.63     apple / peach
 9    2.18    1.91     lychee / lychee
```

**Two independent parses agree on the size of the win**: the wait falls 0.44 s
and the loop-entry position falls 0.053 m = **0.44 s of belt travel at
0.12 m/s**; the span falls 0.37 s (the wait is inside the span; the residual
0.07 s is the moved branch's other segments).

**The commit distance, stated as a range and NOT as a lower-bound artefact.**
The naive read (dy0 + pre-pose travel) is **0.463 -> 0.411 m**, but that parse
**excludes the ~0.76 s hover**, and the floor's own `1.5 s` setup term *includes*
it — so the two are not measuring the same interval and the raw number is a
**lower bound**, not a commit distance. Adding the hover's 0.76 s x 0.12 m/s =
**0.09 m**: the true commit is **~0.553 -> ~0.501 m** against a `0.399 m` floor,
i.e. the nearest rule sits **~0.15 -> ~0.10 m above its own floor**, not "at"
it. So the lever **does not spend the selection margin** the shipped floor buys
(the setup headroom that the v9 pre-fix collapse needed, `AGENTS` §2) — it
removes the measured **0.053 m** of loop-entry over-commit (0.44 s of wait) and
leaves **~0.10-0.15 m** of margin above the floor. That **downgrades** this
item's risk: a 0.10-0.15 m margin is still on the same side of the floor as the
control.

**Falsifiers (all three pass - the item is positive):**

1. *the wait does not fall* -> it falls **1.41 -> 0.97 s** mean (1.20 -> 0.63
   median), and the cases that do not move are the ones where only one floored
   candidate existed (attempt 0: 0.42 = 0.42). **PASS**;
2. *placed < C-1* -> **7 >= 5** (and `>= C` = 6). **PASS**;
3. *a new failure reason* -> the reason set is the control's own two classes
   (`carried-not-placed` with empty notes, and attempt 3's
   `['fruit did not follow the gripper']`); nothing new. **PASS**.

**The mechanism, exactly**: the first differing filtered line is attempt 1's
*selection* — `peach grade A into output lane 0` (farthest) becomes
`strawberry grade C into output lane 1` (nearest above the floor). The knob
therefore also re-orders *which arm* works (this line sets the arm from the
fruit's grade): the left/right split stays 5/5, but its composition moves
(attempt 8 becomes a left peach) and the left's placements go **1 -> 2**
(control left 1/3/1 -> 2/2/1). That is the lever's real risk — the nearest
floored fruit may be a grade the other arm sorts — and it did not cost here.

**Verdict**: the wait falls by the measured amount, the count does not fall, no
new reason appears → a **positive at 10 attempts on one branch**, with the
caveats that (i) it is a moved attractor (`fingerprint: DIFFERS`, recorded, not
adjudicated), (ii) the acceptance's own rate floor (75 %) fails in **both** arms
— the known P32 6/10 branch — so the 7/10 is not a rate claim against the
shipped 9/10, and (iii) `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` is **not shipped**:
a default flip needs its own reference re-record, an adoption gate and the
two-line/`190` no-harm batch, all phase-4 decisions.

---

## Refused / not run (and why)

* **the substeps pear test** — CUT by Oracle gate 2: the force is already
  measured (`EFFORT_READ.md`; 4.42 -> 9.95 N at 480 Hz) and the battery would
  re-measure a force step, not a class.
* **a "shorter setup"** (pre-pose/hover speed) — `ARRIVAL_SPLIT.md` §5: the arm
  block is 100 % overlapped by the fruit's travel, so it can only re-label the
  wait. **The floor value** is likewise untouched: this phase changes only which
  floored fruit is taken.
* **R-R on the direct/policy interface** — the bound reaches
  `_grasp_carry_place_impl` but prints nothing there (§R-R scope), so it needs
  its own A/B; nothing here is a statement about that path.
* **`FRUIT_SELECT_NEAREST_MARGIN`** — plumbed, default `0.0`, **not exercised**:
  a margin sweep is a new pre-registration.
* **`FRUIT_REGRASP_REOPEN`** — default off and left off: with `=2` its
  last-iteration slot moves from probe 3 to probe 2, which would be a different
  configuration.
* **`scripts/189_w7a_chain.sh`** — never run; it rewrites
  `configs/motion_reference_twoline.json`. `scripts/190_twoline_gate.sh` is
  read-only and was run as the brief asks (note: the brief's `python3` prefix is
  a typo; 190 is a shell script).

## What this does *not* claim

* No cross-attractor success-rate comparison: R-R (b) 5/9 vs 6/10 and R-S 7/10
  vs 6/10 are counts in **moved** branches, and the only paired quantities
  quoted here are per-attempt mechanism numbers (`[cycle] grip`, the wait, the
  loop-entry position).
* No adoption: both knobs are default off; no `configs/` file changed; nothing
  committed.

