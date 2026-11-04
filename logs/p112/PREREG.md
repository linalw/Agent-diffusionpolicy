# P112 pre-registration - the three-jaw ring

Pinned **before** any battery cell.  md5 in `PREREG.md5` (`md5sum PREREG.md`).

## 0. What is registered, and what is not

The owner chose P111's **item 2**: a **three-pad ring at 3 x 120 deg**, because
P111's algebra says the lever is the **count of tangential contacts**, not the
drive.  This registration covers the **battery** only; the algebra
(`logs/p112/algebra.py`) and the closure fixture (`logs/p112/fixture_cage3.py`,
report `logs/p112/fixture_report.txt`) are already measured and are quoted, not
re-derived.

**The build under test** (`FRUIT_GRIPPER_KIND=cage3`, `cage_hand.py`):

| quantity | value | why |
|---|---|---|
| pads | **3**, at 0/120/240 deg | the registration's subject |
| plate | **20.0 x 60.0 mm**, 10.0 mm thick | width <= 0.866 x aperture at the 26 mm closed aperture (22.5 mm legal, 20 with margin); length 60 mm clears the OpenArm palm (P107) |
| distal plane / lip / tool offset | 80.500 / 10.500 / **70.000 mm** - unchanged | the hand's own derivation (P107) |
| aperture law | **0.98 x min over its three pad axes** (`CageHand.aperture_extent`) | a 3-jaw must load all three, which needs the *narrowest* of its own axes; the 4-pad ring closes on the widest and its opposed pair can never load (P111) |
| drive | **k = 3300 N/m**, c = 16.2 Ns/m, cap **4.90 N/pad** | the algebra's window over the whole pool at mu 1.46 is [2.9e3, 3.8e3] N/m; 3300 is its geometric mean |
| hold | **1e5 N/m** (P111's hard stop) | the close must stay soft enough to centre, the carry must hold 3 x 4.90 N = 14.7 N (1.5x the shipped pinch's 12.7 N) |
| open aperture | **200 mm** (`FRUIT_CAGE_OPEN_FACE_R=0.100`) | P108: 120 mm blocks the descent |
| close protocol | the task's own (freeze at 0.5 N for 3 ticks) | unchanged |

## 1. The primary endpoints (all four are registered; a win needs 1 and 2)

1. **The clean enclosure.**  P110's split of the `[cage]` pad count, applied to
   **3** pads: `jam` = the descent's `end > 15 mm`; `over-closure` = `aper < dia
   - 4 mm` or `F > 1.5 x 3 x cap`; `clean` = the rest with `pads == 3`.  The cage
   family's measured baseline is **0-3 clean rows of 73-77** (P111); the
   registered bar is **> 10 % of cage rows clean**.
2. **The placed count.**  Against the **shipped `openarm` hand on the same
   tree and the same seeds**, and against P111's rigid 4-pad ring
   (**19/76 = 25.0 %**).  The registered bar is **>= 40 %** pooled over the four
   seeds (i.e. between the ring's 25 % and the shipped hand's 65 %).
3. **The class.**  The no-contact/ejection class (`force_min == 0` with
   `clean_slip > 100 mm`) and the loaded-slide class must not rise above the
   rigid ring's; one `[cage] off0 -> off` **negative** median (centring) is
   registered as a supporting read, not a gate.
4. **The crush guard.**  `sep@loss - dia >= -15 mm` on every leg, and the
   over-closure count in the enclosure split reported.

## 2. The guards (a fail here is a fail regardless of the endpoints)

* **G1 no-harm**: with `FRUIT_GRIPPER_KIND` unset, `scripts/accept.sh` must read
  `fingerprint: matches configs/motion_reference.json` and its `[fruit]` stream
  must be **byte-identical** to `logs/p111/accept_noharm.log` (the pre-phase
  record), and `scripts/selfcheck.sh` must pass.
* **G2 landing**: `FRUIT_PLACE_TRACE`'s `on_belt` on every payload-present
  release (`release_bottom >= 0`); the `-184 mm` rows are the upstream-lost
  class, reported separately (P86/P87).
* **G3 budgets**: the `[motion]` descent budget per leg, `--min-success-rate 0.0`
  (a treatment moves the branch, so it is gated on budgets only; the control is
  gated against its own record).
* **G4 slots**: `ATTEMPTS=20` must yield 20 attempts (a starved slot is a lost
  slot and is reported, not hidden).
* **G5 no new failure reason** beyond the baseline set (the shipped control's
  own keys, with the notes' digits normalised by `113_rl_report.py`).

## 3. The cells

The scripted single arm (`FRUIT_BIARM=0`; the two-line scheduler refuses a
non-`openarm` hand by construction, `tasks.py:9543`), `ATTEMPTS=20`, one claim
per run, **identical instrumentation on every arm** (`FRUIT_CAGE_PROBE=1
FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1`), seeds **5, 6,
101, 202** (P93's fresh-seed rule):

| arm | hand | seeds |
|---|---|---|
| **C** | shipped `openarm` | 5, 6, 101, 202 |
| **T** | `cage3`, k 3300 / c 16.2 / hold 1e5, 200 mm | 5, 6, 101, 202 |

Two seeds would not be enough: P111's regex `T1` read 1/20 at seed 5 and 5/19 at
seeds 101/202, i.e. a 5x over-statement from one seed.  The count is a **branch
draw** on this tree (`logs/p80`), so the count is quoted with its per-seed split.

## 4. The decision rule

* **ADOPT** if (1) and (2) pass, G1-G5 pass, and no seed loses more than 2 of 20
  against its own same-seed control.
* **NOT ADOPTED** if any of (1), (2) or a guard fails.  The phase then publishes
  the mechanism it measured (the fixture's centring + enclosure, or the failure
  that stopped it) and the hardware price; it ships **no default**.
* **A kill, registered before the fixture**: if the closure cannot centre a
  known offset (fixture `off` not below `off0`), the battery is not run at all.
  *Measured: it centres (0-20 mm arrivals -> 0.5-1.9 mm), so the battery is
  owed.*

## 5. What is explicitly NOT claimed

* Not a rate: the loop is not reproducible (rendered frames), so 20 attempts x 4
  seeds is one draw per seed and the per-seed split is published.
* Not a `configs/` change: no motion reference is re-recorded unless the
  treatment **ships**, and the phase ships nothing by default.
* Not the two-line: a non-`openarm` hand is refused in a `CoopSession`, so the
  battery is the scripted single arm only.
* Not the policy: the direct/hybrid interface keeps the shipped hand.
