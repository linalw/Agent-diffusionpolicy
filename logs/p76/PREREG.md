# P76 pre-registration — the clamp force at which the **pry** stops, per class,
# and the force at which the **smallest** fruit is crushed

Written and md5-pinned **before any measured run**. Nothing is adopted, no
default moves, `configs/*` is untouched. This is a **measurement** phase whose
product is one number for the owner: *the sim needs X N to stop the pry; a real
jaw would have to deliver X*.

---

## 0. The question, and why it is a force question again

`logs/p75/RESULTS.md` refuted both P41/P42 readings of *how* the left place leg
loses its payload: it is not a slide at constant pad separation (`sep` is
constant to the print for 110 ticks and then **rises**), and it is not a command
transient (0/26 legs step `|Δv_cmd|`). It is an **expulsion**: the force
collapses in two ticks (5.03 → 4.11 → 0.00 N) and the pads are driven to their
**98.1 mm mechanical open stop in 9 ticks while the force servo closes the
command** (68.7 → 66.7 mm).

A pry is a **force-vs-geometry contest**, and the force side has never been
measured on the **direct** line at anything between 10 N (shipped) and 30 N.
P41's ladder is scripted-only, has a **20 mm gap between 10 and 30 N**, and its
top rung crushes a 3.7 cm strawberry:

| P41 rung | `sep_max` on escape legs | outcome |
|---|---|---|
| 10 N (shipped) | **98.5** / 76.0 / 77.4 / 64.2 mm | 6/10, left 1/5 |
| 30 N | **43.5** / 42.2 mm | 8/9, left 2/3 |
| 60 N | **31.2** / 39.0 mm | 9/10, left 3/3, **strawberry crushed** (`clean_slip` 641 mm at `F@onset` 62.3 N) |

So the number the owner asked for lives between 10 and 30 N, and the crush
threshold lives between 30 and 60 N. **This phase brackets both.**

## 1. The variable, and the manipulation check

`FRUIT_FINGER_MAXFORCE` — the per-joint `UsdPhysicsDriveAPI:linear.maxForce` the
build writes on `joint1` of both arms, **default off** (`scene.py`
`resolve_finger_maxforce` / `apply_finger_maxforce`), i.e. an unset run keeps
the asset's own 10 N. `joint2` is a drive-less `PhysxMimicJointAPI` mimic and is
never written. Per P41 phase 2, the delivered pinch tracks the cap ~1:1, so
**the rung *is* the delivered force**.

**Ladder (one seed first, as instructed):**

| rung | env | expected delivered pinch (P41's law) |
|---|---|---|
| **F10** (shipped control) | `FRUIT_FINGER_MAXFORCE` **unset** | ~9.8 N |
| **F15** | `=15` | ~14.9 N |
| **F20** | `=20` | ~19.9 N |
| **F30** | `=30` | ~29.9 N |

Seed **77**, 15 picks, one claim per run. A second seed is added **only** if a
rung's read is ambiguous (§5).

**Manipulation check, quoted for every rung (both, per the instruction):**

1. the **build print** — `finger drive profile=... maxForce=<cap>/0.0N ... |
   FRUIT_FINGER_MAXFORCE=<cap> N -> openarm_left_finger_joint1=<cap>, ...`;
2. the **manifest's `physics` block** — `finger_drive.readback_matches: true`
   with `maxForce` = the rung on both `joint1`s (the runtime articulation
   read-back, P41 phase 4), and `physics.finger_drive.joints[*].maxForce`;
3. the in-log **held-leg pinch** (`force_min` median on placed legs) — the
   behavioural consequence of (1)-(2), quoted as a sanity band, never as the
   proof.

A rung whose (1) and (2) disagree with its label is **not evaluable** and is
re-run.

## 2. The scenario, held fixed

The P66-phase-3 / P71-phase-2 / P73 / P74 / P75 cell verbatim, so the control
rung is comparable to those corpora:

```
HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1
FRUIT_NO_SLEEP=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival
FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11
FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1
checkpoint moe_v13s 61da390a, --presentation direct --episodes 15 --seeds 77
```

**The instrument is identical in every arm** (the AGENTS rule: instrument inside
one batch). No `FRUIT_PLACE_ONSET_TRACE` (it costs super-linearly and does not
cover the lift-leg firing site).

## 3. The instrument (one new default-off field group, `[carry]`)

Five reporting-only fields, inside the existing `if guard_armed:` block
(`FRUIT_CARRY_DIAG=1`), so the unset path stays byte-inert:

| field | meaning | why |
|---|---|---|
| `dia=<mm>` | the fruit's own class width (`sample.diameter`) | the crush denominator, per fruit |
| `sep_max=<mm>@t<row>` | running **max** measured pad separation over the leg, and its tick | the pry: `sep@loss` is read at the *loss* tick and the pads reach the stop **9 ticks later**, so mean/max must be accumulated |
| `gap@sep_max=<mm>` | the **commanded** gap at the tick of `sep_max` | "pads driven open while the command closes" - P75's ordering, now per leg |
| `sep_min=<mm>` | running **min** measured separation | interference: crushing drives the pads *below* the fruit's own width |
| `fmax=<N>` | running **max** tactile pinch | the crush's other side: a payload lost with the force **not** collapsed |

`sep` is `arm.jaw_separation()` (link-origin distance, the **same instrument** as
`sep@onset`/`sep@loss`/`sep_end` and as P41's offline `sep_max`, so the numbers
are directly comparable to the 98.1 mm stop). Cost: two prim world-pose reads
per guarded tick; the control rung carries it too, so it cancels across rungs.
Pinned by a new `scripts/243_p76_sep_selftest.py` selfcheck leg.

## 4. Endpoints and the rule

### 4.1 Primary — does the pry stop, per escape leg

* **escape leg** = a `[carry]` leg with `clean_slip_max > 100 mm` (P74's
  mechanism count; the `> 800 mm` form is reported beside it).
* **`sep_max`** on each escape leg, in mm, against the **98.1 mm open stop**
  (read live in P75).
* **"at the stop"** (pre-registered): `sep_max >= 95.0 mm`, i.e. within 3.1 mm of
  the stop - the stop is a hard mechanical limit, so anything above 95 is the
  pads' travel exhausted, not a span.
* **"still gripping"** band: `sep_max` in **[40, 70] mm** - the `_pad_standoff`
  command (`_pad_standoff(True) = FRUIT_FINGER_LEN 0.060 + PAD_LIFT 0.010 =
  70.0 mm`) minus the servo's own closed form (42-54 mm measured on
  payload-lost legs). A leg **in** this band lost its payload with the pads
  inside a plausible holding gap.
* **A rung "stops the pry"** when **no** escape leg on the ladder reaches the
  stop (`sep_max >= 95 mm` on 0 escape legs). Ambiguity (a single leg in
  90-95 mm) adds the second seed.
* Also reported per escape leg: `sep@loss`, `sep_end`, `gap@sep_max`, `fmax`,
  `force_min`, the fruit class and the arm.

### 4.2 The crush guard — per fruit, the strawberry is the binding case

A fruit is **crushed** when the pads' span collapses through its own width while
the force stays high. Two observable forms, **either** counts:

* **(C1) interference** — `sep_min <= dia - 15 mm`: the pads are driven 15 mm
  inside the fruit's own class width. 15 mm is 3x the compliant pad's own travel
  (`FRUIT_FINGER_COMPLIANCE` 30000 N/m at the ~10 N pinch deforms ~0.3 mm; the
  asset's pad body travel is 5 mm), so it cannot be pad compliance.
* **(C2) high force, payload gone** — an escape leg (`clean_slip_max > 100 mm`)
  with `force_min >= 35 N`: the payload left **without** the force collapsing,
  which is P41's 60 N signature (641 mm slip at 62.3 N onset) and the opposite
  of the pry's `F -> 0`.

**Reported at every rung, explicitly:** the **strawberry** (class width
3.6-4.2 cm, `FRUIT_SHAPES["strawberry"]` the smallest class) — its `dia`,
`sep_min`, `sep_max`, `fmax`, `force_min` and outcome, and the same five numbers
for every other class that appears. **The crush threshold is the *lowest* rung at
which any class shows C1 or C2**; the strawberry is quoted separately because it
is the width that binds first.

### 4.3 Counts — reported, never gated

Left/right placed per rung, the class split (`placed` / `cnp` / `never-held` /
`fell off` / `did not land`), the arm mix, and `s/attempt`. **A count across
rungs compares attractors** (AGENTS §2): the direct loop is not reproducible
(rendered frames), each rung is a different branch as soon as one fruit is
placed differently, so these are descriptive only. No rate is quoted as a result.

## 5. Decision rule, fixed before the run

1. If **some rung** has **0 escape legs at the stop** (§4.1) **and 0 crushed
   legs** (§4.2) → write the phase-2 plan: 3 seeds x 15, the paired
   carried-class endpoint (`cnp` per arm, `FRUIT_CARRY_DIAG=1` on both arms),
   and the no-harm pairs (scripted `accept.sh` 346/346 `[fruit]` lines +
   `fingerprint: matches`; one two-line run + `scripts/190_twoline_gate.sh`) -
   at the **lowest** such rung, because the cost is force headroom against the
   smallest fruit.
2. If the pry stops **only** at a rung that also crushes a fruit → no rung is
   admissible; the deliverable is the **bracket** (pry stops at >= X, crush at
   <= Y, X > Y) and the phase closes with the face-geometry lever
   (`SIM_LIMIT.md`'s new-pad-asset sanction) named as the only remaining one.
3. If no rung stops the pry → the pry is not force-limited on this interface at
   10-30 N, which contradicts P41's scripted ladder read and is itself the
   finding (the direct line's landing geometry would then differ from the
   scripted one); report the ladder's `sep_max` curve and close.

**Ambiguity rule:** a rung whose escape set is **empty** is **not** a pass (no
evidence) - it needs the second seed (101) before it can be read as "the pry
stopped". A rung with 1-2 escape legs and a `sep_max` inside 90-95 mm gets the
same treatment.

## 6. What this phase cannot say

* **A raised cap is not "physical" until a real jaw is anchored to it.** The
  deliverable is "the sim needs X N; a real jaw would have to deliver X" - the
  `SIM_LIMIT.md` sanction. Nothing here says a real jaw can.
* A cap is **global** (both arms, both presentations): a rung that helps the
  left does not by itself justify a shipped default.
* P41 already measured the class **not converting** at 30 N on the scripted
  battery (pear 4/10, two-line 6/10) - a successful rung here re-opens only the
  *mechanism* (does the pry stop), not a rate claim.

---

## Amendment A1 (recorded 2026-10-31, **before any counted rung**)

**`sep_min` is the *loaded* span.** The first instrument accumulated the leg's
minimum pad separation unconditionally, and the first (discarded) partial run at
10 N showed why that is not well posed: on a shipped escape leg the payload is
already gone when the force servo closes the pads onto nothing, so `sep_end`
reads **51.9 mm inside a 68.3 mm fruit** (`sep_min - dia = -16.4 mm`) - the
unconditional minimum would fire the crush rule on **every** escape leg. It is
therefore taken **only while the tactile pinch is loaded** (`force_now > 0`), and
a leg with no loaded tick prints `n/a` (a payload that was never in the pinch
cannot be crushed by it).

No counted run existed when this was written: the 10 N cell was stopped at 8/15
episodes, its log is kept as `logs/p76/direct/DISCARDED_F10_pre_a1.log`, and the
ladder was re-run from scratch on the amended tree. The **thresholds and
endpoints are unchanged** (`sep_min <= dia - 15 mm`, `force_min >= 35 N`,
`sep_max >= 95 mm`, `clean_slip_max > 100 mm`); only the quantity the first one
is measured over is stated.

---

## Amendment A2 (recorded 2026-10-31, **before the run it names**, after the
## four-rung seed-77 ladder was read)

The ladder's own result (10/15/20/30 N at seed 77) puts **no rung above 30 N**
anywhere: the crush rule never fires, and the smallest fruit that is carried at
every rung (a 3.6 cm strawberry) reads `sep_min - dia` **+3.3 / +3.3 / +2.7 mm**
at 15/20/30 N, i.e. the pads never travel into its own width. P41's crush point
is **60 N on the scripted line**, so the owner's crush number is an **open upper
bracket** until the direct line is measured at that rung.

**A2 registers two DECLARED EXTENSION cells, not rungs** (P75's A4 convention -
they are not part of the registered ladder, no count from them is a result):

* **`F60`**, seed 77: the rung P41 measured a strawberry crush at. It closes the
  bracket at the top: if it crushes, the crush threshold is in **(30, 60] N**;
  if it does not, P41's crush does not reproduce on this interface and the
  threshold is **> 60 N**.
* **`F45`**, seed 77: run **only if `F60` crushes**, to halve the bracket.

Both carry the identical instrument and scenario; `F45`/`F60` add no threshold,
no endpoint and no rule - §4 is unchanged, and a crush leg in either is read by
the same C1/C2 definitions.

---

## Amendment A4 (recorded 2026-10-31, **after `F60` was read, before `F45` runs**)

`F60` came back **clean on both endpoints**: 0 of 26 carry legs pried to the stop
(`sep_max` max on the corpus **< 95 mm**), **0 escape legs**, **0 crushed**, 13/15
placed, and the smallest fruit (3.6 cm strawberry) held at **36.1 mm** span under a
**60.16 N** pinch (`loss-interference +0.5 mm`). So:

* the **pry threshold lies in (30, 60] N** - 30 N still pried an apple to 98.2 mm
  and lost it (116.9 m ejection) at seed 101, 60 N pried nothing;
* **P41's 60 N strawberry crush does not reproduce on the direct line** - the
  3.6 cm fruit is *held* at 60 N here, so that crush was a **seating** event (the
  pads driven to 10 mm around a 37 mm fruit), not a force threshold.

A2 made `F45` conditional on a `F60` crush, which did not happen; the bisection is
therefore registered **here** as a third declared extension cell, for the same
reason A2 registered the first two - to narrow the one number the owner asked for:

* **`F45`**, seed 77: if the pry is gone there too, the threshold is in **(30, 45]
  N**; if a leg still reaches the stop, it is in **(45, 60] N**. Same instrument,
  same scenario, same C1/C2 crush rule; no count from it is a result.

---

## Amendment A3 (recorded 2026-10-31, after the seed-77 ladder and the seed-101
## F20 cell, **before the remaining seed-101 cells were read**)

**An escape leg must have had a pinch.** The seed-101 F20 cell contains a
strawberry `grasp_lift` leg whose `clean_slip_max` is **308 215 mm (308 m)** with
`fmax = 0.00 N` - a payload that was **never in the pinch** and whose position
was recycled/teleported, so its "slip" is a bookkeeping artifact, not motion.
The registered rules would count it as an escape (`slip > 100 mm`) and then ask
whether its pads reached the stop (they read 10.4 mm - pads closed on air).

The counting rule is therefore: **a leg is an escape leg only if `fmax > 0`**
(a pinch existed). A leg with `fmax == 0` is the **never-held** class already
used across this project (P43/P60), is listed separately, and its slip is not
read. This changes no threshold, adds no endpoint, and removes an artifact; the
legs it removes are named in `RESULTS.md`.
