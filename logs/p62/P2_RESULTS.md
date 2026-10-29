# P62 phase 2 — the T0 left grasp attitude: **the knob is built and the registered falsifier F3 fired — the direct line already commands T0, so the 3 × 15 cell was not run**

Written 2026-10-29 on HEAD `21690c3` + this phase's uncommitted edit. **No shipped
default changed** (the knob is default **off**), **no `configs/` byte moved**, **no
commit**, no motion reference re-recorded.

## Verdict

* **The lever is structurally already shipped on the direct line.** The armed
  override is the attitude the run *already* commands: `configs/waypoints.json`'s
  left `grasp_quaternion` **is T0** (`[w,x,y,z] = (+0, −0.707107, +0.707107, +0)`,
  tool axis `(0,0,−1)`, belt projection **0.000**), and the never-stop catch's own
  installed hold (`mirror_across_xz(top_down_quaternion("x"))`, `tasks._run_impl`)
  is that **same value bit-for-bit**. The armed run's own `[grasp]` row says so in
  one line: `file_same=1 hold_same=1`.
* **Measured, not argued — twice.** Gate **P0/P0b** (registered in
  `logs/p62/PREREG_P2.md` §3 *before* the runs) reads the achieved attitude per
  arm, on two independent seeds (the second on the final tree): the left's
  `grasp_lift` belt projection moves **+0.3554 → +0.3536 = −0.0018** (seed 77) and
  **+0.3210 → +0.3211 = +0.0001** (seed 101) against the registered **0.05**
  gate — **28×** and **500×** below it — while the **untouched right arm** moves
  **+0.0675** / **−0.0174**, i.e. **37× / 174× more** than the treatment's own
  delta. The gate's threshold sits inside the loop's own run-to-run spread.
* **So F3 fires** ("E1 fails → the attitude did not change the mechanism; stop and
  report") and **the 3 × 15 cell was not spent**. With the treatment equal to the
  control, every E2–E5 count difference would have been branch noise of a
  non-reproducible loop (`AGENTS.md` §3b), and each pair draws the **same fruit
  sequence on the same arms with the same outcomes** in both arms (§2).
* **Nothing here says T0 is wrong or that an attitude change cannot move the
  class.** T0 *is* the shipped command; what the measurement exposes is the
  **achieved-vs-commanded gap** (§5) and that the override channel the brief
  specified cannot reach it.
* **The scripted line is byte-identical by construction, proven**: 377/377
  `[fruit]` rows identical to `logs/p41/p2/accept_profile.log`,
  `fingerprint: matches` (§6).

## 1. What was built (default off, `None` = shipped)

| where | what |
|---|---|
| `tasks.py` (`fe11910a`) | `PickAndPlaceTask.__init__(..., grasp_quat_override: dict | None = None)`; `_grasp_quat(side)` returns that arm's entry when present, else the file. The caller-owned-kwarg pattern of `feed_cadence` (`None` = the shipped env read) — no `os.environ` write, no file edit |
| `rl_env.py` (`921972a3`) | `GRASP_LEFT_TOPDOWN` + `resolve_grasp_quat_override(presentation, env_value)`: `FRUIT_GRASP_LEFT_TOPDOWN=1` **and** `presentation == "direct"` → `{"left": T0}`, everything else `None`. Passed as `grasp_quat_override=` at the single construction site. The armed run prints one `[grasp] left attitude override:` row naming the override, the file's value and the hold the catch installs |
| `scripts/232_p62_grasp_selftest.py` (`e1f86725`) | new selfcheck leg (`PASS: P62 grasp attitude override`, 36 checks incl. the four the brief named) |
| `scripts/selfcheck.sh` (`f97b928d`) | the leg registered |

The selftest executes the **real** `_grasp_quat` body (extracted with `ast`, so no
`pxr`/Isaac import) to prove the contract rather than the source text: an empty
override returns the file's left/right value **exactly** (`array_equal`), the
overridden arm returns the override and the **other arm still returns the file**,
an override wins even with no file entry, an arm with neither is still `None`, and
the returned array is a **copy** (a caller cannot corrupt the override). It also
pins that the env var is read in exactly one place, the env is never written,
`rl_env` has exactly one `grasp_quat_override=` site, `scripts/20_pick_place.py`
never constructs `SortingRLEnv`, `configs/waypoints_oriented.json` is
`0ea08ebb`, and `TASKS_MD5` follows the shipped `tasks.py`.

`scripts/selfcheck.sh` → **PASS, 0 failures** (the new leg included,
`failed=0 skipped=1`).

## 2. Gate P0 / P0b — the two arm pairs (`logs/p62/p2/P0{A,B}.log` seed 77, `P0b{A,B}.log` seed 101)

Scenario and harness: the cell's own environment (`FRUIT_SUPPLY_SCATTER=1
FRUIT_SUPPLY_PATCH=1`, balanced mix, `arrival` trigger lead 0.9,
`FRUIT_DYNAMIC_PICK=1`, policy seed 11, `FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1
FRUIT_ACQ_DIAG=1`) plus `FRUIT_CARRY_ATTITUDE=1` (P39's reporting-only read: one
TCP-pose read per carry leg) and the P61 harness env
(`HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1`). **A**
= control (knob unset), **B** = `FRUIT_GRASP_LEFT_TOPDOWN=1`; one claim per run,
`--episodes 2`, both exit 0 in both pairs, **no wedge** (F1 unused), drivers
`logs/p62/p2/run_p0.sh` + `run_p0b.sh`, headers `p0_header.txt` / `p0b_header.txt`
(carrying every pin). **P0** ran on the measured tree (`tasks.py` `e5bc98a9` /
`rl_env.py` `97d86460`); **P0b** ran on the **final** tree (`fe11910a` /
`921972a3`), whose only delta from the measured one is the two comment blocks and
the `TASKS_MD5` string (§7).

**Pair P0 (seed 77):**

| read | A (control) | B (T0 armed) |
|---|---|---|
| episodes | 2, **1/2 placed** | 2, **1/2 placed** |
| the two picks | ep0 pear/left **cnp**, ep1 lychee/right placed | **identical** (same fruit, same arm, same outcome) |
| `[grasp]` override row | **absent** (knob off) | **present**, `file_same=1 hold_same=1` |
| left `grasp_lift` tool axis | `(+0.3217, −0.3554, −0.8776)` | `(+0.3239, −0.3536, −0.8775)` |
| **left `grasp_lift` belt projection** | **+0.3554** | **+0.3536** → **Δ −0.0018** |
| left `grasp_lift` tilt | 28.6° | 28.7° |
| left `grasp_lift` slip | 101.2 mm, `(−75.0, +0.7, +67.9)`, tool share **+0.671** | 102.8 mm, `(−75.0, +15.9, +68.5)`, tool share **+0.666** |
| right `grasp_lift` belt projection (**untouched arm**) | −0.0689 | −0.0014 → **Δ +0.0675** |

**Pair P0b (seed 101, final tree, an independent draw):**

| read | A (control) | B (T0 armed) |
|---|---|---|
| episodes | 2, **1/2 placed** | 2, **1/2 placed** |
| the two picks | ep0 apple/left **cnp**, ep1 orange/right placed | **identical** |
| **left `grasp_lift` belt projection** | **+0.3210** | **+0.3211** → **Δ +0.0001** |
| left `grasp_lift` tilt | 26.3° | 26.3° |
| left `grasp_lift` slip | 23.0 mm, tool share **+1.000** | 21.6 mm, tool share **+0.998** |
| right `grasp_lift` belt projection (**untouched arm**) | −0.2776 | −0.2950 → **Δ −0.0174** |

The registered gate is `|Δ| >= 0.05` for the left. It **fails by 28× and 500×**
(`0.0018`, `0.0001`), and the *untouched* arm's own spread (`0.0675`, `0.0174`) is
**larger than the gate in one pair and 174× the treated delta in the other**, so
the threshold cannot even separate the treatment from the loop's noise. The
mechanism row agrees independently: the left's escape still walks out along the
tool axis (share **0.666–0.671** at seed 77 against P61's 0.905, n = 14; **0.998–1.000**
on the seed-101 apple, whose slip is only 22 mm, i.e. below the 50 mm escape
threshold), and the **achieved tilt is a property of the branch, not of the knob**
(28.6/28.7° at seed 77, 26.3/26.3° at seed 101).

Post-run tree md5s: `logs/p62/p2/tree_md5_before_accept.txt` and
`_after_accept.txt` are identical.

## 3. E1–E5, endpoint by endpoint (registered in `logs/p62/PREREG_P2.md` §2)

| id | status | why |
|---|---|---|
| **E1** (mechanism: left slip's tool-axis \|belt projection\| ≤ 0.10) | **not evaluable** | there is no attitude change to attribute it to: the command is identical (`file_same=1 hold_same=1`) and the achieved projection moved 0.0018 / 0.0001 in the two pairs — the *treatment does not exist*. The endpoint itself reads 0.666–0.671 at seed 77 (P61: 0.905, n = 14) and 0.998–1.000 on a 22 mm sub-threshold slip at seed 101, which is an anecdote, not a delta |
| **E2** (left cnp ≤ 12/18 vs P61's 16/18) | **not measured** | needs the 3 × 15 cell; not run (F3). The P0/P0b left attempts cnp'd in **both** arms in both pairs (pear, apple) |
| **E3** (left never-held, the +x cliff) | **not measured** | same; no arm in either pair produced a never-held leg (2 attempts per arm) |
| **E4** (right does not move) | **not measured as a cell**; the scoping is proven *structurally* | the knob returns `None` on every presentation but `direct` and names only `{"left": …}` (pinned by `232`), and the `[grasp]` row's `right=file` field prints the right arm's unchanged attitude. What the pairs *do* show is that the right arm moves by **0.0675** / **0.0174** with **no** knob acting on it, i.e. an arm-level 2-episode delta is not a measurement on this loop |
| **E5** (no new reason; ACQ margin; j3 risk) | **not measured as a cell** | P0's only notes are the shipped `intercept trigger (...)` rows on both arms; the j3 +0.007 rad risk of `CANDIDATES.md` §5.1 was not exercised at scale |

F1 (wedge → retry once): **not used**. F2 (the `[grasp]` row must name the
override): **PASS** — printed only in the armed arm, and it names all three
attitudes. F3 (E1 fails → stop and report): **FIRED**.

## 4. Why the cell cannot measure what it was asked to measure

Three attitudes exist and only one of them is the one the run moves the arm with:

| | left `[w,x,y,z]` | belt proj | is it what runs? |
|---|---|---|---|
| `configs/waypoints_oriented.json` (the file `CANDIDATES.md`/`IK_PROBE.txt` analysed) | `(+0.184162, +0.709672, −0.193123, +0.652038)` | **+0.5132** | **no** — `PickAndPlaceTask` defaults to `os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json")`, and **no** shipped path sets `FRUIT_WAYPOINTS` (grep over `scripts/`, `accept*.sh`, `110_rl_rollout.py`, `run.sh`, `154_claim_run.sh`) |
| `configs/waypoints.json`'s left (= the file the env loads; `_grasp_quat`'s return) | `(+0, −0.707107, +0.707107, +0)` | **0.0000** | the **pre-pose** hold only |
| the never-stop catch's own installed hold, `mirror_across_xz(top_down_quaternion("x"))` | `(+0, −0.707107, +0.707107, +0)` | **0.0000** | **yes**, for the hover/descent/close |

The catch **discards** `_grasp_quat` before the descent: `_run_impl` sets
`arm.hold_quaternion = self._grasp_quat(arm_name)`, then
`arm.hold_quaternion = None` ("the carry and the place poses are position-only"),
then the `dynamic_pick` branch installs the top-down hold. Between the two writes
the only consumer is a `solve_to` gated on `not self.grippers[arm].enabled` — the
**kinematic-pads** gripper — while the default `openarm` hand has `enabled = True`
and `FRUIT_PREPOSE_SOLVE` defaults to `0`. So the brief's channel reaches the
pre-pose only, and its value there is already T0.

**`logs/p62/PREREG_P2.md` §3 registered exactly this gate before the runs**, with
the decision rule "moves < 0.05 → F3 fires, the cell is not run". The tree read
that motivated it is in that file; §2 above is the measurement of it.

## 5. The one thing this phase hands on: the gap is achieved-vs-commanded, not the command

The left **is commanded** the ideal attitude (T0, projection 0.000) and **achieves
+0.355 (seed 77) / +0.321 (seed 101)** at the end of its `grasp_lift` — 28.6° and
26.3° of tilt. So on the owner's question
("choose a grasp attitude that suits the left"), the *command* axis is exhausted:
phase 1 already measured that the world-z yaw family — the only family that
changes the projection while preserving the attitude's relation to the vertical —
**never solves** at the left station (residual 10.6 → 118.0 mm, j2 margin
collapsing to its limit, pads down to and through the belt top), and T0 is the one
attitude that reaches projection 0 *and* solves. T0 is also **not the right arm's
mirror** (the two are 100.7° apart; the right keeps its own). What remains is the
**tracking**: the arm's achieved tool axis is 26.3–28.7° off the attitude it is
asked for, and that is a seed / hold-stiffness property, not a file entry
(`CANDIDATES.md` §5.3's "a new seed for the attitude"). Named next items, each
needing its own pre-registration:

1. **the grasp seed** (`configs/waypoints.json` `arms.left.grasp`, the joint
   vector the reset teleports to) re-solved *for* T0 and pinned — a `configs/`
   change, so it moves the scripted line too and needs **both** motion references
   re-recorded (P41's rule);
2. **the attitude hold's weight** in `ik_step` (the rotation error is one term of
   a 6-DoF solve whose Jacobian is position-led), whose per-tick cost is the
   `AGENTS.md` §2 "instrumentation in the control loop" class and therefore needs
   its own A/B;
3. a **hold-side** override (the line that installs the top-down hold) if a future
   candidate ever differs from T0 — the `_grasp_quat` channel is proven not to be
   it.

## 6. A1 — the scripted line is byte-identical (proven, not assumed)

`scripts/accept.sh` once with **every knob unset** (`SKIP_SELFCHECK=1`, the run log
`logs/p62/p2/accept_wall.log`, the gate's own output
`logs/p62/p2/motion_gate.txt`):

| read | value |
|---|---|
| `[fruit]` physics rows | **377**, vs the reference's **377** after its own instrument rows are removed (the P41 log carries 60 `[fruit] [diag]` + 20 `[fruit] [carry]` rows a knobs-off run cannot produce — 457 − 80 = 377) |
| identity | **377/377 IDENTICAL**, stream md5 `8345af7f…` on both sides |
| motion gate | **`fingerprint: matches configs/motion_reference.json`** (`8a399626`) |
| `[stats]` | `attempts=10 successes=6 diverted=0 success_rate=60% sim=150.5s total, 15.0s/attempt gate_open=0.0s`, `queue_peak=0` |
| gate verdict | FAIL **on the rate only** (`success: 6/10 = 60% (floor 75%)`, `- success 6/10 below 75%`) — **6/10 + `fingerprint: matches` is this tree's documented count** (P41/P42/P43/P44/P50 all record it) |
| tree md5s before/after | identical |

This is the P38-M4 / P43 style **import guard** and is stated as such: the scripted
entry (`20_pick_place.py`) never constructs `SortingRLEnv`, the kwarg defaults to
`None` (the `232` leg executes the real `_grasp_quat` to prove `None` = the file
exactly), and no `configs/` byte changed. It could not have measured a knob effect
either way.

## 7. What this settles, and what it does not

**Settled.** (a) The direct line's left grasp attitude is **already T0** in the
file it loads *and* in the hold the catch installs — the two are the same array.
(b) The brief's override channel (`_grasp_quat`) **cannot** move the achieved
attitude: −0.0018 / +0.0001 against a 0.05 gate on two independent seeds, with the
untouched arm moving 37× / 174× more. (c) `configs/waypoints_oriented.json` — the
attitude phase 1's candidate table, `IK_PROBE.txt` and P61's world mapping were
computed from — is **not** the attitude this environment runs; a future phase that
wants to reason about the *achieved* attitude must read it (`FRUIT_CARRY_ATTITUDE=1`,
`[attitude] tool_axis=`) rather than the file. (d) The scripted line is
byte-identical. (e) The two pairs also give this loop a small **noise floor** for
future arm-level attitude work: the same command produced achieved tilts of
28.6/28.7° on one draw and 26.3/26.3° on another, and the untouched arm's
projection moved 0.0675 / 0.0174 — an attitude endpoint needs several samples
before any delta under ~0.07 is quotable.

**Not shown.** (i) Whether a left attitude that the arm can *hold* (a re-solved
seed, a stiffer hold) would convert the cnp class — untested, and the family that
zeroes the projection without breaking the station is a single point (T0).
(ii) P61's **world** decomposition: it maps the leg frame with
`configs/waypoints_oriented.json`'s rotation, which this phase shows is not the
attitude the run holds, so its **world** y sign in particular should be re-derived
from `[attitude] tool_axis=` before it is quoted again; P61's **leg-frame**
numbers and its 25.2° / 76.1° angles are unaffected (they need no file).
(iii) Any rate: two arms × 2 episodes is not a cell, and the direct loop
conditions on rendered frames.

## 8. Reproduce / provenance

```bash
python3 scripts/232_p62_grasp_selftest.py     # the new selfcheck leg (36 checks)
bash logs/p62/p2/run_p0.sh                    # gate P0  (seed 77, measured tree)
bash logs/p62/p2/run_p0b.sh                   # gate P0b (seed 101, final tree)
python3 logs/p62/p2_report.py --check         # -> logs/p62/p2_report.txt, 31/31 PASS
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p62/p2/accept_wall.log scripts/accept.sh   # A1
python3 scripts/105_motion_regression.py logs/p62/p2/accept_wall.log \
  --fingerprint configs/motion_reference.json > logs/p62/p2/motion_gate.txt
```

Pins (final tree): `tasks.py` **`fe11910a`**, `rl_env.py` **`921972a3`** (the
`TASKS_MD5` metadata-only follow + the resolver/row), `scripts/232_p62_grasp_selftest.py`
**`e1f86725`**, `scripts/selfcheck.sh` **`f97b928d`**, `logs/p62/PREREG_P2.md`
**`6be9bfb9`**, `logs/p62/p2/run_p0.sh` **`33f132c7`**, `run_p0b.sh` **`3a06f212`**,
`p0_header.txt` **`25e80259`**, `p0b_header.txt` **`8f178c6a`**, `P0_A.log`
**`cff1e798`**, `P0_B.log` **`cd797b89`**, `P0b_A.log` **`128f43b2`**, `P0b_B.log`
**`cf86313f`**, `accept_wall.log` **`93b6e201`**, `motion_gate.txt` **`c181f8b2`**,
`p2_report.py` **`efff1c95`**, `p2_report.txt` **`fa7db074`**. **Measured-tree
note**: P0 ran `tasks.py` `e5bc98a9` / `rl_env.py` `97d86460`; the delta to the
final pins is the two comment blocks and the `TASKS_MD5` string (a provenance
comparison, not a control input), and P0b re-measured the gate on the final tree.
Checkpoint `moe_v13s` `61da390a`; `configs/*` untouched (`waypoints.json`
`d81c6f1c`, `waypoints_oriented.json` `0ea08ebb`, `motion_reference.json`
`8a399626`, `motion_reference_twoline.json` `2246f83c`), `fruits.py` `c7461d41`,
`control.py` `9384ff4f`, `scene.py` `27e3d64a`. `FRUIT_GRASP_LEFT_TOPDOWN` is
**default off** and `FRUIT_CARRY_ATTITUDE` / `FRUIT_CARRY_DIAG` / `FRUIT_MOTION_REPORT`
stay default off. **`logs/` is gitignored**, so this directory needs `git add -f`
at the close-out.
