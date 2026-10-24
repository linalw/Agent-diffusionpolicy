> **SUPERSEDED 2026-10-24 by `logs/p35/C_RESULTS.md`.** Gate 1 blocked this batch's
> manipulation check on five P0 defects (M1 against the configured command instead
> of the achieved pose; M2 read at the band's least-occluding edge; a bbox fitted to
> the visible mask instead of the projected disc; the stale first call; an
> undocumented diag). The check was revised (`logs/p35/C_PREREG_AMEND.md`) and the
> A/B re-run (N=5x15, same arms/seeds) as `logs/p35/C_ab/`, which is the record of
> record. This file is kept as the pre-P0 provenance: its outcome numbers are a
> separate sample and its own new failure reason (1/75) is not reproduced in C.

# P35 phase 2 — the arm-park A/B: the park removes the band occlusion and the right's carried class converts; the mediator is not identified and the adoption stays blocked

Measured 2026-10-24 on `21b9acc` + the P35 phase-1 working tree (`rl_env.py`
`611b18d8`, `configs/arm_parks.json` `42ab4fb7`, `tasks.py` `cdde6bd2`,
`trigger.py` `d7ec85fc`, `runtime.py` `379ac706`, `meshes.py` `41efc522`;
checkpoint `moe_v13s` `61da390a`; the tree md5s are identical **before and
after** the batch). **No shipped default changed** (`FRUIT_ARM_PARK` unset =
the shipped `ready` teleport), **no commit**. Pre-registration:
`logs/p35/PREREG.md`; the check's amendment (written before the A/B, on the
check's own smoke data only): `logs/p35/B_PREREG_AMEND.md`.

## 0. The one-line answer

With the **inactive left arm parked at `back`** instead of the shipped `ready`
pose, the direct policy sees the fruit in the +0.30..+0.45 approach band - the
band's **fully-hidden calls fall 51 % -> 1 %**, the parked arm contributes
**0.000** of the target's pixels at **every** band call (control: the arm's
pixels are **1.125 x** the target's), and the **right arm's carried-not-placed
class - the interface's characteristic failure - goes 26/57 -> 0/48**, with the
right's success 28/57 (49 %) -> 45/48 (94 %) and the pooled rate 29/75 (39 %) ->
47/75 (63 %). The left arm (the treatment's no-op) is unchanged (1/18 -> 2/27),
which is where the attribution comes from. **The falsifier does not fire.** The
pre-registered adoption blocks do: **one new failure reason** (1 episode) and the
park's realized pose sits **0.09-0.10 rad** from its command (> 0.02) - and a
positive still needs a recollection, since every recorded store frame has the
left arm at `ready`.

## 1. The manipulation check (the gate)

The check is the per-call census of `FRUIT_PARK_DIAG=1` (`[park]` rows, one per
episode + one per band call), identical on **both** arms. It reads the frame the
model call conditioned on, at the band the arm occludes. **Sentinels:** `px=0` =
the target's mask is empty (`top=-`, no bbox); `rel=-1` / `frac=-1` = the ratio
is undefined; a summary `min_rel=-1` = no band call had a usable ratio (the
target was never visible in the band).

**The pre-registered readings, as written** (`PREREG.md` section 2):

| reading | control (A) | park (B) |
| --- | --- | --- |
| **M1** the inactive arm <= 0.02 rad of its command, first model call | **0/57** (residual 0.038) | **0/48** (0.090) |
| **M2** the *first* band call: target >= 0.85 x max **and** arm < 0.10 x target | 23/57 | 31/48 |

Both are unusable as the gate, for measured reasons: **M1's bar sits below the reset's own teleport
accuracy** - the shipped `ready` pose misses its command by 0.027-0.038 rad,
because `ArmController.teleport_joints` re-bases `sync_command_to_measured()`
after a 30-substep settle, and the park's 0.5 rad j1 move is not finished in it;
the residual is **stable** (first call -> band call: +0.011 rad) and
**reproducible** (0.091 / 0.090 in two episodes). And **M2's first call is the
band's least-occluding edge** (phase 1's cover 0.81/0.98/0.57/**0.01** at
+0.30/+0.35/+0.40/+0.45), which is why the control passes it 23/57.

**The amended gate** (`B_PREREG_AMEND.md`), read at the pose the mechanism is
about and over the whole band:

| the amended reading | control (A) | park (B) |
| --- | --- | --- |
| **M1'** applied + stable: `|q-back| <= 0.15` **and** `|q-ready| >= 0.30` **and** drift <= 0.02 rad | **0/57** (`|q-back|` 0.602, `|q-ready|` 0.042) | **48/48** (0.100 / 0.602, drift <= 0.012) |
| **M2a'** the arm term: `max arm_frac < 0.10` over every band call | **1/57** (median 1.125, max 3.000) | **48/48** (0.000 on every call) |
| **M2b'** the visibility term, robust form: the episode's **median** `rel >= 0.85` | **1/57** (median 0.423) | **48/48** (0.942) |
| the same, strict form (`band_all`: every call passes both clauses) | 0/57 | 24/48 |
| the same, strict form over the calls that have a ratio at all (`min_rel >= 0.85`) | 0/57 | 39/48 |
| band calls with a **fully hidden** target | **1017/2010 = 51 %** (median share 0.514/ep) | **17/1645 = 1.0 %** (median 0.000/ep) |
| the worst band-call ratio in the set | median of `min_rel` **0.019** | median **0.893**, worst **0.766** |

**The within-batch negative control.** On **left-active** episodes the inactive
arm is the **right** one, which `configs/arm_parks.json` leaves shipped (`null`):
A and B then run the *same* scene. Its numbers agree across the two arms -
episode-median `rel` 0.940 (A, n=18) vs 0.933 (B, n=27), `arm_frac` 0.000 on
18/18 and 27/27, `px=0` share 0.090 vs 0.081 - so the instrument is not
systematically failing; and its strict form fails **0/27** while its median
passes 25/27, which is the measured reason the median is the read (the
small-fruit mask is 24-30 px, so +-2 px is +-8 %; the treatment's whole-set worst
call is **0.766**, i.e. a 13-23 % dip, nowhere near an occlusion, while the
control's median worst call is **0.019**).

**Attribution** (`B_attribution.txt`): where the visibility term still fails
under the park, the largest instance at the worst *visible* call is the target
itself (24/24 episodes) - so the dip is partial (mask jitter, and on the
left-active episodes the *active* arm at `grasp`, which the census does not
count) or the belt/frame at the outer x (phase 1's `outer_edge`: 0.105 visible
under **every** park). The lever's own term is exactly zero on all 48 episodes.

**Verdict on the check: PASS** (M1' 48/48, M2a' 48/48, M2b' 48/48; per treatment
run 10/10, 10/10, 8/8, 11/11, 9/9 on all three - >= 4/5 in each of the five as
pre-registered; the control fails M2a' 56/57 and M2b' 56/57). The pre-registered
M1/M2 sample points are reported above and do not gate.

## 2. The A/B

The P33/W8-A direct protocol verbatim: patch supply
(`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25`),
the arrival trigger + ACQ (`lead 0.9`, `FRUIT_DYNAMIC_PICK=1`,
`FRUIT_POLICY_TRIGGER_ACQ=1`), `moe_v13s` `61da390a` on **both** arms, camera
240x424, policy seed 11, **N = 5 runs x 15 episodes**, seeds
77/101/202/303/404, interleaved A,B in one `154_claim_run.sh` claim
(`logs/p35/B_ab/B_driver.log`, 09:53-11:06). Arm A = the shipped env; arm B =
`FRUIT_ARM_PARK=back`. Diagnostics on both arms: `FRUIT_ACQ_DIAG=1`,
`FRUIT_RESET_ALIGN_DIAG=1`, `FRUIT_PARK_DIAG=1`.

| run | A | B (right ok / no-grasp / carried) |
| --- | --- | --- |
| 1 (77) | 7/15 (7/2/2) | 9/15 (8/2/0) |
| 2 (101) | 2/15 (1/0/8) | 9/15 (9/1/0) |
| 3 (202) | 8/15 (8/0/6) | 8/15 (8/0/0) |
| 4 (303) | 5/15 (5/1/5) | 11/15 (11/0/0) |
| 5 (404) | 7/15 (7/0/5) | 10/15 (9/0/0) |

Run level: B >= A in **5/5** seeds, strictly better in **4/5** (one-sided sign
p = 0.0625, 4 discordant).

| per arm | A | B |
| --- | --- | --- |
| **right** (the lever's population) | n=57, ok **28 (49 %)**, no-grasp 3, carried **26** | n=48, ok **45 (94 %)**, no-grasp 3, carried **0** |
| **right composite** (carried + no-grasp) | **29** | **3** |
| **left** (the guard, a no-op) | n=18, ok **1 (6 %)**, no-grasp 0, carried 17 | n=27, ok **2 (7 %)**, no-grasp 0, carried 25 |
| pooled | **29/75 (39 %)** | **47/75 (63 %)** |
| median cycle | 1851 ticks (right 1823) | 1821 ticks (right 1793; **-1.6 %**) |

**Primary (the right's paired carried-not-placed conversion)** - the
exact-instance pairing (`park_ab_report.py`: same run, episode, species,
diameter, arm - the P33 convention): **22 usable pairs** of 75 slots (53
excluded on the fruit class, the two arms' streams diverge), 5 both-ok, 7
both-fail, **8 B-only / 2 A-only** (one-sided sign **p = 0.0547**);
carried-class **7 B-only / 1 A-only**; no-grasp-class 1/1. The pre-registered
bar (>= 5 B-only / <= 1 A-only for the carried class) is **met**. The looser
same-species pairing (`113_rl_report.py`) reads 9 B-only / 4 A-only,
p = 0.1334, 48 excluded.

**Primary-secondary**: the right's no-grasp **3 -> 3** (no class relocation) and
the composite **29 -> 3**; the **outer-band subgroup** (right-arm attempts with a
check-frame `x < 0.26`): A n=24 ok 4 / carried 18 / no-grasp 2, B n=15 **ok 15 /
carried 0 / no-grasp 0**; exact pairs inside it 10 usable, 3 B-only / 1 A-only,
carried 2-1.

**Guard**: the left's placed 1/18 -> 2/27 (6 % -> 7 %, no regression) and its
no-grasp 0 -> 0; pooled placed rises. **Secondary**: cycle -1.6 %; the
`[align]` first-call counters are unchanged in kind - the first call's along
median **+0.485 / +0.478**, its target mask **0 on 72/75 episodes in both arms**
(the first call sits in the +Y belt's hidden band, P34-B), `pfc` 0 / 0 and `pcm`
**99 / 119**, the fire-zone zero-mask counters 0/16 and 0/12 - and the fire-time
`dx` / effective-lead medians are the P33's (`B_class_split.txt`).

**New failure reason - one episode, and it blocks adoption.** B run 1, episode
10 (strawberry 3.6 cm, right, x 0.355): `openarm fingertips 37 mm from the
fruit; closing anyway` -> `close: fruit drifted 6160 mm off the pick centre
(cross-belt); re-closing on it where it is` -> `close: fruit left the pick
station (17977 mm cross-belt); aborting the attempt instead of chasing it`
-> the episode note `fruit left the pick station during the close (17977 mm)`.
A 6.2 m -> 18.0 m fruit displacement is not a mechanism on a 2 m line: it is a
runaway body state (the note fires on the `drift_max` test in the close). The
class it lands in is the existing **no-grasp** (grasped=False), so the *class*
counts are comparable - but the **reason string is new**, and `PREREG.md`
section 5 blocks any adoption claim on a new reason. That block is recorded, not
waived.

## 3. The mechanism, and what this A/B does not separate

The park does exactly one thing in the scene: it moves the **inactive** left arm
from `ready` (jaw at (0.333, 0.055, 1.363), hand 0.115 m over the belt) to
`back` (hand 0.287 m over the belt, into the spawn corner), once per episode, in
the reset. The active arm is untouched (the phase-1 guard). The in-vivo census
shows the consequence on every band call: the arm's pixels inside the fruit's own
bbox are 0.000 (control 1.125 x the fruit's own pixels, max 3.000), the fruit's
median visibility rises 0.423 -> 0.942 of the episode's own maximum, and the
band's fully-hidden calls fall 51 % -> 1 %. The failure that disappears is the
right arm's **carried-not-placed** class - the same class the scripted line's
close/load work targeted (P18b's direct-interface carried class), here removed by making the fruit visible
to the policy rather than by changing the primitive.

**Not separated**: the park changes the **image** (a static silhouette in every
frame, 3497 -> 4155 px) *and* the **7 inactive-arm joint channels of the 25-D
proprio** (the store has the left arm at `ready`). So the measured gain is "this
checkpoint on shifted inputs"; the sightline is measured as *present* (the
census), but the A/B cannot attribute the gain between the two channels. That is
the same OOD class `PREREG.md` section 6 priced, and it is why the adoption path
is a **recollection** (which fixes both channels) whose own A/B is the gate.

## 4. The verdict

* **The falsifier does not fire.** The check passes (M1' 48/48, M2a' 48/48,
  M2b' 48/48; control 1/57 and 1/57) and the right arm moves decisively in the
  predicted direction: carried **26 -> 0**, composite **29 -> 3**, exact-pair
  carried conversion **7 B-only / 1 A-only** (bar met), outer band 4/24 -> 15/15,
  the guard flat, the cycle -1.6 %.
* **The park is a measured interface lever on this scenario; the mediator is not
  identified** (`PREREG.md` section 5's positive clause on the outcome, not on
  the mechanism): the check shows it removes the fruit's band occlusion, but the
  park moves the image *and* the 7 inactive-arm proprio channels, and the C
  record's control succeeds with the fruit invisible - so a simple perception
  bottleneck is not established (see `logs/p35/C_RESULTS.md` section 3 for the
  named proprio-spoof x image-spoof test). It ships **default off**: no shipped
  default changed, and every recorded store frame carries the left arm at
  `ready`.
* **Adoption is blocked, twice, as pre-registered**: the new reason (§2) and the
  park's realized pose residual 0.090-0.102 rad > 0.02 (`PREREG.md` section 5's
  last bullet) - the latter is a *teleport settle* artifact, not a sightline
  defect (the census is 48/48), but the bullet is the bullet. A positive is
  therefore a statement about **this checkpoint on shifted inputs**, and the
  shipping path is a recollection + its own A/B.
* The pre-registered power caveat held: the exact-pair sign test is
  **p = 0.0547** (8-2) - one pair short of 0.05 at this N - so the primary read
  is the **class conversion** (7-1) and the per-run consistency (5/5), not the
  pooled sign test.

## 5. Provenance, no-harm, files

* `logs/p35/B_ab/` - `B_driver.log` (the batch), `A_1..5.log` / `B_1..5.log`,
  `B_report.txt` (the check + endpoints), `B_class_split.txt`, `B_pairs.txt`,
  `B_verdict.txt` (`113`), `B_attribution.txt`, `B_band_stats.txt`,
  `B_tables.txt`, `B_check_perrun.txt` + `B_check_perrun_M2b.txt` (the per-run
  check), `B_ckpt_md5.txt`, `B_tree_md5_before/after.txt` (identical),
  `B_head.txt`. Tree pins in §0.
* **No-harm**: `scripts/selfcheck.sh` **PASS** (0 failures, 1 skipped;
  `logs/p35/B_selfcheck.log`, and the same before the batch in
  `B_selfcheck_before.log`). The scripted acceptance with the knob **unset**:
  **6/10, `fingerprint: matches configs/motion_reference.json`**, and its 376
  `[fruit]` lines are **IDENTICAL** to `logs/p34/73_accept_no_harm.log`
  (`logs/p35/B_accept_identity.txt`). The 6/10 is the pre-existing P32 pear-on
  branch (rate-only FAIL against the 75 % dynamic floor; AGENTS.md section 2).
* The scratch smokes: `logs/p35/10..13_smoke*.log` (the check's own exercise;
  the last pair reads control 0/2, park 2/2 on the same two instances - a smoke,
  never a rate).
* **Risks**: (a) the two-channel confound of §3; (b) the exact pairing covers 22
  of 75 slots, so the primary is a paired *class* read on a partial intersection
  (the per-run table is the second leg); (c) the park's j1 residual is a
  `teleport_joints` property (both arms) - a longer reset settle would fix it,
  but that changes the belt's reset travel and is its own pre-registration;
  (d) `min_rel=-1` and `frac=-1` are the diag's undefined sentinels (documented
  above); (e) one new reason (1/75) - a runaway fruit state, recorded as a block.
