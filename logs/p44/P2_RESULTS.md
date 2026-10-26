# P44 phase 2 — the speed cells (S1 place / S2 release / S3 lift / S13 the union), measured

Measured 2026-10-27. **No commit, no `configs/` change, every cell default off.**
Tree: HEAD `ca99148` + the working-tree cells; `tasks.py` **`b6de439c`**,
`rl_env.py` **`93e35ef7`** (the `TASKS_MD5` metadata-only follow),
`control.py` `9384ff4f`, `scene.py` `27e3d64a`, `motion.py` `7f2443c1`;
`configs/motion_reference.json` **`8a399626`** and
`configs/motion_reference_twoline.json` **`2246f83c`** untouched.
Evidence: `logs/p44/p2/` (11 runs, `run_batch.sh`, `p2_report.py` ->
`P2_report.txt`, `gates.txt`), `logs/p44/{CAP_CENSUS,PREREG}.md`.
PREREG endpoints E1-E6 / falsifiers F1-F5 are judged in §7.

**The headline.** The three caps are exactly the lever the census said they were:
the union buys **-1.45 s/attempt (median of two seeds; 15.00 -> 13.50 and
14.60 -> 13.20)**, **-1.90 s** on the pear and **-1.10 s** on the two-line
(**+12 % placed/min there, 4.90 -> 5.49, same 8/10**). Each cell's own block moves
by the profile's arithmetic (`place` 3.35 -> 2.49, `release` 2.04 -> 1.48, `lift`
1.82 -> 1.59). **The grip guard does not implicate any cell:** the four
`fruit did not follow the gripper` rows the cells drew are the *pre-contact
acquisition* class (fingertip-to-fruit **59-63 mm** at the close, payload never
between the pads), the **control draws the same class at the same signature on
seed 6 (59.4 mm) and 3/147 = 2.0 % of the shipped single-arm corpus does**, and
on every held leg the cells read *lower* payload-in-hand motion (0.08-0.13 m/s
vs the control's 0.07-0.18) and a *lower* place cone (median 0.87-0.88x vs
0.97/0.89x). **S1/S2/S3 fail
the registered E4 on the letter** (one new row each) and were stopped after their
attribution battery; **S13 passes E4 on all four batteries** but **fails E2 on the
acceptance seed 6 (5/10 vs 8/10)** - the two branches draw 4 vs 1 load losses
(Fisher p = 0.30; the shipped line's own two seeds read 4 and 1) - so **nothing is
adopted**. The one positive worth a follow-up is the **two-line**, where S13 is
class-identical to the control and 11 % faster.

---

## 1. What was implemented (three knobs, one union, default off)

`src/fruit_sorting/tasks.py`, the `_SPEED_SHIPPED` / `speed_cell_defaults()` block
(line 99-200) and the seven caps (ten read sites). Each cell sets only the **default string**
of an existing per-leg override, so unset it is byte-identical by construction and
an explicit `FRUIT_DYNAMIC_*` / `FRUIT_RELEASE_*` still wins:

| cell | knob | what it moves | read site |
| --- | --- | --- | --- |
| **S1** | `FRUIT_SPEED_PLACE=0.52` | `place0/1` `v_max` **0.35 -> 0.52**, `a_max` left at the shipped **1.089** | `tasks.py:3542` (`FRUIT_DYNAMIC_PLACE_VMAX`) |
| **S2** | `FRUIT_SPEED_RELEASE=1` | dwell **20 -> 0**, pad hold **3 -> 2**, finger hold **3 -> 2** (`FRUIT_SPEED_RELEASE_SETTLE` moves the settle) | `tasks.py:11931/11937/11950` (+ the resync block 11962) |
| **S3** | `FRUIT_SPEED_LIFT=0.36` | `grasp_lift` `v_max` **0.30 -> 0.36**, `a_max` **1.0 -> 1.9** (the census ceiling; `FRUIT_SPEED_LIFT_AMAX` pins it) | `tasks.py:3516` (`FRUIT_DYNAMIC_LIFT_VMAX/_AMAX`) |
| **S13** | `FRUIT_SPEED_ALL=1` | the union; an explicit single-cell value still wins | - |

A cell value is its own speed in m/s (`FRUIT_SPEED_PLACE=0.61`), or `1`/`on` for
the registered value; `0`/unset is off. **The registered pair is the census's**:
0.52 is inside the **0.61 m/s** ceiling where the `a_max` term starts to bind, so
the cell is a pure speed raise and spends no cone margin (the place's cone budget
is 4.273 m/s²; the delivered cone *fell*, see §5).

**A defect the cell found, and the only behavioural edit:**
`FRUIT_DYNAMIC_PLACE_VMAX` was `min()`'d against the base carry cap
`FRUIT_CARRY_VMAX` (0.38), so the 0.52 cell would have silently resolved to
**0.38** - a **-0.42 s** block, not the census's -1.09 s, with nothing in the log
saying so. The place branch now **assigns** its own cap (documented at the site).
Byte-identical for every recorded configuration: the shipped 0.35 is already
below 0.38 and **no script in the tree sets `FRUIT_CARRY_VMAX`**.

`scripts/225_p44_speed_selftest.py` (new `selfcheck.sh` leg, 0.2 s) pins the
contract offline on the real resolver: unset = the shipped **strings** exactly
(no float round-trip), one knob per cell, `=0` off, S13 = the union with an
explicit cell winning, the numeric form, the `a_max` shape
`a = 0.20*(v/0.15)^2`, and the seven caps / ten read sites by AST (including the
"assigned, not `min()`'d" property). `scripts/selfcheck.sh`: **PASS, 0 failures, 1 skipped** (`logs/selfcheck.log`,
30 checks).

## 2. Default off, proven four ways

| proof | result |
| --- | --- |
| acceptance **seed 5**, C, vs `logs/p43/p2/post_revert_accept_unset.log` | **387/387 `[fruit]` lines identical** |
| acceptance **seed 6**, C, vs `logs/p43/p2/r_accept_A_s6.log` | **388/388 identical** |
| pear **seed 5**, C, vs `logs/p43/p2/d0_pear_A_s5.log` (all `[bed*]` census rows dropped) | **388/388 identical** |
| two-line dense, C, `scripts/190_twoline_gate.sh` | **`fingerprint: matches` `configs/motion_reference_twoline.json`, 8/10, PASS** |
| single-arm motion gate, C, `105 --fingerprint configs/motion_reference.json` | **`fingerprint: matches`**; the only failure is the rate floor (6/10 < 75 %, the shipped branch's own count) |

## 3. The cycle: what each cell buys (acceptance seed 5, all five arms)

`[cycle]` means over 10 attempts, `FRUIT_CYCLE_REPORT=1` on every arm (the
instrument is inside the contrast, AGENTS §3b):

| arm | placed | cnp | no-grasp | s/att | `place` | `release` | `lift` | total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **C** | 6/10 | 4 | 0 | **15.00** | 3.35 | 2.04 | 1.82 | 15.05 |
| **S1** | 6/10 | 3 | 1 | **14.20** | **2.49** | 2.06 | 1.79 | 14.25 |
| **S2** | 6/10 | 3 | 1 | **14.30** | 3.42 | **1.48** | 1.80 | 14.34 |
| **S3** | **8/10** | 1 | 1 | **14.50** | 3.28 | 2.24 | **1.59** | 14.47 |
| **S13** | 6/10 | 4 | 0 | **13.50** | **2.62** | **1.38** | **1.56** | 13.52 |

The leg's own tick count is the cap (the census's rule 1): `grasp_lift`
**168.0 -> 140.9** ticks (S3) / 136.8 (S13, -0.26 s); `place0` **378.4 -> 243.0**
(S1, n=4) / 246.6 (S13, n=7); `place1` **245.8 -> 181.6** (S1, n=5) / 172.3 (S13,
n=3); the place's commanded peak **0.343 -> 0.510 m/s** (0.98 of the 0.52 cap, so
the cell materialised). The release's open-loop holds go **188 -> 112 ticks
(1.57 -> 0.93 s)** on top of the block's untouchable relax ramp and `place low`
retreat.

**Attribution.** Each cell moves *its own* block and only its own: S1's `lift`
-0.03 s from C, S2's `place` +0.07, S3's `release` +0.20 (the last two are branch
draws - neither cell touches those blocks). The residual total deltas differ from the
block sums because the descent/grip blocks re-draw with the supply phase
(S1's descent 2.75 -> 3.01), which is the attractor moving, not a cell.

## 4. E1 / E2, per battery (C vs S13; the single cells have one seed, §8)

| battery | s/att C -> S13 | E1 (>= 1.0 s) | placed C -> S13 | E2 (>= C-1) |
| --- | --- | --- | --- | --- |
| acceptance **seed 5** | 15.00 -> 13.50 (**-1.50**) | PASS | 6 -> 6 | PASS |
| acceptance **seed 6** | 14.60 -> 13.20 (**-1.40**) | PASS (median **-1.45**) | **8 -> 5** | **FAIL** |
| pear **seed 5** | 15.70 -> 13.80 (**-1.90**) | PASS | 6 -> 6 | PASS |
| two-line dense | 9.80 -> 8.70 (**-1.10**) | PASS | 8 -> 8 (left 4/5 + 4/5, right 4/5 + 4/5) | PASS |

The single cells on seed 5: S1 **-0.80**, S2 **-0.70**, S3 **-0.50** s/attempt
(each below the E1 bar - they are the *attribution* arms; their own blocks fall
0.86 / 0.56 / 0.23 s).

## 5. The grip guard (the pillar)

Two instruments, both exact and both printed per attempt by
`logs/p44/p2/p2_report.py`:

* the **closure test** - `tasks.py:11733` appends `fruit did not follow the
  gripper` **iff `not result.grasped`**, so the note is *any* attempt that ends
  without the payload in the hand, including one that never had it;
* the **class split** - `grasped` (was it ever held), and the **jaw-to-fruit
  distance at the release row** (`over the output belt: jaw=... fruit=...`),
  which is bimodal with no overlap: **0.065-0.067 m** when the payload is in the
  hand, **0.70-1.27 m** when it left earlier.

| arm (battery) | notes | no-grasp | **held-then-lost** (W8-B carry class) | re-seats | place cone (held legs) | in-hand \|v\|max (held place legs) |
| --- | --- | --- | --- | --- | --- | --- |
| C (acc s5) | 0 | 0 | **4/10** | 0 | 0.97x | 0.07-0.18 |
| S1 (acc s5) | **1** | 1 | 3/10 | 0 | **0.87x** | **0.09-0.11** |
| S2 (acc s5) | **1** | 1 | 3/10 | 0 | **0.87x** | 0.08-0.20 |
| S3 (acc s5) | **1** | 1 | **1/10** | 0 | **0.88x** | 0.07-0.17 |
| **S13** (acc s5) | **0** | 0 | **4/10** | 0 | **0.87x** | **0.09-0.13** |
| C (acc s6) | 1 | 1 | **1/10** | 0 | 0.89x | 0.08-0.17 |
| **S13** (acc s6) | **1** | 1 | **4/10** | 0 | 0.87x | **0.08-0.11** |
| C (pear) | 0 | 0 | 4/10 | 0 | 1.20x (2 over) | - |
| **S13** (pear) | **0** | 0 | 4/10 | 0 | **0.99x (0 over)** | - |
| C (two-line) | **2** | 2 | 0/10 | 0 | 2.49x | - |
| **S13** (two-line) | **2** | 2 | 0/10 | 0 | 3.12x | - |

**Every row in the whole battery is one class, and the signature names it.** All
five single-arm note-rows read **fingertip-to-fruit 59-63 mm at the close** - the
moving catch fired with the fruit ~6 cm away, the pads closed on air (S1: close
span 70.1 mm around a 55.8 mm fruit, closed to 61.7 mm; S3: 42.5 mm around a
29.6 mm fruit, closed to 27.1 mm; C s6: 39.2 mm around a 31.4 mm fruit, closed to
26.3 mm), two re-seats each, `lift +0.000..+0.004 m`. That is the **pre-contact
acquisition** class (the W7-B no-contact class / the R10 lead shortfall), not a
grip-magnitude event. **The control's own row has the identical signature**
(seed 6 attempt 0: 59.4 mm), and S13's seed-6 row is that **same attempt bit-for-bit
through the grip** (same close force 35.85 N, same span, same pads, same
`F[0.00,18.62]`; only the lift leg differs, 82 vs 101 ticks - the faster profile
doing its job).

**The base rate on the shipped line is 2.0 %/attempt, so 1/10 is not signal.**
Shipped profile (P41), default knobs, single-arm scripted acceptance + pear logs
from P41/P42/P43 (`p41/p2/accept_profile`, `pear_profile`, `p41/p3/accept_control`,
`p42/p2/control_accept`, `pear_control`, `p43/p2/d0_accept_A_s5`,
`d0_pear_A_s5`, `post_revert_*`, `r_accept_*`, `r_pear_*`): **3 / 147 = 2.0 %**
(acceptance 2/87, pear 1/60). The two-line record's own rate is **2/10 = 20 %**
(`logs/p41/p2/twoline_profile.log`) - and both of my two-line arms read **2/10**,
on the same two attempts.

**The load itself is not worse - it is better.** On the place legs the payload
survived, the cells read **lower** payload-in-hand motion (**0.08-0.13** vs
0.07-0.18 m/s; S13's seeds are 0.09-0.13 and 0.08-0.11, C's 0.07-0.18 and
0.08-0.17) and a **lower** place cone (**median 0.87-0.88x** against C's
0.97/0.89x), with one leg each at 1.24-1.29x on S2/S13 against C's own worst held
place leg at 1.16x: a shorter leg at the same `a_max` spends a smaller share of
its acceleration budget, and the fastest place is also the *cleanest* one. The escape signature is unchanged in kind (lost legs read
0.45-2.03 m/s in-hand, a clean separation from the 0.20 m/s maximum on the held
legs) and its count is branch-dominated: C's own two seeds read **4 and 1**, and
the pooled C 5/20 vs S13 8/20 is **Fisher p = 0.50** (seed 6 alone 1 vs 4, p = 0.30).

**F1 and the force-delta remedy.** The registered rule ("any new grip-loss row
fails the cell") **fires on S1, S2 and S3** and does not fire on S13, so S1/S2/S3
were stopped after the attribution battery (§8). The mechanism does **not**
support the ForceDelta layer as the remedy: a force-derived pose residual acts
*after contact on the carried segment*, and every row measured here is a
**pre-contact** failure (payload never in the hand), while the carried segment
reads *better* on both instruments. What the rows justify is the **acquisition**
path - the named W7-B lead/ACQ item and the R2 reach-edge refusals - not a carry
correction layer. That statement is the honest one; the letter's verdict still
stands and S1/S2/S3 are not adopted.

## 6. E3 (the motion gate), E5 (the two-line), E6

**E3 - no motion budget fails anywhere** (`gates.txt`). All 11 logs: descent
`|v|max` **0.108-0.130** m/s against a 0.160-0.161 budget, lurch **0.017-0.021**
m/s/tick against 0.2915, no over-budget leg. C matches both per-scenario
fingerprints (§2). The moved arms' fingerprints **differ by construction** - the
fingerprint contains each leg's `|v|max`, which is exactly what a speed cell
changes - so a moved arm needs its own reference (a `configs/` write, out of this
phase's scope). **One reported (not gated) change:** the `>= 0.45 m/s` hand
convention is now spent by the place cell - C 3/20 legs over, **S1 11/19, S13
11/20** - at the profile's own commanded 0.51 m/s. That is the census's "0.45 is
just above the fastest carry profile (0.371)" being knowingly breached: if that
0.45 is a hardware proxy, the place cell pays it.

**E5 - the two-line is the positive.** `scripts/186_w6_report.py`:

| two-line dense, seed 5 | C | **S13** |
| --- | --- | --- |
| placed | 8/10 (left 4/5, right 4/5) | **8/10 (left 4/5, right 4/5)** |
| batch span / `s/attempt` | 98.0 s / 9.80 | **87.5 s / 8.70 (-11 %)** |
| pooled inter-placement interval | 9.13 s mean / 8.10 p50 | **8.27 s / 4.90** |
| throughput batch / window | 4.90 / 6.57 placed/min | **5.49 / 7.25 placed/min** |
| `190` | **PASS** (fingerprint matches, 80 %) | floor PASS (80 %), **fingerprint differs** (moved profile) |
| guard | 2 notes, 0 load losses | **2 notes, 0 load losses - the same two attempts** |

So E5 passes on placed, interval and floor; the fingerprint item is the moved
configuration, not a break. The cone is reported, not gated, on this line
(C 2.49x, S13 3.12x - the belt-riding catch class, unchanged in outcome).

**E6 - no new failure reason** in any arm of any battery: every row is
`fruit did not follow the gripper`, which is in the reason parser's baseline set.

**F4 - the release cut does not lose the payload.** Every held-then-lost attempt
reads **jaw-fruit 0.70-1.27 m at the release row** (and the pear's C losses land
on the floor at z = 0.023-0.041 while S13's are still mid-air at z = 1.20) - i.e.
the payload was gone **upstream** of the release, and the accompanied `place low`
drop completed on every held attempt (`placed` 6/10 = the held-and-survived
count). S2/S13 take -0.56/-0.66 s (-0.90 on seed 6) from the release block with
**no** release-time loss.

## 7. Verdicts

| | S1 place | S2 release | S3 lift | **S13 union** |
| --- | --- | --- | --- | --- |
| **E1** `s/attempt` >= 1.0 s | **FAIL** (-0.80) | **FAIL** (-0.70) | **FAIL** (-0.50) | **PASS (-1.45 median)** |
| **E2** `placed` >= C-1 | PASS (6=6) | PASS (6=6) | PASS (8>6) | **FAIL** (seed 6: 5 vs 8) |
| **E3** motion gate | PASS | PASS | PASS | PASS (hand-0.45 note) |
| **E4** grip guard | **FAIL (F1)** | **FAIL (F1)** | **FAIL (F1)** | **PASS** (0 vs 0 s5; 1 vs 1 s6, same attempt; 2 vs 2 two-line; 0 vs 0 pear) |
| **E5** two-line | n/r | n/r | n/r | **PASS** behaviour / fingerprint = moved config |
| **E6** failure reasons | PASS | PASS | PASS | PASS |
| **F1** new grip row | **FIRES** | **FIRES** | **FIRES** | does not fire |
| **F2** motion budget | - | - | - | - |
| **F3** placed ->> 1 | - | - | - | **FIRES** (seed 6) |
| **F4** release loses payload | - | - | - | - |
| **F5** new reason | - | - | - | - |
| **adopted** | no | no | no | **no** |

**Nothing is adopted; every cell stays default off.** The union delivers a real
**-10 % cycle** (-1.45 s/attempt on the acceptance, -1.90 on the pear, -11 % on
the two-line with +12 % throughput) and a *cleaner* grip read, but the
acceptance seed 6 places 5/10 against the control's 8/10 - 4 load losses vs 1, in
different branches, with the shipped line's own two seeds reading 4 and 1 - so
E2/F3 fails and the adoption candidate cannot ship on this evidence. The named
next spend is a **placed-count** measurement at the WS-4.2 N (>= 5 seeds per arm)
on the acceptance, since the class that decides E2 swings 4x within one
configuration; the *timing* and the *two-line* are already positive.

## 8. Deviations, and what this does not claim

* **The single cells ran one battery (acceptance seed 5) only.** F1 fires on each
  of them, and the instruction for this phase is "stop that cell". Their
  per-block attribution, their placed count and their guard read are complete;
  their E1 (needs two seeds), E2 (needs the pear/two-line) and E5 are **not
  evaluable** - S13, the adoption candidate, carries the full grid. Justification
  for not stopping S13 too: its guard read is **parity with the same-battery
  control on every battery**, and the rows are the 2.0 %-per-attempt control class.
* **The note is a closure test, not a slip test** (`tasks.py:11733`): it fires for
  any attempt ending without the payload. Reading it as "the carry class" would
  have charged the cells for the acquisition class; §5's class split is the
  correction, and every row is quoted with its signature.
* **No rate is compared across branches** (AGENTS §2): the placed counts above are
  per-branch draws, and the cells *move the branch* because they change the cycle
  phase the attempt-relative feeder sees (`diverted` 0/1, first divergence often
  attempt 0-1). The timing endpoints (E1) and the per-leg/per-class reads are the
  comparisons; the placed counts are quoted as the battery's own counts, not as a
  rate.
* **Not measured here**: the force-delta/pose-residual layer (scoped out by PREREG
  §1 and not justified by §5), a reference re-record for the moved arms (a
  `configs/` change), the joint-limit/gain cells (the census closed them: 2.1x /
  2.4x headroom and no duration effect), and the direct/policy interface (the
  scripted primitive owns all three blocks; the policy path would need its own
  arm).
