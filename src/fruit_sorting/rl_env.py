"""RL rollout environment around the sorting cell's hybrid pick-and-place loop.

P4 (RL post-training): this is the environment the diffusion policy is rolled out
in and scored by, and the one the reward-weighted fine-tune consumes. It is a
wrapper, not a rewrite - the contact work stays `PickAndPlaceTask.grasp_carry_place`
(unchanged), the conveyor/scene stay the shipped build, and `tasks.py` is frozen
at the revision this module asserts by md5.

Two presentations:

``handoff``
    Reproduces ``scripts/60_eval_policy.py`` (the hybrid evaluator) step for step,
    for the P0a check only: the policy drives for ``approach_steps`` control
    iterations, then the fruit is handed to the jaw by teleport (the station
    hand-off) and the deterministic primitive cycle runs. The policy's approach
    does not decide the outcome - which is exactly what P0b measures.

``direct``
    No station hand-off teleport: the fruit keeps moving on the belt. The
    primitive cycle is *triggered by the policy's own close command* - when the
    policy commands ``finger < 0.030`` while the jaw is within 0.06 m of the
    fruit - which is the causal interface the RL work needs. The close trigger
    is the same ``finger < 0.030`` test the hybrid evaluator uses for its
    ``GraspPrimitive`` branch, and the 0.06 m test is the same 2-D
    (cross-belt) proximity test the harness uses for the modelled attach.
    Both fire paths (the learned close gate above and the optional encoder
    intercept trigger) consult the same ``FRUIT_POLICY_TRIGGER_X_MAX``
    reach-cliff refusal (R7-A/WS-4.6): a fruit past the reachable band edge is
    refused at whichever fire tick sees it, and rides past the station.

    ``direct`` starts where the demonstrations do: every recorded `demos_v7`
    episode begins in the scripted pick's wait loop, with the arm already at the
    calibrated grasp pose (`|q-grasp| <= 0.011 rad` at frame 0; no demo frame
    comes closer than 0.220 rad to the ready pose), because the pre-pose before
    it is not recorded. The env therefore parks both arms at ready (like
    `go_ready()` before every collected episode) and puts the active arm at the
    grasp pose. Starting `direct` at the ready pose - as the harness does, and
    as this env did before the P4 Step-1 diagnostic - hands the policy an
    observation no demonstration ever produced.

``direct`` + ``dagger``
    Adds the scripted pick-phase controller as an HG-DAgger expert
    (`ExpertConfig`): each decision point's label is the scripted command for
    that state, and the expert takes control for a short window when the policy
    deviates from it.

``direct`` + ``rtc``
    RTC-style asynchronous chunking (``FRUIT_RTC=1``, see
    ``policy.runtime.RTCSettings``): one action executes per control step and the
    next chunk is sampled *interleaved* with execution (a few denoising steps per
    control step over ``inference_delay`` control steps), its first
    ``inference_delay`` actions frozen to the old chunk's tail and the rest
    soft-inpainted so the boundary is continuous. Default off; the shipped
    synchronous path is unchanged. ``--execute-steps`` is the chunk turnover
    period in both paths, so ``1/2/4`` is the same tight-loop knob.

Observation interface (identical to training): the head-camera frame is rendered
and read every 4 physics ticks (30 Hz), downsampled and buffered by
``PolicyRunner.push_frame``; proprioception is all 22 joint positions + the finger
opening + the two tactile forces (25-D); the goal is the 8-D
``[position(3), velocity(3), diameter, bin_index]`` vector the demonstrations
recorded. Action interface: ``action[:7]`` are the active arm's joint targets,
``action[7]`` is the finger opening clipped to ``[0, 0.044]``, and ``action[8]``
is only recorded (mirrored from ``action[7]``) exactly like the harness.

P28-B (the belt-speed channel, ``FRUIT_OBS_SPEED=1``, default off): a 26th
proprio scalar carrying the belt speed the scripted primitive acts on
(``policy.trigger.transport_speed()``). With the gate unset the 25-D vector above
is assembled exactly as before; with it on, a 26-D checkpoint is required (the
constructor refuses a mismatch) and the second assembly site
(``scripts/60_eval_policy.py``) appends the same scalar through the same helper.
See ``logs/p28/SPEED_CHANNEL_DESIGN.md`` and ``logs/p28i/IMPLEMENTATION.md``.

Mechanics that must not be broken (see AGENTS.md section 3b):
* every advance is ``SimulationManager.step`` + ``update_app(steps=0)``; this
  file never calls ``update_app(steps=N)``;
* ``RenderingManager.render()`` runs before every camera read;
* diagnostics default off and are read-only;
* one simulator at a time is the caller's job.

The manifest written per run records the presentation, ablation, reward config,
camera resolution, checkpoint and the md5 of every source that decided the run,
and the constructor refuses to build when ``src/fruit_sorting/tasks.py`` is not
the revision the environment was validated against.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field

import numpy as np

from .motion import min_jerk_ramp, mirror_across_xz, top_down_quaternion
from .policy.data import belt_speed_scalar, speed_channel_enabled
from .policy.trigger import TriggerSettings, should_fire, x_edge_refusal

#: md5 of `src/fruit_sorting/tasks.py` this environment was validated against.
#: History: `0bc3253a` was the P2/P3 frozen revision; `e553b34e` is that
#: revision plus the P4 recorder-semantics fix (record the commanded joint
#: target, not the measured q - see WORKLOG "P4: the recorder now records the
#: command"); `4e17dd1d` is the revision the RTC phase (P4 fast closed loop)
#: pinned for its A/B - every run's manifest carries it, and
#: `scripts/129_rtc_report.py` cross-checks the source set across runs. A run on
#: a different tasks.py is a different scenario, so the constructor refuses to
#: start instead of writing a manifest that cannot be tied to a tree.
#: `e871231a` is the v5 revision (force-servo knobs + the dynamic lift-origin
#: fix); the B lane's trigger A/B runs on it with `FRUIT_DYNAMIC_FORCE_SERVO`
#: off/on, so the pin was moved from 4e17dd1d when that tree froze.
#: `7decbbc7` was the v6 revision (contact-verification dwell + staged lift,
#: deeper finger face; both default off). `ae841a17` is the v7 revision: the
#: dynamic lift metric is peak-hold (`FRUIT_DYNAMIC_LIFT_PEAK`, default on only
#: while a dynamic capture is active); the indexed path and all control are
#: unchanged, so the policy loop (which never sets `_dynamic_capture_active`)
#: runs the same scenario.
#: `085256b2` is the v5-A integrated revision: the shipped place is the lowered,
#: accompanied descent (`FRUIT_PLACE_LOW=1`, the new default; `=0` restores the
#: historical free drop bit-for-bit). The indexed line's descents are unchanged
#: and the policy loop (which never sets `_dynamic_capture_active`) runs the
#: same scenario with the lowered place at the end of `grasp_carry_place`; the
#: D-entry canary re-measured the hybrid policy path on it (`logs/d_v5entry/`).
#: `3003679b` was the first D2-integrated revision (compliant soft pads opt-in,
#: default off). The D2 lane kept iterating while the entry work ran, and the
#: pin moved with it - it is now `25281bb1`, the revision the second place-low
#: canary ran on (7/10 PASS; `logs/d_v5entry/08_canary_placelow_d2.*`). The
#: re-pin smoke for this revision is queued in `entry_batch3` because the D2
#: lane holds the simulator. The D1 baseline was measured on the earlier
#: `29db6b64` merge and is bit-identical to the pre-merge `085256b2` outputs.
#: The F1 lane moved `tasks.py` again (dynamic line the shipped default, faster
#: dynamic profiles, cycle report), so the pin is now `d47be123`, the revision
#: the F1 acceptance ran on (`logs/fast/11_accept_v7fast_verified.log`; the F2
#: bimanual lane must move it again when it edits `tasks.py`).
#: The P2b lane (left-handover diagnosis + fix) moved `tasks.py`; the pin below
#: is the P2b revision measured in `logs/p2b/` (diagnostic revision first, then
#: the frozen fix revision - the hash follows the file).
#: The final-review pass (2026-10-08) touched only the `_dynamic_pick_mode`
#: docstring (the stale "ceiling is 8/10" -> the Gate-19 9/10), so the pin moved
#: with the docstring-only revision (`2574ceac...`); no control logic changed,
#: and the P2b/G measurements remain valid for this tree.
#: The v9/V1 scattered-supply lane (2026-10-08) changed `select_target` /
#: `_balance_arm`: the moving catch now refuses candidates inside
#: `_dynamic_select_floor()` and takes the farthest-upstream eligible fruit
#: (the documented schedule semantics; the lane path takes the nearest usable
#: one). The policy handover keeps the indexed primitive unless
#: `FRUIT_DYNAMIC_PICK=1`, but the pin follows the file as always.
#: The v9/V3 integration (2026-10-09) froze the V2 two-line tree: the
#: `_prepare_two_line_stations` setup now steps physics explicitly
#: (`SimulationManager.step(10)` + `update_app(0)`, AGENTS section 3b) instead
#: of the non-fixed `update_app(steps=10)`, the two-line scheduler is the
#: explicit opt-in `FRUIT_BIARM_TWOLINE=1` (the pre-registration's decision
#: rule: 1.08x placed/min missed the 1.25x bar), and the station docstrings
#: state the shipped 0.10 m separation. The dynamic-path measurements on this
#: revision are `logs/v3/`; the pin is the frozen revision.
#: The W1/W2 lanes (2026-10-09) then moved `tasks.py` twice (the two-line grip
#: profile, the W2 clearance levers - all measured in `logs/w1`/`logs/w2`), and
#: the W3 lane (2026-10-10) added the pure per-arm grade routing
#: (`FRUIT_GRADE_ROUTING`), the capture token (wave two-line default: one arm in
#: its capture window at a time), allowed the recorder on the two-line branch,
#: and bridged the recorder render; the pin follows the file as always
#: (`logs/w3/`).
#: The W4 gate-30 pass (2026-10-10) added one comment at `_biarm_park`'s broad
#: `except` (a swallowed `AttemptTimeout` is safe because the per-attempt
#: deadline is already cleared); comment-only, so the control path is unchanged
#: and the W3 measurements carry (`logs/w4/`).
#: The W5-C mechanism-screens lane (2026-10-10) added the default-off
#: probe/belt-break x-pin (`FRUIT_DYNAMIC_TAKEOFF_LOCK_X`, `69823dc1`); with the
#: env unset the control path is byte-identical (the cfg0 screen reproduced the
#: W4 `[fruit]` stream; `logs/w5/30_cfg0_rate1.log` vs
#: `logs/w4/20_dense_repeat.log`), so the W3/W4 measurements carry and the H5
#: direct-path trace rides the same branch as `logs/w4/13_direct_v13s_pinned.log`.
#: The W6-C speed-lever lane (2026-10-11) added two default-off, two-line-only
#: knobs (`FRUIT_BIARM_PARK_EARLY` - the park-gate lever; `FRUIT_BIARM_PREFETCH`
#: - L1 prefetch/reserve) plus a prefetch-gated handover log line; with the
#: envs unset the single-arm control path is byte-identical (the acceptance
#: fingerprint matches and the two-line baseline stream reproduces;
#: `logs/w6/`), so the W5-C measurements carry and the pin follows the file as
#: always.
#: The W7-A lane (2026-10-12) flipped `FRUIT_BIARM_PARK_EARLY` to **default on
#: for the two-line session** (`_dynamic_profile("FRUIT_BIARM_PARK_EARLY", "0",
#: "1")`, the W1-profile scoping convention; explicit `=0` restores the pre-W7
#: gate). Single-arm, shared-station and policy paths are byte-unchanged (the
#: single-arm no-harm stream and the acceptance fingerprint match; `logs/w7/`),
#: so the pin follows the file as always.
#: The W7-B lane (2026-10-12) added the default-off, direct-path-only
#: `FRUIT_ACQ_DIAG` acquisition report (a handful of state reads on close
#: boundary ticks; the same single-arm invariance argument holds - the knob is
#: off on every shipped path), so the pin follows the file.
#: The R2 lane (2026-10-13) added the default-off, direct-path-only
#: `FRUIT_POLICY_TRIGGER_X_MAX` reach-cliff guard in `policy/trigger.py` plus
#: the env-side once-per-fruit refusal note, and the default-off,
#: direct-path-only `FRUIT_DIRECT_RESEED` pose-side lever in `tasks.py`
#: (re-seed to the calibrated grasp pose before the direct handover's dynamic
#: blocks; the measured flail class is a setup/pose budget problem, see
#: `logs/w8/R2_RESULTS.md` section 3). Both knobs are unset on every shipped
#: path; the W7-B invariance argument holds and the pin follows the file as
#: always.
#: The R3 speed-lever lane (2026-10-13) added the default-off, two-line-only
#: L2 adaptive selection lead (`FRUIT_BIARM_SELECT_LEAD_ADAPT`, the
#: `FRUIT_BIARM_SELECT_LEAD_S` floor override that now replaces the shipped
#: 1.5 s setup instead of max()ing with it, `FRUIT_BIARM_SELECT_LEAD_MIN/MAX`,
#: and the pure-reporting `FRUIT_BIARM_SELECT_DIAG`) and the L3 hot-arm
#: residency (`FRUIT_BIARM_HOT_ARM` and its hold/settle knobs). Every knob is
#: unset on the shipped paths: the two-line patch control replays the W7-A
#: record bit-identically (821/821 physics lines) and the single-arm
#: acceptance stream is 385/385 identical (`logs/w8/R3_RESULTS.md`), so the
#: W7-B invariance argument holds and the pin follows the file as always.
#: The R11-A adoption attempt (2026-10-15) measured the flip of the
#: reach-anywhere moving catch (`FRUIT_REACH_ANYWHERE=1`) + its priced 60-tick
#: hover settle (`FRUIT_REACH_HOVER_SETTLE=60`) toward the shipped *scripted*
#: defaults and **rejected it by its own gate**: the candidate replays the
#: measured R10-A.1 arm B bit-for-bit on the patch battery, but the shipped
#: scattered acceptance collapses 9/10 -> 4/10 (deterministic; the knob-off
#: control is byte-identical to the pre-adoption record), so the shipped
#: defaults stay off (`logs/r11/A_RESULTS.md`). This revision adds the
#: `select_target(..., reach_anywhere=False)` opt-out at this environment's
#: direct-presentation selection (closing a latent R10-A leak: with the knob
#: on, the direct/policy episode selection would otherwise take the reach
#: branch; the default-off paths are byte-unchanged) and follows the pin from
#: the stale R10-A revision `7e20255c...` (the R10-A.1 `7d6e60fb...` follow
#: was missed, leaving this environment refusing to start) through the
#: measured candidate `c752a90c...` to `b7d6f849...`.
#:
#: R11-B (2026-10-15): the pin follows the pre-onset load-path tree
#: (the md5 below; the three default-off candidates -
#: `FRUIT_CLOSE_LOAD_RATE` / `FRUIT_CLOSE_CONTACT_LEAD` / `FRUIT_PLUCK_DWELL`;
#: `logs/r11/PREREGISTRATION_LOADPATH.md`). **The previous pin
#: (`b7d6f849...`) no longer matched main's `tasks.py` (`c2c7a626...`, the
#: R11-A.1 floored selector) - the R11-A.1 "the pin now follows the final
#: tree" fix was not in the committed R11-A.1 revision, so the direct
#: environment refused to start at `fd2e39e`; this follow repairs both.**
#:
#: P8-1 (2026-10-17): the pin follows the P8-2 load-floor monitor tree - the
#: default-off `FRUIT_CARRY_MONITOR_LOAD_FLOOR` term on `_CarryMonitorLeg`'s
#: hot predicate plus the `asym@fire` diag field
#: (`logs/p8/PREREG_CARRY_MONITOR_LF.md` section 7.2; offline stub pins
#: 29/0/2/33 and 28/0/3/33, `logs/p8c/IMPLEMENTATION.md`). The previous pin
#: `7489f302...` is the P7-2c monitor tree; every shipped default is unchanged
#: (floor default 0.0 is the P7-2b rule exactly).
#:
#: P9-A (2026-10-17): the pin follows the P9-A ready-transit tree - the
#: default-off, single-arm-scoped `FRUIT_READY_SKIP` (B1) and
#: `FRUIT_READY_SETTLE` (B2) knobs plus the pure-reporting `FRUIT_READY_DIAG`
#: readout on the `go_ready` transit (`logs/p9/PREREG_GOREADY_B1.md`; the
#: implementation record is `logs/p9a/IMPLEMENTATION_B1.md`). Every shipped
#: default is unchanged: the two control knobs resolve only inside
#: `_ready_move`'s single-arm scope and are inert when unset.
#:
#: P10-C (2026-10-17): the pin follows the two-line carry-monitor scope tree -
#: the default-off `FRUIT_CARRY_MONITOR_TWOLINE` scope knob that extends the
#: P7-2b/P8-2 carry monitor (the same scorer, the same
#: `FRUIT_CARRY_MONITOR_LOAD_FLOOR` term, the same `FRUIT_CARRY_MONITOR_DIAG`
#: traffic) to the two-line scheduler's own scripted moving catch
#: (`logs/p10/PREREG_MONITOR_TWOLINE.md`; implementation record
#: `logs/p10c/IMPLEMENTATION.md`). Scope-only and default-inert: with the knob
#: unset the two-line never arms (its park/gate/arbiter path is byte-unchanged)
#: and the direct/policy scope is unchanged either way.
#:
#: P10-C.2 (2026-10-17): the pin follows the slip-magnitude confirmation tree -
#: the default-off `FRUIT_CARRY_MONITOR_CONFIRM_MM` gate (default 0.0 =
#: byte-inert: every classifier trip confirms exactly as the P10-C form; a
#: cancelled trip prints one `[monitor] cancel` diag row and leaves the attempt
#: running) plus the monitor-path clean-slip accumulator that keeps the gate's
#: operand live with `FRUIT_CARRY_DIAG` off (`logs/p10c/PREREG_CONFIRM_GATE.md`;
#: implementation record `logs/p10c2/IMPLEMENTATION.md`). Every shipped default
#: is unchanged and no other path is touched.
#:
#: P10-C.3 (2026-10-17): the pin follows the two-line carry-monitor default
#: flip - the W7-A park-gate pattern applied to the P10-C/P10-C.2 monitor
#: (`logs/p10c2/PREREG_ADOPT_FLIP.md`): in a two-line session with the
#: relevant env unset the four monitor knobs resolve to the tested config
#: (monitor 1, scope 1, confirmation gate 8.0 mm, load floor 3.5 N); explicit
#: env values always win and the single-arm, shared-station and direct/policy
#: scopes are byte-inert. The collector manifest gains
#: `collection.carry_monitor` (the W7-C.1 `park_early` pattern; implementation
#: record `logs/p10c3/IMPLEMENTATION.md`).
#:
#: P32 phase A (2026-10-22): metadata-only follow - the bed's selection
#: diagnostic (`select_target(..., diag=...)`, one `is not None` per state when
#: off) and the `FRUIT_BED_DIAG` report hook are comment/list plumbing on the
#: default-off path; no shipped default or control-loop statement moved
#: (proven by the pear-off control's byte-identical acceptance raw run,
#: `logs/p32/81_accept_raw_pear_off.log`).
#:
#: P32 phase D: the follow had gone stale again by the Phase-B/C tree
#: (`ea271ccc` here vs the file's `9277fa64`), so the direct env refused to
#: start; the pin now follows the shipped `tasks.py`. Metadata-only.
#:
#: P39 phase 2: the follow for the default-off `FRUIT_CARRY_ATTITUDE` report
#: (`[attitude]`, reporting only: one TCP-pose read per carry leg, no control
#: input). `RL_TASKS_MD5` is a provenance guard, not a behaviour switch - the
#: direct/policy path is untouched by the changes it names.
#:
#: P39 phase 2, amendment A2.3 (metadata-only follow): `FINGER_TIP_BELOW_JAW`
#: corrected 76.8 -> 80.5 mm (the `[attitude]` `lip`/`tip=` reporting constant,
#: geometry not a contact stop) and the line's axis/corner print added. Still
#: reporting only.
#:
#: P40 G0 (metadata-only follow): the default-off `FRUIT_GRIP_EFFORT=1`
#: readout (`[effort]`, reporting only - the finger drive's applied effort
#: beside the tactile `N`, one 5-tick median per event; no command, threshold
#: or control path is touched).
#:
#: P40 R-S (metadata-only follow): the default-off
#: `FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1` single-arm selection rule (nearest
#: floored candidate instead of the farthest-upstream one; the two-line
#: selector, `_dynamic_select_floor` and the aim are untouched). Scope: it is
#: the `lane is None and prefer_lane is None` return, so the two-line selector
#: and the reseed path here (`lane=int(self._bin_index)`) never reach it - but
#: this environment's *episode* selection (`rl_env.py:1656`, no lane) would, so
#: a direct-loop use of the knob is a new configuration, not the shipped one.
#: The knob is unset everywhere in this tree.
#:
#: P40 phase 4 (metadata-only follow): the `FRUIT_REGRASPS` probe cap is now
#: PATH-SCOPED - `2` on the dynamic capture line, `3` on the indexed /
#: policy-handover path (`tasks.py`, `regrasp_cap`), with an explicit env value
#: winning on both. The 17/17 zero-conversion third-probe evidence is the
#: dynamic line only; the indexed retry is a different mechanism.
#: P41 phase 2 (default-off reporting only): the W8-B `[carry]` diag line
#: gains `sep@loss` (the pad span on the tick contact is lost - the W8-B
#: 98-99 mm pry read, live) and `sep_end`. Both exist only under
#: `FRUIT_CARRY_DIAG=1`; with the knob unset the run is unchanged.
#: P42 phase 1 (default-off reporting only): the `[seat]` census row
#: (`FRUIT_SEAT_DIAG=1`) prints the pads' midpoint minus the fruit's centre in
#: x/y/z at the close freeze and at four bounded carry ticks. Unset = inert.
#: P42 phase 2 (default-off lever): `FRUIT_SEAT_CENTRE=<m>` is ONE bounded
#: pre-close re-aim of the pads' midpoint onto the fruit's centre (`clip` at the
#: registered 20 mm per axis, x/y only, no re-approach). Scope: the scripted
#: OpenArm moving catch - the direct/policy handover and the two-line scheduler
#: are not armed, so this environment's path never reads it. Unset = one float
#: test per close, i.e. inert.
#: The P42 phase-3 pin records the **comment-only** docstring correction on
#: `_seat_centre_step` (`3e6ea4cf -> e2d0f12a`): the close's own `coherent` flag
#: is True on this hand and the close re-aims every tick, so the one-shot lever is
#: absorbed and the freeze's 1.4-4.6 mm is servo following error. No byte of code
#: changed - the measured runs (`logs/p42/p3/`, P2_RESULTS) ran `3e6ea4cf`.
#:
#: P43 phase 2 (metadata-only follow, `e2d0f12a -> a1b3d673`): `select_target`
#: gains the `direct` keyword, which only resolves the **default** of
#: `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` (always `"0"` for this env's episode
#: selection; the scripted line reads the module constant
#: `NEAREST_ABOVE_FLOOR_SCRIPTED`, **off** in the shipped tree - the P43 flip was
#: measured and not adopted, `logs/p43/P2_RESULTS.md`). The rule itself is
#: unchanged and this env passes `direct=True`, i.e. it keeps the
#: farthest-upstream pick byte-for-byte. An explicit env value wins on both paths
#: (`=1` reproduces the measured treatment arm with no code change).
#:
#: P62 phase 2 (metadata-only follow, `9a5e0459 -> fe11910a`): `PickAndPlaceTask`
#: gains the caller-owned kwarg `grasp_quat_override` and `_grasp_quat` returns
#: that arm's entry when present. The default is `None`/empty everywhere, so
#: every caller (scripted line, collector, two-line scheduler, hybrid canary)
#: reads the waypoints file byte-for-byte; the only armed caller is this env,
#: behind `FRUIT_GRASP_LEFT_TOPDOWN=1` (default off, `direct` only), and on this
#: tree it resolves to the attitude `configs/waypoints.json` already carries.
#:
#: P65 phase 1 (metadata-only follow, `7a8a163a -> 309e5a38`): the `[carry]`
#: row gains five reporting-only fields under `FRUIT_CARRY_DIAG` (the measured
#: joint-limit margin and its binding joint, the same for the controller's
#: post-clip command, the command's largest per-tick step, the jaw-opening
#: axis' world z, and the first tick the hold drift passes 10 deg). Nothing in
#: `tasks.py` changes behaviour: the whole block needs `_carry_guard_active or
#: _carry_diag` (the knob is default off) **and** `_dynamic_capture_active`, so
#: the scripted line cannot reach it (377/377 `[fruit]` lines identical).
#:
#: P66 phase 2 (metadata-only follow, `309e5a38 -> 7edf4324`): the `[carry]` row
#: gains three more reporting-only fields under the same `FRUIT_CARRY_DIAG`
#: (`drift_end`, the **last** guarded tick's hold drift rather than the max;
#: `res_end`/`dz_end`, the achieved TCP position error at the leg's end against
#: the target the same tick issued - the target is the array `ik_step` was handed
#: and `tcp_pose()` already returns the position, so **no new read**), and
#: `PickAndPlaceTask` gains the caller-owned kwarg `lift_dz`, applied by
#: `tasks.lift_dz_for` at `_carry`'s `grasp_lift` end pose. `None` (every caller
#: but this env) does no arithmetic at all, so the scripted line's targets are
#: byte-for-byte the shipped ones; the only armed caller is this env behind
#: `FRUIT_LIFT_DZ` (default off, `direct` only).
#:
#: P66 phase 3 (metadata-only follow, `7edf4324 -> d41d8e1c`): the same row gains
#: `clr=` (the leg's **minimum** payload clearance to the highest surface under
#: it - P2-3's `_payload_clearance`, already measured every tick in the slip
#: bookkeeping, so again **no new read**, and its surface code `@belt/@obelt/
#: @rail` because the +33 mm access floor of record is the *rail*'s), and the
#: `direct` presentation's `FRUIT_LIFT_DZ` **default** becomes the 0.20 m rung
#: (`LIFT_DZ_DIRECT_DEFAULT`; `+0.08` restores the shipped 0.36 m). Both are
#: print/no-op for every scripted path (they never construct this env).
#:
#: P66 phase 4 (metadata-only follow, `40e196e8 -> 1296bd44`): only the `clr`
#: reduction changes - `clr=` becomes the **rail-crossing** sample (the first
#: tick whose |payload y| reaches the inner rail's centreline, 0.4125 m, derived
#: by `_output_rail_y`) with the transfer-window minimum beside it (`clr_win=`)
#: and P3's leg minimum kept as `clr_min=`; one pure formatter
#: (`_clearance_field`), still no new read, so every scripted and direct
#: trajectory is byte-unchanged.
#:
#: P67 (metadata-only follow, `1296bd44 -> e5168578`): `PickAndPlaceTask` gains
#: the caller-owned kwarg `lift_climb` (applied by `tasks.lift_climb_for` in
#: `_carry`) - the **climb re-shape** of P66 phase 4's failed rail-crossing gate:
#: a vertical raise at the **place leg's** start, before the transit, so the
#: crossing (only 0.175:1 with the lift height) is bought at 1:1. `None` (every
#: caller but this env behind `FRUIT_LIFT_CLIMB`, default off, `direct` + left)
#: keeps `transit_start is start`, i.e. the shipped command list is built by
#: exactly the same expressions; the climb is a prepended waypoint that leaves
#: the leg's end pose (the release geometry) untouched.
#:
#: P70 (metadata-only follow, `e5168578 -> 7c00e555`): the clearance report reads
#: the **authored** rail instead of a hard-coded 0.035 (`_payload_clearance` now
#: tests `output_rail_keep[0]` and adds `SceneConfig.output_rail_proud =
#: output_rail_height - OUTPUT_RAIL_INSET`), so `clr`/`clr_win` follow
#: `FRUIT_OUTPUT_RAIL_HEIGHT` and fall through to the belt top when the inner
#: rail is dropped; and the scene gains the `FRUIT_OUTPUT_BELT_TOP_Z` knob
#: (default 1.35 = the shipped geometry). Print/report only - nothing on the
#: control path reads either, and at the shipped geometry the reported surface
#: is the same to 1e-12 m (`scripts/238_p70_belt_top_selftest.py`).
#:
#: P73 (metadata-only follow, `f61323f2 -> adcfd348`): the `[carry]` row gains
#: the **rotation schedule** (`tilt0`/`tilt_end`/`tilt_max`/`t45`/`t75`/
#: `tilt_rate`) - the achieved tilt from world -Z accumulated per guarded tick
#: inside the existing `if guard_armed:` block. Pure arithmetic on `rot_now`,
#: which is that block's own read for `clean_slip`: no new articulation read, no
#: command, threshold or control path touched, and the whole block is still gated
#: by `FRUIT_CARRY_DIAG` (default "0"). `logs/p73/PREREG.md` §3.
#:
#: P76 (metadata-only follow, `303d025d -> 9d5824ef`): the `[carry]` row gains
#: the **pry/crush** group (`dia`, `sep_max=…@t<tick>`, `gap@sep_max`, `sep_min`,
#: `fmax`) - reporting only, inside the same `if guard_armed:` block, gated by
#: `FRUIT_CARRY_DIAG` (default "0"). One added `jaw_separation()` per guarded
#: tick (the read `sep@onset`/`sep@loss`/`sep_end` already take at their own
#: ticks); no command, threshold or control path touched. `logs/p76/PREREG.md`
#: §3.
#:
#: P78 (metadata-only follow, `9d5824ef -> b1464c43`): the P77 scoped-finger-
#: force form. `_carry` becomes a wrapper (the leg body is `_carry_leg`) that
#: raises the left finger drive's live `maxForce` for a `place*` leg and restores
#: it in a `finally`; the new pure resolver `finger_cap_scope_for` and the new
#: caller-owned kwarg `finger_cap_scope` are `None` on every path that does not
#: pass it (so the scripted line, the collector, the two-line scheduler and the
#: hybrid canary run the shipped leg with one dict lookup and no write/read).
#: `FRUIT_FINGER_MAXFORCE_SCOPE` is default off and `direct`-only
#: (`rl_env.resolve_finger_cap_scope`). `logs/p78/PREREG.md` §2.
#:
#: P79 (metadata-only follow, `b1464c43 -> e8dfa6d8`): the **pick half** of the
#: same form. `finger_cap_scope_for` now keys on `"<side>:<legs>"` and resolves
#: two disjoint carry-leg classes - `place*` (P78's `place-left`) and
#: `grasp_lift` (P79's `grasp-left`) - so a lift-only cap cannot move the place
#: transfer and a place-only cap cannot move the pick. Default off, `direct`
#: only, same wrapper and same `finally` restore; the shipped path is one dict
#: lookup, unchanged. `logs/p79/PREREG.md` §2.
#: P83 follow is **metadata-only**: `FRUIT_FAIL_FAST=<mm>` (default unset/0 = off)
#: is a **`scripted`-only** knob read by `PickAndPlaceTask.__init__`, so the
#: direct env neither arms it nor can reach it - the pin below follows the new
#: `tasks.py` hash without a behaviour change on this path.
#: P87 follow is **metadata-only** too: the release clock's two-line default is
#: scoped by `Task.two_line_enabled()` (a `CoopSession` predicate this env never
#: satisfies) and the manifest builder passes `two_line=False`, so the direct
#: path's release clock is the shipped 20/3/3 unless an explicit
#: `FRUIT_SPEED_RELEASE`/`FRUIT_SPEED_ALL` says otherwise.
TASKS_MD5 = "32efa98c20d31d8014db7389a6e7e35e"

#: Repository root, derived from this file (`src/fruit_sorting/rl_env.py`).
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


#: P62 phase 2: the left-only, direct-scoped grasp attitude candidate **T0** -
#: fingers straight down, jaws exactly across the belt, `[w, x, y, z]`, written
#: here as the full-double form (`-0.7071067811865475 / +0.7071067811865476`,
#: i.e. the registered `-0.70710678 / +0.70710678` to 8 dp) that
#: `configs/waypoints.json` already carries, so the override is bit-identical to
#: that file's left value rather than 1e-9 away from it.
#: Source: `logs/p62/CANDIDATES.md` §3 - it is the reach harness's own
#: `top_down_quaternion("x")` mirrored for the left. Its tool axis is `(0, 0, -1)`,
#: so the belt's world `-y` drag has **zero** component along the finger axis
#: (`proj 0.000`, against the `waypoints_oriented.json` attitude's `+0.513`).
GRASP_LEFT_TOPDOWN = (0.0, -0.7071067811865475, 0.7071067811865476, 0.0)


def _tool_belt_proj(q) -> float:
    """`(tool axis) . (belt direction)` for a `[w, x, y, z]` tool quaternion.

    The belt runs toward world `-y` (`fruits.py` sets the conveyor's surface
    velocity to `[0, cfg.belt_speed, 0]` with a negative `belt_speed`), and the
    tool axis is the TCP frame's column 2 (`motion.top_down_quaternion`'s
    convention: "column 2 [is] the direction the fingers extend"). Pure numpy;
    used only by the P62 `[grasp]` row, never as a control input.
    """
    w, x, y, z = (float(v) for v in q)
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    tool = np.array(
        [
            2 * (x * z + y * w),
            2 * (y * z - x * w),
            1 - 2 * (x * x + y * y),
        ]
    )
    # `+ 0.0` folds a signed zero to `+0.0`, so a zero projection prints
    # `+0.0000` rather than `-0.0000` (the belt points along -y, so the
    # negated y-component is the natural signed form).
    return float(-tool[1]) + 0.0


#: ---------------------------------------------------------------------------
#: P64 phase 1: the **measured** left `grasp_lift` achieved-attitude drift and
#: its pre-compensated command (default off; `direct` + left only).
#:
#: The chain P61-P63 measured: the left is **commanded** T0 (fingers straight
#: down, `GRASP_LEFT_TOPDOWN` = `configs/waypoints.json`'s left value) and
#: **achieves** a 25-29 deg tilt whose azimuth is the belt axis (tool `y`
#: -0.32..-0.37, downstream, while the right's azimuth lands across the belt).
#: The command path is exhausted (the P62 world-z yaw family never solves at
#: this station and its `_grasp_quat` channel is inert on the achieved
#: attitude), so the remaining object is the **tracking residual** and the only
#: lever is to ask for the inverse of it.
#:
#: Derived in `logs/p64/p1/derive.py` from the `[attitude] ... tool_axis=` rows
#: of seven left `grasp_lift` legs in the P63 cell's own scenario/checkpoint
#: (`logs/p63/p2/A1_77.log`, 3 legs; `logs/p62/p2/P0{A,B}.log` and
#: `P0b{A,B}.log`, 1 leg each), **median over the legs** of the achieved tool
#: axis and of the tilt:
#:
#:   median achieved tool axis (+0.303490, -0.350929, -0.885857), belt
#:   projection +0.3509; per-leg tilt 25.1-28.7 deg (median 26.80), per-leg
#:   azimuth -127.2..-133.6 deg from +y (spread +-3.2), per-leg projection
#:   +0.3210..+0.3658 -> a single constant is a first-order model of a
#:   residual that varies by ~1.8 deg in magnitude and ~3 deg in azimuth.
#:
#: `q_drift` is the **minimal** rotation from the commanded axis (0, 0, -1) to
#: that median: axis = (0,0,-1) x t = (t_y, -t_x, 0) normalized, angle =
#: acos(-t_z) (the brief's definition; a roll about the tool axis is not
#: observable from the axis and does not move it). The command is the inverse
#: on the **left** - `q_cmd = q_drift^-1 (x) q_T0`, i.e. the world-frame
#: residual model `q_ach = q_drift (x) q_cmd` - which is the brief's registered
#: form; `q_T0 (x) q_drift^-1` is the tool-frame alternative (`logs/p64/p1/
#: derive_out.txt` prints both, the registered one is used).
#:
#: **Caveat, measured by P62 and re-read in the code for this phase:** the
#: `GRASP_LEFT_TOPDOWN`/`grasp_quat_override` channel (`tasks._grasp_quat`) is
#: **not** what the lift runs - the never-stop catch releases it before the
#: descent and installs its own top-down hold, which `_carry` then inherits on
#: `grasp_lift` (the clear is `name != "grasp_lift"`). So this knob does **not**
#: reuse that kwarg: it passes `carry_hold_override` to `PickAndPlaceTask` and
#: `tasks.carry_hold_override_for` writes `arm.hold_quaternion` for the
#: `grasp_lift` leg only - the command `ik_step` actually tracks during the lift.
#: The grip itself is still taken at the shipped attitude (one leg, not the
#: hover/descent/close), so the P42/P61 seat geometry is untouched.
P64_LEFT_DRIFT_AXIS = (-0.756380334927, -0.654132088294, 0.0)
P64_LEFT_DRIFT_ANGLE_DEG = 26.798198


def _quat_conjugate(q) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    return np.array([q[0], -q[1], -q[2], -q[3]], dtype=float)


def _quat_mul(a, b) -> np.ndarray:
    """Hamilton product, `[w, x, y, z]`: `R(a (x) b) = R(a) R(b)`."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    w1, v1 = float(a[0]), a[1:]
    w2, v2 = float(b[0]), b[1:]
    return np.array(
        [w1 * w2 - float(v1 @ v2), *(w1 * v2 + w2 * v1 + np.cross(v1, v2))],
        dtype=float,
    )


def _quat_from_axis_angle(axis, angle_deg: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis = axis / max(float(np.linalg.norm(axis)), 1e-12)
    half = math.radians(float(angle_deg)) / 2.0
    return np.array([math.cos(half), *(math.sin(half) * axis)], dtype=float)


def left_precomp_quat(axis, angle_deg: float, commanded) -> np.ndarray:
    """`q_drift^-1 (x) q_cmd`, normalized, `[w, x, y, z]` (pure; pinned by `234`).

    `q_drift` is built from `axis`/`angle_deg` (the measured residual), and the
    result is the command whose *predicted* achieved attitude is `commanded`.
    """
    q_drift = _quat_from_axis_angle(axis, angle_deg)
    q = _quat_mul(_quat_conjugate(q_drift), np.asarray(commanded, dtype=float))
    return q / max(float(np.linalg.norm(q)), 1e-12)


#: The resolved command (one array, built at import from the two constants).
GRASP_LEFT_PRECOMP = left_precomp_quat(
    P64_LEFT_DRIFT_AXIS, P64_LEFT_DRIFT_ANGLE_DEG, GRASP_LEFT_TOPDOWN
)


def resolve_carry_hold_override(
    presentation: str, env_value: str | None
) -> dict[str, np.ndarray] | None:
    """The resolved `FRUIT_GRASP_LEFT_PRECOMP` carry-hold override, or `None`.

    P64 phase 1: **direct-scoped and left-only, default off**. Returns
    `{"left": GRASP_LEFT_PRECOMP}` only for `presentation == "direct"` with an
    explicit `FRUIT_GRASP_LEFT_PRECOMP=1`; every other combination returns
    `None`, which is the shipped `PickAndPlaceTask(carry_hold_override=None)`
    path (no write to any arm's hold). The scripted line, the collector, the
    two-line scheduler and the hybrid canary never construct this env.
    """
    if presentation != "direct":
        return None
    if (env_value if env_value is not None else "0") != "1":
        return None
    return {"left": np.asarray(GRASP_LEFT_PRECOMP, dtype=float)}


def resolve_grasp_quat_override(
    presentation: str, env_value: str | None
) -> dict[str, np.ndarray] | None:
    """The resolved `FRUIT_GRASP_LEFT_TOPDOWN` override, or `None` (shipped).

    P62 phase 2: **direct-scoped and left-only, default off**. The scripted
    line, the collector, the two-line scheduler and the hybrid canary never
    construct this env, so they keep `configs/waypoints*.json`'s attitude
    byte-for-byte (the constraint `logs/p62/CANDIDATES.md` §5.4 registers).

    An explicit `FRUIT_GRASP_LEFT_TOPDOWN=1` on the direct presentation returns
    `{"left": T0}`; every other combination returns `None`, which is the
    shipped `PickAndPlaceTask(grasp_quat_override=None)` path.
    """
    if presentation != "direct":
        return None
    if (env_value if env_value is not None else "0") != "1":
        return None
    return {"left": np.asarray(GRASP_LEFT_TOPDOWN, dtype=float)}


#: P66 phase 3: the `direct` presentation's default lift-height offset, in metres
#: above `tasks.jaw_target("grasp_lift")`'s `belt_top + 0.28` base. `-0.08` is
#: **0.20 m above the belt** - the phase-2 `L2` rung, which moved the left's
#: `drift_end` from 23.8-25.7 deg to 0.7 deg and its placed count from 1/34 to
#: 10/16 (`logs/p66/P2_RESULTS.md`). The value is expressed on the **code's** base
#: (the `0.28`), never on the shipped height: "shipped - 0.16" would be 0.12 m,
#: i.e. the pads 40 mm above the belt (`logs/p66/DEVIATION.md` D4/D5).
#:
#: **P71: this is `-0.08` again, and now it ships.** P66 P4 had reverted it to
#: `+0.08` (the shipped 0.36 m) because gate (a) - the rail crossing - failed at
#: `+5 mm` against the +33 mm floor (`logs/p66/P4_RESULTS.md`); the reverting
#: brief said the rung stays opt-in "until the named re-shape is registered and
#: measured". P67/P68 measured the climb re-shape (it clears the crossing but
#: drops the payload on 3/8 place legs) and P70 measured the geometry instead:
#: **removing the output belts' side rails raises the crossing 1:1 (+35 mm) and
#: is inert on this scenario** (`logs/p70/RESULTS.md`), so the rung's gate (a)
#: now passes for a reason that costs the carry nothing - and the rung's own
#: win is the left's 25 deg carry rotation (0/25 -> 14/25, N = 5). Both are
#: defaults as of P71 (`FRUIT_LIFT_DZ=+0.08` restores the 0.36 m lift; the
#: `FRUIT_OUTPUT_RAILS=both` restore is `assets.SceneConfig`'s).
#: `+0.08` (the shipped 0.36 m) is the documented restore and is bit-identical
#: to the pre-P71 unset path.
LIFT_DZ_DIRECT_DEFAULT = -0.08
#: The hand's own clearance add above the same base (`FRUIT_OPENARM_TRANSFER_LIFT`'s
#: default), i.e. the shipped `grasp_lift` height. `FRUIT_LIFT_DZ=+0.08` restores
#: it and is the documented escape from the phase-3 default; the env var still
#: wins at the *task*, so this constant is the restore's value, not a second
#: source of truth for the target.
LIFT_DZ_HAND_ADD = 0.08


def resolve_lift_dz(
    presentation: str, env_value: str | None
) -> tuple[dict[str, float] | None, bool]:
    """The resolved `FRUIT_LIFT_DZ` lift-target-height offset, and its origin.

    **P71: `direct`-scoped and left-only, and the `direct` presentation's default
    is the 0.20 m rung** (`LIFT_DZ_DIRECT_DEFAULT = -0.08` above
    `tasks.jaw_target("grasp_lift")`'s `belt_top + 0.28` base; `FRUIT_LIFT_DZ=+0.08`
    restores the pre-P71 shipped 0.36 m). `dz` **replaces** the hand's
    `FRUIT_OPENARM_TRANSFER_LIFT` add on that leg, so the ladder reads
    `+0.08` = the shipped `0.36 m` (the documented restore), `0.00` = `0.28 m`,
    `-0.08` = `0.20 m`. The code's base is the `0.28`, **not** the shipped
    height: a value written as "0.36 + dz" (the phase-3 brief's `-0.16`) would
    put the pads 40 mm above the belt (`logs/p66/DEVIATION.md` D4/D5).

    History: P66 phase 3 flipped this to `-0.08`, P4 reverted it when the rung's
    rail-crossing gate failed, and P71 flips it back because the gate's *obstacle*
    was removed instead (`FRUIT_OUTPUT_RAILS=none` is the P71 default, +35 mm 1:1,
    `logs/p70/RESULTS.md`) - so the carry win and the crossing both hold.

    Returns `(offsets, defaulted)`, the P43 `resolve_arm_park` shape:

    * any presentation but `direct` -> `(None, False)`, the shipped
      `PickAndPlaceTask(lift_dz=None)` path with **no target arithmetic at all**
      (so the scripted line, the collector, the two-line scheduler and the
      hybrid canary are byte-inert - none of them constructs this env);
    * `direct`, value unset -> `({"left": LIFT_DZ_DIRECT_DEFAULT}, True)`: the
      P71 default, and the manifest's `defaulted: true` tells a post-flip
      store from an explicit arm;
    * `direct`, value set -> `({"left": dz}, False)`, parsed strictly. `+0.08`
      restores the shipped height (the same two float adds, so a `+0.08` arm's
      targets are bit-identical to the pre-P71 unset path); an empty value is
      the same explicit restore (the P43 `FRUIT_ARM_PARK=ready` precedent).

    Strict parsing is the P44/P45/P52/P53 precedent: a typo that fell back to
    the shipped height would be published as a null result, so a non-number and a
    non-finite value raise.
    """
    if presentation != "direct":
        return None, False
    text = "" if env_value is None else str(env_value).strip()
    if env_value is None or not text:
        if env_value is None:
            return {"left": LIFT_DZ_DIRECT_DEFAULT}, True
        return {"left": LIFT_DZ_HAND_ADD}, False
    try:
        dz = float(text)
    except ValueError:
        raise ValueError(
            f"FRUIT_LIFT_DZ={env_value!r} is not a number of metres"
        ) from None
    if not math.isfinite(dz):
        raise ValueError(f"FRUIT_LIFT_DZ={env_value!r} is not finite")
    return {"left": dz}, False


def resolve_lift_climb(
    presentation: str, env_value: str | None
) -> dict[str, float] | None:
    """The resolved `FRUIT_LIFT_CLIMB` place-leg climb, or `None` (shipped).

    P67: the **climb re-shape** of P66 phase 4's failed rail-crossing gate. The
    P66 measurement: the 0.20 m rung's place transit crosses the output rail's
    centreline at `+5 mm` against the `+33 mm` access floor, because the crossing
    sits 82.5 % of the way along the leg's `y` span, so only
    `1 - 0.825 = 0.175` of the lift's deficit is recovered there
    (`logs/p66/P4_RESULTS.md` §4). The lever that **is** 1:1 with the crossing is
    the height at the **start of the place transit**, so this knob raises the
    pads by `climb` metres **vertically at the lift's own x/y** before the
    transit begins, and the leg still ends at `jaw_target` (the release geometry
    is untouched). It is applied by `tasks.lift_climb_for` in `_carry` as a
    **prepended waypoint**.

    Scope: `direct` only, left arm only, `None` = **no arithmetic at all** - not
    "a climb of zero": `_carry` then keeps `transit_start is start`, so every
    cached print and the whole shipped command list are byte-identical. There is
    no presentation default (unlike `FRUIT_LIFT_DZ`): the re-shape is opt-in.

    Strict parsing is the P44/P45/P52/P53/P66 precedent: a climb is a **positive**
    number of metres, so a non-number, a non-finite value and `<= 0` raise (the
    off state is the unset or empty value, never `0`).
    """
    if presentation != "direct":
        return None
    text = "" if env_value is None else str(env_value).strip()
    if not text:
        return None
    try:
        climb = float(text)
    except ValueError:
        raise ValueError(
            f"FRUIT_LIFT_CLIMB={env_value!r} is not a number of metres"
        ) from None
    if not math.isfinite(climb):
        raise ValueError(f"FRUIT_LIFT_CLIMB={env_value!r} is not finite")
    if climb <= 0.0:
        raise ValueError(
            f"FRUIT_LIFT_CLIMB={env_value!r}: a climb is positive metres "
            "(leave it unset for the shipped path)"
        )
    return {"left": climb}


#: P78: the token `FRUIT_FINGER_MAXFORCE_SCOPE` accepts. The scope is one
#: **site** - P77 §2 measured that every escape and every pry, in both arms, is a
#: left `place0` leg (C 7/38 escaped and 4/38 pried, T 3/40 and 1/40, right 0 and
#: P78/P79: the two scoped sites, as `token -> (side, leg class)`. The class is
#: the **carry-leg class** `tasks.finger_cap_scope_for` resolves against
#: (`place*` for `place-left`, `grasp_lift` for `grasp-left`); the two are
#: disjoint, so neither token can arm the other's legs. P78 shipped
#: `place-left`; P79 adds `grasp-left` to isolate the **pick** half of P77's
#: global 60 N arm.
FINGER_CAP_SCOPE_TOKENS: dict[str, tuple[str, str]] = {
    "place-left": ("left", "place"),
    "grasp-left": ("left", "grasp"),
}
#: The P78 token, kept named for the `place*`-scoped documents and the 244 leg.
FINGER_CAP_SCOPE_TOKEN = "place-left"
#: P78: the scoped cap used when `FRUIT_FINGER_MAXFORCE_SCOPED` is unset - the
#: P77 `T` rung (60 N per joint, ~53 N delivered), which is the only dose this
#: tree has measured at three seeds. The ladder passes it explicitly.
FINGER_CAP_SCOPE_DEFAULT = 60.0
#: The leg name a scope's class arms, for the `[drive] finger cap scope` row.
#: The manifest carries the class itself (`"grasp"` / `"place"`), not this text.
FINGER_CAP_LEG_TEXT: dict[str, str] = {"grasp": "grasp_lift", "place": "place*"}


def finger_cap_scope_label(scope: dict | None) -> str:
    """The token a resolved scope dict came from (`grasp-left`), `""` when off.

    Pure, derived from the dict's own keys (`"<side>:<legs>"`), so the row can
    never print a token the resolver did not resolve.
    """
    if not scope:
        return ""
    out = []
    for key in sorted(scope):
        side, _, legs = str(key).partition(":")
        out.append(f"{legs}-{side}")
    return "+".join(out)


def finger_cap_scope_legs(scope: dict | None) -> str:
    """The leg names a resolved scope dict arms (`grasp_lift`), `""` when off."""
    if not scope:
        return ""
    classes = sorted({str(key).partition(":")[2] for key in scope})
    return "+".join(FINGER_CAP_LEG_TEXT.get(cls, cls) for cls in classes)


def resolve_finger_cap_scope(
    presentation: str,
    scope_value: str | None,
    cap_value: str | None,
    global_value: str | None,
) -> tuple[dict[str, float] | None, float | None]:
    """The resolved `FRUIT_FINGER_MAXFORCE_SCOPE` write, or `None` (shipped).

    P78: a **runtime, per-leg** finger-drive force cap - the shippable form of
    P77's 60 N count win. P77 measured the win (left placed 11/21 -> 17/20,
    Fisher p = 0.043, 3/3 seeds) and its price: the cap is a per-joint drive
    property written at build time on **both arms of every presentation**, so a
    global flip moves the scripted acceptance at attempt 0 (`fingerprint:
    DIFFERS`) and the two-line's fingerprint too, and owes both motion
    references, a scripted re-baseline and every store's provenance.

    This resolver is the containment. It returns `(scopes, cap)`:

    * any presentation but `direct` -> `(None, None)`: the shipped
      `PickAndPlaceTask(finger_cap_scope=None)` path, with **no resolver call,
      no write and no read** on that path at all - the scripted line, the
      collector, the two-line scheduler and the hybrid canary never construct
      this env, so "no blast radius" is structural before it is measured;
    * `direct` with the scope unset or empty -> `(None, None)`;
    * `direct` with an **explicit** `FRUIT_FINGER_MAXFORCE` -> `(None, None)`:
      the existing global knob wins, so the global path keeps its meaning and
      the two cannot stack;
    * `direct`, scope `place-left` -> `({"left:place": cap}, cap)`; scope
      `grasp-left` (P79) -> `({"left:grasp": cap}, cap)`. The key carries the
      leg **class** because it is the dict's own scope: `place*` for
      `place-left`, `grasp_lift` for `grasp-left`, disjoint by construction
      (`tasks.finger_cap_scope_for`). The cap comes from
      `FRUIT_FINGER_MAXFORCE_SCOPED` (default `FINGER_CAP_SCOPE_DEFAULT`),
      parsed strictly.
    Strict parsing is the P44/P45/P52/P53/P66 precedent: a typo that fell back to
    the shipped cap would be published as a null result, so an unknown token, a
    non-number, a non-finite value and `<= 0` all raise.
    """
    if presentation != "direct":
        return None, None
    token = "" if scope_value is None else str(scope_value).strip()
    if not token:
        return None, None
    site = FINGER_CAP_SCOPE_TOKENS.get(token)
    if site is None:
        raise ValueError(
            f"FRUIT_FINGER_MAXFORCE_SCOPE={scope_value!r} is not a known scope; "
            f"the tokens are {', '.join(sorted(FINGER_CAP_SCOPE_TOKENS))!r}"
        )
    explicit_global = "" if global_value is None else str(global_value).strip()
    if explicit_global:
        say(
            f"[drive] FRUIT_FINGER_MAXFORCE={explicit_global} is set, so the "
            f"global build-time cap wins and FRUIT_FINGER_MAXFORCE_SCOPE="
            f"{token} resolves to no runtime write"
        )
        return None, None
    key = f"{site[0]}:{site[1]}"
    text = "" if cap_value is None else str(cap_value).strip()
    if not text:
        return {key: FINGER_CAP_SCOPE_DEFAULT}, FINGER_CAP_SCOPE_DEFAULT
    try:
        cap = float(text)
    except ValueError:
        raise ValueError(
            f"FRUIT_FINGER_MAXFORCE_SCOPED={cap_value!r} is not a number of newtons"
        ) from None
    if not math.isfinite(cap):
        raise ValueError(f"FRUIT_FINGER_MAXFORCE_SCOPED={cap_value!r} is not finite")
    if cap <= 0.0:
        raise ValueError(
            f"FRUIT_FINGER_MAXFORCE_SCOPED={cap_value!r}: a clamp force is "
            "positive newtons (leave FRUIT_FINGER_MAXFORCE_SCOPE unset for the "
            "shipped cap)"
        )
    return {key: cap}, cap


def resolve_arm_park(presentation: str, env_value: str | None) -> tuple[str, bool]:
    """The resolved `FRUIT_ARM_PARK` and whether it came from the P43 default.

    P43 phase 4 (the adoption, `logs/p43/P3_RESULTS.md`): the park named `back`
    is the **`direct` presentation's default** - the phase-3 A/B re-measured it
    on this tree's 9.8-9.9 N grip profile (right-arm carried 20/54 -> 0/56,
    placed 32/54 -> 53/56, 5/5 runs, cycle +0.2 %).

    The default is scoped to `presentation == "direct"` for a reason: the park
    can only be applied there (the reset teleports the arms; the guard in
    `__init__` raises for any other presentation), so an unscoped default would
    make `handoff` constructions raise. `handoff` therefore resolves to `""`,
    i.e. the shipped `ready` pose, exactly as before.

    An explicit env value always wins, which is the escape hatch: `=ready`
    restores the shipped pose everywhere (**every direct number before P43 is a
    pre-park number and is reproduced with `FRUIT_ARM_PARK=ready`**), `=back`
    reproduces the opt-in arm, and `=""` is the same as `=ready`.

    Returns `(name, defaulted)`; `defaulted` is the manifest field that tells a
    post-flip store (`defaulted: true`) from a pre-P43 one (no `arm_park` block)
    and from an explicit `=back` arm (`defaulted: false`).
    """
    default = "back" if presentation == "direct" else ""
    name = (default if env_value is None else env_value).strip()
    return name, bool(env_value is None and name)


#: Sources whose md5 goes into the run manifest (mirrors 40_collect_demos.py's
#: shard manifest, plus this file and the waypoints it moves the arms with, plus
#: the policy runtime that decided the actions - the RTC phase needs the sampler
#: code pinned alongside the checkpoint).
_MANIFEST_SOURCES = (
    "src/fruit_sorting/tasks.py",
    "src/fruit_sorting/assets.py",
    "src/fruit_sorting/conveyor.py",
    "src/fruit_sorting/scene.py",
    "src/fruit_sorting/fruits.py",
    # P32 phase-D remediation (Gate D C1): the bed schedule owns the dense
    # supply's row/pitch draws, so it is provenance next to fruits.py; without
    # it a bed rollout and a scatter rollout were indistinguishable and a
    # bed.py edit moved no md5.
    "src/fruit_sorting/bed.py",
    # P32 phase B: the pear profile sets the per-instance draw count and
    # therefore the supply stream; a direct-path rollout manifest without
    # this key is pre-pear (the same rule as the collector's sources).
    "src/fruit_sorting/meshes.py",
    "src/fruit_sorting/control.py",
    # P41 phase 2: `common.py` holds the physics substep count (`substeps()`),
    # the other lever to the same delivered pinch (3.08x wall at 480 Hz).
    "src/fruit_sorting/common.py",
    "src/fruit_sorting/rl_env.py",
    "src/fruit_sorting/policy/runtime.py",
    "src/fruit_sorting/policy/diffusion.py",
    "src/fruit_sorting/policy/trigger.py",
    # P28-B: the belt-speed channel's whole content is *how the input is
    # assembled*, so the loader and the fine-tune that may widen a checkpoint
    # are part of the measurement (design 2.5 item 2). Before this they were
    # unpinned, and two runs with different loaders were indistinguishable.
    "src/fruit_sorting/policy/data.py",
    "src/fruit_sorting/policy/finetune.py",
    "configs/waypoints.json",
    "configs/motion_reference.json",
    # P36 phase 1: the proprio spoof's vectors (the P35 achieved poses). A
    # rollout that writes them into the observation must pin them, or two
    # "park-proprio" cells with different vectors are indistinguishable.
    "configs/proprio_spoof.json",
)


def _md5(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.md5(handle.read()).hexdigest()
    except OSError:
        return ""


def apply_proprio_spoof(
    dof: np.ndarray,
    active: str,
    indices: dict[str, list[int]],
    vectors: dict[str, np.ndarray],
) -> tuple[np.ndarray, dict]:
    """P36: write the *inactive* arm's 7 joints into a copy of the joint row.

    Pure array work - no simulator state is read or written, so this is the one
    channel the P36 proprio cell moves (`logs/p36/PREREG.md`).

    ``dof`` is the 22-D joint row the observation carries (the interleaved
    layout `left_joint1, right_joint1, left_joint2, ..., tcp_joint`s);
    ``indices`` maps each arm to its 7 dof indices (`ArmController.arm_dofs`);
    ``vectors`` maps a side to the 7 joint values to write. The **active** arm,
    the fingers, the hand and the TCP joints are copied untouched, and the
    caller's array is not modified. A side with no vector (the park file has no
    right-arm `back`) is left live and reported ``applied=0`` - the spoof is
    defined only where the pose is measured.
    """
    out = np.array(dof, dtype=np.float32, copy=True)
    inactive = "right" if active == "left" else "left"
    vec = vectors.get(inactive)
    if vec is None or inactive not in indices:
        return out, {
            "applied": 0,
            "side": inactive,
            "indices": np.zeros(0, dtype=int),
            "before": np.zeros(0, dtype=np.float32),
        }
    idx = np.asarray(indices[inactive], dtype=int)
    before = out[idx].copy()
    out[idx] = np.asarray(vec, dtype=np.float32).reshape(-1)
    return out, {
        "applied": 1,
        "side": inactive,
        "indices": idx,
        "before": before,
    }


def store_guard_reason(record: bool, spoof_pose: str) -> str:
    """P36: why a *recording* rollout may not run under the proprio spoof.

    ``FRUIT_PROPRIO_SPOOF`` rewrites 7 observation channels before ``record``
    sees them, so the store would carry a proprio pose the robot never held -
    and for the `ready` pose it would look like an ordinary store. That is a
    silent poisoning of every later training run, so the combination is refused
    (the spoof is an *evaluation* interface: it changes what the policy reads,
    which is exactly what a store must not contain). ``FRUIT_ARM_PARK`` is not
    refused: a parked store is a real post-park dataset and is named in the
    manifest's ``arm_park`` block.

    One predicate, so ``scripts/218_proprio_spoof_check.py`` can pin it offline;
    the env raises on it.
    """
    if record and spoof_pose:
        return (
            f"FRUIT_PROPRIO_SPOOF={spoof_pose!r} with a recording rollout: the "
            "store's proprio would carry the spoofed 7 joints instead of the "
            "measured pose (a training-data poisoning). Collect with the shipped "
            "channels; spoof the evaluation interface only."
        )
    return ""


def resolve_time_scale(raw: str | None) -> float:
    """P52 phase 2: `FRUIT_POLICY_TIME_SCALE` -> the executed-chunk rate ``s``.

    ``s == 1.0`` (unset) is the shipped path: one chunk waypoint per control
    tick, and the env never consults the interpolation at all - which is what
    makes the control arm byte-identical by construction rather than by
    arithmetic luck.

    A value below 1 would *slow* the chunk, which is not a registered cell (the
    lever is a speed-up, `logs/p52/PREREG_DRAFT.md` section 1.2), and a
    non-number, a non-positive or a non-finite value is a hard error - an A/B
    arm must never run with a knob it did not resolve, and a silently ignored
    typo would read as a null result.
    """
    text = "" if raw is None else str(raw).strip()
    if not text:
        return 1.0
    try:
        value = float(text)
    except ValueError:
        raise ValueError(
            f"FRUIT_POLICY_TIME_SCALE={raw!r} is not a number"
        ) from None
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(
            f"FRUIT_POLICY_TIME_SCALE={raw!r} must be a finite positive number"
        )
    if value < 1.0:
        raise ValueError(
            f"FRUIT_POLICY_TIME_SCALE={raw!r} is a slow-down; only s >= 1 is "
            "registered (the lever is a speed-up of the executed chunk)"
        )
    return float(value)


def retime_action(chunk: np.ndarray, index: int, scale: float) -> np.ndarray:
    """P52 phase 2: the action to apply on control tick ``index`` of a chunk.

    The chunk is a sequence of **absolute 9-D joint targets** (the active arm's
    7 joints, then the finger opening twice), so "execute it faster" is a
    re-parameterisation of the waypoint path: at rate ``scale`` the position
    along that path advances ``scale`` waypoints per control tick, tick
    ``index`` sits at ``i = scale * index``, and the applied action is the
    **linear interpolation of the two bracketing waypoints**. Nothing about the
    model changes - the same predicted path is executed in fewer ticks.

    **At ``scale == 1.0`` this returns ``chunk[index]`` exactly** (``i`` is the
    integer ``index``, so the fraction is 0 and the arithmetic short-circuits
    before any float operation touches the values). That identity is what makes
    the control arm byte-identical; `scripts/228_p52_retime_selftest.py` asserts
    it over random chunks, because the direct loop itself is not bit-reproducible
    (rendered frames, AGENTS.md section 3b) and no *run* can prove it.

    The last waypoint is a terminal hold, not a clamp of convenience: past it
    the chunk carries no further information, so the return is that waypoint
    rather than an extrapolation of the final segment. The re-plan boundary is
    untouched - the next chunk's action 0 is applied unchanged (census section
    6), which is the jump a time-scale cannot and does not scale.
    """
    arr = np.asarray(chunk, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[0] == 0:
        raise ValueError(
            f"a chunk must be 2-D with at least one waypoint, got shape {arr.shape}"
        )
    horizon = int(arr.shape[0])
    i = float(scale) * float(index)
    base = int(i)  # scale >= 1 and index >= 0, so this is floor(i)
    if base >= horizon - 1:
        return arr[horizon - 1]
    frac = i - base
    if frac == 0.0:
        return arr[base]
    return arr[base] * (1.0 - frac) + arr[base + 1] * frac


def retime_contact(
    force: float, finger: float, force_threshold: float, open_threshold: float
) -> bool:
    """P52 phase 2's contact gate: is the action **in contact** this tick?

    Two channels the environment **already samples** every decision - so the
    gate costs no simulator read and cannot perturb the loop (AGENTS.md section
    2: instrumentation that runs in the control loop changes the result):

    * the **tactile normal force** on the active hand's finger links - above
      ``force_threshold`` (~1 N) the fingers are loaded. On the direct path this
      is a *spiky* signal (0 N for most decisions, 15-190 N while the hand is in
      the belt or on the fruit), which is exactly what a contact gate should
      catch;
    * the **finger opening** - the fallback. Note the measured range on this
      interface: the pool's diameters are 2.8-7.0 cm and the channel's ceiling is
      4.4 cm, so a *loaded* finger reads 2.5-4.4 cm, i.e. **the finger channel
      cannot separate "holding a fruit" from "open"** (`logs/p52/p2/`, the
      `[retime]` rows: 25-44 mm across a whole approach). The default threshold
      is therefore **2.0 cm - below every class's diameter**, so it fires only on
      a *collapsed* finger (a close that passed through the fruit), which is the
      one state the channel does identify. A threshold at the trigger's own
      `finger < 0.030` close test would gate on the policy's ordinary approach
      posture (measured: 14 % of decisions) and is not a contact reading.

    Either one is enough (the conservative union). Returns ``True`` when the
    caller must clamp the effective scale to 1.0, i.e. execute at the
    demonstrated rate. This is the RoboPace shape, restricted to what this tree
    can measure: the cost of a retimed chunk is the speed **at contact**, not
    the speed overall (`logs/p52/FRONTIER.md` section 2.1), and the robot's
    kinematic limits are not the binding constraint there.

    Pure arithmetic, so `scripts/228_p52_retime_selftest.py` pins it offline.
    """
    return bool(
        float(force) > float(force_threshold)
        or float(finger) < float(open_threshold)
    )


def resolve_joint_clamp(raw: str | None) -> bool:
    """P53 C1: `FRUIT_POLICY_JOINT_CLAMP` -> clip the 7 joint targets?

    ``False`` (unset) is the shipped path: `_apply` hands the policy's 7
    absolute joint targets to the drives **untouched**, so a command past a
    joint stop is not refused and the drive pushes into the stop - the mechanism
    `logs/p52/P2B_FEASIBILITY.md` section 1.6 measures (**13.1 % of joint-steps
    out of range, on 74.3 % of ticks**, j3 1 750 of 23 548, a 2.8-3.2 deg p50
    overshoot with the measured joint at the stop). ``True`` clips each of the
    seven targets into the arm's own measured joint range
    (`ArmController.arm_lo`/`arm_hi`, read once from `get_dof_limits()` at
    construction - `control.py:197-202`) before the drives see it.

    The tokens are parsed strictly (the P44/P45/P52 precedent): a typo that fell
    back to the shipped value would be published as a null result, so anything
    that is not an explicit false/true token is a hard error.
    """
    text = "" if raw is None else str(raw).strip().lower()
    if text in ("", "0", "false", "no", "off"):
        return False
    if text in ("1", "true", "yes", "on"):
        return True
    raise ValueError(
        f"FRUIT_POLICY_JOINT_CLAMP={raw!r} is not a boolean (0/1, off/on, "
        "false/true, no/yes)"
    )


def resolve_action_hold(raw: str | None) -> int:
    """P53 C2: `FRUIT_POLICY_ACTION_HOLD` -> control ticks per executed waypoint.

    ``1`` (unset) is the shipped path: one chunk waypoint per control tick, i.e.
    the 16-waypoint chunk is replayed at **120 Hz** although the training stream
    was recorded at 30 Hz (one frame per 4 control ticks, `_record_tick`). The
    census's own read of that mismatch is a **10x command dither** with a
    **19.3 mm p50** same-tick tracking residual while the arm's *achieved* rate
    is the demo's own (`logs/p52/P2B_FEASIBILITY.md` section 2.5).

    ``hold = n`` executes each waypoint for ``n`` control ticks, so the chunk's
    command rate becomes ``120 / n`` Hz and one decision covers
    ``execute_steps * n`` ticks. The registered cell is ``n = 2`` (60 Hz, half
    the command rate, half the decisions); any integer >= 1 is accepted so the
    knob is a rate, not a switch. A non-integer, a zero, a negative and a
    non-finite value are hard errors for the same reason as C1's.
    """
    text = "" if raw is None else str(raw).strip()
    if not text:
        return 1
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"FRUIT_POLICY_ACTION_HOLD={raw!r} is not a number") from None
    if not math.isfinite(value) or value != int(value):
        raise ValueError(
            f"FRUIT_POLICY_ACTION_HOLD={raw!r} must be a whole number of ticks"
        )
    value = int(value)
    if value < 1:
        raise ValueError(
            f"FRUIT_POLICY_ACTION_HOLD={raw!r} must be >= 1 tick per waypoint "
            "(1 is the shipped one-waypoint-per-tick execution)"
        )
    return value


def clamp_joint_targets(action: np.ndarray, lo, hi) -> np.ndarray:
    """P53 C1: the 9-D action with its 7 arm targets inside ``[lo, hi]``.

    Returns a **new** array: `_apply` receives a row of the caller's chunk
    (`np.asarray(...).reshape(-1)` can be a view of a float64 chunk), so writing
    the clip in place would silently rewrite the policy's prediction for every
    later tick of the same chunk. The finger channels (7, 8) are untouched -
    `_apply` already clips channel 7 to the 0-44 mm opening.

    With every value already inside the range this is the input values
    unchanged (element for element, signed zeros included), which is why the
    knob-off path is the shipped expression rather than "the same arithmetic".
    """
    out = np.array(action, dtype=np.float64, copy=True)
    out[:7] = np.clip(out[:7], np.asarray(lo, dtype=np.float64), np.asarray(hi, dtype=np.float64))
    return out


def emit_out_of_range(q, lo, hi) -> tuple[int, float]:
    """P53: how many of the 7 joint targets are outside the range, and by how far.

    The number is the census's own count (`logs/p52/P2B_FEASIBILITY.md` 1.6:
    "13.1 % of joint-steps ... on 74.3 % of ticks"), reported for the command
    *before* the clamp (C1's input, T0's whole stream) and *after* it (what the
    drives receive). The overshoot is the largest single-joint excursion in rad,
    so a clamp that only trims rounding noise reads differently from one that
    trims a 3 deg overshoot. A 1e-12 tolerance keeps an exactly-on-the-stop
    command out of the count.
    """
    q = np.asarray(q, dtype=np.float64)[:7]
    lo = np.asarray(lo, dtype=np.float64)[:7]
    hi = np.asarray(hi, dtype=np.float64)[:7]
    over = np.maximum(lo - q, 0.0)
    under = np.maximum(q - hi, 0.0)
    count = int(np.count_nonzero((over > 1e-12) | (under > 1e-12)))
    return count, float(max(float(over.max()), float(under.max())))


def hold_index(tick: int, hold: int) -> int:
    """P53 C2: the chunk waypoint control tick ``tick`` of a decision executes.

    ``hold == 1`` is the shipped mapping (``arr[index]``); the repeat of each
    waypoint is what makes the command rate ``120 / hold`` Hz. Pure, so the
    offline selftest can pin the mapping the env uses.
    """
    return int(tick) // max(1, int(hold))


def direct_fire(
    *, intercept: bool, policy_close: bool, gate_refuse: float | None
) -> bool:
    """The direct interface's fire decision this tick (R7-A/WS-4.6).

    Either path may fire the scripted primitive - the encoder intercept
    (`should_fire`) or the shipped learned close gate (`finger < 0.030` and the
    jaw within 6 cm) - but the shared reach-cliff refusal binds **both**:
    ``gate_refuse`` is the fruit's x when `FRUIT_POLICY_TRIGGER_X_MAX` refuses
    the learned-gate tick (`x_edge_refusal`), so a refused candidate rides past
    instead of being attempted anyway. Before R7-A the refusal lived only
    inside `should_fire`, and a refused fruit could still be attempted through
    the learned gate - every such attempt flailed (R2 P1 4/7; R6 C0/C1/C2
    3/3, 4/4, 3/3). ``gate_refuse`` is ``None`` whenever the guard is off, so
    the shipped direct interface is byte-unchanged. Pure bookkeeping: kept
    module-level so `scripts/811_trigger_test.py` pins the truth table offline.
    """
    return bool(intercept or (policy_close and gate_refuse is None))


def no_firable_ready(
    *, latched: bool, policy_close_seen: bool, dy: float
) -> bool:
    """The `FRUIT_POLICY_REFUSE_END` predicate (P38 phase 2; default off).

    The terminal class may only be claimed on a **measured joint closure**
    (`logs/p38/PREREG_A1.md` A1): a latched *provable* trigger refusal
    (``latched``), no learned close on the candidate since the reset
    (``policy_close_seen`` False - the lateral gate has never bound
    `policy_close`, `direct_fire` above), and the fruit past the trigger's own
    downstream gate (``dy <= -0.05``). Kept module-level and pure so
    `scripts/811_trigger_test.py` pins the truth table offline.
    """
    return bool(latched and not policy_close_seen and float(dy) <= -0.05)


@dataclass
class RewardConfig:
    """Terminal-only reward (the Oracle's recipe): no shaping.

    ``R = success_value * (1 - time_penalty * T / horizon)`` on success, else 0.
    ``T`` is the number of *policy-phase control steps* - the loop iterations the
    policy took before the scripted primitive decided the episode, which is the
    budget `horizon=1500` refers to (the hybrid evaluator's own loop). It is not
    the total simulated cycle time: the primitive then spends ~3,000 more scripted
    ticks whose length the policy barely influences, and including them would
    clamp every success to the same ``0.8`` and erase the time gradient. The
    callers log both (`ticks=` total cycle time, `decision=` policy steps).
    """

    success_value: float = 1.0
    time_penalty: float = 0.2
    horizon: int = 1500

    def compute(self, success: bool, ticks: float) -> float:
        if not success:
            return 0.0
        t = min(max(float(ticks), 0.0), float(self.horizon))
        return float(self.success_value) * (
            1.0 - float(self.time_penalty) * t / float(self.horizon)
        )


@dataclass
class ExpertConfig:
    """DAgger expert: the scripted pick-phase controller, run *env-side*.

    Enabled with ``--dagger`` (``direct`` presentation only). At every policy
    decision point the scripted line's command for the current state is computed
    as the label: hold the calibrated grasp pose while the fruit is outside the
    tracking window, then track the fruit's measured centre and ramp the pads
    closed (the same window and ramp `PickAndPlaceTask` uses, read from the same
    env knobs). If the policy's own action deviates from that label by more than
    ``tolerance`` rad - or closes the finger before the window opens - the expert
    takes control for ``window_steps`` policy steps. The recorded ``action`` is
    always the expert label (standard DAgger aggregation: states from the policy,
    labels from the expert); the policy's own action is recorded alongside as
    ``policy_action``.
    """

    tolerance: float = 0.35
    #: How many 4-tick policy steps the expert holds control after a deviation.
    window_steps: int = 15


@dataclass(frozen=True)
class WaitGateSettings:
    """P31-A: the direct loop's deterministic WAIT GATE (default off).

    The direct loop samples one action chunk per ``execute_steps`` control ticks
    from the first tick the observation horizon is full until the attempt's end,
    including the 1.1-1.3 s during which the target fruit is still far upstream
    and the sampled chunk is a no-op hold. Measured on the existing logs
    (``logs/p31/WAIT_GATE_DESIGN.md``, 148 direct episodes + 3 per-step traces at
    the shipped 0.12 m/s belt):

    * the first chunk is sampled with the fruit **0.46-0.55 m** upstream of the
      pick station (`[rl] episode` ``y=`` minus the measured 0.10 m of
      post-selection travel);
    * the two fire channels only act on a fruit inside **0.301 m**: the encoder
      intercept trigger fires at ``lead * speed`` (90 logged fires: 0.107-0.301 m,
      the low end the fixed 0.9 s lead, the high end the adaptive-acquisition
      lead), and the learned close gate at ``|jaw-fruit|xy < 0.06`` m;
    * so 25-48 chunks (median ~40) of a fired attempt are sampled where no
      decision is possible - 47-59 % of its 70-85 chunks on the R11-A.1/R7
      episodes, 40 of 123 on the P30-B success row.

    With the gate armed, a model call in that region is replaced by a *held*
    chunk: the last applied action repeated for the whole action horizon. That is
    the shipped "no new action" state (`act(None)` before ``policy.ready``,
    which the drive holds by leaving its position targets alone) expressed as an
    action, so

    * the arm receives the same command it already holds (no motion is
      commanded - a zero action would command all seven joints to their zero
      configuration, and a "return to the grasp pose" action would command a
      motion; both are rejected);
    * ``_apply`` still runs every tick, so the fire machinery (the learned close
      gate, the intercept trigger, the presented-fruit adoption) and the
      recorder see exactly the ticks they saw before - only ``policy.act``
      disappears;
    * the 4-tick chunk cadence, the physics, the reward's ``decision`` and the
      episode's simulated length are unchanged, so the gate moves the inference
      cost and nothing else.

    The predicate is one-sided in the fruit's along-distance by default. The
    optional ``past`` term covers the *post-miss* tail: once the fruit is that
    far downstream it can no longer be caught (the trigger's own firable bound is
    ``dy >= -0.05``), so the same argument applies - and there it is the bigger
    share: 0.78 m of the 1.36 m a no-fire episode's fruit travels lies past
    -0.10 m, i.e. 195 of its 326 chunks (60 %). It stays 0 here because it
    interacts with ``FRUIT_POLICY_TRIGGER_PRESENT``' fruit adoption (an adopted
    fruit at the station is firable while the selected sample is past) and needs
    its own pre-registration.

    No hysteresis: the along-distance is monotone in simulated time for a fruit
    on a running belt (the station reference is fixed at reset), so the predicate
    crosses the boundary once per attempt in each direction. A feeder recycle
    that teleports the fruit back upstream re-arms the gate, which is correct -
    that *is* a new wait. A pile-up nudging a fruit a few millimetres across the
    threshold costs one extra chunk per crossing.

    Byte-inertness: ``from_env`` returns the defaults immediately unless
    ``FRUIT_WAIT_GATE=1``, so an unset (or ``=0``) gate never parses the
    sub-knobs and cannot raise on a malformed value; the env caches
    ``_wait_gate_on`` and every new statement on the hot path is dominated by it
    (``logs/p31/check_wait_gate.py`` proves this by AST domination).
    """

    #: ``FRUIT_WAIT_GATE`` - the master knob (default 0).
    enabled: bool = False
    #: ``FRUIT_WAIT_GATE_DIST`` - the upstream along-distance above which no
    #: model call is made [m]. Default 0.35 = the measured maximum fire distance
    #: (0.301 m) + one 4-tick chunk of belt travel (0.0048 m) + 4.6 cm of margin,
    #: so the model is live 10-60 chunks before either fire channel can act.
    dist: float = 0.35
    #: ``FRUIT_WAIT_GATE_PAST`` - the downstream distance beyond which no model
    #: call is made [m]; 0 = off (the shipped one-sided gate).
    past: float = 0.0
    #: ``FRUIT_WAIT_GATE_WARM`` - chunks that must have been sampled before the
    #: gate may hold, so the held action is a real one (``_last_action`` is zeros
    #: until the first chunk executes). Floor 1.
    warm: int = 1
    #: ``FRUIT_WAIT_GATE_DIAG`` - one ``[gate]`` row per episode (pure reporting).
    diag: bool = False

    @classmethod
    def from_env(cls) -> "WaitGateSettings":
        """Resolve the knobs once, at construction (the default path returns early)."""
        if os.environ.get("FRUIT_WAIT_GATE", "0") != "1":
            return cls()
        return cls(
            enabled=True,
            dist=float(os.environ.get("FRUIT_WAIT_GATE_DIST", "0.35")),
            past=max(0.0, float(os.environ.get("FRUIT_WAIT_GATE_PAST", "0.0"))),
            warm=max(1, int(os.environ.get("FRUIT_WAIT_GATE_WARM", "1"))),
            diag=os.environ.get("FRUIT_WAIT_GATE_DIAG", "0") == "1",
        )

    def skips(self, along: float, warm: bool = True) -> bool:
        """The gate's predicate for one model call (pure; the stub pins it).

        ``along`` is the target fruit's along-distance to the pick station
        [m], ``+`` = upstream. ``warm`` is False until ``warm`` chunks have been
        sampled, which keeps the held action a real one. A NaN position (no
        fruit yet) never gates: the shipped path is the safe fallback.
        """
        if not self.enabled or not warm:
            return False
        if along != along:  # NaN
            return False
        if self.dist > 0.0 and along > self.dist:
            return True
        if self.past > 0.0 and along < -self.past:
            return True
        return False

    def summary(self) -> str:
        """One line for the run banner / manifest."""
        if not self.enabled:
            return "wait_gate=off"
        return (
            f"wait_gate=on dist={self.dist:.3f} past={self.past:.3f} "
            f"warm={self.warm} diag={'on' if self.diag else 'off'}"
        )


@dataclass
class StepResult:
    """Result of one ``act`` call: terminal reward, done flag, outcome info."""

    obs: dict
    reward: float
    done: bool
    info: dict = field(default_factory=dict)


def carry_and_release(arm, cfg, bin_index: int, advance, steps: int = 220) -> None:
    """Post-grasp primitive copied from ``scripts/60_eval_policy.py``.

    The same Cartesian path to the output-belt drop point, then the pads open
    over the moving belt. Only used by the ``direct`` path's fallback below: the
    task's own ``grasp_carry_place`` already carries and releases, so this is
    the harness helper re-run when a grasp did not end on the output belt.
    """
    px, py = cfg.output_belt_drop_points[bin_index]
    goal = np.array([px, py, cfg.output_place_z])
    for _ in range(steps):
        arm.ik_step(arm.tcp_target_for_jaw(goal))
        advance(1)
        if float(np.linalg.norm(arm.jaw_centre() - goal)) < 0.010:
            break
    for value in np.linspace(arm.finger_opening(), arm.OPEN, 16):
        arm.set_gripper(float(value))
        for _ in range(3):
            advance(1)
    for _ in range(60):
        advance(1)


class RolloutRecorder:
    """Records rollout episodes in the training schema, successes *and* failures.

    ``EpisodeRecorder`` (the demonstration schema) is deliberately untouched: it
    drops failed episodes and computes ``success`` from the caller. This recorder
    keeps every attempt whose arrays were written, writes the same npz keys
    ``EpisodeStore`` reads (so a rollout directory trains like a demo directory),
    and adds the RL bookkeeping - ``success/grasped/placed/notes/ticks/category/
    diameter/reward`` - to ``index.json``.

    ``add`` is called on the observation ticks (every 4 physics steps, 30 Hz);
    ``decimation`` must stay 1 so the rollout frames have the same 30 Hz cadence
    as the demonstrations.
    """

    def __init__(self, out_dir: str, decimation: int = 1):
        self.out_dir = out_dir
        self.decimation = max(1, int(decimation))
        self._counter = 0
        self._frames: list[dict] = []
        self.meta: dict | None = None
        os.makedirs(out_dir, exist_ok=True)

    # ------------------------------------------------------------------ #
    def begin(self, meta: dict) -> None:
        self.meta = dict(meta)
        self._frames = []
        self._counter = 0

    @property
    def recording(self) -> bool:
        return self.meta is not None

    def tick(self) -> bool:
        self._counter += 1
        return self._counter % self.decimation == 0

    def add(self, observation: dict, action: np.ndarray | None = None) -> None:
        if self.meta is None or not self.tick():
            return
        frame = {k: np.asarray(v) for k, v in observation.items() if v is not None}
        if action is not None:
            frame["action"] = np.asarray(action, dtype=np.float32)
        self._frames.append(frame)

    # ------------------------------------------------------------------ #
    def finish(
        self,
        *,
        success: bool,
        grasped: bool,
        placed: bool,
        reward: float,
        ticks: int,
        notes: list[str] | None = None,
        extra: dict | None = None,
    ) -> str | None:
        """Write the episode npz + index row. Returns the path (or None)."""
        meta = self.meta
        self.meta = None
        frames = self._frames
        self._frames = []
        if meta is None:
            return None
        if not frames:
            # Nothing was written for this attempt (it failed before an
            # observation tick). No file, no index row - an empty npz would
            # break `EpisodeStore`'s skill labelling.
            return None
        keys = frames[0].keys()
        arrays = {key: np.stack([f[key] for f in frames]) for key in keys}
        name = f"rollout_{int(meta['index']):05d}.npz"
        path = os.path.join(self.out_dir, name)
        np.savez_compressed(path, **arrays)
        row = {
            "file": name,
            "index": int(meta["index"]),
            "category": str(meta.get("category", "")),
            "grade": str(meta.get("grade", "")),
            "arm": str(meta.get("arm", "")),
            "bin_index": int(meta.get("bin_index", -1)),
            "diameter": float(meta.get("diameter", 0.0)),
            "success": bool(success),
            "grasped": bool(grasped),
            "placed": bool(placed),
            "notes": list(notes or []),
            "ticks": int(ticks),
            "reward": float(reward),
            "frames": int(len(frames)),
            "presentation": str(meta.get("presentation", "")),
            "ablate": str(meta.get("ablate", "")),
            "seed": int(meta.get("seed", -1)),
        }
        if extra:
            row.update(extra)
        self._append_index(path, row)
        return path

    def abort(self) -> None:
        """Drop an unfinished episode without writing anything."""
        self.meta = None
        self._frames = []

    def _append_index(self, path: str, row: dict) -> None:
        index_path = os.path.join(self.out_dir, "index.json")
        entries = []
        if os.path.exists(index_path):
            try:
                with open(index_path, encoding="utf-8") as fh:
                    entries = json.load(fh)
                if not isinstance(entries, list):
                    entries = []
            except (OSError, ValueError):
                # A run killed mid-write (the contact-grind wedge) can leave a
                # truncated/empty index; treat it as empty instead of crashing
                # the next episode's recorder. The npz files are unaffected.
                entries = []
        name = os.path.basename(path)
        for position, existing in enumerate(entries):
            if existing.get("file") == name:
                entries[position] = row
                break
        else:
            entries.append(row)
        # Atomic write: a SIGKILL during json.dump must not corrupt the index.
        tmp_path = index_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=2)
        os.replace(tmp_path, index_path)


class SortingRLEnv:
    """One sorting cell, reused for many episodes; the policy is rolled inside.

    The caller creates the env once (scene build is expensive), then per episode::

        obs = env.reset(seed)          # first episode of a run
        while not done:
            chunk = env.sample_chunk()  # harness order: frame push, then sample
            result = env.act(chunk, execute_steps=4)
            done = result.done
        obs = env.reset()               # subsequent episodes

    ``act`` executes up to ``execute_steps`` actions of ``chunk`` (one physics
    tick each), so ``execute_steps=4`` reproduces the hybrid evaluator's
    re-plan-every-4-actions loop.
    """

    def __init__(
        self,
        *,
        presentation: str = "direct",
        seed: int = 77,
        size_filter: str | None = None,
        ablate: str = "none",
        checkpoint: str | None = None,
        record: bool = False,
        out_dir: str | None = None,
        execute_steps: int = 4,
        ddim_steps: int = 16,
        approach_steps: int = 400,
        reward: RewardConfig | None = None,
        verbose: bool = False,
        waypoint_path: str | None = None,
        dagger: ExpertConfig | None = None,
    ) -> None:
        if presentation not in ("direct", "handoff"):
            raise ValueError(f"presentation must be direct|handoff, got {presentation!r}")
        if ablate not in ("none", "zero", "scripted"):
            raise ValueError(f"ablate must be none|zero|scripted, got {ablate!r}")
        if ablate == "none" and not checkpoint:
            raise ValueError("ablate='none' needs --ckpt (the policy to roll out)")
        if dagger is not None and presentation != "direct":
            raise ValueError("the DAgger expert is only defined for presentation='direct'")
        self.presentation = presentation
        #: P58: the direct presentation's **supply profile** - the release clock
        #: on every tick of both loops (`FRUIT_FEED_CADENCE` in the task, the
        #: P55 `FRUIT_DIRECT_FEED` in `advance`), the release interlock paced on
        #: the selector's approach band at `FRUIT_SUPPLY_BAND_MAX=4`, all
        #: resolved **on for `presentation == "direct"` only** with an explicit
        #: environment value winning. Note the cap is **4**, not 3: cap 3 is a
        #: measured regression (`logs/p58/A_APRIME_RESULTS.md`: the cap binds,
        #: refuses ~2.5 patch partners per pick, thins the catchable window
        #: 2.38 -> 2.02 and starves 1/42) and cap 4 reads 0/42 with `skipped`
        #: 8/4/9 against the shipped control's 104/107/105.
        self._supply = self._resolve_supply_profile(presentation == "direct")
        #: P62 phase 2: the **left-only, direct-scoped grasp attitude** override
        #: (`FRUIT_GRASP_LEFT_TOPDOWN=1`, default **off**). Resolved here, one
        #: dict lookup when off, and passed to the task as the caller-owned kwarg
        #: `grasp_quat_override` - never by writing the environment or the
        #: `configs/` file, so the scripted acceptance, the collector, the
        #: two-line scheduler and the hybrid canary keep the attitude the
        #: waypoints file records (`logs/p62/CANDIDATES.md` §5.4).
        #:
        #: The candidate is **T0** (`logs/p62/CANDIDATES.md` §3/§5: fingers
        #: straight down, jaws exactly across the belt), the only attitude of the
        #: measured family that zeroes the belt's projection on the finger axis
        #: *and* still solves at the left station. Phase 2 measures what it does
        #: to the mechanism; the row below prints the resolved attitude, the
        #: file's, and the hold the dynamic catch actually commands, so an armed
        #: run says in its own log which attitude it ran.
        self._grasp_quat_override = resolve_grasp_quat_override(
            presentation, os.environ.get("FRUIT_GRASP_LEFT_TOPDOWN")
        )
        #: P64 phase 1: the **pre-compensated left carry attitude**
        #: (`FRUIT_GRASP_LEFT_PRECOMP=1`, default **off**, `direct` + left only).
        #: A different channel from the override above on purpose: P62 measured
        #: that `_grasp_quat` cannot reach the achieved lift attitude (the
        #: never-stop catch releases it before the descent), so this one is
        #: passed as `carry_hold_override` and written into `arm.hold_quaternion`
        #: for the `grasp_lift` leg - the command `ik_step` tracks. The constant,
        #: its derivation and the measured spread are at `P64_LEFT_DRIFT_*`.
        self._carry_hold_override = resolve_carry_hold_override(
            presentation, os.environ.get("FRUIT_GRASP_LEFT_PRECOMP")
        )
        #: P66 phase 2/3: the **lift's target height** (`FRUIT_LIFT_DZ`, metres
        #: above `belt_top + 0.28`, **`direct` + left only**; since phase 3 the
        #: `direct` **default** is the 0.20 m rung, `LIFT_DZ_DIRECT_DEFAULT`).
        #: Threaded the P64 way: resolved here, passed as a caller-owned kwarg,
        #: applied by `tasks.lift_dz_for` at `_carry`'s `grasp_lift` end pose. It
        #: moves one number (the leg's end z) and nothing else - the attitude,
        #: grip, station and command are the shipped ones - which is what makes
        #: the cell a test of the rotation (the reachability curve
        #: `logs/p66/STATION_SWEEP.md` measured) rather than of the drag.
        #: `_lift_dz_defaulted` is the P43-style origin flag: `True` = the direct
        #: default, `False` = an explicit env value (including the `+0.08`
        #: restore), and it is printed and recorded so a pre-flip log cannot be
        #: mistaken for a post-flip one.
        self._lift_dz, self._lift_dz_defaulted = resolve_lift_dz(
            presentation, os.environ.get("FRUIT_LIFT_DZ")
        )
        #: P67: the **place-leg climb** (`FRUIT_LIFT_CLIMB`, metres of vertical
        #: raise at the lift's own x/y, `direct` + left only, default **off**).
        #: P66 phase 4's gate (a) named this shape: the crossing is only
        #: 0.175:1 with the lift height, and 1:1 with the height the place
        #: transit *starts* at. Threaded the `lift_dz` way (one resolve here, one
        #: caller-owned kwarg, `tasks.lift_climb_for` at `_carry`); it moves the
        #: command list and **not** the leg's end pose, so the release geometry is
        #: the shipped one. `None` = no arithmetic at all (every non-direct caller,
        #: and a direct run with the knob unset).
        self._lift_climb = resolve_lift_climb(
            presentation, os.environ.get("FRUIT_LIFT_CLIMB")
        )
        #: P78/P79: the **runtime, per-leg** finger-drive force cap
        #: (`FRUIT_FINGER_MAXFORCE_SCOPE=place-left|grasp-left`, `direct` only,
        #: default off): `{"left:place": <N>}` while the left arm's `place*`
        #: legs run (P78), or `{"left:grasp": <N>}` while its single
        #: `grasp_lift` leg runs (P79, the pick half), restored to the cap the
        #: leg found at its end. P77 measured the 60 N count win and the global
        #: form's price (both motion references, a scripted re-baseline, every
        #: store); this is the contained form. `None` = the shipped build-time
        #: cap, with no write and no read on any path.
        self._finger_cap_scope, self._finger_cap_value = resolve_finger_cap_scope(
            presentation,
            os.environ.get("FRUIT_FINGER_MAXFORCE_SCOPE"),
            os.environ.get("FRUIT_FINGER_MAXFORCE_SCOPED"),
            os.environ.get("FRUIT_FINGER_MAXFORCE"),
        )
        #: P55: the live feeder, now part of the profile. `FRUIT_DIRECT_FEED=0`
        #: restores the pre-P55 behaviour; non-direct presentations stay off.
        self._direct_feed = bool(self._supply["feed"])
        self._direct_feed_warned = False
        self._direct_feed_refreshed = False
        #: P56: the **multi-pick episode** (`FRUIT_DIRECT_CONTINUOUS=<n>`, default
        #: 0 = the shipped one-fruit-per-episode loop). One logical episode = *n*
        #: picks: after a place the env re-selects the next candidate from the
        #: live belt and starts it instead of returning `done`, so the belt is
        #: never drained between picks. The mode **implies** the P55 feeder
        #: (`FRUIT_DIRECT_FEED=1`): separating the two knobs would make the A/B
        #: measure two things at once.
        #:
        #: What is per pick and what is per run, and why (`logs/p56/DESIGN.md`
        #: A.1-A.3): the world (pool, belt, spawner schedule) is process-scoped
        #: and is *not* rebuilt by `reset` - so the only per-pick work is the
        #: selection, the active arm's teleport to the calibrated `grasp` pose
        #: (the demos' frame 0), its settle, the trigger station, the bookkeeping
        #: block and `policy.reset()`. The last one is load-bearing: the obs
        #: history is 2 frames, so keeping it across picks would condition pick
        #: k+1's first chunk on pick k's carry frames - a state no demonstration
        #: contains (PREREG F2). `self._episode` still increments **per pick**: it
        #: is the recorder's npz name, and two picks under one index would
        #: silently overwrite the first file.
        self._continuous_picks = int(os.environ.get("FRUIT_DIRECT_CONTINUOUS", "0"))
        if self._continuous_picks < 0:
            raise ValueError(
                "FRUIT_DIRECT_CONTINUOUS must be >= 0, got "
                f"{self._continuous_picks}"
            )
        if self._continuous_picks and (presentation != "direct" or ablate != "none"):
            raise ValueError(
                "FRUIT_DIRECT_CONTINUOUS is only defined for presentation='direct' "
                f"with ablate='none' (got presentation={presentation!r}, "
                f"ablate={ablate!r}); the handoff presentation teleports the fruit "
                "to the station and a scripted/zero ablation does not run the "
                "learned loop the mode re-primes"
            )
        if self._continuous_picks:
            self._direct_feed = True
        self._picks_done = 0          # picks finished in the current episode
        self._cont_reward = 0.0
        self._cont_ticks = 0
        self._cont_placed = 0
        self._cont_gaps: list[int] = []
        #: Set by `_finalize` when it started the next pick: `act` must stop
        #: executing the finished pick's remaining actions on the new pick.
        self._pick_boundary = False
        #: P56: pass `select_target`'s refusal census through to `bed_diag_report`
        #: (`FRUIT_BED_DIAG=1`, the scripted driver's own instrument). The direct
        #: env never passed `diag`, so "the belt stays stocked" was not
        #: measurable on this interface - pure reporting, off by default.
        self._bed_diag = os.environ.get("FRUIT_BED_DIAG", "0") == "1"
        #: P56 P6 (`FRUIT_GRASP_DIAG=1`, default off): one `[grasp]` row per pick
        #: with the active arm's distance from the calibrated `grasp` pose (the
        #: demos' frame-0 state) and the pick's own start time. One articulation
        #: read per pick; it is the manipulation check that says the continuation
        #: reproduced the per-episode loop's start state, so it must run in **both**
        #: arms of a comparison (an asymmetric instrument is not a measurement).
        self._grasp_diag = os.environ.get("FRUIT_GRASP_DIAG", "0") == "1"
        self._grasp_err = float("nan")
        self.ablate = ablate
        self.dagger = dagger
        self.seed = int(seed)
        self._active_seed = int(seed)
        self.execute_steps = int(execute_steps)
        self.ddim_steps = int(ddim_steps)
        #: P30-B: model inference calls (action-chunk samples) this episode.
        #: One call = one `PolicyRunner.act` = one DDIM chain of `ddim_steps`
        #: denoising steps (16 by default); with `execute_steps=4` it is one
        #: call per 4 control ticks. Counted at the single inference site
        #: (`sample_chunk`) plus the RTC chunker's completions, and published to
        #: the task before the scripted primitive runs so the `[hub]` row can
        #: report it. Pure reporting: nothing reads it as a control input.
        self._infer_calls = 0
        self.approach_steps = int(approach_steps)
        self.reward = reward or RewardConfig()
        self.verbose = bool(verbose)
        #: Off by default. `RL_ENV_DEBUG=1` traces the direct close decision
        #: (one fruit-pose read every 25 applied actions) - diagnostics are part
        #: of the measurement, so this must only be used to find a mechanism.
        self._debug = os.environ.get("RL_ENV_DEBUG", "0") == "1"
        #: GEM-style tracking half (arXiv 2508.14042), default off: add the
        #: joint-space image of the fruit's measured Cartesian velocity to the
        #: policy's arm command each tick, so the end-effector tracks the fruit
        #: and the learned action only has to supply the interaction. Read-only
        #: (a rigid-body velocity read plus the TCP Jacobian); the knob is
        #: diagnostics-grade in the sense that it changes the control loop, so
        #: it is opt-in and recorded in the manifest.
        self._policy_track = os.environ.get("FRUIT_POLICY_TRACK", "0") == "1"
        #: Encoder-based intercept trigger (P4b1, `policy/trigger.py`), default
        #: off: with `FRUIT_POLICY_TRIGGER` unset the trigger below is the
        #: shipped `finger < 0.030 and distance < 0.06` test unchanged. When
        #: enabled it fires the scripted primitive on the fruit's predicted
        #: arrival at the jaw, from the belt encoder / measured velocity.
        self.trigger_settings = TriggerSettings.from_env()
        #: P54: the **direct presentation**'s measured configuration carries the
        #: adaptive acquisition lead. The shipped default left `acq` off, and P54
        #: measured the shipped direct config at **16/45** against **34/45** with
        #: it (right 15/28 = 53.6 % -> 34/35 = 97.1 %; the never-held class 26 -> 2),
        #: because the fixed 0.90 s lead fires *behind* the handover's own 1.17 s
        #: setup (the catch-up residual p50 90.6 mm over the 6 mm tolerance). The
        #: knob was registered as a measurement interface in W7-B/R5; this default
        #: is a **recorded deviation** from that decision, scoped to the direct
        #: presentation. An explicit `FRUIT_POLICY_TRIGGER_ACQ=0` restores the
        #: pre-P54 default; the scripted, hybrid and two-line paths are untouched.
        if (
            "FRUIT_POLICY_TRIGGER_ACQ" not in os.environ
            and self.presentation == "direct"
        ):
            self.trigger_settings.acq = True
        #: P28-B belt-speed channel, default off: with `FRUIT_OBS_SPEED` unset
        #: `proprio()` is the shipped 25-D vector and the extra value is never
        #: computed. Armed, the observation is 26-D and the checkpoint must be a
        #: 26-D artifact (the guard below refuses a mismatch instead of feeding
        #: the model a vector it was not trained on).
        self._speed_channel = speed_channel_enabled()

        # --- P31-A wait gate, default off ----------------------------------- #
        #: Deterministic WAIT GATE (`WaitGateSettings`): while the target fruit
        #: is farther than `dist` upstream of the pick station (or, with
        #: `past > 0`, that far downstream), no decision is possible, so the
        #: model call is replaced by the last applied action repeated. Resolved
        #: once here (a malformed sub-knob is only parsed when the gate is on);
        #: `_wait_gate_on` is the single flag every new hot-path statement is
        #: dominated by, so the shipped loop is byte-inert with the gate unset.
        self.wait_gate = WaitGateSettings.from_env()
        self._wait_gate_on = bool(self.wait_gate.enabled)
        self._wait_gate_skipped = 0      # model calls replaced this episode
        self._wait_gate_held = 0         # control ticks executed on a held chunk
        self._wait_gate_hold_chunk = False   # the chunk now executing is a hold
        self._wait_gate_open = False     # the gate is holding right now
        self._wait_gate_resumed = False  # the gate held and then reopened
        self._wait_gate_along0 = float("nan")  # along at the first held call

        # --- P34 phase 2 reset alignment, default off ------------------------ #
        #: `FRUIT_RESET_ALIGN=1` (direct presentation only): after the reset's
        #: setup, advance the line until the target sits at the *demos' first
        #: view* (first-detectable along p50 +0.399) at the **first model
        #: call**, instead of the shipped p50 +0.583 (inside the +Y output
        #: belt's fully-hidden band, +0.515..+0.870 - `logs/p34/REPORT.md`).
        #: The resolver returns on its first line unless the knob is on, so a
        #: malformed sub-knob cannot raise while off and the shipped path is
        #: byte-inert: one False branch, no reads and no advance.
        self._reset_align = os.environ.get("FRUIT_RESET_ALIGN", "0") == "1"
        self._reset_align_along = 0.399
        self._reset_align_max_ticks = 600
        #: P34-B: the reset's own settle (physics ticks after the teleport to
        #: the calibrated start pose; the shipped value is 20). A measurement
        #: knob for the reset-pose diagnostic only - at 20 it is byte-identical
        #: to the shipped path. It cannot be swept independently of the fruit's
        #: advance (the belt runs during it), so a sweep is read through the
        #: `[align]` row's `q_r`/`q_f` (the pose) and the first call's along.
        self._reset_settle = max(1, int(os.environ.get("FRUIT_RESET_SETTLE", "20")))
        #: `FRUIT_RESET_ALIGN_DIAG=1`: one `[align]` row per episode (pure
        #: reporting) with the first model call's along/visible-fraction inputs
        #: and the target-mask counters at the fire zone. Runs on both A/B arms
        #: (the control needs the manipulation check too).
        self._align_diag = os.environ.get("FRUIT_RESET_ALIGN_DIAG", "0") == "1"
        if self._reset_align:
            if presentation != "direct":
                raise ValueError(
                    "FRUIT_RESET_ALIGN is only defined for presentation='direct' "
                    "(the handoff presentation teleports the fruit to the station)"
                )
            self._reset_align_along = float(
                os.environ.get("FRUIT_RESET_ALIGN_ALONG", str(self._reset_align_along))
            )
            self._reset_align_max_ticks = max(
                1, int(os.environ.get("FRUIT_RESET_ALIGN_MAX_TICKS", "600"))
            )
        # --- P35 phase 1 / P43 phase 4: the inactive arm's park -------------- #
        #: `FRUIT_ARM_PARK=<name>`: park the **inactive** arm at a named pose
        #: from `configs/arm_parks.json` instead of the shipped `ready`
        #: waypoint, for the whole episode. Measured (P35 phase 1,
        #: `logs/p35/A_READ.md`): the inactive left arm at `ready` hides 98 % of
        #: a 58 mm fruit at along +0.35 and 57 % at +0.40, and the park named
        #: `back` takes the marginal cover to 0.002. `=ready` is byte-inert: no
        #: file read, one dict lookup per arm.
        #:
        #: **P43 phase 4 (the adoption): `back` is the `direct` presentation's
        #: default.** The phase-3 A/B re-measured the park on this tree's
        #: 9.8-9.9 N grip profile (`logs/p43/P3_RESULTS.md`): right-arm carried
        #: **20/54 -> 0/56**, right placed **32/54 -> 53/56**, run level 5/5,
        #: cycle +0.2 %. The default is scoped to `presentation == "direct"`
        #: (the guard below still raises for a named park on any other
        #: presentation, so `handoff` constructions are unchanged);
        #: **`FRUIT_ARM_PARK=ready` restores the shipped pose** everywhere, and an
        #: explicit env value always wins - which is also the escape hatch for
        #: reproducing a pre-P43 direct arm (every direct number before this
        #: phase is a *pre-park* number).
        self._park_env = os.environ.get("FRUIT_ARM_PARK")
        self._arm_park, self._arm_park_defaulted = resolve_arm_park(
            presentation, self._park_env
        )
        self._arm_park_poses: dict[str, np.ndarray] = {}
        self._arm_park_source: dict | None = None
        if self._arm_park and self._arm_park != "ready":
            if presentation != "direct":
                raise ValueError(
                    "FRUIT_ARM_PARK is only defined for presentation='direct' "
                    "(the scripted line parks through tasks.go_ready)"
                )
            park_path = os.environ.get(
                "FRUIT_ARM_PARK_FILE", os.path.join(_REPO_ROOT, "configs/arm_parks.json")
            )
            with open(park_path, encoding="utf-8") as fh:
                parks = json.load(fh)
            entry = parks.get("parks", {}).get(self._arm_park)
            if entry is None:
                raise ValueError(
                    f"FRUIT_ARM_PARK={self._arm_park!r} is not in {park_path} "
                    f"(have: {sorted(parks.get('parks', {}))})"
                )
            for name in ("left", "right"):
                vec = entry.get(name)
                if vec:
                    self._arm_park_poses[name] = np.asarray(vec, dtype=float).reshape(7)
            self._arm_park_source = {
                "name": self._arm_park,
                #: P43 phase 4 (A1): the resolved park's origin. `true` = the
                #: direct presentation's default (the adoption), `false` = an
                #: explicit `FRUIT_ARM_PARK`. Without it a post-flip store and
                #: an opt-in arm look identical in the manifest.
                "defaulted": self._arm_park_defaulted,
                "file": os.path.relpath(park_path, _REPO_ROOT),
                "source": parks.get("source", ""),
                "sides": sorted(self._arm_park_poses),
            }
        # --- P36 phase 1: the proprio spoof, default off --------------------- #
        #: `FRUIT_PROPRIO_SPOOF=<pose>` (direct presentation only): replace the
        #: **inactive** arm's 7 joint values in the observation's proprio with
        #: the pose the reset *achieved* for that pose (the `q_settled` rows of
        #: the P35 batch, `configs/proprio_spoof.json`), leaving the image, the
        #: active arm, the fingers and the tactile channels untouched. It is the
        #: P35 mechanism discriminator's proprio channel: `FRUIT_ARM_PARK` moves
        #: the arm (the image), this writes the obs (the proprio), and
        #: `logs/p36/PREREG.md` crosses the two. Pure observation code - no
        #: simulation state is written - and off it is not even a copy: the
        #: vector dict is empty and `proprio()` skips the call.
        self._spoof_pose = os.environ.get("FRUIT_PROPRIO_SPOOF", "").strip()
        self._spoof_vectors: dict[str, np.ndarray] = {}
        self._spoof_source: dict | None = None
        if self._spoof_pose:
            if presentation != "direct":
                raise ValueError(
                    "FRUIT_PROPRIO_SPOOF is only defined for presentation='direct' "
                    "(the handoff presentation is the harness reproduction)"
                )
            spoof_path = os.environ.get(
                "FRUIT_PROPRIO_SPOOF_FILE",
                os.path.join(_REPO_ROOT, "configs/proprio_spoof.json"),
            )
            with open(spoof_path, encoding="utf-8") as fh:
                spoof = json.load(fh)
            poses = spoof.get("poses", {})
            entry = poses.get(self._spoof_pose)
            if entry is None:
                raise ValueError(
                    f"FRUIT_PROPRIO_SPOOF={self._spoof_pose!r} is not in {spoof_path} "
                    f"(have: {sorted(poses)})"
                )
            for name in ("left", "right"):
                vec = entry.get(name)
                if vec is None:
                    continue
                arr = np.asarray(vec, dtype=np.float32).reshape(-1)
                if arr.size != 7 or not np.all(np.isfinite(arr)):
                    raise ValueError(
                        f"proprio spoof {self._spoof_pose!r}/{name} must be 7 finite "
                        f"joint values (got {arr.size})"
                    )
                self._spoof_vectors[name] = arr
            if not self._spoof_vectors:
                raise ValueError(
                    f"FRUIT_PROPRIO_SPOOF={self._spoof_pose!r} has no side vector in "
                    f"{spoof_path}"
                )
            self._spoof_source = {
                "pose": self._spoof_pose,
                "file": os.path.relpath(spoof_path, _REPO_ROOT),
                "source": spoof.get("source", ""),
                "sides": sorted(self._spoof_vectors),
            }
        #: P36: a recorded store must not carry a spoofed proprio (the spoof is
        #: an evaluation interface). `record` + the pose is refused here, before
        #: any episode runs; the predicate is pinned offline by `218`.
        _store_refusal = store_guard_reason(record, self._spoof_pose)
        if _store_refusal:
            raise ValueError(_store_refusal)
        #: `FRUIT_SPOOF_DIAG=1` (P36 phase 1): report the substitution from the
        #: log alone - the 7 indices, the live and written values, the md5 of
        #: the assembled proprio before/after, and the md5 of the same vector
        #: with the 7 indices zeroed (equal iff *only* those 7 changed). Pure
        #: reporting over the array `proprio()` already built; off, nothing is
        #: hashed or printed.
        self._spoof_diag = os.environ.get("FRUIT_SPOOF_DIAG", "0") == "1"
        self._spoof_index_cache: dict[str, list[int]] | None = None
        self._spoof_calls = 0
        self._spoof_drift = float("nan")
        self._spoof_first: dict | None = None
        #: `FRUIT_PARK_DIAG=1` (P35 phase 2, Gate-1 P0 revision): the **per-call
        #: park manipulation check** of `logs/p35/PREREG.md` section 2. M1 is
        #: "the pose held": the inactive arm's joints at the first **non-stale**
        #: model call against the pose the reset actually **achieved** (read
        #: after the reset's own settle), plus the achieved-vs-commanded
        #: residual as a report (the teleport re-bases onto the measured state,
        #: so the command is not reachable within 0.02 rad). M2 is "the
        #: sightline": censused over the **+0.30..+0.40** band (phase 1's cover
        #: is 0.81 / 0.98 / 0.57 there and 0.01 at +0.45, so +0.45 samples the
        #: one pose the mechanism is not about) and read at the band's **worst**
        #: call, with the arm's pixels counted inside the target's **projected
        #: disc** bbox - the analytic sphere projection, not the visible-mask
        #: extent, which shrinks with the occluder it is supposed to measure.
        #: The first model call is skipped: it conditions on the pre-reset frame
        #: (P34-B), so it cannot carry a pose or sightline claim. Pure reporting
        #: and off by default: with `image_channels == 5` the segmentation frame
        #: is already read, so this only keeps it plus one projection per band
        #: call; off, none of these fields is read or written.
        self._park_diag = os.environ.get("FRUIT_PARK_DIAG", "0") == "1"
        self._park_band = (0.30, 0.40)
        self._last_seg = None
        self._last_seg_labels: dict = {}
        self._park_settled: dict[str, np.ndarray] = {}
        self._park_q_settled: list[float] = []
        self._park_m1_hold = float("nan")
        self._park_m1_cmd = float("nan")
        self._park_q_first: list[float] = []
        self._park_q_band: list[float] = []
        self._park_band_along = float("nan")
        self._park_band_x = float("nan")
        self._park_band_px = -1
        self._park_band_disc = -1.0
        self._park_band_vis = -1.0
        self._park_band_arm = -1
        self._park_band_top = ""
        self._park_pxc_max = -1.0
        self._park_band_calls = 0
        self._park_stale_skipped = 0
        self._park_worst_arm = -1.0
        self._park_worst_arm_along = float("nan")
        self._park_worst_vis = -1.0
        self._park_worst_vis_along = float("nan")
        self._park_worst_top = ""
        self._park_min_frac = -1.0
        self._park_max_frac = -1.0
        self._park_min_frac_along = float("nan")
        self._park_max_frac_along = float("nan")
        self._park_min_rel = -1.0
        self._park_min_rel_along = float("nan")
        #: Per-episode diagnostic state (`_align_diag` only; pure reporting).
        self._align_y0 = float("nan")        # the selection (header) along
        self._align_along_reset = float("nan")   # along at the reset return
        self._align_steps = 0                # alignment physics ticks
        self._align_first_along = float("nan")
        self._align_first_x = float("nan")
        self._align_first_d = float("nan")
        self._align_first_px = -1            # target mask pixels at the 1st call
        self._align_first_visible = -1       # call index of the first visible frame
        self._align_hidden_calls = 0         # calls with a zero target mask first
        self._align_q_reset: list[float] = []  # active arm's joints at the reset return
        self._align_q_first: list[float] = []  # ... at the first model call (P34-B)
        self._align_px_max = -1              # the episode's largest target mask (P34-B)
        #: P34-B: the depth-corrected mask (px * camera distance^2), the same
        #: measure as `213`'s per-episode normalisation - the raw pixel count
        #: grows as the fruit approaches the head camera, so `px / px_max`
        #: alone would read a depth change as an occlusion change.
        self._align_pxc_first = -1.0
        self._align_pxc_max = -1.0
        self._align_zone_n = 0               # fire-zone (0.15-0.30) calls
        self._align_zone_zero = 0            # ... with a zero target mask
        self._align_zone_px: list[int] = []  # ... target-mask pixels

        # --- P38 phase 2: the lateral-refusal harness, default off ----------- #
        #: The direct harness holds **one** candidate per episode, and the
        #: trigger's lateral gate refuses it *silently*: `should_fire` returns
        #: `False` with no marker, nothing re-selects, and the attempt burns the
        #: whole 1500-tick policy horizon (`rl_env.py` `act`, the only exit) to
        #: end `timeout: no grasp within 1500 ticks`. Measured on the shipped
        #: interface: 2/3103 episodes; on the patch band 2/653 direct episodes
        #: are delivered below the arm's admission floor (`logs/p38/
        #: P1_RESULTS.md`). Four knobs, all `presentation == "direct"` only and
        #: all off by default (`logs/p38/PREREG_A1.md`):
        #:   FRUIT_POLICY_REFUSE_DIAG=1     one `lateral refuse:` note per
        #:                                  candidate at the first *provable*
        #:                                  refusal (run-neutral: a note)
        #:   FRUIT_POLICY_REFUSE_END=1      end at the fruit's departure with the
        #:                                  named class `no firable fruit` -
        #:                                  gated on a **measured** joint closure
        #:                                  (the trigger refuses *and* the learned
        #:                                  close never fired), because the lateral
        #:                                  gate has never bound the policy-close
        #:                                  path (`direct_fire`), so the trigger's
        #:                                  refusal alone is not "nothing can fire"
        #:   FRUIT_POLICY_RESEED=1          bounded same-lane re-selection at the
        #:                                  first provable refusal (implies DIAG)
        #:   FRUIT_POLICY_RESEED_MAX=2      adoptions per episode (0 = off); M1
        #:                                  cannot reach it (nothing is adopted)
        self._refuse_diag = os.environ.get("FRUIT_POLICY_REFUSE_DIAG", "0") == "1"
        self._refuse_end = os.environ.get("FRUIT_POLICY_REFUSE_END", "0") == "1"
        self._reseed = os.environ.get("FRUIT_POLICY_RESEED", "0") == "1"
        self._reseed_max = max(0, int(os.environ.get("FRUIT_POLICY_RESEED_MAX", "2")))
        self._reseed_scans_max = 4        # the PREREG's scan bound (per refusal)
        self._reseed_stride = 60          # ticks between scans (0.5 s, A2c)
        self._refuse_knobs = bool(self._refuse_diag or self._refuse_end or self._reseed)
        if self._refuse_knobs and presentation != "direct":
            raise ValueError(
                "FRUIT_POLICY_REFUSE_DIAG / _END / RESEED are only defined for "
                "presentation='direct' (the scripted/collector paths never run "
                "the trigger's silent refusal)"
            )
        if self._reseed and self._reseed_max <= 0:
            self._reseed = False
        if self._reseed:
            # The re-selection note is what the conversion is read from.
            self._refuse_diag = True
        self._refuse_latch: dict | None = None
        self._refuse_count = 0
        self._refuse_indices: set[int] = set()
        self._policy_close_seen = False
        self._policy_best_gap = float("inf")
        self._reseed_left = int(self._reseed_max)
        self._reseed_adopted = 0
        self._reseed_scans = 0
        self._no_firable = False

        # --- event-triggered replanning (path-3 arm), default off ----------- #
        #: DVAC/ChunkTrust-spirited test-time horizon adaptation: the execute
        #: horizon for each newly sampled chunk is chosen from the continuity
        #: between the new chunk's clean actions and the previous chunk's
        #: overlapping prediction (see `_event_horizon`). Off by default; when
        #: off the loop is the shipped fixed `execute_steps`.
        self._event = os.environ.get("FRUIT_POLICY_EVENT", "0") == "1"
        self._event_min = max(2, int(os.environ.get("FRUIT_POLICY_EVENT_MIN", "2")))
        self._event_max = max(
            self._event_min, int(os.environ.get("FRUIT_POLICY_EVENT_MAX", "6"))
        )
        self._event_default = min(
            self._event_max,
            max(
                self._event_min,
                int(os.environ.get("FRUIT_POLICY_EVENT_HORIZON", str(self.execute_steps))),
            ),
        )
        if self._event and presentation != "direct":
            raise ValueError(
                "event-triggered replanning is only defined for presentation='direct'"
            )
        #: A2C2-style per-step correction head (path-3 arm), default off. Loaded
        #: after the policy below (it only needs the checkpoint normalizer).
        self._a2c2_path = os.environ.get("FRUIT_A2C2", "").strip()
        self._a2c2 = None

        # --- RTC (real-time chunking), default off --------------------------- #
        from .policy.runtime import RTCSettings

        self.rtc_settings = RTCSettings.from_env()
        if self.rtc_settings.enabled:
            if presentation != "direct":
                raise ValueError("RTC is only defined for presentation='direct'")
            if dagger is not None:
                raise ValueError("RTC and the DAgger expert are mutually exclusive")
        #: `FRUIT_RTC_REPORT=1` records per-control-step wall time and the executed
        #: action stream's boundary jumps, for both the legacy and the RTC path.
        #: Pure reporting (already-materialised CPU arrays plus `perf_counter`),
        #: off for the rate runs.
        self._rtc_report = os.environ.get("FRUIT_RTC_REPORT", "0") == "1"
        self.rtc = None
        #: P43 L2 (`FRUIT_LOOP_TIMING=1`, default off): the policy loop's wall
        #: **decomposition** - one accumulator per stage of the decision period,
        #: so the pause is attributed instead of inferred. The stages are the
        #: three that can own it: the model call (`sample_chunk`), the render
        #: (`RenderingManager.render()`, inside `_observe`) and the camera reads
        #: (`get_data`, same site); "other" is derived per episode as the total
        #: episode wall minus those three. `perf_counter` only - no command, no
        #: state read, no control input - but per `AGENTS.md` section 2 the
        #: instrument sits *inside* the run it measures, so the row is a wall
        #: measurement of that run, never a rate pair, and it is off by default.
        self._loop_timing = os.environ.get("FRUIT_LOOP_TIMING", "0") == "1"
        self._loop_t: dict[str, float] = {
            "policy_ms": 0.0, "render_ms": 0.0, "camera_ms": 0.0,
        }
        self._loop_counts: dict[str, int] = {"observations": 0, "decisions": 0}
        self._loop_episodes: list[dict] = []
        #: Run-level RTC report accumulators (only filled when `_rtc_report`).
        self._rtc_totals: dict = {
            "boundary": [], "within": [], "step": [], "jerk": [],
            "control_ms": [], "policy_ms": [],
            "switches": 0, "steps": 0, "chunks": 0, "decisions": 0,
            "policy_ms_total": 0.0,
        }

        # --- frozen-tree check, before any simulator state is spent ---------- #
        self.tasks_md5 = self._verify_tasks()

        # Deferred Isaac imports: this module must import offline (selfcheck).
        import isaacsim.core.experimental.utils.app as app_utils
        from isaacsim.core.rendering_manager import RenderingManager
        from isaacsim.core.simulation_manager import SimulationManager

        from .assets import SceneConfig
        from .common import say
        from .fruits import FruitSpawner
        from .scene import SortingScene
        from .tactile import GripperTactile
        from .tasks import PickAndPlaceTask

        self._app_utils = app_utils
        self._RenderingManager = RenderingManager
        self._SimulationManager = SimulationManager
        self._say = say
        self._sim_time = lambda: float(SimulationManager.get_simulation_time())

        # The direct presentation's contract is "no station hand-off": a fruit
        # the policy is about to grasp must not be teleported to the nest mark.
        # `grasp_carry_place` only teleports when the fruit is > FRUIT_HANDOFF_MAX
        # from the nest centre (default 0.30 m) or below seat height; disabling
        # that fallback does not change the function, only the data it sees.
        if presentation == "direct":
            os.environ.setdefault("FRUIT_HANDOFF", "contact")
            os.environ.setdefault("FRUIT_HANDOFF_MAX", "10.0")

        kwargs = {}
        if size_filter:
            kwargs["size_filter"] = size_filter
        self.cfg = SceneConfig(**kwargs)
        self.scene = SortingScene(self.cfg).build()
        self.tactile = GripperTactile()
        self.tactile.attach(stage=self.scene.stage)
        self.scene.start(physics_dt=1.0 / 120.0, warmup_steps=60)
        self.tactile.refresh()

        self.spawner = FruitSpawner(
            self.scene.stage,
            self.cfg,
            seed=self.seed,
            # P85 scope: the direct/policy presentation is **not** the scripted
            # bimanual cell. It never runs `run_bimanual`, so it pins the supply
            # plan to the single-arm defaults instead of resolving the two
            # scheduler knobs - otherwise the flip's dense wave sheet and
            # balanced mix would silently re-baseline every direct cell.
            two_line=False,
            band_interlock=(
                self._supply["band_interlock"] if self.presentation == "direct" else None
            ),
            band_max=(
                self._supply["band_max"] if self.presentation == "direct" else None
            ),
        )
        self.spawner.create_pool()
        self.advance(30)
        self.spawner.refresh_rigids()
        self.spawner.belt = self.scene.belt
        self.spawner.reset()
        self.spawner.prime(count=6)

        # Policy (only `ablate=none`): the same runner the hybrid evaluator uses.
        from .policy.runtime import PolicyRunner, RealtimeChunker

        self.policy = PolicyRunner(checkpoint) if ablate == "none" else None
        if self.policy is not None:
            say(
                f"[rl] loaded {checkpoint} (obs_horizon={self.policy.obs_horizon}, "
                f"action_horizon={self.policy.action_horizon})"
            )
            if self._a2c2_path:
                from .policy.correction import CorrectionController

                self._a2c2 = CorrectionController(
                    self._a2c2_path, device=self.policy.device
                )
                say(
                    f"[rl] A2C2 correction head {self._a2c2_path} "
                    f"(gain={self._a2c2.gain}, clamp={self._a2c2.clamp})"
                )
            self.action_dim = int(self.policy.config["action_dim"])
            self.action_horizon = int(self.policy.config["action_horizon"])
            self._image_channels = int(self.policy.config["image_channels"])
            # P28-B: the observation width is a property of the artifact, and
            # the gate decides it here - so a 26-D checkpoint without the gate
            # (or the other way round) fails at construction, loudly, instead of
            # conditioning the policy on a vector it never saw.
            want_proprio = 25 + (1 if self._speed_channel else 0)
            got_proprio = int(self.policy.config.get("proprio_dim", 25))
            if got_proprio != want_proprio:
                raise RuntimeError(
                    f"checkpoint {checkpoint} has proprio_dim={got_proprio} but "
                    f"this environment builds {want_proprio}-D proprio "
                    f"(FRUIT_OBS_SPEED={'1' if self._speed_channel else 'unset'}). "
                    "Set FRUIT_OBS_SPEED=1 to run a 26-D (belt-speed channel) "
                    "checkpoint, or unset it for a 25-D one."
                )
            if self.rtc_settings.enabled:
                self.rtc = RealtimeChunker(
                    self.policy,
                    execute_steps=self.execute_steps,
                    settings=self.rtc_settings,
                )
                say(
                    f"[rl] {self.rtc_settings.summary()} period={self.execute_steps} "
                    f"(interleaved sampler, no background thread)"
                )
        else:
            self.action_dim = 9
            self.action_horizon = 16
            self._image_channels = 5

        # --- P52 phase 2: the contact-gated action time-scale, default off -- #
        #: `FRUIT_POLICY_TIME_SCALE=<s>` executes the active chunk's waypoints
        #: `s` times faster by linearly interpolating the 9-D absolute joint
        #: targets (`retime_action`) - the same predicted path in fewer ticks,
        #: the model unchanged. `s == 1.0` (unset) is the shipped one-waypoint-
        #: per-tick path, byte-identical by construction: `act` never reaches the
        #: interpolation. `FRUIT_POLICY_RETIME_GATE=1` arms the **contact gate**
        #: (`retime_contact`): the scale applies only outside contact and is
        #: clamped to 1.0 while the fingers are loaded or closed.
        #:
        #: Scope: `direct` only. The `handoff`/canary presentation and the
        #: scripted/bimanual paths never see a policy chunk re-timed - the
        #: scripted line's own speed lever is the P44 profile cells, whose cost
        #: class is measured (`logs/p51/COMBO_MAP.md`), and mixing them would
        #: move two things at once. RTC is refused because it never returns a
        #: chunk to `act` (one action per tick from its own queue), so the knob
        #: would silently be a no-op arm.
        self._time_scale = resolve_time_scale(
            os.environ.get("FRUIT_POLICY_TIME_SCALE")
        )
        self._retime_gate_on = (
            os.environ.get("FRUIT_POLICY_RETIME_GATE", "0") == "1"
        )
        self._retime_force_threshold = float(
            os.environ.get("FRUIT_POLICY_RETIME_FORCE", "1.0")
        )
        self._retime_open_threshold = float(
            os.environ.get("FRUIT_POLICY_RETIME_OPEN", "0.020")
        )
        #: True when either knob is armed. Off, every branch below is the
        #: shipped one and no counter, read or print exists.
        self._retime_on = bool(self._time_scale != 1.0 or self._retime_gate_on)
        if self._retime_on:
            if presentation != "direct":
                raise ValueError(
                    "FRUIT_POLICY_TIME_SCALE / FRUIT_POLICY_RETIME_GATE are only "
                    f"defined for presentation='direct', got {presentation!r}"
                )
            if self.rtc_settings.enabled:
                raise ValueError(
                    "the action time-scale needs a chunk from `act`; RTC executes "
                    "one action per tick from its own queue and never passes one"
                )
            if self._time_scale * self.execute_steps > self.action_horizon:
                raise ValueError(
                    f"FRUIT_POLICY_TIME_SCALE={self._time_scale} x "
                    f"execute_steps={self.execute_steps} exceeds the chunk's "
                    f"action_horizon={self.action_horizon}"
                )
            if self._retime_force_threshold < 0.0:
                raise ValueError("FRUIT_POLICY_RETIME_FORCE must be >= 0 N")
            if self._retime_open_threshold < 0.0:
                raise ValueError("FRUIT_POLICY_RETIME_OPEN must be >= 0 m")
        #: The gate's two cached channels. They are written in `proprio()` from
        #: the reads that already happen there (the tactile normal force and the
        #: active arm's finger opening), so the gate adds **no** sensor read to
        #: the control loop - the value a tick uses is the one from the
        #: decision's own observation, at most 3 ticks old.
        self._retime_force_live = 0.0
        self._retime_finger_live = 0.0
        #: Per-episode gate bookkeeping (only touched when armed): consulted
        #: ticks and clamped ticks, the per-decision pair the `[retime]` rows
        #: report, and the peak force seen.
        self._retime_calls = 0
        self._retime_gated = 0
        self._retime_decisions = 0
        self._retime_gated_decisions = 0
        self._retime_force_gated = 0
        self._retime_finger_gated = 0
        self._retime_force_max = 0.0

        # P53: the policy's own emission defect - two default-off cells. C1
        # clips the 7 absolute joint targets into the joint range before the
        # drives see them (`FRUIT_POLICY_JOINT_CLAMP`); C2 executes each chunk
        # waypoint over `hold` control ticks (`FRUIT_POLICY_ACTION_HOLD`). Both
        # resolve to the shipped path when unset, and `_apply`/`act` then take
        # the shipped branch exactly (`if self._joint_clamp:` /
        # `if self._action_hold > 1:`), which is what makes the control arm the
        # shipped code rather than a re-derivation of it. The joint range is
        # NOT copied here: `_apply` reads the arm's own `arm_lo`/`arm_hi`
        # (`control.py:197-202`, one `get_dof_limits()` read at construction),
        # so the clip uses the drive's own limits on the arm it commands.
        self._joint_clamp = resolve_joint_clamp(
            os.environ.get("FRUIT_POLICY_JOINT_CLAMP")
        )
        self._action_hold = resolve_action_hold(
            os.environ.get("FRUIT_POLICY_ACTION_HOLD")
        )
        if (self._joint_clamp or self._action_hold > 1) and presentation != "direct":
            raise ValueError(
                "FRUIT_POLICY_JOINT_CLAMP / FRUIT_POLICY_ACTION_HOLD are only "
                f"defined for presentation='direct', got {presentation!r}"
            )
        if self._action_hold > 1:
            if self.rtc_settings.enabled:
                raise ValueError(
                    "the action hold needs a chunk from `act`; RTC executes one "
                    "action per tick from its own queue and never passes one"
                )
            if self._retime_on:
                raise ValueError(
                    "FRUIT_POLICY_ACTION_HOLD (a slower replay) and "
                    "FRUIT_POLICY_TIME_SCALE / FRUIT_POLICY_RETIME_GATE (a faster "
                    "one) are opposite re-parameterisations of the same chunk"
                )
            if self._event:
                raise ValueError(
                    "FRUIT_POLICY_ACTION_HOLD and FRUIT_POLICY_EVENT both choose "
                    "how many ticks a decision covers"
                )
            if self.execute_steps > self.action_horizon:
                raise ValueError(
                    f"execute_steps={self.execute_steps} exceeds the chunk's "
                    f"action_horizon={self.action_horizon}"
                )
        if self._joint_clamp and self._retime_on:
            raise ValueError(
                "FRUIT_POLICY_JOINT_CLAMP is measured on the shipped "
                "one-waypoint-per-tick replay; combining it with the time-scale "
                "would move two things at once"
            )
        #: The `[emit]` row's provenance (P53): one flag, so the per-episode
        #: out-of-range count is a *report* and never a control input. The
        #: counter is pure array work on the action `_apply` already holds - no
        #: simulator read - so it cannot perturb the loop the way a per-tick
        #: articulation read does (AGENTS.md section 2).
        self._emit_diag = os.environ.get("FRUIT_EMIT_DIAG", "0") == "1"
        self._emit_ticks = 0
        self._emit_decisions = 0
        self._emit_pre_out = 0
        self._emit_post_out = 0
        self._emit_pre_max = 0.0
        self._emit_clamped_ticks = 0

        # The task is used for its primitives only; it must not record.
        self.task = PickAndPlaceTask(
            self.scene, self.spawner, self.tactile, self.cfg,
            waypoint_path=waypoint_path,
            feed_cadence=(
                self._supply["cadence"] if self.presentation == "direct" else None
            ),
            grasp_quat_override=self._grasp_quat_override,
            carry_hold_override=self._carry_hold_override,
            lift_dz=self._lift_dz,
            lift_climb=self._lift_climb,
            finger_cap_scope=self._finger_cap_scope,
        )
        self.task.recorder = None

        with open("configs/waypoints.json", encoding="utf-8") as fh:
            self.waypoints = json.load(fh)

        # Harness warm-up (60_eval_policy.py does this once): both arms parked at
        # the calibrated ready pose before the first episode - the initial
        # condition the demonstrations start from, and part of the 22-D proprio
        # the policy sees.
        for name in ("left", "right"):
            arm = self.task.arms[name]
            arm.set_gripper(arm.OPEN)
            arm.teleport_joints(
                np.asarray(self.waypoints["arms"][name]["ready"], dtype=float)
            )
        self.advance(40)

        self._out_dir = out_dir
        self.run_dir = None
        self.manifest_path = None
        if out_dir:
            self.run_dir = os.path.join(
                out_dir, f"{presentation}_{ablate}_seed{self.seed}"
            )
            os.makedirs(self.run_dir, exist_ok=True)
            self._manifest_base = self._build_manifest(checkpoint)
            self._write_manifest()

        self._recorder = RolloutRecorder(self.run_dir) if (record and self.run_dir) else None

        self.belt_top = float(self.cfg.belt_center[2]) + float(self.cfg.belt_size[2]) / 2.0
        self._episode = -1
        self._done = True
        self._sample = None
        self._active = "left"
        self._bin_index = 0
        self._goal = np.zeros(8, dtype=np.float32)
        self._tick = 0
        self._step = 0
        self._observed_step = -1
        self._last_rgb: np.ndarray | None = None
        self._last_depth: np.ndarray | None = None
        self._last_mask: np.ndarray | None = None
        self._outcome: dict | None = None
        # --- DAgger expert state (only when `dagger` is set) ----------------- #
        self._expert_until = -1
        self._expert_close_start: int | None = None
        self._expert_label: np.ndarray | None = None
        self._expert_grasp = np.zeros(7, dtype=np.float32)
        self._expert_jaw_y = float(self.cfg.pick_y)
        self._policy_proposal: np.ndarray | None = None
        self._ep_interventions = 0
        self._ep_expert_ticks = 0
        say(f"[rl] env ready: presentation={presentation} ablate={ablate} "
            f"dagger={'on' if dagger is not None else 'off'} "
            f"park={self._park_label()} "
            f"camera={self._camera_res_text()} tasks_md5={self.tasks_md5[:8]}")
        if self.trigger_settings.enabled:
            say(f"[rl] {self.trigger_settings.summary()}")
        if self.presentation == "direct":
            say(self._supply_profile_row(self._supply, self._direct_feed))
        if self._finger_cap_scope:
            # P78/P79: the armed runtime cap's own row. Only an armed run prints
            # it, so a log's first lines say whether the drive was re-clamped -
            # the per-leg `[drive] ... finger cap raise/restore` rows carry the
            # in-leg read-back, this row carries the intent, the scope and the
            # leg class ("place*" for `place-left`, "grasp_lift" for the P79
            # `grasp-left`).
            say(
                f"[drive] finger cap scope: "
                f"{finger_cap_scope_label(self._finger_cap_scope)} x "
                f"{self._finger_cap_value:g} N "
                f"(runtime, {', '.join(sorted(self._finger_cap_scope))} "
                f"{finger_cap_scope_legs(self._finger_cap_scope)} legs; "
                f"restored at each leg's end)"
            )
        if self._grasp_quat_override:
            # P62 phase 2: the armed knob's own row. It names **all three**
            # attitudes the run touches, because on the dynamic catch the
            # commands are not all the same object: the `grasp` pre-pose hold
            # (`_grasp_quat`, i.e. the override / the file) is released before
            # the descent (`tasks._run_impl` sets `hold_quaternion = None`, then
            # the never-stop catch installs its own top-down hold), so a row
            # that named only the override could not say which attitude the arm
            # was asked for during the close. `file_same` / `hold_same` are the
            # two equalities that decide whether the knob can move anything.
            say(
                self._grasp_override_row(
                    self._grasp_quat_override,
                    self.task.waypoints,
                    os.environ.get("FRUIT_HAND_AXIS", "x"),
                )
            )
        if self._carry_hold_override:
            # P64 phase 1: the armed pre-compensation's own row - the command
            # quaternion, the measured drift it inverts, and the belt projection
            # it is predicted to remove. The *control* (knob unset) prints
            # nothing at all, so a log says in its first lines whether it ran
            # the pre-compensated lift.
            say(self._precomp_row(self._carry_hold_override))
        if self._lift_dz is not None:
            # P66 phase 2/3: the lift-height offset's own row - the resolved dz
            # **and its origin** (`default` / `explicit`, the `park=back(default)`
            # pattern), the arm/leg scope, the height it puts the lift's end at
            # and the documented restore, so a log says which rung it ran
            # (`belt_top` from the task, i.e. the value `jaw_target` itself adds
            # to). Since the flip it prints on every `direct` run.
            say(
                self._lift_dz_row(
                    self._lift_dz, self.task.belt_top, self._lift_dz_defaulted
                )
            )
        if self._lift_climb is not None:
            # P67: the climb re-shape's own row (only when armed - the knob has
            # no presentation default, so an unset run prints nothing at all).
            say(
                self._lift_climb_row(
                    self._lift_climb,
                    self.task.belt_top,
                    self.cfg,
                    self._lift_dz,
                )
            )
        if self._continuous_picks > 0:
            say(
                f"[cont] enabled: picks_target={self._continuous_picks} "
                f"feed=on(implied) bed_diag={int(self._bed_diag)} "
                "(one reset per episode, one episode per n picks)"
            )
        if self._refuse_knobs:
            say(
                f"[rl] refuse: diag={int(self._refuse_diag)} "
                f"end={int(self._refuse_end)} reseed={int(self._reseed)} "
                f"max={int(self._reseed_max)}"
            )
        if self._retime_on:
            # P52 phase 2: the knob's own banner, so an armed run is identifiable
            # from its first lines (and from the manifest's `retime` block).
            say(
                f"[rl] retime: scale={self._time_scale:.2f} "
                f"gate={int(self._retime_gate_on)} "
                f"force>{self._retime_force_threshold:.2f}N "
                f"finger<{self._retime_open_threshold * 1000:.1f}mm "
                f"execute_steps={self.execute_steps} "
                f"horizon={self.action_horizon}"
            )
        if self._joint_clamp or self._action_hold > 1:
            # P53: the emission cells' own banner - the resolved knobs plus the
            # joint ranges the clamp actually uses (read from the arm, so the
            # log proves which limits were applied rather than which were
            # intended).
            right = self.task.arms["right"]
            ranges = " ".join(
                f"j{i + 1}[{float(lo):+.3f},{float(hi):+.3f}]"
                for i, (lo, hi) in enumerate(zip(right.arm_lo, right.arm_hi))
            )
            say(
                f"[rl] emit: joint_clamp={int(self._joint_clamp)} "
                f"action_hold={self._action_hold} "
                f"execute_steps={self.execute_steps} "
                f"ticks_per_decision={self.execute_steps * self._action_hold} "
                f"hz={120.0 / self._action_hold:.1f} range(right)={ranges}"
            )

    # ------------------------------------------------------------------ #
    # Frozen-tree / manifest
    # ------------------------------------------------------------------ #
    def _verify_tasks(self) -> str:
        digest = _md5(os.path.join(_REPO_ROOT, "src/fruit_sorting/tasks.py"))
        if digest != TASKS_MD5:
            raise RuntimeError(
                "src/fruit_sorting/tasks.py md5 is "
                f"{digest or 'missing'}, expected {TASKS_MD5}. The RL environment "
                "was validated against the frozen revision; refusing to run on a "
                "different tree."
            )
        return digest

    def _camera_res_text(self) -> str:
        return os.environ.get(
            "FRUIT_CAMERA_RES",
            f"{self.cfg.camera_resolution[0]},{self.cfg.camera_resolution[1]}",
        )

    def _build_manifest(self, checkpoint: str | None) -> dict:
        sources = {
            name: _md5(os.path.join(_REPO_ROOT, name)) for name in _MANIFEST_SOURCES
        }
        checkpoint_md5 = ""
        if checkpoint:
            checkpoint_md5 = _md5(
                checkpoint
                if os.path.isabs(checkpoint)
                else os.path.join(_REPO_ROOT, checkpoint)
            )
        return {
            "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "presentation": self.presentation,
            "ablate": self.ablate,
            "seed": self.seed,
            "size_filter": self.cfg.size_filter,
            "camera_res": self._camera_res_text(),
            "fixed_stepping": True,
            "execute_steps": self.execute_steps,
            "ddim_steps": self.ddim_steps,
            "approach_steps": self.approach_steps,
            "reward": asdict(self.reward),
            "dagger": asdict(self.dagger) if self.dagger is not None else None,
            "rtc": asdict(self.rtc_settings) if self.rtc_settings.enabled else None,
            "rtc_report": bool(self._rtc_report),
            #: P43 L2: the wall-decomposition instrument's provenance (absent
            #: from every pre-P43 manifest = off). Reporting only; it never
            #: touches a command.
            "loop_timing": bool(self._loop_timing),
            "policy_track": bool(self._policy_track),
            #: P31-A: the wait gate's provenance (absent = off). An A/B arm must
            #: be identified by this block, not by the printed count alone.
            "wait_gate": asdict(self.wait_gate) if self.wait_gate.enabled else None,
            #: P34 phase 2: the reset alignment (absent = off; the diagnostic
            #: alone is recorded, because it changes the printed rows only).
            "reset_align": (
                {
                    "on": bool(self._reset_align),
                    "along": float(self._reset_align_along),
                    "max_ticks": int(self._reset_align_max_ticks),
                    "settle": int(self._reset_settle),
                    "diag": bool(self._align_diag),
                }
                if (self._reset_align or self._align_diag)
                else None
            ),
            #: P35 phase 1: the inactive arm's park (absent = the shipped
            #: `ready` waypoint). A run's arm pose is part of its scenario.
            "arm_park": self._arm_park_source,
            #: P64 phase 1: the pre-compensated left carry attitude (null = off,
            #: the shipped hold). An armed arm is identified by this block, not
            #: by the `[grasp] left precomp:` row alone - and it is a different
            #: scenario (the lift is commanded an attitude no shipped run has).
            "carry_hold_precomp": (
                {
                    "arm": "left",
                    "leg": "grasp_lift",
                    "axis": list(P64_LEFT_DRIFT_AXIS),
                    "angle_deg": P64_LEFT_DRIFT_ANGLE_DEG,
                    "q_cmd": [float(v) for v in GRASP_LEFT_PRECOMP],
                    "source": "median of 7 left grasp_lift legs (P63 A1_77 + P62 P0/P0b)",
                }
                if self._carry_hold_override
                else None
            ),
            #: P66 phase 2/3: the lift's target-height offset (null = the shipped
            #: `grasp_lift` end pose, i.e. a non-`direct` caller). A lifted arm is
            #: a **different scenario** - its lift ends at another height - so it
            #: is identified by this block, not by the `[grasp] lift_dz:` row
            #: alone. Since the flip `defaulted` says whether the value is the
            #: `direct` default or an explicit `FRUIT_LIFT_DZ`, and the per-arm
            #: `arms` map names the resolution the run actually applied (the right
            #: arm is never armed by this knob). `hand_target_m_above_belt` is the
            #: hand's own add - **not** "the shipped target": after a flip the
            #: shipped height is no longer the run's default, which is the P43
            #: `park` defect this rename closes. `default_target_m_above_belt` is
            #: what an unset `FRUIT_LIFT_DZ` would resolve to on this
            #: presentation.
            "lift_dz": (
                {
                    "leg": "grasp_lift",
                    "defaulted": bool(self._lift_dz_defaulted),
                    "dz_m_above_0p28": float(self._lift_dz.get("left", 0.0)),
                    "target_m_above_belt": 0.28
                    + float(self._lift_dz.get("left", 0.0)),
                    "default_dz_m_above_0p28": LIFT_DZ_DIRECT_DEFAULT,
                    "default_target_m_above_belt": 0.28 + LIFT_DZ_DIRECT_DEFAULT,
                    "hand_target_m_above_belt": 0.28
                    + float(os.environ.get("FRUIT_OPENARM_TRANSFER_LIFT", "0.08")),
                    "arms": {
                        "left": float(self._lift_dz.get("left", 0.0)),
                        "right": "shipped",
                    },
                }
                if self._lift_dz is not None
                else None
            ),
            #: P67: the place-leg climb (null = the shipped place leg, i.e. every
            #: non-direct caller and a direct run with `FRUIT_LIFT_CLIMB` unset).
            #: A climbed place leg is a **different trajectory** - it raises the
            #: pads vertically at the lift's own x/y before transiting - so a run
            #: is identified by this block (the `[grasp] lift_climb:` row alone is
            #: a print).
            "lift_climb": (
                {
                    "legs": "place0,place1",
                    "climb_m": float(self._lift_climb.get("left", 0.0)),
                    "arms": {"left": float(self._lift_climb.get("left", 0.0)),
                             "right": "shipped"},
                }
                if self._lift_climb is not None
                else None
            ),
            #: P36 phase 1: the proprio spoof (absent = the measured joints).
            #: A cell of the 2x2 is identified by this block plus `arm_park`;
            #: the image channel is the park, the obs channel is this.
            "proprio_spoof": self._spoof_source,
            #: P38 phase 2: the lateral-refusal harness (absent = all four
            #: knobs off, the shipped interface). An A/C arm is identified by
            #: this block, not by the printed note text.
            "refuse": (
                {
                    "diag": bool(self._refuse_diag),
                    "end": bool(self._refuse_end),
                    "reseed": bool(self._reseed),
                    "max": int(self._reseed_max),
                    "scans": int(self._reseed_scans_max),
                }
                if self._refuse_knobs
                else None
            ),
            "event_replan": {
                "enabled": bool(self._event),
                "min": int(self._event_min),
                "max": int(self._event_max),
                "default": int(self._event_default),
            },
            #: P52 phase 2: the contact-gated action time-scale (null = off, the
            #: shipped one-waypoint-per-tick execution). An A/B arm is
            #: identified by this block, not by the `[retime]` rows alone.
            "retime": (
                {
                    "scale": float(self._time_scale),
                    "gate": bool(self._retime_gate_on),
                    "force_n": float(self._retime_force_threshold),
                    "open_m": float(self._retime_open_threshold),
                }
                if self._retime_on
                else None
            ),
            #: P53: the emission cells (null = both knobs off, the shipped
            #: unchamped one-waypoint-per-tick replay). An A/B arm is identified
            #: by this block, not by the `[emit]` rows alone.
            "emit": (
                {
                    "joint_clamp": bool(self._joint_clamp),
                    "action_hold": int(self._action_hold),
                    "ticks_per_decision": int(
                        self.execute_steps * self._action_hold
                    ),
                }
                if (self._joint_clamp or self._action_hold > 1)
                else None
            ),
            "a2c2": (
                {
                    "path": self._a2c2_path,
                    "md5": _md5(
                        self._a2c2_path
                        if os.path.isabs(self._a2c2_path)
                        else os.path.join(_REPO_ROOT, self._a2c2_path)
                    ),
                    "gain": os.environ.get("FRUIT_A2C2_GAIN", "1.0"),
                    "clamp": os.environ.get("FRUIT_A2C2_CLAMP", "0.2"),
                }
                if self._a2c2_path
                else None
            ),
            "dynamic_force": {
                # OpenArm grip force servo (tasks.py; default off). Recorded even
                # when off so a run is identifiable from its manifest alone.
                "servo": os.environ.get("FRUIT_DYNAMIC_FORCE_SERVO", "0"),
                "min": os.environ.get("FRUIT_DYNAMIC_FORCE_MIN", "2.0"),
                "drop": os.environ.get("FRUIT_DYNAMIC_FORCE_DROP", "0.8"),
                "max": os.environ.get("FRUIT_DYNAMIC_FORCE_MAX", "12.0"),
                "ref_max": os.environ.get("FRUIT_DYNAMIC_FORCE_REF_MAX", "4.0"),
                "step": os.environ.get("FRUIT_DYNAMIC_FORCE_STEP", "0.0004"),
                "ticks": os.environ.get("FRUIT_DYNAMIC_FORCE_TICKS", "3"),
                "ref_ticks": os.environ.get("FRUIT_DYNAMIC_FORCE_REF_TICKS", "48"),
                "range": os.environ.get("FRUIT_DYNAMIC_FORCE_RANGE", "0.015"),
                "backoff": os.environ.get("FRUIT_DYNAMIC_FORCE_BACKOFF", "0.003"),
            },
            "dynamic_lift": {
                # v6 contact-verification dwell + staged first lift (tasks.py;
                # default off for both). Recorded even when off so a run is
                # identifiable from its manifest alone.
                # v7: `lift_peak` is the peak-hold lift metric, default **on**
                # only while a dynamic capture is active (the policy loop never
                # is, so its scenario is unchanged).
                "lift_peak": os.environ.get("FRUIT_DYNAMIC_LIFT_PEAK", "1"),
                "verify_dwell": os.environ.get("FRUIT_DYNAMIC_VERIFY_DWELL", "0"),
                "verify_force": os.environ.get("FRUIT_DYNAMIC_VERIFY_FORCE", "2.0"),
                "verify_ticks": os.environ.get("FRUIT_DYNAMIC_VERIFY_TICKS", "24"),
                "verify_max_ticks": os.environ.get(
                    "FRUIT_DYNAMIC_VERIFY_MAX_TICKS", "240"
                ),
                "ramp": os.environ.get("FRUIT_DYNAMIC_RAMP_LIFT", "0"),
                "ramp_step": os.environ.get("FRUIT_DYNAMIC_RAMP_STEP", "0.0025"),
                "ramp_step_ticks": os.environ.get(
                    "FRUIT_DYNAMIC_RAMP_STEP_TICKS", "24"
                ),
                "ramp_pause_ticks": os.environ.get(
                    "FRUIT_DYNAMIC_RAMP_PAUSE_TICKS", "24"
                ),
                "ramp_rest_ticks": os.environ.get(
                    "FRUIT_DYNAMIC_RAMP_REST_TICKS", "72"
                ),
            },
            "trigger": (
                asdict(self.trigger_settings) if self.trigger_settings.enabled else None
            ),
            "trigger_x_max": (
                # R7-A (WS-4.6): the reach-cliff guard binds the learned
                # policy-gate fire path too, so it acts even when the trigger
                # itself is off - recorded unconditionally for provenance.
                self.trigger_settings.x_max
            ),
            "tasks_md5": self.tasks_md5,
            "checkpoint": checkpoint or "",
            "checkpoint_md5": checkpoint_md5,
            "handoff_mode": os.environ.get("FRUIT_HANDOFF", ""),
            "handoff_max": os.environ.get("FRUIT_HANDOFF_MAX", ""),
            "no_attach": os.environ.get("FRUIT_NO_ATTACH", ""),
            "no_sleep": os.environ.get("FRUIT_NO_SLEEP", ""),
            "policy_seed": os.environ.get("FRUIT_POLICY_SEED", ""),
            # P28-A's collector field (`supply.belt_speed`, 9cbcfa2) had no
            # rollout-side twin: a direct A/B arm at 0.08 was identifiable only
            # from a sidecar (the P27 driver wrote one). The magnitude is
            # recorded because `SceneConfig.belt_speed` is signed along -Y.
            "belt_speed": abs(float(self.cfg.belt_speed)),
            # P28-B: whether the 26th proprio scalar (the belt-speed channel)
            # was part of the model's input for this run.
            "speed_channel": bool(self._speed_channel),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            #: P41 phase 4 (A2): the grip's physics, not just the tree that ran
            #: it. The shipped finger-drive profile moves the delivered pinch
            #: 2.2x (4.4 -> 9.8 N per pinch) without touching one trajectory,
            #: and `FRUIT_SUBSTEPS` reaches the same force at 3.08x wall, so a
            #: rollout store recorded under either was indistinguishable from a
            #: pre-profile one by its own metadata. The block is the *same
            #: builder the collector writes* (`finger_physics_provenance`), read
            #: back from the live articulations (gains **and** maxForce caps),
            #: so a direct-rollout store and a collector shard are comparable.
            #: A failure here must not stop an eval run: it degrades to a named
            #: block with the reason.
            "physics": self._physics_provenance(),
            #: P72: the scene's collider set (the rail pair, the output slab's
            #: top z / inboard edge, and the direct lift rung). P71's flips move
            #: the stream without moving one trajectory, and no manifest field
            #: named the geometry - so a pre-P71 store was identifiable only by
            #: an `assets.py` md5 that any unrelated edit also moves. Same
            #: builder as the collector's shard (`assets.scene_provenance`).
            "scene": self._scene_provenance(),
            #: P58: the supply profile this store was recorded under. The flip
            #: changes the release schedule of every direct run, and without
            #: this block a post-profile store is indistinguishable from a
            #: pre-profile one by its own metadata (the P41 `physics` rationale,
            #: `defaulted` following P43's `arm_park.defaulted`).
            "supply": {
                "cadence": bool(self._supply["cadence"]),
                "band_interlock": bool(self._supply["band_interlock"]),
                "band_max": self._supply["band_max"],
                "target_from": self._supply["target_from"],
                "direct_feed": bool(self._direct_feed),
                "continuous": int(self._continuous_picks),
                "defaulted": dict(self._supply["defaulted"]),
            },
            "sources": sources,
        }

    def _physics_provenance(self) -> dict:
        """The manifest's `physics` block, with the runtime finger-drive read-back.

        Kept as a method so a failure cannot take the manifest (or the run)
        down: the collector's builder raises nothing by design, but an env that
        cannot read its own articulation is a reported state, not a crash.

        `two_line=False` (P87): this env never runs a `CoopSession`, so its
        release clock is the shipped one unless `FRUIT_SPEED_RELEASE` /
        `FRUIT_SPEED_ALL` says otherwise - the block records which. The scope
        argument is the same predicate `_grasp_carry_place_impl` passes to
        `speed_cell_defaults`, so the store and the run cannot disagree.
        """
        try:
            from .scene import finger_physics_provenance

            return finger_physics_provenance(
                arms=self.task.arms, scope=self._finger_cap_scope, two_line=False
            )
        except Exception as exc:  # noqa: BLE001 - provenance must not stop a run
            return {"finger_drive": {"source": "error", "why": str(exc)}}

    def _scene_provenance(self) -> dict:
        """The manifest's `scene` block (P72): the collider set this run was in.

        Same builder the collector's shards call (`assets.scene_provenance`), so
        a direct rollout store and a collector shard name their rail pair, the
        output slab's top z / inboard edge and the lift rung the same way. P71
        moved both rails and the lift default; without this block a pre-P71
        store is distinguishable only by an `assets.py` md5 that also moves for
        unrelated edits (`logs/p71/RESULTS.md` section 5's named gap). The full
        lift resolution stays in the `lift_dz` block; the copy here keeps
        `scene` readable on its own.
        """
        try:
            from .assets import scene_provenance

            return scene_provenance(
                self.cfg,
                lift_dz=self._lift_dz,
                lift_dz_defaulted=self._lift_dz_defaulted,
            )
        except Exception as exc:  # noqa: BLE001 - provenance must not stop a run
            return {"why": str(exc)}

    def _write_manifest(self) -> None:
        assert self.run_dir is not None
        self.manifest_path = os.path.join(self.run_dir, "manifest.json")
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump(self._manifest_base, fh, indent=2, sort_keys=True)
        self._say(f"[rl] manifest -> {self.manifest_path} "
                  f"(reward={json.dumps(self._manifest_base['reward'])})")

    # ------------------------------------------------------------------ #
    # Stepping
    # ------------------------------------------------------------------ #
    @staticmethod
    def _resolve_supply_profile(direct: bool) -> dict:
        """P58: the direct presentation's supply profile, resolved once.

        Four knobs, one mechanism - the release clock must run on the task's
        primitive ticks (`FRUIT_FEED_CADENCE` -> `PickAndPlaceTask`) and on the
        policy phase's `advance` (`FRUIT_DIRECT_FEED`), and the interlock must
        pace the **approach band** rather than the station window
        (`FRUIT_SUPPLY_BAND_INTERLOCK`, cap `FRUIT_SUPPLY_BAND_MAX`). All four
        default **on for `direct` only**; an explicit environment value wins, so
        `FRUIT_FEED_CADENCE=0 FRUIT_SUPPLY_BAND_INTERLOCK=0 FRUIT_DIRECT_FEED=0`
        reproduces every pre-P58 direct number. The profile is passed to the
        spawner/task as keyword arguments (`None` there = the shipped env read),
        never by mutating the process environment, so the scripted line and the
        two-line scheduler stay byte-identical (`logs/p58/A_RESULTS.md` P3:
        `accept.sh` 377/377 identical + `fingerprint: matches`).
        """
        def _flag(name: str, default: bool) -> tuple[bool, bool]:
            raw = os.environ.get(name)
            return (default, True) if raw is None else (raw == "1", False)

        cadence, cad_defaulted = _flag("FRUIT_FEED_CADENCE", direct)
        band, band_defaulted = _flag("FRUIT_SUPPLY_BAND_INTERLOCK", direct)
        feed, feed_defaulted = _flag("FRUIT_DIRECT_FEED", direct)
        raw_max = os.environ.get("FRUIT_SUPPLY_BAND_MAX")
        if raw_max is not None:
            band_max = max(1, int(raw_max))
        else:
            band_max = 4 if direct else None
        #: The band's upstream edge (`_approach_depth`): not flipped, but it
        #: moves the interlock's window, so phase 2's arm B must be attributable
        #: from the artefacts - P59 gate 1 (Oracle) found it in neither the row
        #: nor the manifest.
        raw_from = os.environ.get("FRUIT_SUPPLY_TARGET_FROM")
        target_from = float(raw_from) if raw_from is not None else 0.35
        return {
            "cadence": bool(cadence) and direct,
            "band_interlock": bool(band) and direct,
            "band_max": band_max if direct else None,
            "feed": bool(feed) and direct,
            "target_from": target_from,
            "defaulted": {
                "cadence": cad_defaulted,
                "band_interlock": band_defaulted,
                "band_max": raw_max is None,
                "feed": feed_defaulted,
                "target_from": raw_from is None,
            },
        }

    @staticmethod
    def _supply_profile_row(profile: dict, direct_feed: bool) -> str:
        """The `[supply] direct profile:` row (pure; pinned by `230`).

        Each member names its **own** provenance, and the band's cap is printed
        **only when the interlock is on** - P59 gate 1 found that the cap was
        labelled from the interlock's `defaulted` flag, so a phase-2 arm with
        `FRUIT_SUPPLY_BAND_MAX=5` explicit would have read
        `band=on(5)(default)`, i.e. indistinguishable from the shipped default
        on the very instrument that answers "is the profile what runs?". The
        three cases are pinned in `scripts/230_p58_supply_selftest.py`:

        * shipped (interlock default on, cap 4 default) - `band=on(4)(default)`
          (byte-identical to the P58 row, so every P58/P59 log stays valid);
        * the pre-P58 recipe (interlock explicit off) - `band=off(explicit)`
          (the misleading `(4)` is gone);
        * a cap override (interlock default, cap explicit) -
          `band=on(5(explicit))(default)`.
        """
        d = profile["defaulted"]

        def mark(key: str) -> str:
            return "(default)" if d.get(key) else "(explicit)"

        if profile["band_interlock"]:
            cap = f"({profile['band_max']}{'' if d.get('band_max') else '(explicit)'})"
        else:
            cap = ""
        return (
            "[supply] direct profile: "
            f"cadence={'on' if profile['cadence'] else 'off'}{mark('cadence')} "
            f"band={'on' if profile['band_interlock'] else 'off'}{cap}"
            f"{mark('band_interlock')} "
            f"feed={'on' if direct_feed else 'off'}{mark('feed')} "
            f"target_from={profile['target_from']:.2f}{mark('target_from')}"
        )

    @staticmethod
    def _grasp_override_row(override: dict, waypoints: dict, hand_axis: str) -> str:
        """The `[grasp] left attitude override:` row (pure; pinned by `232`).

        P62 phase 2. Printed **only when the knob is armed**, so every knob-off
        log (and the scripted acceptance, which never constructs this env) is
        byte-unchanged. The row reports:

        * the resolved **override** for the left arm and its belt projection;
        * the **file**'s left value (`waypoints["grasp_quaternion"]["left"]`) and
          its belt projection;
        * the hold the **never-stop catch** installs before the descent - 
          `top_down_quaternion(FRUIT_HAND_AXIS)`, mirrored for the left
          (`tasks._run_impl`), which *replaces* `_grasp_quat`'s value;
        * the right arm, unchanged, and its projection.

        `file_same` and `hold_same` are the two equalities that decide whether
        the knob can move the mechanism at all: if the override equals the file's
        value *and* equals the dynamic hold, the armed run commands exactly what
        the shipped run commands and the cell is a structural null.
        """
        file_q = (waypoints.get("grasp_quaternion") or {}).get("left")
        file_q = None if file_q is None else np.asarray(file_q, dtype=float)
        hold_q = mirror_across_xz(top_down_quaternion(hand_axis))
        right_q = (waypoints.get("grasp_quaternion") or {}).get("right")

        def fmt(q) -> str:
            if q is None:
                return "none"
            return "[" + ",".join(f"{float(v):+.6f}" for v in q) + "]"

        def same(a, b) -> str:
            if a is None or b is None:
                return "n/a"
            return "1" if float(np.max(np.abs(np.asarray(a) - np.asarray(b)))) < 1e-6 else "0"

        left_q = override.get("left")
        return (
            "[grasp] left attitude override: "
            f"q={fmt(left_q)} (w,x,y,z) belt_proj={_tool_belt_proj(left_q):+.4f} | "
            f"file={fmt(file_q)} belt_proj="
            f"{'n/a' if file_q is None else f'{_tool_belt_proj(file_q):+.4f}'} "
            f"file_same={same(left_q, file_q)} | "
            f"dynamic_hold={fmt(hold_q)} (top_down FRUIT_HAND_AXIS={hand_axis}, "
            f"mirrored for the left) belt_proj={_tool_belt_proj(hold_q):+.4f} "
            f"hold_same={same(left_q, hold_q)} | "
            f"right=file {fmt(right_q)} belt_proj="
            f"{'n/a' if right_q is None else f'{_tool_belt_proj(right_q):+.4f}'}"
        )

    @staticmethod
    def _precomp_row(override: dict) -> str:
        """The `[grasp] left precomp:` row (pure; pinned by `234`).

        P64 phase 1, printed **only when the knob is armed**, so the control arm
        (and every scripted path, which never constructs this env) prints
        nothing. It names what the run commands and what that is predicted to
        achieve:

        * the **drift** inverted: axis and angle (the measured median) and the
          per-leg spread it was taken over;
        * the resulting **command** `q_cmd = q_drift^-1 (x) q_T0`, its belt
          projection (the command is tilted *upstream* by the drift angle) and
          the **predicted achieved** projection - computed by applying
          `q_drift` to `q_cmd`, i.e. the registered model `q_ach = q_drift (x)
          q_cmd`, so the row proves the arithmetic rather than asserting a 0;
        * the scope: one leg (`grasp_lift`), one arm (left), the right shipped.
        """
        q_cmd = override.get("left")
        q_cmd = np.asarray(q_cmd, dtype=float)
        q_drift = _quat_from_axis_angle(
            P64_LEFT_DRIFT_AXIS, P64_LEFT_DRIFT_ANGLE_DEG
        )
        predicted = _quat_mul(q_drift, q_cmd)
        return (
            "[grasp] left precomp: "
            f"q_cmd=[{','.join(f'{float(v):+.6f}' for v in q_cmd)}] (w,x,y,z) "
            f"axis=({P64_LEFT_DRIFT_AXIS[0]:+.6f},{P64_LEFT_DRIFT_AXIS[1]:+.6f},"
            f"{P64_LEFT_DRIFT_AXIS[2]:+.6f}) angle={P64_LEFT_DRIFT_ANGLE_DEG:.3f}deg "
            f"cmd_belt_proj={_tool_belt_proj(q_cmd):+.4f} "
            f"predicted_proj={_tool_belt_proj(predicted):+.4f} | "
            "leg=grasp_lift (hold written at the leg start; the grip is the "
            "shipped attitude), side=left (right=shipped) | "
            "source=median of 7 left grasp_lift legs (P63 A1_77 + P62 P0/P0b), "
            "per-leg tilt 25.1..28.7deg, achieved proj +0.3210..+0.3658"
        )

    @staticmethod
    def _lift_dz_row(offsets: dict, belt_top: float, defaulted: bool = False) -> str:
        """The `[grasp] lift_dz:` row (pure; pinned by `236`).

        P66 phase 2/3. Since the phase-3 flip it prints on **every `direct`**
        run (the offset is the presentation's default there) and never on a
        scripted path (they do not construct this env, so `offsets` is `None`).
        It names the resolved offset **with its origin** - `(default)` = the
        P66 phase-3 `direct` default, `(explicit)` = `FRUIT_LIFT_DZ` was set,
        the `park=back(default)` pattern - the height it puts the lift's end at,
        and the documented **restore** (`+0.08` = the hand's own add = the
        shipped 0.36 m), all rebuilt from the numbers
        `tasks.jaw_target("grasp_lift")` itself uses: the offset is measured
        above the `belt_top + 0.28` base and **replaces** the hand's
        `FRUIT_OPENARM_TRANSFER_LIFT` add, so `+0.08` is the shipped height and
        `-0.08` the 0.20 m rung. A log therefore proves which rung it ran rather
        than asserting the cell's table, and its origin says whether a flip
        could have caused it.
        """
        dz = float(offsets.get("left", 0.0))
        origin = "default" if defaulted else "explicit"
        hand = 0.28 + float(os.environ.get("FRUIT_OPENARM_TRANSFER_LIFT", "0.08"))
        return (
            "[grasp] lift_dz: "
            f"dz={dz:+.4f}({origin}) m above the 0.28 base "
            f"-> {belt_top + 0.28 + dz:.4f} m above floor "
            f"(belt_top {belt_top:.4f} + {0.28 + dz:.4f}) | "
            "arm=left leg=grasp_lift (right=shipped, place legs=shipped) | "
            f"default dz={LIFT_DZ_DIRECT_DEFAULT:+.4f} = "
            f"{0.28 + LIFT_DZ_DIRECT_DEFAULT:.4f} m; "
            f"restore the shipped {belt_top + hand:.4f} m with "
            "FRUIT_LIFT_DZ=+0.0800 (the hand's own add)"
        )

    @staticmethod
    def _lift_climb_row(climb: dict, belt_top: float, cfg, lift_dz: dict | None) -> str:
        """The `[grasp] lift_climb:` row (pure; pinned by `237`).

        P67. Names the resolved climb, its scope, the two heights the re-shape
        moves (the place transit's **start** and, through the leg's own straight
        line, the **crossing**), and the documented restore. Rebuilt from the
        numbers `tasks.jaw_target` builds and the scene's own geometry, not from
        the cell's table:

        * the lift's end is `belt_top + 0.28 + dz` (`dz` = the resolved
          `FRUIT_LIFT_DZ`, i.e. the `[grasp] lift_dz:` row's own value);
        * the transfer pose is `output_place_z + the hand's add`;
        * the crossing fraction is `rail centreline / |place y|` - the same
          derivation `tasks._output_rail_y` uses for the rail (a 0.025 m thick
          rail at `output_belt_y - (size/2 + 0.0125)`, so its centreline is at
          `|output_belt_y| - size/2 - 0.0125`), against the drop point's `|y|`.

        With a climb the transit is a straight line from `lift_end + climb` to
        the transfer, so
        `z_crossing = transfer - (1 - f) * (transfer - lift_end - climb)`. The
        row prints that value and its rise over the same arm without the climb,
        which is the point: the transit's **start** moves 1:1 with the climb,
        the **crossing** only `(1 - f) = 0.175:1`.
        """
        c = float(climb.get("left", 0.0))
        hand = float(os.environ.get("FRUIT_OPENARM_TRANSFER_LIFT", "0.08"))
        dz = float((lift_dz or {}).get("left", LIFT_DZ_HAND_ADD))
        lift_end = belt_top + 0.28 + dz
        transfer = float(cfg.output_place_z) + hand
        rail_centre = abs(float(cfg.output_belt_y)) - (
            float(cfg.output_belt_size[1]) / 2.0 + 0.0125
        )
        place_y = abs(float(cfg.output_belt_drop_points[0][1]))
        f = rail_centre / place_y
        start = lift_end + c
        cross = transfer - (1.0 - f) * (transfer - start)
        cross_no = transfer - (1.0 - f) * (transfer - lift_end)
        return (
            "[grasp] lift_climb: "
            f"climb={c:+.4f}(explicit) m, arm=left legs=place0,place1 | "
            f"lift end {lift_end:.4f} -> transit start {start:.4f} m "
            f"(+{c * 1000:.1f} mm at 1:1) | transfer {transfer:.4f} m | "
            f"crossing |y|={rail_centre:.4f} of the {place_y:.4f} m span "
            f"(f={f:.3f}) -> z_crossing {cross:.4f} m "
            f"({(cross - cross_no) * 1000:+.1f} mm vs no climb) | "
            "restore the shipped place leg by leaving FRUIT_LIFT_CLIMB unset"
        )

    def advance(self, steps: int) -> None:
        """Tick-exact physics advance + callback pump.

        Same rule as `60_eval_policy.advance` and `40_collect_demos.advance`:
        `SimulationManager.step` is the fixed step, `update_app(steps=0)` only
        services the camera/sensor callbacks. Never `update_app(steps=N)`.
        """
        self._SimulationManager.step(steps=int(steps))
        self._app_utils.update_app(steps=0)
        if self._direct_feed:
            # P55: the live feeder. The direct interface's supply used to be
            # built once per `reset` and then frozen for the whole episode (the
            # only `spawner.update` site was the reset's target-selection loop,
            # which is why the belt drains and the fruit arrives in one burst per
            # episode). With `FRUIT_DIRECT_FEED=1` the spawner's own absolute
            # schedule runs every advance, so the belt stays stocked and the
            # policy works back-to-back. Default off: unset is byte-identical.
            if not self._direct_feed_refreshed:
                # One-shot: the direct pool can gain samples after the env's
                # setup refresh (the reset path re-creates/recycles), and the
                # spawner's `_pick_recyclable` indexes `_rigids` by sample index.
                self._direct_feed_refreshed = True
                self.spawner.refresh_rigids()
            try:
                self.spawner.update(self._sim_time())
            except KeyError:
                # The direct pool can hold a sample whose rigid is not in the
                # spawner's `_rigids` (the recycle path in `_pick_recyclable`
                # assumes every sample has one); the transport still has to be
                # enforced, and the release pump is skipped for this tick.
                if not self._direct_feed_warned:
                    self._direct_feed_warned = True
                    print(
                        "[rl] FRUIT_DIRECT_FEED: the spawner's recycle path hit a "
                        "sample without a rigid; the release pump is skipped for "
                        "that tick (transport still enforced)",
                        flush=True,
                    )
            self.spawner.enforce_transport()

    # ------------------------------------------------------------------ #
    # Episode setup
    # ------------------------------------------------------------------ #
    def reset(self, seed: int | None = None) -> dict:
        """Start the next episode. Returns a light observation snapshot.

        The first episode of a run passes `seed` (the spawner seed); later
        episodes call `reset()` so the fruit sequence continues rather than
        restarting from the same RNG state every time.
        """
        if self._loop_timing:
            # P43 L2: the episode wall starts at the reset (setup included) and
            # is closed in `_finalize`, so the per-episode wall below is the
            # whole episode including selection and setup.
            self._loop_reset_start = time.perf_counter()
            self._loop_t = {"policy_ms": 0.0, "render_ms": 0.0, "camera_ms": 0.0}
            self._loop_counts = {"observations": 0, "decisions": 0}
        if self._recorder is not None and self._recorder.recording:
            # An episode that is reset without reaching `_finalize` (the driver
            # grew impatient) must not leak a half file into the index.
            self._recorder.abort()
        if seed is not None:
            seed = int(seed)
            if seed != self._active_seed:
                self.spawner.rng.seed(seed)
                self._active_seed = seed
                self.seed = seed
        # P56: a new **logical** episode. The multi-pick counters start here and
        # are cleared only by this method - never by `_begin_pick`, which a
        # continuous episode calls *n* times.
        self._picks_done = 0
        self._cont_reward = 0.0
        self._cont_ticks = 0
        self._cont_placed = 0
        self._cont_gaps = []
        self._pick_boundary = False

        # Target selection. `handoff` uses the hybrid evaluator's window (the
        # teleport makes distance harmless); `direct` uses the *scripted line's*
        # selector, which is how demos_v7 was collected: a fruit already at the
        # station first (`pick_y`+0.02..0.18 with the pre-pose lead), and only
        # then the closest fruit upstream. Selecting far upstream gives the
        # policy an 11 s walk for a 12.5 s budget, which is a different task
        # from the one it was trained on.
        rounds = 0
        target_state: dict | None = None
        diag: list | None = None
        while True:
            for _ in range(30):
                self.advance(1)
                self.spawner.update(self._sim_time())
                self.spawner.enforce_transport()
            # P56: the refusal census (`FRUIT_BED_DIAG=1`) is *reporting*; one fresh
            # list per round (a 41-round starvation loop must not stack rows), and
            # `_begin_pick` prints it before the teleports.
            diag = [] if self._bed_diag else None
            if self.presentation == "handoff":
                states = [
                    s for s in self.spawner.state()
                    if s["diameter"] <= self.cfg.gripper_max_object
                ]
                states = [
                    s for s in states
                    if abs(float(s["position"][0]) - self.cfg.belt_center[0]) < 0.30
                    and self.cfg.pick_y + 0.15 < float(s["position"][1])
                    < self.cfg.spawn_y + 0.05
                ]
                target_state = min(states, key=lambda s: float(s["position"][1])) if states else None
            else:
                # R11-A scope: the direct/policy interface keeps the shipped
                # (station-fixed) selector explicitly - its measured history
                # (the demos stores and the W4/W7-B/W8-A/W9/R6-B/R9 direct
                # A/Bs) lives on it, while the reach-anywhere catch (the
                # R10-A/R11-A candidate; opt-in) is scoped to the scripted
                # line (`logs/r11/A_RESULTS.md`). The scripted loop, the
                # collector and the bimanual workers leave `select_target`'s
                # default and inherit it.
                #
                # P43 L1 scope (`direct=True`): the same applies to the
                # nearest-above-floor rule, whose scripted default is **on**
                # (`tasks.py` `select_target`). This call is the direct
                # environment's episode selection - the one unlaned caller of
                # the single-arm branch - so it resolves the rule off and the
                # shipped farthest-upstream pick stays byte-identical. An
                # explicit `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` wins either way.
                target_state = self.task.select_target(
                    self.spawner.state(), reach_anywhere=False, direct=True,
                    diag=diag,
                )
            if target_state is not None or rounds >= 40:
                break
            rounds += 1
        if target_state is None:
            raise RuntimeError(
                "no graspable fruit reached the selection window in 40 feed rounds"
            )
        return self._begin_pick(target_state, diag=diag)

    def _begin_pick(self, target_state: dict, diag: list | None = None,
                    continuation: bool = False, prev_active: str | None = None) -> dict:
        """Start one pick from an already-selected target (P56).

        Factored out of `reset`: everything here is per pick (the episode index,
        the target bookkeeping, the `grasp` teleport + settle, the trigger
        station, the per-episode counters and `policy.reset()`), while `reset`
        keeps the run-level half (the loop timer, the recorder abort, the RNG
        seeding and the feed/selection loop). On the shipped per-episode path the
        body is the code that used to sit in `reset`, unchanged (proven
        byte-identical by `logs/p56/p0/base_{before,after}.sh`).

        `continuation=True` (only `FRUIT_DIRECT_CONTINUOUS`) reduces the setup to
        DESIGN A.1 row 7's "partly": the active arm skips its redundant `ready`
        teleport (the `grasp` teleport overwrites it) and the inactive arm is
        re-parked only when the pick switches arms - 50 ticks instead of 110.
        """
        self._episode += 1
        self._pick_boundary = False
        #: `StepResult.reward` reads `_outcome`; a new pick must not inherit the
        #: previous pick's value (in the per-episode loop the reset always ran
        #: between them, and nothing consumed it - here a consumer would).
        self._outcome = None
        if diag is not None:
            # P56: the same block the scripted driver prints after its selection
            # (`scripts/20_pick_place.py`), so the belt stock at every pick is
            # readable from the log (`window` = candidates at/above the catch
            # floor). Printed before the teleports: the numbers describe the
            # selection instant.
            self.task.bed_diag_report(self._episode, diag)
        target = target_state
        sample = next(s for s in self.spawner.samples if s.index == target["index"])
        grade = target["grade"]
        bin_index = 0 if grade == "A" else 1
        active = "left" if bin_index == 0 else "right"

        self._sample = sample
        self._active = active
        self._bin_index = bin_index
        self._goal = np.array(
            [
                *np.asarray(target["position"], dtype=np.float32),
                *np.asarray(target["velocity"], dtype=np.float32),
                float(target["diameter"]),
                float(bin_index),
            ],
            dtype=np.float32,
        )
        self._belt_rest = self.belt_top + float(target["diameter"]) / 2.0

        # Start state. Every `demos_v7` episode begins when the scripted pick
        # reaches its *wait loop*: the pre-pose before it is not recorded, so the
        # first frame of every demonstration already has the arm at the calibrated
        # grasp pose (measured: |q-grasp| <= 0.011 rad at frame 0, and no demo
        # frame ever comes closer than 0.220 rad to the ready pose). `handoff`
        # still reproduces the hybrid evaluator (ready pose + station hand-off);
        # `direct` is the causal interface and must start where the training
        # distribution starts, or the policy's very first observation is a state
        # it has never seen. Both arms are parked at ready first, like
        # `go_ready()` does before every collected episode, so the inactive arm is
        # not left wherever the previous carry dropped it.
        arm = self.task.arms[active]
        if self.presentation == "direct":
            # P56 continuation: the per-pick setup is reduced to what the demos'
            # frame 0 actually needs (DESIGN section 1 A.1 row 7, "partly").
            # (a) The active arm's teleport to `ready` in the loop below is
            #     immediately overwritten by its `grasp` teleport, so on a
            #     continuation it is skipped - one settle, not two.
            # (b) The inactive arm is re-parked only when this pick **switches**
            #     arms: an arm that just carried is where the park put it, and
            #     re-teleporting it costs 30 ticks of belt travel for nothing.
            # Both are continuation-only, so the shipped per-episode reset is
            # byte-unchanged (the `[grasp]` row's `q_err_max` is what checks that
            # the reduced setup still lands on the demos' start pose - PREREG P6).
            switched = continuation and prev_active is not None and prev_active != active
            for name, other in self.task.arms.items():
                other.set_gripper(other.OPEN)
                if name == active and continuation:
                    continue
                if name != active and continuation and not switched:
                    continue
                # P35: the *inactive* arm only - the active one is teleported to
                # its `grasp` right below, and a second park teleport would add a
                # settle's worth of belt travel to the reset. An unset
                # `FRUIT_ARM_PARK` leaves the shipped `ready` call unchanged
                # (`_arm_park_poses` is empty).
                park = None if name == active else self._arm_park_poses.get(name)
                other.teleport_joints(
                    np.asarray(self.waypoints["arms"][name]["ready"], dtype=float)
                    if park is None
                    else park
                )
            start = np.asarray(self.waypoints["arms"][active]["grasp"], dtype=float)
        else:
            start = np.asarray(self.waypoints["arms"][active]["ready"], dtype=float)
        arm.teleport_joints(start)
        # `teleport_joints` writes the *measured* dof state back through the
        # drive, and Isaac re-targets from it, so the `set_gripper(OPEN)` in the
        # parking loop does not survive: the first observation then carried all
        # four finger joints at 0.000 where every recorded wait frame has them
        # at 0.044. The policy reads those channels as its wait/close phase cue
        # (measured: with them closed the first chunk executes the close/track
        # phase, and with them open it holds the grasp pose), so start the
        # episode with both grippers open, measured and commanded, exactly like
        # the demonstrations' frame 0.
        gripper_open = float(arm.OPEN)
        dof = np.asarray(self.scene.robot.get_dof_positions().numpy())[0].copy()
        for other in self.task.arms.values():
            dof[list(other.finger_dofs)] = gripper_open
        self.scene.robot.set_dof_positions(dof)
        for other in self.task.arms.values():
            other.set_gripper(gripper_open)
        self.advance(self._reset_settle)
        #: Pick-station jaw line the scripted tracking window is measured against
        #: (`_run_impl` reads it after its pre-pose, at the same pose).
        self._expert_jaw_y = float(arm.jaw_centre()[1])
        #: Nominal close zone captured at reset: the jaw centre at the calibrated
        #: grasp pose. The intercept trigger can time the fruit's arrival against
        #: this point instead of the current jaw, which is robust to the policy's
        #: own slow arm drift over the long wait (`FRUIT_POLICY_TRIGGER_FRAME`).
        self._trigger_station = np.asarray(arm.jaw_centre()[:2], dtype=float).copy()
        if self._grasp_diag:
            # P56 P6: the pick's start state against the demos' frame-0 pose. Read
            # after the settle (the last pose change before the first observation),
            # so it is the state the policy's first chunk conditions on.
            self._grasp_err = float(
                np.abs(
                    np.asarray(arm.joint_positions(), dtype=float)
                    - np.asarray(start, dtype=float)
                ).max()
            )
        else:
            self._grasp_err = float("nan")
        if self.spawner.belt is not None:
            self.spawner.belt.start()
        # P34-B: the active arm's pose at the reset return (diag only; one
        # articulation read, never on the shipped path).
        q_reset = [float(v) for v in arm.joint_positions()] if self._align_diag else []
        # P35 phase 2 (Gate-1 P0): the pose the reset **achieved** for every arm,
        # read after the reset's own settle. The park's M1 is measured against
        # this, not against the commanded vector: `teleport_joints` writes the
        # pose, steps 30 substeps and then re-bases the drive onto the measured
        # state, so a 0.5 rad j1 move is *held* 0.09-0.10 rad short of its
        # command - and the shipped `ready` pose is 0.027-0.038 short of its own.
        # Diag only: two articulation reads per episode.
        if self._park_diag:
            self._park_settled = {
                name: np.asarray(other.joint_positions(), dtype=float)
                for name, other in self.task.arms.items()
            }
        else:
            self._park_settled = {}
        # P34 phase 2: put the first *model call* at the demos' first view
        # (default off; one False branch and no read on the shipped path).
        # The advance is physics-only and happens before `_episode_t0`, so the
        # attempt's own span excludes it.
        if self._reset_align:
            self._align_presentation()

        if self.policy is not None:
            self.policy.reset()
        if self.rtc is not None:
            self.rtc.reset()

        self._tick = 0
        self._step = 0
        self._observed_step = -1
        #: P36 phase 1: per-episode spoof reporting state (diag only).
        self._spoof_calls = 0
        self._spoof_drift = float("nan")
        self._spoof_first = None
        self._last_rgb = None
        self._last_depth = None
        self._last_mask = None
        self._done = False
        self._triggered = False
        self._handoff_done = False
        self._grasp_done = False
        self._lifted = False
        self._grasped = False
        self._placed = False
        self._notes: list[str] = []
        #: R2.3 reach-cliff guard bookkeeping: fruit indices already reported as
        #: x-edge refusals this episode (the note must not repeat per tick).
        self._x_refused: set[int] = set()
        #: R7-A (WS-4.6): fruit indices whose *policy-gate* fire the same
        #: guard refused (one note per fruit; see `_note_gate_refuse`).
        self._gate_refused: set[int] = set()
        #: P38 phase 2: the lateral-refusal harness state for this episode (all
        #: four knobs off -> every branch below is a `False` short-circuit).
        self._refuse_latch = None
        self._refuse_count = 0
        self._refuse_indices = set()
        self._policy_close_seen = False
        self._policy_best_gap = float("inf")
        self._reseed_left = int(self._reseed_max)
        self._reseed_adopted = 0
        self._reseed_scans = 0
        self._reseed_seen = set()
        self._reseed_scans_left = 0
        self._reseed_next_tick = 0
        self._reseed_empty = 0
        self._reseed_off = 0
        self._reseed_exhausted_noted = False
        self._no_firable = False
        self._last_action = np.zeros(self.action_dim, dtype=np.float32)
        self._episode_t0 = self._sim_time()
        self._decision_step: int | None = None
        self.spawner.protected = int(target["index"])
        # P30-B: no model has run for this episode yet (a scripted-ablation
        # episode, or one that ends before the primitive, must not inherit the
        # previous episode's count).
        self.task.policy_inference_calls = None
        # RTC report buffers for this episode (empty and unused when off).
        self._report_boundary: list[float] = []
        self._report_within: list[float] = []
        self._report_step: list[float] = []
        self._report_jerk: list[float] = []
        self._report_control_ms: list[float] = []
        self._report_policy_ms: list[float] = []
        self._report_decisions = 0
        self._infer_calls = 0
        # P31-A: the wait gate's per-episode counters (the outcome keys and the
        # `[gate]` row read them; they are written above only when the gate is on).
        self._wait_gate_skipped = 0
        self._wait_gate_held = 0
        self._wait_gate_hold_chunk = False
        self._wait_gate_open = False
        self._wait_gate_resumed = False
        self._wait_gate_along0 = float("nan")
        self._last7: np.ndarray | None = None
        self._prev7: np.ndarray | None = None
        self._switch_flag = False
        self._pending_switch = False
        self._applied_any = False
        # Event-triggered replanning state for this episode (empty when off).
        self._prev_chunk: np.ndarray | None = None
        self._prev_exec = 0
        self._event_continuities: list[float] = []
        self._event_horizons: list[int] = []
        # P52 phase 2: the contact gate's per-episode bookkeeping (written only
        # when the time-scale knobs are armed; the shipped path leaves them at
        # these values and never reads them).
        self._retime_calls = 0
        self._retime_gated = 0
        self._retime_decisions = 0
        self._retime_gated_decisions = 0
        self._retime_force_gated = 0
        self._retime_finger_gated = 0
        self._retime_force_max = 0.0
        self._retime_force_live = 0.0
        self._retime_finger_live = 0.0
        # P53: the `[emit]` row's per-episode counters (zero-cost unless
        # `FRUIT_EMIT_DIAG=1`: the shipped path never increments them).
        self._emit_ticks = 0
        self._emit_decisions = 0
        self._emit_pre_out = 0
        self._emit_post_out = 0
        self._emit_pre_max = 0.0
        self._emit_clamped_ticks = 0
        # DAgger bookkeeping for this episode (the expert label buffer starts
        # empty; `_observe`/`_record_tick` fill it at the decision points).
        self._expert_until = -1
        self._expert_close_start = None
        self._expert_label = None
        self._expert_grasp = np.asarray(
            self.waypoints["arms"][active]["grasp"], dtype=np.float32
        ).copy()
        self._policy_proposal = None
        self._ep_interventions = 0
        self._ep_expert_ticks = 0
        # P35 phase 2: the per-call park check's episode state (the `[park]` row
        # is printed only when `FRUIT_PARK_DIAG=1`; off, this is one False
        # branch and no writes).
        if self._park_diag:
            self._park_q_settled = []
            self._park_m1_hold = float("nan")
            self._park_m1_cmd = float("nan")
            self._park_q_first = []
            self._park_q_band = []
            self._park_band_along = float("nan")
            self._park_band_x = float("nan")
            self._park_band_px = -1
            self._park_band_disc = -1.0
            self._park_band_vis = -1.0
            self._park_band_arm = -1
            self._park_band_top = ""
            self._park_pxc_max = -1.0
            self._park_band_calls = 0
            self._park_stale_skipped = 0
            self._park_worst_arm = -1.0
            self._park_worst_arm_along = float("nan")
            self._park_worst_vis = -1.0
            self._park_worst_vis_along = float("nan")
            self._park_worst_top = ""
            self._park_min_frac = -1.0
            self._park_max_frac = -1.0
            self._park_min_frac_along = float("nan")
            self._park_max_frac_along = float("nan")
            self._park_min_rel = -1.0
            self._park_min_rel_along = float("nan")
            self._last_seg = None
            self._last_seg_labels = {}
        # P34 phase 2: per-episode diagnostic state (one False branch on the
        # shipped path; the `[align]` row is printed only when `_align_diag`).
        if self._align_diag:
            self._align_y0 = float(target["position"][1])
            if not self._reset_align:
                # The control arm: report the along at the same point the
                # aligned arm leaves the presentation (one fruit-pose read;
                # diagnostic only, never on a rate run with the diag off).
                self._align_along_reset = self._wait_gate_along()
                self._align_steps = 0
            self._align_first_along = float("nan")
            self._align_first_x = float("nan")
            self._align_first_d = float(sample.diameter)
            self._align_first_px = -1
            self._align_first_visible = -1
            self._align_hidden_calls = 0
            self._align_q_reset = list(q_reset)
            self._align_q_first = []
            self._align_px_max = -1
            self._align_pxc_first = -1.0
            self._align_pxc_max = -1.0
            self._align_zone_n = 0
            self._align_zone_zero = 0
            self._align_zone_px = []

        if self._grasp_diag:
            # P56 P6 + P1's cross-check: the start pose error and the pick's own
            # clock start. `t0` is `_episode_t0` (after the per-pick setup), so a
            # gap is `t0(k+1) - t0(k) - ticks(k)` for **either** arm.
            self._say(
                f"[grasp] episode {self._episode} "
                f"pick={self._picks_done + 1}/"
                f"{self._continuous_picks or 1} arm={active} "
                f"t0={self._episode_t0:.4f} q_err_max={self._grasp_err:.4f}"
            )
        self._say(
            f"[rl] episode {self._episode}: {target['category']} grade={grade} "
            f"d={target['diameter'] * 100:.1f}cm bin={bin_index} arm={active} "
            f"y={float(target['position'][1]):+.3f} presentation={self.presentation}"
        )
        if self._recorder is not None:
            self._recorder.begin(
                {
                    "index": self._episode,
                    "category": sample.category,
                    "grade": sample.grade,
                    "arm": active,
                    "bin_index": bin_index,
                    "diameter": sample.diameter,
                    "presentation": self.presentation,
                    "ablate": self.ablate,
                    "seed": self._active_seed,
                }
            )
        # Frame 0, so `policy.ready` becomes true after the first window fills.
        self._observe()
        return self._obs_snapshot()

    # ------------------------------------------------------------------ #
    # Observation
    # ------------------------------------------------------------------ #
    def _observe(self) -> None:
        """Render and read the head camera once per observation tick."""
        if self._observed_step == self._step:
            return
        self._observed_step = self._step
        if self.policy is None and self._recorder is None:
            return
        _t0 = time.perf_counter() if self._loop_timing else 0.0
        self._RenderingManager.render()
        if self._loop_timing:
            # P43 L2: the render stage of the decision period.
            self._loop_t["render_ms"] += (time.perf_counter() - _t0) * 1e3
            self._t_camera = time.perf_counter()
        raw_rgb = self.scene.camera_sensor.get_data("rgb")
        raw_depth = self.scene.camera_sensor.get_data("distance_to_image_plane")
        rgb = np.asarray(raw_rgb[0].numpy()) if raw_rgb is not None else None
        depth = np.asarray(raw_depth[0].numpy()) if raw_depth is not None else None
        mask = None
        if rgb is not None and depth is not None:
            # P35 phase 2: `_park_diag` retains the segmentation frame it reads
            # for the per-call park check. With `image_channels == 5` (the
            # shipped policy) that read already happens, so the diag adds no
            # sensor read on the A/B path; when the mask is not part of the
            # observation the diag *does* read the segmentation (reporting
            # only - `push_frame` still gets the same `None`).
            if (self._image_channels == 5 or self._recorder is not None
                    or self._park_diag):
                raw = self.scene.camera_sensor.get_data("instance_id_segmentation")
                seg = np.asarray(raw[0].numpy()) if raw is not None else None
                labels: dict = {}
                if seg is not None:
                    if seg.ndim == 3:
                        seg = seg[..., 0]
                    info = raw[1] if isinstance(raw, tuple) and len(raw) > 1 else {}
                    labels = info.get("idToLabels", {}) if isinstance(info, dict) else {}
                if self._park_diag:
                    self._last_seg, self._last_seg_labels = seg, labels
                if seg is not None and (self._image_channels == 5
                                        or self._recorder is not None):
                    target_id = 0
                    want = self._sample.prim_path if self._sample is not None else None
                    for key, value in labels.items():
                        if want and want in str(value):
                            target_id = int(key)
                            break
                    mask = (seg == target_id).astype(np.float32)
        if self._loop_timing:
            # P43 L2: the camera stage (every `get_data` read of the observation
            # plus the mask arithmetic) and the observation count. `push_frame`
            # below is the observation *assembly* and lands in "other".
            self._loop_t["camera_ms"] += (time.perf_counter() - self._t_camera) * 1e3
            self._loop_counts["observations"] += 1
        self._last_rgb, self._last_depth, self._last_mask = rgb, depth, mask
        if self.policy is not None and rgb is not None and depth is not None:
            self.policy.push_frame(rgb, depth, mask)

    def proprio(self) -> np.ndarray:
        """The proprioception vector the training data recorded (25-D, or 26-D).

        All 22 joint positions, the active arm's finger opening, the two tactile
        normal forces. In `handoff` mode the finger channel is the harness's
        (``mean(dof[[14, 15]])`` - the left fingers, whatever arm is active),
        because that presentation's job is to reproduce the harness exactly;
        `direct` uses the active arm's finger, which is what the demonstrations
        recorded.

        P28-B: with ``FRUIT_OBS_SPEED=1`` one more scalar is appended - the belt
        speed from ``trigger.transport_speed()``, the same estimator the
        scripted primitive's schedule acts on (design C1). It is a per-episode
        constant in this build, which is why the stores synthesise it from a pin
        instead of recording it. The gate is read once in `__init__`, and with
        it off this method is the shipped 25-D assembly byte for byte - the
        extra value is not even computed.

        The channel deliberately does **not** inherit
        ``FRUIT_POLICY_TRIGGER_ENCODER``: a trigger knob must not change the
        model's observation, or an A/B arm would move two things at once (P28
        Gate A section 1). With no belt on the spawner the configured belt speed
        is reported, never 0.0 - 0.0 would read as "the belt is stopped".

        P36 (``FRUIT_PROPRIO_SPOOF``, default off): the **inactive** arm's 7
        joint values are overwritten with a named pose's achieved joints
        (``configs/proprio_spoof.json``) while the arm itself, the image, the
        fingers and the tactile channels stay live. It is the proprio half of
        the P35 mediator test - `FRUIT_ARM_PARK` moves the arm, this writes the
        observation - and it is pure array work on the copy below.
        """
        dof = np.asarray(self.scene.robot.get_dof_positions().numpy())[0].astype(
            np.float32
        )
        # P36 phase 1: the inactive arm's 7 joints (the park/proprio 2x2's obs
        # channel). Off - the shipped default - this is one empty-dict test, no
        # copy, and the assembled vector below is byte-identical.
        spoof = None
        if self._spoof_vectors:
            dof, spoof = apply_proprio_spoof(
                dof, self._active, self._spoof_arm_dofs(), self._spoof_vectors
            )
        if self.presentation == "handoff":
            finger = float(np.mean(dof[[14, 15]]))
        else:
            arm = self.task.arms[self._active]
            finger = float(np.mean(dof[list(arm.finger_dofs)]))
        reading = self.tactile.read()
        zero = 0.0
        forces = [
            float(reading.get("left").normal_force) if reading.get("left") else zero,
            float(reading.get("right").normal_force) if reading.get("right") else zero,
        ]
        if self._retime_on:
            # P52 phase 2: the contact gate's two channels, cached from the read
            # that just happened. The gate itself never reads a sensor (AGENTS.md
            # section 2 - per-tick work inside the control loop is what shifts a
            # run), and with the knob off neither this block nor the attributes
            # are touched, so the assembled vector below is byte-identical.
            side = "left" if self._active == "left" else "right"
            live = reading.get(side)
            self._retime_force_live = float(live.normal_force) if live else zero
            self._retime_finger_live = finger
            if self._retime_force_live > self._retime_force_max:
                self._retime_force_max = self._retime_force_live
        parts = [
            dof,
            np.array([finger], dtype=np.float32),
            np.asarray(forces, dtype=np.float32),
        ]
        if self._speed_channel:
            # The value the scripted primitive acts on: the encoder when it is
            # usable, else the fruit's measured velocity (read lazily inside the
            # helper). `use_encoder` stays the estimator's default - the trigger
            # knob must not change the model's observation (P28 Gate A sec. 1).
            # A missing belt reports the configured speed, never 0.0.
            parts.append(
                np.array(
                    [
                        belt_speed_scalar(
                            self.spawner,
                            self._sample,
                            fallback=self.cfg.belt_speed,
                        )
                    ],
                    dtype=np.float32,
                )
            )
        out = np.concatenate(parts).astype(np.float32)
        if self._spoof_diag:
            # P36 phase 1: the substitution's log certificate (pure reporting
            # over the vector just assembled; `spoof is None` = off/no-op).
            self._spoof_note_call(out, spoof)
        return out

    def _spoof_arm_dofs(self) -> dict[str, list[int]]:
        """The 7 proprio indices per arm (built on first use; knob-on only)."""
        if self._spoof_index_cache is None:
            self._spoof_index_cache = {
                name: [int(i) for i in arm.arm_dofs]
                for name, arm in self.task.arms.items()
            }
        return self._spoof_index_cache

    def _spoof_note_call(self, out: np.ndarray, info: dict | None) -> None:
        """P36: one proprio call's spoof bookkeeping (`FRUIT_SPOOF_DIAG` only).

        The **first** call records the certificate a reader needs to verify the
        substitution from the log alone: the 7 indices, the live and written
        values, the md5 of the assembled proprio before/after, and the md5 of
        the same vector with the 7 indices zeroed (equal before/after iff *only*
        those 7 channels changed - the report prints `rest_same`). Later calls
        only track the largest ``|live - written|`` over the episode: the pose
        the arm is actually in against the pose the observation claims.
        """
        self._spoof_calls += 1
        idx = np.asarray(info["indices"], dtype=int) if info is not None else np.zeros(0, int)
        inactive = "right" if self._active == "left" else "left"
        if idx.size and info is not None:
            vec = self._spoof_vectors.get(info["side"])
            if vec is not None:
                drift = float(
                    np.max(np.abs(np.asarray(info["before"], np.float32) - vec))
                )
                if self._spoof_drift != self._spoof_drift or drift > self._spoof_drift:
                    self._spoof_drift = drift
        if self._spoof_first is not None:
            return
        post = np.ascontiguousarray(out, dtype=np.float32)
        pre = post.copy()
        if idx.size and info is not None:
            pre[idx] = np.asarray(info["before"], dtype=np.float32)
        rest_post = post.copy()
        rest_pre = pre.copy()
        if idx.size:
            rest_post[idx] = 0.0
            rest_pre[idx] = 0.0
        self._spoof_first = {
            "applied": int(info["applied"]) if info is not None else 0,
            "side": info["side"] if info is not None else inactive,
            "indices": [int(i) for i in idx],
            "live": [float(v) for v in info["before"]] if info is not None else [],
            "obs": [float(v) for v in post[idx]] if idx.size else [],
            "pre_md5": hashlib.md5(pre.tobytes()).hexdigest(),
            "obs_md5": hashlib.md5(post.tobytes()).hexdigest(),
            "rest_md5": hashlib.md5(rest_post.tobytes()).hexdigest(),
            "rest_same": int(
                hashlib.md5(rest_pre.tobytes()).hexdigest()
                == hashlib.md5(rest_post.tobytes()).hexdigest()
            ),
        }

    def _spoof_report(self) -> str:
        """The `[spoof]` row: the proprio cell's manipulation check (P36)."""
        first = self._spoof_first or {}
        pose = self._spoof_pose or "-"

        def vals(values) -> str:
            return ",".join(f"{float(v):+.3f}" for v in values) if values else "-"

        drift = self._spoof_drift
        return (
            f"[spoof] episode {self._episode} pose={pose} "
            f"applied={int(first.get('applied', 0))} "
            f"side={first.get('side', '-')} "
            f"idx={','.join(str(i) for i in first.get('indices', [])) or '-'} "
            f"live={vals(first.get('live', []))} obs={vals(first.get('obs', []))} "
            f"pre_md5={first.get('pre_md5', '-')} obs_md5={first.get('obs_md5', '-')} "
            f"rest_md5={first.get('rest_md5', '-')} "
            f"rest_same={int(first.get('rest_same', 0))} "
            f"calls={int(self._spoof_calls)} "
            f"drift={format(float(drift), '+.4f') if drift == drift else '-'}"
        )

    def _obs_snapshot(self) -> dict:
        """Light observation for the caller (the policy input is built above).

        Getting the policy's observation is `push_frame` (camera) plus
        `proprio()` plus `goal`; this snapshot only reports where the episode is,
        so it costs no extra sensor reads in the control loop.
        """
        sample = self._sample
        return {
            "episode": self._episode,
            "tick": self._tick,
            "step": self._step,
            "policy_ready": bool(self.policy.ready) if self.policy is not None else False,
            "goal": self._goal.copy(),
            "fruit_position": (
                np.asarray(self.spawner.position(sample), dtype=float).copy()
                if sample is not None else None
            ),
            "presentation": self.presentation,
            "ablate": self.ablate,
        }

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def sample_chunk(self, num_steps: int | None = None) -> np.ndarray | None:
        """Sample a fresh action chunk, or zeros for the zero ablation.

        Matches the harness order: push the due camera frame first, then sample
        from the buffer. Returns None until the observation horizon is full.
        With RTC the chunker samples internally, one action per control step, so
        this only services the camera and returns None (`act` ignores it).
        """
        if self._done:
            return None
        if self._step % 4 == 0:
            self._observe()
        if self.ablate == "zero":
            return np.zeros((self.action_horizon, self.action_dim), dtype=np.float32)
        if self.policy is None or not self.policy.ready:
            return None
        if self.rtc is not None:
            return None
        if self._wait_gate_on:
            # P31-A: far fruit -> no decision -> no inference. The held chunk is
            # the last applied action repeated, so `act` still runs `_apply`
            # (fire machinery, recorder) on every tick; only the model call goes.
            held = self._wait_gate_hold()
            if held is not None:
                return held
        if self._rtc_report:
            start = time.perf_counter()
        if self._align_diag:
            # P34 phase 2: one fruit-pose read + the already-read target mask,
            # pure reporting for the manipulation check. Reached only when a
            # model call is about to happen; the diag is off by default.
            self._align_note_call()
        if self._park_diag:
            # P35 phase 2: the per-call park counters (same site: one fruit-pose
            # read plus a bbox census on the band call only).
            self._park_note_call()
        _loop_start = time.perf_counter() if self._loop_timing else 0.0
        chunk = self.policy.act(
            self.proprio(), self._goal, num_steps=self.ddim_steps if num_steps is None
            else int(num_steps)
        )
        if self._loop_timing:
            # P43 L2: the model-inference stage of the decision period.
            self._loop_t["policy_ms"] += (time.perf_counter() - _loop_start) * 1e3
            self._loop_counts["decisions"] += 1
        # P30-B: one model inference = one action chunk (a `ddim_steps`-step
        # denoising chain). Counted here, the only synchronous sampling site.
        self._infer_calls += 1
        if self._rtc_report:
            self._report_policy_ms.append((time.perf_counter() - start) * 1e3)
            self._report_decisions += 1
            self._pending_switch = True
        return chunk

    # ------------------------------------------------------------------ #
    # P31-A: the wait gate
    # ------------------------------------------------------------------ #
    def _wait_gate_active(self) -> bool:
        """Whether this episode may hold at all (scope, not the predicate).

        The narrowest scope that the measurement supports, checked in the order
        that fails fastest:

        * ``direct`` only - the interface P30-B measured and the one whose loop
          is `sample_chunk`-per-4-ticks. The `handoff` presentation teleports the
          fruit to the station, so it has no far-fruit wait to gate;
        * synchronous sampling only (`rtc is None`) - with RTC the sampler lives
          inside `next_action` and there is no per-chunk call to skip;
        * a real model only (`ablate == "none"`): the zero ablation already
          samples nothing, and a scripted ablation never reaches this path;
        * no event-triggered replanning - that lever chooses each chunk's
          execute horizon from the new chunk's continuity with the previous one,
          and a held chunk (continuity 0 against itself) would pollute its
          online median; the two are separate inference-scheduling arms;
        * no DAgger expert - the expert label, the takeover statistics and the
          recorded `policy_action` are per-decision data, and holding would
          silently change the store;
        * no active recorder - for the same reason (the dataset would lose the
          held frames and stay labelled by the held action).
        """
        if not self._wait_gate_on:
            return False
        if self.presentation != "direct":
            return False
        if self.rtc is not None or self.ablate != "none" or self.dagger is not None:
            return False
        if self._event:
            return False
        if self._recorder is not None and self._recorder.recording:
            return False
        return True

    def _wait_gate_along(self) -> float:
        """The target fruit's along-distance to the pick station [m], + upstream.

        The station reference is `_expert_jaw_y`, captured at reset at the
        calibrated grasp pose (the same point `_trigger_station` holds and the
        same one the DAgger expert's tracking window is measured from). A fixed
        reference is what makes the predicate monotone: the *measured* jaw walks
        up to 0.39 m upstream over a long wait (the policy's own tracking), so a
        jaw-relative distance would open early and drift.

        One rigid-body pose read per 4-tick chunk. `_episode_events` already
        reads the same pose every tick, so this is in the measured-safe class
        (AGENTS section 2: fruit-pose reads do not shift the run).
        """
        if self._sample is None:
            return float("nan")
        fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
        return float(fruit[1]) - float(self._expert_jaw_y)

    def _wait_gate_hold(self) -> np.ndarray | None:
        """The held chunk for this call, or None when the model must run.

        Called from `sample_chunk` behind `self._wait_gate_on`. Counts the skip,
        marks the chunk as a hold (`act` adds its executed ticks and clears the
        flag), and returns the last applied action repeated over the action
        horizon. `warm` (>= 1) guarantees `_last_action` is a real command: the
        first chunk has to have executed before the gate may hold, because
        `_last_action` is zeros at reset and a zero action commands all seven
        joints to their zero configuration.
        """
        if not self._wait_gate_active():
            return None
        warm = int(self._infer_calls) >= int(self.wait_gate.warm)
        along = self._wait_gate_along()
        if not self.wait_gate.skips(along, warm):
            if self._wait_gate_open:
                # The decision zone opened: model calls resume for the rest of
                # the attempt unless the fruit is recycled back upstream.
                self._wait_gate_open = False
                self._wait_gate_resumed = True
            return None
        if not self._wait_gate_open:
            self._wait_gate_open = True
            self._wait_gate_along0 = float(along)
        self._wait_gate_skipped += 1
        self._wait_gate_hold_chunk = True
        return np.repeat(
            np.asarray(self._last_action, dtype=np.float32)[None, :],
            int(self.action_horizon),
            axis=0,
        )

    def _wait_gate_report(self) -> str:
        """The `[gate]` row: skipped calls, held ticks, calls made, resume.

        One row per episode, printed from `_finalize` only with
        ``FRUIT_WAIT_GATE_DIAG=1``. `calls` is the same count P30-B publishes
        (`inference_calls`), so the saving is `skipped / (skipped + calls)`.
        """
        along0 = (
            f"{self._wait_gate_along0:+.3f}"
            if self._wait_gate_along0 == self._wait_gate_along0
            else "-"
        )
        return (
            f"[gate] episode {self._episode} skipped={int(self._wait_gate_skipped)} "
            f"held={int(self._wait_gate_held)} calls={int(self.inference_calls())} "
            f"along0={along0} dist={float(self.wait_gate.dist):.3f} "
            f"past={float(self.wait_gate.past):.3f} "
            f"resumed={int(self._wait_gate_resumed)}"
        )

    # ------------------------------------------------------------------ #
    # P34 phase 2: the reset alignment (default off)
    # ------------------------------------------------------------------ #
    def _align_presentation(self) -> None:
        """Put the target at the demos' first-view along at the first call.

        P34 phase 1 (`logs/p34/REPORT.md`): the recorded demonstrations begin
        at the wait loop with the target visible (frame 0 p50 +0.374,
        first-detectable p50 +0.399, no frame inside the +Y belt's band); the
        shipped direct reset presents it at p50 +0.583, i.e. inside the
        analytic fully-hidden band (+0.515..+0.870), and the model's first
        call then meets the fruit at +0.455..+0.551 (the P31 wait anatomy).

        This method advances the line **after** the reset's own setup (the
        arm teleport, `advance(20)`, `belt.start`) until the target sits at
        `_reset_align_along` upstream of the pick station at the first
        **model call**. The first call comes `execute_steps` control ticks
        after this returns (`sample_chunk` pushes the second frame at
        `_step % 4 == 0`; `obs_horizon=2`), so the aim prices that travel in
        with the belt's commanded speed (measured 1.000 mm/tick at 0.12 m/s,
        P31). The advance is the control loop's own pair - `advance(1)` plus
        `spawner.enforce_transport()` every tick - and no feeder `update`, so
        the release schedule stays where the reset left it. The arm holds the
        calibrated grasp pose throughout, exactly like the demos' wait loop.
        """
        aim = float(self._reset_align_along)
        speed = abs(float(self.cfg.belt_speed))
        travel = speed * float(max(1, int(self.execute_steps))) / 120.0
        aim0 = aim + travel
        steps = 0
        along = self._wait_gate_along()
        while along == along and along > aim0 and steps < self._reset_align_max_ticks:
            self.advance(1)
            self.spawner.enforce_transport()
            steps += 1
            along = self._wait_gate_along()
        self._align_steps = int(steps)
        self._align_along_reset = float(along)

    def _align_note_call(self) -> None:
        """Record one model call's along + target-mask pixels (diag only).

        Called immediately before `policy.act`; `_last_mask` is the frame that
        call conditions on (`_observe` ran at the same control step). Pure
        reporting: one fruit-pose read and one sum over the already-read mask.
        """
        if self._sample is None:
            return
        fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
        along = float(fruit[1]) - float(self._expert_jaw_y)
        zone = 0.15 <= along <= 0.30
        mask = self._last_mask
        px = -1 if mask is None else int(np.asarray(mask).sum())
        eye = np.array([float(self.cfg.head_camera_forward), 0.0,
                        float(self.cfg.head_camera_z)])
        pxc = float(px) * float(np.sum((fruit - eye) ** 2)) if px >= 0 else -1.0
        if pxc > self._align_pxc_max:
            self._align_pxc_max = pxc
        if px > self._align_px_max:
            # P34-B: the episode's raw maximum target mask (reported for
            # provenance only - it is depth-biased, because the fruit is closer
            # to the head camera downstream; `pfc`/`pcm` above are the
            # depth-corrected pair the treatment check reads).
            self._align_px_max = int(px)
        if (
            self._align_first_along == self._align_first_along  # set already
            and self._align_first_visible >= 0
            and not zone
        ):
            return
        if self._align_first_along != self._align_first_along:  # NaN
            self._align_first_along = along
            self._align_first_x = float(fruit[0])
            self._align_first_d = float(self._sample.diameter)
            self._align_first_px = int(px)
            self._align_pxc_first = float(pxc)
            # P34-B: the arm's pose at the first call (diag only, one
            # articulation read per episode). The reset pose and this one
            # answer "does the arm move during the reset/alignment?".
            arm = self.task.arms.get(self._active)
            if arm is not None:
                self._align_q_first = [float(v) for v in arm.joint_positions()]
        if self._align_first_visible < 0 and px >= 0:
            # The first *visible* model call: a zero target mask means the
            # fruit is fully hidden (belt and/or arm) in that frame.
            if px > 0:
                self._align_first_visible = int(self._infer_calls)
            else:
                self._align_hidden_calls += 1
        if zone:
            # P34 phase 1's arm-occlusion window (world y 0.15-0.30, the
            # decision zone's upstream half): the target mask there measures
            # the *arm* over the belt, which the reset alignment cannot move.
            self._align_zone_n += 1
            if px == 0:
                self._align_zone_zero += 1
            elif px > 0:
                self._align_zone_px.append(int(px))

    def _park_note_call(self) -> None:
        """P35 phase 2 (Gate-1 P0): one model call's park counters (diag only).

        **M1 - the pose held.** Read at the first **non-stale** model call
        (`_infer_calls >= 1`; the first call conditions on the pre-reset frame,
        P34-B) and measured against the pose the reset **achieved** for the
        inactive arm (captured after the reset's own settle), with the
        achieved-vs-commanded residual reported separately. The command is not
        the right reference: `teleport_joints` re-bases the drive onto the
        measured state, so the shipped `ready` sits 0.027-0.038 rad from its own
        command and the park 0.090-0.102 from its.

        **M2 - the sightline.** Censused over **+0.30..+0.40** (phase 1's cover
        is 0.81 / 0.98 / 0.57 there and 0.01 at +0.45, so counting +0.45 samples
        the one pose the arm does not occlude) and read at the band's **worst**
        call. The arm's pixels are counted inside the target's **projected disc**
        bbox (`_park_disc_bbox`: the analytic sphere projection, the same camera
        model as `212`/`217`) - not the visible-mask extent, which shrinks by
        exactly the occlusion being measured and so under-counts the occluder.
        The target's visibility is reported two ways and gated on the first:
        `rel` (against the episode's depth-corrected maximum, the phase-1/PREREG
        normalisation) and `vis` (against the projected disc's own pixel area -
        absolute, no assumption that some call of the episode is unoccluded, but
        the analytic disc over-reads the rendered silhouette by 10-15 %, so it
        is a report and not a bar: phase 1's fully-visible proxies read
        0.878-0.953 of it).
        Reporting only: one fruit-pose read plus one projection + bbox histogram
        per band call.
        """
        if self._sample is None:
            return
        if self._infer_calls < 1:
            # The pre-reset frame (P34-B): the first model call conditions on a
            # frame one or more renders behind, so it can carry neither a pose
            # nor a sightline claim.
            if self._park_diag:
                self._park_stale_skipped += 1
            return
        fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
        along = float(fruit[1]) - float(self._expert_jaw_y)
        mask = self._last_mask
        px = -1 if mask is None else int(np.asarray(mask).sum())
        eye = np.array([float(self.cfg.head_camera_forward), 0.0,
                        float(self.cfg.head_camera_z)])
        pxc = float(px) * float(np.sum((fruit - eye) ** 2)) if px >= 0 else -1.0
        if pxc > self._park_pxc_max:
            self._park_pxc_max = pxc
        inactive = "right" if self._active == "left" else "left"
        arm = self.task.arms.get(inactive)
        want = self._arm_park_poses.get(inactive)
        if want is None:
            want = np.asarray(self.waypoints["arms"][inactive]["ready"], dtype=float)
        want = np.asarray(want, dtype=float)
        settled = self._park_settled.get(inactive)
        if self._park_m1_hold != self._park_m1_hold and arm is not None:
            q = np.asarray(arm.joint_positions(), dtype=float)
            if settled is not None:
                self._park_m1_hold = float(np.max(np.abs(q - settled)))
                self._park_m1_cmd = float(np.max(np.abs(np.asarray(settled) - want)))
                self._park_q_settled = [float(v) for v in settled]
            else:
                self._park_m1_cmd = float(np.max(np.abs(q - want)))
            self._park_q_first = [float(v) for v in q]
        lo, hi = self._park_band
        if lo <= along <= hi and px >= 0:
            bbox, disc_area = self._park_disc_bbox(fruit, float(self._sample.diameter))
            if bbox is None:
                return
            arm_px, target_px, top = self._park_bbox_census(bbox, inactive)
            rel = pxc / self._park_pxc_max if self._park_pxc_max > 0 and pxc > 0 else -1.0
            frac = arm_px / target_px if arm_px >= 0 and target_px > 0 else -1.0
            vis = target_px / disc_area if disc_area > 0 else -1.0
            ok = int(frac >= 0 and frac < 0.10 and rel >= 0.85)
            self._park_band_calls += 1
            if self._park_q_band == [] and arm is not None:
                # The pose at the band's first call, so `drift` (first non-stale
                # call -> band call) reports whether the pose holds through the
                # window the sightline is scored in. One articulation read.
                self._park_q_band = [float(v) for v in arm.joint_positions()]
            if self._park_band_along != self._park_band_along:  # first band call
                self._park_band_along = along
                self._park_band_x = float(fruit[0])
                self._park_band_px = int(px)
                self._park_band_disc = float(disc_area)
                self._park_band_vis = float(vis)
                self._park_band_arm = int(arm_px)
                self._park_band_top = top
            # The gate reads the band's WORST call, not its best or its first.
            if frac >= 0 and frac > self._park_worst_arm:
                self._park_worst_arm = float(frac)
                self._park_worst_arm_along = float(along)
                self._park_worst_top = top
            if vis >= 0 and (self._park_worst_vis < 0 or vis < self._park_worst_vis):
                self._park_worst_vis = float(vis)
                self._park_worst_vis_along = float(along)
            if frac >= 0 and (self._park_min_frac < 0 or frac < self._park_min_frac):
                self._park_min_frac = float(frac)
                self._park_min_frac_along = float(along)
            if frac > self._park_max_frac:
                self._park_max_frac = float(frac)
                self._park_max_frac_along = float(along)
            if rel >= 0 and (self._park_min_rel < 0 or rel < self._park_min_rel):
                self._park_min_rel = float(rel)
                self._park_min_rel_along = float(along)
            self._say(
                f"[park] call ep={self._episode} n={self._park_band_calls} "
                f"along={along:+.3f} x={float(fruit[0]):.3f} px={int(px)} "
                f"disc={disc_area:.0f} vis={vis:.3f} rel={rel:.3f} "
                f"arm_px={int(arm_px)} tgt_px={int(target_px)} frac={frac:.3f} "
                f"ok={ok} top={top or '-'}"
            )

    def _park_disc_bbox(self, fruit: np.ndarray, diameter: float):
        """The target's **projected disc** bbox + its exact pixel area.

        The analytic sphere projection of the shipped head camera - the same
        camera model as `scripts/212_occlusion_map.py` / `217_arm_park_map.py`
        (`assets.SceneConfig`'s eye/target/focal/aperture, the frame's own
        resolution). A sphere of radius `r` at distance `d` subtends
        `asin(r/d)`, so its silhouette is a circle of pixel radius
        `f * r / sqrt(d^2 - r^2)` and area `pi * radius^2` - exact, no sampling.
        Deliberately *not* the visible mask's extent: that extent is the disc
        minus its occluder, so a bbox fitted to it shrinks exactly when the
        occlusion the check is measuring is present, and the arm's share of it
        is under-counted. Returns `(bbox, area_px)` with
        `bbox = (c0, c1, r0, r1)` clipped to the frame, or `(None, -1)` if the
        sphere is behind the camera or off-frame.
        """
        seg = self._last_seg
        if seg is None:
            return None, -1.0
        h, w = seg.shape[:2]
        eye = np.array([float(self.cfg.head_camera_forward), 0.0,
                        float(self.cfg.head_camera_z)])
        target = np.asarray(self.cfg.head_camera_target, dtype=float)
        z = eye - target
        z = z / np.linalg.norm(z)
        up = np.array([0.0, 0.0, 1.0])
        x = np.cross(up, z)
        x = x / np.linalg.norm(x)
        y = np.cross(z, x)
        rot = np.stack([x, y, z], axis=1)
        fx = (w / 2.0) * float(self.cfg.camera_focal_length) / (
            float(self.cfg.camera_aperture[0]) / 2.0)
        fy = fx
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        radius = float(diameter) / 2.0
        rel = np.asarray(fruit, float) - eye
        dist = float(np.linalg.norm(rel))
        if dist <= radius * 1.01:
            return None, -1.0
        pc = rot.T @ rel
        if pc[2] >= -1e-9:
            return None, -1.0
        r_px = fx * radius / float(np.sqrt(max(dist * dist - radius * radius, 1e-9)))
        col = cx + fx * (pc[0] / -pc[2])
        row = cy - fy * (pc[1] / -pc[2])
        # The census bbox: the silhouette's own extent, rounded outward by one
        # pixel (the rasterised edge) - and no wider.
        c0 = int(np.floor(col - r_px)) - 1
        c1 = int(np.ceil(col + r_px)) + 1
        r0 = int(np.floor(row - r_px)) - 1
        r1 = int(np.ceil(row + r_px)) + 1
        if c1 < 0 or c0 > w - 1 or r1 < 0 or r0 > h - 1:
            return None, -1.0
        c0, c1 = max(0, c0), min(w - 1, c1)
        r0, r1 = max(0, r0), min(h - 1, r1)
        if c1 <= c0 or r1 <= r0:
            return None, -1.0
        return (c0, c1, r0, r1), float(np.pi * r_px * r_px)

    def _park_bbox_census(self, bbox, inactive: str) -> tuple[int, int, str]:
        """The parked arm's pixels in the target's disc bbox, the target's, top 3.

        Both counts come from the same segmentation frame the model call
        conditioned on: the arm's primitives all start `openarm_<side>_` (so
        `<side>_right_finger` cannot confuse the sides), the target's from its
        own mask. Returns `(-1, -1, "")` when the frame or the mask is missing.
        """
        seg = self._last_seg
        mask = self._last_mask
        if seg is None or mask is None or bbox is None:
            return -1, -1, ""
        c0, c1, r0, r1 = bbox
        sub = np.asarray(seg)[r0:r1 + 1, c0:c1 + 1]
        sub_mask = np.asarray(mask)[r0:r1 + 1, c0:c1 + 1] > 0
        if sub.size == 0:
            return -1, -1, ""
        ids, counts = np.unique(sub, return_counts=True)
        labels = self._last_seg_labels or {}
        prefix = f"openarm_{inactive}_"
        arm_px = 0
        for ident, count in zip(ids, counts):
            text = str(labels.get(str(int(ident)), labels.get(int(ident), "")))
            if prefix in text:
                arm_px += int(count)
        target_px = int(sub_mask.sum())
        order = np.argsort(-counts)[:3]
        top = " | ".join(
            f"{int(ids[i])}:{int(counts[i])}px:"
            f"{str(labels.get(str(int(ids[i])), labels.get(int(ids[i]), '?')))[-40:]}"
            for i in order
        )
        return arm_px, target_px, top

    def _park_label(self) -> str:
        """The resolved park **and its origin**, e.g. `back(default)`.

        P43 phase 4 (A1): every row that names the park names where the value
        came from - `default` (the direct presentation's P43 default),
        `explicit` (`FRUIT_ARM_PARK` was set) or `shipped` (nothing set, no
        park). Without it a post-flip log cannot be told from an opt-in arm's,
        and the A arm of any pre-P43 A/B is an `explicit`/`shipped` `ready`.
        """
        origin = (
            "default"
            if self._arm_park_defaulted
            else "explicit"
            if self._park_env is not None
            else "shipped"
        )
        return f"{self._arm_park or 'ready'}({origin})"

    def _park_poses_label(self) -> str:
        """The pose each arm **resolves** to, e.g. `left:back,right:ready`.

        `configs/arm_parks.json` carries a `back` vector for the left arm only
        (the right arm's `back` does not hold and puts the fingertip in the
        belt footprint), so a **right-inactive** episode's park name is `back`
        while the right arm stayed at the shipped `ready`. P43 phase 3's rows
        printed only the name and therefore read as if both arms had moved;
        this states which pose each arm actually takes. The row's `inactive=`
        field names the one that is applied this episode.
        """
        return ",".join(
            f"{side}:{self._arm_park if side in self._arm_park_poses else 'ready'}"
            for side in ("left", "right")
        )

    def _park_report(self) -> str:
        """The `[park]` row: M1/M2 of `logs/p35/PREREG.md` section 2 (P0 gate)."""
        def num(value: float, fmt: str = "+.3f") -> str:
            return format(float(value), fmt) if value == value else "-"

        inactive = "right" if self._active == "left" else "left"
        band = int(self._park_band_along == self._park_band_along)
        m1_hold_ok = int(self._park_m1_hold == self._park_m1_hold
                         and self._park_m1_hold <= 0.02)
        # M2 is the pre-registered conjunction at the band's worst call: the
        # arm's share of the target's *disc* bbox (< 0.10) and the target's
        # visibility against the episode's depth-corrected maximum (`rel`,
        # `[align]`'s `pfc`/`pcm` normalisation, >= 0.85). `vis` (against the
        # projected disc's pixel area, `disc`) is reported, not gated: the
        # analytic disc over-reads the rendered silhouette by 10-15 % (phase 1's
        # fully-visible proxies read 0.878-0.953 of it), so its 0.85 bar would
        # fail a fully visible fruit.
        # The first band call can be fully occluded (`band_px == 0`, the
        # control's normal case), so this ratio needs its own guard: the row
        # must never raise (a `ZeroDivisionError` here aborts the episode, and
        # it did - the first record batch's arm-A runs died at episode 3).
        band_frac = (float(self._park_band_arm) / float(self._park_band_px)
                     if self._park_band_arm >= 0 and self._park_band_px > 0
                     else -1.0)
        m2_arm = int(0.0 <= self._park_worst_arm < 0.10)
        m2_rel = int(self._park_min_rel >= 0.85)
        drift = float("nan")
        if self._park_q_band and self._park_q_first:
            drift = float(np.max(np.abs(np.asarray(self._park_q_band, float)
                                        - np.asarray(self._park_q_first, float))))
        return (
            f"[park] episode {self._episode} arm={self._active} inactive={inactive} "
            f"park={self._park_label()}[{self._park_poses_label()}] "
            f"m1_hold={num(self._park_m1_hold)} m1_hold_ok={m1_hold_ok} "
            f"m1_cmd={num(self._park_m1_cmd)} "
            f"m2_arm={self._park_worst_arm:.3f} m2_arm_ok={m2_arm if band else -1} "
            f"m2_rel={self._park_min_rel:.3f} m2_rel_ok={m2_rel if band else -1} "
            f"m2_ok={int(m2_arm and m2_rel) if band else -1} "
            f"m2_vis={self._park_worst_vis:.3f} "
            f"band={num(self._park_band_along)} band_x={num(self._park_band_x)} "
            f"band_px={int(self._park_band_px)} band_disc={self._park_band_disc:.0f} "
            f"band_vis={self._park_band_vis:.3f} "
            f"arm_px={int(self._park_band_arm)} band_frac={band_frac:.3f} "
            f"band_calls={int(self._park_band_calls)} "
            f"stale_skipped={int(self._park_stale_skipped)} "
            f"worst_arm_at={num(self._park_worst_arm_along)} "
            f"worst_vis_at={num(self._park_worst_vis_along)} "
            f"min_frac={self._park_min_frac:.3f} max_frac={self._park_max_frac:.3f} "
            f"drift={num(drift)} calls={int(self._infer_calls)} "
            f"q={','.join(format(v, '.3f') for v in self._park_q_first) or '-'} "
            f"q_settled={','.join(format(v, '.3f') for v in self._park_q_settled) or '-'} "
            f"top={self._park_worst_top or self._park_band_top or '-'}"
        )

    def _align_report(self) -> str:
        """The `[align]` row: the manipulation check + the fire-zone mask."""
        def num(value: float, fmt: str = "+.3f") -> str:
            return format(float(value), fmt) if value == value else "-"

        px50 = int(np.median(self._align_zone_px)) if self._align_zone_px else -1

        def joints(values: list[float]) -> str:
            return ",".join(format(float(v), ".3f") for v in values) if values else "-"

        return (
            f"[align] episode {self._episode} knob={int(self._reset_align)} "
            f"y0={num(self._align_y0)} reset={num(self._align_along_reset)} "
            f"steps={int(self._align_steps)} jaw={num(self._expert_jaw_y)} "
            f"settle={int(self._reset_settle)} "
            f"first={num(self._align_first_along)} x={num(self._align_first_x)} "
            f"first_d={num(self._align_first_d)} first_px={int(self._align_first_px)} "
            f"first_vis_call={int(self._align_first_visible)} "
            f"hidden={int(self._align_hidden_calls)} "
            f"zone_n={int(self._align_zone_n)} zone_zero={int(self._align_zone_zero)} "
            f"zone_px={px50} px_max={int(self._align_px_max)} "
            f"pfc={self._align_pxc_first:.0f} pcm={self._align_pxc_max:.0f} "
            f"calls={int(self.inference_calls())} "
            f"q_r={joints(self._align_q_reset)} q_f={joints(self._align_q_first)}"
        )

    def inference_calls(self) -> int:
        """P30-B: model inference calls this episode (chunks sampled, pure count).

        The synchronous path counts one call per `sample_chunk`; with the RTC
        chunker the sampler completes chunks inside `next_action`, so its
        `chunks_sampled` is added. GDP's K-candidate sampling rides inside one
        `PolicyRunner.act` and is therefore one call (its K chains are the
        per-call cost, reported by the `[gdp]` row). A zero ablation samples no
        model and reads 0.
        """
        calls = int(self._infer_calls)
        if self.rtc is not None:
            calls += int(getattr(self.rtc, "chunks_sampled", 0))
        return calls

    def act(self, chunk: np.ndarray | None, execute_steps: int | None = None) -> StepResult:
        """Execute up to ``execute_steps`` actions; returns the step result.

        With event-triggered replanning (``FRUIT_POLICY_EVENT=1``) the horizon
        for this chunk is chosen by `_event_horizon` instead of the passed
        ``execute_steps``; the argument is then the reference/default only.
        """
        steps = self.execute_steps if execute_steps is None else max(1, int(execute_steps))
        if self._action_hold > 1:
            # P53 C2: one chunk waypoint per `_action_hold` control ticks, so a
            # decision covers `execute_steps * hold` ticks and the chunk's
            # command rate is 120/hold Hz. Twice the ticks, half the decisions
            # and half the re-plan boundaries per second of sim time - the
            # direction the census's 30 Hz-vs-120 Hz mismatch points at
            # (`logs/p52/P2B_FEASIBILITY.md` 2.5).
            steps *= self._action_hold
        if self._done:
            return self._step_result()
        if self._sample is None:
            raise RuntimeError("call reset() before act()")
        # P56: a fresh `act` call starts the pick that is now active; the flag is
        # only read inside this loop (it is set by `_finalize` when a continuous
        # episode moved on to the next pick mid-call).
        self._pick_boundary = False
        if self.ablate == "scripted":
            self._run_scripted()
            return self._step_result()
        if self._event:
            steps = self._event_horizon(chunk)

        executed = 0
        for index in range(steps):
            step_start = time.perf_counter() if self._rtc_report else 0.0
            if self._step % 4 == 0:
                self._observe()
            # The handoff evaluator hands over on a fixed control-step budget,
            # before the observation branch of the loop body.
            if self.presentation == "handoff" and self._step >= self.approach_steps:
                self._run_primitive()
                if self._done:
                    break
            self._switch_flag = False
            action = None
            if self.rtc is not None:
                # One action per control step; the sampler advances interleaved.
                # `last_switch` was set by the previous step's completion, so the
                # action about to be applied is the first of a new chunk.
                self._switch_flag = bool(self.rtc.last_switch)
                if self.policy.ready:
                    if self._rtc_report:
                        start = time.perf_counter()
                    action = self.rtc.next_action(
                        self.proprio, self._goal, self.ddim_steps,
                        roll=self._roll_proprio if self.rtc_settings.vlash else None,
                    )
                    if self._rtc_report:
                        self._report_policy_ms.append((time.perf_counter() - start) * 1e3)
            elif chunk is not None:
                arr = np.asarray(chunk)
                if self._action_hold > 1:
                    # P53 C2: expand each waypoint to `hold` control ticks, so
                    # the shipped `arr[index]` lookup below stays the lookup and
                    # the hold is a property of the *path*, not of the index
                    # arithmetic. Once per decision, 16x9 -> 32x9 floats.
                    arr = np.repeat(arr, self._action_hold, axis=0)
                if index < arr.shape[0]:
                    if self._retime_on:
                        # P52 phase 2: apply the contact-gated time-scale. With
                        # the gate clamped to 1.0 (or the scale unset) this
                        # returns `arr[index]` exactly - see `retime_action`.
                        action = self._retime_step(arr, index)
                    else:
                        action = arr[index]
                if self._rtc_report and index == 0:
                    self._switch_flag = bool(self._pending_switch)
                    self._pending_switch = False
            if self.dagger is not None:
                action = self._dagger_action(action)
            if action is not None:
                self._apply(action, index)
                if self._done or self._pick_boundary:
                    executed = index + 1
                    break
                self._record_tick()
                self.advance(1)
            else:
                self.advance(1)
            if self._rtc_report:
                self._report_control_ms.append(
                    (time.perf_counter() - step_start) * 1e3
                )
            self._tick += 1
            self.spawner.enforce_transport()
            self._step += 1
            executed = index + 1
            if self._episode_events():
                if self._pick_boundary:
                    # P56: the event ended pick k and started pick k+1; the rest
                    # of this chunk belongs to the old pick.
                    break
                continue
            if self._tick >= int(self.reward.horizon):
                self._finalize(
                    notes=self._notes + [
                        f"timeout: no grasp within {int(self.reward.horizon)} ticks"
                    ]
                )
                break
        if self._event:
            # The next chunk is sampled at the state after these `executed`
            # steps; its index `i` then corresponds to this chunk's index
            # `executed + i` (the same absolute control step).
            self._prev_chunk = (
                None if chunk is None else np.asarray(chunk, dtype=np.float64).copy()
            )
            self._prev_exec = int(executed)
        if self._wait_gate_hold_chunk:
            # P31-A: the chunk just executed was the gate's held chunk (no model
            # call); book the ticks it actually covered. False on the default
            # path (`_wait_gate_hold` sets it only when the gate holds).
            self._wait_gate_held += int(executed)
            self._wait_gate_hold_chunk = False
        return self._step_result()

    def _retime_step(self, arr: np.ndarray, index: int) -> np.ndarray:
        """P52 phase 2: the re-timed action for tick ``index`` (+ the gate row).

        The gate is consulted per control tick against the **decision's own**
        observation (the channels `proprio()` cached: at most 3 ticks old, since
        the observation grid is 4 ticks). With the gate armed and the hand in
        contact the effective scale is 1.0, which is the demonstrated rate - the
        re-timing is applied to free-space motion only.

        One ``[retime]`` row per **decision** (``index == 0``) carrying ``s``,
        the effective scale, the gate state and the two channels it read, plus a
        per-episode summary in `_retime_row`. Off, neither exists.
        """
        in_contact = bool(
            self._retime_gate_on
            and retime_contact(
                self._retime_force_live,
                self._retime_finger_live,
                self._retime_force_threshold,
                self._retime_open_threshold,
            )
        )
        effective = 1.0 if in_contact else float(self._time_scale)
        self._retime_calls += 1
        if in_contact:
            self._retime_gated += 1
            if self._retime_force_live > self._retime_force_threshold:
                self._retime_force_gated += 1
            if self._retime_finger_live < self._retime_open_threshold:
                self._retime_finger_gated += 1
        if index == 0:
            self._retime_decisions += 1
            if in_contact:
                self._retime_gated_decisions += 1
            self._say(
                f"[retime] ep={self._episode} decision={self._retime_decisions - 1} "
                f"s={self._time_scale:.2f} s_eff={effective:.2f} "
                f"contact={int(in_contact)} "
                f"force={self._retime_force_live:.2f}N "
                f"finger={self._retime_finger_live * 1000:.1f}mm "
                f"step={self._step} tick={self._tick}"
            )
        return retime_action(arr, index, effective)

    def _retime_row(self) -> str:
        """P52 phase 2: the per-episode gate summary (armed runs only)."""
        share = (
            self._retime_gated_decisions / self._retime_decisions
            if self._retime_decisions
            else 0.0
        )
        tick_share = (
            self._retime_gated / self._retime_calls if self._retime_calls else 0.0
        )
        return (
            f"[retime] episode {self._episode}: s={self._time_scale:.2f} "
            f"gate={int(self._retime_gate_on)} "
            f"decisions={self._retime_decisions} "
            f"gated={self._retime_gated_decisions} ({share:.1%}) "
            f"ticks={self._retime_calls} gated_ticks={self._retime_gated} "
            f"({tick_share:.1%}) "
            f"by_force_ticks={self._retime_force_gated} "
            f"by_finger_ticks={self._retime_finger_gated} "
            f"force_max={self._retime_force_max:.2f}N"
        )

    def _emit_row(self) -> str:
        """P53: the per-episode emission summary (printed only with the diag on).

        One print, no state: the out-of-range joint count of the command the
        policy emitted (`pre`, the census's 13.1 % / 74.3 % measurement) beside
        the count the drives received (`post` - identical without C1's clamp by
        construction), the applied ticks and the policy decisions, so the
        hold's effect on the decision count is auditable from the log alone.
        """
        post = self._emit_post_out if self._joint_clamp else self._emit_pre_out
        share = (self._emit_pre_out / (7 * self._emit_ticks)) if self._emit_ticks else 0.0
        post_share = (
            post / (7 * self._emit_ticks) if self._emit_ticks else 0.0
        )
        return (
            f"[emit] episode {self._episode}: hold={self._action_hold} "
            f"clamp={int(self._joint_clamp)} ticks={self._emit_ticks} "
            f"decisions={self._emit_decisions} "
            f"out_pre={self._emit_pre_out}/{7 * self._emit_ticks} "
            f"({share:.1%}) "
            f"out_post={post}/{7 * self._emit_ticks} ({post_share:.1%}) "
            f"ticks_with_overshoot={self._emit_clamped_ticks} "
            f"overshoot_max={self._emit_pre_max * 1000:.1f}mrad"
        )

    def _apply(self, action, index: int = 0) -> None:
        action = np.asarray(action, dtype=np.float64).reshape(-1)
        if not np.isfinite(action).all():
            self._notes.append("non-finite policy action")
            return
        arm = self.task.arms[self._active]
        if self._a2c2 is not None and not self._triggered:
            # A2C2-style per-step correction on the frozen base policy, before
            # the primitive owns the arm. The head only shifts the 7 arm
            # channels; the finger command (and so the trigger) is unchanged.
            action = self._a2c2.correct(action, self.proprio(), self._goal, index)
        if self._policy_track and self._sample is not None and not self._sample.attached:
            action = self._tracking_action(action, arm)
        if self._emit_diag:
            # P53: the out-of-range count of the command as the policy emits it
            # (T0's whole stream, C1's input) - pure array work on the action in
            # hand, no simulator read.
            count, over = emit_out_of_range(action, arm.arm_lo, arm.arm_hi)
            self._emit_ticks += 1
            if index == 0:
                self._emit_decisions += 1
            self._emit_pre_out += count
            if over > self._emit_pre_max:
                self._emit_pre_max = over
            if count:
                self._emit_clamped_ticks += 1
        if self._joint_clamp:
            # P53 C1: clip the 7 absolute joint targets into the arm's own joint
            # range before the drives see them. The census measured the shipped
            # emissions out of range on 74.3 % of ticks with no clamp on this
            # path (`logs/p52/P2B_FEASIBILITY.md` 1.6), so the drive pushes into
            # the stop; this is the zero-time-cost cell that removes that.
            action = clamp_joint_targets(action, arm.arm_lo, arm.arm_hi)
            if self._emit_diag:
                count, over = emit_out_of_range(action, arm.arm_lo, arm.arm_hi)
                self._emit_post_out += count
        self.scene.robot.set_dof_position_targets(
            [action[:7].tolist()], dof_indices=list(arm.arm_dofs)
        )
        finger = float(np.clip(action[7], 0.0, 0.044))
        self.scene.robot.set_dof_position_targets(
            [[finger, finger]], dof_indices=list(arm.finger_dofs)
        )
        if action.shape[0] > 8:
            # Recorded channel: the two finger joints mirror `action[7]`, the
            # same convention the demonstrations use.
            action = action.copy()
            action[7] = finger
            action[8] = finger
        if self._rtc_report:
            # Executed-stream diagnostics (off for rate runs): the 7-D arm command
            # jump between consecutive applied actions, split into switch
            # boundaries and within-chunk steps, plus the second difference
            # (jerk) of the whole executed stream. Pure reporting over
            # already-materialised arrays.
            current7 = np.asarray(action[:7], dtype=np.float64)
            if self._applied_any:
                delta = float(np.linalg.norm(current7 - self._last7))
                if self._switch_flag:
                    self._report_boundary.append(delta)
                else:
                    self._report_within.append(delta)
                self._report_step.append(delta)
                if self._prev7 is not None:
                    self._report_jerk.append(
                        float(np.linalg.norm(current7 - 2.0 * self._last7 + self._prev7))
                    )
            self._prev7 = self._last7
            self._last7 = current7
            self._applied_any = True
        self._last_action = action.astype(np.float32)
        self._last_finger = finger
        if self.presentation == "handoff":
            self._handoff_action_extras(finger)
        elif not self._triggered:
            jaw = arm.jaw_centre()
            fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
            distance = float(
                np.linalg.norm(fruit[:2] - np.asarray(jaw[:2], dtype=float))
            )
            if self._debug and (self._step % 25 == 0 or finger < 0.030):
                self._say(
                    f"[rl]   step={self._step} finger={finger:.4f} "
                    f"|jaw-fruit|xy={distance * 100:.1f}cm "
                    f"fruit=({fruit[0]:.3f},{fruit[1]:+.3f},{fruit[2]:.3f}) "
                    f"jaw=({jaw[0]:.3f},{jaw[1]:+.3f},{jaw[2]:.3f})"
                )
            policy_close = bool(finger < 0.030 and distance < 0.06)
            # R7-A (WS-4.6): the reach-cliff refusal binds the learned gate too.
            # `policy_close` is the shipped fire path and is evaluated
            # independently of the trigger, so before this change the x-band
            # guard could only refuse the *trigger* arm of the
            # `policy_close or intercept` union below: a fruit the trigger had
            # refused (a recorded `x_refuse`) was still attempted by the
            # learned close on a later tick, and every attempted-anyway
            # refusal flailed (R2 P1 4/7; R6 C0/C1/C2 3/3, 4/4, 3/3 -
            # `logs/w8/R2_RESULTS.md` section 3, `logs/r6/B_RESULTS.md`
            # section 1). The same predicate now refuses this path at its own
            # fire tick. `x_max` unset -> `None`, byte-neutral.
            gate_refuse = (
                x_edge_refusal(self.trigger_settings, fruit)
                if policy_close
                else None
            )
            intercept = False
            intercept_info: dict | None = None
            presented_note: str | None = None
            if self.trigger_settings.enabled:
                encoder = None
                if self.spawner.belt is not None:
                    encoder = getattr(self.spawner.belt, "encoder_speed", None)
                reference = jaw
                if self.trigger_settings.frame == "station":
                    reference = np.array(
                        [self._trigger_station[0], self._trigger_station[1], jaw[2]],
                        dtype=float,
                    )
                intercept, intercept_info = should_fire(
                    self.trigger_settings,
                    fruit,
                    reference,
                    encoder_speed=encoder,
                    measured_velocity=self.spawner.velocity(self._sample),
                    finger=finger,
                    jaw_pos=jaw,
                    station=self._trigger_station,
                )
                # R2.3 reach-cliff guard (default off): a would-fire tick the
                # x-edge gate refused is recorded once per fruit, so a run with
                # `FRUIT_POLICY_TRIGGER_X_MAX` set reports how many candidates
                # it refused and the episode's own timeout line says why.
                self._note_x_refuse(self._sample.index, intercept_info)
                # P4b2: the scripted primitive re-selects the fruit the feeder
                # presents (`task.station_sample`) at grasp time, but this trigger
                # was watching the selected upstream sample. When that sample is
                # blocked, recirculated or pushed off-lane, a *firable* presented
                # fruit is the one the primitive would grasp - adopt it here so
                # the trigger fires on the fruit that will actually be picked.
                # Only when the selected sample is not already firable/closable,
                # so the clean path is byte-identical. Default off.
                if (
                    self.trigger_settings.present
                    and not intercept
                    and not policy_close
                ):
                    presented = self.task.station_sample()
                    if (
                        presented is not None
                        and int(presented.index) != int(self._sample.index)
                        and float(presented.diameter)
                        <= float(self.cfg.gripper_max_object)
                    ):
                        presented_fruit = np.asarray(
                            self.spawner.position(presented), dtype=float
                        )
                        p_fire, p_info = should_fire(
                            self.trigger_settings,
                            presented_fruit,
                            reference,
                            encoder_speed=encoder,
                            measured_velocity=self.spawner.velocity(presented),
                            finger=finger,
                            jaw_pos=jaw,
                            station=self._trigger_station,
                        )
                        self._note_x_refuse(presented.index, p_info)
                        if p_fire:
                            selected_dy = float(
                                (intercept_info or {}).get("dy", float("nan"))
                            )
                            self._sample = presented
                            # Keep the observation coherent for any tick before
                            # the primitive takes over; the arm's lane is kept
                            # (`_bin_index`), like the task's station re-select.
                            self._goal = np.array(
                                [
                                    *np.asarray(
                                        self.spawner.position(presented), dtype=np.float32
                                    ),
                                    *np.asarray(
                                        self.spawner.velocity(presented), dtype=np.float32
                                    ),
                                    float(presented.diameter),
                                    float(self._bin_index),
                                ],
                                dtype=np.float32,
                            )
                            intercept, intercept_info = True, p_info
                            presented_note = (
                                f"presented intercept: adopted index "
                                f"{presented.index} ({presented.category}) over the "
                                f"selected sample (selected dy={selected_dy:+.3f} m)"
                            )
            if self._refuse_knobs and not self._triggered:
                # P38 phase 2: the lateral-refusal harness (default off). Runs
                # after the P4b2 presentation adoption and before the fire
                # decision; on a refusal tick `intercept` is False by
                # construction and the learned close is a tracked term, so the
                # re-selection never races a fire on the same tick.
                self._track_refuse(distance, policy_close, intercept_info)
                if self._done:
                    return
            if direct_fire(
                intercept=intercept,
                policy_close=policy_close,
                gate_refuse=gate_refuse,
            ):
                self._triggered = True
                closer = (
                    "expert"
                    if self.dagger is not None and self._step < self._expert_until
                    else "policy"
                )
                if policy_close:
                    self._notes.append(
                        f"{closer} closed on the fruit (finger={finger:.4f}, "
                        f"|jaw-fruit|xy={distance * 100:.1f}cm)"
                    )
                if intercept:
                    info = intercept_info or {}
                    # W7-B: with the adaptive acquisition lead on, record the
                    # effective lead/reach at the fire tick (diagnostic; the
                    # note is not parsed by the physics compares).
                    acq_note = (
                        f", lead={info.get('lead', float('nan')):.2f}s/"
                        f"reach={info.get('reach', float('nan')):.2f}"
                        if self.trigger_settings.acq else ""
                    )
                    self._notes.append(
                        "intercept trigger ("
                        f"dy={info.get('dy', float('nan')) * 100:.1f}cm, "
                        f"dx={info.get('dx', float('nan')) * 100:.1f}cm, "
                        f"t_arrive={info.get('t_arrive', float('nan')):.2f}s, "
                        f"speed={info.get('speed', float('nan')):.3f}m/s/"
                        f"{info.get('source', '?')}, frame={self.trigger_settings.frame}, "
                        f"finger={finger:.4f}{acq_note})"
                    )
                if presented_note is not None:
                    self._notes.append(presented_note)
                self._run_primitive()
            elif gate_refuse is not None:
                # R7-A (WS-4.6): the learned close wanted to fire on a fruit
                # past the band edge - refuse it exactly as the trigger path
                # does. The canonical refusal note is once per fruit (the
                # trigger may already have recorded it this episode); the gate
                # event is recorded once per fruit too and the candidate rides
                # past instead of running the primitive.
                self._note_x_refuse(self._sample.index, {"x_refuse": gate_refuse})
                self._note_gate_refuse(
                    self._sample.index, gate_refuse, finger, distance
                )

    def _note_x_refuse(self, index: int, info: dict | None) -> None:
        """R2.3: record one x-edge refusal per fruit (the reach-cliff guard).

        `should_fire` sets ``info["x_refuse"]`` on a tick that would have fired
        but for `FRUIT_POLICY_TRIGGER_X_MAX`; the note names the fruit's x and
        the outcome line then says the candidate rode past instead of being
        chased (the flail class `logs/w8/R2_RESULTS.md` section 3 measures).
        No-op when the knob is off (the key is absent), so the shipped default
        is unchanged.
        """
        if not info or info.get("x_refuse") is None:
            return
        if int(index) in self._x_refused:
            return
        self._x_refused.add(int(index))
        self._notes.append(
            f"x-edge refuse: fruit x={float(info['x_refuse']):.3f} beyond "
            "FRUIT_POLICY_TRIGGER_X_MAX (rides past the station)"
        )

    def _note_gate_refuse(
        self, index: int, x: float, finger: float, distance: float
    ) -> None:
        """R7-A (WS-4.6): record one policy-gate refusal per fruit.

        The learned close wanted to fire (``finger < 0.030`` and the jaw within
        6 cm) but the fruit sits past `FRUIT_POLICY_TRIGGER_X_MAX`, so the
        fire is refused at its own tick - the same refuse-and-ride-past the
        trigger path performs. The event is what the R7-A cross-check counts
        (the canonical note may already exist from the trigger tick). One note
        per fruit per episode; no-op when the guard is off, so the shipped
        direct interface is unchanged.
        """
        if int(index) in self._gate_refused:
            return
        self._gate_refused.add(int(index))
        self._notes.append(
            f"x-edge policy-gate refuse: fruit x={x:.3f} beyond "
            f"FRUIT_POLICY_TRIGGER_X_MAX (finger={finger:.4f}, "
            f"|jaw-fruit|xy={distance * 100:.1f}cm; rides past the station)"
        )

    # ------------------------------------------------------------------ #
    # P38 phase 2: the lateral-refusal harness (all four knobs default off)
    #
    #: Known defects, recorded by the P38 Gate-2 review and NOT fixed here
    #: (`logs/p38/P2_RESULTS.md` section 8, "the latent defects"):
    #:  (a) `_reseed_step` calls `spawner.protect(adopted)` and never unprotects
    #:      it at the episode end (the reset only sets the scalar
    #:      `spawner.protected`, it does not touch `protected_indices`), so an
    #:      adoption leaks one index into `protected_indices` for the rest of the
    #:      process. Inert on the direct path (its selection does not exclude the
    #:      set); the scripted/bimanual callers read `protected_indices` in their
    #:      own selectors, which is why the reseed stays direct-only.
    #:  (b) the END's `dy` is measured against the **captured station**
    #:      (`_trigger_station`), while `should_fire` measures `dy` in
    #:      `FRUIT_POLICY_TRIGGER_FRAME`'s frame (default `station`; `jaw` moves
    #:      the trigger's own downstream gate). Inert at `FRAME=station`.
    #:  (c) the END is evaluated *before* the tick's fire decision and reads
    #:      neither `intercept` nor the P4b2 `present` adoption, and
    #:      `_policy_best_gap` is per-episode rather than per-candidate (the
    #:      note's "best |jaw-fruit|" spans a pre-reseed candidate too). All
    #:      three are direct-only and default-off (the era's readings are on the
    #:      shipped configuration, where none of them can fire).
    # ------------------------------------------------------------------ #
    def _track_refuse(
        self, distance: float, policy_close: bool, info: dict | None
    ) -> None:
        """Book one tick of the lateral-refusal harness. No-op when all off.

        The learned close is *tracked* every tick (it is the second fire path the
        lateral gate has never bound - `direct_fire`), because the terminal class
        is only allowed to claim a closure the run itself observed
        (`logs/p38/PREREG_A1.md` A1, term C3).
        """
        if policy_close:
            if not self._policy_close_seen and self._refuse_diag:
                # P38 Gate-2 (H1): the second fire path's *timing*, so the END's
                # closure ("no close fired before the fruit's departure") can be
                # read where it is claimed - the tick the learned close latched,
                # in the END's own frame (`dy <= -0.05` is past the departure).
                # One fruit-pose read per episode, in the documented-safe class.
                fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
                dy = float(fruit[1]) - float(self._trigger_station[1])
                self._say(
                    f"[refuse] close: tick={int(self._tick)} dy={dy:+.3f} m "
                    f"(station frame; <= -0.05 is past the departure) "
                    f"|jaw-fruit|xy={distance * 100:.1f}cm"
                )
            self._policy_close_seen = True
        if distance < self._policy_best_gap:
            self._policy_best_gap = float(distance)
        if policy_close:
            # The learned gate fired: the primitive owns the episode.
            return
        dx_refuse = (info or {}).get("lateral_refuse")
        if dx_refuse is not None and int(
            self._sample.index
        ) not in self._refuse_indices:
            self._latch_refusal(float(dx_refuse))
        if self._refuse_latch is not None:
            # The temporal scan retry (bounded by the per-refusal budget).
            self._reseed_step()
        if (
            self._refuse_end
            and self._refuse_latch is not None
            and not self._policy_close_seen
        ):
            self._maybe_end_no_firable()

    def _latch_refusal(self, dx: float) -> None:
        """The first provable trigger refusal for this candidate (`should_fire`).

        Provable = every other trigger gate passed and only `|dx| > lateral`
        failed, and `x` is frozen for the rest of the transit (`P1_RESULTS.md`
        section 2: the transport's lateral term is exactly 0.000 mm, and the
        reference is the station captured at reset), so no later tick can fire
        this candidate.
        """
        index = int(self._sample.index)
        fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
        x = float(fruit[0])
        station_x = float(self._trigger_station[0])
        lateral = float(self.trigger_settings.lateral)
        self._refuse_count += 1
        self._refuse_indices.add(index)
        self._refuse_latch = {
            "index": index,
            "category": self._sample.category,
            "x": x,
            "dx": float(dx),
            "station_x": station_x,
            "lateral": lateral,
            "tick": int(self._tick),
            "policy_gap": float(self._policy_best_gap),
        }
        if self._refuse_diag:
            self._notes.append(
                f"lateral refuse: fruit x={x:.3f} |dx|={abs(dx):.3f} > lateral "
                f"{lateral:.3f} (station x={station_x:.3f} -> x >= "
                f"{station_x - lateral:.3f} admitted; x frozen, permanent)"
            )
        if self._reseed and self._reseed_left > 0:
            # A fresh scan budget for this refusal. The retry is *temporal*
            # (one scan per `_reseed_stride` ticks, PREREG_A1 A2c): at the
            # refusal instant the selector's upstream window is usually empty
            # of other candidates (measured: 3/3 refusals scanned once and got
            # `None`, `logs/p38/z6_smoke_m2c6.log`), so a same-instant 4-scan
            # loop would report "the supply has no alternative" for an
            # implementation reason. The *bound* is unchanged: 4 scans and
            # `RESEED_MAX` adoptions per episode.
            self._reseed_seen = {index}
            self._reseed_scans_left = int(self._reseed_scans_max)
            self._reseed_next_tick = 0
            self._reseed_exhausted_noted = False
            self._reseed_step()

    def _reseed_step(self) -> None:
        """One bounded same-lane scan; adopt the first candidate inside the gate.

        Everything is rebuilt exactly as the reset does (`_goal`, `_belt_rest`,
        protection) so the observation stays coherent. The grade lane is
        re-checked (`Ff`): a cross-lane adoption would invalidate the arm and the
        bin, so such a candidate is rejected like an off-lateral one.
        """
        if not self._reseed or self._triggered or self._refuse_latch is None:
            return
        if self._reseed_left <= 0 or self._reseed_scans_left <= 0:
            return
        if int(self._tick) < int(self._reseed_next_tick):
            return
        self._reseed_scans_left -= 1
        self._reseed_scans += 1
        self._reseed_next_tick = int(self._tick) + int(self._reseed_stride)
        station_x = float(self._trigger_station[0])
        lateral = float(self.trigger_settings.lateral)
        state = self.task.select_target(
            self.spawner.state(),
            reach_anywhere=False,
            lane=int(self._bin_index),
            exclude=set(self._reseed_seen),
        )
        if state is None:
            self._reseed_empty += 1
            self._reseed_note_exhausted()
            return
        index = int(state["index"])
        self._reseed_seen.add(index)
        x = float(state["position"][0])
        if abs(x - station_x) > lateral:
            self._reseed_off += 1
            self._reseed_note_exhausted()
            return
        lane = 0 if state.get("grade") == "A" else 1
        if lane != int(self._bin_index):
            self._reseed_off += 1
            self._reseed_note_exhausted()
            return
        sample = next(
            (s for s in self.spawner.samples if int(s.index) == index), None
        )
        if sample is None:
            self._reseed_empty += 1
            self._reseed_note_exhausted()
            return
        old = self._sample
        position = np.asarray(self.spawner.position(sample), dtype=np.float32)
        velocity = np.asarray(self.spawner.velocity(sample), dtype=np.float32)
        self.spawner.unprotect(int(old.index))
        if self.spawner.protected is not None and int(
            self.spawner.protected
        ) == int(old.index):
            self.spawner.protected = None
        self._sample = sample
        self._goal = np.array(
            [
                *position,
                *velocity,
                float(sample.diameter),
                float(self._bin_index),
            ],
            dtype=np.float32,
        )
        self._belt_rest = self.belt_top + float(sample.diameter) / 2.0
        self.spawner.protect(index)
        self.spawner.protected = index
        self._reseed_left -= 1
        self._reseed_adopted += 1
        self._refuse_latch = None
        self._notes.append(
            f"reseed: adopted index {index} ({sample.category}, x={x:.3f}, "
            f"dx={x - station_x:+.3f}) over index {int(old.index)} "
            f"after {int(self._reseed_scans_max) - int(self._reseed_scans_left)} "
            f"scan(s), budget left {self._reseed_left}"
        )

    def _reseed_note_exhausted(self) -> None:
        """One note per refusal when the scan budget is spent (never repeats)."""
        if self._reseed_scans_left > 0 or self._reseed_exhausted_noted:
            return
        self._reseed_exhausted_noted = True
        self._notes.append(
            f"reseed: no firable candidate in "
            f"{int(self._reseed_scans_max)} scan(s) (lane {self._bin_index}, "
            f"selector empty {self._reseed_empty}, off-lateral/lane "
            f"{self._reseed_off}; {self._refuse_count} refusal(s) so far)"
        )

    def _maybe_end_no_firable(self) -> None:
        """`FRUIT_POLICY_REFUSE_END`: end at the fruit's *departure*.

        Requires a latched provable refusal **and** that the learned close never
        fired from the reset through the fruit passing the station
        (`dy <= -0.05`, the trigger's own downstream gate). That is a measured
        joint closure, not a claim that the policy could never chase the fruit
        downstream afterwards (`PREREG_A1.md` A1): the trigger will never fire
        it, and the shipped learned gate has had the whole approach to do so.
        One fruit-pose read per tick, and only while a refusal is latched and
        the close has not fired (the documented-safe read class).
        """
        latch = self._refuse_latch
        if latch is None or self._policy_close_seen:
            return
        station_x = float(self._trigger_station[0])
        lateral = float(self.trigger_settings.lateral)
        fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
        x = float(fruit[0])
        dy = float(fruit[1]) - float(self._trigger_station[1])
        if abs(x - station_x) <= lateral:
            # The fruit drifted back inside the gate (measured: up to ~13 mm of
            # in-loop lateral displacement, the P1 section 2 open residual), so
            # "no firable fruit" is not claimable any more: skip the end and let
            # the episode take its own course.
            return
        if not no_firable_ready(
            latched=True, policy_close_seen=self._policy_close_seen, dy=dy
        ):
            return
        drift = abs(x - float(latch["x"]))
        self._no_firable = True
        self._notes.append(
            f"no firable fruit: the trigger refuses (candidate x={x:.3f}, "
            f"|dx|={abs(x - station_x):.3f} > lateral {lateral:.3f}; x >= "
            f"{station_x - lateral:.3f} admitted) and the learned close never "
            f"fired (best |jaw-fruit|={self._policy_best_gap * 100:.1f}cm) "
            f"through dy={dy:+.3f} m (the fruit passed the station); x drift "
            f"{drift * 1000:.1f}mm since the latch"
        )
        self._finalize(notes=self._notes)

    def _event_horizon(self, chunk: np.ndarray | None) -> int:
        """Event-triggered execute horizon from chunk-to-chunk continuity.

        The new chunk is sampled at the state after ``_prev_exec`` steps of the
        previous chunk, so new index ``i`` and prev index ``_prev_exec + i`` are
        the same absolute control step. Their mean 7-D arm disagreement over the
        first few indices is a direct continuity read on the clean actions
        (ChunkTrust's stability idea; DVAC's "variance decides the replan" at
        chunk turnover). With the run's online median ``m``: ``hi = 1.5 m``,
        ``lo = 0.5 m``; horizon = min (2) above hi, max (6) below lo, the
        default (4) in between. Test-time only; no retraining.
        """
        if chunk is None or self._prev_chunk is None:
            return self._event_default
        new = np.asarray(chunk, dtype=np.float64)
        prev = self._prev_chunk
        start = int(self._prev_exec)
        window = min(
            self._event_default + 2,
            self._event_max,
            new.shape[0],
            int(prev.shape[0]) - start,
        )
        if window <= 0:
            return self._event_default
        delta = new[:window, :7] - prev[start : start + window, :7]
        continuity = float(np.linalg.norm(delta, axis=1).mean())
        self._event_continuities.append(continuity)
        median = float(np.median(self._event_continuities))
        hi = max(1.5 * median, 1e-4)
        lo = max(0.5 * median, 1e-4)
        if continuity >= hi:
            steps = self._event_min
        elif continuity <= lo:
            steps = self._event_max
        else:
            steps = self._event_default
        self._event_horizons.append(int(steps))
        if os.environ.get("FRUIT_POLICY_EVENT_LOG", "0") == "1":
            self._say(
                f"[event] step={self._step} continuity={continuity:.5f} "
                f"median={median:.5f} horizon={steps}"
            )
        return int(steps)

    def _tracking_action(self, action: np.ndarray, arm) -> np.ndarray:
        """GEM-style tracking half: shift the arm command with the fruit velocity.

        The policy's 7 joint targets are an interaction command in the belt
        frame; adding the joint image of the fruit's measured Cartesian velocity
        for one control tick (``J^+ v dt``, damped least squares, the same
        pseudo-inverse `control.ik_step` uses) makes the end-effector track the
        fruit so the learned action only has to supply the interaction. Default
        off (`FRUIT_POLICY_TRACK=1`); gain and damping are env knobs. Skipped
        once the fruit is attached/held.
        """
        velocity = np.asarray(self.spawner.velocity(self._sample), dtype=float)
        if float(np.linalg.norm(velocity)) < 1e-4:
            return action
        jacobian = self.scene.robot.get_jacobian_matrices().numpy()[
            0, arm.tcp_jacobian_index
        ]
        jac = np.asarray(jacobian[:3, list(arm.arm_dofs)], dtype=float)
        damping = float(os.environ.get("FRUIT_POLICY_TRACK_DAMPING", "1.0e-3"))
        gain = float(os.environ.get("FRUIT_POLICY_TRACK_GAIN", "1.0"))
        dq = jac.T @ np.linalg.solve(
            jac @ jac.T + damping * np.eye(3), velocity / 120.0
        )
        tracked = np.array(action, dtype=float, copy=True)
        tracked[:7] += gain * dq
        return tracked

    def _roll_proprio(self, measured: np.ndarray, window) -> np.ndarray:
        """VLASH state roll-forward: the execution-time proprio under the chunk.

        arXiv 2512.01031: for absolute actions, "the last action in the executed
        sequence directly serves as the estimated future state". ``window`` is
        the slice of the current chunk that will execute while the next chunk is
        sampled (the inference delay); its last action replaces the active
        arm's 7 joint channels and the finger channel, the other arm and the
        two tactile reads stay measured. The rolled state is only fed to the
        sampler; once a chunk is executing, the action applied to the robot is
        still the chunk's own command.
        """
        out = np.array(measured, dtype=np.float32, copy=True)
        if window is None or len(window) == 0:
            return out
        last = np.asarray(window[-1], dtype=np.float32)
        if last.shape[0] < 8:
            return out
        arm = self.task.arms[self._active]
        out[list(arm.arm_dofs)] = last[:7]
        out[22] = float(np.clip(last[7], 0.0, 0.044))
        return out

    def _handoff_action_extras(self, finger: float) -> None:
        """The hybrid evaluator's attach / grasp-primitive branch (P0a)."""
        from .grasp import GraspPrimitive

        arm = self.task.arms[self._active]
        jaw = arm.jaw_centre()
        fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
        near = float(np.linalg.norm(fruit[:2] - np.asarray(jaw[:2], dtype=float))) < 0.06
        if os.environ.get("FRUIT_NO_ATTACH", "0") != "1":
            if finger < 0.030 and near and not self._sample.attached:
                self._sample.held = True
                self.spawner.attach(self._sample, jaw)
            elif finger > 0.040 and self._sample.attached:
                self.spawner.detach(self._sample)
                self._sample.held = False
        elif not self._grasp_done and finger < 0.030 and near:
            primitive = GraspPrimitive(
                self.cfg, self.spawner, arm, self.tactile, self._active,
                waypoints=self.waypoints,
            )
            held = primitive.run(self._sample)
            self._grasp_done = True
            self._say(
                f"[rl]   grasp primitive: {'held' if held else 'failed'} "
                f"({primitive.last_note})"
            )
            if held and os.environ.get("FRUIT_PRIMITIVE_CARRY", "0") == "1":
                carry_and_release(arm, self.cfg, self._bin_index, self.advance)
                self._say(
                    f"[rl]   carry primitive: released at "
                    f"{np.round(self.spawner.position(self._sample), 3).tolist()}"
                )
        if self._sample.attached:
            self.spawner.follow(self._sample, arm.jaw_centre())

    # ------------------------------------------------------------------ #
    # DAgger expert (the scripted pick-phase controller)
    # ------------------------------------------------------------------ #
    def _dagger_action(self, policy_action) -> np.ndarray | None:
        """Return the action to execute; keep the expert label for the recorder.

        One label per decision point (`index 0` of a 4-tick chunk). While the
        expert has control the label is recomputed every tick, like the scripted
        close loop. `_record_tick` writes the label as the frame's ``action``.
        """
        if self._done or self._sample is None:
            return policy_action
        label = None
        if self._step % 4 == 0 or self._step < self._expert_until:
            label = self._expert_action()
            self._expert_label = label
        if self._step < self._expert_until:
            self._ep_expert_ticks += 1
            return label
        if policy_action is None or label is None:
            return policy_action
        self._policy_proposal = np.asarray(policy_action, dtype=np.float32)
        if self._expert_deviation(policy_action, label):
            self._expert_until = self._step + self.dagger.window_steps * 4
            self._ep_interventions += 1
            self._ep_expert_ticks += 1
            return label
        return policy_action

    def _expert_deviation(self, policy_action, expert_action: np.ndarray) -> bool:
        """The HG-DAgger takeover test: joint-space error, plus an early close.

        The scripted line keeps the pads open until the fruit reaches its
        tracking window; a policy that closes before that is deviating even if
        its arm joints are close.
        """
        policy = np.asarray(policy_action, dtype=np.float64).reshape(-1)
        error = float(np.linalg.norm(policy[:7] - expert_action[:7]))
        early_close = bool(expert_action[7] > 0.040 and policy[7] < 0.030)
        return error > float(self.dagger.tolerance) or early_close

    def _expert_action(self) -> np.ndarray:
        """The scripted pick-phase command for the current state [9-D].

        Same shape as the recorded demonstrations: 7 absolute arm joint targets
        (the calibrated grasp pose while the fruit is outside the tracking
        window, then the IK command that tracks the fruit's measured centre) and
        the two equal finger channels (open, then the scripted 60-tick quintic
        close ramp). The window and the ramp knobs are the ones
        `PickAndPlaceTask` reads, so the label is the controller the dataset came
        from; the controller itself lives in the frozen `tasks.py` and is not
        called here because `grasp_carry_place` would run the whole cycle.
        """
        arm = self.task.arms[self._active]
        sample = self._sample
        fruit = np.asarray(self.spawner.position(sample), dtype=float)
        label = np.zeros(max(9, self.action_dim), dtype=np.float32)

        # Tracking window, relative to the pick-station jaw line (`_run_impl`).
        track_start = float(os.environ.get("FRUIT_TRACK_START", "0.05"))
        track_end = -float(os.environ.get("FRUIT_TRACK_END", "0.02"))
        dy = float(fruit[1]) - float(self._expert_jaw_y)
        if self._expert_close_start is None and track_end <= dy <= track_start:
            self._expert_close_start = int(self._step)

        if self._expert_close_start is None:
            # Wait loop of the scripted line: hold the calibrated grasp pose
            # with the pads open (the recorded wait-phase action).
            label[:7] = self._expert_grasp
            finger = float(arm.OPEN)
        else:
            quat = np.asarray(arm.tcp_pose()[1], dtype=float)
            width = float(sample.diameter)
            if os.environ.get("FRUIT_CLOSE_ON_EXTENT", "1") == "1":
                width = float(self.task.pinch_width(sample, quat))
            grip_gap = width * float(os.environ.get("FRUIT_GRIPPER_SQUEEZE", "0.98"))
            ramp = min_jerk_ramp(
                float(os.environ.get("FRUIT_GRIPPER_OPEN", "0.09")),
                grip_gap,
                60,
            )
            index = min(int(self._step - self._expert_close_start), len(ramp) - 1)
            finger = float(arm.gripper_value_for_separation(float(ramp[index])))
            # The close tracks the fruit's measured centre with position-only IK,
            # one step per tick (the same call the scripted close makes). The
            # command is written to the robot here and immediately overwritten by
            # whatever action the caller applies, so this only decides the label.
            arm.hold_quaternion = None
            arm.sync_command_to_measured()
            pad_lift = float(os.environ.get("FRUIT_PAD_LIFT", "0.010"))
            arm.ik_step(
                arm.tcp_target_for_jaw(fruit + np.array([0.0, 0.0, pad_lift]))
            )
            if arm._q_cmd is not None:
                label[:7] = np.asarray(arm._q_cmd, dtype=np.float32)[:7]
        label[7] = label[8] = np.float32(finger)
        return label

    def _record_tick(self) -> None:
        """Record (observation, action) on observation ticks (30 Hz like demos)."""
        if self._recorder is None or not self._recorder.recording:
            return
        if self._observed_step != self._step:
            return
        arm = self.task.arms[self._active]
        dof = np.asarray(self.scene.robot.get_dof_positions().numpy())[0].astype(
            np.float32
        )
        reading = self.tactile.read()
        left = reading.get("left")
        right = reading.get("right")
        observation = {
            "joint_positions": dof,
            "finger_opening": np.array(
                [float(np.mean(dof[list(arm.finger_dofs)]))], dtype=np.float32
            ),
            "goal": self._goal.copy(),
            "tactile": np.array(
                [
                    float(left.normal_force) if left else 0.0,
                    float(right.normal_force) if right else 0.0,
                ],
                dtype=np.float32,
            ),
        }
        if self._last_rgb is not None:
            observation["image_rgb"] = self._last_rgb
        if self._last_depth is not None:
            observation["image_distance_to_image_plane"] = (
                self._last_depth[..., None] if self._last_depth.ndim == 2
                else self._last_depth
            )
        if self._last_mask is not None:
            observation["target_mask"] = (np.asarray(self._last_mask) > 0.5).astype(
                np.uint8
            ) * 255
        observation["fruit_position"] = np.asarray(
            self.spawner.position(self._sample), dtype=np.float32
        )
        label = self._last_action
        if self.dagger is not None and self._expert_label is not None:
            # Standard DAgger aggregation: the frame's label is the expert
            # command for the state the policy visited; the policy's own
            # *proposal* for this state is kept so the takeover statistics can be
            # read off the data (the applied action is the expert's while the
            # expert holds control, so it is not the proposal).
            observation["policy_action"] = (
                np.asarray(self._last_action, dtype=np.float32)
                if self._policy_proposal is None
                else np.asarray(self._policy_proposal, dtype=np.float32)
            )
            label = np.asarray(self._expert_label, dtype=np.float32)
        self._recorder.add(observation, action=label)

    # ------------------------------------------------------------------ #
    # Episode events / primitives
    # ------------------------------------------------------------------ #
    def _episode_events(self) -> bool:
        """Post-step episode bookkeeping; returns True to skip this iteration.

        The handoff teleport is the harness's station hand-off (never used in
        `direct`: the constructor disables its fallback and the trigger decides).
        """
        if self._done or self._sample is None:
            return False
        sample = self._sample
        pos = np.asarray(self.spawner.position(sample), dtype=float)
        z = float(pos[2])
        if z < self.belt_top - 0.25:
            self._notes.append("fruit fell off the line")
            self._finalize(notes=self._notes)
            return True
        if self.presentation == "handoff":
            if not self._handoff_done and float(pos[1]) <= self.cfg.pick_y + 0.10:
                arm = self.task.arms[self._active]
                jaw = np.asarray(arm.jaw_centre(), dtype=float)
                self.spawner.place(
                    sample,
                    np.array(
                        [jaw[0], jaw[1], self.belt_top + float(sample.diameter) / 2.0 + 0.002]
                    ),
                )
                sample.held = True
                for _ in range(20):
                    self.advance(1)
                self._handoff_done = True
                return True
            if z > self._belt_rest + 0.05:
                self._lifted = True
        return False

    def _run_primitive(self) -> None:
        """The contact work: `grasp_carry_place` on the measured fruit."""
        from .tasks import EpisodeResult

        self._decision_step = int(self._step)
        result = EpisodeResult(
            sample_index=self._sample.index,
            category=self._sample.category,
            grade=self._sample.grade,
            arm=self._active,
        )
        # P30-B: publish this episode's model cost for the `[hub]` row. The
        # scripted primitive reads it only for reporting (None = no model).
        self.task.policy_inference_calls = self.inference_calls()
        result = self.task.grasp_carry_place(
            self._active, self._sample, self._bin_index, result, verbose=self.verbose
        )
        self._grasped = bool(result.grasped)
        self._placed = bool(result.placed)
        self._lifted = bool(result.grasped)
        notes = list(self._notes) + list(result.notes)
        if (
            self.presentation == "direct"
            and result.grasped
            and not result.placed
        ):
            # `grasp_carry_place` already carried and released, so this is the
            # harness helper re-run only when a grasp did not end on the belt
            # (the plan's "on res.grasped call carry_and_release"). On a placed
            # episode it would repeat the same arm motion with an empty hand.
            self._say("[rl]   grasp did not land on the belt; re-running carry_and_release")
            carry_and_release(
                self.task.arms[self._active], self.cfg, self._bin_index, self.advance
            )
        self._finalize(notes=notes)

    def _run_scripted(self) -> None:
        """`--ablate scripted`: the demonstration controller runs the episode."""
        self._decision_step = int(self._step)
        state = next(
            (s for s in self.spawner.state() if int(s["index"]) == int(self._sample.index)),
            None,
        )
        if state is None:
            self._finalize(notes=["scripted ablation: target left the line"])
            return
        result = self.task.run(state, self._bin_index, verbose=self.verbose)
        self._grasped = bool(result.grasped)
        self._placed = bool(result.placed)
        self._lifted = bool(result.grasped)
        self._finalize(notes=list(self._notes) + list(result.notes))

    def _finalize(self, notes: list[str] | None = None) -> None:
        if self._done:
            return
        self._ticks = int(round((self._sim_time() - self._episode_t0) * 120.0))
        decision = (
            int(self._decision_step)
            if self._decision_step is not None
            else min(int(self._step), int(self.reward.horizon))
        )
        final = np.asarray(self.spawner.position(self._sample), dtype=float)
        success = bool(self._lifted) and bool(self.cfg.on_output_belt(final))
        reward = self.reward.compute(success, decision)
        notes = list(self._notes if notes is None else notes)
        self._outcome = {
            "episode": self._episode,
            "category": self._sample.category,
            "grade": self._sample.grade,
            "diameter": float(self._sample.diameter),
            "bin_index": self._bin_index,
            "arm": self._active,
            "success": success,
            "grasped": bool(self._grasped),
            "placed": bool(self._placed),
            "lifted": bool(self._lifted),
            "ticks": self._ticks,
            "decision": decision,
            "reward": float(reward),
            "notes": notes,
            "final_position": final.tolist(),
            "presentation": self.presentation,
            "ablate": self.ablate,
            "dagger": self.dagger is not None,
            "interventions": int(self._ep_interventions),
            "expert_ticks": int(self._ep_expert_ticks),
            #: P30-B: model inference calls (action chunks) this episode. The
            #: `[hub]` row reads the same count on the primitive side; this is
            #: the machine-readable copy for the report tools.
            "policy_inferences": int(self.inference_calls()),
        }
        if self._refuse_knobs:
            #: P38 phase 2: the refuse harness's own record (absent when all
            #: four knobs are off, so the shipped outcome dict is unchanged).
            self._outcome["refuse"] = {
                "refusals": int(self._refuse_count),
                "adopted": int(self._reseed_adopted),
                "scans": int(self._reseed_scans),
                "scans_empty": int(self._reseed_empty),
                "scans_off": int(self._reseed_off),
                "budget_left": int(self._reseed_left),
                "policy_close_seen": bool(self._policy_close_seen),
                "no_firable": bool(self._no_firable),
                "latched": self._refuse_latch is not None,
            }
            if self._no_firable:
                # The PREREG's named terminal class. Still a failure
                # (`success=False`) and still in the rate denominator: the
                # endpoint is *attribution*, never elimination.
                self._outcome["outcome"] = "no_firable"
        if self._wait_gate_on:
            # P31-A: the gate's own counters (a gated episode's `policy_inferences`
            # above is already the reduced count). Absent with the gate off, so
            # the shipped outcome dict is unchanged.
            self._outcome["wait_gate_skipped"] = int(self._wait_gate_skipped)
            self._outcome["wait_gate_held_ticks"] = int(self._wait_gate_held)
            self._outcome["wait_gate_resumed"] = bool(self._wait_gate_resumed)
        if self._event:
            horizons = np.asarray(self._event_horizons, dtype=float)
            continuity = np.asarray(self._event_continuities, dtype=float)
            self._outcome["event_chunks"] = int(horizons.size)
            self._outcome["event_horizon_2"] = int((horizons == 2).sum())
            self._outcome["event_horizon_4"] = int((horizons == 4).sum())
            self._outcome["event_horizon_6"] = int((horizons == 6).sum())
            self._outcome["event_mean_horizon"] = (
                float(horizons.mean()) if horizons.size else float("nan")
            )
            self._outcome["event_continuity_median"] = (
                float(np.median(continuity)) if continuity.size else float("nan")
            )
        if self._recorder is not None:
            self._recorder.finish(
                success=success,
                grasped=bool(self._grasped),
                placed=bool(self._placed),
                reward=float(reward),
                ticks=self._ticks,
                notes=notes,
            )
        self.spawner.protected = None
        self._done = True
        # --- P56: the continuous episode -------------------------------------- #
        #: Accumulate this pick into the logical episode and decide whether the
        #: episode continues. The **per-pick** rows below still print for every
        #: pick (one `[rl] episode` row per pick, never zero and never two - that
        #: is what `scripts/113_rl_report.py` and the P54 report parse); the
        #: *episode-level* rows (`[loop]`, the `[cont]` summary and the diag
        #: summaries, whose buffers `_begin_pick` resets) belong to the true end.
        cont = False
        if self._continuous_picks > 0:
            self._picks_done += 1
            self._cont_reward += float(reward)
            self._cont_ticks += int(self._ticks)
            self._cont_placed += int(bool(self._placed))
            cont = self._picks_done < self._continuous_picks
        report = None if cont else self._collect_rtc_report()
        if report:
            self._outcome.update(report)
        if self._loop_timing and not cont:
            self._say(self._loop_episode_row())
        self._say(
            f"[rl] episode {self._episode}: {self._sample.category} "
            f"d={self._sample.diameter * 100:.1f}cm bin={self._bin_index} "
            f"arm={self._active} success={success} grasped={bool(self._grasped)} "
            f"placed={bool(self._placed)} ticks={self._ticks} decision={decision} "
            f"reward={reward:.4f} notes={notes} presentation={self.presentation} "
            f"ablate={self.ablate}"
        )
        if cont:
            self._begin_next_pick(notes)
            return
        if self._retime_on:
            # P52 phase 2: the gate's own per-episode summary, so the duty cycle
            # is readable without re-flowing the per-decision rows. One print,
            # no state; the shipped path never reaches it.
            self._say(self._retime_row())
        if self._emit_diag:
            # P53: the emission census (out of range before/after the clamp, the
            # applied ticks and the policy decisions). One print, no state; the
            # shipped path never reaches it.
            self._say(self._emit_row())
        if self._refuse_knobs:
            # P38 phase 2: the harness's per-episode counters as one row, so
            # the batch is auditable from the log alone (scans, adoptions, the
            # mechanism split of a failed scan, and the terminal class). One
            # print, no state: the shipped path never reaches it.
            self._say(
                f"[refuse] episode {self._episode}: "
                f"refusals={int(self._refuse_count)} "
                f"adopted={int(self._reseed_adopted)} "
                f"scans={int(self._reseed_scans)} "
                f"empty={int(self._reseed_empty)} "
                f"off={int(self._reseed_off)} "
                f"budget_left={int(self._reseed_left)} "
                f"policy_close_seen={int(self._policy_close_seen)} "
                f"no_firable={int(self._no_firable)}"
            )
        if report:
            self._say(
                f"[rtc]   boundaries={report['rtc_boundaries']} "
                f"median={report['rtc_boundary_median']:.4f} "
                f"within={report['rtc_within_median']:.4f} "
                f"step={report['rtc_step_median']:.4f} "
                f"jerk={report['rtc_jerk_median']:.4f} "
                f"switches={report['rtc_switches']} "
                f"decisions={report['rtc_decisions']} "
                f"rate={report['rtc_decision_rate']:.1f}/s "
                f"policy_ms={report['rtc_policy_ms_median']:.1f} "
                f"policy_ms/step={report['rtc_policy_ms_per_step']:.2f} "
                f"control_ms={report['rtc_control_ms_median']:.1f}"
            )
        if self._event:
            self._say(
                f"[event] chunks={self._outcome['event_chunks']} "
                f"h2={self._outcome['event_horizon_2']} "
                f"h4={self._outcome['event_horizon_4']} "
                f"h6={self._outcome['event_horizon_6']} "
                f"mean={self._outcome['event_mean_horizon']:.2f} "
                f"continuity_med={self._outcome['event_continuity_median']:.5f}"
            )
        if self._wait_gate_on and self.wait_gate.diag:
            # P31-A: the gate's per-episode row (pure reporting; one formatting
            # pass over already-materialised ints).
            self._say(self._wait_gate_report())
        if self._align_diag:
            # P34 phase 2: the first-call manipulation check + the fire-zone
            # target-mask counters (pure reporting over already-read values).
            self._say(self._align_report())
        if self._park_diag:
            # P35 phase 2: M1/M2 of the park A/B's manipulation check (pure
            # reporting over the frame the calls already conditioned on).
            self._say(self._park_report())
        if self._spoof_diag:
            # P36 phase 1: the proprio cell's certificate (the 7 indices, the
            # before/after hashes, the untouched-rest hash, the live drift).
            self._say(self._spoof_report())
        if self.dagger is not None:
            decisions = max(1, int(self._step) // 4)
            self._say(
                f"[rl]   dagger: interventions={self._ep_interventions}/{decisions} "
                f"expert_ticks={self._ep_expert_ticks}/{int(self._step)}"
            )
        if self._continuous_picks > 0:
            # P56: the logical episode's totals, printed once at the true end.
            # `StepResult.reward` stays this pick's own reward, so a per-pick
            # consumer is unchanged; the episode total lives in the info dict.
            gaps = [int(g) for g in self._cont_gaps]
            self._outcome["continuous"] = {
                "picks": int(self._picks_done),
                "target_picks": int(self._continuous_picks),
                "picks_placed": int(self._cont_placed),
                "reward_total": float(self._cont_reward),
                "ticks_total": int(self._cont_ticks),
                "gap_ticks": gaps,
                "gap_ticks_mean": (
                    float(np.mean(gaps)) if gaps else float("nan")
                ),
            }
            self._say(
                f"[cont] episode {self._episode}: picks={self._picks_done}/"
                f"{self._continuous_picks} placed={self._cont_placed} "
                f"reward={self._cont_reward:.6f} ticks={self._cont_ticks} "
                f"gap_ticks={np.mean(gaps) if gaps else float('nan'):.1f} "
                f"gaps={gaps}"
            )

    def _begin_next_pick(self, notes: list[str]) -> None:
        """P56: re-target the live belt and start the next pick of the episode.

        Called from `_finalize` **after** the finished pick's outcome row has been
        printed. It clears the feeder's `protected` index (already done by the
        caller), re-runs the **same** selection the reset runs -
        `select_target(..., direct=True)`, which rejects a fruit on an output
        conveyor or above the main belt (`tasks.py:5709-5727`) and therefore
        cannot re-pick the one just placed - and starts pick *k+1* with
        `_begin_pick`, which re-primes `policy.reset()` and restores the
        calibrated `grasp` pose.

        A belt with no candidate ends the episode **honestly** (a note, then the
        normal end); it never raises - the reset's "40 feed rounds" error is not
        available mid-episode, because a real continuous cell that runs dry is a
        result, not an exception.
        """
        gap_t0 = self._sim_time()
        prev_active = self._active
        # The reset's own starvation contract, reused: a selection round is 30
        # ticks of belt travel and the reset allows 40 of them (10 s) before it
        # raises. Mid-episode there is no exception to raise, so the same bound
        # ends the episode - but a **momentary** gap in front of the catch floor
        # (all live fruit already inside it, the next release still upstream)
        # must not end the run: that is what the wait is for, and the census
        # measured 0/11 reset transitions needing a second round, so a wait here
        # is an event worth printing, not the normal path.
        rounds = 0
        while True:
            diag = [] if self._bed_diag else None
            target = self.task.select_target(
                self.spawner.state(), reach_anywhere=False, direct=True, diag=diag
            )
            if target is not None:
                break
            if diag is not None and (rounds == 0 or rounds >= 40):
                # Name the predicate that refused every live fruit. The scripted
                # driver prints the same block on its empty-selection path; the
                # direct env had no census at all before P56.
                self.task.bed_diag_report(self._episode + 1, diag)
            if rounds >= 40:
                self._notes.append(
                    "continuous: no candidate on the belt in 40 feed rounds; "
                    "ending the episode"
                )
                self._say(
                    f"[cont] pick {self._picks_done + 1}/{self._continuous_picks}: "
                    "no candidate on the belt in 40 feed rounds; ending the episode"
                )
                return
            rounds += 1
            self._say(
                f"[cont] pick {self._picks_done + 1}/{self._continuous_picks}: "
                f"waiting for a candidate (round {rounds}/40)"
            )
            for _ in range(30):
                self.advance(1)
        self._begin_pick(
            target, diag=diag, continuation=True, prev_active=prev_active
        )
        gap = int(round((self._sim_time() - gap_t0) * 120.0))
        self._cont_gaps.append(gap)
        #: Tells `act` that the pick it was executing has ended: the remaining
        #: actions of that pick's chunk belong to the *old* pick and must not be
        #: applied to the new one.
        self._pick_boundary = True
        self._say(
            f"[cont] pick {self._picks_done + 1}/{self._continuous_picks}: "
            f"{target['category']} grade={target['grade']} "
            f"y={float(target['position'][1]):+.3f} gap_ticks={gap} "
            f"placed_so_far={self._cont_placed}"
        )

    def _loop_episode_row(self) -> str:
        """One `[loop]` row: the decision period's wall split (P43 L2).

        `FRUIT_LOOP_TIMING=1` only. The stages are `policy` (the model call in
        `sample_chunk`), `render` (`RenderingManager.render()`), `camera` (every
        `get_data` read of the observation plus its mask arithmetic) and
        `other` = the episode wall minus those three (setup/selection, the
        `ik_step`/`_apply` path, `advance` = `SimulationManager.step` +
        `update_app(steps=0)`, and the `push_frame` assembly). Because a
        decision and an observation both happen every 4th control step, the two
        divisors are the same number on the shipped synchronous path.
        """
        wall_ms = max((time.perf_counter() - self._loop_reset_start) * 1e3, 1e-6)
        decisions = max(int(self._loop_counts["decisions"]), 1)
        obs = max(int(self._loop_counts["observations"]), 1)
        policy_ms = self._loop_t["policy_ms"]
        render_ms = self._loop_t["render_ms"]
        camera_ms = self._loop_t["camera_ms"]
        other_ms = max(wall_ms - policy_ms - render_ms - camera_ms, 0.0)
        row = {
            "episode": int(self._episode),
            "wall_s": wall_ms / 1e3,
            "sim_s": int(self._ticks) / 120.0,
            "decisions": int(self._loop_counts["decisions"]),
            "observations": int(self._loop_counts["observations"]),
            "policy_ms_dec": policy_ms / decisions,
            "render_ms_obs": render_ms / obs,
            "camera_ms_obs": camera_ms / obs,
            "other_ms_dec": other_ms / decisions,
            "policy_share": policy_ms / wall_ms,
            "render_share": render_ms / wall_ms,
            "camera_share": camera_ms / wall_ms,
            "other_share": other_ms / wall_ms,
        }
        self._loop_episodes.append(row)
        return (
            f"[loop] ep={row['episode']} wall={row['wall_s']:.1f}s "
            f"sim={row['sim_s']:.1f}s "
            f"sim/wall={row['sim_s'] / row['wall_s']:.2f} "
            f"decisions={row['decisions']} obs={row['observations']} | ms/decision: "
            f"policy={row['policy_ms_dec']:.1f} "
            f"render={row['render_ms_obs']:.1f} "
            f"camera={row['camera_ms_obs']:.1f} "
            f"other={row['other_ms_dec']:.1f} | share: "
            f"policy={row['policy_share']:.1%} "
            f"render={row['render_share']:.1%} "
            f"camera={row['camera_share']:.1%} "
            f"other={row['other_share']:.1%}"
        )

    def _loop_summary(self) -> str:
        """Run-level `[loop]` summary (mean of the per-episode rows)."""
        rows = self._loop_episodes
        n = max(len(rows), 1)

        def _mean(key: str) -> float:
            return sum(float(r[key]) for r in rows) / n

        wall = sum(float(r["wall_s"]) for r in rows)
        sim = sum(float(r["sim_s"]) for r in rows)
        return (
            f"[loop] summary: episodes={len(rows)} wall={wall:.1f}s "
            f"sim={sim:.1f}s sim/wall={sim / max(wall, 1e-9):.2f} "
            f"wall/episode={wall / n:.1f}s | ms/decision: "
            f"policy={_mean('policy_ms_dec'):.1f} "
            f"render={_mean('render_ms_obs'):.1f} "
            f"camera={_mean('camera_ms_obs'):.1f} "
            f"other={_mean('other_ms_dec'):.1f} | share: "
            f"policy={_mean('policy_share'):.1%} "
            f"render={_mean('render_share'):.1%} "
            f"camera={_mean('camera_share'):.1%} "
            f"other={_mean('other_share'):.1%}"
        )

    def _collect_rtc_report(self) -> dict:
        """Episode-level executed-boundary + wall-time stats (empty when off)."""
        if not self._rtc_report:
            return {}
        boundary = np.asarray(self._report_boundary, dtype=np.float64)
        within = np.asarray(self._report_within, dtype=np.float64)
        step = np.asarray(self._report_step, dtype=np.float64)
        jerk = np.asarray(self._report_jerk, dtype=np.float64)
        controls = np.asarray(self._report_control_ms, dtype=np.float64)
        policy = np.asarray(self._report_policy_ms, dtype=np.float64)
        decisions = (
            int(self.rtc.chunks_sampled)
            if self.rtc is not None
            else int(self._report_decisions)
        )
        # Decision rate over the *policy phase* (the steps before the scripted
        # primitive takes over), not the whole episode: the primitive's carry
        # ticks would dilute it (measured: an E=1 episode reads 119/s on its
        # policy steps and 13/s over the full episode).
        seconds = max(int(self._step), 1) / 120.0
        policy_total = float(policy.sum()) if policy.size else 0.0

        def _median(values: np.ndarray) -> float:
            return float(np.median(values)) if values.size else float("nan")

        self._rtc_totals["boundary"].extend(boundary.tolist())
        self._rtc_totals["within"].extend(within.tolist())
        self._rtc_totals["step"].extend(step.tolist())
        self._rtc_totals["jerk"].extend(jerk.tolist())
        self._rtc_totals["control_ms"].extend(controls.tolist())
        self._rtc_totals["policy_ms"].extend(policy.tolist())
        self._rtc_totals["policy_ms_total"] += policy_total
        self._rtc_totals["switches"] += int(boundary.size)
        self._rtc_totals["steps"] += int(self._step)
        self._rtc_totals["decisions"] += decisions
        self._rtc_totals["chunks"] += int(
            self.rtc.chunks_sampled if self.rtc is not None else 0
        )
        return {
            "rtc_boundaries": int(boundary.size),
            "rtc_boundary_median": _median(boundary),
            "rtc_boundary_p90": (
                float(np.percentile(boundary, 90)) if boundary.size else float("nan")
            ),
            "rtc_within_median": _median(within),
            "rtc_within_p90": (
                float(np.percentile(within, 90)) if within.size else float("nan")
            ),
            "rtc_step_median": _median(step),
            "rtc_step_p90": (
                float(np.percentile(step, 90)) if step.size else float("nan")
            ),
            "rtc_jerk_median": _median(jerk),
            "rtc_jerk_p90": (
                float(np.percentile(jerk, 90)) if jerk.size else float("nan")
            ),
            "rtc_switches": int(boundary.size),
            "rtc_decisions": decisions,
            "rtc_decision_rate": decisions / seconds,
            "rtc_policy_ms_median": _median(policy),
            "rtc_policy_ms_p90": (
                float(np.percentile(policy, 90)) if policy.size else float("nan")
            ),
            "rtc_policy_ms_per_step": policy_total / max(int(self._step), 1),
            "rtc_control_ms_median": _median(controls),
        }

    def report_summary(self) -> str | None:
        """Run-level RTC timing/boundary summary; None when reporting is off."""
        if not self._rtc_report:
            # P43 L2: the loop-timing instrument has its own summary and does
            # not need RTC's (the two are independent knobs).
            return self._loop_summary() if self._loop_timing else None
        boundary = np.asarray(self._rtc_totals["boundary"], dtype=np.float64)
        within = np.asarray(self._rtc_totals["within"], dtype=np.float64)
        step = np.asarray(self._rtc_totals["step"], dtype=np.float64)
        jerk = np.asarray(self._rtc_totals["jerk"], dtype=np.float64)
        controls = np.asarray(self._rtc_totals["control_ms"], dtype=np.float64)
        policy = np.asarray(self._rtc_totals["policy_ms"], dtype=np.float64)
        steps = max(int(self._rtc_totals["steps"]), 1)
        decisions = int(self._rtc_totals["decisions"])
        seconds = steps / 120.0

        def _stats(values: np.ndarray, label: str) -> str:
            if not values.size:
                return f"{label}=n/a"
            return (
                f"{label} n={values.size} med={np.median(values):.2f} "
                f"p90={np.percentile(values, 90):.2f} max={values.max():.2f}"
            )

        return (
            f"[rtc] summary: steps={self._rtc_totals['steps']} "
            f"chunks={self._rtc_totals['chunks']} "
            f"decisions={decisions} "
            f"decisions/s={decisions / seconds:.1f} "
            f"switches={self._rtc_totals['switches']} | "
            f"step {_stats(step, 'rad')} | jerk {_stats(jerk, 'rad')} | "
            f"boundary {_stats(boundary, 'rad')} | within {_stats(within, 'rad')} | "
            f"policy_ms {_stats(policy, 'ms')} | "
            f"policy_ms/step {self._rtc_totals['policy_ms_total'] / steps:.2f} | "
            f"control_ms {_stats(controls, 'ms')}"
            # P43 L2: the two instruments are independent switches; when both are
            # on the run prints both rows.
            + (f"\n{self._loop_summary()}" if self._loop_timing else "")
        )

    def _step_result(self) -> StepResult:
        outcome = self._outcome or {}
        return StepResult(
            obs=self._obs_snapshot(),
            reward=float(outcome.get("reward", 0.0)),
            done=bool(self._done),
            info=dict(outcome),
        )

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        """No-op: the driver owns the SimulationApp lifetime."""
