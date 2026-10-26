# P41 phase 4 — recorded deviation from pre-registered falsifier **F2**

Written 2026-10-26 at the close of P41, against `logs/p41/PREREG_DRAFT.md`
§3 (the pre-registration as returned by the Oracle-1 gate). The close ships the
finger-drive profile as the **shipped default** and re-records **both** motion
references. The pre-registered F2 clause says exactly the opposite on both
counts. This file is the deviation record, not a rewrite of the
pre-registration: `PREREG_DRAFT.md` stays as it was submitted.

---

## 1. What F2 said

> **F2** | **The force rises but the class does not move** → **a fidelity
> record, not an adoption**; the profile still ships as a *documented,
> provenance-tagged* option but `FRUIT_SIM_FIDELITY` does **not** become the
> default and no reference is re-recorded for it | live, and the phase-1 sample
> (0/2 before and after, the same two left peaches) points this way

(Note on names: the draft's `FRUIT_SIM_FIDELITY` / `grip_damp02` never existed in
code. The implemented form is the **`finger_damp02`** profile inside
`control.finger_drive_profile()` — `k = 1e5 N/m`, `c = 2000 Ns/m` pinned
explicitly — with `FRUIT_FINGER_STIFFNESS=0` as the pre-P41 path and both env
knobs still winning.)

## 2. What happened: **F2 fired**

The force rose and the class did not move. On the pre-registered arm (the
profile vs the same-tree control, `logs/p41/P2_RESULTS.md` §4/§5):

| read | control (4.4 N) | profile (9.9 N) | verdict |
|---|---|---|---|
| delivered pinch, held legs | 3.58-4.36 N (right), 4.25-4.53 (pear) | 9.79-9.99 N, 9.6-11.0 | **2.2x, real** |
| acceptance | 5/9, 133.0 s | 6/10, 150.5 s | different attractor, **not a rate** |
| pear, left | 1 placed / 4 attempts, **cnp 3** | 2 placed / 6 attempts, **cnp 4** | cnp share 0.75 -> 0.67, attempt count moved -> **report, not a verdict** (P39 A1.3) |
| two-line | 6/10 (record `d87c3cdf`) | 8/10 | moved branch, **not a rate** |
| **`sep_max` on the escape legs** | **98.3 / 98.2** mm (2 of 3 at the 98 mm open stop) | **98.5** mm (1 of 4 still at the stop) | the pry **remains** |
| in-hand `\|v\|max` on escapes | 1.667-4.048 m/s | 1.382-1.646 | unchanged |

The decisive read is `sep_max`, not the loss-tick span: the profile's worst
escape still reaches the pads' **own mechanical open stop (98.5 mm against the
0.010 + 2·0.044 = 98 mm limit)**, so the payload is not being held less because
the drive is weak — the drive is pushing its faces apart against a payload that
walks out along the tool axis. The pads hold and the payload slides
(`logs/w8/B_RESULTS.md`'s loaded-slide class), which is the sentence the
pre-registration did not expect.

The pre-registered ladder went the same way and is the second half of the
falsification (`logs/p41/P3_RESULTS.md` §3): raising the drive's **cap** deletes
the pry — `sep_max` 98.5 → **43.5** → **31.2** mm at 10 → 30 → 60 N — and the
class *gets worse* on the two batteries whose attempt counts are invariant:
**pear left 2/6 → 0/6 on the same-tree pear 6/10 → 4/10**, **two-line left 4/5 →
1/5, 8/10 → 6/10**. The acceptance's 6/10 → 8/9 → 9/10 are **three attractors**
and carry no class claim.

**So: mechanism-positive (the force is real, free, and it owns the pry),
class-negative (the carried-not-placed class does not convert, and at 30/60 N it
gets worse on the evaluable batteries).**

## 3. Why the profile ships as the default anyway

Not because the class moved. Because **the shipped 4.4 N is 44 % of what the
*same drive* delivers at 480 Hz (9.95 N, P40)** — i.e. the 120 Hz setting is a
mis-parameterization of the asset's own authored drive, not a tuning choice:

* the drive is authored at `k = 1e6 N/m` with a **10 N/joint** cap and delivers
  **22 % of that cap** per pinch (2.21 N/joint = 4.42 N per pinch, P40); the
  same drive at a 480 Hz physics step delivers **9.95 N**, 50 % of the cap;
* the collapse is on the **damping ratio**, not on `k`: authoring the asset's
  gains on both joints is **byte-identical** to shipped, `k = 3e5` with the
  asset's `c = 100` stays at 4.44 N, and the plateau (~9.75-9.9 N = 50 % of the
  two-joint cap, 5.0 N per face of `Fsat` 10.0 N per joint) is reached at
  **`c/k = 0.02`** — the profile's ratio — for **1.00-1.01x wall**;
* the plateau's onset is **`c/k >= ~3e-3`** (bracketed: 0.002 → 7.2 N,
  0.0033 → 10.0 N). No threshold number is transported into the documents
  because the mechanism behind the ratio is **not identified**
  (`logs/p41/FIDELITY_SWEEP.md` §6.4: the collapse is measured, not explained).

F2's clause treats the profile as a **lever** to be judged by its class effect.
The measurement says it is a **parameterization defect**: the sim was delivering
less than half the grip its own asset declares, for free. Correcting that is not
a performance claim and cannot make the configuration worse (the force is the
only thing that moves, at 1.00x wall) — but it *does* invalidate any force
statement, store or comparison made against the defect. Leaving the defect as the
default would mean every future force measurement is against a drive that
delivers 44 % of its own intent, and that every store's manifest would need a
side-channel to say so.

Two further measured reasons the defect could not be left shipped-as-is:

1. **Provenance is now unconditional.** The collector's and the direct env's
   manifests carry the `physics` block (profile, substeps, control_dt, dt, c/k,
   per-joint k/c/`maxForce` read-back, intent level), so a post-P41 store is
   identifiable *and* a profile flip is no longer silent. Shipping the defect
   would have made "profile = the shipped one" mean the 22 % drive.
2. **The profile is the only free lever left in this family.** The
   substeps route to the same force costs **3.08x wall** (P40); the profile is
   **1.00-1.01x** and lands on the same plateau.

## 4. References re-recorded (the second, independent deviation)

F2 also says "no reference is re-recorded". Both were, because the profile
**moves the branch** (`logs/p41/P2_RESULTS.md` §6):

* `configs/motion_reference.json` `adef05c9` → **`8a399626`**, from
  `logs/p41/p2/accept_profile.log` (6/10); the **pre-P41 archive
  `logs/p41/motion_reference_single_pre_p41.json` (`adef05c9`) is matched by the
  control arm** — so the move is the flip's, not the tree's — and the
  independent trace twin matches the new file too. Gate: `fingerprint: matches`,
  rate-only FAIL at 6/10 < the single-arm 0.75 floor (the documented 6/10
  branch).
* `configs/motion_reference_twoline.json` `d87c3cdf` → **`2246f83c`**, from
  `logs/p41/p2/twoline_profile.log` (8/10); pre-P41 archive
  `logs/p41/motion_reference_twoline_pre_p41.json` (`d87c3cdf`).
  `scripts/190_twoline_gate.sh` **PASS** (budgets clean, 8/10 at the 0.60 floor).

`scripts/189_w7a_chain.sh` was **not** run (it rewrites the single-arm reference
from `logs/w7/10`; P39 §10).

## 5. What does **not** ship

`FRUIT_FINGER_MAXFORCE` (`scene.py`: `resolve_finger_maxforce` /
`apply_finger_maxforce`, written on the stage before the articulation exists) is
**default off and not adopted**. It is the ladder that produced §2's second
result: the pry is deleted (98.5 → 43.5 → 31.2 mm at 30/60 N) and the class is
not converted (pear 6/10 → 4/10; two-line 8/10 → 6/10; 60 N squeezes a 3.7 cm
strawberry out of the hand at `clean_slip` 641 mm). The knob exists as the
measured record of the top of the force family, not as a setting.

## 6. Scope of the deviation

* The profile names a **delivered simulated pinch**, not a physical jaw: P41's
  real-jaw anchor is dropped (no robot), so "2.2x" is a statement about *this
  simulator's* grip, not about a real hand.
* **The sim's hold limit is geometry/hardware, not force.** The class that
  survives both levers is a loaded slide with the pads still closed; the named
  next lever is geometric (asymmetric/loaded contact, jaw compliance), with its
  own pre-registration. Nothing here says the sim "now holds" the fruit: the
  acceptance still reads **6/10** and the pear **6/10** with the profile.
* The class evidence is small-n and branch-bound: 3 control vs 4 profile escape
  legs on the acceptance, one pear run per arm, one two-line run per arm.
  Counts and mechanisms, never rates (AGENTS §2).
* The phase-4 canary (the hybrid policy loop, `moe_v12`, fixed supply) reads
  **7/10 = 70 %** with 2 grip losses + 1 pick-station escape
  (`logs/p41/p4/accept_policy_profile.log`; the gate FAILs on the reason clause
  only, that note being outside the recorded baseline set). It is a **smoke**
  inside this interface's recorded 5-8/10 spread, of the *p33-era* grip/station
  class - it does not measure the profile. The **direct** interface (the
  presentation whose drive the profile now sets) remains **unmeasured** under it.
