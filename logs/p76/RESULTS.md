# P76 results — the pry needs **more than 30 N** and the payload **more than 45 N**;
# the smallest fruit is **not crushed at 60 N** on the direct line

**Measurement phase.** One default-off diagnostic field group on the `[carry]`
row, a four-rung clamp-force ladder (10 / 15 / 20 / 30 N) at two seeds, and three
**declared extension cells** (45 / 60 N) that were registered before they ran. **Nothing adopted, no
default changed, `configs/*` untouched, no commit.** The rule and its three
amendments were pinned before the runs they govern (`PREREG.md`, md5
`62567d8b` → A1 `0397a929` → A2 `5e51d95b` → A3 `af7da4e5` → A4 `1991c5fa`).

---

## 0. Verdict — the owner's two numbers

| question | answer | measured at |
|---|---|---|
| **at what clamp force do the pads stop being pried to their travel stop?** | **> 30 N; gone at 45 N** | 30 N: 2/54 legs at **98.2 mm** (of the 98.1 mm stop). 45 N: **0/26**, corpus max **90.4 mm**. 60 N: **0/26**, corpus max **76.7 mm** |
| **at what force does the payload stop being pried out?** | **> 45 N; gone at 60 N** | 45 N still loses the same 6.8 cm pear, **829.5 mm**, pads at 90.4 mm, force 0.00 N. 60 N: **0 escapes in 26 legs** |
| **at what force is the smallest fruit crushed?** | **not at 60 N on the direct line** | the 3.6 cm strawberry reads `sep@loss - dia` **+0.5 mm** at a **36.1 mm** span under a **60.16 N** pinch, `force_min` 55.40 N, held and placed |

**The two thresholds are different and the gap between them is where the class
lives.** At **45 N** the pads no longer reach their stop (`90.4 mm` = 92 % of it)
and the payload *still* leaves: the pry becomes a **shallow** expulsion rather
than a travel-limited one. Only **60 N** stops both, and 60 N does **not** crush
the smallest fruit on this interface - which **contradicts P41's scripted
reading** ("60 N crushes a 3.7 cm strawberry"): that crush was a **seating**
event (the pads driven to 10.0 mm around a 37 mm fruit), not a force threshold.

**The one number for the owner, in the form the sanction requires:** *the sim's
direct line needs **60 N per finger joint** (a delivered pinch of ~54-60 N) to
stop the pry; a real jaw would have to deliver that, and the 60 N cell must be
confirmed at N = 5 before any default moves.*

## 1. The knob, and the manipulation check (two independent confirmations)

`FRUIT_FINGER_MAXFORCE` — the per-joint `UsdPhysicsDriveAPI:linear.maxForce` the
build writes on `openarm_{left,right}_finger_joint1`, **default off** (unset = the
asset's own **10 N**); `joint2` is a drive-less `PhysxMimicJointAPI` mimic and is
never written (`scene.py` `resolve_finger_maxforce` / `apply_finger_maxforce`,
`control.py:242` for the intent level).

**Six cells, all evaluable** (`p76_report.txt` §0). Each rung carries **both**
confirmations the phase asked for:

| rung | build print (`maxForce=`/`0.0N`) | env derev | **live articulation read-back** (`[drive] … joint1/joint2=`) |
|---|---|---|---|
| F10 (control) | `10.0` (the shipped string, nothing written) | (unset) | (absent by construction - the P41 read-back is default-off) |
| F15 | `15.0` | `15` | `15.00/0.00 N` on both arms |
| F20 | `20.0` | `20` | `20.00/0.00` |
| F30 | `30.0` | `30` | `30.00/0.00` |
| F45 (ext) | `45.0` | `45` | `45.00/0.00` |
| F60 (ext) | `60.0` | `60` | `60.00/0.00` |

The behavioural consequence is the third leg of the check: the **held-leg
`force_min` median** tracks the cap at every rung - **9.6-9.7 / 14.2-14.7 /
18.2-19.3 / 25.3-29.2 N** at 10/15/20/30 N, **39.9 N at 45 N** and **53.9 N at
60 N**, i.e. **85-99 % of the cap** across the two seeds (P41's law: delivered
pinch ≈ cap). So the rung *is* the delivered force, and no rung is a stage-only
write.

**The manifest's `physics` block carries the same pin** (phase 4's provenance
rule), read back from the live articulation after the task exists: all **11**
rollout manifests (`logs/p76/rollouts/<arm>_<seed>/direct_none_seed<seed>/`)
report `finger_drive.readback_matches: true` with
`left/right_finger_joint1 = 10.0 / 15.0 / 20.0 / 30.0 / 45.0 / 60.0` and
`joint2 = 0.0` (the drive-less mimic), and `finger_maxforce` = the rung
(`null` on the unset control). So the two independent confirmations the phase
asked for are both on record, per cell.

## 2. The cells, and the instrument

The P66-phase-3 / P71-phase-2 / P73 / P74 / P75 scenario verbatim (patch sheet,
balanced A:B:C, arrival trigger, lead 0.9, `moe_v13s` `61da390a`,
`--presentation direct --episodes 15`), **instrument identical in every arm**:
`FRUIT_CARRY_DIAG=1` plus the new field group. Seeds **77 and 101**, one claim per
run, 8 cells, ~85 min of simulator wall.

**The instrument** (`tasks.py`, five reporting-only fields inside the existing
`if guard_armed:` block, so unset is byte-inert):

| field | what it is | why it had to exist |
|---|---|---|
| `dia=` | the fruit's own class width (`sample.diameter`) | the crush denominator, per fruit |
| `sep_max=…@t<tick>` | the leg's **extreme** measured pad separation, and its tick | `sep@loss` is sampled at the *loss*, but P75 measured the pads reaching the stop **9 ticks later** |
| `gap@sep_max=` | the **commanded** gap at that tick | P75's ordering, per leg: the pads opening while the servo closes |
| `sep_min=` | minimum separation **while the pinch is loaded** | the crush's interference form |
| `fmax=` | the leg's max tactile pinch | the crush's other form: a payload lost with the force *not* collapsing |

`sep` is `arm.jaw_separation()` - the **same** link-origin read as
`sep@onset`/`sep@loss`/`sep_end` and as P41's offline `sep_max`, so every number
here is directly comparable to the **98.1 mm** stop. Pinned by
`scripts/243_p76_sep_selftest.py` (a `selfcheck.sh` leg), which also pins that
the accumulation adds **one** articulation read per guarded tick and that the
stored gap is the per-tick command, not the leg-end cursor.

## 3. The pry, per rung — the ladder does not delete it in 10-30 N

`[carry]` legs only, escape leg = `clean_slip_max > 100 mm` **with a pinch**
(PREGREG A3). "Pried" = the pads reached **≥ 95 mm** (the 98.1 mm stop) on any
leg, escape or not.

| rung | carry legs | escape legs | of which at the stop | legs pried to the stop | `sep_max` range on escape legs |
|---|---|---|---|---|---|
| **10 N** | 55 | 7 | 3 | **5** | 69.6 - **98.2** |
| **15 N** | 54 | 4 | 1 | **1** | 24.4 - **98.1** |
| **20 N** | 55 | 3 | 0 | **2** | 69.0 - 92.0 |
| **30 N** | 54 | 3 | 2 | **2** | 10.2 - **98.3** |
| 45 N (ext) | 26 | 1 | 0 | **0** | 90.4 |
| 60 N (ext) | 26 | **0** | 0 | **0** | - (corpus max **76.7**) |

**The same instance at every rung** - the 6.8 cm pear, left arm, seed 77, the
cleanest possible control because only the cap differs:

| rung | `grasp_lift` `sep_max` | `place0` `sep_max` | `place0` slip | `force_min` | outcome |
|---|---|---|---|---|---|
| 10 N | 77.9 | **98.1** (@t169, gap 66.9) | 791.0 mm | 0.00 N | **lost** |
| 15 N | 77.8 | **98.1** (@t167, gap 69.9) | 741.6 mm | 0.00 N | **lost** |
| 20 N | **96.4** (@t78) | **98.1** (@t0) | 11.0 / 13.6 mm | 17.91 / 15.61 N | **placed** |
| 30 N | 77.2 | **98.3** (@t139) | 96 756.7 mm (ejection) | 0.00 N | **lost** |
| 45 N | 76.8 | **90.4** (@t150) | 829.5 mm | 0.00 N | **lost** |
| 60 N | 75.8 | 75.2 (@t400) | 0.0 mm | 55.55 / 54.17 N | **placed** |

Three things are settled by that column:

1. **The pads are pushed to their travel limit at 10 / 15 / 20 / 30 N** on this
   instance, and the command they are fighting is **25.7-31.2 mm narrower** than
   the span they reach (`gap@sep_max` 66.9-69.9 vs `sep_max` 96.4-98.3) - P75's
   wedge, reproduced at every low rung. **30 N does not relieve it**, which is
   where this interface departs from P41's scripted ladder (sep_max 98.5 → 43.5 →
   31.2 at 10/30/60 N there).
2. **The pads' stop is relieved between 30 and 45 N** (98.3 → 90.4 mm, and 0/26
   legs past 95 mm at 45 N).
3. **The payload is not saved by that**: at 45 N it still leaves, 829.5 mm, with
   the force collapsing to 0.00 N. Retention at 60 N is the first evidence in the
   corpus of the pry being *deleted* rather than *reduced* (`sep_max` 75.2-75.8,
   i.e. **below the fruit's own 68.3 mm + a 7 mm pad shell**, and 0.0 mm slip).

**Retention is not monotone in force** (20 N keeps the pear, 30 N ejects it, 45 N
loses it, 60 N keeps it) and every cell is **one draw**: the direct loop is not
reproducible (rendered frames), so those rows are a **per-instance dose-response**,
not a rate. The mechanism that is monotone is the pad travel (98.1 → 90.4 → 75.2),
and it is the one the phase asked about.

## 4. The crush guard, per fruit — the strawberry is not crushed in this range

`sep_min - dia` (loaded span) is reported for every leg; the **registered** C1 was
sharpened before the extension cells ran to the **loss tick**
(`sep@loss - dia`), the one tick the payload is provably between the pads, because
a loaded `sep_min` can also be taken while the pads press **each other** after a
small fruit has gone (two 3.9 cm strawberry legs at seed 101 read a 148 m / 223 m
`clean_slip` - recycled payloads - with the pads at 10.0 mm).

**C1 (`≤ -15 mm`) and C2 (`force_min ≥ 35 N` on an escape leg) fire on 0 legs in
all six cells.** The numbers behind that:

| class (width) | worst `sep@loss - dia` at ≤ 30 N | at 60 N | verdict |
|---|---|---|---|
| **strawberry 3.6 cm** | **-14.8 mm** (one leg, 15 N, `fmax` 24.26 N, slip 496 mm) | **+0.5 mm**, `fmax` 60.16 N, `fmin` 55.40 N, placed | at the boundary at 15 N in **one** instance; **held** at 60 N |
| strawberry 3.9 cm | -28.7 mm but with a 223 m slip (**recycled** payload, pads at their 10 mm closed limit before the loss) | - | excluded (not physical) |
| apple 7.0 / peach 5.8-6.0 / pear 6.1-6.8 / orange 6.0-6.3 / kiwi 5.3-6.7 / lychee 3.0 | **-0.8 … +13.1 mm** | +3.3 … +8.0 | never inside their own width |
| lychee 3.0 | +13.0 | - | the widest margin |

**Read the -14.8 mm row honestly:** it sits **0.2 mm inside** the registered
-15 mm rule, so the rule does **not** fire and no rung has a crushed leg. What it
*does* say is that a 3.9 cm strawberry can be squeezed 14.8 mm inside its own
width and shot out (496 mm) at **15 N** - a **seating** event (the close landed
24.7 mm inside the fruit) whose depth the cap amplifies, not a force threshold.
That is the same reading P41's 60 N crush supports from the other side (pads to
10.0 mm around 37 mm), and it is why **60 N is safe for the strawberry on the
direct line but was not on the scripted line**: the crush depends on where the
close lands, not on the cap alone.

## 5. Counts — a report, **not** a rate

| rung | placed | left | right | cnp | never-held | held `force_min` median | ticks/attempt |
|---|---|---|---|---|---|---|---|
| 10 N | 20/30 | 6/14 | 14/16 | 3 | 5 | 9.58-9.66 N | 1747 |
| 15 N | 23/30 | 6/9 | 17/21 | 2 | 5 | 14.19-14.67 N | 1748 |
| 20 N | 24/30 | 7/10 | 17/20 | 1 | 5 | 18.22-19.27 N | 1749 |
| 30 N | 24/30 | 7/10 | 17/20 | 2 | 3 | 25.32-29.19 N | 1756 |
| 45 N (ext) | 12/15 | 4/5 | 8/10 | 1 | 2 | 39.86 N | 1730 |
| 60 N (ext) | 13/15 | 6/6 | 7/9 | 0 | 2 | 53.9 N | 1729 |

**A count across rungs compares attractors** (AGENTS §2): the direct loop
conditions on rendered frames and is not reproducible, every rung is a different
branch as soon as one fruit is placed differently, and 13-15 attempts per cell is
one draw. The **direction** (the left's placed count rising with the cap,
6/14 → 4/5 → 6/6) is consistent with the per-leg mechanism of §3 and is **not** offered
as a rate. The only rate-shaped claim this phase makes is the per-leg one: **0 of
26 legs pried and 0 of 26 escapes at 60 N against 5 of 55 pried at 10 N.**

## 6. What this means, and the phase-2 plan (registered condition met at 60 N)

The registered condition (§5.1) is met at **F60**: no leg pried to the stop, no
escape leg, nothing crushed. That is a **declared extension cell**, not a
registered rung, so it licenses a **plan**, not an adoption.

**Phase 2, if the owner wants the 60 N line:**
1. **3 seeds x 15** (`FRUIT_FINGER_MAXFORCE=60` vs the shipped 10 N), the P43
   protocol, with the **paired carried-class endpoint** (`cnp` per arm, both arms
   instrumented) - the class this whole arc has been chasing, now with a
   mechanism-predicted direction.
2. **Two-line and scripted no-harm**: `accept.sh` at 60 N and the two-line at
   60 N, each against its own re-recorded reference (a cap change **moves the
   branch**: P41 measured `accept_mf30` DIFFERS on legs 7/9/10, and the two-line
   `190` gate FAILs on the fingerprint alone). **This is the expensive item** -
   three references and every store's provenance.
3. **The honesty item, which is the sanction and cannot be skipped**: the cap is
   **not physical until a real jaw is anchored to it**. A real parallel jaw that
   delivers ~55-60 N of pinch is plausible (a 2F-85-class gripper reaches
   20-235 N), but *this sim's* number is 60 N **per joint** with the delivered
   pinch ≈ cap, and nothing here measures a real jaw's compliance, faces or
   contact patch. The deliverable stays: **the sim needs 60 N; a real jaw would
   have to deliver 60 N** - the owner decides.
4. **What phase 2 must not be gated on**: a crush threshold. 60 N does not crush
   the strawberry here; P41's scripted crush at 60 N is a seating event and would
   need its own cell if the scripted line were also raised.

**What this phase does not license at all:** a shipped default. `FRUIT_FINGER_MAXFORCE`
stays **default off** (10 N), `configs/*` is untouched, and both motion references
are unchanged (`8952c320` / `eb697f23`) - no reference was re-recorded.

## 7. Deviations, all recorded before the run they govern

* **A1** (before any counted rung): `sep_min` is the **loaded** span
  (`force_now > 0`). The first (discarded) partial 10 N run showed the
  unconditional minimum fires on every escape leg: a payload that has already
  left lets the servo close the pads onto nothing (`sep_end` 51.9 mm inside a
  68.3 mm fruit). That run is `logs/p76/direct/DISCARDED_F10_pre_a1.log`.
* **A2** (before F45/F60): declared **extension cells**, not rungs (P75's A4
  convention), to close the crush's upper bracket (P41's 60 N).
* **A3** (after the seed-101 F20 cell): an escape leg must have had a **pinch**
  (`fmax > 0`). One leg's `clean_slip_max` is **308 215 mm** with `fmax = 0.00 N`
  - a recycled payload, not motion. Never-held legs are listed separately
  (`p76_report.txt` §1c).
* **A4** (after F60, before F45): the bisection the A2 rule made conditional on a
  crush, run instead because F60 came back **clean on both endpoints** and the
  pry threshold is the number the owner asked for.

## 8. No-harm

`scripts/accept.sh` with every knob unset (the new fields need
`FRUIT_CARRY_DIAG=1`, so they cannot run on the scripted path): **6/9,
`fingerprint: matches`, and its 346 `[fruit]` lines are byte-identical to
`logs/p73/accept_noharm.log`** (stream md5 `d0079a237202e2f9b0e152655af32a77`;
`logs/p76/accept_noharm_full.log` is the run stream, `logs/p76/accept_noharm.log`
the summary + gate). The exit=1 is the standing rate floor (6/9 = 67 %
< 75 %), this tree's branch since P32. `scripts/selfcheck.sh` **PASS, 0
failures** (the new `P76 pry/crush fields` leg).

## 9. Evidence layout and pins

```
logs/p76/PREREG.md            the rule + A1/A2/A3/A4                  (md5 1991c5fa)
logs/p76/PREREG.md5           every pin along the way + timestamps
logs/p76/header.txt           the md5 pin block of the batch
logs/p76/run_p76.sh           the driver (F10/F15/F20/F30 + F45/F60 extensions)
logs/p76/p76_report.py/.txt   the per-leg table, the crush census, the registered read
logs/p76/direct/*_77.log      4 rungs x 2 seeds + F45/F60, one claim each
logs/p76/direct/DISCARDED_F10_pre_a1.log   the pre-A1 partial cell (not counted)
logs/p76/accept_noharm.log    the scripted no-harm run
logs/p76/smoke_a1.log         the 2-episode smoke on the amended tree
```

Pins: `tasks.py` **`9d5824ef`** (`9d5824ef2fe08efa060bdd8c4be3cfd3`, the field
group), `rl_env.py` (the `TASKS_MD5` metadata-only follow),
`scripts/243_p76_sep_selftest.py` **`fc0e738e`**, `scripts/selfcheck.sh`
**`84f77dcb`**, `logs/p76/p76_report.py` **`544fc6f2`**; `configs/arm_parks.json` `42ab4fb7`,
`configs/waypoints.json` `d81c6f1c`, `configs/motion_reference.json`
**`8952c320`** and `..._twoline.json` **`eb697f23`** both untouched, checkpoint
`moe_v13s` `61da390a`.
