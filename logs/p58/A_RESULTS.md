# P58 phase 1 (A) — the continuous-supply stack: the adoption A/B

Measured **2026-10-28** on HEAD `96849c6` (the P57 tree, `tasks.py` `c7eef701`,
`fruits.py` `55921c46`, `rl_env.py` `ddcb7816`), one battery, one simulator, six
runs, wall **3116 s** (`logs/p58/batch_outer.log`). No `src/`, `configs/`,
`datasets/` or checkpoint write; no default flipped; no commit. Registered in
`logs/p58/PREREG.md` **before** the first run (+ amendments A1/A2/A3, each
written before the run it governs). Report: `logs/p58/p1_report.txt`
(`python3 logs/p58/p1_report.py --dir logs/p58/p1`), raw logs
`logs/p58/p1/{A,B}_{77,101,202}.log`.

---

## 0. Verdict

**P1 PASS — the registered adoption gate clears on all four falsifiers.**
Arm B (the stack) reads **`window >= 1` at 45/45 selections = 100 %** (bar 95 %)
and a **longest inter-pick gap of 80 ticks in every run** (bar 140); no new
failure reason (P2 PASS); the scripted no-harm reproduces the P41 record
**377/377 with `fingerprint: matches`** (P3 PASS); no B gap anywhere near the
200-tick F2 line. **The adoption decision (flip `FRUIT_FEED_CADENCE`,
`FRUIT_SUPPLY_BAND_INTERLOCK`/`_BAND_MAX`, and the direct-line
`FRUIT_DIRECT_CONTINUOUS`/`FEED` resolution) therefore goes to Oracle 1**, with
the re-baseline rule that every pre-P58 direct number is a control number.

**The one thing to read before the verdict is used: P1 does not separate the
arms on this scenario.** The **control also passes both conjuncts** - A reads
45/45 = 100 % and exactly **140** ticks (which is `<= 140`). The bar was
registered as the owner's *absolute* requirement, and on the shipped
per-episode line that requirement is already met: its reset prints only its
successful selection and its own feed rounds (up to 40 x 30 ticks) always found
a candidate here - zero retries, so `window=0` never occurs in A (0/45) and the
per-episode boundary stays at 140 ticks
(the P56 census, re-measured here at 139-141 on 42/42 boundaries by the
selection clock, amendment A1.2). **What the battery measures between the arms
is therefore the mechanism, not a pass/fail delta**: stock depth **5 -> 10**
bodies, scheduler skips **105 -> 38**, boundary **140 -> 50/80** ticks. The
P56-era "80 % / 8-of-14 starved" figures are **not** this control's baseline: the
8-of-14 starvation was P56's *continuous* arm (which removes the reset's feed
round) measured **without** the cadence pump, and the 80 % was `window>=2` on a
per-round census that counted retries as selections. Neither number describes
today's A, which is 45/45 with zero retries.

| endpoint | verdict | the number |
| --- | --- | --- |
| **P1** pickable-band stock (primary) | **PASS** | B `window>=1` **45/45 = 100.0 %** (bar >= 95 %); B longest gap **80/80/80** ticks on seeds 77/101/202 (bar <= 140); A same numbers **45/45 = 100 %**, **140** (by construction, confirmed 139-141) |
| **P2** no new failure reason | **PASS** | B keys ⊆ A ∪ the P43/P54 baseline; the only B-only note (`fruit left the pick station during the close`) is a baseline key; per-seed novelty **none/none/none** |
| **P3** scripted no-harm | **PASS** | `fingerprint: matches` (`8a399626`), `[fruit]` filtered **377/377 identical** to `logs/p41/p2/accept_profile.log` (md5 `8345af7f` both sides); 6/10 = the recorded `cnp` branch, gate exit=1 is **rate-only** |
| **P4** placed count | **reported** | A **33/45** (left 1/12, right 32/33) vs B **30/45** (left 3/16, right 27/29) - different branches, **no rate claim** |
| **P5** wall per pick | **reported** | A **29.66 s/pick** (1334 s / 45) vs B **34.37 s/pick** (1547 s / 45) = **+15.9 %**, of which the simulated span is **+1.1 %** |
| F1 P1 fails | does not fire | |
| F2 a B gap > 200 ticks | does not fire | worst B boundary by the selection clock, including the reset's first transition, is **111** ticks |
| F3 a new reason in every pair | does not fire | none in any pair |
| F4 P3 fails | does not fire (after A3) | the first P3 read **did** fire F4 on the letter - see §4 |

## 1. The arms and the protocol (as registered)

Both arms: `checkpoints/moe_v13s/policy_best.pt` (`61da390a`), the W6-A/W8-A
patch sheet (`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`, balanced A:B:C
0.375/0.375/0.25), `FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1`, camera 240x424, one
claim per run, seeds **77/101/202 interleaved A-then-B**, 15 picks per run
(A: `--episodes 15`; B: `--episodes 1` + `FRUIT_DIRECT_CONTINUOUS=15`).

* `FRUIT_POLICY_TRIGGER_ACQ` **unset** -> resolves **on** (P54 default for
  `direct`); every log prints `acq=on(...)`, so both arms are post-P54.
* `FRUIT_ARM_PARK` **unset** -> resolves **`back`** (P43 default); every log
  prints `park=back(default)`.
* Arm B adds `FRUIT_DIRECT_CONTINUOUS=15 FRUIT_DIRECT_FEED=1
  FRUIT_FEED_CADENCE=1 FRUIT_SUPPLY_BAND_INTERLOCK=1 FRUIT_SUPPLY_BAND_MAX=3`.

All six runs exited 0 with **15 picks** each (90 picks total, 45 per arm); no
wedge, no retry. Tree pins identical before and after the batch
(`logs/p58/p1/P1_tree_md5_after.txt`).

## 2. The table

Unit = one pick = one `[rl] episode ... success=` row. `placed` == `success` on
every row (0 exceptions in 90).

| arm | seed | picks | placed (left/right) | `window>=1` | longest gap | wall | s/pick |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 77 | 15 | **12** (0/2, 12/13) | 15/15 | 140 | 453.1 s | 30.2 |
| A | 101 | 15 | **11** (1/5, 10/10) | 15/15 | 140 | 445.9 s | 29.7 |
| A | 202 | 15 | **10** (0/5, 10/10) | 15/15 | 140 | 435.5 s | 29.0 |
| **A pooled** | | **45** | **33** (1/12, 32/33) | **45/45 = 100 %** | **140** (by construction) | 1334 s | **29.7** |
| B | 77 | 15 | **10** (1/5, 9/10) | 15/15 | **80** | 503.2 s | 33.5 |
| B | 101 | 15 | **9** (1/7, 8/8) | 15/15 | **80** | 516.0 s | 34.4 |
| B | 202 | 15 | **11** (1/4, 10/11) | 15/15 | **80** | 527.5 s | 35.2 |
| **B pooled** | | **45** | **30** (3/16, 27/29) | **45/45 = 100 %** | **80** | 1547 s | **34.4** |

Gaps: B's 42 boundaries are **all 50 or 80** ticks (25 x 50, 17 x 80; zero 110,
zero waits, zero empty selections). A's 42 boundaries measured **139-141** by
the selection clock (median 140, `>200` = 0).

B accounting (`[cont]`): `picks=15/15` and `ticks_total == sum(per-pick ticks)`
exactly in 3/3 runs (27 485 / 27 889 / 27 725); `reward_total` equals the
per-pick sum to **1e-4** (the per-pick rows are printed to 4 dp). Three distinct
15-pick stores' worth of episode indices, one logical episode per run.

## 3. The mechanism

**Stock (the owner's intent).** `on_belt` at the selection instant: A **median 5**
(3-9) vs B **median 10** (4-12) - the belt under the stack carries about
**twice** the stock on the same pool and the same patch sheet. The *usable*
distribution moves with it: A `window` = {1: 4, 2: 20, 3: 11, 4: 10}; B {1: 10,
2: 21, 3: 14} - B never has fewer than 1 and never more than 3, i.e. the
interlock's `_BAND_MAX=3` shows up where it should.

**The band interlock moves stock out of the unusable window.** `admitted` (the
station window below the catch floor) reads A **median 5** (3-8) vs B **median 4**
(3-6): B holds *more* fruit overall and *fewer* of them in the segment the catch
can no longer reach, which is exactly the P57 inversion it was built for.

**The scheduler is current.** Final cumulative `supply_skipped`: A
**104 / 105 / 107** vs B **40 / 38 / 36** (-63 %): without the mid-attempt pump
the release clock falls behind during the primitive phase and the late backlog is
skipped; with it, 36-40 slots are skipped over 15 picks instead of ~105.
`bed_rebased` and `late_dropped` are **0 in both arms** - no backlog was rebased
and nothing was dropped late, so the difference is the clock, not a re-basing
artefact. The pump's own row (`[feed]`, seed 77) reads
`updates=309-347 ticks=1238-1390 stride=4` per pick, i.e. it services
**~68-76 % of a pick's ticks** at stride 4 (a pick is ~1 830 ticks).

**The boundary.** 140 ticks (the per-episode reset: 30 feed + 3x30 teleport +
20 settle) -> **50 (same arm) / 80 (arm switch)** on every one of B's 42
boundaries. The selection-clock cross-check (amendment A1.2) reads B's first
transition at 110/111 ticks (it includes the reset's own feed round) and the
other 13 per run at the printed value +-1 tick, so **B's worst boundary is 111
ticks, 29 under A's 140**.

**Wall (P5).** B costs **+15.9 % wall per pick** (29.66 -> 34.37 s) while its
simulated span is only **+1.1 %** (82 193 -> 83 099 ticks over 45 picks = 1 827
-> 1 847 ticks/pick). So the cost is **per-tick compute** in the pump (Python,
stride 4), not more simulated work - consistent with P55's +11.1 % for the direct
feeder alone and P33's +20 % for the two-line pump. P3 in this battery is
unaffected (the scripted line never arms the cadence knob).

**Failure classes (P2, and the reason P4 is a branch statement).** Failures: A
**12/45** (1 no-grasp + 11 grasped-not-placed), B **15/45** (3 no-grasp + 12
grasped-not-placed). Named notes: A 1x `fruit did not follow the gripper`; B 2x
`fruit did not follow the gripper` + 1x `fruit left the pick station during the
close` (a P43/P54 baseline key). No new key in any seed pair. The left arm's
1/12 (A) and 3/16 (B) are the closed grip/`cnp` class (`logs/p42/SIM_LIMIT.md`),
not a supply effect. The right arm - the one the belt feeds - reads A **32/33 =
97.0 %**, B **27/29 = 93.1 %**: B took **4 fewer right attempts** (29 vs 33,
because the left took 16 vs 12), which is the arm mix, not a per-arm drop.

## 4. Deviations and the F4 stop (recorded)

1. **F4 fired on the letter at the first P3.** P3 ran first (cheap, and it voids
   the battery if it fails). It read **377** `[fruit]` lines against the
   registered **376** (`logs/p34/73_accept_no_harm.log`), so per F4 the battery
   was **stopped before any B run** (A seed 77 was killed at ~5 picks; its log is
   `logs/p58/p1/A_77_aborted_5picks.log`, not parsed).
2. **Diagnosis (PREREG A2, corroborated by the orchestrator and re-verified
   here).** The p34 file is **pre-P41**: P41 shipped the finger-drive profile,
   moved the acceptance's physics (close 25 ticks / 4.22 N -> 23 ticks /
   10.00 N) and **re-recorded the reference**. No post-P41 tree can reproduce
   p34. The count difference is print-only: the P41 provenance suffix on the
   finger line and the state-conditional `[task] place low:` row.
3. **Correct comparator (PREREG A3).** `logs/p41/p2/accept_profile.log`, both
   sides filtered with `grep '[fruit]' | grep -vE "\[diag\]|\[carry\]|\[seat\]|\
   [attitude]|\[pry\]|\[grip\]|\[release]"`: **377 vs 377, `diff` = 0**, both
   sequences md5 **`8345af7f014e4f0bf75f7e6164532abf`**. Cross-check (unfiltered):
   `logs/p53/03b_accept_noharm_run.log` **377/377 identical**. The battery was
   then re-run whole (all six runs), so no run in this report is from the aborted
   attempt.
4. **A1** recorded the instrument asymmetry before the run: A prints one
   `[bed-sel]` per *successful* selection, B also prints empty rounds - so A's
   share is an upper bound. **On this battery it is moot**: neither arm printed a
   `pick=none` row and neither had a starved reset, so both shares are 45/45.

## 5. What this does not show

* **No throughput claim, in either direction.** 33 vs 30 placed is two branches
  of a loop that is not reproducible (real rendered frames), the per-arm split
  shows the difference is the arm mix and not the right arm's rate, and the
  registered P4 is "reported only". Nothing here says the stack sorts faster; the
  wall says it costs 15.9 % more per pick.
* **P1's share bar does not separate the arms.** The shipped per-episode line is
  already never starved at the selection instant on this scenario (45/45). What
  separates is the stock depth (`on_belt` 5 -> 10), the scheduler's skipped slots
  (105 -> 38) and the boundary (140 -> 50/80). A future registration that wants
  P1 to *discriminate* must use one of those, or a starvation-prone scenario (the
  continuous mode without the cadence, which is what P56/P57 measured).
* **No attribution inside the stack.** Cadence, band interlock, direct feeder and
  multi-pick episode are one unit here by design (the adoption test of the stack
  as shipped). A failure of one member would not be separable from this battery;
  a pass does not say which member bought the stock.
* **The catchable segment is unchanged.** `spawn_y - (pick_y + floor) = 0.281 m`
  (P57). The stack keeps 2-3 bodies inside it; it does **not** make it longer.
  The geometry question is phase 1(B) (`logs/p58/GEOMETRY.md`), not this report.
* **Scenarios not covered:** the hybrid canary (`60_eval_policy.py`, `moe_v12` -
  it never constructs `SortingRLEnv`, so the stack has no path there), the
  two-line scheduler (`CoopSession` installs its own pump; the cadence knob is
  single-arm scoped), the scripted line with the knobs explicitly set (not run),
  and any *store* collected under the stack (no `--record`). The park/ACQ
  defaults sit **inside both arms**, so this is the post-P43/P54 interface.
* **The left arm** (3/16 in B) is the closed grip class; nothing here is evidence
  about the left arm's rate, and a left-heavy scenario would move the pooled
  counts without touching the mechanism.

## 6. Files

`logs/p58/PREREG.md` (+A1/A2/A3), `logs/p58/run_batch.sh`,
`logs/p58/p1_report.py`, `logs/p58/p1_report.txt`, `logs/p58/p1/{A,B}_{seed}.log`,
`logs/p58/p1/P1_header.txt`, `logs/p58/p1/P1_tree_md5_after.txt`,
`logs/p58/p1/A_77_aborted_5picks.log`, `logs/p58/p3_accept.log`,
`logs/p58/p3_accept_outer.log`, `logs/p58/p3_accept_first_f4.log` (the F4 run),
`logs/p58/batch_outer.log`. **Nothing was flipped, committed or re-recorded.**
