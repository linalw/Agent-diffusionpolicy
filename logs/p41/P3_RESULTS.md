# P41 phase 3 — the finger drive's force cap (`FRUIT_FINGER_MAXFORCE`):
# the pry is deleted, the class is not converted, the force family closes

Measured 2026-10-26 on the P41-phase-2 tree (`ae0a579` + phase 2's uncommitted
`control.py` / `scene.py` changes) + this phase's change. **No commit, no
`configs/` change** (both references still read **8a399626** and **2246f83c**).
Nine claimed runs, ~48 min of simulator wall, **all sequential through
`scripts/154_claim_run.sh`** (one claim at a time). Every command is in §7.

---

## 1. The knob, resolved

`FRUIT_FINGER_MAXFORCE=<N>` — **default off**, and set where the drive is
authored, not on a live view:

```
src/fruit_sorting/scene.py
  resolve_finger_maxforce()   # env -> float | None; unset/empty = None, <= 0 refused
  apply_finger_maxforce()     # UsdPhysics.DriveAPI.Get(joint1,"linear")
                              #   .GetMaxForceAttr().Set(value)   (both arms)
  _finger_drive_rows()        # per-joint readback, `HasAPI` only (never `Get`:
                              #   `DriveAPI.Get` *applies* the schema)
```

It runs in `build()`, i.e. **before `start()` creates the `Articulation`**
(`scene.py:1850`), so PhysX parses the cap when it builds the DOFs. `joint2`
carries **no `PhysicsDriveAPI:linear` at all** (a `PhysxMimicJointAPI` mimic,
`assets/openarm_flat/openarm_flat_deinst.usda:3822-3843`), so it is skipped by
construction — it is never given a cap. `UsdPhysicsDriveAPI:linear.maxForce` on
`joint1` is `usda:3803` (10 N).

**Resolved drive, per joint** (build print + a one-time live readback from
`get_dof_max_efforts` in `ArmController.__init__`, default-off so the unset run
prints nothing):

| joint | k [N/m] | c [Ns/m] | maxForce unset | `=30` | `=60` |
|---|---|---|---|---|---|
| `openarm_left_finger_joint1` | 100000 | 2000 | **10.0** (USD) | 30.0 | 60.0 |
| `openarm_left_finger_joint2` | 100000 | 2000 | **0.0** (mimic, no drive) | 0.0 | 0.0 |
| `openarm_right_finger_joint1` | 100000 | 2000 | **10.0** (USD) | 30.0 | 60.0 |
| `openarm_right_finger_joint2` | 100000 | 2000 | **0.0** (mimic, no drive) | 0.0 | 0.0 |

The gains are the shipped `finger_damp02` profile and are **not** touched by this
knob; the k/c column is what `set_dof_gains` programs on both finger DOFs, and
`joint2`'s absent drive block is why it cannot push even with those gains. The
build line (task 5) is the existing one, extended:

```
# unset (unchanged string — this is what makes the byte-identity below possible)
finger drive profile=finger_damp02 k=100000 N/m c=2000 Ns/m maxForce=10.0/0.0N (joint1/joint2; joint2 is a drive-less mimic)
# FRUIT_FINGER_MAXFORCE=30  (logs/p41/p3/accept_mf30.log:369)
finger drive profile=finger_damp02 k=100000 N/m c=2000 Ns/m maxForce=30.0/0.0N (joint1/joint2; joint2 is a drive-less mimic) | FRUIT_FINGER_MAXFORCE=30 N -> openarm_left_finger_joint1=30.0, openarm_left_finger_joint2=n/a (drive-less mimic), openarm_right_finger_joint1=30.0, openarm_right_finger_joint2=n/a (drive-less mimic) (written on the stage before the articulation is created)
```

**Does the setter have an effect? Yes, and it is proven twice.** The stage
readback prints `30.0`, and the **live articulation** readback prints
`joint1/joint2=30.00/0.00 N` for both arms (`accept_mf30.log:386-387`; `60.00`
in mf60:386-387) — i.e. PhysX parsed the written cap. The delivered pinch tracks
it (below), so it is not a stage-only write.

**Byte-identity at the default**: `logs/p41/p3/accept_control.log` (same command,
`FRUIT_FINGER_MAXFORCE` unset) is **457/457 `[fruit]` lines identical to
`logs/p41/p2/accept_profile.log`, zero differences** — including the build line,
which the unset path leaves untouched. `105_motion_regression.py` →
`fingerprint: matches configs/motion_reference.json` (the documented 6/10
branch's rate-only FAIL, identical to phase 2).

---

## 2. The two cells — the pry census at the raised limit

Both claimed runs are `ATTEMPTS=10 SEED=5 FRUIT_CARRY_DIAG=1
FRUIT_MOTION_REPORT=1 FRUIT_FINGER_MAXFORCE={30,60}`; the 10 N column is
`logs/p41/p3/accept_control.log` (= phase 2's `accept_profile.log`, byte for
byte). Re-derived by `logs/p41/p3/mf_table.py` → `mf_table.txt`, with the pad
spans from `logs/w8/B_metric.py` on the trace runs → `pry_sep_max_mf30.txt`,
`pry_sep_max_mf60.txt` (`pry_census.txt` is the per-leg dump).

| | **10 N** (control) | **30 N** (`accept_mf30`) | **60 N** (`accept_mf60`) |
|---|---|---|---|
| closed pinch (close line, n=10/9/10) | 8.76-11.82 N | **24.99-31.54 N** | **41.21-62.33 N** |
| held-leg `force_min` (median, range) | 9.92 N (9.09-9.99) | **29.15 N (20.25-29.99)** | **56.12 N (17.75-59.58)** |
| `F@onset` on the failing lift legs | 7.68 / 12.12 / 18.19 / 8.03 N | **30.79 N** (1 leg) | **62.32 N** (1 leg, no-grasp) |
| `F@onset` on the escapes that placed | — | 33.86 N | 40.34 N |
| servo trips on the failing legs | 38-54, all **close**-direction (chasing a lost payload) | 53 (`closed=18.00 mm`) | 85 (`closed=24.40 mm`) |
| servo trips on the held legs | 0-8 | **8**, each a 3 mm backoff (`opened=3.00 mm`) | 8 |
| **`sep_max` on the escape legs** | **98.5** / 76.0 / 77.4 / 64.2 mm | **43.5** / 42.2 mm | **31.2** / 39.0 mm |
| → % of the 98 mm open stop | **101 %** | **44 %** | **40 %** |
| `clean_slip` (failing lift legs) | 120.5-278.3 mm | **89.9 mm** | **641.2 mm** (never held) |
| in-hand `\|v\|max` (failing legs) | 1.382-1.646 m/s | **1.101 m/s** | 0.672 m/s |
| outcome | **6/10**, left **1/5**, right 5/5 | **8/9**, left **2/3**, right 6/6 | **9/10**, left **3/3**, right 6/7 |
| span | 15.0 s/attempt | 15.4 | 15.5 |

`sep_max` on a *held* leg is only the fruit's own diameter (31-81 mm at every
cap), so the pry reading is the **escape** rows, which is how the table is built.
**Units**: every force here is the tactile `normal_force`, i.e. the **pinch**
(both faces summed). P41 phase 2's law is that the delivered pinch equals the
per-joint cap (`cap=10 -> 9.9 N`, `30 -> 29.9`, `60 -> 58`) because the drive
delivers ~50 % of `Fsat` per face at the 120 Hz operating point — so the cap
column is a **linear gain on the delivered force**, not a saturation that is only
reached at the top. 60 N is 6x the shipped pinch; 30 N is 3x.

**Does it still reach ~98 mm? No.** At 10 N one failing lift still pries the pads
to 98.5 mm (the mechanical stop) and three more reach 64-77 mm. At 30 N the
largest span on any escape is **43.5 mm**; at 60 N **31.2 mm**. The 98 mm
signature is gone from the corpus at both raised caps.

**The cleanest causal pair is attempt 0 — the same peach, the same instance.**
The descent, intercept, deadline, catch-up residual (5.7 mm) and the **frozen
close command (66.4 mm)** are identical in all three arms up to the close
(`first_divergence.txt`); the only behavioural difference on that leg is the
drive's force:

```
control : dynamic close: sustained contact after 23 ticks (force=10.00 N, span=71.5 mm); freeze 66.4 mm
mf30    : dynamic close: sustained contact after 23 ticks (force=29.94 N, span=70.7 mm); freeze 66.4 mm
mf60    : dynamic close: sustained contact after 29 ticks (force=57.96 N, span=70.1 mm); freeze 62.4 mm

control : [carry] left grasp_lift clean_slip=278.3mm F@onset=12.12N sep@onset=73.2mm min_contacts=0 → cnp
mf30    : [carry] left grasp_lift clean_slip=  0.1mm F@onset=n/a  (2 contacts) force_min=29.78N → placed
mf60    : [carry] left grasp_lift clean_slip=  0.0mm (2 contacts) force_min=59.04N          → placed
```

Same command, same geometry, same fruit: at 10 N the payload walks 278 mm and
the pads end at the 98.5 mm stop; at 30/60 N it does not move (0.0-0.1 mm) and
the peach is placed. **This is the "increase the grip force" the owner asked
for, and on this class it works.**

The 60 N cell is **not** an improvement on 30 N: its single failure is a
3.7 cm strawberry whose close (42.74 N, freeze 33.0 mm) let the servo's
full-range close-chase drive the pads to 10.0 mm around it — the fruit is
squeezed *out* at 60 N (`[carry] right grasp_lift clean_slip=641.2mm
F@onset=62.32N sep_end=10.0mm min_contacts=0`, note `fruit did not follow the
gripper`). Its held-leg floor also dips to 17.75 N on one apple leg. 30 N is the
candidate; 60 N is too much for the small fruit.

---

## 3. The class battery at 30 N — it does not convert

Run because §2 cleared both conditions (the pry stopped **and** the acceptance's
left escapes fell 4 → 1 → 0).

| battery | 10 N (phase 2, same tree) | 30 N | left attempt count | read |
|---|---|---|---|---|
| **pear** (`FRUIT_SUPPLY_SPECIES=pear`) | `pear_profile.log` **6/10**, left **2/6** (4 cnp), right 4/4 | `pear_mf30.log` **4/10**, left **0/6** (4 cnp + 2 no-grasp), right 4/4; `diverted=2` | 6 = 6 | **evaluable** (P39 A1.3), **negative** |
| **two-line** (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`) | `twoline_profile.log` **8/10**, left **4/5**, right 4/5, 9.8 s/attempt | `twoline_mf30.log` **6/10**, left **1/5** (3 cnp + 1 no-grasp), right **5/5**, **9.5 s/attempt** (95.5 s sim) | 5 = 5 | **evaluable**, **negative** |

**Mechanism — why the extra force does not convert these two.** The surviving
escapes are not an artefact of a low absolute force: the raise bought 2.8-3x the
shipped pinch on these very legs and they still leave, and the pad geometry that
produces them is visible in the same rows:

* pear (left loaded legs, `pear_census.txt`): `F@onset` **14.11 / 19.74 / 26.56 /
  28.18 / 29.05 N** pinch against the arm's own **27.9 N median** held-leg level
  (range 26.8-29.1) — the onset already sits at 47-97 % of what this grip
  delivers, so the contact is degrading rather than the drive being out of
  travel — while the pads are **7-14 mm wider than the frozen command** (frozen
  59.6-64.1 mm, pads 70.8-78.5 mm on a 6.1-6.7 cm pear, the same 2-9 mm gap the
  10 N arm shows). The pear wedges the pads apart at the *close*, and the extra
  force raises the pinch without closing that geometry gap.
* two-line (`twoline_mf30_carry.log`, byte-identical to the claimed run modulo
  its own `[carry]`/`[diag]` rows, 419/419): the left escapes read `F@onset`
  **16.30 / 19.54 N** pinch at `sep@onset` 73.4 / 67.1 mm with `clean_slip`
  314.9 / 281.5 mm — the force has already fallen from the ~28-30 N close level
  when the slide starts, again with the pads held (no pry).

So the class that survives the force raise is a **loaded slide with the pads
still closed** (W8-B's class: contact loss 13-62 ticks after the slip onset,
single-sided, `F → 0`), not a pry. The 10 N corpus carried both; the raise
deleted the pry and left the slide. On the acceptance that slide is still present
at 3x force too — its one remaining escape starts at **30.79 N pinch** (100 % of
what the 30 N cap delivers there) and walks 89.9 mm — and at 6x it turns into a
crush failure on a 3.7 cm fruit. Escalating the force does not remove it.

---

## 4. Fingerprints (reported, **not** re-recorded — phase 4's call)

| log | reference | verdict |
|---|---|---|
| `accept_control.log` | `configs/motion_reference.json` **8a399626** | **matches** (rate-only FAIL 6/10) |
| `accept_mf30.log` | 8a399626 | **DIFFERS** (legs 7/9/10; a 9-attempt branch against a 10-leg record) |
| `accept_mf60.log` | 8a399626 | **DIFFERS** (legs 8/9/10) |
| `twoline_mf30.log` | `configs/motion_reference_twoline.json` **2246f83c** | **DIFFERS** (all 10 descent legs ±1-3 samples); `190_twoline_gate.sh` **FAIL on the fingerprint only** — 6/10 = exactly the 0.60 floor |

The motion budgets themselves are clean in all three: worst descent `|v|max`
0.110 m/s (budget 0.160-0.161), lurch 0.017 (budget 0.291), every descent inside
budget, `gate_mf30.txt` / `gate_mf60.txt` / `gate_control.txt`. The reported
held-grip cones rise with the cap (control 1.53x, mf30 1.59x, mf60 **3.32x**, the
last on the leg after the no-grasp; the two-line 2.27x) — the dynamic line
reports the cone rather than gating it, no attempt failed by a cone, and the
rise is the expected consequence of a bigger normal force at the same
tangential load. `selfcheck.sh`: **PASS, 0 failures** (1 skipped).

Both `configs` md5s are unchanged after every gate run (the 190 run writes
nothing).

---

## 5. Verdict — is the force limit the binding term?

**For the pry: yes, and it is now measured rather than assumed.** The
`maxForce = 10 N` drive cap *was* what let the pads be pried to their 98.5 mm
open stop; raising it to 30 N holds the same command, on the same fruit, at
`clean_slip` 0.0-0.1 mm. That is the last force-family lever, and it moves the
one class it owns.

**For the class: no.** The conversion does not transfer. On the two batteries
whose left attempt counts are identical across arms — the only evaluable form
this phase has — the left gets **worse**: pear 2/6 → **0/6**, two-line 4/5 →
**1/5**. And the rows say why: those escapes start with the pinch already down to
16-29 N of the ~28-30 N this grip delivers, the pads held closed (no pry, i.e.
the 10 N cap is *not* what ended them), and on the pear the pads sit 7-14 mm
wider than the frozen command at both caps. There is no force shortage left to
buy: the payload is off-centre in the jaw, and single-sided contact does the
rest.

**Therefore the force family is closed with a mechanism.** The 10 N corpus had
two escape mechanisms superposed: a **pry** (drive vs. geometry — force-bound)
and a **loaded slide** (payload vs. pad shape/asymmetry — geometry-bound). This
phase deletes the pry and leaves the slide untouched, and the slide is what the
pear and the two-line lose to. The sim's "hold" limit is **a hardware/geometry
problem, not a force problem**: jaws that cannot oppose an off-centre payload
and pads with no feature that resists an axial walk. The named next lever is
therefore geometric (asymmetric/loaded contact, jaw compliance), not another
force number — and 60 N should not be anyone's default (it crushes a 3.7 cm
strawberry out of the hand).

**Recommendation: `FRUIT_FINGER_MAXFORCE` stays default off, not adopted.** The
acceptance scenario's 6/10 → 8/10-9/10 at 30-60 N is a *moved attractor*, not a
rate; the batteries that are evaluable read negative; and the force family has
now been tested at its own top end.

---

## 6. Limits of this phase

* **Cross-attractor counts.** The three acceptance cells land in three branches
  (10, 9 and 10 attempts; different fruit sequences from attempt 1 on), so the
  6/10 / 8/9 / 9/10 columns are **class reads, not rates** (AGENTS §2). The one
  causal pair is attempt 0's peach (§2), where the pre-grip stream is identical
  and only the close force differs.
* **The servo's own regime moves with the cap.** `FRUIT_DYNAMIC_FORCE_MAX`
  is 12 N, so at 30/60 N every leg reads `over` and the servo saturates its
  3 mm `BACKOFF` at the close (`opened=3.00 mm`, trips=8, where the 10 N arms
  trip 38-54 times in the *close* direction chasing the payload). The cells are
  "cap + servo-in-backoff"; separating them needs a
  `FRUIT_DYNAMIC_FORCE_MAX` cell, which this phase did not run.
* **`sep_max` comes from traces.** The mf30/mf60 trace runs are byte-identical
  to their claimed partners (423/423 and 467/467 `[fruit]` lines modulo the
  `[trace]` banners), and the control's trace is phase 2's, whose claimed run is
  457/457 identical here. The mf60 trace run's **wall was 19m54s against ~4.5
  min for its partners** (a renderer hitch; its stream is identical, so there is
  no evidence it changed the run).
* **n is small and the cells are one branch each**: 1 loaded escape leg at 30 N
  and 1 no-grasp at 60 N on the acceptance, one pear and one two-line run. The
  verdict rests on the mechanism (the pad span at the loss, the onset force
  against the arm's own delivered level, the pads-vs-command gap) and on the
  evaluable per-arm counts, not on the rates.
* **The knob is hand-global**, so every path that sets it inherits it (policy
  handover, direct env). Only the scripted single arm, the pear battery and the
  two-line were measured; `accept_policy.sh` was **not** run this phase.
* The two-line's per-leg readout needed an extra run (`twoline_mf30_carry.log`)
  because the claimed two-line form carries no `[carry]` rows; that run is
  byte-identical to the claimed one modulo its own diagnostic rows.
* No commit, no `configs/` write, `scripts/189_w7a_chain.sh` not run, and no
  `AGENTS.md` / `WORKLOG.md` entry yet — those are phase 4's, together with the
  fingerprint decision.

---

## 7. The runs (all through `scripts/154_claim_run.sh`, sequential)

```
# the setter (1 attempt, effort readout on)
ATTEMPTS=1 SEED=5 FRUIT_FINGER_MAXFORCE=30 FRUIT_GRIP_EFFORT=1 FRUIT_MOTION_REPORT=1 \
  → logs/p41/p3/probe_mf30_effort.log                                     (50 s wall)
# the byte-identity control + the two cells
ATTEMPTS=10 SEED=5 FRUIT_CARRY_DIAG=1 FRUIT_MOTION_REPORT=1                → accept_control.log     (4m36)
  ... + FRUIT_FINGER_MAXFORCE=30                                          → accept_mf30.log        (4m20)
  ... + FRUIT_FINGER_MAXFORCE=60                                          → accept_mf60.log        (4m56)
# the trace twins (sep_max)
  ... FRUIT_FINGER_MAXFORCE=30 + FRUIT_DYNAMIC_TRACE=1 FRUIT_DYNAMIC_TRACE_DIR=logs/p41/p3/trace_mf30 → accept_mf30_trace.log (4m23)
  ... FRUIT_FINGER_MAXFORCE=60 + FRUIT_DYNAMIC_TRACE=1 FRUIT_DYNAMIC_TRACE_DIR=logs/p41/p3/trace_mf60 → accept_mf60_trace.log (19m54)
# the class battery at 30 N
ATTEMPTS=10 SEED=5 FRUIT_SUPPLY_SPECIES=pear FRUIT_CARRY_DIAG=1 FRUIT_MOTION_REPORT=1 FRUIT_FINGER_MAXFORCE=30 → pear_mf30.log   (4m26)
ATTEMPTS=10 SEED=5 FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_CYCLE_REPORT=1 FRUIT_MOTION_REPORT=1 FRUIT_FINGER_MAXFORCE=30 → twoline_mf30.log (4m37)
  ... + FRUIT_CARRY_DIAG=1                                                → twoline_mf30_carry.log (4m40)
# the gates
python3 scripts/105_motion_regression.py <log> --fingerprint configs/motion_reference.json   (control/mf30/mf60)
scripts/190_twoline_gate.sh logs/p41/p3/twoline_mf30.log                                     (FAIL: fingerprint)
python3 logs/p41/p3/mf_table.py ...                                              → mf_table.txt
python3 logs/p41/p2/pry_census.py logs/p41/p2/pear_profile.log logs/p41/p3/pear_mf30.log → pear_census.txt
python3 logs/w8/B_metric.py --trace-dir logs/p41/p3/trace_mf{30,60}              → pry_sep_max_mf{30,60}.txt
python3 logs/p41/p3/first_divergence.py                                        → first_divergence.txt
```

Code: `src/fruit_sorting/scene.py` **8fae708f** and `src/fruit_sorting/control.py`
**9384ff4f** (both carry phase 2's changes as well; this phase adds the three
helpers + the extended build line / the default-off live readback). Evidence:
`logs/p41/p3/` (nine logs + the two trace dirs + the five re-derived
txt/census files), `logs/p41/P3_RESULTS.md` (this file).
