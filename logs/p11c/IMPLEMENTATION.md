# P11-C implementation: the re-seat arrival geometry (`FRUIT_DYNAMIC_REGRASP_FROM_OPEN`), offline

Status: **implemented, offline-verified** (branch `p-supply`, 2026-10-18). **No simulator run in
this lane** - the Tier-A battery is a separate lane per the frozen pre-registration
`logs/p11c/PREREG_REGRASP_ARRIVAL.md`. Writes: `src/fruit_sorting/tasks.py` (the knob + the
arrival branch), `src/fruit_sorting/rl_env.py` (the `TASKS_MD5` follow), `logs/p11c/` (this
record, `check_regrasp_from_open.py`, `selfcheck.log`, `WORKLOG_entry.md`). No commit by this
lane; no branch operation; `Paper/`, `datasets/`, `checkpoints/` untouched.

## 1. The diff

| file | md5 (new) | md5 (was) | change |
| --- | --- | --- | --- |
| `src/fruit_sorting/tasks.py` | `810658b802d22bbd63013726fc78af81` | `6574d92eafe38f1025b880d39a9410f9` | +69/-1, two hunks (below) |
| `src/fruit_sorting/rl_env.py` | `9a2c38721b32f0af91371ca3e8809196` | `8413fece2203c1bccd84b0d5c3830eb3` | the metadata-only `TASKS_MD5` pin follow (line 271) |
| `logs/p11c/check_regrasp_from_open.py` | `c74342bbb45a15495ccfc9e66a8c5d9d` | - | the new stub (section 4) |

**Hunk 1** (`_grasp_carry_place_impl`, right after the `regrasp_keep` resolution, `tasks.py:6657`):
the new knob resolution

```python
regrasp_from_open = (
    self._dynamic_profile("FRUIT_DYNAMIC_REGRASP_FROM_OPEN", "0", "0") == "1"
)
```

**Hunk 2** (the W1 keep branch of the re-seat, `tasks.py:8708`): the arrival change. The descent
phase is shared and only the gap it holds differs (`descent_gap`); under the knob it is followed
by the horizontal close to the same keep depth:

```python
descent_gap = float(gap_open) if regrasp_from_open else keep_gap
# ... the shipped 40-tick tracking loop, holding `descent_gap` ...
if regrasp_from_open:
    reseat_close = np.concatenate([
        min_jerk_ramp(gap_open, wide, fast_ticks),
        min_jerk_ramp(wide, keep_gap, load_ticks),
    ])
    # ... the same tracking loop, closing through `float(gap)` ...
```

plus the observability suffix on the existing say row
(`... + (" [from-open]" if regrasp_from_open else "")`). The `keep_gap` expression, the
`_force_servo_reset`, the ratchet (`FRUIT_DYNAMIC_REGRASP_STEP`) and the non-keep regrasp branch
are untouched.

## 2. The knob semantics

* **Name / default**: `FRUIT_DYNAMIC_REGRASP_FROM_OPEN`, default `0` on both paths - the shipped
  form, byte-inert. The pre-registered `_dynamic_profile` triple is `("0", "0")`: the battery's
  arm B sets the env explicitly (`PREREG_REGRASP_ARRIVAL.md` "Arms and scenario"), so the
  two-line default must stay `0` or arm A would already carry the treatment.
* **Resolution channel**: `_dynamic_profile` like the rest of the W1 profile - an explicit env
  value always wins, and a future adoption flip is one literal (`"0"` -> `"1"` in the two-line
  slot) with the single arm left alone.
* **Scope**: the value is consumed only inside the `regrasp_keep` branch, which is the
  two-line-only W1 profile (`FRUIT_DYNAMIC_REGRASP_KEEP` resolves `0`/`1`). On the shipped
  single arm the keep branch never runs, so the knob cannot act there unless both knobs are
  forced on by env (the `_dynamic_profile` "explicit env wins" contract).
* **Effect**: with the knob on, the W1 re-seat **descends at the pre-close open gap** (no
  descent contact) and then **closes horizontally** to the same keep depth with the initial
  close's two-phase shape. Everything else in the W1 profile - the probe lift, the re-seat
  depth (`keep_gap`), the cycle bound (`FRUIT_REGRASPS`), the force-servo reset, the ratchet -
  is unchanged.
* **Observability**: the say row keeps the shipped text (`dynamic regrasp: re-seated in place
  (gap N mm kept)`) and gains exactly ` [from-open]` when the knob is on, so the battery can
  count the arrival geometry per attempt while existing `mm kept` greps keep working.

## 3. The geometry choice + the alternatives

The P11-B probe (`logs/p11b/B_EJECTION_PROBE.md` sections 0/3/4/8) measured: the ejection is a
**kinematic wedge of the descending jaws** - the `plow` geometry (jaws already at a sub-width
gap, descending onto the fruit) escapes **3/3 at every contacting gap**, bit-identically over
20 mm of commanded interference - while the **close-from-open** geometry never ejects (`belt`
0/3, `air` 0/3 at every delta), and the contact parameters (stiffness, fruit compliance,
restitution, substeps) do not move it. The fix is therefore the arrival geometry only.

**Descent gap - chosen: the pre-close open gap (`gap_open` = `FRUIT_GRIPPER_OPEN`, default
0.09 m).** This is the gap the initial close's settle holds and the gap the non-keep regrasp
path descends at, i.e. the closest-to-shipped form. It is wider than the measured blocking span
for every fruit in the pool: the probe's stop is `extent + ~11 mm` of link span (tomato
51.0 -> 62.3 mm, apple 64.5 -> 75.6 mm), the pool's largest nominal extent is 0.070 m
(apple/orange/peach/pear draws), so 0.070 + 0.0113 = **0.0813 m < 0.090 m** (with the mesh's
+/-6 % length bias, 0.0742 + 0.0113 = 0.0855 < 0.09). The probe's `-15` anchors show a descent
at/above the blocking span leaves the pads at 0.14 N / no motion.
*Alternative (documented, not chosen)*: the live measured extent + the measured blocking offset
(`pinch_width(sample, quat) + ~0.0113`). It tracks the fruit's own width, but adds a
hand-specific measured constant and a live geometric read where the open gap already clears the
blocking span for every pool fruit; the pre-reg explicitly allows "simply the pre-close open
gap".

**Close shape - chosen: the initial close's two-phase shape** (`min_jerk_ramp(gap_open, wide,
fast_ticks)` then `min_jerk_ramp(wide, keep_gap, load_ticks)`, reusing the shipped `wide` =
`max(pinch_width * 1.02, diameter * 1.02)`, `fast_ticks` = 24, `load_ticks` = 60). The mission
and the pre-reg say "the same close shape as the initial close"; the two-phase form *is* that
shape, and reusing the shipped computation keeps the two close geometries coupled.
*Alternative (documented, not chosen)*: the non-keep regrasp path's single 45-tick
`min_jerk_ramp(gap_open, keep_gap, 45)` (also the probe's close shape). It is simpler but is
not the initial close's shape, and it would duplicate rather than reuse the shipped constants.

**Close depth - chosen: `keep_gap` (the W1 re-seat depth).** The mission says keep the rest of
the W1 profile intact, and the pre-reg says "close horizontally to the grip depth": with the
chased depth kept, the only changed variable is *how* the pads arrive. The probe's close-from-
open groups commanded sub-width sweep gaps in one step (delta up to +15 mm of interference) and
never ejected, so closing horizontally to the chased depth is inside the measured ejection-free
set.
*Alternative (documented, not chosen)*: close to `grip_gap` (the initial close's designed
depth). That would change the re-seat depth (out of scope) and would couple the fix to the
chase; the pre-reg lists the chase stop (`FRUIT_FORCE_REENTRY=1`) as a **separate optional
battery arm**.

**Not reproduced (documented)**: the initial close's *freeze* (the depth freezes at the first
sustained contact). The shipped re-seat holds a fixed depth too, and the probe's belt/air
groups held the sub-width gap 0.5 s without ejection; the re-seat depth is already the
post-chase depth, so the freeze would add a new state machine for no measured benefit. The
**pad-opening phase** (the pads open from the chased gap to 0.09 at the start of the descent)
is the fix's essence and is deliberately accepted: the W1 "pads never leave the fruit" property
is not preserved for this arm - the pre-reg's expectation is exactly that a re-seat which does
not press in may leave the marginal grip marginal (the class may shift toward B2/C slip; the
rate may not improve, `logs/p11b/C_DECISION.md`).

## 4. The verification (offline only)

1. `python3 -m py_compile src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py` - OK.
2. **The new stub** `logs/p11c/check_regrasp_from_open.py` (**PASS**, all 39 checks; the
   archived output is `logs/p11c/10_stub_check.txt`) pins three layers:
   * *source*: the knob is written once, as the pre-registered `_dynamic_profile` triple with
     the `== "1"` parse; the pre-existing W1 triples are unchanged; the knob name is consumed
     exactly in the four expected places; the keep branch keeps the shipped `keep_gap`
     expression, the shipped 40-tick loop statement sequence and the shipped `ik_step`
     tracking expression (the only change is the `descent_gap` argument), the
     `_force_servo_reset` order, and the say row; the close block builds exactly the two-phase
     ramp and replays it through `follow_centre(..., float(gap))` with the same tracking
     command; the non-keep branch and the ratchet are unchanged; `wide`/`fast_ticks`/
     `load_ticks` are defined earlier in the same function under the same `dynamic_capture`
     local the re-seat guard reads.
   * *resolution truth table* (the real statements, exec'd): 18 rows (three sessions x six env
     states) against an independent reference; with the env unset the knob resolves `False` on
     every session (the shipped branch is taken); `=1` wins on every session; `true` parses
     `False`.
   * *the approach branch* (the real statements, exec'd end-to-end against recording fakes):
     knob off -> `descent_gap == keep_gap` and the gap sequence is exactly `[keep_gap] * 40`
     with no close block (the no-harm replay), the shipped descent gap is below the fruit's
     extent (the `plow` condition reproduced), and the say row is the byte-identical shipped
     string; knob on -> `[gap_open] * 40` + the 84-tick ramp, monotone non-increasing, first
     tick still ~`gap_open`, last tick exactly `keep_gap`, and the geometry invariant
     `0.09 > 0.070 + 0.0113`; the say row gains exactly ` [from-open]`.
3. **The four existing stubs still pass**: `logs/p10c/check_twoline_scope.py`,
   `logs/p10c2/check_confirm_gate.py`, `logs/p9a/check_skip_predicate.py`,
   `logs/p10c3/check_flip_resolution.py` (all exit 0; each also re-checks the `TASKS_MD5` pin).
4. **`scripts/selfcheck.sh`** (`SELFCHECK_LOG=logs/p11c/selfcheck.log`): **PASS, 0 failures, 1
   skipped** (motion budgets - it needs a run log and this lane made no simulator run).
5. **The one-off executed-command-log comparison vs `HEAD`** (throwaway, not committed): the
   ORIGINAL shipped keep-branch statements and the NEW knob-off path were exec'd against
   identical fakes (same fruit pose/velocity, same bindings). The recorded command logs -
   40 `ik_step` targets + 40 `follow_centre` gaps, 80/80 ops - are **identical**. With the knob
   on the same harness records 124 ops: 40 descent ticks at 0.09 m, then the 84-tick ramp from
   0.089974 down to exactly 0.0519 (monotone, equal to the independent
   `np.concatenate([min_jerk_ramp(0.09, 0.052, 24), min_jerk_ramp(0.052, 0.0519, 60)])`).
   This is the strongest offline form of the pre-reg's kill #1 ("the A records must replay
   modulo reporting rows"): the knob-off path issues the same commands in the same order with
   the same values, so the A-side replay is the battery's confirmation, not a re-derivation.

## 5. The battery (deferred, per the pre-registration)

This lane stops before any simulator command. The battery is `logs/p11c/PREREG_REGRASP_ARRIVAL.md`:
arm A = the shipped two-line (no env), arm B = A + `FRUIT_DYNAMIC_REGRASP_FROM_OPEN=1`; the
W6-A patch battery, `SEED=11` primary (the hard seed) + seeds 5/23; the endpoints are the
arrival geometry (per attempt: no descend-at-the-gap contact - the ` [from-open]` marker plus
the absence of the ejection signature), the no-grasp class split (B1/B2/C) and the falls
(`[carry] lowest payload point <= -100 mm`), the outcomes, the `105` motion budgets + the `190`
two-line gate + no new failure reasons, and the cycle (+5 % non-inferiority). The kills: the
knob-off replay fails, the falls/blowups do not disappear on B, a new failure reason appears,
or the acceptance no-harm fails. The battery lane should also re-run the A-side replay check
(the knob-off two-line pair vs the P10-C.3 records modulo reporting rows) and, if its parsers
anchor on the full say line, account for the new ` [from-open]` token.

## 6. Honest limits

1. **No simulator run** - every claim here is static + executed-statement evidence; the
   per-attempt arrival readout, the falls and the class movement are the battery's to measure.
2. **"No descent contact" is a geometric argument**: `gap_open` (0.09) clears the measured
   blocking span (<= 0.0855 with the mesh bias) and the descent travel is only the probe height
   (~6 mm at the two-line profile), but only the battery's traces can confirm it per attempt.
3. **The marginal grip remains marginal**: the from-open close still commands the chased
   sub-width depth *horizontally*; the probe says that geometry does not eject, but a re-seat
   that does not press in cannot restore a lost grip (`C_DECISION.md`: the class may shift to
   B2/C; the rate may not improve). A rate gain is a possible bonus, not the claim.
4. **The reused close constants** (`wide`, `fast_ticks`, `load_ticks`) couple the re-seat close
   to the initial close by construction; retuning the initial close retunes the re-seat close
   with it. That is the "same close shape" requirement, recorded here so it is a decision, not
   an accident.
5. **The ` [from-open]` suffix is a new log token** (only with the knob on). Existing greps
   that match the `(gap N mm kept)` substring are unaffected; a parser anchoring on the line
   end must be updated by the battery lane.
6. **The knob is default-off**: no shipped default changed; the acceptance line and every
   shipped path are untouched by construction (and by the executed-log identity of section 4.5
   on the re-seat path itself).
