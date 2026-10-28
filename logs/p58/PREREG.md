# P58 phase 1 PREREG — the continuous-supply stack, the adoption A/B

Written **before any run** (2026-10-28), from `logs/p57/{RESULT.md,cand_census.txt}`
and `.slim/deepwork/p58-continuous-supply.md`. This file fixes what the simulator
battery is allowed to conclude. Nothing here is a shipped-default change; the
decision the phase feeds is Oracle 1 (adopt / not adopt), taken by the owner.

## 0. The question

The three default-off knobs of the continuous stack were each measured on their
own at seed 77 (`FRUIT_FEED_CADENCE`, `FRUIT_SUPPLY_BAND_INTERLOCK`, and the
P55/P56 pair `FRUIT_DIRECT_FEED` / `FRUIT_DIRECT_CONTINUOUS`). The combined stack
was measured **once** on a single branch (`logs/p57/band_s77.log`: 15 picks,
`window=0` 1/16, longest gap 110 ticks, placed 11/15). The owner's intent is
supply continuity, not a rate: *as long as fruit are available they should be
sorted promptly; slowness caused by a lack of fruit is acceptable; the line must
deliver fruit continuously, not in bursts or on a timed refresh*.

**Question: does the stack deliver the owner's continuity endpoints on three
seeds, without a new failure reason and without moving a shipped path?**

## 1. The arms

Both arms, in full (nothing else is set except the harness block in §1.3):

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1
```

**A — control: today's shipped direct configuration.**

```bash
--episodes 15                       # no other env
```

**B — the continuous stack.**

```bash
--episodes 1
FRUIT_DIRECT_CONTINUOUS=15 FRUIT_DIRECT_FEED=1 FRUIT_FEED_CADENCE=1
FRUIT_SUPPLY_BAND_INTERLOCK=1 FRUIT_SUPPLY_BAND_MAX=3
```

Deliberately **not** set in either arm, because they are the shipped defaults
since P54/P43 and setting them would make the arms differ from the shipped line:

* `FRUIT_POLICY_TRIGGER_ACQ` — **not set**; resolves **on** for
  `presentation == "direct"` (P54). Both arms therefore run ACQ on, and the P54
  re-baseline rule applies: every direct number measured before P54 is an
  ACQ-off control number and is not comparable.
* `FRUIT_ARM_PARK` — **not set**; resolves to `back` for the direct presentation
  (P43, `_park_default`). Both arms run the park.
* `FRUIT_REGRASPS` — unset; the P40 path scope (2 on `_dynamic_capture`) applies
  to both arms.
* `FRUIT_SUBSTEPS`, `FRUIT_FINGER_STIFFNESS`, `FRUIT_FINGER_MAXFORCE` — unset;
  the P40/P41 shipped values apply to both arms.

### 1.1 The two arms differ in more than "one knob" and this is the point

B is a **stack**: the cadence (the feeder's clock runs during the primitive
phase), the band interlock (the release paces on the selector's approach band
`[pick_y+0.35, spawn_y]` with a depth ceiling of 3), the direct feeder (the
spawner also advances during the policy phase) and the multi-pick episode (one
reset per 15 picks, a re-selection after every place). This is the **adoption
test of the stack as a unit**, not a per-knob screen — the per-knob mechanism
reads are already published (P55/P56/P57). Arm A is the shipped configuration, so
a pass would be adoptable as-is; a fail says the stack as a unit does not deliver
the endpoints, and does **not** attribute the failure to a member.

### 1.2 The episode count differs between the arms (the easiest way to wreck it)

Arm A runs `--episodes 15` = 15 picks = 15 logical episodes. Arm B runs
`--episodes 1` with `FRUIT_DIRECT_CONTINUOUS=15` = 1 logical episode = 15 picks.
`--episodes 15` on arm B would deliver 225 picks. The driver asserts
`picks_seen == 15` from the `[rl] episode ... success=` rows before the report is
accepted; a run whose count differs is reported and flagged, never silently
pooled.

**Unit: one pick = one `[rl] episode` outcome row.** 3 seeds × 15 picks = **45
picks per arm**, 90 picks total.

### 1.3 Fixed harness block (both arms, the P54 batch verbatim)

`checkpoints/moe_v13s/policy_best.pt` (md5 `61da390a`); `execute_steps=4`,
`ddim=16`; `HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER=`
`FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1`; one `scripts/154_claim_run.sh` claim per
run; `RUN_LIMIT=1800`. No `--record` (no endpoint reads a store; a store would
only add wall and I/O).

### 1.4 Seeds, order, files

Seeds **77 / 101 / 202**, **interleaved A then B** per seed (the P54/P43 batch
shape). Logs `logs/p58/p1/{A,B}_{seed}.log`. One claim per run (the claim
script itself polls, so back-to-back runs cannot overlap). A run that wedges
(the known renderer freeze) is retried **once** and the retry is recorded as
such; a second wedge on the same file is reported and the batch continues.

Tree pins (recorded in `logs/p58/p1/P1_header.txt` before the first run):
`rl_env.py` `ddcb7816`, `tasks.py` `c7eef701`, `fruits.py` `55921c46`,
`scene.py` `27e3d64a`, `control.py` `9384ff4f`, `trigger.py` `b09d3cb2`,
`runtime.py` `379ac706`, `configs/arm_parks.json` `42ab4fb7`,
`configs/motion_reference.json` `8a399626`, `..._twoline.json` `2246f83c`,
HEAD `96849c6`. No `src/`, `configs/`, `datasets/` or checkpoint write in this
phase.

## 2. Endpoints (the decision rule, written first)

### P1 — the pickable-band stock (PRIMARY; the owner's intent, mechanism)

Two mechanical reads, both from the logs:

1. **`window >= 1` share at the selections.** Every `[bed-sel] attempt` row
   (`FRUIT_BED_DIAG=1`) is one **selection instant**; `window=` is the number of
   candidates the moving catch's floor admits (`usable + chosen`). A row with
   `pick=none` is an empty selection and carries `window=0` by construction, so
   it counts in the denominator (that is the honest reading: a selection that
   found nothing is the failure mode the endpoint exists to catch). B's
   multi-pick path prints one extra `[bed-sel]` row from a starve episode's empty
   round **in addition to** the row of the successful retry, so empty rounds are
   counted at least once, never zero times (A's reset prints only its successful
   selection - amendment A1.1, which is why A's share is an upper bound).
2. **The longest inter-pick gap**, in ticks, per B run: the `[cont] ... gap_ticks=`
   values, cross-checked against the `[cont] episode` summary's `gaps=[...]`
   list (the two must agree). One gap is one pick boundary
   (`_finalize` → next pick's first `act`).

*Pass bars, conjunctive:* **`window >= 1` at `>= 95 %` of arm B's selections,
pooled over the three runs**, **and the longest gap `<= 140` ticks in every B
run**.

**Arm A's same numbers are the control and its gaps are 140 by construction.**
A has no `[cont]` rows (no multi-pick episode); the per-episode boundary was
measured at exactly **140 ticks = 1.167 s** (30 feed + 3×30 teleport + 20 settle)
on 14/14 transitions and 11/11 resets (`logs/p56/CENSUS.txt`, P56), so A's
per-run longest gap is reported as **140 (by construction, not re-measured)**
unless a run reports a starved reset ("no graspable fruit reached the selection
window in 40 feed rounds"), which would be longer and is reported if it happens.
A's `window>=1` share **is** measured (same `[bed-sel]` format) and is reported
beside B's.

*Why 95 % and 140:* the owner's endpoint is "a fruit is always there when the arm
is ready". The P57 single-branch read was 15/16 = 93.8 % with one 110-tick gap;
95 % pooled at 45 picks means **at most 2 empty selections of 45**, i.e. it asks
the stack to clear the 1-in-16 rate that P57 measured, not to be perfect. 140
ticks is A's own boundary: a B gap at or below it means the multi-pick episode
never waits longer than the shipped reset it replaces.

### P2 — no new failure reason

Normalised exactly as `scripts/113_rl_report.py`'s `reasons()`: for every
unsuccessful row, the whole `notes=[...]` text with every run of
`[-+0-9.]+` replaced by `#`. Baseline = the union of the same normalisation over
**`logs/p43/p3/*.log` and `logs/p54/p1/*.log`** (the P43/P54 baseline set, the
P56 precedent). *Pass bar:* `keys(B) ⊆ keys(A) ∪ baseline`. A new key is a
**FAIL** even if the rate is fine (P38/P41 precedent). Reasons are reported in
both directions (`B - A`, `A - B`) and the raw note fragments are listed.

### P3 — the scripted no-harm (a shipped path must not move)  *[amended by A2]*

`scripts/accept.sh` on this tree with **all knobs unset** (the batch's own env
does not leak into it; it runs in its own process):

* the motion gate must print **`fingerprint: matches`** against
  `configs/motion_reference.json` (`8a399626`, the P41 re-record), and
* the log's `[fruit]` physics lines must be **byte-identical** to the 376 lines
  of `logs/p34/73_accept_no_harm.log` (which P35-P43 all reproduce; P50 is the
  one exception and re-recorded nothing).

*Pass bar:* both, **as amended by A2** (the same-tree record is
`logs/p53/03b_accept_noharm_run.log`, 377 lines; the p34 file named below is
pre-P41 and is kept as a diagnostic only). The rate line is **not** an endpoint (the acceptance's 6/10 is
the `cnp` class of record, `logs/p42/SIM_LIMIT.md`). `ACCEPT_LOG` points into
`logs/p58/`, never at `logs/accept.log`.

### P4 — the placed count (REPORTED ONLY)

`placed` per arm, pooled and per run, with the per-arm split (`arm=left/right`
on each row). **No rate claim in either direction**: the two arms are different
scenarios (the supply changes which fruit are presented), the loop is
non-reproducible (rendered frames), and AGENTS §2 forbids a cross-configuration
success-rate comparison. The count is reported because a *collapse* would be
visible in it and because the stack's single-branch read was 11/15.

### P5 — the wall cost per pick (REPORTED)

Wall seconds per pick = the run's `[rl] run wall end ... duration Xs` divided by
the picks delivered, per run and pooled. Report only; no bar. (P55 measured the
direct feeder at +11.1 % wall, P56 the multi-pick mode at -4.8 % on one branch;
this endpoint exists to state the stack's cost on three seeds, not to gate it.)

### 2.1 Secondary mechanism reads (reported, not gated)

From the same rows, because they cost nothing and name the mechanism if P1
fails: `on_belt` / `live` medians per arm, `admitted` (the band count), the pump
`lag=` (schedule clock vs now), `skipped`, `rebased`, `dropped`, and the gap
distribution (how many 50 / 80 / 110 / >140). The `[cont]` summary's
`picks=`, `placed=`, `reward=`, `ticks=` are used for the accounting.

## 2.2 AMENDMENT A1 (written offline, 2026-10-28, **before any run**)

Two facts about the instrument, found by reading the tree and one P56-era log
while rehearsing the parser. They change nothing that is gated; they change how
one control number must be read, and they add one secondary read.

**A1.1 — the `[bed-sel]` print sites differ between the arms.** On the current
tree the reset path prints exactly **one** census row per pick: `_begin_pick`
(`rl_env.py:2387`) prints the *successful* selection's `diag`, and the reset's
retry rounds (`while True: ... rounds += 1`) print **nothing**. The
multi-pick path (`_begin_next_pick`, `rl_env.py:4957`) additionally prints the
**empty** round's census (`rounds == 0` and `rounds >= 40`). Consequences:

* **A's `window>=1` share is an upper bound** on A's selection-level share - its
  starved rounds are invisible, B's are counted. The A-vs-B share is therefore
  **not a like-for-like contrast**, and A's number is context only (the
  registered bar, P1a, is on B alone, as written).
* the P56-era log `logs/p56/p3/Q12_s77.log` carries **24** `[bed-sel]` rows for
  15 picks because that tree printed per round; it must not be used as this
  statistic's A reference.

**A1.2 — one uniform secondary read: the selection-clock gap.** Consecutive
`[bed-sel] attempt` rows carry the sim time `t=` at the selection instant, and
each pick carries its own `ticks=`; so

```
sel_gap_k = 120 * (t_{k+1} - t_k) - ticks_k        (ticks)
```

is measurable in **both** arms and sees A's silent retry rounds (each retry is
one 30-tick feed round, so A's boundary is `140 + 30 * retries`), while in B it
must agree with the printed `[cont] gap_ticks` up to the per-arm teleport term
(50 ticks same-arm, 110 ticks on an arm switch). **Reported, never gated**: it is
the cross-arm continuity statement that the asymmetric census cannot make.
`A`'s expected values: 140 (no retry) / 170 (one retry) / 200 (two retries).

## 2.3 AMENDMENT A2 — **F4 fired on the letter, and the reference is stale** (2026-10-28, 14:04)

Recorded **after** the first P3 run and **before** the battery is resumed. The
battery was stopped exactly as F4 requires: P3 ran first, read **377** `[fruit]`
lines against the registered 376, so the batch was killed before any B run
(arm A seed 77 had ~5 picks when it was killed; its log is kept as
`logs/p58/p1/A_77_aborted_5picks.log`, not parsed).

**What the first P3 run measured.** `logs/p58/p3_accept.log` (10 attempts,
6/10, 150.5 s, `diverted=0`) reads

* the motion budgets: **all 9 descents and all 20 carry legs inside budget**
  (worst held-grip cone 1.53x reported, the `--strict-cone` report class);
* **`fingerprint: matches configs/motion_reference.json`** (`8a399626`), and
* a **rate-only** gate failure (`success 6/10 below 75%`), the documented
  `cnp`-class acceptance of this tree since P32.

**Why it is not 376.** `logs/p34/73_accept_no_harm.log` is a **pre-P41** record.
P41 shipped the finger-drive profile (`finger_damp02`, delivered pinch
4.42 -> 9.9 N) and **re-recorded both motion references because of it**; on this
tree the acceptance's first attempt closes at **23 ticks / 10.00 N** where the
p34 file has **25 ticks / 4.22 N**, and the finger-bound line carries the P41
provenance suffix. No post-P41 tree can reproduce the p34 file, so the
AGENTS/P41-P43 sentence "P35-P43 all reproduce that record" is **stale for this
tree** (it describes the pre-P41 lineage). The net +1 line vs p34 is the
state-conditional `[task] place low:` row (`tasks.py:12404` prints it when the
place descent binds the finger floor), which the p42/p53 records also carry.

**The same-tree evidence (the amended reference).** The fresh log's `[fruit]`
sequence is **byte-identical (377/377)** to

* `logs/p53/03b_accept_noharm_run.log` — the **most recent** no-harm acceptance
  on this tree (2026-10-28 02:10, md5 `eb6fbc5a`), 6/10, 150.5 s, same stats;
* `logs/p42/p2/control_accept.log` — P42's control (2026-10-26).

A tree-wide scan for an exact `[fruit]`-sequence match finds **exactly these two
files plus `logs/accept.log`** (which is the same P42/P53 content), i.e. the
scripted acceptance has been bit-stable on this tree since P42 and nothing in
P44-P57 moved it (every change in that span is a default-off knob).

**Amended P3 pass bar (used from here on).** `scripts/accept.sh` must read
**`fingerprint: matches`** and its `[fruit]` sequence must be **byte-identical to
`logs/p53/03b_accept_noharm_run.log` (377 lines)**. The p34 comparison is
**reported as a diagnostic** (count + the first differing line), never gated.
The rate line remains not-an-endpoint. The deviation and its evidence are
carried into `A_RESULTS.md`; no other registered rule changes, and F4's intent
("a shipped path moved") is met only if the **same-tree** record fails to
reproduce.

## 2.4 AMENDMENT A3 — the P3 comparator, verified (2026-10-28, 14:13)

A2's *diagnosis* is confirmed and its **comparator is superseded** by one that
is a same-tree record and is robust to the opt-in diagnostic rows. The phase is
told (orchestrator, verified here independently):

* comparator: **`logs/p41/p2/accept_profile.log`** (the acceptance P41 re-recorded
  when it shipped the finger-drive profile), filtered identically on both sides
  with `grep '[fruit]' | grep -vE "\[diag\]|\[carry\]|\[seat\]|\[attitude\]|\[pry\]|\[grip\]|\[release\]"`;
* the fresh log and the reference read **377 vs 377 lines, `diff` = 0** (both
  filtered sequences md5 **`8345af7f014e4f0bf75f7e6164532abf`**), with
  **`fingerprint: matches`** and **6/10** - the recorded branch;
* so **P3 PASSES**, and the battery is **not** stopped (F4's intent - "a shipped
  path moved" - is not met; the only F4 hit was the stale 376-line count).

**What actually makes 376 -> 377.** Two print-only facts, no physics: the P41
finger line gained the provenance suffix (`| finger drive profile=finger_damp02
k=100000 N/m c=2000 Ns/m maxForce=10.0/0.0N ...`) and the state-conditional
`[task] place low:` row (`tasks.py:12404`, printed when the place descent binds
the finger floor) appears in this branch; the physics difference against p34 is
the P41 profile itself (delivered pinch 4.42 -> 9.9 N), which is why P41
re-recorded the reference. The p53/p42 cross-checks of A2 remain true and are
reported beside it.

**Amended P3 pass bar (final, used in the report).** `fingerprint: matches`
**and** the filtered `[fruit]` sequence byte-identical to
`logs/p41/p2/accept_profile.log` (377/377). Reported beside it, not gated: the
unfiltered equality to `logs/p53/03b_accept_noharm_run.log` (377/377) and the
p34 count/diff diagnostic. The rate line remains not-an-endpoint.

## 3. Falsifiers (each stops the phase)
* **F1** P1 fails (either conjunct) → **nothing is adopted**, the stack stays
  default-off and the report says which conjunct failed and on which runs.
* **F2** any B run reports an inter-pick gap **> 200 ticks** → the stack is
  **not continuous** on that run; stop and report the mechanism (`window=0`
  rounds, `lag`, `on_belt`) instead of continuing to other endpoints.
* **F3** a new failure reason in **every** seed pair (i.e. the B − (A ∪
  baseline) key appears in all three B runs) → stop; that is a systematic new
  failure mode, not a branch.
* **F4** P3 fails (fingerprint mismatch **or** a different `[fruit]` line count
  or bytes) → **stop**: a shipped path moved, which voids the whole battery and
  is a `src/` regression to diagnose before any adoption question is asked.

## 4. Read rules carried into the report

1. **Branches, not rates.** Every placed count is one draw of a loop that is not
   reproducible (real rendered frames; AGENTS §3b). Quote them as counts with
   the per-arm split, never as a rate delta between the arms.
2. **The instrument is inside the contrast.** `FRUIT_BED_DIAG=1` is set in both
   arms. It is print-only (it reads the selection census that the selector has
   already built), but it is not free of wall and it is the same in both arms.
3. **The left arm's ceiling is the closed grip class** (P42 `SIM_LIMIT.md`): a
   left-arm placed count of 0-2 is the documented `cnp`/loaded-slide class, not a
   supply effect, and must be read that way.
4. **Continuity is not throughput.** P1 says the belt has a catchable candidate
   at every selection; it says nothing about the pick taking less time. The
   owner explicitly accepts slowness that comes from the fruit not being there;
   P5 reports the wall so the trade is visible, and P1 alone decides the
   adoption question.
5. **The scenario is the P43/P54 one.** Any comparison to a P35-P43 number is a
   comparison to a pre-P58 tree only if the tree pins match; the pins are in §1.4
   and in the header file, and the only `src/` difference from P57's close is
   none (this phase runs P57's tree unchanged).

## 5. The decision (for Oracle 1, not for this file)

Adopt = F1-F4 all pass and P1 passes. Then the three direct-line defaults flip
(`FRUIT_FEED_CADENCE`, `FRUIT_SUPPLY_BAND_INTERLOCK` + `_BAND_MAX`,
`FRUIT_DIRECT_CONTINUOUS`/`FEED` resolution for the direct presentation), the
re-baseline rule is recorded (every pre-P58 direct number is a control number),
and the two references are re-checked (P3 already pins the scripted one; the
two-line gate is `scripts/190_twoline_gate.sh` on a two-line log, which this
phase does not produce). **No default is flipped in this phase** - the phase's
deliverable is the measurement and its verdict.
