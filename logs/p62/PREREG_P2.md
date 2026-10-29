# P62 phase 2 pre-registration — the T0 left grasp attitude, and the gate that decides whether the cell can measure anything

Written **before any simulator run of this phase**, on HEAD `21690c3` + the
uncommitted phase-2 edit (`tasks.py` `e5bc98a9`, `rl_env.py`
`425b92e0`, `scripts/232_p62_grasp_selftest.py`). `configs/*` untouched
(`waypoints_oriented.json` `0ea08ebb`, `motion_reference.json` `8a399626`,
`motion_reference_twoline.json` `2246f83c`). Inputs read: `logs/p62/CANDIDATES.md`
(+`IK_PROBE.txt`), `.slim/deepwork/p62-left-grasp.md`, `logs/p61/P2_RESULTS.md`,
`logs/p61/p2/S_{77,101,202}.log` (the control).

## 1. What is being measured

The **T0** left grasp attitude — fingers straight down, jaws exactly across the
belt, `[w,x,y,z] = (+0.000000, −0.707107, +0.707107, +0.000000)`, tool axis
`(0,0,−1)`, belt projection **0.000** — carried **left-only and direct-scoped**
through the caller-owned `PickAndPlaceTask(grasp_quat_override=...)` kwarg behind
`FRUIT_GRASP_LEFT_TOPDOWN=1` (**default off**). The mechanism it targets: P61's
left escape leaves **along the tool axis** (leg-frame share **0.905**) and the
attitude `logs/p62/CANDIDATES.md` analysed has a **+0.513** belt projection on
that axis, so the belt's drag has a component along the direction the payload
leaves in.

## 2. Registered endpoints (the brief's E1–E5, verbatim in intent)

| id | endpoint | comparison |
|---|---|---|
| **E1** (primary, mechanism) | the left's escaping `grasp_lift` legs' slip mapped to the tool axis has a **\|belt projection\| ≤ 0.10** | P61: 0.513 / share 0.905 |
| **E2** (primary, class) | the left's **cnp** count falls | P61: **16/18**; bar **≤ 12/18** (a third fewer), exact reported |
| **E3** (predicted cost) | the left's **never-held** count | P61: **0/18**; a rise is the **+x cliff** (32.8 mm vs 8.3 at x = 0.398), recorded as such, **not** as a mechanism failure |
| **E4** (scoping proof) | the **right does not move** | P61: 1 cnp / 25 placed / 27 attempts |
| **E5** | no new failure reason; placed reported only; the ACQ joint-limit margin (`FRUIT_ACQ_DIAG`) reported (the **j3 +0.007 rad** risk) | P61's note keys |

Falsifiers: **F1** a wedge → retry once. **F2** the `[grasp]` row does not name
the override → stop (the knob did not arm). **F3** E1 fails → the attitude did
not change the mechanism; stop and report.

## 3. The precondition gate (registered here, before the runs)

E1 is a **mechanism** endpoint, and a mechanism endpoint is only meaningful if
the armed run actually commands a different attitude from the control. The tree
read below is therefore registered as a **gate that runs before the 3 × 15 cell**,
so a structural null cannot be reported as a measured one (and so 3 simulator
runs are not spent proving that two identical commands give identical results):

**P0 (the attitude gate).** One episode per arm at seed 77, the cell's scenario,
with `FRUIT_CARRY_ATTITUDE=1` added (reporting only: one TCP-pose read per carry
leg), control vs `FRUIT_GRASP_LEFT_TOPDOWN=1`. **Decision rule:** if the left's
achieved `grasp_lift` tool-axis belt projection moves by **< 0.05** between the
arms, the knob does not reach the attitude the catch runs and **F3 fires** (the
cell is not run; the finding is reported with its numbers). If it moves by
**≥ 0.05**, E1 is evaluable and the 3 × 15 cell runs as registered.

**Why this gate and not a code argument.** The read that motivates it, all
measured or read off the tree before this file:

1. **The direct env does not load the file phase 1 analysed.**
   `PickAndPlaceTask` defaults its waypoints to
   `os.environ.get("FRUIT_WAYPOINTS", "configs/waypoints.json")`
   (`tasks.py`), and `FRUIT_WAYPOINTS` is set by **no** shipped path (grep over
   `scripts/`, `accept*.sh`, `110_rl_rollout.py`, `run.sh`, `154_claim_run.sh`).
   `configs/waypoints.json`'s left `grasp_quaternion` is
   `(0, −0.70710678, +0.70710678, 0)` — **T0**, belt projection **0.000** — and
   its right is the un-mirrored top-down. `configs/waypoints_oriented.json`
   (left `(+0.184162, +0.709672, −0.193123, +0.652038)`, projection **+0.513**)
   is the file `CANDIDATES.md`/`IK_PROBE.txt` computed the candidate table from,
   and it is **not** the attitude this environment's run moves the arms with.
2. **The never-stop catch discards `_grasp_quat` before the descent.** In
   `_run_impl`, `arm.hold_quaternion = self._grasp_quat(arm_name)` is followed
   ~30 lines later by `arm.hold_quaternion = None` ("the carry and the place
   poses are position-only"), and the `dynamic_pick` branch then installs
   `mirror_across_xz(top_down_quaternion("x"))` for the left — which **is** T0,
   bit-identical to `configs/waypoints.json`'s left value (the `232` selftest
   pins this). Between the two writes the only consumer is a `solve_to` gated on
   `not self.grippers[arm].enabled`, i.e. the **kinematic-pads** gripper; the
   default `openarm` hand has `enabled = True`, and `FRUIT_PREPOSE_SOLVE`
   defaults to `0`.
3. So the override can only reach the **pre-pose** hold — the attitude the arm
   is asked for **before** the hover/descent, on an already-T0 value.

**What the gate can and cannot conclude.** If P0 reads "no movement", every
E2–E5 count difference would be **branch noise of a non-reproducible loop**
(`AGENTS.md` §3b) and no E1 claim is available; that is a **structural null of
this interface**, not a statement that T0 is wrong (T0 is *already* what runs)
and not a statement that an attitude change cannot move the class on an
interface that commands the achieved attitude (the seed and the hold stiffness
are the named channels, `CANDIDATES.md` §5.3). If P0 reads "movement", the cell
runs and E1–E5 are read as registered.

## 4. No-harm item (independent of the above, and owed either way)

**A1 — the scripted line is byte-identical by construction, proven.**
`scripts/accept.sh` once with **every knob unset**: its `[fruit]` stream must be
**377/377 identical** to `logs/p41/p2/accept_profile.log` and the motion gate
must read **`fingerprint: matches`**. The mechanism: the scripted entry
(`20_pick_place.py`) never constructs `SortingRLEnv`, the kwarg defaults to
`None` (the `232` selftest executes the real `_grasp_quat` to prove `None` = the
file exactly), and no `configs/` byte changed. This is the P38-M4 / P43 style
**import guard** and is stated as such.

## 5. Reading rules carried in from the record

- **No rate claim.** The direct loop conditions on rendered frames
  (`AGENTS.md` §3b), so a count is one draw; per-arm class counts are the read,
  and cross-arm *rates* are not.
- **`cnp` = `carried-not-placed`**, the closed loaded-slide class
  (`logs/p42/SIM_LIMIT.md`); the left reaches it at a 47× rate with
  arm = lane = grade confounded (`rl_env.py:2516`), so a movement here is
  "left+bin0+grade-A", not "the arm".
- **Slip is read at the maximum, one vector per leg**, in the **achieved TCP
  frame** (`rot_now.T @ (fruit − pads)` differenced against the leg's first
  tick), so the tool-axis share is exact and needs no `configs/` attitude.
- **Place/discard rows**: a `place0` row with `contacts@onset = 0` is the
  downstream view of a payload already gone (P60), never the seat.
