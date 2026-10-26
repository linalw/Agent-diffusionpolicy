# P41 phase 2 — the `finger_damp02` profile as the shipped default, its provenance,
# and the jaw-pry census at the plateau

Measured 2026-10-26 on the P40-final tree `ae0a579` + this phase's change. **No
commit.** `configs/` changed only where a fingerprint genuinely differed (§6), both
old files archived beside this one. Seven claimed runs, ~30 min of simulator wall,
all sequential (`logs/p41/p2/*.log`; every run's claim line is in the log).

---

## 1. The profile, resolved

`src/fruit_sorting/control.py`: the finger drive's defaults are now **k = 100000
N/m, c = 2000 Ns/m, pinned explicitly** (`FINGER_PROFILE = "finger_damp02"`,
`finger_drive_profile()`); c is *not* derived from k (the ratio is the mechanism,
phase 1 §3). `FRUIT_FINGER_STIFFNESS` / `_DAMPING` still win;
`FRUIT_FINGER_STIFFNESS=0` skips the gain call and leaves the asset's own drive
(the pre-profile line). The old `FRUIT_FINGER_PADS=1` 60000 N/m default is
**removed**: it only ever unstuck a padded close, the shipped 1e5 delivers that
unconditionally, and keeping a softer-than-default override would undo the profile
on the one hand that has pads.

**Caption (use everywhere): the plateau is 2.2x the shipped pinch and 50 % of the
two-joint cap** — 5.0 N per face of `Fsat` 10.0 N per joint (the `proj` read agrees
at 10.00 N) — **the same ceiling 480 Hz reaches**, at **1.00-1.01x wall**. It is a
delivery change, not a trajectory change.

Build print (`scene.py`, extended in place; every entry script now self-describes):

```
finger links bound with mu=2.0, compliant k=30000 N/m c=80 Ns/m (friction combine
override) | finger drive profile=finger_damp02 k=100000 N/m c=2000 Ns/m
maxForce=10.0/0.0N (joint1/joint2; joint2 is a drive-less mimic)
```

The compliant-contact cell is **cut** from the plan: `assets.py:62-63` already
ships `FRUIT_FINGER_COMPLIANCE=30000` / damping 80, and the P3-face screen
bracketed 1e4..1e5 flat — there is no cell left to test.

## 2. Provenance (`scripts/40_collect_demos.py`)

* `sources` now pins **`src/fruit_sorting/control.py`** and **`src/fruit_sorting/common.py`**
  (the drive and the substep count); `rl_env._MANIFEST_SOURCES` gains `common.py`.
* New unconditional `physics` block (runtime read-back after the task exists;
  the first write carries the env-resolved pair, so a build that dies still
  leaves a named block):

```
physics.profile        "finger_damp02"
physics.substeps       1
physics.control_dt     0.008333333333333333      (the controller's 120 Hz period)
physics.dt             0.008333333333333333      (control_dt / substeps)
physics.c_over_k       0.02
physics.finger_drive   {"source":"runtime","readback_matches":true,"joints":
                        {"openarm_left_finger_joint1":{"k":100000,"c":2000,"maxForce":10.0},
                         "openarm_left_finger_joint2":{"k":100000,"c":2000,"maxForce":0.0},
                         ... right pair ...}}
physics.finger_contact {"compliance":30000.0,"contact_damping":80.0,"mu":2.0,
                        "combine":null,"fruit":{"mu":"per-class draw",
                        "mu_band":[0.45,1.05],"compliance":0.0,"contact_damping":null}}
```

`joint2`'s 0.0 N cap is the USD's (a drive-less mimic): the gain call programs it,
the cap does not move, so it cannot push (phase 1's byte-identical `rho_asset`).
`combine: null` is deliberate — unset means the engine's default pair rule and
`GRIP_CENSUS` §3 records min-vs-average as **unverified**; the fruit-side block is
what makes the pair reconstructible. Verified on a real shard
(`logs/p41/p2/collect_manifest_smoke.log`, `FRUIT_EPISODES=1`, ~70 s).

## 3. The runs

| run | config | log | result |
|---|---|---|---|
| control acceptance | `FRUIT_FINGER_STIFFNESS=0` | `accept_preprofile.log` | **5/9**, 133.0 s, 14.8 s/attempt |
| profile acceptance | the new default | `accept_profile.log` | **6/10**, 150.5 s, 15.0 s/attempt |
| pear (profile) | `FRUIT_SUPPLY_SPECIES=pear` | `pear_profile.log` | **6/10**, 157.1 s, 15.7 s/attempt |
| two-line (profile) | `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1` | `twoline_profile.log` | **8/10**, 98.0 s, 9.8 s/attempt |
| profile + trace | the new default | `accept_profile_trace.log` | 6/10, 150.5 s — **same branch** |
| control + trace | `FRUIT_FINGER_STIFFNESS=0` | `accept_preprofile_trace.log` | 5/9, 133.0 s — **same branch** |

The two trace runs are **byte-identical to their non-trace partners** on the
`[fruit]` stream (profile 437/437 lines, control 390/390) and on every `[carry]`
row, so the trace's per-tick span read describes the same branch as the claimed
runs, and both diagnostics are run-neutral here.

## 4. The jaw-pry census (the decisive read)

Per carry leg: `force@onset` and `sep@loss` from the live `[carry]` line (this phase
added `sep@loss` / `sep_end` to it, default-off), `sep_max` from the trace's own
`sep` rows (`logs/w8/B_metric.py`; the mechanical limit is
`0.010 + 2*0.044 = 98 mm`). Re-derived in `pry_census.py` → `pry_census.txt`,
`pry_sep_max*.txt`.

**The control (4.4 N), left `grasp_lift` escapes — 3 loaded legs, 1 no-grasp:**

| att | fruit | clean_slip | F@onset | sep@onset | sep@loss | **sep_max** | in-hand v | trips |
|---|---|---|---|---|---|---|---|---|
| 0 | peach | 303.2 mm | 5.31 N | 70.9 | 82.4 | **98.3** | 1.667 | 52 |
| 1 | peach | 26.3 → 1092.2 (place0) | 2.90 / 4.40 | 77.9 | 61.9 | 77.9 / 75.0 | 0.343 / 1.954 | 38 |
| 2 | kiwi | 281.1 mm | 5.86 N | 71.2 | 75.5 | **98.2** | 2.022 | 46 |
| 3 | orange | 1165.7 (no-grasp) | 28.49 N @ sep 9.6 | 9.6 | 68.4 | 68.3 | 4.048 | 54 |

**The profile (9.9 N), left `grasp_lift` escapes — 4 legs:**

| att | fruit | clean_slip | F@onset | sep@onset | sep@loss | **sep_max** | in-hand v | trips |
|---|---|---|---|---|---|---|---|---|
| 0 | peach | 278.3 mm | 12.12 N | 73.2 | 78.0 | **98.5** | 1.646 | 54 |
| 1 | peach | 24.3 → 978.8 (place0) | 7.68 / 10.10 | 75.4 | 67.8 | 76.0 / 74.8 | 0.295 / 1.984 | 38 |
| 3 | orange | 139.1 mm | 18.19 N | 76.0 | 63.3 | 77.4 | 1.394 | 38 |
| 9 | lychee | 120.5 mm | 8.03 N | 43.7 | 43.2 | 64.2 | 1.382 | 53 |

Right arm (all placed): control `force_min` 3.58-4.36 N, profile 9.79-9.99 N;
`clean_slip` 0.0-0.1 mm both arms.

**Answer to the question — does the escape still spread the pads at ~9.9 N?** **Yes,
on 1 of 4 escapes it still reaches the limit** (`sep_max` 98.5 mm), and on the other
three it does not (76.0 / 77.4 / 64.2; the control 98.3 / 98.2 / 77.9). The loss-tick
span the brief asks for reads **43.2-78.0 mm (profile) vs 61.9-82.4 mm (control)**:
the pry, when it happens, happens *mid-slide* and the servo has closed by the tick
contact is lost — so `sep@loss` cannot be read as "the jaws never pried", and the
trace's `sep_max` is the field that decides it. **The delivered force at the onset
rises 2.2-3x (median 5.3 → 10.1 N) and the class does not move: the pads still reach
their own open stop (98.5 vs 98.3/98.2 mm — the same bound), so the binding term is
pad geometry/kinematics** (the payload wedges to the finger stop and walks out along
the tool axis; contact loss 12-63 ticks after the onset, single-sided contact,
`F → 0.00 N`, 38-54 servo trips). **The force hypothesis is closed with a
mechanism — on this scenario the carried class is not force-starved.**

## 5. The pear battery

`FRUIT_SUPPLY_SPECIES=pear ATTEMPTS=10 SEED=5` → `pear_profile.log`: **6/10**, left
**2 placed / 6 attempts, cnp 4** (att 1, 5, 6, 8), force at onset 9.6-11.0 N, attempt
max 9.54-10.86 N. The same-tree control of record
(`logs/p39/p3/pear_C.log`, P39): left **1 placed / 4, cnp 3**, attempt force
4.25-4.53 N. **The left `cnp` share does not fall (4/6 vs 3/4) and the left-attempt
count moved 4 → 6**, so by P39 A1.3's evaluability rule this is a **report, not a
verdict**. No new failure reason in any arm (all notes empty except the control
acceptance's known orange `fruit did not follow the gripper`). It was run on the
loss-tick read, which suggested the pry had stopped; the trace read above then put
one escape back at the limit, so §4's closure is the verdict and this battery is
corroboration of it.

## 6. The fingerprint verdicts (not just a check — both references moved)

* Control acceptance **matches** `logs/p41/motion_reference_single_pre_p41.json`
  (**adef05c9**, the shipped pre-P41 file) — so the archive is a valid pre-profile
  record, and the reference moved because of the flip, not because of the tree.
* Profile acceptance **DIFFERS** from adef05c9 (leg 5 `[89, 0.108]` vs `[89,
  0.109]`, leg 10 absent from the reference — the 9-attempt branch became 10).
  Archived, re-recorded from `accept_profile.log`: **8a399626**; the independent
  trace run matches it too. Gate: `fingerprint: matches`, rate-only FAIL
  (6/10 < the single-arm 0.75 floor — the documented 6/10 branch).
* Two-line **DIFFERS** from **d87c3cdf** (8/10 vs the 6/10 record; every descent
  leg +1 sample / +0.001-0.002 m/s). Archived to
  `logs/p41/motion_reference_twoline_pre_p41.json`, re-recorded from
  `twoline_profile.log`: **2246f83c**; `scripts/190_twoline_gate.sh` **PASS**
  (budgets clean, 8/10 at the 0.60 floor).

`scripts/189_w7a_chain.sh` was **not** run.

## 7. Limits of this phase

* n: 3 loaded escape legs (control) vs 4 (profile) on the acceptance, 1 pear pair,
  one two-line run. Counts and mechanisms, never rates.
* `sep_max` comes from the trace runs; they are byte-identical to the claimed runs
  here, but that identity is a property of this branch, not a general rule (traces
  are documented as mechanism-only).
* The pear control is the P39 log (pre-P40 tree). The attempt count moved, so the
  comparison is a report; a same-tree pear control would be the phase-3 form if the
  class read is ever needed as a verdict.
* The profile names a *delivered pinch*, not a physical jaw: P41's real-jaw anchor
  is dropped (no robot). "2.2x the simulated pinch" says this simulator's grip is
  no longer the force-binding term; §4 says the carried class is geometric anyway.
