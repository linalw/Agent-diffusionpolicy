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

``FRUIT_EVAL_LATENCY`` (P228, default off) is the **evaluation** knob, not a
policy one: it advances the world `d` control ticks after each decision's
inference returns and before the chunk executes (`sync-hold`, the
LIBERO-Dynamic/ReflexBench protocol), so the latency the shipped loop gets for
free - it never steps the simulator while the model runs - becomes visible.
`auto` uses this machine's measured `act()` wall, an integer is the controlled
sweep, and `0`/unset is byte-identical to the shipped path. It is refused with
`FRUIT_RTC`/`FRUIT_VLASH`, which model the same delay by interleaving.

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

#: The control period (120 Hz) the env, the scripted primitive and the latency
#: accounting all run at. `tasks.CONTROL_DT` is the same number, but this module
#: cannot import `tasks` at module scope (it pulls Isaac Sim in) and the
#: offline selfcheck executes the latency injector on a stub - the leg pins the
#: equality against `tasks.py`'s own literal instead.
CONTROL_DT = 1.0 / 120.0
from .policy.data import (
    BELT_TAU_DEFAULT,
    BELT_TAU_ENV,
    belt_speed_scalar,
    goal_aux_enabled,
    speed_channel_enabled,
)
from .policy.trigger import TriggerSettings, should_fire, x_edge_refusal
from .perception import (
    CameraModel,
    _calibration_bias,
    _fit_sphere,
    _fit_sphere_known_radius,
    _fit_spheroid,
    workcell_roi,
)
from .tracking import FruitTracker, track_config_from_env

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
#: P96 (metadata-only follow): `tasks.py` gains the **pre-pose clearance**
#: resolver + its station solve (`FRUIT_BIARM_PREPOSE_CLEAR`, two-line only).
#: The direct/policy presentation never constructs a `CoopSession`, so
#: `two_line_enabled()` is False there and the resolver reads `scope-off`.
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
#: P91 follow is **metadata-only** as well: the take-off validation ramp
#: resolves through `Task.two_line_enabled()` (a `CoopSession` predicate this
#: env never satisfies) and the manifest builder passes `two_line=False`, so
#: the direct path keeps its 40-tick probe / 10 mm ramp unless an explicit
#: `FRUIT_DYNAMIC_PROBE_TICKS`/`FRUIT_DYNAMIC_PROBE` says otherwise.
#: P95 follow is **metadata-only**: `FRUIT_FRUIT_TRACE` / `..._ARM` / `..._NOOP`
#: are a **diagnostic** read by `PickAndPlaceTask.__init__` and hooked in
#: `_step_sim`; with the knob unset the hook is one attribute read per tick and
#: nothing is read, written or measured, so the direct path is unchanged
#: (`logs/p95/RESULTS.md` section 0 proves it with the scripted stream instead).
#: P98 follow is **metadata-only** (the `P97` revert): the clearance pre-pose's
#: two-line default goes back to False, and this env never constructs a
#: `CoopSession`, so the resolver reads `scope-off` here in both phases. No
#: direct/policy behaviour moves.
#: P107 follow is **metadata-only**: `cage_hand.py` is a fifth hand kind behind
#: `FRUIT_GRIPPER_KIND=cage4` (default off) and `tasks.py`'s changes are the
#: `RIGID_TOOL_HANDS` predicate (the shipped `openarm` hand is a *subset*, so its
#: behaviour cannot move), the hand-aware `_pad_standoff`/`_fingertip_offset`/
#: `_hand_separation` (no shipped hand carries those attributes), `pinch_width`'s
#: radial branch (same predicate) and one per-tick `track_arm` attribute lookup.
#: This env never constructs a cage, so no direct/policy behaviour moves - proven
#: on the scripted side by `scripts/accept.sh`'s 421/421 byte-identical `[fruit]`
#: stream (`logs/p107/RESULTS.md` section 5).
TASKS_MD5 = "e3795cf43d9fd0718219ead6c04a261b"

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


def resolve_eval_latency(raw: str | None) -> tuple[str, int]:
    """P228 (Stage 0): ``FRUIT_EVAL_LATENCY`` -> the latency the **world** pays.

    The shipped direct loop is synchronous and **free**: `sample_chunk` runs the
    model while `SimulationManager` is never stepped, so the 26 ms of wall time
    costs zero belt travel. A real cell pays it (at 0.12 m/s, 26 ms is 3.2 mm),
    and the benchmark critique in the record's paper pass (ReflexBench;
    LIBERO-Dynamic) is exactly that a paused world inflates the metric.

    This knob makes the pause visible: after a decision's inference returns, the
    environment advances that many control ticks with the arm **holding still**
    (`sync-hold`, LIBERO-Dynamic's protocol) before the chunk is executed - so
    the chunk is applied to a world it was not computed for.

    * unset / ``""`` / ``0`` - off, the shipped path byte for byte;
    * ``auto`` - ``round(measured act() wall / (1/120 s))``, i.e. this machine's
      real latency (26.4 ms at DDIM-16 is 3 ticks);
    * a positive integer - that many control ticks (the controlled sweep);
    * anything else (negative, non-numeric, non-finite) is a hard error, so a
      typo cannot read as "off".

    Refused together with ``FRUIT_RTC``/``FRUIT_VLASH``: the chunker models the
    same delay by interleaving denoising with execution, and counting both would
    double it.
    """
    text = "" if raw is None else str(raw).strip()
    if not text or text == "0":
        return ("off", 0)
    if text.lower() == "auto":
        return ("auto", 0)
    try:
        ticks = int(text)
    except ValueError:
        raise ValueError(
            f"FRUIT_EVAL_LATENCY={raw!r} is not 'auto', '0' or a whole number of "
            "control ticks"
        ) from None
    if ticks < 0:
        raise ValueError(
            f"FRUIT_EVAL_LATENCY={raw!r}: a negative latency is not a thing"
        )
    return ("fixed", ticks)


def resolve_skip_late(raw: str | None) -> float:
    """P227aa: ``FRUIT_SKIP_LATE`` -> refuse a catch that has no lead left [s].

    The owner's cell semantics: on a real line **several arms share one belt, and
    each takes the fruit it can serve** - nothing is obliged to catch every
    passing fruit. This is the software form of that rule. When the arrival
    trigger fires with `t_arrive` below this many seconds the fruit is already
    inside the window a descent can meet, so the attempt is ended **on this tick**
    instead of chasing it: the arm does not run the doomed catch-up (measured:
    failed attempts carry a 1.18 rad joint range and 44 direction reversals p50
    against 0.10 and 9 on placements - the only "weird" motion this cell shows),
    and in a continuous episode the loop moves straight to the next pick.

    ``0``/unset is the shipped path (every fruit is attempted, byte for byte).
    Strict parsing, the `resolve_target_rate` precedent: a non-number, a negative
    or a non-finite value is a hard error so a typo cannot read as "off".
    """
    text = "" if raw is None else str(raw).strip()
    if not text:
        return 0.0
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"FRUIT_SKIP_LATE={raw!r} is not a number") from None
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(
            f"FRUIT_SKIP_LATE={raw!r} must be a finite number >= 0 (0 = off)"
        )
    return value


def resolve_target_rate(raw: str | None) -> float:
    """P207: ``FRUIT_POLICY_TARGET_RATE`` -> the emitted joint target's rate cap.

    Units are **radians per second of commanded joint travel**, the same unit a
    drive's velocity limit uses. ``0``/unset is the shipped path: the policy's
    7 absolute joint targets reach `set_dof_position_targets` untouched.

    The measured defect this is for (`logs/p202_video.log`, `logs/p204_video.log`):
    the emitted target's per-waypoint step is p50 0.018-0.021 rad but its p95 is
    0.055-0.19 and its **maximum 0.275-3.37 rad**, while the arm only achieves a
    p95 of 0.27-1.98 rad/s. A target step that large is a command transient no
    servo can follow smoothly; the arm's visible response is the "weird pose".
    A rate cap spreads the step over successive ticks, so the drive sees a ramp
    rather than a step. It is not a filter: a request inside the cap is emitted
    unchanged, so the slow trajectory the demonstrations teach is not delayed.

    Strict parsing (the C1/C2 precedent): a non-number, a negative, or a
    non-finite value is a hard error - a typo must not read as the shipped path
    and be published as a null result. ``0`` is the explicit off token.
    """
    text = "" if raw is None else str(raw).strip()
    if not text:
        return 0.0
    try:
        value = float(text)
    except ValueError:
        raise ValueError(
            f"FRUIT_POLICY_TARGET_RATE={raw!r} is not a number"
        ) from None
    if not math.isfinite(value):
        raise ValueError(
            f"FRUIT_POLICY_TARGET_RATE={raw!r} must be finite"
        )
    if value < 0.0:
        raise ValueError(
            f"FRUIT_POLICY_TARGET_RATE={raw!r} must be >= 0 rad/s "
            "(0 is the shipped uncapped path)"
        )
    return value


def rate_limit_target(prev, request, rate: float, dt: float = 1.0 / 120.0):
    """P207: one step of a per-joint rate limiter (rad/s), pure arithmetic.

    ``rate <= 0`` returns ``request`` **unchanged** - the shipped path, element
    for element, so an unarmed run is not "the same arithmetic". With a positive
    rate each joint moves from ``prev`` toward ``request`` by at most
    ``rate * dt``, and a request already inside that ball is emitted exactly.
    The return is a new float64 array; neither argument is written.
    """
    req = np.asarray(request, dtype=np.float64)
    if rate <= 0.0:
        return req
    if prev is None:
        return req
    base = np.asarray(prev, dtype=np.float64)
    if base.shape != req.shape:
        raise ValueError(
            f"rate_limit_target: shape mismatch {base.shape} against {req.shape}"
        )
    limit = float(rate) * float(dt)
    return base + np.clip(req - base, -limit, limit)


def resolve_ensemble_alpha(raw: str | None) -> float:
    """P210: ``FRUIT_POLICY_ENSEMBLE`` -> the new chunk's weight in the overlap.

    ``0``/unset is the shipped path: the chunk is executed as sampled. A value in
    ``(0, 1]`` blends the new chunk's overlapping waypoints with the previous
    chunk's remaining ones (ACT-style temporal ensembling), so a stochastic
    re-plan does not replace the old prediction at every boundary. Strict, so a
    typo cannot read as the shipped path.
    """
    text = "" if raw is None else str(raw).strip()
    if not text:
        return 0.0
    try:
        value = float(text)
    except ValueError:
        raise ValueError(
            f"FRUIT_POLICY_ENSEMBLE={raw!r} is not a number"
        ) from None
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(
            f"FRUIT_POLICY_ENSEMBLE={raw!r} must be in [0, 1] "
            "(0 = the shipped un-averaged chunk)"
        )
    return value


def ensemble_action_chunk(prev, new, steps: int, alpha: float):
    """P210: average the overlapping part of two consecutive chunks.

    The first ``steps`` waypoints of ``new`` describe the same future control
    steps as ``prev[steps:steps+overlap]`` (the part of the previous chunk that
    was **not** executed). The output keeps ``new`` outside the overlap and uses
    ``alpha * new + (1-alpha) * prev`` inside it. Pure arithmetic, no simulator
    read; ``alpha <= 0``, ``prev is None`` or a shape mismatch returns ``new``
    unchanged (the shipped path).
    """
    new_arr = np.asarray(new, dtype=np.float64)
    if alpha <= 0.0 or prev is None:
        return new_arr
    prev_arr = np.asarray(prev, dtype=np.float64)
    if prev_arr.shape != new_arr.shape:
        return new_arr
    horizon = int(new_arr.shape[0])
    steps = int(steps)
    overlap = min(steps, horizon - steps)
    if overlap <= 0:
        return new_arr
    out = new_arr.copy()
    out[:overlap] = (
        float(alpha) * new_arr[:overlap]
        + (1.0 - float(alpha)) * prev_arr[steps:steps + overlap]
    )
    return out


def close_phase_trigger(dy: float, hi: float, lo: float) -> bool:
    """P216: the phase close's along-belt window, **two-sided**.

    The shipped trigger was ``dy <= hi``. A fruit that has gone **behind** the hand
    has a negative ``dy``, so the condition was true at -0.44 m as well - measured
    on the small-fruit cells (`[close] xy=442 mm`, `[fire] dy=-442 mm`): the phase
    gate closed the pads when the fruit was half a metre away. ``lo=-inf`` is the
    shipped path exactly; a finite ``lo`` requires the fruit to be within
    ``[lo, hi]`` of the jaw.
    """
    return bool(float(lo) <= float(dy) <= float(hi))


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


def score_endpoint() -> str:
    """Which event the direct episode scores (`FRUIT_SCORE_ENDPOINT`).

    P142. ``final`` (the shipped default) is "the payload is on an output line
    when the episode ends"; ``release`` is "the task released it onto the line"
    (``lifted and placed``). They differ only when a placed payload leaves the
    slab before the finalize - which `FRUIT_OUTPUT_RAILS=none` (P71) makes
    possible, and which is why a direct run can read `placed=True success=False`.
    Strict, so a typo is an error instead of a silently different metric.
    """
    endpoint = os.environ.get("FRUIT_SCORE_ENDPOINT", "final").strip().lower()
    if endpoint not in ("final", "release"):
        raise ValueError(
            f"FRUIT_SCORE_ENDPOINT={endpoint!r} is not 'final' or 'release'"
        )
    return endpoint


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


def carry_and_release(arm, cfg, bin_index: int, advance, steps: int = 220,
                      place_xy: tuple[float, float] | None = None) -> None:
    """Post-grasp primitive copied from ``scripts/60_eval_policy.py``.

    The same Cartesian path to the output-belt drop point, then the pads open
    over the moving belt. Only used by the ``direct`` path's fallback below: the
    task's own ``grasp_carry_place`` already carries and releases, so this is
    the harness helper re-run when a grasp did not end on the output belt.

    ``place_xy`` (P121) is the armed instruction's destination target; with an
    instruction the id is a destination, not an index into the shipped two-lane
    drop points (a third destination would raise `IndexError` otherwise). Unset
    is the shipped expression, byte for byte.
    """
    if place_xy is None:
        px, py = cfg.output_belt_drop_points[bin_index]
    else:
        px, py = place_xy
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


def direct_dispatch(target: dict, armed: bool, sort_destination, arm_for_destination):
    """The direct env's ``(destination, arm)`` for one selected fruit (P121).

    Un-instructed this is the shipped expression, byte for byte: **grade A ->
    block 0 -> the left arm, everything else -> block 1 -> the right arm** - the
    policy's trained interface, where the arm is the grade and the goal's
    ``bin_index`` is that lane. Armed, the destination is the instruction's
    decision and the arm is the capability map's answer, so a fruit can be
    carried by the arm its *destination* needs rather than the arm its grade
    named.

    The instruction's selector has already refused `skip`/unmatched fruits
    (`tasks.select_target`'s `_sort_admits`), so a non-int here is a caller bug:
    raising is the P114 capability rule (refuse, never mis-sort).
    """
    if not armed:
        bin_index = 0 if target.get("grade") == "A" else 1
        return bin_index, "left" if bin_index == 0 else "right"
    destination = sort_destination(target)
    if not isinstance(destination, int):
        raise ValueError(
            f"[sort] REFUSED: the selected fruit {target.get('index')} has no "
            f"servable destination ({destination!r}); the instructed selector "
            "must not hand it to the policy"
        )
    return int(destination), arm_for_destination(int(destination))


def unseen_destinations(assigned) -> list[int]:
    """Destination ids an instruction maps that the two shipped lanes do not have.

    P121: the goal vector's last element is ``bin_index``, a **policy input**.
    For destinations 0/1 the value equals the lane the arm will use, so the
    instructed run is the trained interface; a third destination is a value the
    policy has never seen. It runs only with ``FRUIT_SORT_THIRD_DEST=1`` and is
    reported as OOD, never assumed safe.
    """
    return sorted(
        {int(d) for d in assigned if isinstance(d, int) and int(d) not in (0, 1)}
    )


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
            # P145: `truth` or `perception` - a store must not be mixed with one
            # whose goal is a different function of time.
            "goal_source": str(meta.get("goal_source", "")),
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
        if os.environ.get("FRUIT_SORT_INSTRUCTION", "").strip():
            # P121: the instruction is **direct-only**. The scripted cell (P114/
            # P115) already dispatches by destination; the handoff presentation
            # keeps its own grade lane (`60_eval_policy.py` computes the bin
            # itself and never touches this env), so an instruction there would
            # be silently ignored - refuse instead.
            if presentation != "direct":
                raise ValueError(
                    "FRUIT_SORT_INSTRUCTION is direct-only in rl_env (the handoff "
                    "presentation has no instruction dispatcher; P121 scopes the "
                    "env routing to presentation='direct')"
                )
        self._sort_ood_dest = (
            os.environ.get("FRUIT_SORT_THIRD_DEST", "0").strip() == "1"
        )
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
        # P141 (P2 of the plan): both are latency knobs, so they are readable
        # from the environment for an A/B without editing the entry scripts.
        # `execute_steps` is how many of the chunk's actions are applied per
        # inference (4 = one replan per 33 ms of sim time); `ddim_steps` is the
        # denoising budget. Defaults are the shipped values, so an unset
        # environment is byte-identical.
        self.execute_steps = int(
            os.environ.get("FRUIT_POLICY_EXEC_STEPS", str(execute_steps))
        )
        self.ddim_steps = int(
            os.environ.get("FRUIT_POLICY_DDIM", str(ddim_steps))
        )
        if self.execute_steps < 1 or self.ddim_steps < 1:
            raise ValueError(
                f"execute_steps={self.execute_steps} and ddim_steps="
                f"{self.ddim_steps} must both be >= 1"
            )
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
        #: P145d.4: the **commanded** finger as an observation channel (the
        #: measured finger aliases the loaded close: command 0.027 vs 0.034 both
        #: read ~0.033). Deployment uses its own last command, which is what the
        #: training stream records as the action's finger channel. Off by default.
        self._cmd_channel = os.environ.get("FRUIT_OBS_CMD", "0") == "1"
        #: P141 goal auxiliary pair: `(v_belt, a_belt)` appended to the 8-D goal
        #: when `FRUIT_OBS_GOAL_AUX=1`. The goal is otherwise a selection-time
        #: snapshot; these two dims are **refreshed every tick** from the same
        #: encoder the trigger reads, because the quantity they carry is the
        #: belt's *state*, not the fruit's. `a_belt` runs the same low-passed
        #: derivative the store's loader runs (`data.belt_accel_trace`), so a
        #: collection store and this loop assemble the same function.
        self._goal_aux = goal_aux_enabled()
        #: P143 diag (default off): the closest the jaws ever came to the target
        #: fruit and the smallest finger command the policy emitted. Both are the
        #: numbers `should_fire` already has on every tick it runs, so this adds a
        #: `min()` and no read - and it answers "did the model even try to grasp"
        #: without a per-tick trace.
        self._goal_source = os.environ.get("FRUIT_GOAL_SOURCE", "truth").strip().lower()
        if self._goal_source not in ("truth", "perception", "truth_moving"):
            raise ValueError(
                f"FRUIT_GOAL_SOURCE={self._goal_source!r} is not 'truth' or 'perception'"
            )
        #: P145: no handover -> the primitive never runs, so `grasped`/`placed` come
        #: from the **fruit's own motion** instead of the primitive's result.
        self._no_handover = os.environ.get("FRUIT_POLICY_HANDOVER", "1").strip() == "0"
        #: P145b: where the direct episode **starts**. `grasp` is the shipped
        #: waypoint; `wait` is the demonstrations' frame-0 pose (measured from
        #: `demos_v11`, `configs/waypoints.json`'s `wait`). The two differ by ~0.35
        #: rad: the shipped start is the scripted line's *close* pose, so the
        #: policy's first observation was a state the demos only reach at the
        #: close, with the fruit still far upstream.
        #: P145d: `FRUIT_ACTION=jaw` makes the policy's action the **task-space**
        #: target `[jaw xyz, finger]`, applied by the same position-only `ik_step`
        #: the scripted close uses (the P145d pre-check: 5.1 mm systematic, 0.2 mm
        #: spread). Default off: the shipped 9-D joint action, byte for byte.
        self._action_jaw = os.environ.get("FRUIT_ACTION", "").strip().lower() in (
            "jaw", "cartesian", "tcp"
        )
        #: `FRUIT_ACTION=tcp` is the **TCP** command (the recorded `cmd_tcp`):
        #: the env applies it with `ik_step(target)` directly. `jaw` is the older
        #: jaw-point action, which needs `tcp_target_for_jaw`. Applying a TCP
        #: action through `tcp_target_for_jaw` adds the ~78 mm tool offset twice
        #: (P145d.1, found by the review agent).
        self._action_tcp = os.environ.get("FRUIT_ACTION", "").strip().lower() == "tcp"
        #: P145d.8: the joint-**delta** action. `FRUIT_ACTION=dq` makes the
        #: policy's 7 arm channels a per-waypoint step from the *measured*
        #: joints (`q_target = q_meas + dq`), i.e. a residual servo. The
        #: measured failure this answers: with absolute targets the direct loop
        #: commands the band-mean aim (jaw x 0.27 for a fruit at 0.225) on
        #: every episode, because the absolute endpoint is what the demos average.
        self._dq_action = os.environ.get("FRUIT_ACTION", "").strip().lower() == "dq"
        #: P145d.13: the **chunk-relative** joint action (`FRUIT_ACTION=rel`).
        #: The chunk's 16 waypoints are offsets from the window's first frame;
        #: the env re-anchors them to the measured joints at the chunk's start,
        #: so the model predicts the motion's shape and cannot under-execute it
        #: by anchoring at its own absolute bias (measured 35 % on the lateral
        #: aim, 42 % on the post-close tracking hold).
        self._rel_action = os.environ.get("FRUIT_ACTION", "").strip().lower() == "rel"
        #: P157: the **position+velocity** action (`FRUIT_ACTION=posvel`). The
        #: action is `[pos(7), fing, fing, delta(7)]`; the delta is the demos'
        #: per-frame command velocity, and the env leads the position command by
        #: `FRUIT_ACTION_DELTA_LEAD` frames of it (default 1.0). The contact
        #: phase's hold is a velocity task (the demos track the belt at 0.97 of
        #: its speed while a position action under-executes to 35-42 %), and a
        #: feed-forward of the position's *own* velocity is a null because that
        #: velocity is already ~0 - the supervised delta is not.
        self._posvel_action = os.environ.get("FRUIT_ACTION", "").strip().lower() == "posvel"
        #: P171: the **hybrid 12-D** action `[pos(7), fing, fing, jaw(3)]`: the
        #: joint form for the approach and the latch (it times the catch), the
        #: free-wrist jaw form for the descent's last 2-5 cm (it reconfigures).
        #: The phase is the committed ramp's clock (`_jaw_now`), so one model owns
        #: both forms on one state distribution.
        self._hybrid_action = os.environ.get("FRUIT_ACTION", "").strip().lower() == "hybrid"
        #: P172: the sample-averaging ensemble (`FRUIT_POLICY_ENSEMBLE_K`, default
        #: 1 = the shipped single draw, byte-identical). `..._DIAG=1` prints one
        #: `[ens]` row per decision.
        #: P173: the **per-tick contact servo**. The chunked policy decides *when*
        #: to take the catch (its phase gate and the committed ramp own the
        #: finger); the last 60 ticks of the aim are served by a position-only
        #: differential-IK update at the control rate, aimed at the **perceived**
        #: fruit (the P135/P145 tracker) - the scripted catch-up's form, driven by
        #: vision instead of truth. Default off: unset is the shipped path.
        self._contact_servo = os.environ.get("FRUIT_CONTACT_SERVO", "0").strip() == "1"
        self._servo_lead = float(os.environ.get("FRUIT_CONTACT_SERVO_LEAD", "0.10") or 0.10)
        self._servo_seat = float(os.environ.get("FRUIT_CONTACT_SERVO_SEAT", "0.070") or 0.070)
        self._servo_diag = os.environ.get("FRUIT_CONTACT_SERVO_DIAG", "0").strip() == "1"
        #: P178 bench only: `truth` aims the contact servo at the rigid body
        #: instead of the estimator, to separate a perception defect from a
        #: geometry one on one arm. Never shipped (default `percept`).
        self._servo_truth = (
            os.environ.get("FRUIT_CONTACT_SERVO_SOURCE", "percept").strip().lower()
            == "truth"
        )
        #: The servo's own window, independent of the finger ramp's: the shipped
        #: catch-up has a **200-tick reach budget at ~1 mm/tick** (`P48`), and the
        #: measured lateral offset at the latch is 75-86 mm, so a 60-tick window
        #: cannot close it (P173's first cell: the aim was converging at 0.8-2.5
        #: mm/tick when the ramp's clock expired).
        self._servo_ticks = int(os.environ.get("FRUIT_CONTACT_SERVO_TICKS", "160") or 160)
        #: The **alignment gate**: the committed ramp (and so the close) may not
        #: start until the aim is actually reached. The shipped ramp latches on a
        #: *one-dimensional* criterion (the jaw's y within `FRUIT_CLOSE_RAMP_DY` of
        #: the fruit's y) while the lateral offset at the latch is measured at
        #: 75-86 mm - so the fingers closed on air 8 cm to the side. With the
        #: gate the hand swings in first and closes where the fruit is.
        #: P182b: the lead is **per arm**, because the two arms' reach bands sit on
        #: opposite sides of the fruit's path (R10-A's intercept map: left
        #: y in [0.00, +0.10], right [-0.10, 0.00]), so the same lead leaves the
        #: right arriving later in the close. Measured at the latch through
        #: `dlat` (the payload's distance from the tool axis, against the plate's
        #: 30.5 mm half-width): right **33.5 mm at lead 0.10** (no contact, F=0) and
        #: **19.1 mm at 0.20** (53.7 N, n=2). The all-right arm reads 0/4 -> 4/4 at
        #: seed 202 and 2/4 at 404; on the mixed supply the right goes 0/6 -> 3/5
        #: and the left falls 6/10 -> 3/11, i.e. one global number cannot serve
        #: both. Defaults to `..._LEAD`, so unset is the shipped single value.
        self._servo_lead_right = float(
            os.environ.get("FRUIT_CONTACT_SERVO_LEAD_RIGHT", "") or self._servo_lead
        )
        self._servo_gate = float(os.environ.get("FRUIT_CONTACT_SERVO_GATE", "0.030") or 0.030)
        #: How far upstream (metres of along-belt distance) the servo takes the
        #: arm. The measured lateral offset at the latch is 75-86 mm and the wrist
        #: moves ~1 mm/tick, so the correction must start before the fruit is at
        #: the station: the shipped catch-up's own lead is ~1.5-2 s of belt travel.
        self._servo_arm_dy = float(os.environ.get("FRUIT_CONTACT_SERVO_ARM_DY", "0.20") or 0.20)
        #: P198: how far **downstream** the fruit may already be when the servo
        #: arms [m]. The measured failure armed at `dy` = -0.24 m and chased; 0.02
        #: keeps a fruit level with the jaw, refuses one that has gone by.
        self._servo_behind_tol = float(
            os.environ.get("FRUIT_CONTACT_SERVO_BEHIND_TOL", "0.02") or 0.02
        )
        #: P175: the **place as a measured-target loop** (opt-in). The destination
        #: is the task's own `jaw_target("place{bin}")` - a pose the cell knows, not
        #: truth about the fruit - and the loop is the same form as the contact
        #: servo: lift clear, transit over the place point, lower, release. The
        #: measured reason it exists: the chunked policy carries ~48 mm of error per
        #: decision over a ~0.9 m transit (P173b) and never emits the release in the
        #: loop (P174), so the learned policy owns the *decisions* and this owns the
        #: centimetres. Default off.
        self._place_servo = os.environ.get("FRUIT_PLACE_SERVO", "0").strip() == "1"
        self._place_drop = float(os.environ.get("FRUIT_PLACE_SERVO_DROP", "0.10") or 0.10)
        self._place_diag = os.environ.get("FRUIT_PLACE_SERVO_DIAG", "0").strip() == "1"
        #: P184: the place transit's own speed limit [m/s] (0 = the shipped direct
        #: aim, i.e. the IK's own clip). The measured motive: a soft fruit's hold
        #: grows 72 -> 96 mm inside the ~300-tick transit at 60 N.
        self._place_vmax = float(os.environ.get("FRUIT_PLACE_SERVO_VMAX", "0") or 0.0)
        #: P212: the place transit's speed is **per arm**. The adopted 0.20 m/s
        #: is a global measured peak (P173: 0.15 -> 8/16, 0.20 -> 14/16, 0.25 ->
        #: 7/16), but the two arms' paths and failure classes differ (right ~48 %,
        #: left ~70 %). An arm that places a payload through a longer transit can
        #: be slowed without touching the other arm; unset falls back to the
        #: global value, so every shipped run is unchanged.
        self._place_vmax_left = float(
            os.environ.get("FRUIT_PLACE_SERVO_VMAX_LEFT", "") or self._place_vmax
        )
        self._place_vmax_right = float(
            os.environ.get("FRUIT_PLACE_SERVO_VMAX_RIGHT", "") or self._place_vmax
        )
        #: P184: the transit's clearance above the belt top [m] (0.30 shipped).
        self._place_lift = float(os.environ.get("FRUIT_PLACE_SERVO_LIFT", "0.30") or 0.30)
        #: P176: the **real-jaw clamp-force spec** on this interface
        #: (`FRUIT_FINGER_MAXFORCE_DIRECT=<N>`, default 0 = the shipped build
        #: cap). A runtime write of the active arm's `joint1` drive cap for the
        #: whole attempt, restored at the end - the direct path only, so the
        #: scripted acceptance, the collector and the hybrid canary never read it
        #: and owe no reference. It is the hardware question in its own units:
        #: *what force must a real jaw deliver at the cycle's contact for this
        #: payload class to survive the carry?* The measured backdrop is P76's
        #: ladder (the pads are back-driven to their open stop below 30 N and the
        #: pry is deleted at 60 N) and P120's null of the *global* cap on the
        #: scripted line, where the count is dominated by other classes.
        self._finger_cap_direct = float(
            os.environ.get("FRUIT_FINGER_MAXFORCE_DIRECT", "0") or 0.0
        )
        #: P215: a **size-dependent** direct clamp. The 60 N real-jaw spec is
        #: the large-fruit setting; the small-fruit class (3.0-3.4 cm) may be
        #: squeezed out at that force. `..._SMALL` overrides the cap only for a
        #: fruit at/below `..._SMALL_DIA` (default 0.040 m); 0/unset keeps the
        #: global cap on every fruit, so the shipped path is unchanged.
        self._finger_cap_small = float(
            os.environ.get("FRUIT_FINGER_MAXFORCE_DIRECT_SMALL", "0") or 0.0
        )
        self._finger_cap_small_dia = float(
            os.environ.get("FRUIT_FINGER_MAXFORCE_DIRECT_SMALL_DIA", "0.040") or 0.040
        )
        self._finger_cap_saved: dict[str, float] = {}
        self._servo_on = False
        self._servo_last_aim = None
        self._place_phase = 0
        self._place_open = 0.0
        self._place_aim = None
        self._finger_was_closed = False
        self._scored_release = False
        self._close_ramp_reported = False
        self._close_ramp_last = -1
        self._ensemble_k = max(1, int(os.environ.get("FRUIT_POLICY_ENSEMBLE_K", "1") or 1))
        self._ensemble_diag = os.environ.get("FRUIT_POLICY_ENSEMBLE_DIAG", "0").strip() == "1"
        #: P177: one `[close-hold]` row per attempt with the **measured** pad span
        #: at the end of the committed close ramp (reporting only, default off).
        self._close_ramp_diag = os.environ.get("FRUIT_CLOSE_RAMP_DIAG", "0").strip() == "1"
        #: P192: the close's **force target** [N] (0 = off, the shipped position
        #: ramp). The force-controlled form keeps closing until the measured pinch
        #: reaches it - the form `docs/END_EFFECTOR_DECISION.md` names.
        #: P193b: the **acquisition window** [m]: the model's own finger close is
        #: honoured only while the jaw-fruit gap is inside it. `0` = off (the
        #: shipped path). The census's successes fire at 106-116 mm; the failures
        #: at 1-69 mm (late) or not at all.
        self._fire_logged = False
        self._close_gap_lo = float(os.environ.get("FRUIT_CLOSE_GAP_MIN", "0") or 0.0)
        self._close_gap_hi = float(os.environ.get("FRUIT_CLOSE_GAP_MAX", "0.16") or 0.16)
        self._close_gap_diag = os.environ.get("FRUIT_CLOSE_GAP_DIAG", "0").strip() == "1"
        #: P194: one `[fire]` row per attempt at the model's close decision (or at
        #: the attempt's end when it never asked) - the acquisition class's own
        #: instrument. Reporting only, default off.
        self._fire_diag = os.environ.get("FRUIT_FIRE_DIAG", "0").strip() == "1"
        #: P202: `FRUIT_EPISODE_END=release` ends the episode on the release event
        #: (the moment the score is taken under `FRUIT_SCORE_ENDPOINT=release`), so
        #: the policy does not idle-and-twitch for the rest of the horizon.
        #: Default `horizon` = the shipped behaviour.
        self._episode_end_release = (
            os.environ.get("FRUIT_EPISODE_END", "").strip().lower() == "release"
        )
        #: P203: the `release` **score endpoint defines the attempt as finished at
        #: the release** (the owner's semantics: after a place there is nothing
        #: left to do with that fruit). The endpoint is opt-in, so the shipped
        #: path is unchanged; `FRUIT_EPISODE_END=release` forces the boundary even
        #: when the endpoint is `final`.
        try:
            self._endpoint_release = score_endpoint() == "release"
        except Exception:  # noqa: BLE001
            self._endpoint_release = False
        self._close_force = float(os.environ.get("FRUIT_CLOSE_FORCE", "0") or 0.0)
        self._close_force_rate = float(
            os.environ.get("FRUIT_CLOSE_FORCE_RATE", "0.0001") or 0.0001
        )
        self._close_force_ticks = int(os.environ.get("FRUIT_CLOSE_FORCE_TICKS", "180") or 180)
        #: P225f: the **carry force servo** - P192's force-controlled finger
        #: extended past the close. The close's P192 loop ends with the ramp; the
        #: loaded slide happens in the lift/place, where the position drive holds
        #: its target while the pinch falls as the payload walks. With
        #: `FRUIT_CARRY_FORCE=<N>` the finger keeps closing at the same bounded
        #: rate while the measured pinch is below N, until the release or the tick
        #: cap - the "stiff in the approach, compliant only inside the closure"
        #: form of `docs/END_EFFECTOR_DECISION.md`, implemented as a measured-force
        #: position loop (the drive stays the shipped position drive). Default 0 =
        #: byte-inert: no read, no arithmetic, no row.
        self._carry_force = float(os.environ.get("FRUIT_CARRY_FORCE", "0") or 0.0)
        self._carry_force_rate = float(
            os.environ.get("FRUIT_CARRY_FORCE_RATE", "0.0001") or 0.0001
        )
        self._carry_force_ticks = int(
            os.environ.get("FRUIT_CARRY_FORCE_TICKS", "600") or 600
        )
        self._carry_force_diag = os.environ.get("FRUIT_CARRY_FORCE_DIAG", "0") == "1"
        #: P225f: 0 = the 8 mm mechanical floor (the measured 4/8 arm);
        #: >0 = the fruit-relative floor `close_grip - margin` (the
        #: size-aware 3/8 arm, a recorded tie/negative at 0.002).
        self._carry_force_floor_margin = float(
            os.environ.get("FRUIT_CARRY_FORCE_FLOOR_MARGIN", "0") or 0.0
        )
        self._fire_logged = False
        self._force_closed_gap = None
        #: P153: **velocity feed-forward** on the applied joint command
        #: (`FRUIT_POLICY_FF=<ticks>`). The policy's 16 waypoints are positions;
        #: a position loop driving a *moving* target lags it by `e ~ v/K`
        #: (measured on the expert's per-tick IK chase: the labels track at 1.00,
        #: the achieved states at 0.61). Leading the command by `alpha` ticks of
        #: the chunk's own velocity removes that lag without changing the policy,
        #: the data or the action space. 0 = off (the shipped path).
        self._ff_ticks = float(os.environ.get("FRUIT_POLICY_FF", "0") or 0.0)
        self._ff_arr: np.ndarray | None = None
        self._rel_base: np.ndarray | None = None
        self._rel_first: np.ndarray | None = None
        self._dq_index: int | None = None
        self._cart_hold: dict[str, np.ndarray] = {}
        self._direct_start = os.environ.get("FRUIT_DIRECT_START", "grasp").strip().lower()
        if self._direct_start not in ("grasp", "wait"):
            raise ValueError(
                f"FRUIT_DIRECT_START={self._direct_start!r} is not 'grasp' or 'wait'"
            )
        self._max_lift = 0.0
        # P145: **the goal can be measured**. With `FRUIT_GOAL_SOURCE=perception`
        # the goal's position, velocity and diameter come from the depth camera's
        # instance mask plus the tracker - no `spawner.position`, no encoder. The
        # fit is the same `perception._fit_sphere` the scripted depth path uses
        # (P135), on the frame `_observe` has already rendered.
        self._goal_perception = self._goal_source == "perception"
        self._percept_camera = None
        #: P214 bench: a mask-free wrist depth read, projected through the head's
        #: estimate. It only prints `[wrist-depth]`; it does not feed the goal.
        self._wrist_depth_probe = (
            os.environ.get("FRUIT_WRIST_DEPTH_PROBE", "0").strip() == "1"
        )
        self._wrist_depth_model = None
        self._wrist_depth_rows = 0
        self._percept_tracker = None
        self._percept_cfg = None
        self._percept_bias = None
        self._percept_roi = None
        self._percept_pos = None
        self._percept_vel = None
        self._percept_dia = None
        self._percept_frames = 0
        self._percept_rejected = 0
        self._percept_missing = 0
        self._percept_last_rms = float("nan")
        self._percept_diag = os.environ.get("FRUIT_PERCEPTION_DIAG", "0") == "1"
        #: P145c: how long the goal may coast on the filter's velocity while the
        #: fruit is occluded (the hand hides it for ~0.5 s at the close). Beyond
        #: this the prediction is held at the cap, not extrapolated further.
        self._percept_coast_s = float(os.environ.get("FRUIT_PERCEPTION_COAST_S", "1.0"))
        #: Bench-only error samples (truth is read for the column, never used).
        self._percept_errs: list[float] = []
        self._percept_errs_close: list[float] = []
        self._percept_last_err = float("nan")
        # P145 ablation instruments (default off): zero the tactile channels, or
        # freeze the policy's image at the first frame. Both are *ablations* of a
        # channel the honest interface keeps live - they are never shipped on, and
        # the shipped path does not read them.
        self._tactile_zero = os.environ.get("FRUIT_TACTILE_ZERO", "0") == "1"
        #: P145 mechanism trace (default off): one row per observation tick with the
        #: gap, the finger, the jaw line and the fruit/goal positions.
        self._policy_trace = os.environ.get("FRUIT_POLICY_TRACE", "0") == "1"
        self._image_freeze = os.environ.get("FRUIT_IMAGE_FREEZE", "0") == "1"
        self._frozen_frames = None
        #: P145c diag (default off): the router's phase at each decision. The
        #: policy is a mixture of five expert residuals; if the mixture's argmax
        #: changes phase before the fruit is at the station, the early close is
        #: the router, not the action head.
        self._route_diag = os.environ.get("FRUIT_ROUTE_DIAG", "0") == "1"
        #: P145d.5: **commit the close ramp**. Once the policy's own finger
        #: command crosses the close threshold, execute the demonstrations' 60-tick
        #: min-jerk ramp to the grip gap and hold it (the arm, the approach and the
        #: lift stay the policy's). The measured close is multimodal at the re-plan
        #: (0.023 <-> 0.043), and the open-loop ramp is the demonstrated actuation
        #: profile - the "commit then gate" pattern the open-loop-execution study
        #: and ACT prescribe. Default off, byte-inert.
        self._close_ramp = os.environ.get("FRUIT_CLOSE_RAMP", "0") == "1"
        self._close_ramp_ticks = max(1, int(os.environ.get("FRUIT_CLOSE_RAMP_TICKS", "60")))
        #: P145d.6: what starts the ramp. `finger` = the policy's own finger
        #: crossing 0.035 (measured: early by ~0.3 m - the policy closes during
        #: the wait); `phase` = the learned phase gate's `grasp` class, which is
        #: trained on the demonstrations' close labels and reads the perceived
        #: fruit. The phase trigger is a learned classifier, not a harness trigger.
        self._close_ramp_trigger = os.environ.get(
            "FRUIT_CLOSE_RAMP_TRIGGER", "finger"
        ).strip().lower()
        if self._close_ramp_trigger not in ("finger", "phase"):
            raise ValueError(
                "FRUIT_CLOSE_RAMP_TRIGGER must be 'finger' or 'phase', got "
                f"{self._close_ramp_trigger!r}"
            )
        #: P145d.11: the **ramp's own** along-distance. The demos close at fruit
        #: y +0.014 (the timing census), while `FRUIT_PHASE_DY` 0.05 is the
        #: *descent's* start (the scripted tracking window). Conflating them
        #: latches the ramp ~0.3 s early, with the hand still descending -
        #: measured `[close] dz` +55..+128 mm against the 70 mm seat.
        #: P151: `FRUIT_DAGGER_CONTACT_TAKEOVER=1` lets the DAgger expert *drive*
        #: the contact phase (the descent through the close and the tracking hold)
        #: instead of only labelling it, so the rollout store contains the
        #: corrected states. Off by default; it needs `--dagger` and no
        #: `FRUIT_DAGGER_NO_TAKEOVER`.
        #: P225s: the DAgger-label fidelity row (`[dagger]`), default off. Under
        #: `--dagger` + `FRUIT_DAGGER_NO_TAKEOVER=1` the policy drives every state
        #: and the expert label is computed for it; this row prints the joint-space
        #: error between the two once per decision - the number that decides
        #: whether a training round has anything to learn.
        self._dagger_diag = os.environ.get("FRUIT_DAGGER_DIAG", "0") == "1"
        self._dagger_contact = (
            os.environ.get("FRUIT_DAGGER_CONTACT_TAKEOVER", "0") == "1"
        )
        # P225p: the **tactile re-close latch** (default off). At the end of the
        # committed ramp, if no pad carries force and the perceived fruit is
        # still within `..._XY`, hold the pads **open** for `..._OPEN` ticks and
        # restart the ramp once. The measured class: `grasped=False` with the
        # ramp having fired at `xy` 11-30 mm and the pads at 0.00 N for the whole
        # carry - the pads closed beside the fruit (or above it) and the servo
        # then carried a closed hand to it. Re-opening lets the fruit enter the
        # jaw before the second close. One retry per attempt; every knob is read
        # once here so the control loop adds no env lookups.
        # P225q: the **height gate** on the phase latch (default off). The close
        # row measures `dz = jaw_z - fruit_z`; the placed legs latch at 47-105 mm
        # and the worst `grasped=False` legs at **110-118 mm** - a hand 11 cm above
        # the fruit closes the pads above it and the servo then carries a closed
        # hand down onto it. With `FRUIT_CLOSE_RAMP_DZ_MAX` set the ramp refuses to
        # latch while `dz` is above it (the servo keeps descending; the latch fires
        # on a later tick).
        self._close_ramp_dz_max = float(
            os.environ.get("FRUIT_CLOSE_RAMP_DZ_MAX", "0") or 0.0
        )
        self._tac_reclose = os.environ.get("FRUIT_TAC_RECLOSE", "0").strip() == "1"
        self._tac_reclose_min = float(
            os.environ.get("FRUIT_TAC_RECLOSE_MIN", "0.5") or 0.5
        )
        self._tac_reclose_open = int(
            os.environ.get("FRUIT_TAC_RECLOSE_OPEN", "12") or 12
        )
        self._tac_reclose_xy = float(
            os.environ.get("FRUIT_TAC_RECLOSE_XY", "0.060") or 0.060
        )
        self._close_ramp_dy = float(os.environ.get("FRUIT_CLOSE_RAMP_DY", "0.05"))
        #: P216: the phase close's **lower** along-belt bound. The shipped form is
        #: one-sided (`dy <= hi`), so a fruit behind the hand (negative dy) also
        #: satisfied it - measured at `dy=-442 mm` on a small fruit. `-inf` keeps
        #: the shipped path; `-0.02` is the measured "level or just behind" window
        #: (the contact servo's own `FRUIT_CONTACT_SERVO_BEHIND_TOL`).
        self._close_ramp_dy_lo = float(
            os.environ.get("FRUIT_CLOSE_RAMP_DY_LO", "-inf")
        )
        self._last_phase: int | None = None
        self._close_t0: int | None = None
        self._close_grip_finger: float | None = None
        self._last_proprio = None
        #: P145c: **phase scheduling** for the honest interface.
        #:   ``perception`` - the learned classifier on (perceived fruit, finger),
        #:   ``dy``         - the classifier, but the *approach -> grasp* boundary
        #:                    is the scripted line's tracking window on the
        #:                    **measured** along-distance (`FRUIT_PHASE_DY`, 0.05 m).
        #: The phase is a function of the cell's own sensing (depth goal + the
        #: jaw's proprioception + the finger); the action inside it is learned.
        self._phase_mode = os.environ.get("FRUIT_POLICY_PHASE", "").strip().lower()
        if self._phase_mode not in ("", "perception", "dy"):
            raise ValueError(
                f"FRUIT_POLICY_PHASE={self._phase_mode!r} is not '', 'perception' or 'dy'"
            )
        self._phase_dy = float(os.environ.get("FRUIT_PHASE_DY", "0.05"))
        self._handover_diag = os.environ.get("FRUIT_HANDOVER_DIAG", "0") == "1"
        self._diag_min_gap = float("inf")
        self._diag_min_finger = float("inf")
        self._diag_gap_close = float("inf")
        self._max_lift = 0.0
        self._belt_t: float | None = None
        self._belt_v = 0.0
        self._belt_a = 0.0

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
            self._policy2 = None
            self._jaw_now = False
            _ck2 = os.environ.get("FRUIT_POLICY_CKPT2", "").strip()
            if _ck2:
                from .policy.runtime import PolicyRunner as _PR

                self._policy2 = _PR(_ck2, device=self.policy.device)
                if getattr(self.policy, "phase_gate", None) is not None:
                    self._policy2.phase_gate = self.policy.phase_gate
                _w1 = int(self.policy.config.get("proprio_dim", 25))
                _w2 = int(self._policy2.config.get("proprio_dim", 25))
                if _w1 != _w2:
                    raise ValueError(
                        f"FRUIT_POLICY_CKPT2 proprio_dim={_w2} != the primary's {_w1}"
                    )
            # P225d: the **arm router** - a right-arm checkpoint for the right
            # episodes, the primary for the left. The low-lift recollection
            # (`checkpoints/p225_lowmix`) doubles the right-only rate (2/8 ->
            # 4/8) but its mixed cell loses the left's branch; routing by the
            # measured arm keeps each arm on the model measured for it. Unset
            # (`""`) = byte-inert: no second runner, no extra frame push.
            self._right_policy = None
            _ckr = os.environ.get("FRUIT_POLICY_CKPT_RIGHT", "").strip()
            if _ckr:
                if self.rtc_settings.enabled:
                    raise ValueError(
                        "FRUIT_POLICY_CKPT_RIGHT is the synchronous arm router; "
                        "it is not wired into the RTC sampler"
                    )
                from .policy.runtime import PolicyRunner as _PRR

                self._right_policy = _PRR(_ckr, device=self.policy.device)
                if getattr(self.policy, "phase_gate", None) is not None:
                    self._right_policy.phase_gate = self.policy.phase_gate
                _wr = int(self._right_policy.config.get("proprio_dim", 25))
                _w1 = int(self.policy.config.get("proprio_dim", 25))
                if _wr != _w1:
                    raise ValueError(
                        f"FRUIT_POLICY_CKPT_RIGHT proprio_dim={_wr} != the "
                        f"primary's {_w1}"
                    )
                _ar = int(self._right_policy.config.get("action_dim", 9))
                _a1 = int(self.policy.config.get("action_dim", 9))
                if _ar != _a1:
                    raise ValueError(
                        f"FRUIT_POLICY_CKPT_RIGHT action_dim={_ar} != the "
                        f"primary's {_a1}"
                    )
                say(f"[rl] right-arm policy {_ckr} (arm router)")
            if self._action_jaw and self.action_dim != 4:
                raise RuntimeError(
                    f"FRUIT_ACTION=jaw needs a 4-D checkpoint (jaw xyz + finger), "
                    f"got action_dim={self.action_dim}"
                )
            if not self._action_jaw and self.action_dim not in (9, 12, 16):
                raise RuntimeError(
                    f"a 9-D joint checkpoint is required unless FRUIT_ACTION=jaw "
                    f"(got action_dim={self.action_dim})"
                )
            self.action_horizon = int(self.policy.config["action_horizon"])
            self._image_channels = int(self.policy.config["image_channels"])
            # P28-B: the observation width is a property of the artifact, and
            # the gate decides it here - so a 26-D checkpoint without the gate
            # (or the other way round) fails at construction, loudly, instead of
            # conditioning the policy on a vector it never saw.
            #: P227w: the width this environment **actually** assembles, not the
            #: bimanual OpenArm's 25. `proprio()` is the whole articulation's DOF
            #: vector + the finger + the two tactile forces, so the bimanual
            #: OpenArm gives 25 (22 joints) and the single Panda **12** (9 joints)
            #: - a checkpoint trained for one arm must be refused on the other,
            #: and the arm's own width must be accepted (the store declares it the
            #: same way, `EpisodeStore.proprio_dim`, P227v).
            _own_dof = len(self.scene.robot.dof_names)
            want_proprio = (
                _own_dof
                + 1
                + 2
                + (1 if self._speed_channel else 0)
                + (1 if self._cmd_channel else 0)
            )
            want_mode = str(self.policy.config.get("action_mode", "") or "")
            got_mode = (
                "dq" if self._dq_action
                else ("hybrid" if self._hybrid_action
                      else ("rel" if self._rel_action
                      else ("posvel" if self._posvel_action
                            else ("jaw" if (self._action_jaw and not self._action_tcp)
                                  else ("tcp" if self._action_tcp else "")))))
            )
            if want_mode != got_mode:
                raise ValueError(
                    f"checkpoint {checkpoint} was trained with action_mode="
                    f"{want_mode!r} but FRUIT_ACTION resolves to {got_mode!r}; "
                    "a delta-action artifact cannot be run with absolute targets"
                )
            got_proprio = int(self.policy.config.get("proprio_dim", 25))
            if got_proprio != want_proprio:
                raise RuntimeError(
                    f"checkpoint {checkpoint} has proprio_dim={got_proprio} but "
                    f"this environment builds {want_proprio}-D proprio "
                    f"({_own_dof} joints + finger + 2 tactile"
                    f"{' + speed' if self._speed_channel else ''}"
                    f"{' + cmd' if self._cmd_channel else ''}). "
                    "A checkpoint must match the arm it was trained on (25 on the "
                    "bimanual OpenArm, 12 on the single Panda); FRUIT_OBS_SPEED=1 "
                    "adds the belt-speed channel."
                )
            # P141: same contract for the goal's belt pair. A 10-D artifact fed
            # an 8-D goal fails loudly here rather than conditioning on garbage.
            want_goal = 8 + (2 if self._goal_aux else 0)
            got_goal = int(self.policy.config.get("goal_dim", 8))
            if got_goal != want_goal:
                raise RuntimeError(
                    f"checkpoint {checkpoint} has goal_dim={got_goal} but this "
                    f"environment builds {want_goal}-D goals "
                    f"(FRUIT_OBS_GOAL_AUX="
                    f"{'1' if self._goal_aux else 'unset'}). Set "
                    "FRUIT_OBS_GOAL_AUX=1 for a (v_belt, a_belt) artifact, or "
                    "unset it for the 8-D goal."
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
        #: P53's documented name is `FRUIT_POLICY_JOINT_CLAMP`; every recipe in
        #: the record (and the P202/P204 clips) wrote `FRUIT_JOINT_CLAMP`, so the
        #: shorter spelling was silently inert. It is now an alias: the canonical
        #: name wins when both are set, and an explicit short spelling is honoured
        #: (including `=0`). The canonical read stays the one `229` pins.
        _joint_clamp_raw = os.environ.get("FRUIT_POLICY_JOINT_CLAMP")
        if _joint_clamp_raw is None and presentation == "direct":
            # The short spelling is honoured only where the knob is defined; on
            # another presentation it stays the inert string it always was,
            # instead of turning every wrapper that exports it into an abort.
            _joint_clamp_raw = os.environ.get("FRUIT_JOINT_CLAMP")
        self._joint_clamp = resolve_joint_clamp(_joint_clamp_raw)
        self._action_hold = resolve_action_hold(
            os.environ.get("FRUIT_POLICY_ACTION_HOLD")
        )
        #: P207: the emitted target's rate cap (rad/s, 0 = off). The command is
        #: ramped at this speed instead of stepping; the state is per arm and is
        #: re-seeded from the measured joints at every attempt (and after a servo
        #: owns the hand), so it cannot integrate a stale pre-servo pose.
        #: P227aa: the "not mine" rule (see `resolve_skip_late`).
        self._skip_late = resolve_skip_late(os.environ.get("FRUIT_SKIP_LATE"))
        # --- P228 (Stage 0): the latency the world pays, not just the wall --- #
        self._eval_latency_mode, self._eval_latency_ticks = resolve_eval_latency(
            os.environ.get("FRUIT_EVAL_LATENCY")
        )
        if self._eval_latency_mode != "off" and self.rtc_settings.enabled:
            raise ValueError(
                "FRUIT_EVAL_LATENCY cannot be combined with FRUIT_RTC/FRUIT_VLASH: "
                "the interleaved chunker already models the delay, and counting "
                "both would double it"
            )
        if self._eval_latency_mode != "off":
            say(
                f"[rl] eval latency: mode={self._eval_latency_mode} "
                f"ticks={self._eval_latency_ticks} (sync-hold: the belt moves "
                "while the policy computes; 'auto' uses this machine's measured "
                "act() wall)"
            )
        #: the last decision's measured inference wall [ms] (`auto` divides it)
        self._last_infer_ms = 0.0
        #: True on a decision that actually called the model (a held/gated chunk
        #: does not, and must not pay the delay)
        self._infer_this_decision = False
        self._lat_decisions = 0
        self._lat_ticks = 0
        self._lat_max = 0
        #: P227ad: **the primitive's pre-grasp reads take the estimate.**
        #: `grasp_carry_place` reads the simulator 117 times; only the pre-grasp
        #: ones are perception in a real cell (after the grasp the payload follows
        #: the hand, which the code dead-reckons). Arming this requires the
        #: perception goal - there is no estimate otherwise.
        #: P233 (`FRUIT_TRIGGER_SURFACE_SPEED=1`, default off): the intercept
        #: trigger's approach speed must be the belt it **is**, not the setpoint it
        #: was initialised with. P232 measured the defect: under a 0.04-0.06 m/s
        #: wave every fire row still printed `speed=0.080m/s/encoder`, i.e.
        #: `t_arrive = dy / 0.08` against a fruit moving 0.02-0.14 - up to 2x wrong
        #: in the one number the handover is scheduled on. `Conveyor.surface_speed`
        #: is the value the collider is driven with (P141); this routes it to the
        #: trigger. Off = the shipped `encoder_speed` read, byte for byte.
        self._trigger_surface_speed = (
            os.environ.get("FRUIT_TRIGGER_SURFACE_SPEED", "0").strip() == "1"
        )
        self._primitive_estimate = (
            os.environ.get("FRUIT_PRIMITIVE_ESTIMATE", "0").strip() == "1"
        )
        #: P227ad: **keep the camera running inside the primitive.** Measured: with
        #: the pre-grasp reads on the estimate but no measurement during the contact
        #: phase, the tracker's last update is ~10 s old by the time the pads close
        #: (the implement is 2226-2519 ticks), the coast cap correctly refuses to
        #: extrapolate that far, and every attempt reports
        #: `close: fruit drifted 1171 mm` - a metre of belt travel, i.e. the stale
        #: point. A real cell's camera runs at 30-60 Hz throughout, so this renders
        #: and measures on the primitive's own tick hook, every 4 ticks.
        self._primitive_percept = (
            os.environ.get("FRUIT_PRIMITIVE_PERCEPT", "0").strip() == "1"
        )
        self._prim_t = -1.0e9
        if self._primitive_percept and not self._primitive_estimate:
            raise ValueError(
                "FRUIT_PRIMITIVE_PERCEPT=1 needs FRUIT_PRIMITIVE_ESTIMATE=1 "
                "(it exists to keep the estimate fresh, not to arm it)"
            )
        if self._primitive_estimate and not getattr(self, "_goal_perception", False):
            raise ValueError(
                "FRUIT_PRIMITIVE_ESTIMATE=1 needs FRUIT_GOAL_SOURCE=perception - "
                "there is no fruit estimate to feed the primitive without the "
                "tracker"
            )
        self._target_rate = resolve_target_rate(
            os.environ.get("FRUIT_POLICY_TARGET_RATE")
        )
        self._rate_prev: dict[str, np.ndarray] = {}
        #: P210: ACT-style temporal ensembling of overlapping chunks. `0` is the
        #: shipped path; the measured cell uses `0.5` with `--execute-steps 2`.
        self._ensemble_alpha = resolve_ensemble_alpha(
            os.environ.get("FRUIT_POLICY_ENSEMBLE")
        )
        self._ensemble_prev: np.ndarray | None = None
        #: P218: a **size-conditioned scripted skill**. The learned policy never
        #: approaches a 3.1-3.4 cm fruit (`[fire] fired=0` at 0.65-1.18 m, P216),
        #: while the shipped scripted catch places 5/6 lychees at 10 N (P217).
        #: `FRUIT_SMALL_HANDOVER=1` routes a fruit at/below `_DIA` to the scripted
        #: `task.run` skill; the learned policy keeps every larger fruit. Off by
        #: default; the learned small-fruit approach is still an open problem.
        self._small_handover = (
            os.environ.get("FRUIT_SMALL_HANDOVER", "0").strip() == "1"
        )
        self._small_handover_dia = float(
            os.environ.get("FRUIT_SMALL_HANDOVER_DIA", "0.040") or 0.040
        )
        #: P222: a **side-conditioned scripted skill**. The scripted B-heavy
        #: control places 6/6 right-arm fruit (10-15.6 N), while the learned
        #: right is 2/6 (P212) - the right class is the learned policy's, not
        #: the hand's. `FRUIT_HANDOVER_SIDE=right` routes every right-arm sample
        #: to `_run_scripted`; the left stays learned. Off by default.
        self._handover_side = os.environ.get(
            "FRUIT_HANDOVER_SIDE", ""
        ).strip().lower()
        if self._handover_side not in ("", "right", "left", "both"):
            raise ValueError(
                "FRUIT_HANDOVER_SIDE must be '', 'right', 'left' or 'both', got "
                f"{self._handover_side!r}"
            )
        if self._handover_side and (presentation != "direct" or ablate != "none"):
            raise ValueError(
                "FRUIT_HANDOVER_SIDE is only defined for presentation='direct' "
                f"with ablate='none' (got presentation={presentation!r}, "
                f"ablate={ablate!r})"
            )
        if self._small_handover and (presentation != "direct" or ablate != "none"):
            raise ValueError(
                "FRUIT_SMALL_HANDOVER is only defined for presentation='direct' "
                f"with ablate='none' (got presentation={presentation!r}, "
                f"ablate={ablate!r})"
            )
        if self._ensemble_alpha > 0.0 and presentation != "direct":
            raise ValueError(
                "FRUIT_POLICY_ENSEMBLE is only defined for presentation='direct', "
                f"got {presentation!r}"
            )
        if self._ensemble_alpha > 0.0 and self.execute_steps >= self.action_horizon:
            raise ValueError(
                "FRUIT_POLICY_ENSEMBLE needs execute_steps < action_horizon to "
                f"have an overlap (got execute_steps={self.execute_steps}, "
                f"action_horizon={self.action_horizon})"
            )
        if self._ensemble_alpha > 0.0 and (
            self._action_jaw or getattr(self, "_hybrid_action", False)
            or self._dq_action or self._rel_action or self._posvel_action
            or float(getattr(self, "_ff_ticks", 0.0)) > 0.0
        ):
            raise ValueError(
                "FRUIT_POLICY_ENSEMBLE operates on plain absolute 7-D joint "
                "chunks; the cartesian/hybrid, dq, rel, posvel and feed-forward "
                "forms are not composed with it"
            )
        if self._wrist_depth_probe and presentation != "direct":
            raise ValueError(
                "FRUIT_WRIST_DEPTH_PROBE is only defined for presentation='direct', "
                f"got {presentation!r}"
            )
        #: P208: when a servo hands the hand back (the contact window closes, or
        #: the place servo declines), the policy chunk that was generated *before*
        #: the servo is stale by the whole servo displacement. Measured on
        #: `logs/p207/C_s303.log` t=996: the command j1 -1.066 against measured
        #: +0.684 (1.75 rad) - the arm is sent back to its pre-place pose. The
        #: rate cap smooths that into a ~1 s sweep but cannot remove it. With this
        #: on, the hand-back drops the remaining chunk and lets `act` re-plan from
        #: a fresh observation; the applied target is not written on that tick.
        self._replan_on_servo_end = (
            os.environ.get("FRUIT_REPLAN_ON_SERVO_END", "0").strip() == "1"
        )
        self._servo_contact_active = False
        self._servo_place_active = False
        self._servo_handback = False
        self._ensemble_prev = None
        #: P208: the hand-back can land between two 4-tick observation phases.
        #: `sample_chunk` observes on `_step % 4 == 0`; this forces one on the
        #: next chunk so the re-plan is conditioned on the post-servo state, not
        #: the pre-servo frame that generated the stale chunk.
        self._force_observe = False
        if self._replan_on_servo_end and presentation != "direct":
            raise ValueError(
                "FRUIT_REPLAN_ON_SERVO_END is only defined for "
                f"presentation='direct', got {presentation!r}"
            )
        if (self._joint_clamp or self._action_hold > 1 or self._target_rate > 0.0) \
                and presentation != "direct":
            raise ValueError(
                "FRUIT_POLICY_JOINT_CLAMP / FRUIT_POLICY_ACTION_HOLD / "
                "FRUIT_POLICY_TARGET_RATE are only defined for "
                f"presentation='direct', got {presentation!r}"
            )
        if self._target_rate > 0.0 and (
            self._action_jaw or getattr(self, "_hybrid_action", False)
            or self._dq_action or self._rel_action or self._posvel_action
            or float(getattr(self, "_ff_ticks", 0.0)) > 0.0
        ):
            raise ValueError(
                "FRUIT_POLICY_TARGET_RATE operates on the plain absolute 7-D "
                "joint action; the cartesian/hybrid, dq, rel, posvel and "
                "feed-forward action forms write or lead their own targets and "
                "must not be composed with it"
            )
        if self._target_rate > 0.0 and os.environ.get(
            "FRUIT_CLOSE_RAMP_SEAT", "0"
        ) == "1":
            raise ValueError(
                "FRUIT_POLICY_TARGET_RATE must not be composed with the "
                "FRUIT_CLOSE_RAMP_SEAT commit (a one-shot IK that is meant to "
                "arrive inside the ramp window)"
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
            # P136: the direct/policy interface keeps the pre-P136 catch. The
            # tracker's default is scoped to the scripted line; the action loop
            # and the trigger were never measured with it.
            scripted=False,
        )
        self.task.recorder = None
        #: P121: the instruction the direct loop dispatches by, resolved by the
        #: task's own constructor (`FRUIT_SORT_INSTRUCTION`, P114). Unset this is
        #: False and every branch below is skipped - the shipped direct path.
        self._sort_armed = bool(self.task.instruction_armed())
        if self._sort_armed:
            #: The third-destination gate. A destination beyond the two shipped
            #: lanes makes the goal channel's `bin_index` an unseen input value
            #: (2.0), so it is an OOD cell, never a silent default.
            unseen = unseen_destinations(
                self.task._instruction.assigned_destinations()
            )
            if unseen and not self._sort_ood_dest:
                raise ValueError(
                    f"[sort] REFUSED: FRUIT_SORT_INSTRUCTION maps fruit to "
                    f"destination(s) {unseen} beyond the two shipped lanes. The "
                    "goal vector's bin_index is a trained policy input; an unseen "
                    "value is out of distribution. Set FRUIT_SORT_THIRD_DEST=1 to "
                    "run it as the declared OOD cell."
                )
            #: P114's `auto` destinations are solved by the task's startup
            #: calibration, which only `run_bimanual` calls on the scripted path.
            #: The direct env never builds a `CoopSession`, so it calls the same
            #: hook here (verified destinations cost nothing - the pending list
            #: is empty and this is one capability refresh).
            self.task._calibrate_sort_destinations()

        #: P227y: the **task's** waypoint file, not a hard-coded
        #: `configs/waypoints.json`. The task already resolved `FRUIT_WAYPOINTS`
        #: or the arm's own default (`configs/waypoints_franka.json` on the
        #: Panda), and this env's reset teleports the active arm to
        #: `arms[active]["grasp"/"ready"/"wait"]` - with the OpenArm's file on this
        #: arm that teleport put it ~4 rad away from the demonstrations' frame 0
        #: (`logs/p227/obs_cmp`: rollout `[-0.804,-0.078,1.329,...]` against the
        #: demo's `[0.441,-1.037,-0.261,...]`), so every episode started out of
        #: distribution and the policy closed the finger immediately. On the
        #: OpenArm both sources are the same file, so its stream is unchanged.
        self.waypoints = self.task.waypoints

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

        if record and self._eval_latency_mode != "off":
            # P228: the injector advances the world without applying an action, so
            # a recorded episode's `ticks_total` would be short of the simulated
            # time it actually covers - the store invariant P173 established
            # (`ticks_total == sum`) would be silently broken by an *evaluation*
            # lever. Refuse rather than write a corrupt store.
            raise ValueError(
                "FRUIT_EVAL_LATENCY is an evaluation lever and cannot be combined "
                "with --record: the paused ticks would not appear in the store's "
                "tick accounting"
            )
        self._recorder = RolloutRecorder(self.run_dir) if (record and self.run_dir) else None

        self.belt_top = float(self.cfg.belt_center[2]) + float(self.cfg.belt_size[2]) / 2.0
        self._episode = -1
        self._done = True
        self._sample = None
        self._active = "left"
        self._bin_index = 0
        self._goal = np.zeros(8 + (2 if self._goal_aux else 0), dtype=np.float32)
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
        if (self._place_vmax_left != self._place_vmax
                or self._place_vmax_right != self._place_vmax):
            say(
                f"[rl] place servo: vmax={self._place_vmax:.3f} "
                f"left={self._place_vmax_left:.3f} "
                f"right={self._place_vmax_right:.3f} m/s"
            )
        if self._ensemble_alpha > 0.0:
            say(
                f"[rl] ensemble: alpha={self._ensemble_alpha:.2f} "
                f"execute_steps={self.execute_steps} "
                f"action_horizon={self.action_horizon} "
                f"overlap={min(self.execute_steps, self.action_horizon - self.execute_steps)}"
            )
        if (self._joint_clamp or self._action_hold > 1 or self._target_rate > 0.0
                or self._skip_late > 0.0):
            # P53: the emission cells' own banner - the resolved knobs plus the
            # joint ranges the clamp actually uses (read from the arm, so the
            # log proves which limits were applied rather than which were
            # intended). P207 adds the target rate only when it is armed, so a
            # clamp/hold-only log keeps its P53 row byte for byte.
            right = self.task.arms["right"]
            ranges = " ".join(
                f"j{i + 1}[{float(lo):+.3f},{float(hi):+.3f}]"
                for i, (lo, hi) in enumerate(zip(right.arm_lo, right.arm_hi))
            )
            rate = (
                f"target_rate={self._target_rate:.3f}rad/s "
                if self._target_rate > 0.0
                else ""
            )
            #: P227aa: printed independently of the rate cell, because the skip
            #: rule is a safety/ownership setting and not an emission one.
            skip = (
                f"skip_late={self._skip_late:.2f}s "
                if self._skip_late > 0.0
                else ""
            )
            say(
                f"[rl] emit: joint_clamp={int(self._joint_clamp)} "
                f"action_hold={self._action_hold} "
                f"{skip}{rate}"
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
            "goal_source": self._goal_source,
            "goal_measured": bool(self._goal_perception),
            #: P225h: the small-fruit perception floor (0 = the shipped 60 px on
            #: every size). A store/run without these keys ran the 60 px floor.
            "perception_min_px_small": int(
                os.environ.get("FRUIT_PERCEPTION_MIN_PX_SMALL", "12") or 0
            ),
            "perception_small_dia": float(
                os.environ.get("FRUIT_PERCEPTION_SMALL_DIA", "0.040") or 0.040
            ),
            "perception_fovea": int(
                os.environ.get("FRUIT_PERCEPTION_FOVEA", "0") or 0
            ),
            "perception_shape": os.environ.get("FRUIT_PERCEPTION_SHAPE", "") or None,
            "perception_shape_small": (
                os.environ.get("FRUIT_PERCEPTION_SHAPE_SMALL", "") or None
            ),
            "perception_shape_species": (
                os.environ.get("FRUIT_PERCEPTION_SHAPE_SPECIES", "") or None
            ),
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
            #: P225f: the carry force servo's target (0 = the shipped position
            #: drive). The drive stays the shipped one; the knob moves its target.
            "carry_force": float(self._carry_force),
            "carry_force_small_dia": float(
                os.environ.get("FRUIT_CARRY_FORCE_SMALL_DIA", "0.040") or 0.0
            ),
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
                    **(
                        {"target_rate": float(self._target_rate)}
                        if self._target_rate > 0.0
                        else {}
                    ),
                }
                if (self._joint_clamp or self._action_hold > 1
                    or self._target_rate > 0.0)
                else None
            ),
            "handover_side": self._handover_side or None,
            "small_handover": (
                {
                    "enabled": True,
                    "dia": float(self._small_handover_dia),
                }
                if self._small_handover
                else None
            ),
            "close_ramp": (
                {
                    "trigger": self._close_ramp_trigger,
                    "dy_hi": float(self._close_ramp_dy),
                    "dy_lo": float(self._close_ramp_dy_lo),
                    "ticks": int(self._close_ramp_ticks),
                }
                if self._close_ramp
                else None
            ),
            "small_select": (
                {
                    "extra_m": float(os.environ.get(
                        "FRUIT_SELECT_SMALL_EXTRA", "0") or 0.0),
                    "dia_m": float(os.environ.get(
                        "FRUIT_SELECT_SMALL_DIA", "0.040") or 0.040),
                }
                if float(os.environ.get(
                    "FRUIT_SELECT_SMALL_EXTRA", "0") or 0.0) > 0.0
                else None
            ),
            "finger_maxforce": (
                {
                    "global": float(self._finger_cap_direct),
                    "small": float(self._finger_cap_small),
                    "small_dia": float(self._finger_cap_small_dia),
                }
                if self._finger_cap_small > 0.0
                else None
            ),
            "place_servo": (
                {
                    "vmax": float(self._place_vmax),
                    "vmax_left": float(self._place_vmax_left),
                    "vmax_right": float(self._place_vmax_right),
                }
                if (self._place_vmax_left != self._place_vmax
                    or self._place_vmax_right != self._place_vmax)
                else None
            ),
            "ensemble": (
                {
                    "alpha": float(self._ensemble_alpha),
                    "execute_steps": int(self.execute_steps),
                    "action_horizon": int(self.action_horizon),
                    "overlap": int(
                        min(self.execute_steps,
                            self.action_horizon - self.execute_steps)
                    ),
                }
                if self._ensemble_alpha > 0.0
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
            #: P225d: the arm router's right checkpoint (empty = the single
            #: model). The right episodes are a different artifact from the
            #: left's, so a store/run without this key ran one model on both.
            "right_checkpoint": (
                os.environ.get("FRUIT_POLICY_CKPT_RIGHT", "").strip() or None
            ),
            "right_checkpoint_md5": (
                _md5(
                    os.environ["FRUIT_POLICY_CKPT_RIGHT"].strip()
                    if os.path.isabs(os.environ["FRUIT_POLICY_CKPT_RIGHT"].strip())
                    else os.path.join(
                        _REPO_ROOT, os.environ["FRUIT_POLICY_CKPT_RIGHT"].strip()
                    )
                )
                if os.environ.get("FRUIT_POLICY_CKPT_RIGHT", "").strip()
                else ""
            ),
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
                #: P93: the **band and mix** the pool was built with, from the
                #: shared builder the collector's shards also call
                #: (`assets.supply_provenance`). Without it a direct/rollout
                #: store under 0.20-0.33 m and one under 0.20-0.36 m are
                #: indistinguishable from their own metadata (the collector's
                #: shard manifest already carried `supply.x_min`/`x_max`; this
                #: block is the direct env's, and it is the same object).
                "band": self._supply_band_provenance(),
            },
            #: P121: the sort instruction the direct loop dispatched by (absent
            #: = the shipped grade lane, so a pre-P121 store is identifiable).
            "sort": self._sort_provenance(),
            "sources": sources,
        }

    def _sort_provenance(self) -> dict | None:
        """The manifest's `sort` block (P121), or None without an instruction.

        A direct store recorded under an instruction is otherwise
        indistinguishable from an un-instructed one: the instruction moves which
        fruit each arm takes and where it is released, while every motion
        profile, physics block and supply band stays the same. The block names
        the rules, their source and the capability map, and states the
        third-destination OOD flag.
        """
        if not getattr(self, "_sort_armed", False):
            return None
        instruction = self.task._instruction
        return {
            "instruction": instruction.source,
            "rules": [rule.text for rule in instruction.rules],
            "default": instruction.default,
            "destinations": sorted(int(d) for d in instruction.assigned_destinations()),
            "arm_of": {
                str(key): value for key, value in sorted(self.task._sort_arm_of.items())
            },
            "goal_bin_index": True,
            "third_destination_ood": bool(self._sort_ood_dest),
        }

    def _supply_band_provenance(self) -> dict:
        """The manifest's `supply.band` block (P93), or a reported error.

        Same builder and same rule as `_scene_provenance`/`_physics_provenance`:
        a manifest must never take a run down, so a failure is a recorded state.
        """
        try:
            from .assets import supply_provenance

            plan = getattr(self.spawner, "supply", None)
            if plan is None:
                return {"why": "the spawner exposes no SupplyPlan"}
            return supply_provenance(plan)
        except Exception as exc:  # noqa: BLE001 - provenance must not stop a run
            return {"why": str(exc)}

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
                arms=self.task.arms,
                scope=self._finger_cap_scope,
                two_line=False,
                # P136: the direct/policy task is built with `scripted=False`, so
                # its store names the tracker's scope-off resolution.
                scripted=False,
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
        # P232: the belt-wave instrument (P135) is ticked inside the task's
        # `_step_sim`, i.e. only while the **primitive** runs. The env advances the
        # physics on its own path, so an armed wave reached the contact phase but
        # not the approach - and the approach is exactly where a varying speed
        # matters (the trigger's `t_arrive`). Tick it here too; the flag is False
        # unless `FRUIT_BELT_WAVE_AMP > 0`, so every shipped path is unchanged.
        _wave_task = getattr(self, "task", None)
        if _wave_task is not None and getattr(_wave_task, "_belt_wave_on", False):
            # `advance` also runs in `__init__` (the scene prime), before the task
            # exists - `getattr(self, "task", None)` is that case.
            _wave_task._belt_wave_tick()
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

    def _apply_direct_finger_cap(self) -> None:
        """P176: raise the active arm's finger drive cap for this attempt.

        A **hardware spec** applied at runtime (`FRUIT_FINGER_MAXFORCE_DIRECT`)
        through the task's own writer (`attempt_finger_cap`), on the direct
        presentation only - the env never touches a drive. Zero/unset does
        nothing at all.
        """
        cap = float(self._finger_cap_direct)
        tag = "FRUIT_FINGER_MAXFORCE_DIRECT"
        if (self._finger_cap_small > 0.0 and self._sample is not None
                and float(self._sample.diameter) <= self._finger_cap_small_dia):
            cap = float(self._finger_cap_small)
            tag = "FRUIT_FINGER_MAXFORCE_DIRECT_SMALL"
        if cap <= 0.0:
            return
        side = self._active
        if side in self._finger_cap_saved:
            return
        base = self.task.attempt_finger_cap(side, float(cap))
        if base is None:
            return
        self._finger_cap_saved[side] = float(base)
        self._say(
            f"[drive] {side} attempt finger cap {base:.2f} -> "
            f"{cap:.2f} N ({tag})"
        )

    def _restore_direct_finger_cap(self) -> None:
        """Put back every cap this attempt raised (idempotent)."""
        if not self._finger_cap_saved:
            return
        for side, base in list(self._finger_cap_saved.items()):
            self.task.attempt_finger_cap_restore(side, float(base))
            self._say(f"[drive] {side} attempt finger cap restore -> {base:.2f} N")
        self._finger_cap_saved.clear()

    def _aligned_start(self) -> np.ndarray | None:
        """The demonstrations' frame-0 start pose for this fruit, or None.

        P160's family (`configs/start_pose_family.json`, `j4 = a + b x`): the
        per-x wait pose the demos actually start at. `_begin_pick` teleports to
        it after the fixed wait pose; the continuous transit (P225n) needs it
        *before* the motion so the blend can end there instead of snapping.
        """
        align = os.environ.get("FRUIT_DIRECT_START_ALIGN", "0").strip().lower()
        if (
            align in ("", "0", "off", "no", "false")
            or self.presentation != "direct"
            or self._sample is None
        ):
            return None
        mode = align
        if mode not in ("family", "demo"):
            return None
        try:
            fx = float(self.spawner.position(self._sample)[0])
            path = os.environ.get(
                "FRUIT_START_FAMILY", "configs/start_pose_family.json"
            )
            if not hasattr(self, "_start_family"):
                import json as _json

                self._start_family = _json.load(open(path))
            fam = getattr(self, "_start_family", {}).get(self._active)
            if fam is None:
                return None
            return np.asarray(fam["a"], dtype=float) + np.asarray(
                fam["b"], dtype=float
            ) * fx
        except Exception:  # noqa: BLE001 - the fixed wait pose is the fallback
            return None

    def _continuous_return(self, side: str, goal) -> None:
        """Drive an arm to `goal` along the scripted transit (P225n, opt-in).

        The per-pick reset teleports the arm; in a continuous episode that is a
        ~1 m snap from the output line back over the belt in one tick, the one
        frame a viewer reads as impossible. This runs the scripted transit
        instead: `_lift_clear` (up and inboard, at least `belt_top + 0.30`),
        `_catch_up_drive` (the drive target onto the measured pose), then a
        min-jerk joint blend to the target with a settle. Same code the scripted
        line uses for `_ready_transit`, so the clearance routing is the measured
        one; the joint steps stay under the posture bound because the blend is
        the same quintic. Frames are captured by the video hook on `_step_sim`.
        """
        task = self.task
        t0 = int(self._step)
        _diag = os.environ.get("FRUIT_CONTINUOUS_TRANSIT_DIAG", "0") == "1"
        _q0 = np.asarray(task.arms[side].joint_positions(), dtype=float) if _diag else None
        task._catch_up_drive(side)
        cap = int(os.environ.get("FRUIT_CONTINUOUS_TRANSIT_LIFT_CAP", "150") or 150)
        _t_lift0 = self._sim_time() if _diag else 0.0
        task._lift_clear(side, cap=cap)
        task._catch_up_drive(side)
        _q1 = np.asarray(task.arms[side].joint_positions(), dtype=float) if _diag else None
        _lift_ticks = (
            int(round((self._sim_time() - _t_lift0) * 120.0)) if _diag else 0
        )
        ticks = int(os.environ.get("FRUIT_CONTINUOUS_TRANSIT_TICKS", "90") or 90)
        settle = int(
            os.environ.get("FRUIT_CONTINUOUS_TRANSIT_SETTLE", "60") or 60
        )
        _stats = {} if _diag else None
        task._blend_to(side, goal, ticks=ticks, settle=settle, stats=_stats)
        if _diag and _q0 is not None:
            #: P227ab: **where the return's motion actually is**. `_blend_to`
            #: starts from the measured pose (`start = joint_positions()`), so a
            #: visible snap at a pick boundary can only come from the phase before
            #: it - the IK lift - or from a commanded step the servo cannot track.
            #: These two numbers separate them: the lift's own displacement, and
            #: the blend's commanded peak per tick (`stats["q_step"]`, the P100
            #: arithmetic). Diag only; nothing is read when it is off.
            _q2 = np.asarray(task.arms[side].joint_positions(), dtype=float)
            self._say(
                f"[transit] side={side} lift_moved={float(np.max(np.abs(_q1 - _q0))):.3f} "
                f"lift_ticks={_lift_ticks} "
                f"lift_step={float(np.max(np.abs(_q1 - _q0))) / max(1, _lift_ticks):.4f} "
                f"blend_cmd_step={float(_stats.get('q_step', 0.0)):.3f} rad/tick "
                f"blend_err={float(_stats.get('ramp_err', 0.0)):.3f} "
                f"total_moved={float(np.max(np.abs(_q2 - _q0))):.3f} "
                f"ticks={ticks}+{settle}"
            )
        if os.environ.get("FRUIT_CONTINUOUS_TRANSIT_DIAG", "0") == "1":
            #: one row per return: the blend's end residual (the same number the
            #: scripted `_blend_to` reports as `settle_err`). The return's clock
            #: is the sim time, which advances inside `_step_sim` while the
            #: env's own `_step` does not.
            arm = task.arms[side]
            err = float(
                np.max(np.abs(arm.joint_positions() - np.asarray(goal, dtype=float)))
            )
            self._say(
                f"[transit] side={side} err={err:.4f} blend={ticks} settle={settle}"
            )

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
        # P121: with an instruction armed the destination is the instruction's
        # decision and the arm is the capability map's answer; unset this is the
        # shipped `grade A -> block 0 -> left` expression, byte for byte.
        bin_index, active = direct_dispatch(
            target,
            self._sort_armed,
            self.task.sort_destination,
            self.task.arm_for_destination,
        )

        self._sample = sample
        self._active = active
        self._bin_index = bin_index
        # P176: the hardware clamp spec for this attempt (no-op when unset)
        self._apply_direct_finger_cap()
        # P145: a new fruit is a new track. The perception estimate and its
        # filter are per attempt (`FruitPerception.reset`'s rule, P135): a
        # carried radius would fit the next fruit at the old one's size.
        self._percept_tracker = None
        self._percept_pos = None
        self._percept_vel = None
        self._percept_dia = None
        self._percept_frames = self._percept_rejected = self._percept_missing = 0
        #: P225k: the fovea's held radius and its frame count, per attempt.
        self._percept_radius_hold = 0.0
        self._percept_fovea_frames = 0
        self._percept_fovea_fail = 0
        self._percept_fovea_skip: dict[str, int] = {}
        self._percept_errs = []
        self._percept_errs_close = []
        #: P225k: the **signed** estimate error per accepted frame (bench only),
        #: so a residual bias names its own axis. `[close] dx` reads 2-17 mm
        #: outboard and the norm cannot say whether the goal or the servo is off.
        self._percept_err_vec = []
        self._percept_err_vec_close = []
        self._percept_last_err = float("nan")
        self._fire_src_logged = False
        self._goal = self._goal_vector(
            target["position"], target["velocity"], target["diameter"], bin_index
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
        # P225n: **continuous return**, opt-in. With `FRUIT_CONTINUOUS_TRANSIT=1`
        # a continued pick drives the arm to its start pose along the scripted
        # transit instead of teleporting it, so a continuous episode reads as
        # approach -> grasp -> carry -> place -> return -> approach with no cut.
        # Default off: every per-episode reset and every measured cell keeps the
        # teleport, byte for byte.
        _transit = (
            continuation
            and os.environ.get("FRUIT_CONTINUOUS_TRANSIT", "0").strip() == "1"
        )
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
                _goal = (
                    np.asarray(self.waypoints["arms"][name]["ready"], dtype=float)
                    if park is None
                    else park
                )
                if _transit and name == prev_active:
                    # the arm that just placed: return along the transit, not a snap
                    self._continuous_return(name, _goal)
                else:
                    other.teleport_joints(_goal)
            start = np.asarray(self.waypoints["arms"][active]["grasp"], dtype=float)
        else:
            start = np.asarray(self.waypoints["arms"][active]["ready"], dtype=float)
        if self._direct_start == "wait" and self.presentation == "direct":
            entry = self.waypoints["arms"][active]
            start = np.asarray(entry.get("wait", entry["grasp"]), dtype=float)
        if _transit:
            # the blend ends at the demos' frame-0 pose, so the align teleport
            # below is skipped (it would snap the few cm the family moves)
            #: P227z: `_aligned_start()` returns an **ndarray** (or None), so
            #: `... or start` raised `ValueError: The truth value of an array
            #: with more than one element is ambiguous` the first time this
            #: opt-in transit ran with a start alignment armed - measured, it
            #: aborted the clip after pick 1 (`logs/121_policy_video_traceback.txt`).
            #: The shipped per-episode reset never reaches here (`_transit` is
            #: `FRUIT_CONTINUOUS_TRANSIT=1` and a continuation), so this is a
            #: latent defect of the continuous path only.
            _aligned = self._aligned_start()
            self._continuous_return(active, start if _aligned is None else _aligned)
        else:
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
        # P145d.11: **the demonstrations' frame 0 is the wait pose solved at the
        # selected fruit's x** (measured on `demos_v11`: j4 = 3.036 - 5.741 x,
        # r = -0.994; the same family in `p145_tcp` and the new anchor shards).
        # The scripted line's hover pre-aligns, so the demos never show a 10 cm
        # lateral descent from a fixed station pose - which is exactly what the
        # direct episode was asking for (`[close] dx` -10..-95 mm). With this on,
        # the episode starts where the demonstrations start: one position-only
        # IK solve of the wait pose at the fruit's x, then a teleport.
        #: P227z: the gate accepted only the literal `"1"` while the dispatch
        #: below wants `family`/`demo` - so **the family mode was unreachable**
        #: (`FRUIT_DIRECT_START_ALIGN=family` skipped the whole block and the arm
        #: stayed at the fixed `grasp` pose, 0.43-0.46 rad from the
        #: demonstrations' frame 0). The gate now accepts any non-off value and
        #: the dispatch decides; `"1"` keeps the IK form.
        _align = os.environ.get("FRUIT_DIRECT_START_ALIGN", "0").strip().lower()
        if (
            _align not in ("", "0", "off", "no", "false")
            and self.presentation == "direct"
            and self._sample is not None
            and not _transit
        ):
            # P145d.11a: the solve must read the **settled** wait pose. Reading
            # the jaw before the reset's settle returns the previous pose (the
            # ready pose, z 1.373 against the wait's 1.314 - measured), so the
            # "aligned" start sat 6 cm above the demonstrations' frame 0 and was
            # out of support, which is why every aligned cell's `[close] dz`
            # regressed to +100..+167.
            try:
                _fx = float(self.spawner.position(self._sample)[0])
                _mode = _align
                if _mode in ("family", "demo"):
                    # P160: the demonstrations' **frame 0** is a linear family in
                    # the selected fruit's x (j4 = 3.036 - 5.741 x, r = -0.994).
                    # The IK alignment reproduced x but sat 5-8 cm high (measured:
                    # jaw_z 1.373-1.385 against every store's frame-0 1.300-1.326),
                    # which is out of support - so use the demos' own family
                    # (`configs/start_pose_family.json`, a least-squares fit over
                    # `p146_anchor_all`, rms 0.014-0.017 rad).
                    _path = os.environ.get(
                        "FRUIT_START_FAMILY", "configs/start_pose_family.json"
                    )
                    if not hasattr(self, "_start_family"):
                        import json as _json

                        self._start_family = _json.load(open(_path))
                    _fam = getattr(self, "_start_family", {}).get(self._active)
                    if _fam is not None:
                        _q = np.asarray(_fam["a"], dtype=float) + np.asarray(
                            _fam["b"], dtype=float
                        ) * _fx
                        arm.teleport_joints(_q)
                        if os.environ.get("FRUIT_DIRECT_START_DIAG", "0") == "1":
                            _m = np.asarray(arm.joint_positions(), dtype=float)
                            print(
                                f"[start] family q={np.round(_q, 3).tolist()} "
                                f"-> measured {np.round(_m, 3).tolist()} "
                                f"(res {float(np.max(np.abs(_m - _q))):.3f} rad, "
                                f"settle {self._reset_settle})",
                                flush=True,
                            )
                        self.advance(self._reset_settle)
                        if os.environ.get("FRUIT_DIRECT_START_DIAG", "0") == "1":
                            _m2 = np.asarray(arm.joint_positions(), dtype=float)
                            print(
                                f"[start] after settle {self._reset_settle} ticks: "
                                f"{np.round(_m2, 3).tolist()} "
                                f"(drift {float(np.max(np.abs(_m2 - _q))):.3f} rad)",
                                flush=True,
                            )
                        raise StopIteration
                arm.capture_hold_pose()
                _jaw = np.asarray(arm.jaw_centre(), dtype=float)
                _target = np.array([_fx, float(_jaw[1]), float(_jaw[2])])
                _q = None
                for _ in range(120):
                    arm.sync_command_to_measured()
                    if arm.ik_step(_target) < 1e-3:
                        break
                    _q = np.array(arm._q_cmd, dtype=float) if arm._q_cmd is not None else _q
                if _q is not None:
                    arm.teleport_joints(_q)
            except StopIteration:
                pass
            except Exception:  # noqa: BLE001 - the fixed wait pose is the fallback
                pass
        self.advance(self._reset_settle)
        if self._target_rate > 0.0:
            # P207: the rate limiter's own state is per arm and per attempt. Seed
            # it from the **measured** joints after the start pose has settled, so
            # the first policy target ramps from where the arm actually is (a
            # stale previous attempt's command would make it lead the measured
            # pose by an unbounded amount).
            self._rate_prev = {
                name: np.asarray(a.joint_positions(), dtype=np.float64)
                for name, a in self.task.arms.items()
            }
        self._close_t0 = None
        self._reclose_until = None
        self._reclosed = False
        self._servo_on = False
        self._servo_last_aim = None
        self._place_phase = 0
        self._place_open = 0.0
        self._finger_was_closed = False
        self._scored_release = False
        self._close_ramp_reported = False
        self._close_ramp_last = -1
        self._fire_logged = False
        self._force_closed_gap = None
        self._close_grip_finger = None
        #: P225f: the carry force servo's own state (None = not started this pick)
        self._carry_force_value = None
        self._carry_force_t0 = None
        self._servo_contact_active = False
        self._servo_place_active = False
        self._servo_handback = False
        self._seat_q = None
        self._last_phase = None
        self._dq_index = None
        self._rel_base = None
        self._rel_first = None
        # P145d.6: the command channel's t=0 value is the training stream's
        # `command[0]` (the wait hold); without this reset the first decision of
        # an episode carries the previous episode's finger.
        self._last_finger = float(arm.OPEN)
        if self._action_jaw:
            # P145d: the cartesian servo holds the attitude the episode starts
            # at; the position is the policy's, the orientation is not its output.
            arm.capture_hold_pose()
            self._cart_hold[active] = np.asarray(arm.hold_quaternion, dtype=float).copy()
            # Seed the IK integrator once (the scripted close carries `_q_cmd`
            # across ticks; resetting it per deploy tick was the train/deploy gap
            # the review agent found).
            arm.sync_command_to_measured()
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
            if getattr(self, '_policy2', None) is not None:
                self._policy2.reset()
            if getattr(self, '_right_policy', None) is not None:
                self._right_policy.reset()
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
        self._diag_min_gap = float("inf")
        self._diag_min_finger = float("inf")
        self._diag_gap_close = float("inf")
        self._max_lift = 0.0
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
        _entry = self.waypoints["arms"][active]
        self._expert_grasp = np.asarray(
            _entry.get(self._direct_start, _entry["grasp"]), dtype=np.float32
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
                    "goal_source": self._goal_source,
                }
            )
        # Frame 0, so `policy.ready` becomes true after the first window fills.
        self._observe()
        return self._obs_snapshot()

    # ------------------------------------------------------------------ #
    # Observation
    # ------------------------------------------------------------------ #
    def _observe(self, force: bool = False) -> None:
        """Render and read the head camera once per observation tick.

        `force=True` (P227ad) bypasses the one-per-`_step` guard: `_step` is the
        **policy** tick, which does not advance while the scripted primitive runs, so
        a perception-driven primitive's hook was calling straight into the early
        return (measured: the frame count stayed at 20-54 while the contact phase
        lasted 2000+ ticks).
        """
        if not force and self._observed_step == self._step:
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
                    or self._park_diag or getattr(self, "_goal_perception", False)):
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
                if getattr(self, "_goal_perception", False) and seg is not None:
                    self._perceive_tick(np.asarray(depth), seg, labels)
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
        if self.policy is not None:
            try:
                self._last_proprio = self.proprio()
            except Exception:  # noqa: BLE001 - reporting only
                self._last_proprio = None
        self._last_rgb, self._last_depth, self._last_mask = rgb, depth, mask
        if (self._goal_source == "truth_moving" and self._sample is not None
                and self._goal.size >= 7):
            # P145c **bench only**: the demonstrations' moving goal rebuilt from
            # the simulator's own fruit state. It is the training distribution's
            # goal (FRUIT_TRAIN_GOAL=moving) with zero measurement error, so a
            # cell with it separates "the perception is the residual" from "the
            # policy is". Never a shipped mode.
            try:
                pos = np.asarray(self.spawner.position(self._sample), dtype=float)
                vel = np.asarray(self.spawner.velocity(self._sample), dtype=float)
                self._goal[0:3] = pos.astype(np.float32)
                self._goal[3:6] = vel.astype(np.float32)
                self._goal[6] = float(self._sample.diameter)
            except Exception:  # noqa: BLE001 - bench column only
                pass
        if (getattr(self, "_goal_perception", False)
                and self._percept_tracker is not None and self._goal.size >= 7):
            # P145c: the goal moves with the fruit **every** observation tick, and
            # through an occlusion with the filter's prediction. Publishing the
            # last *measurement* instead froze the goal at +0.065 m for 0.53 s
            # while the hand hid the fruit (measured, `[route]`), and the policy
            # closed on the frozen value. `predict_at` is non-mutating; the cap is
            # the longest coast a 30 Hz filter is trusted for.
            horizon = float(self._sim_time()) - float(self._percept_tracker.t)
            horizon = min(max(horizon, 0.0), float(self._percept_coast_s))
            self._percept_pos = np.asarray(
                self._percept_tracker.predict_at(horizon), dtype=float
            )
            self._percept_vel = np.asarray(self._percept_tracker.velocity, dtype=float)
            self._goal[0:3] = self._percept_pos.astype(np.float32)
            self._goal[3:6] = self._percept_vel.astype(np.float32)
            if self._percept_dia is not None:
                self._goal[6] = float(self._percept_dia)
        if self._wrist_depth_probe:
            self._wrist_depth_tick()
        if self.policy is not None and rgb is not None and depth is not None:
            if self._image_freeze:
                # P145 ablation: one frame for the whole run - the information is
                # removed, the tensor statistics (and the model's shapes) are not.
                if self._frozen_frames is None:
                    self._frozen_frames = (
                        np.array(rgb, copy=True),
                        np.array(depth, copy=True),
                        None if mask is None else np.array(mask, copy=True),
                    )
                else:
                    rgb, depth, mask = self._frozen_frames
            _uv = None
            _fov = int(os.environ.get("FRUIT_IMAGE_FOVEA", "0") or 0)
            if _fov > 0 and os.environ.get(
                "FRUIT_IMAGE_FOVEA_PHASE", "0"
            ).strip() == "1" and self._close_t0 is not None:
                # P173b: after the latch the view is the **wide** frame (the bins),
                # matching the loader's per-frame choice.
                _fov = 0
            if _fov > 0:
                try:
                    from .policy.vision import project

                    if not hasattr(self, "_fovea_cam"):
                        from .assets import head_camera_override

                        self._fovea_cam = head_camera_override(self.cfg)
                    _eye, _tgt = self._fovea_cam
                    _uv = project(
                        np.asarray(self._goal, dtype=float)[:3],
                        eye=_eye,
                        target=_tgt,
                        width=np.asarray(rgb).shape[1],
                        height=np.asarray(rgb).shape[0],
                    )
                except Exception:  # noqa: BLE001 - the full frame is the fallback
                    _uv = None
            _right = getattr(self, "_right_policy", None)
            _right_active = _right is not None and self._active == "right"
            if _right_active:
                # P225d: the arm router's **active-only** push - the right
                # checkpoint's buffer is filled on right episodes only, so the
                # per-frame crop/resize is paid once, not twice (the two-buffer
                # form added enough wall to feed the P145b/P220 wedge class).
                _right.push_frame(rgb, depth, mask, uv=_uv)
            if not _right_active or getattr(self, "_policy2", None) is not None:
                # the primary owns the left; the hybrid's jaw head (`_policy2`)
                # still needs the primary's frames on either arm.
                self.policy.push_frame(rgb, depth, mask, uv=_uv)
            if getattr(self, "_policy2", None) is not None:
                # the hybrid's jaw head has its own observation horizon buffer
                self._policy2.push_frame(rgb, depth, mask, uv=_uv)

    # ------------------------------------------------------------------ #
    # P141: the belt-state channel
    # ------------------------------------------------------------------ #
    def _belt_state(self) -> tuple[float, float]:
        """``(v_belt, a_belt)``: the belt's surface speed and its derivative.

        Positive downstream. The speed is :func:`data.belt_speed_scalar` - the
        *same* assembly site the 26th proprio column uses, so the two channels
        cannot disagree - and the acceleration is a first-order low-passed
        difference with the store loader's own time constant
        (:func:`data.belt_accel_trace`), so a recorded `a_belt` and this one are
        the same function of the same signal.

        Called once per observation tick while the gate is armed; with the gate
        off nothing calls it and the encoder is not read.
        """
        try:
            speed = float(
                belt_speed_scalar(
                    self.spawner, self._sample, fallback=self.cfg.belt_speed
                )
            )
        except Exception:  # noqa: BLE001 - a missing belt must not stop the loop
            speed = abs(float(self.cfg.belt_speed))
        now = float(self._sim_time())
        prev_t, prev_v = self._belt_t, self._belt_v
        self._belt_t, self._belt_v = now, speed
        if prev_t is None:
            return speed, 0.0
        dt = now - prev_t
        if not math.isfinite(dt) or dt <= 0.0 or dt > 0.5:
            # No usable interval (a reset or a stalled loop) reads as "steady".
            return speed, 0.0
        tau = float(os.environ.get(BELT_TAU_ENV, str(BELT_TAU_DEFAULT)))
        alpha = dt / (tau + dt)
        self._belt_a = (1.0 - alpha) * self._belt_a + alpha * (
            (speed - prev_v) / dt
        )
        return speed, float(self._belt_a)

    def _goal_vector(self, position, velocity, diameter, bin_index) -> np.ndarray:
        """The goal conditioning vector - the single assembly site.

        The shipped 8-D form is ``[xyz, v(3), diameter, bin_index]``. P141
        appends ``(v_belt, a_belt)`` when the gate is armed; those two are the
        belt's state, so unlike dims 0-7 they are refreshed **every tick**
        (`_refresh_goal_aux`).
        """
        position = np.asarray(position, dtype=np.float32).reshape(-1)[:3]
        velocity = np.asarray(velocity, dtype=np.float32).reshape(-1)[:3]
        # P145: **the goal can come from perception** (`FRUIT_GOAL_SOURCE=perception`),
        # which is what a real cell has: the tracker's own estimate of where the
        # fruit is and how fast it moves, measured from the camera, instead of the
        # simulator's `spawner.position`/`velocity`. The diameter stays the measured
        # value for now - `perception.measure` does not hand its radius back yet, and
        # a truth diameter in a perception cell must be named rather than assumed.
        if getattr(self, "_goal_perception", False):
            if self._percept_pos is not None:
                position = np.asarray(self._percept_pos, dtype=np.float32)[:3]
                velocity = np.asarray(self._percept_vel, dtype=np.float32)[:3]
                if self._percept_dia is not None:
                    diameter = float(self._percept_dia)
            else:
                # No frame yet: the cell's own geometry (the belt's pick point and
                # a nominal upstream lead), never the simulator's fruit state. The
                # first observation replaces all three with measurements.
                position = np.array(
                    [float(self.cfg.pick_x), float(self.cfg.pick_y) + 0.45,
                     float(self.belt_top) + 0.05], dtype=np.float32
                )
                velocity = np.zeros(3, dtype=np.float32)
                diameter = 0.060
        # P143: **the goal can be the intercept, not the current position**.
        # Measured on the shipped direct loop: the policy closes the finger
        # (min 0.005-0.016) while the jaws are still **128-155 mm** from the
        # fruit - both arms - and the handover gate needs 60 mm, so the primitive
        # never fires. 13 cm at 0.12 m/s is ~1.1 s of belt travel: the model aims
        # where the fruit *is* and arrives a second late. The scripted line fixed
        # exactly this with the tracker (`FRUIT_TRACK`, P136) but that is scoped to
        # `scripted=True`, so it never reaches the policy. `FRUIT_GOAL_LEAD=<s>`
        # moves the goal forward by the fruit's own velocity, which is already in
        # the observation - a zero-shot change, no retraining.
        lead = float(os.environ.get("FRUIT_GOAL_LEAD", "0.0"))
        if lead > 0.0 and np.all(np.isfinite(velocity)):
            position = position + velocity * lead
        # P225r: **the goal's y clamp** (default off). The chase census (RESULTS
        # 4n) reads 39 % of the 0.12/seed-101 decisions at a joint limit: the
        # goal follows a fruit that has passed the station, the policy keeps
        # following it downstream and the arm pins at a limit. With
        # `FRUIT_GOAL_Y_CLAMP=<y>` the goal stops at that downstream bound and
        # the velocity's y component is zeroed with it, so the policy holds at
        # the band edge instead of chasing. It is a goal-space change (the model
        # has not seen a clamped goal), so it is a measured cell, not a default.
        _yclamp = os.environ.get("FRUIT_GOAL_Y_CLAMP", "").strip()
        if _yclamp:
            _ymin = float(_yclamp)
            if float(position[1]) < _ymin:
                position = np.array(
                    [float(position[0]), _ymin, float(position[2])],
                    dtype=np.float32,
                )
                velocity = np.zeros(3, dtype=np.float32)
        values = [
            *position,
            *velocity,
            float(diameter),
            float(bin_index),
        ]
        if self._goal_aux:
            speed, accel = self._belt_state()
            values.extend([speed, accel])
        # P145d.8 diagnostic: a constant offset on the goal's x, so the *causal*
        # use of the fruit's lateral position can be read in the closed loop
        # (the aim is measured against the truth; a policy that ignores the goal's
        # x returns the same jaw x under a +100 mm offset). Not a control knob.
        _dx = float(os.environ.get("FRUIT_GOAL_X_OFFSET", "0.0") or 0.0)
        if _dx:
            values[0] = float(values[0]) + _dx
        return np.array(values, dtype=np.float32)

    # ------------------------------------------------------------------ #
    # P145: the measured goal
    # ------------------------------------------------------------------ #
    def _wrist_depth_tick(self) -> None:
        """P214 bench: one mask-free wrist depth read, guided by the head estimate.

        The wrist pair is authored with `FRUIT_WRIST_ANNOTATORS` (P213 can leave
        it RGB+depth only). There is no instance mask to segment, so the head's
        own estimate (`self._percept_pos`) is projected into the wrist frame and
        a small disk of depth pixels around it is fitted as a sphere. Reporting
        only: the goal, the policy and the control loop do not read this result.
        It exists to answer whether the second view is usable before building a
        mask-free tracker.
        """
        if not self._wrist_depth_probe or self._sample is None:
            return
        if getattr(self, "_percept_pos", None) is None:
            return
        side = self._active
        entry = getattr(self.scene, "wrist_cameras", {}).get(side)
        if entry is None:
            return
        task = self.task
        arm = task.arms[side]
        try:
            jaw = np.asarray(arm.jaw_centre(), dtype=float)
            axis = np.asarray(arm.approach_axis(), dtype=float)
            axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
            rot = task._quat_matrix(np.asarray(arm.tcp_pose()[1], dtype=float))
            side_vec = np.asarray(rot[:, 0], dtype=float)
            position = (
                jaw
                - float(getattr(task, "_wrist_back", 0.06)) * axis
                + float(getattr(task, "_wrist_side", 0.045)) * side_vec
            )
            target = np.asarray(self._percept_pos, dtype=float)
            self.scene.set_wrist_pose(side, position, target)
            self._RenderingManager.render()
            raw = entry[1].get_data("distance_to_image_plane")
            if raw is None:
                return
            depth = np.asarray(raw[0].numpy(), dtype=np.float32)
            if depth.ndim == 3:
                depth = depth[..., 0]
            if depth.ndim != 2:
                return
            if self._wrist_depth_model is None:
                focal = float(os.environ.get(
                    "FRUIT_WRIST_FOCAL", str(self.cfg.camera_focal_length)))
                ax, ay = (
                    float(v) for v in os.environ.get(
                        "FRUIT_WRIST_APERTURE", "0.036,0.02025").split(",")
                )
                self._wrist_depth_model = CameraModel(
                    depth.shape[1], depth.shape[0], focal, ax, ay,
                    np.eye(3), np.zeros(3),
                )
            model = self._wrist_depth_model
            model.update_pose(self.scene, f"/World/WristCamera_{side}")
            p_cam = (target - model.translation) @ model.rotation
            if float(p_cam[2]) >= -0.03:
                return
            h, w = depth.shape[:2]
            fx, fy, cx, cy = model.intrinsics(h, w)
            u = float(cx - fx * p_cam[0] / p_cam[2])
            v = float(cy + fy * p_cam[1] / p_cam[2])
            radius = int(os.environ.get("FRUIT_WRIST_PROBE_R", "35"))
            vv, uu = np.mgrid[0:h, 0:w]
            disk = (uu - u) ** 2 + (vv - v) ** 2 <= radius * radius
            py, px = np.nonzero(disk)
            if len(px) == 0:
                return
            pix = np.stack([px, py], axis=1)
            z = depth[py, px].astype(float)
            finite = np.isfinite(z) & (z > 0.03)
            if int(finite.sum()) < 12:
                return
            z_med = float(np.median(z[finite]))
            band = np.abs(z - z_med) <= float(
                os.environ.get("FRUIT_WRIST_PROBE_BAND", "0.05")
            )
            keep = finite & band
            if int(keep.sum()) < 12:
                return
            points = model.backproject(
                depth, pix[keep][:: max(1, int(os.environ.get(
                    "FRUIT_PERCEPTION_STRIDE", "2")))]
            )
            centre, fit_r, rms = _fit_sphere(points, trim=2.5)
            if centre is None or not math.isfinite(fit_r):
                return
            truth = np.asarray(self.spawner.position(self._sample), dtype=float)
            err = float(np.linalg.norm(centre - truth)) * 1e3
            self._wrist_depth_rows += 1
            self._say(
                f"[wrist-depth] t={self._step} side={side} u={u:.0f} v={v:.0f} "
                f"px={int(keep.sum())} fit_r={fit_r * 1e3:.1f}mm "
                f"rms={rms * 1e3:.2f}mm err={err:.2f}mm "
                f"head_err={float(getattr(self, '_percept_last_err', float('nan'))):.2f}mm"
            )
        except Exception as exc:  # noqa: BLE001 - a bench probe must not stop the run
            self._say(f"[wrist-depth] failed: {exc}")

    def _perceive_tick(self, depth, seg, labels) -> None:
        """One depth+mask measurement -> the tracker -> the goal.

        No simulator fruit state is read here. The only inputs are the rendered
        depth, the instance mask, the fitted sphere and the camera's calibration -
        the same pipeline P135 validated at 1.98 mm (bench) and which the scripted
        line uses as `FRUIT_TRACK_SOURCE=depth`. Doesn't render: `_observe`
        already did that.
        """
        sample = self._sample
        if sample is None or depth is None or seg is None:
            return
        if self._percept_cfg is None:
            # Lazy: `__init__` resolves the knob before the scene config exists.
            self._percept_cfg = track_config_from_env(os.environ, "depth")
            self._percept_bias = np.asarray(_calibration_bias("head"), dtype=float)
            # P225k: a **direct-only** bias override on top of the calibration
            # file (mm). The bench bias was measured on the scripted depth path;
            # the direct lane's `[close] dx` reads 2-17 mm outboard, so the
            # residual is measurable per axis here and adjustable without moving
            # the scripted reader (which never reads this env).
            _adj = os.environ.get("FRUIT_PERCEPTION_BIAS_ADJUST", "").strip()
            if _adj:
                parts = [float(item) for item in _adj.split(",")]
                if len(parts) != 3:
                    raise ValueError(
                        "FRUIT_PERCEPTION_BIAS_ADJUST needs x,y,z in mm"
                    )
                self._percept_bias = self._percept_bias + np.asarray(
                    parts, dtype=float
                ) / 1000.0
            self._percept_roi = (
                workcell_roi(self.cfg)
                if os.environ.get("FRUIT_PERCEPTION_ROI", "1") == "1"
                else None
            )
        depth = np.asarray(depth, dtype=np.float32)
        if depth.ndim == 3:
            depth = depth[..., 0]
        seg = np.asarray(seg)
        if seg.ndim == 3:
            seg = seg[..., 0]
        if depth.shape[:2] != seg.shape[:2]:
            self._percept_rejected += 1
            return
        # The instance id of *this* fruit. A missing id is "not in frame", not
        # "the background": the shipped mask channel maps a miss to id 0 and the
        # policy was trained on that, so this path must not reuse it.
        want = getattr(sample, "prim_path", None)
        target_id = None
        for key, value in (labels or {}).items():
            if want and want in str(value):
                target_id = int(key)
                break
        if target_id is None:
            self._percept_missing += 1
            return
        mask = seg == target_id
        margin = int(os.environ.get("FRUIT_PERCEPTION_CLIP_PX", "2"))
        if margin > 0 and (
            mask[:margin].any() or mask[-margin:].any()
            or mask[:, :margin].any() or mask[:, -margin:].any()
        ):
            # A truncated view fits a *smaller* sphere: the centre is biased
            # toward the visible part (P135: 24-32 mm at 0.11 m). Predict instead.
            self._percept_rejected += 1
            return
        pixels = np.argwhere(mask)[:, ::-1]
        # P225k: the **foveal goal** (the user's option 1). Once the full-frame
        # fit has acquired the fruit, every later frame is re-measured inside a
        # crop around the **mask's own centroid** - the instance mask is the
        # fruit's pixels, so this needs no camera extrinsics (the projection
        # variant was measured wrong on this rig: the predicted point fell
        # behind the camera model or off the mask on 96-228 frames/attempt).
        # The crop's median surface depth seeds the fit, the radius is **held**
        # from the first image-only measurement (P135's known-radius rule: the
        # hand occludes the cap and a free fit drifts along the view axis), and
        # only the centre is solved on the crop's pixels. No truth read is an
        # input. The first frame still falls through to the full frame, which
        # seeds both. `FRUIT_PERCEPTION_FOVEA=<px>` is the crop's side; 0 = off.
        _fovea = int(os.environ.get("FRUIT_PERCEPTION_FOVEA", "0") or 0)
        _radius_hold = float(getattr(self, "_percept_radius_hold", 0.0) or 0.0)
        if (
            _fovea > 0
            and self._percept_tracker is not None
            and _radius_hold > 0.005
            and len(pixels) >= 5
        ):
            try:
                cam = self._percept_camera
                if cam is None:
                    cam = CameraModel.from_scene(self.scene, self.cfg)
                    self._percept_camera = cam
                cu = int(round(float(np.median(pixels[:, 0]))))
                cv = int(round(float(np.median(pixels[:, 1]))))
                half = max(8, _fovea // 2)
                sel = pixels[
                    (pixels[:, 0] >= cu - half) & (pixels[:, 0] < cu + half)
                    & (pixels[:, 1] >= cv - half) & (pixels[:, 1] < cv + half)
                ]
                if len(sel) < 6:
                    self._percept_fovea_skip["px"] = (
                        self._percept_fovea_skip.get("px", 0) + 1
                    )
                else:
                    now = float(self._sim_time())
                    sel_pts = cam.backproject(depth, sel)
                    zc = depth[sel[:, 1], sel[:, 0]].astype(float)
                    zfin = zc[np.isfinite(zc) & (zc > 0.05)]
                    if len(zfin) < 4:
                        raise ValueError("fovea: no usable depth")
                    zmed = float(np.median(zfin))
                    # The surface point under the centroid at the crop's median
                    # depth (`backproject`'s exact inverse; no depth-array write).
                    fx, fy, cx, cy = cam.intrinsics(seg.shape[0], seg.shape[1])
                    x_cam = (cu - cx) / fx * zmed
                    y_cam = -(cv - cy) / fy * zmed
                    surface = cam.rotation @ np.array(
                        [x_cam, y_cam, -zmed], dtype=float
                    ) + cam.translation
                    ray = surface - cam.translation
                    ray = ray / max(float(np.linalg.norm(ray)), 1e-9)
                    centre0 = surface + ray * _radius_hold
                    centre, rms = _fit_sphere_known_radius(
                        sel_pts, _radius_hold, centre0
                    )
                    if centre is None or not np.all(np.isfinite(centre)):
                        self._percept_fovea_skip["fit"] = (
                            self._percept_fovea_skip.get("fit", 0) + 1
                        )
                    else:
                        centre = np.asarray(centre, dtype=float) - self._percept_bias
                        ok = True
                        if self._percept_roi is not None:
                            lo = self._percept_roi
                            ok = (
                                lo[0] <= centre[0] <= lo[1]
                                and lo[2] <= centre[1] <= lo[3]
                                and lo[4] <= centre[2] <= lo[5]
                            )
                        if not ok:
                            self._percept_fovea_skip["roi"] = (
                                self._percept_fovea_skip.get("roi", 0) + 1
                            )
                        else:
                            self._percept_tracker.update(centre, now)
                            self._percept_pos = np.asarray(
                                self._percept_tracker.position, dtype=float
                            )
                            self._percept_vel = np.asarray(
                                self._percept_tracker.velocity, dtype=float
                            )
                            self._percept_dia = float(2.0 * _radius_hold)
                            self._percept_last_rms = (
                                float(rms) if math.isfinite(rms) else 0.0
                            )
                            self._percept_fovea_frames = int(
                                getattr(self, "_percept_fovea_frames", 0)
                            ) + 1
                            self._percept_frames += 1
                            if self._percept_diag:
                                try:
                                    truth = np.asarray(
                                        self.spawner.position(sample), dtype=float
                                    )
                                    err = float(
                                        np.linalg.norm(self._percept_pos - truth)
                                    )
                                    self._percept_last_err = err * 1e3
                                    self._percept_errs.append(err)
                                    if (
                                        float(getattr(self, "_last_finger", 1.0))
                                        < 0.030
                                    ):
                                        self._percept_errs_close.append(err)
                                except Exception:  # noqa: BLE001 - bench only
                                    pass
                            return
            except Exception as exc:  # noqa: BLE001 - the fovea is an optimisation
                self._percept_fovea_fail = int(
                    getattr(self, "_percept_fovea_fail", 0)
                ) + 1
                if os.environ.get("FRUIT_PERCEPTION_FOVEA_DIAG", "0") == "1":
                    # A print, not a note: a new note string is a new failure
                    # key in the direct lane's ledger (P38's rule), and the
                    # fovea is an optimisation that must not change the classes.
                    from .common import say as _say

                    _say(
                        f"[fovea] ep {self._episode} t={self._sim_time():.2f} "
                        f"fail={type(exc).__name__}: {exc}"
                    )
        min_px = int(os.environ.get("FRUIT_PERCEPTION_MIN_PX", "60"))
        # P225h: the **small-fruit** perception floor. The shipped 60 px is the
        # P135 reliability bar for the 5-7 cm pool; a 3.1-3.9 cm lychee/
        # strawberry is ~12 px even at the head's 240x424, so the 60 px floor
        # refused every small frame and the filter coasted to the station's
        # nominal - the measured `[close]` fired 88-383 mm from the fruit. The
        # small mask at 12 px is enough for the fit (`err_close_p50` 1.5-4.9 mm,
        # the `L16P12` cell 0/5 -> 3/4). Scoped by the presented fruit's
        # diameter (the env's size class, the same field the small handover
        # uses); the 5-7 cm pool keeps 60. `FRUIT_PERCEPTION_MIN_PX_SMALL=0`
        # restores the pre-P225h behaviour on every size.
        _small_dia = float(
            os.environ.get("FRUIT_PERCEPTION_SMALL_DIA", "0.040") or 0.040
        )
        _min_small = int(
            os.environ.get("FRUIT_PERCEPTION_MIN_PX_SMALL", "12") or 0
        )
        if (
            _min_small > 0
            and float(getattr(sample, "diameter", 1.0)) <= _small_dia
        ):
            min_px = min(min_px, _min_small)
        if len(pixels) < max(8, min_px):
            self._percept_rejected += 1
            return
        stride = max(1, int(os.environ.get("FRUIT_PERCEPTION_STRIDE", "2")))
        pixels = pixels[::stride]
        if self._percept_camera is None:
            try:
                self._percept_camera = CameraModel.from_scene(self.scene, self.cfg)
            except Exception as exc:  # noqa: BLE001 - a missing calibration is fatal to this path
                self._notes.append(f"perception: no camera model ({exc})")
                self._goal_perception = False
                return
        points = self._percept_camera.backproject(depth, pixels)
        z = depth[pixels[:, 1], pixels[:, 0]].astype(float)
        finite = np.isfinite(z) & (z > 0.05)
        if not np.any(finite):
            self._percept_rejected += 1
            return
        band = np.abs(z - np.median(z[finite])) <= 0.05
        keep = finite & band
        points = points[keep]
        if len(points) < 12:
            self._percept_rejected += 1
            return
        # P225i: the **spheroid** fit for the small fruit (P135's shape knob,
        # previously only in `FruitPerception`). A strawberry is conical, not a
        # sphere; the equatorial disc the close consumes is the short axis.
        # Scoped to the small by `FRUIT_PERCEPTION_SHAPE_SMALL`; the 5-7 cm pool
        # keeps the sphere unless `FRUIT_PERCEPTION_SHAPE=spheroid` is explicit.
        _shape = os.environ.get("FRUIT_PERCEPTION_SHAPE", "").strip().lower()
        _shape_small = os.environ.get(
            "FRUIT_PERCEPTION_SHAPE_SMALL", ""
        ).strip().lower()
        if _shape_small and float(getattr(sample, "diameter", 1.0)) <= float(
            os.environ.get("FRUIT_PERCEPTION_SMALL_DIA", "0.040") or 0.040
        ):
            _shape = _shape_small
        # The spheroid is the **conical** fruit's shape; the round lychee's
        # spheroid fit read rms 14.88 mm (the sphere 0.1-0.3) and cost the
        # `N12P12FSs` lychee, so the species list is the correct scope.
        _shape_species = os.environ.get(
            "FRUIT_PERCEPTION_SHAPE_SPECIES", ""
        ).strip().lower()
        _spheroid_cats = {
            item.strip().lower()
            for item in _shape_species.split(",")
            if item.strip()
        }
        if _spheroid_cats and str(
            getattr(sample, "category", "")
        ).lower() in _spheroid_cats:
            _shape = "spheroid"
        if _shape == "spheroid":
            centre, _long_r, radius, rms = _fit_spheroid(points, axis=1)
        else:
            centre, radius, rms = _fit_sphere(
                points, trim=float(os.environ.get("FRUIT_PERCEPTION_TRIM", "2.5"))
            )
        if centre is None or not math.isfinite(radius) or not 0.005 < radius < 0.15:
            self._percept_rejected += 1
            return
        centre = np.asarray(centre, dtype=float) - self._percept_bias
        if self._percept_roi is not None:
            lo = self._percept_roi
            if not (
                lo[0] <= centre[0] <= lo[1]
                and lo[2] <= centre[1] <= lo[3]
                and lo[4] <= centre[2] <= lo[5]
            ):
                self._percept_rejected += 1
                return
        now = float(self._sim_time())
        if self._percept_tracker is None:
            self._percept_tracker = FruitTracker(
                self._percept_cfg, belt_velocity=None, tau=0.0
            )
            self._percept_tracker.reset(centre, now)
        else:
            self._percept_tracker.update(centre, now)
        self._percept_pos = np.asarray(self._percept_tracker.position, dtype=float)
        self._percept_vel = np.asarray(self._percept_tracker.velocity, dtype=float)
        self._percept_dia = float(2.0 * radius)
        #: P225k: the radius the fovea holds (image-only, from a full cap).
        self._percept_radius_hold = float(radius)
        self._percept_last_rms = float(rms)
        self._percept_frames += 1
        if self._percept_diag:
            try:
                truth = np.asarray(self.spawner.position(sample), dtype=float)
                err = float(np.linalg.norm(self._percept_pos - truth))
                self._percept_last_err = err * 1e3
                self._percept_errs.append(err)
                _vec = self._percept_pos - truth
                self._percept_err_vec.append(_vec)
                if float(getattr(self, "_last_finger", 1.0)) < 0.030:
                    self._percept_errs_close.append(err)
                    self._percept_err_vec_close.append(_vec)
            except Exception:  # noqa: BLE001 - bench column only
                pass

    def _percept_report(self) -> str:
        """The `[percept]` row: what the camera measured, and the bench error."""
        if not getattr(self, "_goal_perception", False):
            return ""
        err = float("nan")
        if self._percept_diag and self._percept_pos is not None and self._sample is not None:
            # Bench-only column (P135's convention): the truth read is never an
            # input to the estimate or the policy.
            truth = np.asarray(self.spawner.position(self._sample), dtype=float)
            err = float(np.linalg.norm(self._percept_pos - truth)) * 1000.0
        def _pct(values, q):
            if not values:
                return "-"
            return format(float(np.percentile(values, q)) * 1000.0, ".1f")

        pos = "-"
        if self._percept_pos is not None:
            pos = ",".join(format(float(v), "+.3f") for v in self._percept_pos)
        vel = "-"
        if self._percept_vel is not None:
            vel = ",".join(format(float(v), "+.3f") for v in self._percept_vel)
        def _vmed(values):
            arr = [np.asarray(v, dtype=float) for v in values]
            if not arr:
                return "-"
            med = np.median(np.asarray(arr), axis=0) * 1000.0
            return ",".join(format(float(v), "+.1f") for v in med)

        return (
            f"[percept] episode {self._episode} frames={self._percept_frames} "
            f"fovea={int(getattr(self, '_percept_fovea_frames', 0))} "
            f"fovea_fail={int(getattr(self, '_percept_fovea_fail', 0))} "
            f"fskip={dict(getattr(self, '_percept_fovea_skip', {}))} "
            f"rejected={self._percept_rejected} missing={self._percept_missing} "
            f"pos={pos} vel={vel} "
            f"dia={format(self._percept_dia * 1000.0, '.1f') if self._percept_dia else '-'}mm "
            f"rms={format(self._percept_last_rms * 1000.0, '.2f')}mm "
            f"err={format(err, '.1f') if err == err else '-'}mm "
            f"err_p50={_pct(self._percept_errs, 50)}mm "
            f"err_p90={_pct(self._percept_errs, 90)}mm "
            f"err_n={len(self._percept_errs)} "
            f"err_close_p50={_pct(self._percept_errs_close, 50)}mm "
            f"err_close_n={len(self._percept_errs_close)} "
            f"err_vec={_vmed(getattr(self, '_percept_err_vec', []))} "
            f"err_vec_close={_vmed(getattr(self, '_percept_err_vec_close', []))} "
            f"jaw_y={float(getattr(self, '_expert_jaw_y', float('nan'))):+.3f}"
        )

    def _apply_contact_servo(self, arm, action: np.ndarray) -> bool:
        """P173: the contact phase's per-tick aim servo. Returns True if it acted.

        The measured boundary this addresses: a 7-15 Hz chunk has to predict the
        belt's 32 mm of travel per decision and its own error is 30 mm (18 mm
        sampler spread + 24 mm bias, `logs/p145/sampler_var.py`), and at the latch
        the hand sits **75-86 mm** lateral of the fruit because the shipped ramp
        latches on a one-dimensional (along-belt) criterion. So the arm's command
        for the contact window is re-derived **every tick** from the perceived
        fruit and applied with one position-only IK step (the scripted catch-up's
        form); the committed ramp still owns the finger, gated on the aim being
        reached so it cannot close on air.

        Default off (`FRUIT_CONTACT_SERVO`), and it decides no endpoint: the
        model's phase gate still decides *when* the contact phase begins.
        """
        if getattr(self, "_percept_tracker", None) is None:
            return False
        try:
            _jaw0 = np.asarray(arm.jaw_centre(), dtype=float)
            _dy0 = float(self._goal[1]) - float(_jaw0[1])
        except Exception:  # noqa: BLE001 - no geometry read, no servo
            return False
        # P198: arm only while the fruit is **upstream** (or level) of the jaw.
        # Measured defect: `<= arm_dy` is satisfied by any *negative* `dy` too, so
        # an attempt whose fruit had already passed armed the servo and the servo
        # then chased it downstream for its whole window - the `[servo]` trace of a
        # 3.1 cm lychee reads the aim running `y -0.242 -> -0.562` (1 mm/tick, the
        # belt's own speed) with the jaw 500 mm behind and `hold` growing to 536 mm,
        # never latching. A fruit already downstream cannot be caught at 1 mm/tick,
        # so the servo now declines and the model keeps the hand (its own approach),
        # which is at worst no worse than a chase.
        if (not getattr(self, "_servo_on", False)
                and -float(self._servo_behind_tol) <= _dy0 <= float(self._servo_arm_dy)):
            self._servo_on = True
        if not getattr(self, "_servo_on", False):
            return False
        if (self._close_t0 is not None
                and int(self._step) - int(self._close_t0) > int(self._servo_ticks)):
            return False
        _now = float(self._sim_time())
        _age = _now - float(self._percept_tracker.t)
        _coast = float(getattr(self, "_percept_coast_s", 1.0))
        if _age > _coast and getattr(self, "_servo_last_aim", None) is not None:
            # The tracker has not been updated for longer than a 30 Hz filter is
            # trusted for (the hand occludes the fruit exactly at the close). Do
            # **not** extrapolate: freeze the last aim. Measured without this,
            # the aim locked onto the hand and ran to x = 0.05 (off the belt),
            # carrying the payload out of the lane (`fruit fell off the line`).
            _aim = np.asarray(self._servo_last_aim, dtype=float)
        else:
            _lead_now = (self._servo_lead_right if self._active == "right"
                         else float(self._servo_lead))
            _h = min(_age + _lead_now, _coast + _lead_now)
            if self._servo_truth:
                # P178 bench: the aim from the **rigid body** instead of the
                # estimator - decides perception vs geometry, never shipped.
                _aim = np.asarray(self.spawner.position(self._sample), dtype=float)
            else:
                _aim = np.asarray(self._percept_tracker.predict_at(_h), dtype=float)
            _aim = _aim + np.array([0.0, 0.0, float(self._servo_seat)])
            self._servo_last_aim = _aim.copy()
        arm.hold_quaternion = None
        _err = arm.ik_step(arm.tcp_target_for_jaw(_aim))
        if self._close_t0 is not None or abs(float(_err)) <= float(self._servo_gate):
            finger = float(np.clip(action[7], 0.0, 0.044))
            if self._close_ramp:
                finger = self._close_ramp_command(arm, finger)
            # P225f: the carry force servo (default 0 = a no-op)
            finger = self._carry_force_adjust(arm, finger)
        else:
            finger = float(arm.OPEN)
        self._last_finger = finger
        self.scene.robot.set_dof_position_targets(
            [[finger, finger]], dof_indices=list(arm.finger_dofs)
        )
        if self._servo_diag and self._step % 4 == 0:
            _tcp = np.asarray(arm.tcp_position(), dtype=float)
            _jawm = np.asarray(arm.jaw_centre(), dtype=float)
            _d = _tcp - arm.tcp_target_for_jaw(_aim)
            self._say(
                f"[servo] t={self._step} err={float(_err) * 1e3:+.1f}mm "
                f"d={np.array2string(_d * 1e3, precision=0)}mm "
                f"aim={np.array2string(_aim, precision=3)} "
                f"jaw={np.array2string(_jawm, precision=3)} "
                f"hold={self._hold_mm(arm):.0f}mm "
                f"finger={finger:.4f} latched={int(self._close_t0 is not None)}"
            )
        return True

    def _fire_row(self, arm, finger: float, fired: bool) -> None:
        """P194: one `[fire]` row - the state at the model's close decision.

        The trigger's own inputs at the tick the finger first asks to close (or at
        the attempt's end, `fired=0`): the jaw-fruit cycle in the trigger's frame
        (`dy` along the belt, `dx` lateral), the plain gap, the fruit's x, the
        finger value and the phase. Reporting only, one row per attempt.
        """
        try:
            jaw = np.asarray(arm.jaw_centre(), dtype=float)
            fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
            gap = float(np.linalg.norm(fruit - jaw)) * 1e3
            dy = float(fruit[1] - jaw[1]) * 1e3
            dx = float(fruit[0] - jaw[0]) * 1e3
            self._say(
                f"[fire] t={self._step} arm={self._active} fired={int(fired)} "
                f"gap={gap:5.0f}mm dy={dy:+6.0f}mm dx={dx:+6.0f}mm "
                f"fruit_x={float(fruit[0]):.3f} fing={float(finger):.4f} "
                f"phase={self._last_phase}"
            )
        except Exception:  # noqa: BLE001 - reporting only
            pass

    def _hold_mm(self, arm) -> float:
        """P183: how far the payload is from the jaw centre [mm] (reporting only).

        The one number that says whether the pinch still holds the payload: a seat
        is 70-80 mm, a lost payload grows without bound. Not a control input.
        """
        try:
            return float(np.linalg.norm(
                np.asarray(self.spawner.position(self._sample), dtype=float)
                - np.asarray(arm.jaw_centre(), dtype=float)
            )) * 1e3
        except Exception:  # noqa: BLE001
            return float("nan")

    def _pad_axis_row(self, arm, _tac=None) -> str:
        """P182: the payload's offset resolved in the **tool axis** [mm].

        The plate is 84.902 mm long from the finger link origin along the tool axis
        (`logs/p66/COLLIDER_READ.md`), so a payload whose axial distance is close to
        that length is covered only by its own top edge - which no centre-distance
        measure can see. Reporting only (one row per attempt, diag-gated).
        """
        try:
            tax = np.asarray(arm.approach_axis(), dtype=float)
            tax = tax / max(float(np.linalg.norm(tax)), 1e-9)
            rel = (np.asarray(self.spawner.position(self._sample), dtype=float)
                   - np.asarray(arm.jaw_centre(), dtype=float))
            d_ax = float(np.dot(rel, tax))
            d_lat = float(np.linalg.norm(rel - d_ax * tax))
            tilt = float(np.degrees(np.arccos(np.clip(-tax[2], -1.0, 1.0))))
            return (f"tax={np.array2string(tax, precision=2)} tilt={tilt:.1f}deg "
                    f"dax={d_ax * 1000:+.1f}mm dlat={d_lat * 1000:.1f}mm")
        except Exception:  # noqa: BLE001 - reporting only
            return "tax=n/a"

    def _apply_place_servo(self, arm, action: np.ndarray) -> bool:
        """P175: the place as a measured-target loop. Returns True if it acted.

        Lift clear of the pick station, transit over the destination's own place
        point (``task.jaw_target("place{bin}")``), lower, and open the pads - each
        step advanced by one position-only IK update per tick, so the phase changes
        on a **measured** error, not on a clock. The learned policy still chooses
        the fruit, the arm and the bin (``_bin_index``); this only serves the pose.
        """
        side = self._active
        try:
            place = np.asarray(
                self.task.jaw_target(side, f"place{int(self._bin_index)}"), dtype=float
            )
            belt_top = float(self.task.belt_top)
        except Exception:  # noqa: BLE001 - no pose, no servo
            return False
        try:
            jaw = np.asarray(arm.jaw_centre(), dtype=float)
        except Exception:  # noqa: BLE001
            return False
        # Only serve a place when the **hand is actually holding the fruit**: the
        # latch fires on the ramp's window, not on a successful seat, and driving
        # an empty hand through the pick station knocked the fruit off the belt
        # (measured: `final=(-0.07, +0.09, 0.92)`, x outside the belt).
        try:
            payload = np.asarray(self.spawner.position(self._sample), dtype=float)
            if float(np.linalg.norm(payload - jaw)) > 0.12:
                return False
        except Exception:  # noqa: BLE001
            return False
        # P184: the transit's clearance. P66 measured the LEFT arm's carry rotation
        # collapsing with the lift's *height* (drift_end 23.8-25.7 deg at
        # belt+0.36, 9.7 at +0.28, 0.7 at +0.20) and P71 shipped the low lift for
        # the direct interface - so a 0.30 m servo clearance re-creates the very
        # attitude that the record's loaded slide depends on. The knob is in metres
        # above the belt top; 0.30 is the value this servo shipped with.
        lift_z = belt_top + float(self._place_lift)
        down_z = float(place[2]) - float(self._place_drop)
        far_xy = float(np.linalg.norm(jaw[:2] - place[:2]))
        if getattr(self, "_place_phase", 0) == 0 and jaw[2] < lift_z - 0.02:
            aim = np.array([jaw[0], jaw[1], lift_z])
        else:
            self._place_phase = 1
            if far_xy > 0.02:
                aim = np.array([place[0], place[1], lift_z])
            else:
                aim = np.array([place[0], place[1], down_z])
        _place_vmax = (
            self._place_vmax_right if side == "right" else self._place_vmax_left
        )
        if _place_vmax > 0.0:
            # P184: the **transit's own speed limit**. The direct aim lets the
            # position-only IK step at its own clip, which carries the payload
            # through the ~0.6 m move in ~300 ticks (0.24 m/s at the jaw) - and a
            # soft fruit's hold was measured growing 72 -> 96 mm inside that
            # move. A bounded reference moves the aim, not the arm: the IK still
            # does one step per tick, so nothing else about the loop changes.
            _prev = getattr(self, "_place_aim", None)
            if _prev is None:
                _prev = np.asarray(jaw, dtype=float)
            _step = float(_place_vmax) * (1.0 / 120.0)
            _d = aim - np.asarray(_prev, dtype=float)
            _n = float(np.linalg.norm(_d))
            aim = (np.asarray(_prev, dtype=float) + _d * (_step / _n)) if _n > _step else aim
            self._place_aim = np.asarray(aim, dtype=float).copy()
        arm.hold_quaternion = None
        _err = arm.ik_step(arm.tcp_target_for_jaw(aim))
        over_ok = far_xy <= 0.025
        low_ok = jaw[2] <= down_z + 0.015
        at_place = bool(over_ok and low_ok)
        if at_place:
            # the release's own ramp, from the ramp's held gap to the open stop
            grip = float(getattr(self, "_close_grip_finger", 0.025))
            t = min(1.0, float(getattr(self, "_place_open", 0.0)) + 1.0 / 40.0)
            self._place_open = t
            finger = grip + (float(arm.OPEN) - grip) * t
        else:
            finger = float(np.clip(action[7], 0.0, 0.044))
            if self._close_ramp:
                finger = self._close_ramp_command(arm, finger)
            # P225f: the carry force servo during the place transit (default 0)
            finger = self._carry_force_adjust(arm, finger)
        self._last_finger = finger
        self.scene.robot.set_dof_position_targets(
            [[finger, finger]], dof_indices=list(arm.finger_dofs)
        )
        if self._place_diag and self._step % 4 == 0:
            self._say(
                f"[pservo] t={self._step} err={float(_err) * 1e3:+.0f}mm "
                f"aim={np.array2string(aim, precision=3)} "
                f"jaw={np.array2string(jaw, precision=3)} "
                f"far={far_xy * 1e3:.0f}mm ph={int(getattr(self, '_place_phase', 0))} "
                f"hold={self._hold_mm(arm):.0f}mm "
                f"at={int(at_place)} fing={finger:.4f}"
            )
        return True

    def _close_ramp_command(self, arm, action_finger: float) -> float:
        """P145d.5: the committed 60-tick close ramp, then hold the grip gap."""
        prev = float(getattr(self, "_last_finger", 0.044))
        if self._close_t0 is None:
            finger_trigger = bool(prev > 0.035 and action_finger <= 0.035)
            phase_trigger = False
            if self._close_ramp_trigger == "phase" and prev > 0.035:
                try:
                    _jaw = np.asarray(arm.jaw_centre(), dtype=float)
                    _dy = float(self._goal[1]) - float(_jaw[1])
                    phase_trigger = close_phase_trigger(
                        _dy, self._close_ramp_dy, self._close_ramp_dy_lo
                    )
                except Exception:  # noqa: BLE001
                    phase_trigger = False
            # P145d.11: the trigger **modes are exclusive**. In `phase` mode the
            # policy's own finger must not latch the ramp: its finger channel sits
            # on the action mean (0.0345, the P145d.8 measurement), which crosses
            # the 0.035 threshold at arbitrary times - measured, the apple episode
            # latched at t=104 with the fruit 167 mm away while the phase gate
            # itself had not fired. `finger` mode keeps the pre-P145d.6 behaviour.
            _trigger = phase_trigger if self._close_ramp_trigger == "phase" else finger_trigger
            if _trigger and self._close_ramp_dz_max > 0.0:
                # P225q: a height gate on the latch (default off). `dz` is the
                # measured jaw-above-fruit distance; above the gate the hand is
                # still descending and a close here lands above the fruit (the
                # 110-118 mm `grasped=False` rows). The servo keeps aiming, so the
                # latch simply fires on a later tick.
                try:
                    _dz = float(arm.jaw_centre()[2]) - float(self._goal[2])
                except Exception:  # noqa: BLE001 - no geometry, no gate
                    _dz = 0.0
                if _dz > self._close_ramp_dz_max:
                    _trigger = False
            if not _trigger:
                return action_finger
            self._close_t0 = int(self._step)
            # P166: the **one-shot seat commit** (oracle-reviewed form of B). At
            # the latch the arm is measured 2.6-5 cm above the 70 mm seat; the
            # scripted line closes exactly that gap with its post-descent solver.
            # This is a *commit*, not a servo: one position-only IK to
            # `[jaw_x, jaw_y, fruit_z + 0.070]` at the latch, held for the ramp's
            # ticks, then the policy resumes. It decides no endpoint and adds no
            # feedback - the same class as the finger's committed ramp.
            self._seat_q = None
            if os.environ.get("FRUIT_CLOSE_RAMP_SEAT", "0") == "1":
                try:
                    _j = np.asarray(arm.jaw_centre(), dtype=float)
                    _f = np.asarray(self.spawner.position(self._sample), dtype=float)
                    _aim = np.array([_j[0], _j[1], float(_f[2]) + 0.070])
                    arm.hold_quaternion = None
                    arm.sync_command_to_measured()
                    _res = None
                    for _ in range(80):
                        _res = arm.ik_step(_aim)
                        if _res < 1e-3:
                            break
                    self._seat_resid = float(_res) if _res is not None else float("nan")
                    if arm._q_cmd is not None:
                        self._seat_q = np.asarray(arm._q_cmd, dtype=float)[:7].copy()
                except Exception:  # noqa: BLE001
                    self._seat_q = None
            try:
                quat = np.asarray(arm.tcp_pose()[1], dtype=float)
                # P178: the committed close's **squeeze scale**, the same knob the
                # DAgger expert already reads (`FRUIT_GRIPPER_SQUEEZE`, default
                # 0.98 = the shipped expression). The mechanism it sets: pads at
                # +-s with the fruit offset `dy` along the belt touch a sphere of
                # radius r only while `s <= sqrt(r^2 - dy^2)`; at `s = 0.98 r`
                # that is `dy <= 0.199 r` = 6.8 mm for a 34 mm-radius fruit, and
                # the measured latch `dy` is 10-13 mm - which is why the smaller
                # fruits (the right arm's grade B/C stream) close on air while the
                # larger ones jam.
                gap = float(self.task.pinch_width(self._sample, quat)) * float(
                    os.environ.get("FRUIT_GRIPPER_SQUEEZE", "0.98")
                )
                self._close_grip_finger = float(arm.gripper_value_for_separation(gap))
            except Exception:  # noqa: BLE001 - a missing sample must not stop the close
                self._close_grip_finger = 0.027
            # P145d.6: the latch's own 3-D certificate. The xy gap is the
            # proximity the phase gate reads; the **dz** is what the earlier
            # cells could not see (a hand 12 cm above the fruit closes on air and
            # still reports a 1-2 cm xy gap). One row per attempt.
            if self._policy_trace:
                try:
                    _jaw = np.asarray(arm.jaw_centre(), dtype=float)
                    _fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
                    self._say(
                        f"[close] t={self._step} trigger="
                        f"{'phase' if phase_trigger else 'finger'} "
                        f"xy={float(np.linalg.norm(_fruit[:2]-_jaw[:2]))*1000:.0f}mm "
                        f"dz={float(_jaw[2]-_fruit[2])*1000:+.0f}mm "
                        f"dx={float(_fruit[0]-_jaw[0])*1000:+.0f}mm "
                        f"jaw_z={float(_jaw[2]):.3f} fruit_z={float(_fruit[2]):.3f} "
                        f"grip={self._close_grip_finger:.4f} "
                        # P177: the **measured** pad span at the latch (one read,
                        # once per attempt). A commanded grip that does not close
                        # the pads is otherwise invisible: the right arm latches at
                        # xy 14-16 mm and never holds, and `grip` alone cannot say
                        # whether the pads moved.
                        f"sep={float(arm.jaw_separation())*1000:.1f}mm "
                        f"pads=[{','.join(format(float(v), '.2f') for v in self._pad_forces(self.task.tactile.read().get(self._active)))}] "
                        f"seat_res={getattr(self, '_seat_resid', float('nan'))*1000:.0f}mm"
                    )
                except Exception:  # noqa: BLE001
                    pass
        if self._close_grip_finger is None:
            self._close_grip_finger = 0.027
        elapsed = int(self._step) - int(self._close_t0)
        # P225p: the tactile re-close latch (default off). The ramp completed with
        # no pad loaded and the fruit still near the jaws -> hold open, then
        # re-close once, so the second ramp can close on the fruit instead of on
        # air. `_goal` is the perceived position (never the simulator's), and the
        # distance gate keeps it off an attempt whose fruit has already left.
        if (
            self._tac_reclose
            and self._reclose_until is None
            and not self._reclosed
            and elapsed >= self._close_ramp_ticks
        ):
            try:
                _tac = self.task.tactile.read().get(self._active)
                _pads = self._pad_forces(_tac) if _tac is not None else []
                _psum = float(sum(_pads)) if _pads else 0.0
                _xy = float(
                    np.linalg.norm(
                        np.asarray(self._goal[:2], dtype=float)
                        - np.asarray(arm.jaw_centre(), dtype=float)[:2]
                    )
                )
            except Exception:  # noqa: BLE001 - no signal, no action
                _psum, _xy, _pads = float("inf"), float("inf"), []
            if _psum < self._tac_reclose_min and _xy <= self._tac_reclose_xy:
                self._reclose_until = int(self._step) + max(
                    1, self._tac_reclose_open
                )
                self._reclosed = True
                if self._carry_force_diag or os.environ.get(
                    "FRUIT_TAC_RECLOSE_DIAG", "0"
                ) == "1":
                    self._say(
                        f"[reclose] t={self._step} arm={self._active} "
                        f"pads=[{','.join(format(float(v), '.2f') for v in _pads)}] "
                        f"xy={_xy * 1e3:.0f}mm open={self._tac_reclose_open}"
                    )
        if self._reclose_until is not None:
            if int(self._step) < int(self._reclose_until):
                return float(arm.OPEN)
            self._reclose_until = None
            self._close_t0 = int(self._step)
            elapsed = 0
        if elapsed >= self._close_ramp_ticks:
            # Hold the grip gap through the lift/carry. A re-close request from
            # the policy (its finger re-opens at the next chunk) is NOT a release;
            # only the place phase hands the finger back. (Measured: releasing on
            # any >0.040 command re-opened at the lift and defeated the ramp.)
            if getattr(self, "_last_phase", None) == 3:
                self._close_t0 = None
                self._servo_on = False
                self._servo_last_aim = None
                self._place_phase = 0
                self._place_open = 0.0
                self._finger_was_closed = False
                self._scored_release = False
                self._close_ramp_reported = False
                self._close_ramp_last = -1
                self._fire_logged = False
                self._force_closed_gap = None
                self._close_grip_finger = None
                return action_finger
            return float(self._close_grip_finger)
        ramp = min_jerk_ramp(
            float(arm.OPEN), float(self._close_grip_finger), self._close_ramp_ticks
        )
        # P178: the ramp's own **time series** (every 4 ticks while the diag is on)
        # - one row cannot separate "still closing at the end" from "flat short of
        # the command", and those have opposite fixes.
        if (self._close_ramp_diag and int(elapsed) % 4 == 0
                and int(elapsed) > int(getattr(self, "_close_ramp_last", -1))):
            self._close_ramp_last = int(elapsed)
            try:
                _tac = self.task.tactile.read().get(self._active)
                self._say(
                    f"[close-ramp] t={self._step} arm={self._active} "
                    f"i={int(elapsed):3d} hit={self._step - int(self._close_t0):3d} "
                    f"cmd={float(ramp[min(int(elapsed), len(ramp) - 1)]):.4f} "
                    f"sep={float(arm.jaw_separation()) * 1000:6.1f}mm "
                    f"F={float(getattr(_tac, 'normal_force', float('nan'))):6.2f}N "
                    f"n={int(getattr(_tac, 'contact_count', -1))}"
                )
            except Exception:  # noqa: BLE001 - reporting only
                pass
        # P177: one row the tick the ramp **completes** - the measured pad span
        # and the command that produced it. The latch's span is 98 mm (the open
        # stop) on both arms, so only this row can say whether a commanded close
        # actually brought the pads together (`_close_ramp_diag` once per attempt).
        if (self._close_ramp_diag and not getattr(self, "_close_ramp_reported", False)
                and elapsed >= len(ramp) - 1):
            self._close_ramp_reported = True
            try:
                # P178: the **contact** at the ramp's end, from the existing tactile
                # read. The mapping probe proved both arms' finger command -> span
                # law is identical (2*cmd + 0.010, 0.00 mm error, delta 0), so a
                # span that differs in the loop means something is between the pads
                # on one arm and nothing on the other.
                _tac = self.task.tactile.read().get(self._active)
                _f = getattr(_tac, "normal_force", float("nan"))
                _n = getattr(_tac, "contact_count", -1)
                self._say(
                    f"[close-hold] t={self._step} arm={self._active} "
                    f"sep={float(arm.jaw_separation()) * 1000:.1f}mm "
                    f"fing={float(ramp[-1]):.4f} "
                    f"grip={float(self._close_grip_finger):.4f} "
                    f"F={float(_f):.2f}N n={int(_n)} "
                    # P178: the **jaw (closing) axis** against the belt's -y. The
                    # pads are 10 mm thick plates: if the axis is parallel to the
                    # belt the fruit sits between their *edges*, not their faces,
                    # and a 14-16 mm centre offset is enough to miss it entirely.
                    f"jax={np.array2string(np.asarray(arm.jaw_axis(), dtype=float), precision=2)} "
                    # P178c: the **two pad points** and the fruit, so the row says
                    # whether the pads straddle the payload at all - a jaw_centre
                    # can be 15 mm from the fruit with both pads on the same side
                    # of it, which is the one state the centre cannot see.
                    f"pL={np.array2string(np.asarray(arm.jaw_positions()[0], dtype=float), precision=3)} "
                    f"pR={np.array2string(np.asarray(arm.jaw_positions()[1], dtype=float), precision=3)} "
                    f"fruit={np.array2string(np.asarray(self.spawner.position(self._sample), dtype=float), precision=3)} "
                    # P182: the **tool axis** at the close, and the payload's offset
                    # resolved in it. The plate spans [0, 84.902] mm along the tool
                    # axis from the finger link origin (`logs/p66/COLLIDER_READ.md`:
                    # the box's proximal plane *is* the origin), so `d_ax` decides
                    # whether the plate covers the payload at all - the one quantity
                    # a per-arm attitude difference can change.
                    f"{self._pad_axis_row(arm, _tac)}"
                )
            except Exception:  # noqa: BLE001 - reporting only
                pass
        _value = float(ramp[min(elapsed, len(ramp) - 1)])
        if self._close_force > 0.0:
            # P192: the **force-controlled finger** (P111's named form: stiff in the
            # approach, compliant only inside the closure). The position ramp above
            # follows a *geometric* target (`pinch_width * squeeze`), which is wrong
            # whenever the payload is offset (`dlat` 19-26 mm on the right) or
            # narrower than that estimate - the pads then reach their command with
            # nothing between them (`sep` = the command exactly, `F = 0.00 N`). This
            # keeps closing, at a bounded rate, until the *measured* pinch force
            # reaches the target, with a tick cap so it cannot squeeze forever.
            # Finger-value space: `d(value)/d(span) = 0.5`, so the default rate is
            # 24 mm/s of span.
            try:
                _tac = self.task.tactile.read().get(self._active)
                _F = float(getattr(_tac, "normal_force", 0.0))
            except Exception:  # noqa: BLE001 - no tactile, keep the position ramp
                _F = float("nan")
            if self._force_closed_gap is None:
                self._force_closed_gap = _value
            _over = int(self._step) - int(self._close_t0) - len(ramp)
            if _F < self._close_force and _over <= self._close_force_ticks:
                self._force_closed_gap = max(
                    0.004, float(self._force_closed_gap) - float(self._close_force_rate)
                )
            _value = float(self._force_closed_gap)
            if self._close_ramp_diag and int(elapsed) % 8 == 0:
                self._say(
                    f"[close-force] t={self._step} arm={self._active} "
                    f"over={_over:3d} F={_F:6.2f}N target={self._close_force:5.1f} "
                    f"sep={float(arm.jaw_separation()) * 1000:6.1f}mm val={_value:.4f}"
                )
        return _value

    @staticmethod
    def _pad_forces(reading) -> list[float]:
        """Per-pad forces of one hand's reading [N] (`[]` when unavailable).

        `TactileReading.normal_force` is the **sum** over the hand's contact
        readers; `fingertip_forces` keeps them separate (`left_0`, `left_1` for
        the OpenArm fingers; one entry per pad on the `cage4` hand). The
        asymmetry is the only geometric information two scalar pads preserve
        (GraspTune/CoorGrasp), and a one-sided pinch is P75's measured signature
        of the loaded slide - so the servo can read it, not just the sum.
        """
        try:
            vals = [float(v) for v in getattr(reading, "fingertip_forces", {}).values()]
        except Exception:  # noqa: BLE001 - a missing field is "no signal"
            return []
        return [v for v in vals if math.isfinite(v)]

    def _carry_force_adjust(self, arm, finger: float) -> float:
        """P225f: the carry force servo - the force-controlled finger past the close.

        The same measured-force position loop as P192's close force
        (`_close_ramp_command`), but scoped to the **lift/place carry**: after the
        close ramp, while the hand is closed and the payload has not been
        released, if the measured pinch is below `FRUIT_CARRY_FORCE`, the finger
        command keeps closing at `FRUIT_CARRY_FORCE_RATE` (finger-value space,
        `d(value)/d(span) = 0.5`, so the default 0.0001/tick is 24 mm/s of span)
        until the target, the `FRUIT_CARRY_FORCE_TICKS` cap or the release. The
        drive stays the shipped position drive; this only moves its target.
        Default 0 = no read, no arithmetic, byte-inert.
        """
        if self._carry_force <= 0.0 or self._close_t0 is None:
            return finger
        # P225h: the small fruit is **excluded** by default. The carry force loop
        # is the medium/large fruit's loaded-slide fix (right-only 2/8 -> 4/8);
        # on a 3.1-3.9 cm lychee/strawberry the same loop drives the pads to the
        # 8 mm floor and over-closes (the `L16P12F` cell 2/4 against the
        # min-px-only `L16P12` 3/4). `FRUIT_CARRY_FORCE_SMALL_DIA=0` runs it on
        # every size (the measured negative).
        _force_skip = float(
            os.environ.get("FRUIT_CARRY_FORCE_SMALL_DIA", "0.040") or 0.0
        )
        if (
            _force_skip > 0.0
            and float(getattr(self._sample, "diameter", 1.0)) <= _force_skip
        ):
            return finger
        if int(self._step) - int(self._close_t0) < int(self._close_ramp_ticks):
            return finger
        if self._scored_release:
            return finger
        if float(finger) > 0.035:
            # the hand is opening (the release ramp or the policy's own open);
            # the servo must not fight a release
            return finger
        if self._carry_force_value is None or self._carry_force_t0 is None:
            self._carry_force_value = float(finger)
            self._carry_force_t0 = int(self._step)
        try:
            _tac = self.task.tactile.read().get(self._active)
            _F = float(getattr(_tac, "normal_force", float("nan")))
        except Exception:  # noqa: BLE001 - no tactile, keep the position command
            _F = float("nan")
        _pads = self._pad_forces(_tac) if _tac is not None else []
        # P225o: **bilateral** criterion (default off). The shipped loop stops at
        # the target *sum*, which a one-sided pinch reaches with the other pad at
        # 0 N - P75's measured escape signature (one face at 8-10 N while the
        # other reads 0.00 N and the payload walks out). With this on the loop's
        # error is the **weakest pad's share** (`n * min(f)`, so the target stays
        # "mean per pad"), i.e. it keeps closing while any pad is unloaded.
        if (
            os.environ.get("FRUIT_CARRY_BILATERAL", "0").strip() == "1"
            and len(_pads) >= 2
        ):
            _F = float(len(_pads)) * float(min(_pads))
        _over = int(self._step) - int(self._carry_force_t0)
        #: P225f: the close floor is the **fruit's** own grip minus 4 mm of span
        #: (2 mm per side), not the 8 mm mechanical floor. The 8 mm floor on a
        #: 34 mm lychee is a 26 mm over-closure (the P111/P112 over-closure
        #: class); the measured close grip is the safe reference.
        _grip = getattr(self, "_close_grip_finger", None)
        _floor = 0.004
        if _grip is not None and self._carry_force_floor_margin > 0.0:
            _floor = max(
                0.004, float(_grip) - float(self._carry_force_floor_margin)
            )
        if _F < self._carry_force and _over <= self._carry_force_ticks:
            self._carry_force_value = max(
                _floor,
                float(self._carry_force_value) - float(self._carry_force_rate),
            )
        finger = min(float(finger), float(self._carry_force_value))
        if self._carry_force_diag and int(self._step) % 8 == 0:
            _ptxt = ",".join(format(float(v), ".2f") for v in _pads) or "-"
            self._say(
                f"[carry-force] t={self._step} arm={self._active} "
                f"F={_F:6.2f}N pads=[{_ptxt}] target={self._carry_force:5.1f} "
                f"val={float(finger):.4f} over={_over:3d} "
                f"bilat={os.environ.get('FRUIT_CARRY_BILATERAL', '0')}"
            )
        return finger

    def _phase_for_decision(self) -> int | None:
        """P145c: the action phase, from the perceived fruit + the jaw + the finger.

        ``None`` lets the policy's own router decide (the shipped path, and the
        ``perception`` mode's inside-phase choice). ``dy`` replaces the
        **approach -> grasp** boundary with the scripted line's tracking window on
        the measured along-distance: the demos close when the fruit is within
        ``FRUIT_TRACK_START`` (0.05 m) of the jaw line, and the policy's learned
        router was firing ``grasp`` ~0.4 s earlier because it reads the arm's
        pose. The phase is not an external trigger: both inputs are the cell's
        own depth goal and the robot's measured jaw.
        """
        if self._phase_mode not in ("perception", "dy"):
            return None
        # P145d.12: **the lift transition**. The demos hold 0.53 s after the
        # close and then emit the coarse test lift ("pop"); the cloned `grasp`
        # expert holds through the deployed state instead (measured: a near
        # perfect close - xy 14 mm, dx -6 mm - ends with the jaw at 1.254 and the
        # fruit on the belt). The committed ramp already owns the finger, so the
        # skill manager can own the *transition*: once the ramp has completed,
        # route the action to the `lift` expert. Default off.
        if (
            os.environ.get("FRUIT_CLOSE_RAMP_LIFT", "0") == "1"
            and self._close_t0 is not None
            and int(self._step) - int(self._close_t0) >= int(self._close_ramp_ticks)
            and float(getattr(self, "_last_finger", 0.044)) < 0.030
        ):
            return 2
        if self._sample is None:
            return None
        finger = float(getattr(self, "_last_finger", 0.044))
        gate = getattr(self.policy, "phase_gate", None)
        base = gate.predict(self._goal, np.asarray(self._last_proprio, dtype=np.float32)) \
            if (gate is not None and self._last_proprio is not None) else 0
        if self._phase_mode == "perception":
            return int(base)
        if finger > 0.030:
            try:
                jaw = self.task.arms[self._active].jaw_centre()
                dy = float(self._goal[1]) - float(np.asarray(jaw, dtype=float)[1])
            except Exception:  # noqa: BLE001 - a missing jaw must not stop the loop
                return int(base)
            return 0 if dy > self._phase_dy else 1
        return int(base)

    def _goal_snapshot(self) -> np.ndarray:
        """The goal as the recorder/observation sees it (belt dims refreshed)."""
        self._refresh_goal_aux()
        return self._goal.copy()

    def _refresh_goal_aux(self) -> None:
        """Rewrite the belt dims of the goal in place (no-op with the gate off)."""
        if self._goal_aux and self._goal.size >= 10:
            speed, accel = self._belt_state()
            self._goal[-2] = speed
            self._goal[-1] = accel

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
        if self._tactile_zero:
            # P145 ablation: the channel is present but carries no contact.
            forces = [0.0, 0.0]
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
        if self._cmd_channel:
            # the previous command (0.044 before the first action of an episode)
            parts.append(
                np.array([float(getattr(self, "_last_finger", 0.044))], dtype=np.float32)
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
            "goal": self._goal_snapshot(),
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
        self._infer_this_decision = False
        if self._step % 4 == 0 or getattr(self, "_force_observe", False):
            self._observe()
            self._force_observe = False
        if self.ablate == "zero":
            return np.zeros((self.action_horizon, self.action_dim), dtype=np.float32)
        _right = getattr(self, "_right_policy", None)
        _right_active = _right is not None and self._active == "right"
        _active_policy = _right if _right_active else self.policy
        if _active_policy is None or not _active_policy.ready:
            # P225d: the router's active-only push means only the active arm's
            # buffer is filled; the inactive one is intentionally unready.
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
        self._refresh_goal_aux()
        phase = self._phase_for_decision()
        self._last_phase = phase
        # P170: the **two-model hybrid** - the joint head times the catch (it
        # latches 24-28 of 30), the free-wrist jaw head reconfigures the descent's
        # last 2-5 cm (the scripted catch-up's form). `FRUIT_POLICY_CKPT2=<path>`
        # selects the jaw head for the 60 ticks after the latch; the joint head
        # owns everything else. The two checkpoints must share the proprio width.
        _use2 = bool(
            getattr(self, "_policy2", None) is not None
            and self._close_t0 is not None
            and int(self._step) - int(self._close_t0) <= int(self._close_ramp_ticks)
        )
        if self._hybrid_action:
            # P171: one model, two action forms. The joint form owns the approach
            # and the latch (it times the catch); the free-wrist jaw form owns the
            # 60 ticks after the latch (it reconfigures the descent's last 2-5 cm).
            self._jaw_now = bool(
                self._close_t0 is not None
                and int(self._step) - int(self._close_t0) <= int(self._close_ramp_ticks)
            )
        else:
            self._jaw_now = _use2
        if _use2:
            _runner = self._policy2
        elif (getattr(self, "_right_policy", None) is not None
                and self._active == "right"):
            # P225d: the arm router - the right checkpoint on the right episodes
            _runner = self._right_policy
        else:
            _runner = self.policy
        _kw = dict(
            num_steps=self.ddim_steps if num_steps is None else int(num_steps),
            phase=(None if _use2 else phase),
        )
        if self._eval_latency_mode != "off":
            _t_lat = time.perf_counter()
        chunk = _runner.act(self.proprio(), self._goal, **_kw)
        if self._eval_latency_mode != "off":
            # P228: what this machine actually spent on the decision. `auto`
            # divides it by the control period; the sweep uses an explicit d.
            self._last_infer_ms = (time.perf_counter() - _t_lat) * 1e3
            self._infer_this_decision = True
        if self._ensemble_k > 1:
            # P172: **sample averaging**. The P172 probe measured the sampler's
            # own spread at a fixed close-start state as 18.4 mm TCP-equivalent
            # (p90 31.3) against a 24.4 mm mean-vs-label error and a 32 mm belt
            # travel per 16-tick decision - so half the contact-phase error is
            # *variance*, and the mean of K draws cuts it by sqrt(K). Costs K
            # inferences per decision (the loop is not real time).
            _acc = np.asarray(chunk, dtype=np.float64)
            for _ in range(self._ensemble_k - 1):
                _acc = _acc + np.asarray(
                    _runner.act(self.proprio(), self._goal, **_kw), dtype=np.float64
                )
            chunk = (_acc / float(self._ensemble_k)).astype(np.float32)
            if self._ensemble_diag and self._step % 4 == 0:
                self._say(
                    f"[ens] t={self._step} k={self._ensemble_k} "
                    f"first={np.array2string(np.asarray(chunk[0])[:3], precision=4)}"
                )
        if self._loop_timing:
            # P43 L2: the model-inference stage of the decision period.
            self._loop_t["policy_ms"] += (time.perf_counter() - _loop_start) * 1e3
            self._loop_counts["decisions"] += 1
        if self._route_diag and self.policy is not None:
            try:
                w = getattr(self.policy.model, "last_router_weights", None)
                if w is not None:
                    w = np.asarray(w.detach().float().cpu()).reshape(-1)
                    k = int(w.argmax())
                    self._say(
                        f"[route] t={self._step} skill={k}"
                        f"({('approach', 'grasp', 'lift', 'place', 'recovery')[k]})"
                        f" max={w[k]:.2f} goal_y={float(self._goal[1]):+.3f}"
                    )
            except Exception:  # noqa: BLE001 - reporting only
                pass
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

    def _latency_ticks_for_decision(self) -> int:
        """P228: the control ticks this decision's inference costs the world."""
        if self._eval_latency_mode == "off" or not self._infer_this_decision:
            return 0
        if self._eval_latency_mode == "auto":
            return max(0, int(round(self._last_infer_ms / 1e3 / CONTROL_DT)))
        return int(self._eval_latency_ticks)

    def _inject_latency(self) -> None:
        """Advance the world `d` control ticks with the arm **holding still**.

        `sync-hold` (LIBERO-Dynamic's protocol; Reflex calls the async form the
        alternative): the chunk was computed from the observation at `t`, the
        world moves `d` ticks, and then the chunk is applied. The observation is
        deliberately **not** refreshed here - a real deployment cannot see the
        frames it did not wait for - and nothing is recorded, because no action
        is applied during the pause.

        `_tick`/`_step` advance with the physics so the observation grid, the
        horizon and the close-phase clocks all stay on simulated time.
        """
        d = self._latency_ticks_for_decision()
        if d <= 0 or self._done:
            return
        for _ in range(d):
            self.advance(1)
            self.spawner.enforce_transport()
            self._tick += 1
            self._step += 1
        self._lat_decisions += 1
        self._lat_ticks += int(d)
        self._lat_max = max(self._lat_max, int(d))
        # The displacement field is the point of the row: at the shipped 0.12 m/s
        # one control tick is exactly 1.0 mm, so `d` reads as millimetres. It is
        # computed from the **configured** speed, not a literal, so a cell on a
        # different belt cannot carry a wrong number.
        _v = abs(float(self.cfg.belt_speed))
        self._say(
            f"[lat] d={d} mode={self._eval_latency_mode} "
            f"infer_ms={self._last_infer_ms:.1f} "
            f"sim_ms={d * CONTROL_DT * 1e3:.1f} "
            f"belt_mm={_v * d * CONTROL_DT * 1e3:.1f}"
        )

    def act(self, chunk: np.ndarray | None, execute_steps: int | None = None) -> StepResult:
        """Execute up to ``execute_steps`` actions; returns the step result.

        With event-triggered replanning (``FRUIT_POLICY_EVENT=1``) the horizon
        for this chunk is chosen by `_event_horizon` instead of the passed
        ``execute_steps``; the argument is then the reference/default only.
        """
        steps = self.execute_steps if execute_steps is None else max(1, int(execute_steps))
        if self._ensemble_alpha > 0.0 and chunk is not None:
            _raw_chunk = np.asarray(chunk, dtype=np.float64)
            if steps >= _raw_chunk.shape[0]:
                raise ValueError(
                    "FRUIT_POLICY_ENSEMBLE needs execute_steps < the chunk's "
                    f"horizon (got {steps} against {_raw_chunk.shape[0]})"
                )
            chunk = ensemble_action_chunk(
                self._ensemble_prev, _raw_chunk, steps, self._ensemble_alpha
            )
            self._ensemble_prev = _raw_chunk.copy()
        if self._rel_action and chunk is not None:
            # the chunk's own first frame is the anchor; the measured joints at
            # the chunk's start are the base the offsets are applied to
            try:
                self._rel_first = np.asarray(chunk[0][:7], dtype=float).copy()
                self._rel_base = np.asarray(
                    self.scene.robot.get_dof_positions().numpy()
                ).reshape(-1)[list(self.task.arms[self._active].arm_dofs)].astype(float)
            except Exception:  # noqa: BLE001 - a read failure falls back to absolute
                self._rel_base = None
                self._rel_first = None
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
        if (self._small_handover and self._sample is not None
                and float(self._sample.diameter) <= self._small_handover_dia):
            # P218: the scripted skill owns this attempt end to end. It is the
            # same `task.run` the `--ablate scripted` path uses and the 5/6
            # lychee control measured; the learned policy keeps the large fruit.
            self._run_scripted()
            return self._step_result()
        if (self._handover_side
                and (self._handover_side == "both"
                     or self._handover_side == self._active)):
            # P222: the scripted skill owns a whole arm. The scripted B-heavy
            # control places 6/6 right-arm fruit; the learned right is 2/6.
            self._run_scripted()
            return self._step_result()
        if self.ablate == "scripted":
            self._run_scripted()
            return self._step_result()
        if self._event:
            steps = self._event_horizon(chunk)

        # P228: the world moves while the policy computes. Placed **after** the
        # observation and **before** the first action, so the chunk is executed
        # late by exactly the latency - the measured harm - and `d == 0` (unset)
        # is the shipped path unchanged.
        self._inject_latency()
        if self._done:
            return self._step_result()

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
                    self._refresh_goal_aux()
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
                if self._ff_ticks > 0.0:
                    self._ff_arr = arr
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
                if (self._done or self._pick_boundary
                        or (self._replan_on_servo_end
                            and self._servo_handback)):
                    # P208: a servo hand-back discards the remaining chunk. The
                    # next `act` observes the state the servo left and plans from
                    # it, instead of playing a pre-servo pose.
                    self._servo_handback = False
                    self._force_observe = True
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
                # P173: the note must not claim "no grasp" on an episode that did
                # grasp and ran out of budget before the place - with the session's
                # `--horizon 900` (7.5 s) every completed grasp landed in exactly
                # that state, and the note read like an acquisition failure. The
                # shipped key is kept when nothing was grasped (that is the class
                # the record's ledgers count), so no rate or reason key moves on
                # the old behaviour.
                _tn = (
                    f"timeout: no grasp within {int(self.reward.horizon)} ticks"
                    if not (getattr(self, "_lifted", False)
                            or float(getattr(self, "_max_lift", 0.0)) > 0.05)
                    else f"timeout: horizon reached while carrying "
                    f"({int(self.reward.horizon)} ticks)"
                )
                self._finalize(notes=self._notes + [_tn])
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
        if self._contact_servo:
            if self._apply_contact_servo(arm, action):
                self._servo_contact_active = True
                # P207: a servo owns the hand for this tick; its target is not
                # the policy's emitted reference, so the rate limiter must re-seed
                # from the measured joints when the policy takes the hand back.
                self._rate_prev.pop(self._active, None)
                return
            if self._servo_contact_active:
                self._servo_contact_active = False
                if self._replan_on_servo_end:
                    self._servo_handback = True
                    self._say(
                        f"[replan] t={self._step} arm={self._active} source=contact"
                    )
        if (self._place_servo and self._close_t0 is not None
                and int(self._step) - int(self._close_t0) > int(self._servo_ticks)):
            if self._apply_place_servo(arm, action):
                self._servo_place_active = True
                self._rate_prev.pop(self._active, None)
                return
            if self._servo_place_active:
                self._servo_place_active = False
                if self._replan_on_servo_end:
                    self._servo_handback = True
                    self._say(
                        f"[replan] t={self._step} arm={self._active} source=place"
                    )
        if self._servo_handback:
            # P208: do not write the stale chunk's target; `act` breaks out and
            # re-plans from the next observation. The servo's own last target
            # stays on the drives for this tick.
            return
        if self._a2c2 is not None and not self._triggered and not self._action_jaw:
            # A2C2-style per-step correction on the frozen base policy, before
            # the primitive owns the arm. The head only shifts the 7 arm
            # channels; the finger command (and so the trigger) is unchanged.
            action = self._a2c2.correct(action, self.proprio(), self._goal, index)
        if (self._policy_track and self._sample is not None
                and not self._sample.attached and not self._action_jaw):
            action = self._tracking_action(action, arm)
        if self._emit_diag and not self._action_jaw:
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
            # the stop; this is the zero-time-cost cell that removes that. A
            # cartesian action (P145d) is not a joint vector and is not clamped.
            if not self._action_jaw:
                action = clamp_joint_targets(action, arm.arm_lo, arm.arm_hi)
                if self._emit_diag:
                    count, over = emit_out_of_range(action, arm.arm_lo, arm.arm_hi)
                    self._emit_post_out += count
        if self._action_jaw or getattr(self, "_jaw_now", False):
            # P145d: the task-space action (P170: also the hybrid's jaw phase). `ik_step` writes the arm's targets
            # itself; the orientation is the episode's captured hold.
            if getattr(self, "_hybrid_action", False) and not self._action_jaw:
                # P171: the hybrid's jaw phase - the finger at 7/8 (the shared
                # layout) and the jaw target at 9:12. The committed ramp still
                # owns the finger (below), so only the *arm's* action form changes.
                finger = float(np.clip(action[7], 0.0, 0.044))
                if self._close_ramp:
                    finger = self._close_ramp_command(arm, finger)
            else:
                finger = float(np.clip(action[3], 0.0, 0.044))
            hold = self._cart_hold.get(self._active)
            # P169: the **free wrist**. The scripted line's post-descent solver
            # is position-only (`hold_quaternion = None`), which is what lets it
            # reconfigure out of the j3-limit pose over several ticks; the jaw
            # action path otherwise holds the captured attitude, removing exactly
            # that freedom. `FRUIT_ACTION_FREE_WRIST=1` restores it.
            if os.environ.get("FRUIT_ACTION_FREE_WRIST", "0") == "1":
                arm.hold_quaternion = None
            elif hold is not None:
                arm.hold_quaternion = np.asarray(hold, dtype=float)
            if getattr(self, "_hybrid_action", False) and not self._action_jaw:
                target = np.asarray(action[9:12], dtype=float)
                target = arm.tcp_target_for_jaw(target)
            else:
                target = np.asarray(action[:3], dtype=float)
            if not self._action_tcp and not (
                getattr(self, "_hybrid_action", False) and not self._action_jaw
            ):
                # jaw-point action: the TCP target carries the tool offset.
                target = arm.tcp_target_for_jaw(target)
            arm.ik_step(target)
            self.scene.robot.set_dof_position_targets(
                [[finger, finger]], dof_indices=list(arm.finger_dofs)
            )
        else:
            target7 = action[:7]
            if self._ff_ticks > 0.0 and self._ff_arr is not None:
                # the chunk's own per-tick velocity, one hold-step ahead
                _j = min(int(index) + max(1, int(self._action_hold)), self._ff_arr.shape[0] - 1)
                _v = (np.asarray(self._ff_arr[_j][:7], dtype=float)
                      - np.asarray(action[:7], dtype=float)) / max(1, int(self._action_hold))
                target7 = np.asarray(action[:7], dtype=float) + self._ff_ticks * _v
            _seat = getattr(self, "_seat_q", None)
            if (
                _seat is not None
                and self._close_t0 is not None
                and int(self._step) - int(self._close_t0) <= int(self._close_ramp_ticks)
            ):
                target7 = _seat
            if self._posvel_action and action.shape[0] >= 16:
                _lead = float(os.environ.get("FRUIT_ACTION_DELTA_LEAD", "1.0"))
                if _lead:
                    target7 = np.asarray(target7, dtype=float) + _lead * np.asarray(
                        action[9:16], dtype=float
                    )
            if self._rel_action and self._rel_base is not None and self._rel_first is not None:
                target7 = self._rel_base + (np.asarray(action[:7], dtype=float) - self._rel_first)
            if self._dq_action:
                # one servo step per executed **waypoint**, not per tick: the
                # same waypoint is held for `_action_hold` ticks, so integrating
                # per tick would multiply the delta by the hold.
                _wp = index // max(1, int(getattr(self, "_action_hold", 1)))
                if self._dq_index != _wp:
                    try:
                        _meas = np.asarray(
                            self.scene.robot.get_dof_positions().numpy()
                        ).reshape(-1)[list(arm.arm_dofs)]
                        target7 = _meas + np.asarray(action[:7], dtype=float)
                    except Exception:  # noqa: BLE001 - a read failure keeps the last target
                        target7 = np.asarray(action[:7], dtype=float)
                    self._dq_index = _wp
                else:
                    target7 = np.asarray(getattr(self, "_dq_target", action[:7]), dtype=float)
                self._dq_target = target7
            _req7 = np.asarray(target7, dtype=np.float64)
            if self._target_rate > 0.0:
                # P207: ramp the reference at <= rate rad/s (120 Hz control).
                # `_rate_prev` is the last *emitted* target for this arm, so the
                # emitted command is continuous in time; a request already inside
                # the cap is emitted unchanged (no phase lag on the slow path).
                _prev = self._rate_prev.get(self._active)
                if _prev is None:
                    _prev = np.asarray(arm.joint_positions(), dtype=np.float64)
                target7 = rate_limit_target(
                    _prev, _req7, float(self._target_rate), 1.0 / 120.0
                )
                self._rate_prev[self._active] = np.asarray(
                    target7, dtype=np.float64
                ).copy()
            self.scene.robot.set_dof_position_targets(
                [np.asarray(target7, dtype=float).tolist()], dof_indices=list(arm.arm_dofs)
            )
            if self._policy_trace and self._step % 4 == 0:
                # P145d.7: does the *command* aim at the fruit, and can the arm
                # follow it? The 7 targets, the measured joints and the smallest
                # distance to the arm's own stops (a saturated joint explains a
                # partial descent that the jaw trace alone cannot).
                try:
                    _all = np.asarray(
                        self.scene.robot.get_dof_positions().numpy()
                    ).reshape(-1)
                    _idx = list(arm.arm_dofs)
                    _meas = _all[_idx]
                    _lo = np.asarray(arm.arm_lo, dtype=float)[: len(_idx)]
                    _hi = np.asarray(arm.arm_hi, dtype=float)[: len(_idx)]
                    _marg = float(
                        np.min(np.minimum(_meas - _lo, _hi - _meas))
                        if len(_idx) else 0.0
                    )
                    _worst = int(
                        np.argmin(np.minimum(_meas - _lo, _hi - _meas))
                        if len(_idx) else 0
                    )
                    _req = (
                        f" req={np.array2string(_req7, precision=3, suppress_small=True)} "
                        if self._target_rate > 0.0 else ""
                    )
                    self._say(
                        f"[cmd] t={self._step} "
                        f"tgt={np.array2string(np.asarray(target7, dtype=float), precision=3, suppress_small=True)} "
                        f"{_req}"
                        f"meas={np.array2string(_meas, precision=3, suppress_small=True)} "
                        f"marg={_marg:+.3f}@j{_worst + 1}"
                    )
                except Exception:  # noqa: BLE001
                    pass
            finger = float(np.clip(action[7], 0.0, 0.044))
            if (self._close_gap_lo > 0.0 and self._close_t0 is None
                    and finger <= 0.035):
                # P193b: the **acquisition window**. The census over the recipe's
                # own cells (`logs/p193`) shows every success firing the policy's
                # close with the jaw-fruit gap at **106-116 mm**, while the failures
                # fire at 1 / 8 / 53 / 60 / 69 mm (late - the fruit is already at
                # the pads) or never fire at all (213 mm). So the model's finger is
                # honoured only inside a gap window; outside it the hand stays open
                # and the committed ramp's own gated latch (the contact servo) does
                # the closing. One jaw read, and only on a tick the finger would
                # close: no per-tick cost.
                try:
                    _gap = float(np.linalg.norm(
                        np.asarray(self._goal[:3], dtype=float)
                        - np.asarray(arm.jaw_centre(), dtype=float)
                    ))
                except Exception:  # noqa: BLE001
                    _gap = float("nan")
                if not (self._close_gap_lo <= _gap <= self._close_gap_hi):
                    finger = float(arm.OPEN)
                    if self._close_gap_diag:
                        self._say(
                            f"[acq] t={self._step} arm={self._active} "
                            f"gap={_gap * 1000:.0f}mm outside "
                            f"[{self._close_gap_lo * 1000:.0f},{self._close_gap_hi * 1000:.0f}]"
                            " - the model's close is held open"
                        )
            if self._close_ramp:
                finger = self._close_ramp_command(arm, finger)
            if (self._fire_diag and not getattr(self, "_fire_logged", False)
                    and self._close_t0 is not None):
                # P194: the **decision tick** is the committed ramp's latch, not the
                # model's finger: that channel hovers at the action mean (0.0345,
                # P145d.11) and crosses 0.035 at random - measured, it fires at t=124
                # with the fruit 335 mm away. The no-latch case is logged at the
                # attempt's end, so every attempt has exactly one row.
                self._fire_logged = True
                self._fire_row(arm, finger, fired=True)
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
            if getattr(self, "_no_handover", False) and self._sample is not None:
                # P145: with the primitive off, `result.grasped` never exists, so the
                # outcome has to be read from the **fruit**: the highest it has been
                # carried above the belt rest. One max per tick, no new read.
                try:
                    _fz = float(self.spawner.position(self._sample)[2])
                    self._max_lift = max(self._max_lift, _fz - float(self._belt_rest))
                except Exception:  # noqa: BLE001 - reporting must not stop the loop
                    pass
            if self._policy_trace and self._step % 4 == 0:
                self._say(
                    f"[policy-trace] t={self._step} gap={distance * 1000:.0f}mm "
                    f"finger={float(finger):.4f} jaw_y={float(jaw[1]):+.3f} "
                    f"fruit_y={float(fruit[1]):+.3f} goal_y={float(self._goal[1]):+.3f} "
                    f"fruit_z={float(fruit[2]):.3f} jaw_z={float(jaw[2]):.3f} "
                    f"jaw_x={float(jaw[0]):+.3f} fruit_x={float(fruit[0]):+.3f} "
                    f"goal_x={float(self._goal[0]):+.3f}"
                )
            if self._handover_diag:
                # P143 diag: the closest the jaws came and the smallest finger the
                # policy asked for, tracked here because this block runs with the
                # trigger **off** as well (with `off`, `should_fire` is never
                # called at all - `trigger_settings.enabled` is False).
                self._diag_min_gap = min(self._diag_min_gap, float(distance))
                self._diag_min_finger = min(self._diag_min_finger, float(finger))
                # P143: the number the gate actually reads - **where the jaws
                # were on the ticks the policy was already closing**. `gap_min`
                # and `finger_min` are independent minima and cannot say whether
                # they coincided (measured: a candidate with gap 36 mm and
                # finger 0.0196 never fired because at 36 mm the finger was still
                # open). This one is the conjunction's own distance.
                if float(finger) < 0.030:
                    self._diag_gap_close = min(self._diag_gap_close, float(distance))
            if self._debug and (self._step % 25 == 0 or finger < 0.030):
                self._say(
                    f"[rl]   step={self._step} finger={finger:.4f} "
                    f"|jaw-fruit|xy={distance * 100:.1f}cm "
                    f"fruit=({fruit[0]:.3f},{fruit[1]:+.3f},{fruit[2]:.3f}) "
                    f"jaw=({jaw[0]:.3f},{jaw[1]:+.3f},{jaw[2]:.3f})"
                )
            # P143 R3: the learned close's distance gate. The shipped 0.06 m is the
            # same 2-D proximity test the hybrid evaluator uses, but the *primitive*
            # catches from up to 0.26 m (`arrival` fires at `t_arrive <= lead`), so
            # a model that closes at 0.10-0.15 m has a valid close that the gate
            # silently drops - measured: the baseline closes at 128-155 mm. The knob
            # is the interface's, not the model's: unset is the shipped 0.06.
            #: **P143 R4 (adopted): the gate is 0.15 m, not 0.06.** Measured on the
            #: untouched `moe_v13s` with no trigger and no teleport: at 0.06 the
            #: model's own close (128-155 mm, P143 section 8) never counts and the
            #: lane reads **0/7**; at 0.15 the same checkpoint reads **2/4 success**
            #: with the note `policy closed on the fruit (... |jaw-fruit|xy=15.0cm)`
            #: and one more `grasped=True` lost at the place. The primitive can catch
            #: from **0.26 m** (`arrival` fires at `t_arrive <= lead`) and its
            #: catch-up budget is 200 mm (P48), so 0.15 is inside the physics; the
            #: 0.06 was the *hybrid evaluator's* modelled-attach constant, not a
            #: constraint of this line. `FRUIT_POLICY_CLOSE_DIST=0.06` restores.
            close_dist = float(os.environ.get("FRUIT_POLICY_CLOSE_DIST", "0.15"))
            policy_close = bool(finger < 0.030 and distance < close_dist)
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
                    # P233: the belt the fruit actually rides (`surface_speed`) or
                    # the shipped setpoint echo (`encoder_speed`). Both are signed
                    # like `cfg.belt_speed`, which is what `transport_speed` takes.
                    _field = (
                        "surface_speed"
                        if self._trigger_surface_speed
                        else "encoder_speed"
                    )
                    encoder = getattr(self.spawner.belt, _field, None)
                reference = jaw
                if self.trigger_settings.frame == "station":
                    reference = np.array(
                        [self._trigger_station[0], self._trigger_station[1], jaw[2]],
                        dtype=float,
                    )
                _fire_pos, _fire_vel, _fire_src = self._fruit_for_trigger(
                    self._sample
                )
                if self._goal_perception and not self._fire_src_logged:
                    self._fire_src_logged = True
                    self._say(
                        f"[fire] source={_fire_src} "
                        f"(goal_source={self._goal_source}) - the trigger reads the "
                        f"{'tracker estimate' if _fire_src == 'percept' else 'simulator'}"
                    )
                intercept, intercept_info = should_fire(
                    self.trigger_settings,
                    _fire_pos,
                    reference,
                    encoder_speed=encoder,
                    measured_velocity=_fire_vel,
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
                        p_pos, p_vel, _ = self._fruit_for_trigger(presented)
                        p_fire, p_info = should_fire(
                            self.trigger_settings,
                            p_pos,
                            reference,
                            encoder_speed=encoder,
                            measured_velocity=p_vel,
                            finger=finger,
                            jaw_pos=jaw,
                            station=self._trigger_station,
                        )
                        self._note_x_refuse(presented.index, p_info)
                        if p_fire:
                            selected_dy = float(
                                (intercept_info or {}).get("dy", float("nan"))
                            )
                            adopt = True
                            if self._sort_armed:
                                # P121: the presented fruit's *destination* must
                                # be servable by the arm already tracking (the
                                # arm cannot change mid-attempt); its own
                                # destination - not the selected fruit's - is
                                # then the attempt's bin.
                                destination = self.task.sort_destination(presented)
                                adopt = False
                                if isinstance(destination, int):
                                    try:
                                        adopt = (
                                            self.task.arm_for_destination(
                                                int(destination)
                                            )
                                            == self._active
                                        )
                                    except Exception:  # noqa: BLE001 - refusal
                                        adopt = False
                                if adopt:
                                    self._bin_index = int(destination)
                            if adopt:
                                self._sample = presented
                                # Keep the observation coherent for any tick before
                                # the primitive takes over; the arm's lane is kept
                                # (`_bin_index`), like the task's station re-select.
                                self._goal = self._goal_vector(
                                    self.spawner.position(presented),
                                    self.spawner.velocity(presented),
                                    presented.diameter,
                                    self._bin_index,
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
            # P145: **no handover** (`FRUIT_POLICY_HANDOVER=0`). The primitive is
            # the scripted controller; handing the grasp to it means the policy
            # never has to close on the fruit, and no encoder/aim assist survives
            # the move to a real cell. With this off the policy's own 7 joints and
            # finger do the whole cycle and nothing else touches the arm.
            handover = os.environ.get("FRUIT_POLICY_HANDOVER", "1").strip() != "0"
            #: P227aa: **the "not mine" rule**. If the trigger fires with less
            #: lead than `FRUIT_SKIP_LATE` seconds, the fruit is already inside the
            #: window a descent can meet - on a line with several arms it is
            #: another arm's (or the end of the line's), so this attempt ends on
            #: this tick instead of chasing. That is the whole point: the chase is
            #: the only "weird" motion this cell produces (measured on 22 recorded
            #: episodes, failed attempts carry **1.18 rad** of joint range and
            #: **44** direction reversals p50 against **0.10** and **9** on
            #: placements, and the worst one oscillates 604 times while the fruit
            #: is already gone). Unset/0 keeps the shipped path byte for byte.
            if self._skip_late > 0.0 and intercept:
                _ta = (intercept_info or {}).get("t_arrive")
                if _ta is not None and float(_ta) < self._skip_late:
                    self._note_skip(float(_ta))
                    self._finalize(
                        notes=[
                            "skipped: no lead (the fruit is already inside the "
                            f"catch window, t_arrive={float(_ta):.2f}s < "
                            f"{self._skip_late:.2f}s) - not this arm's"
                        ]
                    )
                    return
            if handover and direct_fire(
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

    def _primitive_frame(self) -> None:
        """One observation inside the primitive, every 4 ticks (P227ad, opt-in).

        Installed as `task.frame_callback` for the contact phase only, so the
        tracker keeps receiving measurements at 30 Hz - which is what a real cell's
        camera does. Costs one render per 4 ticks; the shipped path installs
        nothing and is unchanged.
        """
        now = float(self._sim_time())
        if now - float(self._prim_t) < 4.0 / 120.0:
            return
        self._prim_t = now
        self._observe(force=True)

    def _estimate_now(self):
        """`(position, velocity)` from the tracker **at this tick**, or None.

        P227ad: the primitive's catch-up reads the fruit every tick, so a frozen
        estimate (published once per *observation*, i.e. every 4 ticks) would have
        it chase a stale point for the whole contact phase. This extrapolates with
        the tracker's own velocity - the same `predict_at` the goal uses - capped by
        the coast budget, so a per-tick read costs one array op and no camera.
        """
        tr = getattr(self, "_percept_tracker", None)
        if tr is None or self._percept_pos is None:
            return None
        horizon = float(self._sim_time()) - float(tr.t)
        horizon = min(max(horizon, 0.0), float(self._percept_coast_s))
        return (
            np.asarray(tr.predict_at(horizon), dtype=float),
            np.asarray(tr.velocity, dtype=float),
        )

    def _fruit_for_trigger(self, sample):
        """`(position, velocity, source)` for the fire decision.

        P227ad: **the trigger must not read the simulator when the goal is
        measured.** With `FRUIT_GOAL_SOURCE=perception` the tracker already
        publishes an estimate *at the current tick* (`predict_at(horizon)` with
        the coast cap), so the fire decision uses the same numbers the policy
        sees. Unset, this returns the simulator's state exactly as before - the
        shipped path is unchanged, and the `source` tag is what lets a log name
        which one it used.
        """
        if (
            getattr(self, "_goal_perception", False)
            and self._percept_pos is not None
            and self._percept_vel is not None
        ):
            return (
                np.asarray(self._percept_pos, dtype=float),
                np.asarray(self._percept_vel, dtype=float),
                "percept",
            )
        return (
            np.asarray(self.spawner.position(sample), dtype=float),
            np.asarray(self.spawner.velocity(sample), dtype=float),
            "truth",
        )

    def _note_skip(self, t_arrive: float) -> None:
        """P227aa: one row per skipped attempt (reporting only, zero reads)."""
        self._skipped_attempts = int(getattr(self, "_skipped_attempts", 0)) + 1
        self._say(
            f"[skip] attempt {self._episode}: t_arrive={t_arrive:.2f}s below "
            f"FRUIT_SKIP_LATE={self._skip_late:.2f}s - the fruit is another "
            f"arm's; ending this attempt (skips so far "
            f"{self._skipped_attempts})"
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
            # P121: with an instruction the selection is by destination, and the
            # *arm* is the capability map's answer - the bin is not a lane.
            lane=None if self._sort_armed else int(self._bin_index),
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
        if self._sort_armed:
            # The same-arm check replaces the grade-lane check: an adoption must
            # keep `_active` and may move `_bin_index` to the candidate's
            # destination (a third destination on the same side included).
            destination = self.task.sort_destination(state)
            if not isinstance(destination, int):
                self._reseed_off += 1
                self._reseed_note_exhausted()
                return
            try:
                candidate_arm = self.task.arm_for_destination(int(destination))
            except Exception:  # noqa: BLE001 - an unservable destination is a refusal
                candidate_arm = None
            if candidate_arm != self._active:
                self._reseed_off += 1
                self._reseed_note_exhausted()
                return
            self._bin_index = int(destination)
        else:
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
        self._goal = self._goal_vector(
            position, velocity, sample.diameter, self._bin_index
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
                carry_and_release(
                    arm, self.cfg, self._bin_index, self.advance,
                    place_xy=(
                        self.task.destination_target(self._bin_index)
                        if self._sort_armed
                        else None
                    ),
                )
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
        # P151: **expert-in-control contact phase** (HG-DAgger). The labels-only
        # store cannot contain the corrected states (P145d.9/P149): the deployed
        # policy reaches the close 3.5 cm high and then holds in the world frame
        # instead of tracking the belt. With this on the expert *executes* from
        # the tracking window (fruit dy <= 0.10 m) through the close ramp and the
        # 60-tick tracking hold, so the store gains those states and their
        # commands; the policy drives the approach and (later) the lift/place.
        if self._dagger_contact and self._sample is not None:
            try:
                _fruit = np.asarray(self.spawner.position(self._sample), dtype=float)
                _dy = float(_fruit[1]) - float(self._expert_jaw_y)
                _in = _dy <= float(os.environ.get("FRUIT_DAGGER_CONTACT_DY", "0.05"))
                if self._expert_close_start is not None and int(self._step) - int(
                    self._expert_close_start
                ) > int(os.environ.get("FRUIT_DAGGER_CONTACT_AFTER", "60")):
                    _in = False
                if _in:
                    _label = self._expert_action()
                    self._expert_label = _label
                    self._ep_expert_ticks += 1
                    return _label
            except Exception:  # noqa: BLE001 - fall through to the shipped path
                pass
        if self._step % 4 == 0 or self._step < self._expert_until:
            label = self._expert_action()
            self._expert_label = label
            if self._dagger_diag and policy_action is not None:
                try:
                    _p = np.asarray(policy_action, dtype=np.float64).reshape(-1)
                    _l = np.asarray(label, dtype=np.float64).reshape(-1)
                    _err = float(np.linalg.norm(_p[:7] - _l[:7]))
                    _df = float(_p[7] - _l[7])
                    _jaw = np.asarray(
                        self.task.arms[self._active].jaw_centre(), dtype=float
                    )
                    self._say(
                        f"[dagger] t={self._step} e={_err:.3f} df={_df:+.4f} "
                        f"fing={float(_l[7]):.4f} "
                        f"dy={float(self._goal[1]) - float(_jaw[1]):+.3f} "
                        f"gap={float(np.linalg.norm(self._goal[:2] - _jaw[:2])) * 1e3:.0f}"
                    )
                except Exception:  # noqa: BLE001 - diag only
                    pass
        if self._step < self._expert_until:
            self._ep_expert_ticks += 1
            return label
        if policy_action is None or label is None:
            return policy_action
        if os.environ.get("FRUIT_DAGGER_NO_TAKEOVER", "0") == "1":
            # P145: labels only. The early-close term would otherwise hand the
            # arm to the expert for one tick at exactly the close, which is the
            # state the store is for; with this on every state is the policy's.
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

        # P145d.9: **pre-align the lateral aim**. The scripted wait holds the
        # calibrated grasp pose (a fixed x) until the fruit reaches the tracking
        # window, so the lateral 10 cm leg is compressed into the last ~0.5 s and
        # the cloned policy reproduces ~35 % of it (measured, `[close] dx`
        # -10..-95 mm). The expert's *label* is ours to choose: the scripted
        # primitive's own descent already aims at the fruit's x, so a wait that
        # tracks that x early is the same controller with a lead. The pads stay
        # open; only x is pre-aligned, at the pose's own height.
        _prealign = os.environ.get("FRUIT_EXPERT_PREALIGN", "0") == "1"
        _lead = float(os.environ.get("FRUIT_EXPERT_PREALIGN_LEAD", "0.25"))
        if self._expert_close_start is None:
            # Wait loop of the scripted line: hold the calibrated grasp pose
            # with the pads open (the recorded wait-phase action).
            label[:7] = self._expert_grasp
            finger = float(arm.OPEN)
            if _prealign and _lead > 0.0 and dy < _lead:
                # a lateral-only servo at the pose's height; the y/z descent
                # stays the scripted window's job
                try:
                    _jaw = np.asarray(arm.jaw_centre(), dtype=float)
                    arm.hold_quaternion = None
                    arm.sync_command_to_measured()
                    arm.ik_step(
                        np.array([float(fruit[0]), float(_jaw[1]), float(_jaw[2])])
                    )
                    if arm._q_cmd is not None:
                        label[:7] = np.asarray(arm._q_cmd, dtype=np.float32)[:7]
                except Exception:  # noqa: BLE001 - the pose stays the fallback
                    pass
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
            # P152 (oracle review): the scripted close **carries** `_q_cmd`
            # across ticks (a per-tick `sync_command_to_measured` makes the
            # label a proportional pursuit that lags the belt by ~2 mm/frame),
            # and it aims at the fruit plus a **velocity lead** (0.18 s, 21.6 mm
            # at 0.12 m/s), not at the fruit's current centre. Both are what the
            # demos' tracking hold is made of; `FRUIT_EXPERT_CARRY=0` restores
            # the pre-P152 label.
            arm.hold_quaternion = None
            _carry = os.environ.get("FRUIT_EXPERT_CARRY", "1") == "1"
            if not _carry:
                arm.sync_command_to_measured()
            pad_lift = float(os.environ.get("FRUIT_PAD_LIFT", "0.010"))
            _lead = float(os.environ.get("FRUIT_EXPERT_LEAD_S", "0.18"))
            try:
                _v = np.asarray(self.spawner.velocity(sample), dtype=float)
            except Exception:  # noqa: BLE001
                _v = np.zeros(3)
            _aim = fruit + np.array([0.0, float(_v[1]) * _lead if _lead > 0 else 0.0, pad_lift])
            arm.ik_step(arm.tcp_target_for_jaw(_aim))
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
            "goal": self._goal_snapshot(),
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
        if self.dagger is not None:
            # P145: **which frames are a usable label**. The pick expert's command
            # is only the controller's behaviour up to the close: after the ramp
            # it holds the (already grasped) fruit where it is, which is not the
            # carry the demos teach. Mark those frames so the window loader drops
            # them instead of training the policy to freeze mid-carry.
            valid = 1.0
            if self._expert_close_start is not None:
                if self._step - self._expert_close_start >= 60:
                    valid = 0.0
            observation["dagger_valid"] = np.array([valid], dtype=np.float32)
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
        # P175: **score the place at the release**, not at finalize. A payload put
        # on an output belt is carried away and despawned before the episode ends,
        # so `on_output_belt(final)` reads False on a good place - measured as
        # `final=(+63.0, 0.0, -50.0)`, the spawner's own park slot. The finger's
        # closed -> open transition is the release; one sticky flag, sampled from
        # the position this function already reads (no extra read).
        # P203: the **physical release event** - one detector, two consumers (the
        # score and the episode boundary). The finger *command* is not one: it
        # hovers at the action mean (0.0345, P145d.11) and crosses 0.035 at random
        # (measured: a "release" at t = 292 / 0.6 s on three episodes, and a
        # `placed=True, grasped=False` false positive). The two physical tests:
        #   * the place servo's own commit - `_place_open >= 1` means its 40-tick
        #     open ramp finished at the destination it drove to; or
        #   * the payload **left the hand**: it had been lifted (`_max_lift`) and
        #     is now further from the jaw than any seat (0.25 m) with the fingers
        #     open - the model's own place path.
        if not getattr(self, "_scored_release", False):
            _lifted = float(getattr(self, "_max_lift", 0.0)) > 0.05
            _opened = float(getattr(self, "_place_open", 0.0)) >= 1.0
            if _lifted and not _opened:
                try:
                    _far = float(np.linalg.norm(
                        pos - np.asarray(self.task.arms[self._active].jaw_centre(),
                                         dtype=float))) > 0.25
                except Exception:  # noqa: BLE001
                    _far = False
                _opened = bool(_far and float(getattr(self, "_last_finger", 0.0)) > 0.035)
            if _lifted and _opened:
                self._scored_release = True
                if bool(self.cfg.on_output_belt(pos)):
                    self._placed = True
        if (self._episode_end_release or getattr(self, "_endpoint_release", False)) \
                and getattr(self, "_scored_release", False):
            # P202: **end the episode at the release** when the task is scored
            # there. The measured defect this removes: after a completed place the
            # episode ran to the horizon - 1192 ticks (9.9 s) in the P201 video -
            # deciding with a stale goal and an empty hand, and its emitted joint
            # jitter is **3.4x the median and 3.7x the p95** of the in-task value
            # (|dtgt|/4 ticks: pre p50 0.0180 / p95 0.0595 rad against post 0.0620
            # / 0.2200). That is the "it stops and twitches" a viewer sees. The
            # shipped behaviour is the horizon (`FRUIT_EPISODE_END` unset).
            self._finalize(notes=self._notes + ["release: task complete"])
            return True
        if z < self.belt_top - 0.25:
            if getattr(sample, "parked", False) and os.environ.get(
                "FRUIT_FALL_PARKED", "0"
            ) == "1":
                # P139: a **recycled** fruit is not a fallen one. `park` puts it
                # at `(60 + 3*i, 0, -50)` (`fruits.FruitSpawner.park`), so the
                # shipped test below reads that as "fell off the line" - the
                # direct loop's dominant failure key is, measured, mostly this
                # (three episodes, three parked poses). With the knob armed the
                # episode is left to its own horizon instead of ending on a note
                # that names the wrong event. Default off: this changes the
                # failure-reason ledger, so it is its own cell.
                return False
            if os.environ.get("FRUIT_FALL_DIAG", "0") == "1":
                # P139, reporting only (default off): the class is a *fruit* below
                # `belt_top - 0.25`, so this names where it left - the one thing
                # the note itself cannot say. One row per episode, at the event.
                from .common import say as _say

                _say(
                    f"[fall] idx={int(sample.index)} pos="
                    f"({float(pos[0]):+.3f},{float(pos[1]):+.3f},{float(pos[2]):+.3f}) "
                    f"belt_top={self.belt_top:.3f} held={bool(getattr(sample, 'held', False))} "
                    f"attached={bool(getattr(sample, 'attached', False))} "
                    f"t={self._sim_time():.2f}"
                )
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
        # P121: the place leg's thread-local target (`tasks._place_xy_for`) and
        # the attempt's ledger fields. The direct entry never runs `run()`/
        # `_run_impl`, so the dispatch the scripted line sets there is set here;
        # un-instructed there is no call at all.
        if self._sort_armed:
            self.task.dispatch_destination(result, self._bin_index)
        _est = self._estimate_now if self._primitive_estimate else None
        self.task.fruit_estimate = _est
        if self._primitive_estimate:
            #: P227ad: the row prints only when the lever is armed, so the shipped
            #: direct path keeps its log line for line.
            self._say(
                f"[prim] source={'percept' if _est is not None else 'truth'} "
                f"(pre-grasp reads; post-grasp follows the hand)"
            )
        _prev_hook = getattr(self.task, "primitive_tick_hook", None)
        if self._primitive_percept:
            self._prim_t = -1.0e9
            #: `_step_sim` is the primitive's own tick path (the `_tick_frame` sites
            #: are only 15 named legs, which is why a `frame_callback` hook never
            #: fired here: measured, the frame count stayed at 20-54 per attempt).
            self.task.primitive_tick_hook = self._primitive_frame
        try:
            result = self.task.grasp_carry_place(
                self._active, self._sample, self._bin_index, result, verbose=self.verbose
            )
        finally:
            if self._primitive_percept:
                self.task.primitive_tick_hook = _prev_hook
            self.task.fruit_estimate = None
            if self._sort_armed:
                self.task.clear_dispatch()
        if self._sort_armed and getattr(result, "destination", None) is not None:
            # The task's own station reselect (`FRUIT_STATION_RESELECT`, armed by
            # default; it runs on the shipped non-dynamic direct config) may have
            # re-dispatched the attempt to the presented fruit's destination
            # mid-call. Adopt it so the outcome record and the failed-grasp
            # fallback below use the destination the place leg actually ran.
            self._bin_index = int(result.destination)
        self._grasped = bool(result.grasped)
        self._placed = bool(result.placed)
        self._lifted = bool(result.grasped)
        notes = list(self._notes) + list(result.notes)
        if self._sort_armed:
            # P114's ledger, one row per attempt (`in_dest` measured from the
            # payload's release position exactly as the scripted path does);
            # the same two calls `tasks.run()` makes after its `finally`.
            self.task.sort_ledger_attempt(result)
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
                self.task.arms[self._active], self.cfg, self._bin_index, self.advance,
                # P121: the destination target, not a lane index into the
                # shipped two-lane drop points (a third destination has none).
                place_xy=(
                    self.task.destination_target(self._bin_index)
                    if self._sort_armed
                    else None
                ),
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
        # P142: **which event is scored**. `final` (the shipped default) reads the
        # payload's position at finalize time, i.e. "the fruit is still on an
        # output line when the episode ends". With `FRUIT_OUTPUT_RAILS=none`
        # (P71) a released payload can roll off the slab in the ~0.3 s between the
        # release and the finalize, so a successful place (`placed=True`, the
        # task's own release onto the line) can still score False - measured in
        # `logs/p139/guard2.log` episode 1 and in P120's seed-101 landing miss.
        # `release` scores the release instead: `success = lifted and placed`,
        # which is the definition the scripted line's ledgers use. It is opt-in,
        # declared, and the row names it - the two are different metrics and a
        # rate is only comparable within one of them.
        endpoint = score_endpoint()
        if (self._fire_diag and not getattr(self, "_fire_logged", False)
                and getattr(self, "_close_t0", None) is None):
            # No close was ever asked for: log where the fruit was at the end.
            try:
                self._fire_row(self.task.arms[self._active], float("nan"), fired=False)
            except Exception:  # noqa: BLE001
                pass
        # P176: put the drive back before anything reads the outcome
        self._restore_direct_finger_cap()
        if getattr(self, "_no_handover", False):
            # The policy carried the fruit if it rose off the belt with the hand;
            # `grasped`/`placed` are reported from that and from the payload's own
            # position at finalize, because the primitive - the only other source
            # of those two flags - never runs here.
            self._lifted = bool(self._lifted) or self._max_lift > 0.05
            self._grasped = bool(self._grasped) or self._lifted
            self._placed = bool(self._placed) or bool(self.cfg.on_output_belt(final))
        if endpoint == "release":
            success = bool(self._lifted) and bool(self._placed)
        else:
            success = bool(self._lifted) and bool(self.cfg.on_output_belt(final))
        reward = self.reward.compute(success, decision)
        notes = list(self._notes if notes is None else notes)
        self._outcome = {
            "episode": self._episode,
            "score_endpoint": endpoint,
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
        if self._sort_armed:
            #: P121: the instruction's destination for this attempt (absent on
            #: the un-instructed direct path, so its outcome dict is unchanged).
            self._outcome["destination"] = int(self._bin_index)
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
            # P142: only printed when it is not the shipped metric, so the
            # default row stays byte-identical (the acceptance's 459 lines).
            + ("" if endpoint == "final" else f" endpoint={endpoint}")
            + (
                ""
                if not self._handover_diag
                else (
                    f" gap_min={self._diag_min_gap * 1000:.0f}mm"
                    f" finger_min={self._diag_min_finger:.4f}"
                    f" gap_close={self._diag_gap_close * 1000:.0f}mm"
                    # P173b: where the payload ended, so "grasped but not placed"
                    # is a *position* read (still at the pick station vs at a bin)
                    # instead of an inference. Reporting only.
                    f" final=({final[0]:+.2f},{final[1]:+.2f},{final[2]:+.2f})"
                    f" on_out={int(bool(self.cfg.on_output_belt(final)))}"
                    f" fing={float(getattr(self, '_last_finger', 0.0)):.4f}"
                )
            )
        )
        percept = self._percept_report()
        if percept:
            self._say(percept)
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
        # P121: the instruction's per-destination ledger is a run-level report
        # on the scripted path (`tasks.run_bimanual` / the single-arm driver
        # print it at the end); the direct entry calls this summary last, so it
        # prints there. No-op without an instruction.
        if getattr(self, "_sort_armed", False):
            self.task.sort_ledger_report()
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
