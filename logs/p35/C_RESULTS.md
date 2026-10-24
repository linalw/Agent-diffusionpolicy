# P35 phase 2 — the arm-park A/B under the Gate-1 P0 check (the record of record)

Measured 2026-10-24 on `21b9acc` + the P35 working tree, **`rl_env.py`
`fd18bb1b`** (the P35 park knob + the P0-revised `FRUIT_PARK_DIAG`), `tasks.py`
`cdde6bd2`, `trigger.py` `d7ec85fc`, `runtime.py` `379ac706`, `meshes.py`
`41efc522`, `configs/arm_parks.json` `42ab4fb7`; checkpoint `moe_v13s`
`61da390a`; the tree md5s are identical **before and after** the batch
(`C_tree_md5_before/after.txt`). **No shipped default changed** (both knobs
default off); the batch itself ran **uncommitted**, and the P35 work is committed
after the Gate-2 documentation corrections (§ the WORKLOG entry).

Batch: `logs/p35/C_ab/`, 12:59-14:10, one `154_claim_run.sh` claim, N = 5 runs x
15 episodes per arm, seeds 77/101/202/303/404, policy seed 11, interleaved A,B,
the P33/W8-A scenario verbatim (`FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival
FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_TRIGGER_ACQ=1`,
camera 240x424), arm A = the shipped env, arm B = `FRUIT_ARM_PARK=back`.
Diagnostics on both arms: `FRUIT_ACQ_DIAG=1 FRUIT_RESET_ALIGN_DIAG=1
FRUIT_PARK_DIAG=1`. The check's pre-registration for this batch:
`logs/p35/C_PREREG_AMEND.md` (written before it); the superseded pre-P0 batch and
its check: `logs/p35/B_ab/`, `B_PREREG_AMEND.md`, `B_RESULTS.md`.

## 0. The one-line answer

With the inactive left arm at **`back`** instead of the shipped `ready`, the
direct policy's view of the +0.30..+0.40 approach band changes completely: the
band's **fully-hidden calls go 856/1257 (68.1 %) -> 0/1236 (0.0 %)** and the
inactive arm contributes **a pixel in 1257/1257 calls (100 %) -> 0/1236 (0 %)**
inside the fruit's **projected-disc bbox**, while the right arm's
**carried-not-placed** class - the interface's characteristic failure - goes
**25/51 -> 0/50**; the right's success **23/51 (45 %) -> 47/50 (94 %)**, pooled
**24/75 (32 %) -> 49/75 (65 %)**. The left arm (the treatment's no-op) is flat
(1/24 -> 2/25). **The falsifier does not fire; no new failure reason appears in
this batch.**

**What that does and does not show.** The **park is a measured interface
lever** on this scenario, and the check shows it **removes the fruit's band
occlusion**. The **mediator is not identified**: the park is a static scene
change on two input channels - the image (3497 -> 4155 px of silhouette in every
frame) and the **7 inactive-arm joints of the 25-D proprio** - and this A/B does
not separate them. The control's **invisible-fruit successes** (9 of its 23
right-arm successes read `px=0` at every band call; the successes' median
fully-hidden share is 0.84 against the failures' 0.60) argue **against a simple
perception bottleneck**, so "the policy could not see the fruit" is not an
established mechanism. The pre-registered adoption still requires a
**recollection**; the named discriminator between the two channels is the
**proprio-spoof x image-spoof** test (section 3), and a recollection - which
fixes both channels at once and can erase a checkpoint-specific input-shift win -
should not be its first spend.

## 1. The manipulation check (Gate-1 P0; both arms, per call)

**M1 - the pose.** Read at the first **non-stale** call (the first call
conditions on the pre-reset frame; `stale_skipped` = 1 on every episode), against
the pose the reset **achieved**:

| | control (A) | park (B) |
| --- | --- | --- |
| **M1 held** `max|q - q_settled| <= 0.02 rad` | 51/51 (median 0.002) | **50/50** (median 0.004) |
| achieved-vs-commanded residual (reported) | 0.037 rad (`ready`) | 0.088 rad (`back`) |
| **M1 applied** `|q-back| <= 0.15` and `|q-ready| >= 0.30`, drift <= 0.02 | **0/51** (0.601 / 0.037) | **50/50** (0.089 / 0.602, drift <= 0.010) |

The command-relative reading is *why the pre-P0 bar was wrong*: the reset's own
teleport re-bases onto the measured state, so `ready` sits 0.037 rad from its
command and the park 0.088. Under a 0.04 rad command bar the **shipped** reset
would be at the edge and the park would fail, which is not a statement about the
sightline; the achieved-pose comparison is the operative one (the gate's first
option) and the command residual is reported beside it. **The two readings are
not the same object**: the *gate* is M1-held-and-applied against the achieved
pose (above), while `PREREG.md` section 5's adoption bullet - "an arm-pose
residual > 0.02 rad" - is read against the **commanded** pose and is therefore
**failed** by the park's 0.088 rad (and would be failed by the shipped `ready`
reset at 0.037); see the verdict line below.

**M2 - the sightline,** censused over **+0.30..+0.40** at the band's **worst**
call, arm pixels counted inside the **projected disc's bbox** (`r_px = f r /
sqrt(d^2 - r^2)`, area `pi r_px^2`, the `212`/`217` camera model):

| the lever's population (inactive = the left arm) | control (A) | park (B) |
| --- | --- | --- |
| band calls | 1257 | 1236 |
| **fully-hidden target calls** | **856 = 68.1 %** | **0 = 0.0 %** |
| **calls with any inactive-arm pixel inside the disc's bbox** | **1257 = 100 %** (worst arm/target ratio **333**) | **0 = 0.0 %** (ratio 0.00) |
| **M2a** `max arm_frac < 0.10` at the worst call | **0/51** | **50/50** |
| **M2b** episode-relative `rel >= 0.85` at the worst call (report, not gate) | 0/51 | **36/50** |
| reported: disc-relative `vis` median at the worst call | 0.000 | 0.984 |

**The no-op side is the within-batch negative control** (left-active episodes: the
inactive arm is the **right**, shipped in both arms): fully-hidden 65/584
(11.1 %) in A vs 55/610 (9.0 %) in B, inactive-arm pixels 0/584 vs 0/610. The
~10 % hidden calls there are the **active** left arm at `grasp`, which this census
does not count - so the instrument behaves the same in both arms when the lever is
absent.

**M2b is a recorded report, not the gate, and its misses are the normalisation
plus small-mask raster drift, not an occluder.** The gate of record is **M1 +
M2a** (the pose and the arm term); M2b reads **36/50 = 72 %** and is reported
beside them. The 14 misses are all at `arm_px = 0`, with `rel` 0.766-0.848, the
disc-relative `vis` at **0.57-1.02** (**2** of them >= 0.98, i.e. fully visible
by the absolute measure; 3 at >= 0.97) and masks of only **22-47 px**, whose
largest instance is the **belt** (the belt/frame where present) - a +-2 px edge
is ~8 % of a 25 px mask. `rel` divides by a **running** `px*d^2` maximum
(updated on every non-stale call, not the episode's final maximum), so a band
call is normalised against another call's geometry as often as against its own.
`vis` is size-biased (the analytic disc reads 39 px for a 36 mm fruit whose
render is 27 px, so a fully visible small fruit measures **0.68** of it; a 68 mm
one 1.11x), so it is reported and never gated. Neither is a bar one can hold at
0.85 across 22-47 px masks, which is why **the exact counts carry the claim**
(fully-hidden 68.1 % -> 0.0 %, arm pixels 100 % -> 0 %) and M2b is reported with
this attribution.

**Check verdict: PASS on M1 (held 50/50, applied 50/50), M2a (50/50) and the band
census (0/1236 hidden, 0/1236 arm-tainted); the gate of record is M1 + M2a, and
M2b is a recorded report, not part of it.** The control fails M2a 51/51 and the
census is 68.1 % hidden / 100 % arm-tainted. **`PREREG.md` section 5's literal
arm-pose block ("a residual > 0.02 rad") is failed by the park's 0.088 rad
achieved-vs-commanded residual** - it would fail the shipped `ready` reset too
(0.037 rad) - so the adoption is blocked on the record whatever the outcome, and
the conclusion (**default off, not adopted**) is unchanged.

**Attribution (Gate-2 audit).** `C_attribution.py` splits the episodes whose
visibility term fails by who holds the worst visible call's pixels: arm A's
inactive-left set is **`arm 40 / never-visible 11`** (the 11 are the episodes whose
whole band census is `px = 0`). The script's first version counted a `frac = -1`
row (no bbox) as **passing** the arm term, which is how A read 11/51; it is fixed
(`max(frac) >= 0` required, so a never-visible episode fails the arm test),
re-run and annotated - **A's arm term reads 0/51** and the census lines are
unchanged (`C_ab/C_attribution.txt`).

## 2. The A/B

| run | A (right ok/ng/carried) | B (right ok/ng/carried) |
| --- | --- | --- |
| 1 (77) | 4/15 (4/2/3) | 9/15 (9/2/0) |
| 2 (101) | 4/15 (4/0/6) | 9/15 (9/0/0) |
| 3 (202) | 3/15 (3/0/8) | 10/15 (9/0/0) |
| 4 (303) | 7/15 (7/1/3) | 11/15 (10/0/0) |
| 5 (404) | 6/15 (5/0/5) | 10/15 (10/1/0) |

B > A in **5/5 runs** (one-sided sign **p = 0.031**; pooled 49 vs 24) - the
design-valid leg.

| per arm | A | B |
| --- | --- | --- |
| **right** (the lever's population) | n=51, ok **23 (45 %)**, no-grasp 3, carried **25** | n=50, ok **47 (94 %)**, no-grasp 3, carried **0** |
| **right composite** (carried + no-grasp) | **28** | **3** |
| **left** (guard, a no-op) | n=24, ok **1 (4 %)**, no-grasp 0, carried 23 | n=25, ok **2 (8 %)**, no-grasp 0, carried 23 |
| pooled | **24/75 (32 %)** | **49/75 (65 %)** |
| median cycle | 1867 ticks (right 1849) | 1802 ticks (right 1762; **-3.5 %**) |

**The design-valid leg is the run level: B > A in 5/5 runs** (one-sided sign
**p = 0.031**), with the **standardised counts** beside it (right 23/51 -> 47/50;
carried 25 -> 0; the class- and size-standardised rates in section 3).
**The exact-instance pairing is conditioned on a post-treatment variable**: the
streams diverge with the outcomes, so only the slots that happen to present the
same fruit become pairable, and which slots those are is a consequence of the
treatment. It reads **22 usable pairs** of 75 slots (53 excluded on the fruit
class: same run, episode, species, diameter, arm), 6 both-ok, 8 both-fail,
**8 B-only / 0 A-only** (one-sided sign **p = 0.0039**); **carried-class 7 B-only
/ 0 A-only** (the pre-registered bar is >= 5 / <= 1 - **met**); no-grasp-class
1/0. The outer-band subgroup pairs **13 usable, 6 B-only / 0 A-only**
(p = 0.0156), carried 5-0. `C_pairs.txt` is the **looser same-species** set
(`113_rl_report.py`): **24 pairs, 8 B-only / 1 A-only**, p = 0.0195 - the extra
A-only pair is **run4 ep10 orange 6.5 vs 6.1 cm, a different fruit**, which the
diameter-matched exact pairing excludes (hence 22 pairs, 8-0). `112_rl_ab.sh`
runs **A then B** in a fixed order inside each run (no randomisation), so an
order term is confounded with the lever and this batch does not separate it.

**Primary-secondary**: the right's no-grasp **3 -> 3** (no class relocation) and
the composite **28 -> 3**; the **outer-band subgroup** (right, check-frame
x < 0.26): A n=23 ok 6 / carried 16 / no-grasp 1, B n=17 **ok 16 / carried 0 /
no-grasp 1**; exact pairs inside it **13 usable, 6 B-only / 0 A-only**
(p = 0.0156), carried-class 5-0.

**Guard**: the left's placed 1/24 -> 2/25 (4 % -> 8 %, no regression), no-grasp
0 -> 0. **Secondary**: cycle -3.5 %; **no new failure reason** (the failure-reason
sets are identical); the `[align]` counters unchanged in kind (first along median
+0.484 / +0.483, `first_px=0` on 72/75 both arms, `pcm` 103 / 109, the fire-zone
zero-mask 0/17 and 0/12). **The cycle's outcome mix is not the same on the two
arms** (right 45 % vs 94 % success), so the raw cycle delta is a median over
different mixes and is not a like-for-like speed read; the per-class deltas
printed by `113` (apple +42, kiwi +7, lychee +35, orange +20, peach +45, pear
+18, strawberry +42, tomato +25 percentage points) are differences of per-class
rates on **different denominators**, not mix-adjusted effects - the mix-adjusted
right-arm rates are in section 3.

## 3. The verdict

* **The falsifier does not fire**: the check passes (M1 50/50, M2a 50/50, the band
  census 0 fully-hidden and 0 arm-tainted calls of 1236) and the right's carried
  class converts 25 -> 0 with 7 B-only / 0 A-only on the exact pairs and B > A in
  **5/5** runs (p = 0.031).
* **The park is a measured interface lever on this scenario** (the PREREG's
  positive clause), and the check shows it **removes the fruit's band occlusion**.
  **The mediator (the image vs the 7 proprio channels) is not identified**: the
  park is a static scene change on both channels and this A/B does not separate
  them, while the control's **invisible-fruit successes** (9 of the 23 right-arm
  successes read `px=0` at every band call; the successes' median fully-hidden
  share 0.84 against the failures' 0.60) argue **against a simple perception
  bottleneck**. It ships **default off**; the adoption gate is a
  **recollection's own A/B**.
* **The named mechanism test** is a small-N 2x2 input spoof: the
  **proprio-spoof** (the park's joint values written into the observation, the arm
  *not* moved) x the **image-spoof** (the arm moved to `back`, the `ready` proprio
  kept). A recollection fixes both channels at once and **can erase a
  checkpoint-specific input-shift win**, so it should not be the first spend on
  the mechanism question; the two spoofs are.
* **The mix, stated**: the right arm is 45 % (A) vs 94 % (B) success, so the raw
  cycle (1867 -> 1802 ticks, -3.5 %) mixes two outcome populations. The
  **mix-adjusted** right-arm rates are **94.9 % class-standardised** (reweighted
  to the control's species mix; the control reweighted to B's mix reads 52.3 %)
  and **94.1 % size-standardised** (diameter tertiles, cuts at 4.0/6.2 cm; the
  control 45.2 %), against the raw 45 % -> 94 %. (1 cm bins read the same within
  0.3 points.)
* **Recorded, not waived**: (i) M2b is a **recorded report** at 36/50 = 72 %, not
  the gate (the gate is M1 + M2a), with every miss arm-free and inside the
  documented `rel`/`vis`/raster biases of section 1; (ii) the park's achieved pose
  is 0.088 rad from its *command* (the shipped `ready` is 0.037), which **fails
  `PREREG.md` section 5's literal 0.02 rad arm-pose block** - a teleport-settle
  property of the reset, not a sightline defect, and the conclusion (not adopted)
  is unchanged; (iii) the pre-P0 batch (`B_ab`) produced one new failure reason
  (1/75) that this batch does not reproduce - both batches are kept, the record is
  this one.
* **The `113` line "B PASSES the improvement criterion" is a harness readout, not
  the decision**: its criteria (rate, same-species sign test, strawberry, no new
  reason, cycle) are the **P33-era** set, and the decision rule is `PREREG.md`
  section 5 - the class conversion, no new reason, no guard regression, and the
  arm-pose block, which fails.
* Instrumentation is part of the measurement: the P0 diag adds two articulation
  reads at reset and one per band call; the control's pooled rate moved 29/75
  (pre-P0) -> 24/75, the treatment's 47 -> 49. The A/B comparison is made inside
  one instrumented batch, as AGENTS section 3b requires.

## 4. No-harm, provenance, files

* **No-harm**: `scripts/selfcheck.sh` **PASS** (0 failures, 1 skipped) before and
  after; the scripted acceptance with both knobs **unset** reads **6/10 +
  `fingerprint: matches configs/motion_reference.json`**, and its **376 `[fruit]`
  lines are IDENTICAL** to `logs/p34/73_accept_no_harm.log`
  (`logs/p35/C_accept_identity.txt`). The 6/10 is the pre-existing P32 pear-on
  branch (rate-only FAIL against the 75 % dynamic floor), i.e. the driver's
  `exit=1` is **expected**; `C_noharm_outer.log`'s identity step also `cat`s a
  file it had not written yet (the 14:22 line vs the 14:25 file) - the identity
  was re-verified afterwards and reads **376/376 IDENTICAL**.
* **Tree**: identical before/after (`C_tree_md5_before/after.txt`); `rl_env.py`
  `fd18bb1b` (**+424/-1 vs HEAD** `21b9acc`), `configs/arm_parks.json`
  `42ab4fb7`, `moe_v13s` `61da390a`, HEAD `21b9acc`. Scripts:
  `scripts/217_arm_park_map.py` `d73618f9`, `logs/p35/park_ab_report.py`
  `cce04b95` (batch time) -> `a796db0b` (after the Gate-2 docstring fix),
  `logs/p35/C_attribution.py` `c15c03ca` (batch time) -> `b3311523` (after the
  `frac` fix - the `C_attribution.txt` here is the re-run, annotated).
* **Files**: `logs/p35/C_ab/` - `C_driver.log`, `A_1..5.log`, `B_1..5.log`,
  `C_report.txt` (the check + endpoints), `C_class_split.txt`, `C_pairs.txt`
  (the same-species set, labelled), `C_verdict.txt` (`113`: "B PASSES the
  improvement criterion" - the P33-era harness readout), `C_tables.txt`,
  `C_attribution.txt`, `C_misses.txt`, the md5 pins, `raw/`. The pilot:
  `logs/p35/23_pilot_ready.log` / `24_pilot_back.log` (2 episodes/arm, the P0 row
  form). The revision record: `logs/p35/C_PREREG_AMEND.md`. No-harm:
  `C_noharm_outer.log`, `C_accept_no_harm.log`, `C_accept_identity.txt`,
  `C_selfcheck.log`.
* **Risks**: (a) the two-channel OOD of section 3 (the mediator is not
  identified); (b) 22 of 75 slots pair exactly and the pairing is conditioned on a
  post-treatment variable, so the paired *class* read is not the design-valid leg
  (the run-level 5/5 and the standardised counts are); (c) M2b is a report, not
  the gate; (d) the park's command residual is a `teleport_joints` property and a
  longer reset settle would change the belt's reset travel (its own
  pre-registration); (e) the pre-P0 new reason is unreproduced at 1/75 - a rate
  that cannot distinguish "gone" from "rare".
