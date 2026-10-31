# P77 pre-registration — the 60 N clamp at three seeds, as a **force-ceiling
# sensitivity** (owner-chosen cell)

Written and md5-pinned **before any measured run**. Nothing is adopted, no
default changes, no commit, `configs/*` untouched. This is **evidence**, not a
shipping claim: the product is the answer to *does the class the prys belong to
convert at the population level at 60 N, and what would shipping it cost?*

---

## 0. The question, and the honesty frame (carried into the report's first line)

`logs/p76/RESULTS.md` measured, on the direct line, that the pads' 98.1 mm
travel stop needs **more than 30 N** (the same 6.8 cm pear reads `place0
sep_max` 98.1 / 98.1 / 98.1 / 98.3 mm at 10 / 15 / 20 / 30 N, 25.7-31.2 mm
wider than the command), is **gone at 45 N** (0/26 legs past 95 mm, corpus max
90.4 mm) but the payload **still leaves** (829.5 mm), and that only **60 N**
gives **0/26 pried and 0/26 escaped** (pear `sep_max` 75.2 mm, slip 0.0 mm), with
the crush guard reading **0 legs** at every rung - the 3.6 cm strawberry held at a
36.1 mm span under a **60.16 N** pinch (`sep@loss - dia` **+0.5 mm**) and placed.
That was **one seed, one draw**, and P76 licensed a plan, not an adoption.

**60 N is jaw-feasible but not fruit-feasible and this sim cannot tell the
difference.** Commercial parallel jaws in this class deliver 20-235 N, so the
*number* is not absurd for the hardware; but a 60 N pinch on a 3.6 cm berry
**would bruise it in reality**, and this simulator has **no bruise model,
no damage model and no compliance model for the flesh**. A clean read here is a
statement about **geometry and retention** - does the payload stay between the
pads - and *not* about fruit quality. That is why this cell is a **sensitivity**
and not a decision to ship.

## 1. Arms, batch shape, and the manipulation check

**Two arms, the one variable `FRUIT_FINGER_MAXFORCE`** (the per-joint
`UsdPhysicsDriveAPI:linear.maxForce` the build writes on `joint1` of both arms;
`scene.resolve_finger_maxforce` / `apply_finger_maxforce`; `joint2` is a
drive-less mimic and is never written):

| arm | env | nominal delivered pinch (P41's law: pinch ≈ cap) |
|---|---|---|
| **C** (shipped control) | `FRUIT_FINGER_MAXFORCE` **unset** = the asset's 10 N | ~9.8 N |
| **T** (treatment) | `FRUIT_FINGER_MAXFORCE=60` | ~54-60 N (P76 measured `force_min` 55.40 / 54.17 N on the pear, 53.9 N held median) |

**Batch: seeds 77 / 101 / 202, 15 picks each, arms interleaved by seed** so each
treatment cell is read against an immediately adjacent control cell. Order
within a seed alternates by seed - **77: C→T, 101: T→C, 202: C→T** - so any
monotone wall-clock/thermal drift is balanced across the batch rather than
loading onto one arm. One claim per cell (`scripts/154_claim_run.sh`, no
overlapping simulator).

**The scenario is the P66-phase-3 / P71-phase-2 / P73 / P74 / P75 / P76 cell
verbatim** (so C is comparable to those corpora and to P76's F10):

```
HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1
FRUIT_NO_SLEEP=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival
FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11
FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1
checkpoint checkpoints/moe_v13s/policy_best.pt (61da390a),
--presentation direct --episodes 15 --seeds <seed>
```

**The instrument is identical in both arms** (AGENTS §3b: instrument inside one
batch). No `FRUIT_PLACE_ONSET_TRACE` (super-linear cost, does not cover the
lift-leg firing site). No other knob is set; every shipped default stands
(P43 park `back`, P54 ACQ on, P58 direct supply profile, P66 lift `-0.08`, P71
rails `none`).

**Manipulation check, required in both arms and quoted in the report:**

1. the **build print** - `finger drive profile=... maxForce=<cap>/0.0N` and, for
   T only, `FRUIT_FINGER_MAXFORCE=60 N -> openarm_left_finger_joint1=60, ...`;
2. the **live articulation read-back** `[drive] ... finger drive maxForce
   readback joint1/joint2=<cap>/0.0 N` and the manifest's
   `physics.finger_drive.readback_matches`;
3. the **behavioural consequence** - the held-leg `force_min` median per arm,
   which P41/P76 measured at 85-99 % of the cap.

A cell whose (1) and (2) disagree with its label is **not evaluable** and is
re-run. C is the unset path: its build string is the shipped `10.0` and its
`[drive]` read-back row is absent by construction (P41 made it default-off), so
C is checked as the unset path rather than failing that clause.

## 2. Endpoints

### 2.1 Primary — the left's placed count and its carried-not-placed class

* **left placed** = episodes with `arm=left` and `placed=True`, pooled over the
  three seeds, with the per-seed counts printed beside the pool.
* **left cnp** (`carried-not-placed`) = `grasped=True, placed=False`.
* **left never-held** = `grasped=False` (named separately, never folded into
  cnp: it is the acquisition class, P47/P48).
* **the pairing that can be defended.** The direct loop is **not reproducible**
  (rendered frames), so the fruit stream diverges as soon as one outcome
  differs. A match is therefore defined **only** on
  `(seed, arm=left, species, diameter to 0.1 cm)`, greedily one-to-one, and it
  is reported as a **descriptor with its own n** - because it is conditioned on
  a post-treatment variable (the fruit presented depends on the earlier
  outcomes). **What cannot be paired is said out loud**: any fruit that appears
  in one arm and not the other, and every pair involving a species/diameter
  change, is **unpairable** and reported as such; no paired rate is quoted as
  the primary.
* **the design-valid count reads** are (a) the **run level** (three seed pairs,
  exact sign test; its minimum attainable p at N=3 is 0.125 and that is stated),
  and (b) the **class-standardised** left placed rate - the per-class
  (`species` x diameter bucket) rates measured in T, weighted by C's class mix -
  so a class/draw shift cannot manufacture a delta (the P36/P43 rule).

### 2.2 Mechanism — the pry, the escape, the force, the strawberry

Per `[carry]` leg, from the existing default-off `[carry]` fields
(`FRUIT_CARRY_DIAG=1` in **both** arms), with P76's definitions unchanged:

* **pried leg** = `sep_max >= 95.0 mm` (within 3.1 mm of the 98.1 mm open stop),
  escape or not;
* **escape leg** = `clean_slip_max > 100 mm` **with a pinch** (`fmax > 0`);
  the `> 800 mm` form is printed beside it (P74: that threshold is not
  speed-invariant - here the profile is constant, so both are reported and the
  100 mm form is the mechanism count);
* **held `force_min` median** per arm (non-escape legs with `force_min > 0`) -
  the delivered pinch;
* **the strawberry's own numbers** in both arms: `dia`, `sep@loss`,
  `sep@loss - dia`, `sep_max`, `gap@sep_max`, `fmax`, `force_min`, outcome -
  the smallest class is the one a higher clamp would damage first, and it is the
  one P76 measured at the 60 N ceiling.
* **crush guards** (P76 §4.2, unchanged): C1 `sep@loss - dia <= -15 mm` on a
  physical, pinched leg; C2 `force_min >= 35 N` on an escape leg.

### 2.3 Guards

* **the right arm** - placed and escapes; the treatment is expected to be a
  **partial** no-op there (P66 measured the right at 88-100 % of its own branch
  spread with the lift lever, and its own carry class is already 0 in the park
  corpus), so "not worse" is read as *no new class and placed within 1 attempt
  of C*, never as flat.
* **the failure ledger by class** - every note string counted per arm; **any
  note that appears in T and not in C is a new failure reason and is a finding**
  (it is not silently absorbed).
* **the landing class** - `did not land` / `fell off the line` / `discharged`
  (the notes that mean the payload reached the wrong place), per arm.
* **the arm mix per seed** - the left/right attempt split, because the direct
  env sets `arm = left if grade == "A"` (`rl_env.py:2516`), so arm, grade and
  lane are one variable and the split drifts with the branch.
* **cycle ticks** - median episode ticks per arm (a cost read; a count across
  arms is not a rate).

## 3. Decision rule, fixed before the run

**What "converts" means, in two separate statements - the mechanism one is the
claim, the count one is a paired report:**

**(M) Converts at the mechanism level** iff **all** of:

1. T's pooled **left escape legs** (`clean_slip_max > 100 mm`, pinched) are
   **<= 1/3 of C's** (i.e. at most a third as many), and
2. T's pooled **left pried legs** (`sep_max >= 95 mm`) are **<= 1/3 of C's**, and
3. T has **zero crush legs** (C1 or C2) - a mechanism win bought by crushing the
   smallest fruit is not a win, and
4. C's left escape count is **> 0**; if C has none, endpoint (1) is **not
   evaluable** and only the pry (2) carries the mechanism statement (the P76
   "empty escape set is not a pass" ambiguity rule, applied to the control).

**(N) Converts at the count level** iff **also**:

5. T's pooled **left placed** is **higher** than C's and T's pooled **left cnp**
   is **lower**, with the **run level not against it** - the left placed delta
   is `>= 0` in **at least 2 of 3** seeds - and
6. the **right is not worse**: right placed within **1 attempt** of C and no new
   right failure reason, and
7. the class-standardised left placed rate moves in the **same direction** as
   the raw pooled one (so the delta is not a class-draw artifact).

**Amendments are allowed only before the run they govern, and are appended
below with their own md5.** The rule above is not re-read after the data.

**The reading discipline the report must carry:** a count across arms is still a
count across **attractors** (AGENTS §2) - the direct loop conditions on rendered
frames, so each cell is one draw of a non-reproducible branch and the pooled
counts are **a paired outcome with its n**, never a rate. The **per-leg
mechanism rows** (pry / escape / force / strawberry) are the claim; the counts
are the report.

## 4. The price of an adoption (report only - nothing is re-recorded)

Two runs at 60 N, each read against the **current** reference without writing a
new one, to tell the owner what a flip would cost:

* **P1 - the scripted line**: one `scripts/accept.sh` at
  `FRUIT_FINGER_MAXFORCE=60`, compared with `logs/p76/accept_noharm_full.log`
  (the shipped-cap record: **346 `[fruit]` lines**, md5 `d0079a23`): does the
  `[fruit]` stream move, and does `scripts/105_motion_regression.py` report
  `fingerprint: matches` against `configs/motion_reference.json` (`8952c320`)?
* **P2 - the two-line**: one `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10
  FRUIT_MOTION_REPORT=1` run at 60 N, reported against
  `configs/motion_reference_twoline.json` (`eb697f23`) via
  `scripts/190_twoline_gate.sh` - again **without re-recording**.

These are a **price**, not a pass/fail: a cap change is global (both arms, both
presentations, every store's provenance), so a moved branch here means *a flip
would owe three references and a store re-baseline* (P76 §6.2), which is the
expensive item the owner must weigh against M/N.

## 5. What this phase cannot say

* **Nothing about fruit quality.** No bruise/damage model exists; a clean 60 N
  read is geometry and retention only (§0).
* **Nothing about a real jaw.** The sim's number is 60 N **per joint** with the
  delivered pinch ≈ cap; whether a real 2F-85-class jaw holds this geometry at
  that force, with these pad faces, is not measured here (P41/P42's
  `SIM_LIMIT.md` face-geometry sanction stands).
* **Nothing about the scripted line's buys.** The scripted dynamic line is a
  different scenario; P1 only measures whether a 60 N cap *moves* its branch.
* **No adoption.** `FRUIT_FINGER_MAXFORCE` stays default off (10 N); no
  `src/`, `configs/` or reference change is made by this phase.

## 6. Run log (filled after the runs)

Cells, wall clock, and any re-run are recorded in `logs/p77/header.txt`
(`run_p77.sh` writes the pin block per batch) and in `RESULTS.md` §1.
