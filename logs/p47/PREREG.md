# P47 phase 2 — PREREG: the bounded acquisition guard (`FRUIT_ACQ_GUARD_MM`)

Written **before any run** of the guard, 2026-10-27, offline phase.
Tree at write time: HEAD **`61660a4`**, clean; `tasks.py` **`b6de439c`**,
`rl_env.py` `93e35ef7`, `control.py` `9384ff4f`, `scene.py` `27e3d64a`,
`fruits.py` `dff684b1`; `configs/motion_reference.json` **`8a399626`** and
`configs/motion_reference_twoline.json` **`2246f83c`** (both untouched by this
phase). Operator of record for the numbers: `logs/p47/ACQ_CENSUS.md` (§1-§4) and
`logs/p47/census_out.txt`.

---

## 1. The item

A **default-off bounded acquisition guard**: at the close, if the fingertip-to-
fruit distance exceeds a threshold, **wait up to N ticks** for the fruit to come
between the pads, then close anyway. One knob pair, default **off**:

| knob | default | meaning |
| --- | --- | --- |
| `FRUIT_ACQ_GUARD_MM` | **`0`** (off) | threshold in mm; `0`/unset = the shipped path, no code reached |
| `FRUIT_ACQ_GUARD_TICKS` | **`40`** | the wait's horizon in control ticks (40 x 1/120 s = **0.333 s** = **40 mm** of belt travel at 0.12 m/s) |

**Site.** `tasks.py`, `_run_impl`, the scripted moving catch: **at the close
entry** — after the catch-up loop's last tick (the tick that prints
`dynamic catch-up: residual=…`) and **before** the `close_attempts` loop. The
measurement is the **same quantity the catch-up's break test uses** and the same
one the census tabulated:

```
r = |tip - (fruit_live + [0, 0, pad_lift])|,   tip = jaw_centre + R @ [0,0,finger_len]
```

so the census's 5.4-6.0 mm / 219.6-480.6 mm numbers *are* the guard's numbers.

**Behaviour when armed.** The trigger compares the `catch_residual` the catch-up
loop **already computed on its last tick** (no new pose read on the un-triggered
path, so an armed-but-never-firing close is byte-identical to a disarmed one).
If `r <= FRUIT_ACQ_GUARD_MM` the guard does nothing (a normal close). Otherwise,
for at most `FRUIT_ACQ_GUARD_TICKS` ticks, repeat the
catch-up's own tracking step (`ik_step` toward the fruit with the shipped
velocity lead, `gripper.follow_centre`, `_step_sim(1)`), re-measuring `r` each
tick, and **exit early** when:
* `r <= FRUIT_ACQ_GUARD_MM` (the fruit entered — the guard succeeded), or
* **the distance has not decreased over the last 8 ticks** (the fruit is moving
  away: a wait cannot help and is strictly harmful). The 8-tick window is a
  fixed constant, not a knob.

Then the shipped close runs **from wherever the pads are**: no belt stop, no
re-approach beyond the station, no change to the close's own ramp, freeze, x-lock
or contact logic. The wait is bounded and the never-stop invariant is preserved.

**Scope.** `dynamic_capture and not direct_capture` — the scripted OpenArm
moving catch, which includes the two-line worker. The direct/policy handover and
the indexed path are **out** (they have their own interfaces and their own
pre-contact knobs, W7-B/ACQ and R2).

**Reporting (inside the arm, not a knob).** With the guard armed: one
`[acqguard] close idx=<i> d=<mm> waited=<ticks> entered=<True|False>` row per
**triggered** close, and one `[acqguard] census fired=<n> entered=<n>
waited_ticks=<sum>` line at the end of the run. With the guard off nothing is
printed — so the C/U arms cannot be disturbed by the instrument.

**Unset = byte-identical, and it is proven, not asserted:**

* by construction — one env read in `__init__`, one `if self._acq_guard_mm > 0.0`
  per close, the wait code unreachable at 0;
* by measurement — the **C** arm must reproduce `logs/p44/p2/accept_s5_C.log`
  on its whole `[fruit]` stream (387 rows) and **U** must reproduce
  `logs/p44/p2/accept_s5_S13.log` (the same env arm), both modulo the added
  instrument tags. A byte difference in either is a **stop** condition, not a
  reading.

---

## 2. What phase 1 measured, and the prediction this registers

Stated **before** the run so the phase cannot be read as a discovery afterwards:

1. The `closing anyway` number is a **standing geometry constant** (the hover
   clearance: 70 mm nominal = `hover 0.060 + pad_lift 0.010`, measured 58-65 mm),
   printed on **317/317** attempted closes, measured against the **station aim**
   before the hover and the descent. It carries no outcome signal (pooled
   `no-grasp` 5/103 at ≥ 62 mm vs 12/181 at ≤ 60 mm, **Fisher p = 0.61**). The
   axis sibling never fires (**0/317**).
2. The **live** pre-close error does separate, with a **gap**: 5.4-6.0 mm on
   309/317 (the catch-up's own 6 mm tolerance) and **219.6 / 245.8 / 251.0 /
   480.6 mm** on the other 8, all 8 no-grasp (vs 11/309 = 3.6 %, **p = 3.3e-11**).
   But it explains only **42 %** of the no-grasp class: 11 of 19 converged and
   were lost in the close/regrasp (worked example in `ACQ_CENSUS.md` §2.4).
3. **The convertible band is empty.** A wait of `N` ticks can convert only a miss
   in `(MM, MM + N]` = **35-75 mm** at the registered setting. The corpus has
   **0 rows in 35-75 mm**; the failing distances need **220-481 ticks
   (1.8-4.0 s)**, i.e. **1.1-2.4x** the catch-up's own 200-tick horizon
   (**12-27 %** of a 15 s attempt). The 480.6 mm row is a **hand-over-timing**
   miss (a target 2.4x the catch's reach budget away), not a "closed a few cm
   early" miss.
4. On the **shipped** line the guard cannot fire at all: the shipped acceptance +
   pear corpus has **0/19** rows above 6 mm (acceptance 10 + pear 9 closes).

**Pre-registered prediction.** With `35 mm / 40 ticks`: the guard fires on
**≤ 2 of the acceptance's 10 closes** and converts **0-1**; `G ≡ C` (byte-
identical) on the shipped line; `UG` fires on the same closes `U` does and
converts at most the one speed-branch row that has a distance signature. **E2 is
therefore predicted to FAIL, and F1 to fire on the distance mechanism.** The
phase is run because that is a *measurement* of the class's retrievability, not
an inference — and because E3/E4/E5/E6 and the trigger census are read either
way.

---

## 3. The arms (6 runs)

| # | battery | arm | env |
| --- | --- | --- | --- |
| 1 | acceptance, seed 5 | **C** | unset |
| 2 | acceptance, seed 5 | **G** | `FRUIT_ACQ_GUARD_MM=35` |
| 3 | acceptance, seed 5 | **U** | `FRUIT_SPEED_ALL=1` |
| 4 | acceptance, seed 5 | **UG** | `FRUIT_SPEED_ALL=1 FRUIT_ACQ_GUARD_MM=35` |
| 5 | pear, seed 5 | **C** | unset |
| 6 | pear, seed 5 | **UG** | `FRUIT_SPEED_ALL=1 FRUIT_ACQ_GUARD_MM=35` |

Order **C → G → U → UG** inside the acceptance, then the pear pair, one
`154_claim_run.sh` claim over all six (the claim is the cost gate).
`FRUIT_ACQ_GUARD_TICKS` stays at its default 40 in every arm.

Battery A = `scripts/accept.sh`'s scenario (the `accept_profile`/`accept_s5_*`
line); battery B = the pear (`pear_s5_*`). Same env/instrument set as P44's
phase-2 battery so the C/U arms are replayable: `FRUIT_MOTION_REPORT=1
FRUIT_CYCLE_REPORT=1` on every arm, and `FRUIT_CARRY_DIAG=1` on every arm
(P44 §9.2 proved CARRY_DIAG run-neutral, 83/83 core rows).

**Branch property of the design.** C vs G is *same-branch* (identical unless the
guard fires); U vs UG is same-branch too, unless the guard fires. So the guard's
firing is a **localised** branch change, attributable to a named tick — the
cleanest attribution the design can have, and the reason the read is a per-cell
count and not a rate.

---

## 4. Endpoints

**E1 — the trigger's incidence and its attribution (an attribution endpoint, not
a rate).**
The brief's literal form ("the `closing anyway` rows with a distance > 50 mm on
UG vs U") is **not evaluable**: every row is 58-65 mm on every arm
(`ACQ_CENSUS.md` §2.3), so both arms would read 100 % and the cut cannot
discriminate. It is registered as a **report**: the `closing anyway` row count
and distribution per arm (expected = the arm's attempted closes, 58-65 mm).
The operative E1 is the **guard's own population**: closes with `r > 35 mm`, the
ticks waited, and how many **entered** — plus, for each triggered close, whether
the waited attempt **converted** (grasped and placed).
*PASS* = the population is measured and non-empty on UG, or the census's
"nothing in 35-75 mm" prediction is confirmed on **both** UG and G (0 fires).
*FAIL* = neither can be established (no attribution).

**E2 — the conversion (the primary).**
`placed(UG) >= placed(U) + 1` **and** `placed(UG) >= 1`.
A per-cell count on the acceptance seed 5 (P44's U = 6/10 there).

**E3 — the wait's cost.**
`s/attempt(UG) <= s/attempt(U) + 0.35 s`, from the `[stats]` span / attempts.
0.35 s is the registered worst case (40 ticks = 0.333 s) plus 0.017 s of slack.

**E4 — no new failure reason.**
Every note in every arm must be in the shipped corpus's note set. The scripted
line's only note is the closure test at `tasks.py:11732-11733`
(`if not result.grasped: notes.append("fruit did not follow the gripper")`), so
any *other* note in any arm fails the phase. The guard's own `[acqguard]` rows
are stdout, not attempt notes, and must not be appended to `result.notes`.

**E5 — the motion gate.**
Every arm: the per-leg budgets must pass (`105`'s descent `|v|max` and the lurch
bound; `190` for the two-line is not part of this battery). C is additionally
gated against `configs/motion_reference.json` (`fingerprint: matches`; the rate
floor is the shipped branch's own count and is reported, not gated). G is
predicted to match too (the guard cannot fire on the shipped line, §2 item 4);
U/UG move the fingerprint **by construction** (P44 §9.3) and are gated on the
budgets and the cone/leg report only.

**E6 — the guard alone must not hurt (non-inferiority on the shipped line).**
`placed(G) >= placed(C)`, no new reason, no budget failure, and C/G byte-
identical on the `[fruit]` stream — which the design makes *expected* rather than
lucky when the guard does not fire (the trigger reads an already-computed value).
This is the no-harm gate that would let the guard ship standalone even if E2
fails.

---

## 5. Falsifiers

| id | condition | reading |
| --- | --- | --- |
| **F1** | the guard changes nothing: 0 triggered closes on the acceptance in both guarded arms, **or** every triggered close ends with the same outcome class as its unguarded counterpart | the distance is **not** the trigger for this class — the lever is elsewhere (the hand-over timing / the converged close losses), and the class is recorded as **not distance-retrievable** |
| **F2** | `s/attempt(UG) > s/attempt(U) + 0.35 s` **and** `placed(UG) <= placed(U)` | the wait costs more than it converts |
| **F3** | a new failure reason appears in any arm | the guard creates a class |
| **F4** | any arm fails a motion budget | the wait destabilises the leg |

**F1 firing is a verdict, not a failure of the phase**: it closes the
distance-guard question and names the two residuals the census measured (the
hand-over that puts the target beyond the catch's reach, and the 11
converged-but-lost closes).

---

## 6. N, cost, and what this will not claim

* **6 runs, one claim, ~35 min wall** (the acceptance is ~150 s of sim + ~60 s
  startup per run at the shipped ~15 s/attempt; the pear the same shape).
* **A per-cell read, not a rate** (AGENTS §2): each arm's count is one draw, the
  U arm moves the branch by construction, and the acceptance seed 5 branch is the
  only one this battery measures. No cross-configuration success-rate claim is
  made; the comparisons of record are E3's timing, E1's trigger census, E4/E5's
  budget and reason sets, and the per-triggered-close outcome.
* **Not measured here**: the two-line (its own scenario and reference would be
  needed), the direct/policy interface (the guard is scoped out of it), the
  pear's two-line, multi-seed replication, and any `configs/` re-record (nothing
  is adopted in this phase).
* If E2 passes and the evidence is a single converted attempt, the phase's
  verdict is "a measured conversion on one attempt in one branch" — it would
  still need the WS-4.2 N = 5 protocol before any default flip.

## 7. Deviations

*(empty at write time; append, dated, if the run departs from this file.)*

---

## 8. Deliverables of the phase

`logs/p47/p2/{accept_s5_{C,G,U,UG},pear_s5_{C,UG}}.log`, `batch_header.txt` (the
md5 pins above), `run_batch.sh`, `p47_report.py` -> `p2_report.txt` (the per-arm
table: placed / cnp / no-grasp, `s/attempt`, the trigger census, the reason set,
the budget read), `gates.txt` (`105` per arm), and `P2_RESULTS.md` judging
E1-E6 / F1-F4.
