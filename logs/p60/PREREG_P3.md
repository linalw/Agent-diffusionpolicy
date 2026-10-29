# P60 phase 3 — PREREG: the `[carry]` onset cell on the direct left

Written **before any run**. Gates the phase-3 cell the Oracle's diagnosis named
(last paragraph of the P60 gate): *"the named next instrument is
`FRUIT_CARRY_DIAG=1` on the direct left"*.

## 0. The question, and the two objects it has to separate

P60 phase 1 (`logs/p60/LEFT_CENSUS.md`) establishes the class but not the cause:
left **58/62 failures are `carried-not-placed`**, right **2/8**, and **no
`[carry]` row exists in the 180-episode corpus**, so there is no force / contact
/ onset signature anywhere in it. Two objects are consistent with every row the
census has:

* **O1 — the closed grip class at a 47x higher rate.** The left's escapes are the
  same **loaded slide** `logs/p42/SIM_LIMIT.md` closes for the scripted pads: the
  payload is between the pads, in contact, at carry-level force, and walks out
  during the transfer. Consequence: **close for good** (the force family, the
  seat family and the gripper geometry are all measured negative on this
  geometry; a left arm with no park vector does not get a new lever).
* **O2 — never properly seated at take-off.** The payload is not between the pads
  when the transfer starts: contact never establishes (or establishes at
  near-zero force on one face only), so the escape's onset is at the **first
  ticks** of the lift leg with `contacts@onset = 0`. Consequence: **a new
  object** (a close/seat-timing instrument, not the closed grip class).

The two are separable by one field pair the `[carry]` row already prints:
**`onset_row`** (which tick of the leg the 2 mm in-hand slip starts on),
**`contacts@onset`** and **`force@onset`**.

## 1. Prior evidence (accepted context; it does not decide)

1. **The scripted comparator** (`logs/p41/p2/accept_profile.log`, the scripted
   single-arm acceptance on the P41 grip profile). Its left `place0` rows are the
   ones the phase-3 brief cites, e.g. line 420
   `[fruit] [carry] left place0: ... clean_slip_max=1059.1mm onset_row=2
   force@onset=0.00N sep@onset=52.4mm contacts@onset=0 ...`.
   **Read with its sibling lift row**, that attempt is *not* "never seated": line
   412 reads `left grasp_lift: clean_slip_max=278.3mm onset_row=93
   force@onset=12.12N contacts@onset=1 ... force_min=0.00N loss_row=127` — i.e.
   the payload was held for 93 of 163 ticks, in contact, at 12 N, and left
   mid-lift. The `place0` row's `onset_row=2 / contacts@onset=0` is the
   **downstream** view of a payload that was already gone when the transfer leg
   started. A `[carry]` row is therefore only interpretable **per leg**, and the
   attempt's class is the class of its **first escaping leg** (§3.3).
   Scripted-left split in that file: **4/4 escapes `seated_then_slid`, 1/1 placed
   `no_slip`** (full table in `P3_RESULTS.md`; the other named files,
   `logs/p58/p3a/*` and `logs/p59/p3/*`, carry **0** `[carry]` rows — checked).
2. **An existing direct-left carry corpus, different scenario**
   (`logs/p43/p3/{A,B}_*.log`, N = 5 x 15 per arm, `FRUIT_CARRY_DIAG=1` in the
   both-arm diagnostic set, `moe_v13s`, **post-P41 profile**, the pre-P58 burst
   supply, tree pins `rl_env.py` `0cefb13d` / `tasks.py` `a1b3d673`). The B arm is
   `FRUIT_ARM_PARK=back`, i.e. the shipped default; the left has no park vector,
   so B is a no-op for the left. Its left escapes read lift-leg
   `onset_row` 91-115, `force@onset` 8.2-14.0 N, `contacts@onset` 1,
   `force_min = 0.00`, `loss_row` after the onset. **Context only, not an
   endpoint**: the supply profile differs from the shipped one, so this file is
   declared in advance as *corroboration*, never as the registered result.
3. **P42's onset census** (the reference for "carry level"): force at onset on the
   loaded-slide escapes has a median **4.90 N**, single-sided contact; the parked
   direct right retains **9.3-9.7 N**; the pre-P41 direct corpus **3.57 N**.

## 2. The cell (registered verbatim)

One `scripts/154_claim_run.sh` claim per run, `RUN_LIMIT=2700`, three seeds x 15
picks, one session each, `checkpoints/moe_v13s/policy_best.pt` (`61da390a`), the
shipped direct profile (**no supply env beyond the scenario block** — the clock
pair, the band interlock at cap 4 and the live feeder all resolve on for
`direct`; P58/P59).

```
SCEN_ENV=
  FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
  FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
  FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
  FRUIT_DYNAMIC_PICK=1 FRUIT_BED_DIAG=1
  FRUIT_CARRY_DIAG=1                     <-- the phase-3 instrument (default off)
HARNESS_ENV=
  HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER=
  FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 FRUIT_POLICY_SEED=11
scripts/run.sh scripts/110_rl_rollout.py --ckpt checkpoints/moe_v13s/policy_best.pt \
  --presentation direct --episodes 15 --seeds <77|101|202> --out logs/p60/p3/rollouts
```

Logs `logs/p60/p3/D_{77,101,202}.log`; driver `logs/p60/p3/run_p3.sh`.
**Deliberately not set** (the shipped `direct` defaults):
`FRUIT_DIRECT_CONTINUOUS`, `FRUIT_POLICY_TRIGGER_ACQ`, `FRUIT_ARM_PARK`,
`FRUIT_CARRY_GUARD`, `FRUIT_SEAT_DIAG`, `FRUIT_ACQ_DIAG`, `FRUIT_SUBSTEPS`.
`--out` is a path only (no `--record`): it keeps the run from writing into
`datasets/rl_rollouts/direct_none_seed*`.

**The knob is a reporting knob** (`tasks.py:1464`, `_carry_diag`): it arms
`guard_armed` (`tasks.py:3713-3717`), whose only effect is the per-tick clean-slip
/ force / contact bookkeeping that prints the `[carry]` row at `tasks.py:4230`;
`guard_acts` (the guard that *acts*) and `relief_acts` stay 0 because
`FRUIT_CARRY_GUARD` / `FRUIT_CARRY_RELIEF` are unset. Default off — verified
before the run: no `[carry]` row in `logs/p59/p3/*`, `logs/p58/p3a/*`,
`logs/p59/p2/*` (0 occurrences each).
Onset trigger: `FRUIT_CARRY_GUARD_TRIGGER` default **0.002 m** the slip must
exceed, measured in the leg's own frame from the leg's first tick.

## 3. Parse definitions (fixed before the run)

### 3.1 attempt
An episode opens with `[rl] episode N: <fruit> grade=<g> d=<d>cm bin=<b>
arm=<arm> y=...` and closes with `[rl] episode N: ... success=<s>
grasped=<g> placed=<p> ticks=... notes=[...]`. `[carry]` rows between the two
lines belong to that episode (episodes are sequential in one session).

Class from the closing line: `placed=True` → **placed**; `grasped=True,
placed=False` → **cnp**; `grasped=False` → **never-held** (P60 phase 1's split).

### 3.2 leg row
`[carry] <side> <name>:` with `clean_slip_max`, `onset_row`, `contacts@onset`,
`force@onset`, `force_min`, `loss_row`, `sep@onset`, `sep_end`. Names on the
direct left: `grasp_lift`, `place0`.

### 3.3 per-leg onset class (2 mm trigger, `clean_slip_max` as the leg's maximum)
| class | rule |
|---|---|
| `no_slip` | `onset_row = None` (the payload never moved 2 mm in the leg's frame) |
| `seated_then_slid` | `onset_row` set, `contacts@onset >= 1`, `force@onset >= 2.0 N` |
| `never_seated` | `onset_row` set, `contacts@onset = 0` (`force@onset` reads `0.00`) |
| `marginal_contact` | `onset_row` set, `contacts@onset >= 1`, `force@onset < 2.0 N` |

**Sensitivity (reported, not a gate):** the `seated_then_slid` / `marginal` split
is re-read at **1.0 / 3.0 / 5.0 N**. 2.0 N is registered as the primary because
it is below every carry-level onset in either comparator (scripted 7.68-18.19 N,
direct-left 8.18-14.04 N) and above the noise floor of an empty hand
(`force_min = 0.00` on a lost payload).

### 3.4 the attempt's onset signature (**P2's unit**)
The class of the attempt's **first escaping leg** = the earliest leg, in print
order, whose class is not `no_slip`. Rationale, registered: a payload lost during
`grasp_lift` necessarily starts the `place0` leg already out of the hand, so the
place row would read `never_seated` for a `seated_then_slid` lift (§1.1). The
per-leg table is printed alongside so nothing is hidden by the reduction.

## 4. Endpoints (registered)

* **P1 — coverage.** Every left attempt has either a `[carry]` row for each leg it
  ran, or a named reason it has none. Counts: left attempts, left carry legs,
  attempts with no leg (expected: the `never-held` class, whose primitive never
  ran a carry leg). Report the presence of all four fields
  (`onset_row`, `contacts@onset`, `force@onset`, `clean_slip_max`) on every row.
* **P2 — the split.** The left's failures by §3.4 signature
  (`never_seated` vs `seated_then_slid` vs `marginal_contact`), and **the same
  split for the left's placed legs** (the control). Per-class the onset row and
  the force are reported as **median [min-max]**, not just counts. The right's
  rows are reported too (the same instrument, the arm that places 24/25).
* **P3 — the comparator.** Does the direct left's signature **match** the
  scripted left's (`seated_then_slid` on the lift leg, i.e. contact + carry-level
  force at the onset, `force_min → 0.00` and a `loss_row` after it) or **differ**
  (the onset at row 1-3 with `contacts@onset = 0`)? Verdict on the majority class,
  with the counts on both sides.
* **P4 — no new failure reason** (the `113_rl_report.py` note keys; phase 1 §2b
  fixes the two existing keys) and **placed reported only** (no rate claim: the
  direct loop is a non-reproducible branch, `logs/p60/P3_RESULTS.md` states it).

## 5. Decision rule (verdict mapping, fixed before the run)

* **O1 (closed grip class, close for good)** if the left's escaping attempts are
  **≥ 70 % `seated_then_slid`** (§3.4) and the per-class `force@onset` median is
  **≥ 2.0 N** — the same signature as the scripted comparator and the P43 direct
  corpus.
* **O2 (never seated at take-off, a new object)** if **≥ 70 % `never_seated`**
  with the onset on the leg's **first 3 rows**.
* **mixed / neither** otherwise: report the split, name both, and do **not**
  close the grip class.
The 70 % bar is a descriptive majority rule, not a significance test; with
~15-20 left attempts per arm it cannot be a rate (`AGENTS.md` §2).

## 6. Falsifiers (registered)

* **F1 — a run wedges** (the known renderer freeze, `[claim_run] TIMEOUT` or no
  `[rl] rollout` summary): **retry that seed once**; two failures on one seed
  ends the batch with the shard recorded.
* **F2 — `[carry]` rows absent** (`0` rows for the left across the batch):
  **stop**, do not interpret, and record "the knob did not arm" with the build
  print / env echo as the evidence.
* **F3 — the instrument changes the outcome.** Compare the class counts
  (left and right, placed/cnp/never-held) with the P59 phase-3 control
  `logs/p59/p3/C_{77,101,202}.log` (**left 2/17/1 of 20, right 24/0/1 of 25,
  placed 26/45**), same scenario, same tree pins (`rl_env.py` `1b1e5cdf`,
  `tasks.py` `8ad8ddc8`, ckpt `61da390a`). The direct loop is **not
  reproducible** (rendered frames), so a difference can never be attributed to
  the diag alone: if the counts differ, report it as an **instrumentation-or-
  branch effect** and quote no rate delta. It does not invalidate P1/P2/P3, which
  are read off the rows, not off the counts.

## 7. What is not changed

No default, no `src/`, `configs/` or `scripts/` edit, no commit.
`FRUIT_CARRY_DIAG` stays default **off**; the tree pins are recorded before and
after the batch (`logs/p60/p3/tree_md5_{before,after}.txt`) so the run is
identifiable.

---

## Amendment A1 (post-run, **bookkeeping only** — no endpoint changes)

One descriptive sentence in §1.1 was wrong about the *scripted placed* attempt:
it reads `no_slip` on its **`place0` leg**, but its **`grasp_lift` leg** is a
**20.0 mm transient** (`seated_then_slid`, `force@onset` 10.43 N, `force_min`
2.36 N, `loss_row = None`) — so its *attempt* signature by §3.4 is
`seated_then_slid`, not `no_slip`. The discriminator against a failure is
therefore the **loss** (`force_min → 0` / `loss_row` / a slip in the
hundreds of mm), not the bare 2 mm onset; `P3_RESULTS.md` reports both fields for
every leg and the placed-control row carries `lost = 0/1`. Nothing else changes:
the classes, the split, the comparator rule, the 70 % decision rule and the
falsifiers stand as registered. `P3_RESULTS.md` §2/§3 are written to this
correction (the direct left's placed leg is `no_slip` on **both** legs, so the
correction does not touch the cell's own control).
