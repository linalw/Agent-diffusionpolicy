# P7-A PREREGISTRATION: FARM Port A - contact-gated force-mode re-entry (`FRUIT_FORCE_REENTRY`)

Written 2026-10-16, branch `p-supply`, lane P7-1/L3 (Tier C: **no simulator runs**).
Source: `docs/papers/MECHANISMS.md` item 3 ("Force lane, Port A: contact-gated
force-mode re-entry", #37 FARM), `logs/p6/B2_reread.md` card 17 (mechanism sketch A),
`logs/p6/B3b_reread.md` card 4 + appendix note 2 (the three naive-force negatives).
Written **before** the implementation (the edit pin is section 7). The byte-identity
proof and the battery are **P7-2's Tier-A work** (section 9).

## 1. The measured failure this targets

The R11-A.1 record (`logs/r11/A1_RESULTS.md` sections 3 and 5.2) isolates a
force-servo signature in the reach candidate's left failures:

* every left failure's servo read `F[0.00,..]N` with **`gap == sep`** (nothing
  between the faces) and **`closed=15.00mm` over `38` trips** - the servo closed
  its **full 15 mm range onto air** after the payload had already left the jaws;
* the shipped control's own failure (attempt-0 kiwi) carries **one** occurrence of
  the identical signature (`F[0.00,14.92]N gap=39.8 sep=39.8 closed=15.00 trips=38`);
* the servo's own range arithmetic explains 38: step 0.4 mm
  (`FRUIT_DYNAMIC_FORCE_STEP=0.0004`), range 15 mm (`FRUIT_DYNAMIC_FORCE_RANGE=0.015`),
  15/0.4 = 37.5 -> 38 moves.

The signature is a **symptom of the payload being out** - the W8-B/R6-B class is a
mid-lift **one-sided loaded slide**, not a servo bug. What FARM's discipline adds is
that a force loop should not keep commanding a squeeze after its contact estimate is
gone: the closing may also **feed** the slide (the pads keep advancing into a payload
that is rolling out - the "bat the payload" class R8-A D2b measured). Whether the
chase is *causal* or only *reported* is exactly what the battery decides (section 5),
and the pre-registered non-adoption reading is "trips fall, carried-not-placed flat
-> timing, not mode entry, owns the failure" (the B2 falsification).

## 2. The mechanism (FARM's dual-mode discipline, ported)

FARM (`logs/p6/B2_reread.md` card 17) enters closed-loop force control only when its
contact estimate is confident (target and FEATS-estimated force past a
noise-derived threshold) and otherwise stays position/width-controlled; its
position-mode counterexample is real (vision-only plant 85% vs FARM 95%), so the
gate is itself a risk. The port, on the existing servo's own signals:

* **Confident contact** = `normal_force >= FRUIT_FORCE_REENTRY_ENTER` (default
  **1.0 N**) **and** `contact_count >= FRUIT_FORCE_REENTRY_CONTACTS` (default **1**).
  The sim tactile exposes exactly normal force + contact count (per
  `docs/papers/MECHANISMS.md` section 2b); both are read from the reading the servo
  already takes, so **no new per-tick sensor work**. "Both-side" is implemented as
  the two available signals agreeing (FARM's own rule form is likewise "target
  **and** estimate"); the stricter both-finger form (`..._CONTACTS=2`) is the
  pre-registered variant if the default produces weak-grip losses - several clean
  carries read `min_contacts=1` (`logs/r11/B_carry_M2.txt`), so `=2` is expected to
  orphan healthy legs and is **not** the default.
* **Entry**: `FRUIT_FORCE_REENTRY_TICKS` (default **3**) consecutive confident ticks.
* **Hysteresis exit**: `FRUIT_FORCE_REENTRY_EXIT_TICKS` (default **3**) consecutive
  lost ticks, where lost = `force < FRUIT_FORCE_REENTRY_EXIT` (default **0.3 N**)
  **or** `contact_count < CONTACTS`. The band `0.3..1.0 N` is the hysteresis: it
  sits below every measured healthy hold minimum (successes read `F_min`
  1.6-4.9 N; clean W8-B legs 1.90-4.25 N) and above the chase's 0.00 N, so a
  shrinking width keeps the mode (the servo closes as shipped) while a lost
  payload exits it.
* **Out of mode**: the servo **holds the commanded gap** - neither the follow-close
  nor the anti-crush back-off runs (both are the force loop's; a genuine crush
  reads confidently and is in mode). Exit is checked **before** the move test, and
  the out-of-mode tick resets the under/over runs, so a pure-air loss fires
  **zero** closes after the debounce.
* **Re-entry**: the latch re-enters when contact confidence returns (a re-seat, a
  re-contact), per the same entry rule.
* **Mode-transition counter** (per attempt, per side): `entries`, `exits`, and
  `gated` (servo ticks out of mode with `force < floor` - the would-be close
  ticks the gate withheld). Counts only, from values already read; no link reads,
  no per-tick log writes.

The three naive-force negatives (`logs/p6/B3b_reread.md` appendix note 2: ForceVLA
pi0-fast 31.0 -> 14.2 %, VLA-Touch RDT+tactile ~+4 %, VisualThink dense 85.8 vs
routed 83.5 on the contact task) constrain the **policy-side** lane (Port B: naive
conditioning of a compact policy). Port A is not that: no new input channel, no
retraining, no action-space change - it is mode discipline on the existing
controller, which is why the B2/B3b resolution orders Port A first (S cost).

Not re-opened: the W5 watcher (the 0-2 tick in-window guard) - this is a
**state-mode discipline**, not a per-tick drop detector.

## 3. Scope

* **Primary: the scripted dynamic-capture force servo.** The knob is read only
  inside `_force_servo_step` and its gate applies only while
  `self._dynamic_capture_active` (the per-attempt flag set by
  `_grasp_carry_place_impl`), so the shipped dynamic OpenArm catch - and with it the
  two-line scheduler, which runs the same scripted catch - is the measured scope.
* **Secondary: the direct interface** (policy handover with `FRUIT_DYNAMIC_PICK=1`,
  the opt-in dynamic line). Same code path; only diagnosed in the N=5 battery if
  P7-2 chooses to include it (section 5).
* **Excluded**: the indexed P1 handover and any `FRUIT_DYNAMIC_FORCE_SERVO=1`
  opt-in on a non-dynamic path keep the shipped ungated servo.
* **Default off**: `FRUIT_FORCE_REENTRY=0` -> the block is not taken, no state is
  written, no move logic is touched -> **byte-identical shipped behaviour**. No
  shipped default changes anywhere; no supply-path or policy change (so
  `scripts/172_supply_selftest.py` is **not** edited).

## 4. The battery and the baseline pin (which battery reproduces the chase population)

Scenario: `accept.sh`'s (single arm, scattered supply, seed 5, 10 attempts). The
chase-signature count is `grep -c "trips=38"` (equivalently: `gap == sep`,
`closed=15.00mm`, `F_min=0.00`) in the `[task] force servo:` rows.

| # | run | env | chase-signature count | source |
| --- | --- | --- | --- | --- |
| B0 | **R11-A.1 candidate acceptance** (the population of record) | `FRUIT_REACH_ANYWHERE=1 FRUIT_REACH_HOVER_SETTLE=60` (+ the reach branch's floored selector, default `FRUIT_REACH_SHIPPED_FLOOR=1`) | **5** (all left; attempts 0/1/4/7/9; lines 417/449/542/609/669) | `logs/r11/A1_10_accept_floored.log` (4/9 = 44 %) |
| B1 | **shipped control** (same battery, knobs off) | `...=0 ...=0` | **1** (attempt-0 kiwi, `F[0.00,14.92]N ... closed=15.00 trips=38`) | `logs/r11/A1_15_accept_control.log` (9/10) |
| B2 | patch cross-check, candidate | PATCHB + candidate | 6 (5 left + 1 right) | `logs/r11/A1_20_patch_floored.log` (10/17) |
| B3 | patch cross-check, control | PATCHB + off | 5 (all left) | `logs/r11/A1_25_patch_control.log` (13/18) |

B0/B1 are the discriminating pair (5 vs 1). On the patch sheet the signature is
**not** candidate-specific (B3 carries 5 too) because the patch's lane 0 sits at its
grip limit in every configuration (`logs/r11/A1_RESULTS.md` section 4); the patch is
a cross-check only.

**The current tree's control is already physics-identical to B1**: `logs/p2d/90_accept.log`
(9/10, `fingerprint: matches`) is `IDENTICAL` to `A1_15` on
`logs/w4/compare_streams.py --physics-only` (365/365 physics `[fruit]` lines), and it
carries the same single kiwi occurrence. P7-2 still **re-reproduces the population on
its own tree first** (probe the branch, then measure): re-run B0, confirm the count is
5 before any knob-on run; if the branch moved, re-pin the baseline and record why.

## 5. Endpoints

**Scripted (primary), battery B0 with the knob OFF vs ON (Tier A, `scripts/154_claim_run.sh`):**

1. **Chase trips (mechanism, primary).** `trips=38` / `closed=15.00` signature count:
   **5 -> <= 1** on B0 (expected ~0 by construction - the close cannot run without
   contact). This endpoint alone does not justify adoption.
2. **Carried-not-placed (value, primary).** The 5 left failures on B0: at least a
   **2-slot conversion** (<= 3 carried-not-placed) with no failure moved into a new
   class; no new reason anywhere in the run. If 1 passes and 2 does not, the
   pre-registered reading is the B2 falsification and **the knob is not adopted**.
3. **Gate.** The knob-ON acceptance must pass the motion gate (every descent inside
   its speed/lurch budget; worst cone reported) and read >= the dynamic floor 0.75.
   A moved branch gets its own fingerprint only on adoption; a fingerprint mismatch
   on a candidate run is recorded, not treated as a break.
4. **Direct N=5 (secondary, only if P7-2 includes the direct path).** The standard
   protocol: `moe_v13s` (`61da390a`), ACQ=1 + R7-A pinned, interleaved N=5 paired
   x 15 episodes, primary = paired carried-class conversion (the 6-0 edge, sign
   p <= 0.05), cycle <= +5 %, zero new reasons (R9/W8-A shape).

**Adoption reading (P7-2/P7-3, none flips here):** trips endpoint met AND at least
one carried-class conversion reproduced AND the no-harm bar (section 8) byte-exact;
otherwise the negative is published and the default stays `0`.

## 6. The kills

* **Trips unchanged** on B0 (the gate never fired or the loss outruns the debounce):
  the mechanism is inert -> stop, publish, do not adopt.
* **Weak-grip losses appear** (new `grasped=False` / `N=0`, lift-slip, or a clean
  carry losing margin on the knob-ON runs): FARM's position-mode risk -> kill; the
  strict `CONTACTS=2` variant may be screened as a named follow-up, not silently.
* **Any descent outside its speed/lurch budget** in the gate -> kill.
* **A re-seat rise** (the R11-A 0 -> 10 signature) -> kill.
* **A new failure reason** in any knob-ON run -> kill (the standing rule).
* Knob-ON acceptance below the dynamic floor 0.75 -> kill.

## 7. Implementation pin (what this lane writes; written before the edit)

`src/fruit_sorting/tasks.py`, default-off, nothing else:

* knob block in `__init__` next to the force-servo state:
  `FRUIT_FORCE_REENTRY` (0/1, default **0**), `..._ENTER` (1.0 N), `..._EXIT`
  (0.3 N), `..._CONTACTS` (1), `..._TICKS` (3), `..._EXIT_TICKS` (3),
  `..._DIAG` (0/1, default **0**); the latch/debounce dicts and the per-attempt
  counter dict;
* `_force_servo_reset`: clears the per-grip latch and debounce runs when the knob
  is on (counters persist across a mid-attempt re-seat);
* `_force_servo_step`: the gate block (entry/exit, counter) and the out-of-mode
  hold, scoped by `self._dynamic_capture_active`, all after the existing reading/
  reference computation and before the move test; the move test itself unchanged;
* `_force_servo_report`: the counts-only `[task] force reentry:` diag line (only
  when the knob **and** the diag are on and any counter is non-zero) and the
  per-attempt counter/latch clear.

No shipped default is touched. The current-tree pins: `tasks.py`
`bcb1fb72d80511a35f8b89cad0ca0a23`, `fruits.py` `f5671a65d6f72eb69a81e12ac6e0bf53`,
`rl_env.py` `0c4f6b65993ea430eb432279cec0da8e` (its `TASKS_MD5` pin matches the
pre-edit `tasks.py`). **The `TASKS_MD5` metadata-only follow is a P7-2 item** (this
lane's write scope is the two files above); until it follows, the RL environment
refuses to start, and no direct-interface run is possible. `172_supply_selftest.py`
is not edited (no supply-path change; `172` should still pass unchanged).

**Post-edit pin (appended after the implementation, 2026-10-16):** the implemented
`tasks.py` is `fec67f004a5ea1d326ed7cf572d824c8` (+132 insertions, no deletions;
nothing else modified by this lane). `rl_env.py` still pins `bcb1fb72...`, i.e. the
metadata follow in the paragraph above is now required before any P7-2 RL-env run.
Offline checks at this pin: `py_compile` OK; `198`, `176`, `172` and the full
`scripts/selfcheck.sh` (0 failures, 1 skip) PASS; an inline stubbed logic check on
the real `_force_servo_step` reproduces the shipped air chase with the knob off
(38 trips, 15.00 mm) and zero closes with it on, with hysteresis/re-entry and the
non-dynamic inertness verified. This is **not** the byte-identity proof (P7-2).

## 8. The no-harm bar (P7-2, knob OFF)

1. Acceptance: **9/10** + `fingerprint: matches configs/motion_reference.json` +
   motion gate PASS, and the physics `[fruit]` stream **365/365 identical** to
   `logs/p2d/90_accept.log` (== B1 on `compare_streams --physics-only`).
2. Patch control: **643/643** physics-identical to `logs/r10/30_control.log`
   (the W6-B record).
3. Two-line dense re-record: **442/442** `[fruit]` identical to the W7-A record and
   `scripts/190_twoline_gate.sh` PASS (`configs/motion_reference_twoline.json`).
4. `scripts/selfcheck.sh` PASS; `172_supply_selftest.py` 52 checks PASS (unchanged,
   re-run for the record).

## 9. What is P7-2's Tier-A work (explicitly not done here)

This lane (P7-1/L3) does **no simulator runs**: it writes this pre-registration, the
default-off implementation, and an offline syntax/selftest check only. **The
byte-identity proof and the whole battery (B0 knob-off reproduction, knob-on runs,
the motion gate, the acceptance, the two-line re-record) are P7-2's Tier-A work**
(`scripts/154_claim_run.sh`, Tier A one lane), together with the `rl_env.py`
`TASKS_MD5` metadata-only follow before any direct-interface run. The knob-on runs
are candidates, not adopted behaviour; nothing here changes a shipped default.
