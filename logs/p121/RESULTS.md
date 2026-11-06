# P121 - RESULTS: the direct/policy line decides its destination

## 0. Verdict

**The direct/policy environment now uses `FRUIT_SORT_INSTRUCTION`: default off,
the unset path is the shipped grade lane, and an instructed run decides the
destination in selection, the arm, the goal channel and the place leg, and
reports it in P114's `[sort]` ledger.** On the shipped two lanes the assignment
is exact (T1 18/18, T1b 22/22, T2 20/20 released in destination, **0
mis-sorts**): an instruction that restates today's routing reproduces the direct
control's destination table (A -> left, B/C -> right), and a non-grade rule sends
a grade-B/C fruit to the **left** lane (11 decisions, 7 placed) - a destination
today's `grade=A else 1` rule can never produce. The **third destination** is
reachable and correctly commanded (`reach 6.0 mm`, leg `place2`, target
`(0.38,+0.55)`, `8 of 9` releases attributed to dest 2), but **one of its nine
releases landed nearer lane 0** at `(0.45,+0.53)` - a 70 mm release scatter
against a **71 mm** destination separation - so the strict "zero mis-sort"
clause fails at **1/23**. That is recorded as **reachable but not separable at
this spacing**, not as a wiring failure. No rate is claimed: the direct loop is
not reproducible, and every count below is one branch draw.

## 1. What the env does with an instruction

Read `logs/p121/METHOD.md` for the full site table. In one paragraph:
`direct_dispatch` replaces `bin_index = 0 if grade == "A" else 1` /
`active = "left" if bin_index == 0 else "right"`. When armed it reads the
fruit's `task.sort_destination` and the capability map's
`task.arm_for_destination`; the selector (`tasks.select_target`'s `_sort_admits`
branch) already refuses `skip`/unmatched fruit, so the policy is never handed a
fruit the instruction does not assign. The goal keeps `[xyz, velocity, diameter,
bin_index]` - destination 0/1 produce the same values the shipped lane did, so
the trained input is unchanged; destination 2 writes `2.0`, the declared OOD
value. `_run_primitive` sets `task.dispatch_destination` (the thread-local
`place_xy` override `_place_xy_for` reads), clears it in a `finally`, and calls
`task.sort_ledger_attempt`; the place leg is named `place<destination>`; the
ledger row and the per-destination table are the same code the scripted `run()`
uses, with `in_dest` measured from the payload's release position. The action
interface is untouched: 7 joint targets + 1 finger, **no destination channel**.
The reseed retry and the presented-fruit adoption check the capability **arm**
instead of the grade lane. A destination beyond the two shipped lanes raises at
construction unless `FRUIT_SORT_THIRD_DEST=1`; an unreachable destination is
refused by P114's capability map. The handoff presentation still refuses the
instruction (it has no dispatcher).

## 2. Cells (3 seeds 77/101/202 x 10 episodes, shipped direct config)

| cell | instruction | placed | grasped | classes |
| --- | --- | --- | --- | --- |
| C | unset | 19/30 | 25/30 | cnp 6, fell_off 2, never_held 3 |
| T1 | `today.txt` (A=>0, B=>1, C=>skip) | 18/30 | 27/30 | cnp 9, never_held 3 |
| T1b | `grade=A => 0; default => 1` (today's direct routing) | 22/30 | 28/30 | cnp 6, fell_off 1, never_held 1 |
| T2 | `size<40 => 1; default => 0` | 20/30 | 27/30 | cnp 7, fell_off 1, never_held 2 |
| T3 | `three_dest.txt` (A=>2, B=>1) + scenario + `FRUIT_SORT_THIRD_DEST=1` | 23/30 | 25/30 | cnp 2, never_held 5 |

Counts are **report only** (a branch draw, P37/P43/P54). The failure classes are
the recorded set - `cnp` (the closed loaded slide), `never_held` (the
acquisition class, including P74's `fruit left the pick station during the
close`), `fell_off` - and **no new reason key** appears in any cell. T1 and
T1b route more fruit to the left arm than C (C's non-A fruit went right; T1
skips grade C, T1b keeps it), which is the known arm-mix effect, not a lever.
The same-seed pre-P121 P77 controls read 32/45 = 71 % (11/15, 7/15, 14/15); C
reads 19/30 = 63 % - both are branches of the same non-reproducible loop, so
this is not a rate comparison.

## 3. The ledger (the endpoint)

| cell | attempts | released | in_dest | mis_sorted | not_placed | assignment |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | 30 | 18 | 18 | 0 | 12 | **18/18 = 100 %** |
| T1b | 29 | 22 | 22 | 0 | 7 | **22/22 = 100 %** |
| T2 | 29 | 20 | 20 | 0 | 9 | **20/20 = 100 %** |
| T3 | 30 | 23 | 22 | 1 | 7 | 22/23 = 95.7 % |

Per destination (attempts / released / in_dest):

| cell | dest 0 | dest 1 | dest 2 |
| --- | --- | --- | --- |
| T1 | 16 / 6 / 6 | 14 / 12 / 12 | - |
| T1b | 13 / 7 / 7 | 16 / 15 / 15 | - |
| T2 | 21 / 13 / 13 | 8 / 7 / 7 | - |
| T3 | - | 16 / 14 / 14 | 14 / 9 / 8 (**1 mis-sorted**) |

The un-instructed control printed **zero** `[sort]`/`[scenario]` rows, so the
unset path is untouched (`logs/p121/direct/C.log`; the `p121_report.py --check`
fails any `[sort]` row in C).

T1b is the clean same-destination reproduction: its attempt table is exactly
`grade=A -> dest 0` (13), `grade=B -> dest 1` (8), `grade=C -> dest 1` (8) -
the same rule the un-instructed env runs. T1 differs by design: P114's
`today.txt` skips grade C (the *scripted two-line's* pure routing), so C is
never selected there (`coverage ... skip=4`).

## 4. Non-grade routing (T2)

`[sort] coverage: pool=16 mapped=16 unassigned=0 skip=0 (dest0=13, dest1=3)`;
the attempt rows contain **7 grade-B and 4 grade-C decisions on dest 0 (left)**
and 6 B / 2 C on dest 1. The shipped rule sends every non-A fruit to the right,
so the left is a destination the grade rule can never produce. The witnesses in
the log: a grade-C kiwi (6.3 cm) placed on dest 0, and a 3.6 cm grade-B
strawberry placed on dest 1.

**Pre-registration correction (P3):** P3 was written as a two-witness
conjunction - a grade-A fruit on dest 1 *and* a grade-B/C fruit on dest 0. The
measured pool drew **no grade-A small fruit**, so P3a is **not evaluable** on
this draw; the discriminating direction (B/C on the left, the one the grade
rule cannot produce) fired with 11 decisions / 7 released in destination. The
report's `--check` accepts the union and prints both counts; this is the
recorded correction, not a re-definition of the endpoint.

## 5. The third destination (T3, OOD)

The startup solve reproduces P114's scripted cell: `[sort] reach arm=left
dest=2 (lane0_upstream_zone) target=(0.38,+0.55) residual=6.0mm tol=25mm ->
reachable`, capability `left=[0,2] right=[1]`, leg `place2`, coverage
`dest1=6 dest2=6` (grade C unassigned, never selected; `pool unassigned=4`).
**23/30 placed**; of the 9 dest-2 releases, 8 read `nearest=2` at 52-64 mm and
**1 reads `nearest=0` at 34 mm**: attempt 13's orange was commanded to
`(0.38,+0.55)` and released at `(0.45,+0.53)`.

The mechanism is the release cloud, not the command: the two targets are
**71 mm apart** and the direct line's release scatter on this leg is
**40-70 mm** (the other eight dest-2 releases sit at `(0.41-0.42, +0.59-0.60)`,
i.e. +40..+50 mm off target). **The third destination is therefore a separation
limit, not an env limit**: the ledger, capability map, leg name and commanded
target all name dest 2; the payload landed outside its zone. Named next: widen
the separation (or give dest 2 its own side/height), or apply P50's
release-offset compensation - it is P50's object, not a new dispatcher. The
`bin_index=2.0` goal value is an OOD input and is declared as such; T3's 23/30
is **not** a rate.

## 6. Guards and no-harm

* `scripts/accept.sh` (scripted, `SKIP_SELFCHECK=1`): **8/10 = 80 %,
  `fingerprint: matches configs/motion_reference.json`, `190: PASS`**, and the
  acceptance's **421 `[fruit]` lines are byte-identical (421/421)** to
  `logs/p110/accept_noharm.log` (and to the P114/P117 records). The scripted
  path never reads `direct_dispatch`, and the stream proves it.
* `scripts/selfcheck.sh`: **PASS (0 failures, 1 skipped)** with the new
  `263` leg (31 checks: the dispatch table, the OOD gate, the capability map
  incl. the unreachable tray, the goal channel, `_run_primitive`'s place
  target/cleanup/ledger, the 7+1 action, the reseed arm check, the manifest
  block, `TASKS_MD5`).
* `python3 scripts/106_index_audit.py`: **OK** (every index matches its files).
  `python3 scripts/107_collect_merge_test.py`: **PASS (21 checks)**.
* The third-destination refusal cell raises **before the first attempt**:
  `ValueError: [sort] REFUSED: ... destination(s) [2] ... Set
  FRUIT_SORT_THIRD_DEST=1` (`logs/p121/refuse_third_off.log`; P114's
  unreachable-tray refusal is pinned by the `263` leg).
* No motion budget is re-tuned; `configs/` is untouched (the P114 scenario file
  `logs/p114/scenarios/three_dest.json` is reused, no new file).
* The direct cells' motion budgets were not re-read/gated (the P121 change moves
  no motion profile); the loss classes are the recorded ones.

## 7. Pins and evidence

`tasks.py` **`78cce1ef`**, `rl_env.py` **`91e0a4ad`**, `scenario.py`
`662369aa`, `assets.py` `165328af`, `fruits.py` `e807216c`, `scene.py`
`a0199097`, `control.py` `9384ff4f`, `conveyor.py` `fb2c58c6`;
`scripts/263_p121_env_sort_selftest.py` **`ce290037`**, `scripts/selfcheck.sh`
**`c071242f`**, `scripts/259_p114_scenario_selftest.py` updated for the new
scope; references **`30fb99f8` / `30fb99f8` / `8952c320`** untouched; ckpt
`moe_v13s` `61da390a`; `logs/p121/PREREG.md` **`c22e40fc`**,
`logs/p121/p121_report.py` **`826ff730`**.

**Close-out note (measured tree vs final tree).** The five cells ran on
`rl_env.py` `dcbd2846` and the `263` leg `b8b63d39`; after the cells, one
direct-only bookkeeping path was synced - the env adopts
`result.destination` when the task's station reselect re-dispatches an attempt
mid-call (reachable on the shipped non-dynamic direct config; the measured cells
run `FRUIT_DYNAMIC_PICK=1`, so none entered it). The final tree is `91e0a4ad` /
`ce290037`; the final acceptance and selfcheck below are on it, and the direct
firmware/behaviour of the measured cells is unchanged (no direct cell was
re-run, and no cell's ledger outcome can move from a post-call bookkeeping
sync).

Evidence: `logs/p121/{METHOD.md,PREREG.md,PREREG.md5,RESULTS.md,header.txt,
p121_report.py,p121_report.txt,one_run.sh,run_p121.sh,run_p121_t1b.sh,
batch_driver.log,t1b_driver.log}`, the cells `direct/{C,T1,T1b,T2,T3}.log`,
`smoke_today.log`, `refuse_third_off.log` + `refuse_third_off.traceback.txt`,
`accept_final.log` + `accept_final.driver`, `selfcheck.log`.
