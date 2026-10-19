# P17-B implementation: the capture-side levers — H1 (the hold/probe-1 slide gate + the bounded in-place re-centre) and H2 (the freeze-side two-sided-load gate), both default-off and dynamic-capture scoped

Status: **implemented and verified offline only** (branch `p-supply`, 2026-10-19). No simulator run,
no commit; writes only to `src/fruit_sorting/tasks.py`, `src/fruit_sorting/rl_env.py` (the
`TASKS_MD5` pin) and `logs/p17i/`. The Stage-M screen (`logs/p17/CAPTURE_LEVER_DESIGN.md` section 4)
is a separate lane and is **not run here** — this lane delivers the `src/` change and its offline
identity/stub evidence.

The design this implements: `logs/p17/CAPTURE_LEVER_DESIGN.md` sections 2.3 and 4 (the pick: the
hold/probe-1 slide gate + the bounded in-place re-seat, plus the alternative freeze-side straddle
form), with the freeze criterion from `logs/p15/CLOSE_HOLD_DESIGN.md` section 2.2 (the P15's #3).
The mission's knob names (`FRUIT_DYNAMIC_SLIDE_GATE*` / `FRUIT_DYNAMIC_FREEZE_TWOSIDED*`) supersede
the design sketch's `FRUIT_CAPTURE_*` placeholders.

---

## 1. The diff summary

| file | before md5 | after md5 | diff |
| --- | --- | --- | --- |
| `src/fruit_sorting/tasks.py` | `54f70584b07fa249418f1efe30f30af0` | `3d88408dd5e82614dec7768faa17f77a` | +521 / −24 lines |
| `src/fruit_sorting/rl_env.py` | `be0248e0c3b88b28b0ec47ff28e1b68c` | `60f462367b1dcaf926d83ecbb260bc88` | +1 / −1 line (the `TASKS_MD5` pin only) |

Unchanged pins (verified): `src/fruit_sorting/fruits.py` `d28546d26137d4540421caa7fa34a139`,
`src/fruit_sorting/meshes.py` `0e32b1ad1830b04dc0a4bddadfc84a5f`. The two files above are the only
ones this lane modified (`logs/p14c/IMPLEMENTATION.md` shows as modified in `git status` — that is
the concurrent P14-C.1 training lane's work, not touched here). The full diff is
`logs/p17i/implementation.diff`; the pins are `logs/p17i/00_tree_pins.txt`.

The change has four pieces (all default-off, dynamic-capture scoped, byte-inert at default):

1. **The knob block** (`PickAndPlaceTask.__init__`, tasks.py:642-728): eleven env knobs, read
   exactly once each with the shipped defaults — seven H1 (`_slide_gate`, `_slide_gate_mmps`,
   `_slide_gate_ticks`, `_slide_gate_step_mm`, `_slide_gate_max`, `_slide_gate_window_mm`,
   `_slide_gate_diag`) and four H2 (`_freeze_twosided`, `_freeze_twosided_force`,
   `_freeze_twosided_ticks`, `_freeze_twosided_diag`).
2. **The H1 scope + book** (tasks.py:6903-6917, right before the gripper block): `slide_on =
   bool(self._slide_gate and dynamic_capture)` and the per-attempt `slide_book` (allocated only
   when the gate is armed, `None` otherwise). Defined at the function level because the hold runs
   inside the gripper block and the probe-1 section does not.
3. **The H1 integration** (tasks.py:8460-8496 the hold; 8918-8987 the probe-1 block; the ten
   helpers at 10375-10624): the bounded re-centre of the jaw target (the `v * lead` feed-forward
   dropped) and the post-step hand-frame monitor, plus the `[slide]` rows.
4. **The H2 integration** (tasks.py:7877 the scope, 7891-7900 the book/fallback state, 8128-8207
   the freeze block, 8165-8207 the straddle commit, 8209-8236 the horizon fallback; the helpers
   `_freeze2_split`/`_freeze2_step`/`_freeze_twosided_report`): the freeze commits on a two-sided
   load-sustained contact with the shipped criterion as the bounded fallback, plus the `[freeze2]`
   rows.

## 2. The knob semantics

| knob | default | meaning |
| --- | --- | --- |
| `FRUIT_DYNAMIC_SLIDE_GATE` | `"0"` | H1 master switch. `1` arms the hold/probe-1 monitor + response **on a dynamic capture**; `0` = the shipped hold/probe byte-for-byte. |
| `FRUIT_DYNAMIC_SLIDE_GATE_MMPS` | `"60.0"` | Over-band drift-rate threshold [mm/s]. The control bands are the ok ≈ 10 mm/s and the hold-walk B1s 80-140 mm/s (`logs/p14b/TRACE_RESULTS.md`), so 60 sits in the gap. Negative → 0.0. |
| `FRUIT_DYNAMIC_SLIDE_GATE_TICKS` | `"3"` | Consecutive over-band samples before a response latches. Floor 1. |
| `FRUIT_DYNAMIC_SLIDE_GATE_STEP_MM` | `"8.0"` | Bounded per-tick move of the re-centring (and the release walk-back) [mm]. Negative → 0.0 (a zero step keeps the aim where it was: bounded to zero). |
| `FRUIT_DYNAMIC_SLIDE_GATE_MAX` | `"2"` | At most this many responses per attempt. Floor 0 (0 = the monitor runs but never responds). |
| `FRUIT_DYNAMIC_SLIDE_GATE_WINDOW_MM` | `"60.0"` | Recovery window [mm]: accumulated hand-frame drift beyond which the response does not fire (the payload is already out of the span; the B1s' max walk is 54.8 mm). |
| `FRUIT_DYNAMIC_SLIDE_GATE_DIAG` | `"0"` | `1` prints the `[slide]` rows (pure reporting). |
| `FRUIT_DYNAMIC_FREEZE_TWOSIDED` | `"0"` | H2 master switch. `1` makes the freeze commit on the two-sided load-sustained contact **on a dynamic capture**; `0` = the shipped freeze byte-for-byte. |
| `FRUIT_DYNAMIC_FREEZE_TWOSIDED_FORCE` | `"0.5"` | Per-face force floor [N] (the shipped `FRUIT_DYNAMIC_CONTACT_FORCE` value by default). Floor 0.0. |
| `FRUIT_DYNAMIC_FREEZE_TWOSIDED_TICKS` | `"3"` | Consecutive two-sided ticks before the commit (the shipped contact-tick count by default). Floor 1. |
| `FRUIT_DYNAMIC_FREEZE_TWOSIDED_DIAG` | `"0"` | `1` prints the `[freeze2]` rows (pure reporting, control-inclusive). |

## 3. The mechanisms

### H1 — the hold/probe-1 slide gate + the bounded in-place re-centre

**The metric** is the W8-B carry-diag recipe (`logs/w8/B_RESULTS.md`) applied to the window the
P14-B trace localized: `rel_world = fruit_centre − pad_centre` (both post-step, the pads'
*measured* centre for the OpenArm hand), `rel_frame = R_tcpᵀ · rel_world`, the **rate** =
`|rel_world − rel_world_prev| / CONTROL_DT` and the **drift** = `|rel_frame − rel_frame_first|`
(the hand-frame displacement since the monitored span's first sample). The first monitored sample
sets the references (rate 0). The span is the hold + the first probe block (`_regrasp == 0`); the
drift reference and the response budget carry across the two phases, the reporting counters reset
per phase.

**The trigger** latches a response when the rate is ≥ `_SLIDE_GATE_MMPS` for `_SLIDE_GATE_TICKS`
consecutive samples, the accumulated drift is ≤ `_SLIDE_GATE_WINDOW_MM`, and fewer than
`_SLIDE_GATE_MAX` responses have been used. The trigger tick/rate/drift and the first applied step
are recorded.

**The response** (per monitored tick while latched) commands the jaw target that the shipped path
would command (`payload centre + v·lead + standoff`, with the shipped closing-axis x pin/seek kept)
**minus the lead**, approached from the previously commanded target by at most
`_SLIDE_GATE_STEP_MM` per tick — i.e. the command walks onto the payload's measured centre at a
bounded step. The frozen gap and the wrist orientation are not part of the target and are never
touched. The **release** fires when the rate falls back under the band (the arrest); the aim then
walks back to the shipped target under the same step bound (the `releasing` state), so neither edge
of the response is a single-tick command jump. At the phase end a still-latched response is
reported (`end=phase`) and released.

**The rows** (`FRUIT_DYNAMIC_SLIDE_GATE_DIAG=1`, one per response + one summary per phase):

```
[slide] <arm> idx=<i> <hold|probe1> response=<k>/<max> trig@<t> rate=<r>mm/s drift=<d>mm step=<s>mm post=<p>mm/s end=<release|phase>
[slide] <arm> idx=<i> <hold|probe1> summary ticks=<n> events=<k> rate_max=<r>mm/s drift_max=<d>mm
```

`rate=`/`drift=` are the trigger's own values, `step=` the first applied re-centring step,
`post=` the rate at the response's end (the arrest check the design's promotion rule reads).

### H2 — the freeze-side two-sided-load gate

**The split.** The tactile dict is keyed `<side>_<i>`; the shipped OpenArm hand carries the two
finger links as `_0`/`_1`, and the opt-in D2 soft pads append `_2`/`_3` for the same two faces, so
`i % 2` groups the sensors by face (`_freeze2_split` returns the max force per face; empty or
malformed keys read zero).

**The commit.** With the gate on, the shipped "first sustained contact + span stall" criterion
(withholds the commit but remembers its first tick/depth/span — the shipped record). The freeze
commits when **both faces** carry ≥ `_FREEZE_TWOSIDED_FORCE` for `_FREEZE_TWOSIDED_TICKS`
consecutive ticks (`_freeze2_step`), at the delivered command of that tick (so the freeze depth is
the two-sided depth, not the first-contact depth). The frozen-gap bookkeeping after the commit is
the shipped path's (`freeze_cmd` pins `cmd`; `grip_gap = min(grip_gap, last_cmd)`).

**The bounded fallback.** If the shipped criterion fired but the two-sided condition never obtained
within the close's horizon (the close ramp's end), the fallback commits at the **shipped depth**
(`freeze_cmd = shipped_depth`, `last_cmd = shipped_depth`), i.e. the record the shipped line would
have frozen — a near-shipped commit rather than a late/deep one. If neither criterion fired, no
freeze happens (as shipped).

**The rows** (`FRUIT_DYNAMIC_FREEZE_TWOSIDED_DIAG=1`, one per commit, control-inclusive — with the
gate off it reports the shipped commit as the control read):

```
[freeze2] <arm> idx=<i> commit=<shipped|straddle|fallback> tick=<t> depth=<d>mm span=<s>mm ft=(<l>,<r>)N run=<r> ship=<t2>t/<d2>mm|none
```

`ft=` is the per-face load split at the commit, `run=` the two-sided run (0 for a shipped commit,
`run_max` for the fallback), `ship=` the shipped-eligible record (the fallback's own source; `none`
when the shipped criterion never fired before a straddle commit).

## 4. The code sites (at the new md5 `3d88408d`)

| site | lines | what |
| --- | --- | --- |
| `__init__` knob block | 643-728 | the eleven knobs, one read each, negative/zero-clamped |
| H1 scope + book | 6903-6917 | `slide_on`, `slide_book` (allocated only when armed) |
| H2 scope + book + fallback state | 7877, 7891-7900 | `two_sided_gate`, `freeze2_book`, `shipped_depth/tick/span` per close attempt |
| the shipped freeze commit | 8128-8150 | unchanged statements, now under `if two_sided_gate: withhold / else: <shipped>` |
| the straddle commit | 8165-8207 | `_freeze2_step` → freeze at the two-sided depth |
| the horizon fallback | 8209-8236 | commit at the shipped depth when the straddle never obtains |
| the hold loop | 8460-8496 | the bounded re-centre target (8462-8474), the post-step monitor (8478-8479), the phase end (8494-8495) |
| the probe-1 block | 8918-8987 | `begin_phase` (8918), the target (8952), the monitor (8974), the phase end (8986) |
| the H1 helpers | 10375-10545 | `_slide_gate_observe/_target/_report/_summary/_begin_phase/_end_phase/_tick` |
| the H2 helpers | 10547-10624 | `_freeze2_split/_freeze2_step/_freeze_twosided_report` |
| `rl_env.py` | 271 | `TASKS_MD5` pin |

## 5. The scoping and the byte-inert argument

- **Scope.** `slide_on` and `two_sided_gate` are both `... and dynamic_capture`; the freeze block
  that H2 modifies already runs only under `freeze_close and dynamic_capture and freeze_cmd is
  None`. The knobs therefore never touch the indexed/static line, the pad hand's non-dynamic path,
  or any non-dynamic capture. On the two-line scripted catch and the shared-station bimanual they
  apply when set (the design's documented dynamic-capture scope, same as the other capture knobs);
  the direct/policy handover only reaches them with `FRUIT_DYNAMIC_PICK=1`.
- **Byte-inert at default.** With the knobs unset: `slide_on`/`two_sided_gate` are `False`,
  `slide_book` is `None` (no allocation), `freeze2_book` is an unread 4-key dict per close attempt;
  the hold/probe blocks take one `if slide_on:` false branch per tick; the freeze block runs the
  shipped statements unchanged inside the `else` (plus one `if two_sided_gate` false check per
  tick until the freeze); the fallback is one false condition per close attempt. The only added
  work at a shipped commit is the `[freeze2]` helper call, whose argument is a pure dict read of
  the already-read tactile reading (it returns before printing with the diag off). No new reads of
  the articulation, no command-value changes: the shipped `[fruit]`/motion streams are
  byte-identical by construction, and the stub pins the gating and the value-transparency.

## 6. The verification (offline; all PASS)

```bash
python3 -m py_compile src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py   # OK
scripts/selfcheck.sh                                                            # PASS 0 failures, 1 skipped (motion budgets: needs a run log)
python3 logs/p17i/check_slide_gate.py                                           # PASS (new stub)
python3 logs/p16i/check_arrive.py                                               # PASS
python3 logs/p10c/check_twoline_scope.py                                        # PASS
python3 logs/p10c2/check_confirm_gate.py                                        # PASS
python3 logs/p9a/check_skip_predicate.py                                        # PASS
python3 logs/p10c3/check_flip_resolution.py                                     # PASS
python3 logs/p11c/check_regrasp_from_open.py                                    # PASS
```

Evidence files: `logs/p17i/00_checks.txt` (the py_compile + stub-suite transcript),
`logs/p17i/check_slide_gate_output.txt` (the new stub's full output),
`logs/p17i/selfcheck_summary.txt` (the post-change selfcheck legs),
`logs/p17i/implementation.diff` (the full diff), `logs/p17i/00_tree_pins.txt` (the md5s),
`logs/p17i/01_shipped_statement_identity.txt` (the AST-level proof that the shipped freeze
statements and the hold/probe target expressions are the pre-change baseline's verbatim, with the
new code behind the default-off gates).

**The new stub** (`logs/p17i/check_slide_gate.py`, run-anywhere, no simulator) pins:

1. *the knob resolution*: the eleven `__init__` statements are exec'd under env values — unset →
   the shipped defaults, the screen values, explicit zeros → the off forms, negatives → the
   clamps (floats 0.0, tick floors 1, the response cap 0, bools False), `"2"` → off;
2. *the default-off byte-identity*: the real `_slide_gate_target` passes the shipped aim through
   unchanged while unlatched (three synthetic targets) and the real `_freeze2_step` never commits
   below its tick floor; the book literal resolves to `None` with `slide_on` False; all three row
   helpers print nothing with the diags off; the call sites are gated `if slide_on:` /
   `if two_sided_gate ...` (AST/source checks);
3. *the slide logic on synthetic drift sequences*: a stationary sequence never triggers; a
   1.2 mm/tick (144 mm/s) slide triggers after exactly `_TICKS` samples with the reference
   rate/drift/tick; the first latched tick moves exactly `_STEP_MM` toward the payload's centre and
   records it; 12 latched ticks converge with every step ≤ `_STEP_MM`; step=0 is bounded to zero;
   the response budget caps the count at `_MAX` (a second trigger, no third); the release fires on
   the first below-band sample and the aim walks back to the shipped target under the same bound;
   the recovery window suppresses the trigger (3.0 mm vs the 4.0 mm boundary); `_TICKS` binds the
   count;
4. *the two-sided truth table*: `_freeze2_split` on the shipped 2-key and the D2 4-key forms,
   empties, malformed keys and missing attributes; `_freeze2_step`'s sustained-run commit/reset/max
   and the inclusive floor edge (0.5 N ready, 0.4999 not);
5. *the rows' formats*: the real `[slide]`/`[freeze2]` statements exec'd with synthetic bindings
   against exact reference strings (including `ship=none` and the control `commit=shipped` row);
6. the scope/source structure (the call-site counts, the phase bracketing, the fallback gating and
   its `last_cmd = float(shipped_depth)` pin, the pure-reporting property) and
   `rl_env.TASKS_MD5 == md5(tasks.py)`.

## 7. What the screen lane needs (the screen is deferred)

The Stage-M screen (`logs/p17/CAPTURE_LEVER_DESIGN.md` section 4) is **not run by this lane**. When
the screen lane runs it:

- **M1's env line**: `FRUIT_DYNAMIC_SLIDE_GATE=1` + the calibration knobs if they are changed from
  the shipped defaults (`_MMPS` 60.0, `_TICKS` 3, `_STEP_MM` 8.0, `_MAX` 2, `_WINDOW_MM` 60.0) and
  `FRUIT_DYNAMIC_SLIDE_GATE_DIAG=1` for the rows; the design's trace env is unchanged.
- **M1's mechanism read**: the `[slide]` response rows carry the design's three endpoints (the
  trigger's drift rate, the re-seat's step, the post-response drift rate) and the summary rows the
  phase's population (`ticks`/`events`/`rate_max`/`drift_max`); the **hold walk** and the
  **probe-1 dz** still come from the trace (`logs/p14b/trace_p14b_analysis.py` verbatim), as the
  promotion rule specifies. The trigger's specificity is checkable against the control's own walk
  bands without the rows.
- **M2's env line**: `FRUIT_DYNAMIC_FREEZE_TWOSIDED=1` (+ `_FORCE`/`_TICKS` if changed from the
  shipped 0.5/3) and `FRUIT_DYNAMIC_FREEZE_TWOSIDED_DIAG=1`; the same diag on the control run
  gives the control's `commit=shipped` rows (the load split at the freeze, control-inclusive).
- **The `[freeze2]` `run=`/`ship=` fields** answer "the two-sided condition's attainment": a
  `commit=straddle` means the condition obtained (at that tick/depth), a `commit=fallback` means it
  never did within the close (with `run_max` the closest it got), and `ship=` the shipped record the
  fallback used.
- **The knobs are env-only**: no `configs/` change, no reference/fingerprint change at default. If
  an arm is promoted, its log is a *different branch*; per AGENTS §2 quote the per-leg motion and
  the class census, and give a moved branch its own fingerprint if a gate is pointed at it.

## 8. Honest notes and limitations

- **No simulator evidence in this lane.** The *effect* of both forms (whether the response arrests
  the slide; whether the two-sided commit is a better grip; the class re-draw) is exactly what the
  Stage-M screen measures; this lane establishes the implementation identity, the boundedness and
  the row formats only.
- **H1's response is a kinematic re-centre, not a friction change.** The design's K1 (the response
  re-centres the contact but does not change the friction margin) is not addressed by the code: the
  post-response rate is the measured read that decides it, and a response that does not arrest is
  the design's predicted negative.
- **H1's release returns to the shipped lead form** (through the bounded walk-back). The walk-back
  itself is a bounded re-seat of the span; if the screen finds it harmful, that is a screen finding
  (the code keeps the release, the row's `end=` names it).
- **H2's fallback is near-shipped, not bit-shipped**: during the withheld window the close keeps
  commanding deeper (the live clamp/ramp), and the fallback re-pins the *recorded* depth to the
  shipped one at the ramp's end. The withheld window is the treatment's cost on attempts whose
  contact never becomes two-sided.
- **H2's depth coupling is the design's named risk** (the deeper two-sided freeze feeding the
  downstream chain); the `[freeze2]` `depth=` column is the read for it.
- The `[slide]` monitor reads the pads' measured centre + the TCP quaternion per monitored tick
  when armed (the W8-B diag cost class); with the knob off there is no such read.
