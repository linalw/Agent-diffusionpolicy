#!/usr/bin/env bash
# Pre-flight self-check: the checks that need no simulator, in one command.
#
#   scripts/selfcheck.sh                                  # the four checks below
#   scripts/selfcheck.sh logs/accept_run1.log             # also judge a pick-and-place run
#   SELFCHECK_DATASET_ROOT=/tmp/broken scripts/selfcheck.sh   # point the audit somewhere else
#
# Runs, in order, and aggregates:
#   1. offline motion checks          scripts/96_motion_check.py
#   2. dataset index audit            scripts/106_index_audit.py
#   3. collect/merge regression       scripts/107_collect_merge_test.py
#   4. finger collider guard          scripts/432_finger_collider_guard_test.py
#   5. rl env smoke                   import + reward math of src/fruit_sorting/rl_env.py
#   6. tasks.py pin                   rl_env.TASKS_MD5 == md5(src/fruit_sorting/tasks.py)
#   7. rl report parser               scripts/113_rl_report.py --self-test
#   8. r9 endpoint report             scripts/196_r9_report.py --self-test
#   9. r9 rollout merge               scripts/197_r9_merge_rollouts.py --self-test
#  10. rtc runtime selftest           scripts/128_rtc_selftest.py (no checkpoint)
#  11. trigger intercept test         scripts/811_trigger_test.py (pure geometry)
#  12. claim slot harness             scripts/181_claim_slot_selftest.sh (pure locking)
#  13. ops selfcheck selftest         scripts/191_ops_selfcheck.sh --selftest (fake
#                                     sim/claim/wrapper in a temp dir; the P1 ops probe)
#  14. bed supply audit               scripts/211_bed_audit.py --fast (the dense bed's
#                                     rows/corridor/pool; stubbed pxr, no simulator)
#  15. motion budgets                 scripts/105_motion_regression.py  (needs a run log)
#
# Each prints "name, result, elapsed"; everything is also written to
# `logs/selfcheck.log`. Any *failure* makes the script exit non-zero; the motion
# budgets check is *skipped* (not failed) when no run log is given, because the run
# it judges takes ten pick-and-place attempts and is a separate command
# (`scripts/accept.sh`).
set -uo pipefail

cd "$(dirname "$0")/.."

python=${PYTHON:-python3}
log=${SELFCHECK_LOG:-logs/selfcheck.log}
dataset_root=${SELFCHECK_DATASET_ROOT:-datasets}
run_log=${1:-}

mkdir -p "$(dirname "$log")"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
: > "$log"

failed=0
skipped=0
total_start=$(date +%s.%N)

run_check() {
    local name=$1
    shift
    local start end elapsed status output
    output="$work/out"
    start=$(date +%s.%N)
    if "$@" > "$output" 2>&1; then
        status=PASS
    else
        status=FAIL
        failed=$((failed + 1))
    fi
    end=$(date +%s.%N)
    elapsed=$(awk -v a="$start" -v b="$end" 'BEGIN { printf "%.2f", b - a }')
    printf '%-26s %-4s %6.2fs\n' "$name" "$status" "$elapsed"
    {
        echo "### $name: $status (${elapsed}s)"
        echo "\$ $*"
        sed 's/^/    /' "$output"
        echo
    } >> "$log"
}

echo "selfcheck: $(date -Iseconds)"
echo

run_check "offline motion checks" "$python" scripts/96_motion_check.py
run_check "dataset index audit" "$python" scripts/106_index_audit.py --root "$dataset_root"
run_check "collect/merge regression" "$python" scripts/107_collect_merge_test.py
# The openarm hand is only real if its finger colliders were authored; the P1
# gate made a collider-less build a hard error and this pins that offline.
run_check "finger collider guard" "$python" scripts/432_finger_collider_guard_test.py
# P4 additions: the RL environment must import and score offline, and the A/B
# report's parser/sign test must be exercised without a simulator. Neither check
# touches Isaac Sim.
run_check "rl env smoke" "$python" -c "import sys; sys.path.insert(0, 'src'); from fruit_sorting.rl_env import RewardConfig, RolloutRecorder, TASKS_MD5; r = RewardConfig(); assert abs(r.compute(True, 0) - 1.0) < 1e-9; assert abs(r.compute(True, 750) - 0.9) < 1e-9; assert abs(r.compute(True, 1500) - 0.8) < 1e-9; assert abs(r.compute(True, 99999) - 0.8) < 1e-9; assert r.compute(False, 100) == 0.0; assert len(TASKS_MD5) == 32; print('rl_env smoke ok')"
# P32 phase-D remediation (Gate D): the stale pin has recurred (R11-A's
# `b7d6f849` vs its `c2c7a626`, the R11-B repair, P32 phase D's `ea271ccc` vs
# `9277fa64`). The direct RL env refuses to start unless `TASKS_MD5` equals the
# shipped `tasks.py`; this asserts the equality on every selfcheck so a
# metadata-only follow cannot be forgotten again.
run_check "tasks.py pin" "$python" -c "import hashlib, sys; sys.path.insert(0, 'src'); from fruit_sorting.rl_env import TASKS_MD5; actual = hashlib.md5(open('src/fruit_sorting/tasks.py', 'rb').read()).hexdigest(); assert TASKS_MD5 == actual, f'TASKS_MD5={TASKS_MD5} tasks.py={actual}'; print('TASKS_MD5 pin ok')"
# P36 phase 1: the proprio spoof (default off). The vectors against the P35
# measured settled poses (`logs/p35/C_ab/` `[park] q_settled=`), the 7 indices
# against the robot's measured dof order (`logs/33_dof.log`), and the
# observation diff (only the inactive arm's 7 channels move, the rest is
# bit-identical) - all pure arrays, no simulator.
run_check "proprio spoof check" "$python" scripts/218_proprio_spoof_check.py
run_check "rl report parser" "$python" scripts/113_rl_report.py --self-test
# R9: the RL/DAgger lane's two offline tools - the N=5 endpoint readout (parse,
# same-fruit pairing, carried-class sign test, verdicts, the optional carry
# mechanism section) and the rollout-shard merge (renumbering, provenance,
# overwrite refusal, merged-npz readability).
run_check "r9 endpoint report" "$python" scripts/196_r9_report.py --self-test
run_check "r9 rollout merge" "$python" scripts/197_r9_merge_rollouts.py --self-test
# The RTC runtime is pinned offline: prefix weights, interleave split, the
# bit-exact base sampler, the frozen prefix and the queue bookkeeping.
run_check "rtc runtime selftest" "$python" scripts/128_rtc_selftest.py
# The encoder intercept trigger (P4b1/P4b2) is pure geometry over the fruit/jaw
# vectors and the belt encoder: pin its gates and the env parsing offline.
run_check "trigger intercept test" "$python" scripts/811_trigger_test.py
# The consistency distillation (v5-C): implied x0, the DDIM-1 == implied-x0
# identity the deployable 1-step sampler relies on, the EMA/CD objective and the
# endpoint probe.
run_check "distill selftest" "$python" scripts/131_distill_selftest.py
# The v5-B loop metric (step/jerk/boundary/decision rate) is pure arithmetic:
# pin it offline, before it is used to judge the fast-loop A/B.
run_check "loop metrics selftest" "$python" scripts/125_loop_metrics.py --self-test
# Path 3: the event-triggered replanning rule, the A2C2 correction head round
# trip and the path-3 report criteria evaluator are all pure offline code.
run_check "path3 event selftest" "$python" scripts/149_path3_selftest.py
run_check "a2c2 correction selftest" "$python" scripts/146_train_correction.py --self-test
run_check "path3 report selftest" "$python" scripts/148_path3_report.py --self-test
# F2: the bimanual token/station invariants (exclusive stepping, alternation,
# determinism, park/resume, steps on the main thread) are pure threading logic.
run_check "bimanual scheduler test" "$python" scripts/152_biarm_selftest.py
# v9/V1: the scattered-supply mix allocation, the resolved FRUIT_SUPPLY_*
# defaults, the prime window and the backlog pump's separation rule (stubbed
# pxr; no simulator).
run_check "supply scatter selftest" "$python" scripts/172_supply_selftest.py
# P28-B: the belt-speed channel (the B0 identity on real windows, the per-episode
# pin chain with the raise-on-missing/conflict, the 25-D byte-inertness) - pure
# logic over synthetic stores; no simulator.
run_check "speed channel test" "$python" logs/p28i/check_speed_channel.py
# v9/V2: the two-line selector (per-arm station floor, grade preference with
# the any-grade fallback, protected-fruit exclusion) and the pre-pose-lock
# decision - pure logic over a stubbed task, no simulator.
run_check "two-line selector test" "$python" scripts/176_twoline_selftest.py
# R10-A: the reach-anywhere moving catch's selector (the band-relative floor,
# the earliest-reachable-intercept choice, the station fallback) and the
# interception-point arithmetic (the bounded fixed point, the band clip, the
# per-arm bands, the aim cache) - pure logic over a stubbed task.
run_check "reach-anywhere selftest" "$python" scripts/198_r10_selftest.py
# X1: the slot claim (mutual exclusion, pool overlap, stale recovery after
# SIGKILL, wait timeout, duplicate-namespace refusal) is pure locking logic.
run_check "claim slot harness" bash scripts/181_claim_slot_selftest.sh
# P1: the ops self-check's synthetic-stall test (a fake sim, a stale claim and
# a fake claim wrapper in a temp dir; asserts OK does not fire and
# STALLED-SIM/STALLED-CHAIN/ACTION do, incl. the own-process-group guard and
# the wrap suppression while a wrapper is alive).
run_check "ops selfcheck selftest" bash scripts/191_ops_selfcheck.sh --selftest
# P32: the dense 2D bed supply (default off). The fast battery pins the row
# lattice, the pair corridor, the 40-fruit pool's **zero live-recycle** fraction
# and a completed belt transit at the shipped queue depth and at 18 - the two
# Gate-1 blocker assertions - plus the legacy bedrock hashes. The full run (the
# record, `logs/p32/bed_audit.txt`) carries all six queue/cadence cells.
run_check "bed supply audit" "$python" scripts/211_bed_audit.py --fast
# P32 phase 2: the prepared-next pipeline's ranking/refresh/consume (the real
# selector on a stubbed task), the default-off pins, the feeder stride
# arithmetic and `fruits.update`'s furniture split (default still steps the
# belt). No simulator; `--cost` is the manual wall-time probe and is not run
# here.
run_check "prepared-next selftest" "$python" scripts/213_prepared_next_selftest.py
# P43 L1: the nearest-above-floor **scope** (the `direct` keyword). The real
# selector on a stubbed task: the scripted line takes the nearest floored
# candidate, the direct/policy env's episode selection keeps the shipped
# farthest-upstream pick, an explicit `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` wins on
# both paths, and the lane/prefer_lane callers (two-line + shared-station) are
# byte-identical under all three settings. Plus the AST call-site census and the
# `TASKS_MD5` provenance pin. P43 phase 4 adds the arm park's **default and
# scope** (direct -> `back`, handoff -> no park, `=ready` the escape hatch, the
# manifest's `defaulted` field, the two printed label sites). No simulator.
run_check "P43 selector + park" "$python" scripts/224_p43_selftest.py
# P44 phase 2: the speed cells (`FRUIT_SPEED_PLACE/_RELEASE/_LIFT`, S13 =
# `FRUIT_SPEED_ALL`). The real resolver on the stubbed import: unset = the
# shipped default *strings* (byte-identical by construction), one knob per cell,
# an explicit per-leg override winning, the union, and the seven read sites by
# AST. No simulator.
run_check "P44 speed cells" "$python" scripts/225_p44_speed_selftest.py
# P45 phase 2: the mass-scale experiment knob (`FRUIT_MASS_SCALE`, a documented
# *physics change* at unchanged size). The real resolver on the stubbed import:
# unset = 1.0 and **no banner** (so the shipped stream is byte-identical), the
# resolution table, `0`/negative/`inf`/`nan`/a non-number as hard errors, both
# mass sites (create + the recycled-fruit `rescale`) multiplied behind the
# `!= 1.0` guard and nothing else, the size paths untouched, and the "inertia is
# derived, not authored" property plus the one-shot read-back. No simulator.
run_check "P45 mass scale" "$python" scripts/227_p45_mass_selftest.py
# P52 phase 2: the contact-gated action time-scale (`FRUIT_POLICY_TIME_SCALE`,
# `FRUIT_POLICY_RETIME_GATE`, both default off). The real resolver and the real
# interpolation run offline: `s = 1.0` returns `chunk[index]` **exactly**
# (array-equal over random chunks, signed zeros included - the direct loop is
# not bit-reproducible, so the algebra is the only proof of byte-identity), the
# executed path advances `s` waypoints per tick, the last waypoint is a hold and
# never an extrapolation, the finger channels ride the same index, the gate is
# the strict-union truth table of the two already-sampled channels, and the
# resolver refuses a slow-down / a zero / a non-finite / a non-number. The
# env-side wiring is pinned by AST (the shipped `action = arr[index]` survives
# as the knob-off branch, `_apply` is retime-free, the gate adds no sensor read).
run_check "P52 retime scale" "$python" scripts/228_p52_retime_selftest.py
# P53: the policy's own emission cells (`FRUIT_POLICY_JOINT_CLAMP`, C1, and
# `FRUIT_POLICY_ACTION_HOLD`, C2 - both default off). The real resolvers and the
# real clip/hold helpers run offline: the clamp is a **copy** that is
# element-identical inside the range (so a knob-off run is the shipped
# expression and a chunk row is never rewritten in place), the hold is
# `np.repeat` (tick i executes waypoint i//hold, the shipped `arr[index]`
# lookup survives), the census counter is the P2B measurement (13.1 % of
# joint-steps / 74.3 % of ticks), and both resolvers refuse a typo rather than
# reading it as "off". The env wiring is pinned by AST (the clip is the last
# shaping before the drives; the hold scales `steps` behind its knob).
run_check "P53 emission cells" "$python" scripts/229_p53_emit_selftest.py
run_check "P58 supply profile" "$python" scripts/230_p58_supply_selftest.py
run_check "P61 slip direction" "$python" scripts/231_p61_slip_selftest.py
run_check "P63 attitude drift" "$python" scripts/233_p63_attitude_selftest.py
# P65: where the drift lives - the `[carry]` row's joint-limit margin
# (`q_margin=`, measured, min over the leg + its 1-based binding joint), the same
# for the controller's post-clip command (`q_cmd_margin=`, free attribute), the
# command's largest per-tick step (`q_step_max=`, the `FRUIT_IK_MAX_STEP`
# operand), the jaw-opening axis' world z (`jaw_z=`, first tick / max abs) and the
# first tick the hold drift passes 10 deg (`drift_on=`). The leg pins the field
# set and order, the `guard_armed` (FRUIT_CARRY_DIAG, default off) containment
# that makes `None` byte-inert, the margin/argmin/min-over-leg arithmetic, the
# `rot[:,1]` jaw axis and the first-crossing onset.
run_check "P65 lift drift" "$python" scripts/235_p65_lift_selftest.py
# P66 phase 2: the lift's **end** reads on the same `[carry]` row (`drift_end=`,
# the last guarded tick's hold drift rather than the max; `res_end=`/`dz_end=`,
# the achieved TCP position error at the leg's end against the target the same
# tick issued - the target array `ik_step` was handed and `tcp_pose()`'s own
# position, so no new read) and the **lift-height knob** (`FRUIT_LIFT_DZ`,
# default off, `direct` + left only). **P71: the `direct` default is the 0.20 m
# rung (`dz = -0.08`), and `+0.08` is the documented restore** - the leg pins the
# default and its origin (the `[grasp] lift_dz:` row / the manifest). It also pins
# the fields and order, the `guard_armed` containment that makes `None` byte-inert,
# the last-tick semantics, the error arithmetic, the P64-style threading (resolve
# once -> caller-owned kwarg -> `tasks.lift_dz_for` at `_carry`'s `grasp_lift` end
# pose, after both goal forms, z only) and that the scripted entries never
# construct the env that arms it.
run_check "P66 lift end + dz" "$python" scripts/236_p66_lift_selftest.py
# P70: the output station's **height** knob (`FRUIT_OUTPUT_BELT_TOP_Z`, default
# 1.35 = shipped) and the clearance report reading the **authored** rail (height
# and keep flag) instead of a hard-coded 0.035. The leg pins the field's
# env-read shape, the five derived consumers that move 1:1 (`output_place_z`,
# the chute top, the chute's run, the discharge envelope, `on_output_belt`), the
# two that must not (the tray floor, the chute's end z), the AST census of the
# eleven `output_belt_top_z` read scopes, the real `_payload_clearance` body on a
# stub (`rails both/outer/none`, `rail_height` 0.05/0.039/0.015 - byte-identical
# at the shipped geometry), and the crossing arithmetic: `f = 0.825`, so the
# belt height is a **0.175:1** lever and removing the rails is 1:1. **P71: the
# rails are now the shipped default (`output_rails=none`)**, so the leg also pins
# that default (the env-read `default_factory` reads `none`, an unset config reads
# exactly like an explicit `none`, and `=both` restores the pre-P71 rail pair).
run_check "P70 belt top + rails" "$python" scripts/238_p70_belt_top_selftest.py
# P72: the **corner** clearance instrument (`clr_edge=`/`clr_edge_min=` on the
# `[carry]` row) and the `scene` provenance block. P71 removed the rails, so the
# rail-frame `clr`/`clr_win` sample a surface that no longer exists; the fields
# pin the slab's own inboard edge (`|output_belt_y| - width/2`, 0.425 m = the
# removed rail's OUTER face, 25 mm outboard of `rail_inner`), the first-tick
# latch + the band minimum, the `guard_armed` containment (FRUIT_CARRY_DIAG off by
# default, no new read), and `assets.scene_provenance` as the shared builder both
# manifest writers call (rail mode/height/proud/inset, the slab's top z and edge,
# the direct lift rung; the collector's `lift` is null by construction).
run_check "P72 clr_edge + scene" "$python" scripts/239_p72_clr_edge_selftest.py
# P129: the pad-material lane. No code ships, so the leg pins the *unset* path
# (cage pad mu 2.0, no close window, no hard stop), the openarm finger material's
# two default sites, the pair arithmetic the record rests on (1.25-1.46) and the
# algebra's two thresholds (0.815 per fruit, 0.613 pool-wide).
run_check "P129 pad material" "$python" scripts/265_p129_material_selftest.py
# P131: the four-pad ring's **aperture law** (`FRUIT_CAGE_APERTURE` = `shipped`
# | `max_extent` | `pad_axes`). The leg pins the unset path bit for bit (the
# P107 widest-horizontal expression), the two variant laws (the mesh's largest
# axis; the max over the ring's own base-frame pad axes, which equals the
# shipped axes for a top-down hand), the cage3 law's invariance, and the one
# task route that makes the variant do anything: `deep = the hand's extent`
# (and the two-jaw 2.5 mm floor dropped) **only** for an armed radial hand, plus
# the `[cage]` row's `law/ext/deep/sep` fields. No simulator.
run_check "P131 cage aperture law" "$python" scripts/266_p131_cage_aperture_selftest.py
# P132: the serrated pad face (fixture-first, **no shape promoted**). The leg
# pins the shape's *unset* path - `FRUIT_FINGER_FACE` still defaults to `flat`,
# the `_add_contact_faces` gate is unchanged and no `serr` token exists in
# `src/` (nothing was built on the hand) - plus the fixture's four registered
# profiles, the brief's tooth geometry (5 crests, 1.0 mm, 8 mm pitch, 60/45 deg),
# the tooth's placement at the fruit's widest row (not the face centre), the
# fixture-only lip's downward-only extension (the plate top is invariant) and the
# corrected right-handed facet frame (P117's left-handed one made one pad 62 mm
# thick). No simulator.
run_check "P132 serrated face" "$python" scripts/267_p132_serr_selftest.py
# P135: the model-based tracker. The leg pins the estimator (exact on the model,
# a velocity step followed by the third tick, the CA form's recorded overshoot),
# the correction's definition (zero under the conveyor, the off-conveyor
# displacement after a step, the clamp), the camera calibration (a ratio, so the
# stage's units cancel; a synthetic sphere re-fitted to 1e-12 m) and every knob's
# off default. No simulator.
run_check "P135 tracker" "$python" scripts/268_p135_track_selftest.py
run_check "P141 observation aux" "$python" scripts/269_p141_obs_aux_selftest.py
run_check "P142 endpoint + handover" "$python" scripts/270_p142_endpoint_selftest.py
# P207: the emitted joint target's rate cap (`FRUIT_POLICY_TARGET_RATE` rad/s,
# default 0 = the shipped untouched target). The leg pins the strict resolver,
# the rate-0 identity (element for element, signed zeros, a new float64 array),
# the one-tick bound, the 0.275 rad step's tick count, and the source shape: one
# resolver, the per-attempt measured re-seed, one call site in `_apply` before the
# joint drive write, the servo hand-back, and the banner/manifest.
run_check "P207 target rate" "$python" scripts/271_p207_target_rate_selftest.py
# P208: a servo hand-back drops the stale policy chunk. The source-shape leg pins
# the default-off direct-only knob, the per-attempt ownership flags, the
# hand-back return in `_apply` before A2C2/tracking/joint shaping, the `act`
# break, and that the P207 rate knob stays independent.
run_check "P208 replan" "$python" scripts/272_p208_replan_selftest.py
# P210: ACT-style temporal ensembling of overlapping chunks. P209 measured that
# executing half a *stochastic* chunk doubles the boundary noise; the classical
# remedy is to average the overlapping predictions. The leg pins the strict
# alpha resolver, the alpha-0 identity, the alpha*new+(1-alpha)*prev arithmetic,
# the shape/steps edges, and the env wiring (one resolver, per-attempt reset, the
# blend before the rel anchor, the banner and the manifest block).
run_check "P210 ensemble" "$python" scripts/273_p210_ensemble_selftest.py
# P211: the size-conditioned selector floor (`FRUIT_SELECT_SMALL_EXTRA` /
# `_DIA`, direct/policy only). The leg pins the two strict parsers, the direct
# gate and the per-candidate filter, the diag row's same floor, the manifest
# block, and the TASKS_MD5 pin against the file on disk.
run_check "P211 small select" "$python" scripts/274_p211_small_select_selftest.py
# P212: the place transit's per-arm speed (FRUIT_PLACE_SERVO_VMAX_LEFT/RIGHT,
# fallback to the global, one side selection, banner/manifest only when armed).
run_check "P212 place vmax" "$python" scripts/275_p212_place_vmax_selftest.py
# P213 probe: `FRUIT_WRIST_ANNOTATORS` is the wrist camera's own list, with the
# head's P135 list as the default; the wrist cameras stay default-off.
run_check "P213 wrist annotators" "$python" scripts/276_p213_wrist_annotators_selftest.py
# P214 probe: the mask-free wrist depth window is reporting-only, default-off,
# direct-only, and cannot write the goal/percept/control targets.
run_check "P214 wrist depth" "$python" scripts/277_p214_wrist_depth_selftest.py
# P215: the size-dependent direct finger cap (`..._DIRECT_SMALL` / `_DIA`,
# default 0 = the global cap; one per-sample selection; manifest block).
run_check "P215 small clamp" "$python" scripts/278_p215_small_clamp_selftest.py
# P216: the phase close's along-belt window gets a lower bound
# (`FRUIT_CLOSE_RAMP_DY_LO`, default -inf = the shipped one-sided path).
run_check "P216 close lo" "$python" scripts/279_p216_close_lo_selftest.py
# P218: the size-conditioned scripted skill (`FRUIT_SMALL_HANDOVER`, default off,
# direct + ablate none; a fruit <= the diameter cut runs `_run_scripted`).
run_check "P218 small handover" "$python" scripts/280_p218_small_handover_selftest.py
# P222: the side-conditioned scripted skill (`FRUIT_HANDOVER_SIDE` = right/left/
# both, default off; the active arm runs `_run_scripted`).
run_check "P222 side handover" "$python" scripts/281_p222_side_handover_selftest.py
# P227i: the single-arm (Franka) jaw law - the Panda's pad faces are 6 mm apart
# at q=0 (measured), its joint/link roots live under `panda_hand`, and the build's
# finger material / drive-cap authoring is spec-driven (the first Franka build
# authored neither). The OpenArm's set, order and offsets are unchanged.
run_check "P227i arm spec" "$python" scripts/282_p227i_arm_spec_selftest.py
# P227z: the continuous pickup's return must not write `_aligned_start() or start`
# - that returns an ndarray, so `or` raises "The truth value of an array with
# more than one element is ambiguous" and the first continuous clip aborted after
# pick 1 (`logs/121_policy_video_traceback.txt`). The fix reads it into a
# variable and tests `is None`; both halves are pinned here, and the shipped
# per-episode reset never reaches the branch (`FRUIT_CONTINUOUS_TRANSIT=1` only).
run_check "P227z continuous return" "$python" -c "import sys; src = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read(); bad = '_aligned_start() or'; good = 'start if _aligned is None else _aligned'; assert bad not in src, f'rl_env.py still contains {bad!r} (an ndarray under `or` raises)'; assert good in src, f'the continuous return lost its None test: {good!r} missing'; assert 'FRUIT_CONTINUOUS_TRANSIT' in src; print('continuous-return form ok')"
# P227z: a multi-minute clip cannot buffer every view (5 min x 4 views is ~60 GB),
# so `121_policy_video.py` grew `--views` (capture a subset) and
# `--capture-every` already keeps real time at 15 fps. `--help` exits at parse,
# before any simulator, so this is a cheap structural pin. A run that asks for
# `--views observer,overhead` writes exactly those two mp4s
# (`logs/p227/video_smoke_views.log`: 2 clips, no gripper/head/side_by_side).
# P227aa: the owner's cell semantics - several arms share a line and each takes
# the fruit it can serve, so a fruit already inside the catch window is not this
# arm's. `FRUIT_SKIP_LATE` ends that attempt on the tick the trigger fires with
# too little lead instead of chasing it (the chase is the only "weird" motion the
# cell shows). The resolver is exercised here; unset/0 must be the shipped path.
run_check "P227aa skip rule" "$python" -c "import sys; sys.path.insert(0, 'src'); from fruit_sorting.rl_env import resolve_skip_late as r; assert r(None) == 0.0 and r('') == 0.0, 'unset must resolve off'; assert abs(r('0.5') - 0.5) < 1e-9, 'the threshold must parse'; bad = 0
for tok in ('-1', 'abc', 'nan', 'inf'):
    try:
        r(tok)
    except ValueError:
        bad += 1
assert bad == 4, f'{bad}/4 bad tokens refused (a typo must not read as off)'; src = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read(); assert 'self._skip_late > 0.0 and intercept' in src, 'the guard site is missing'; assert 'not this arm' in src, 'the skip note is missing'; print('skip rule ok')"
# P227ab: a long clip must not buffer its frames in RAM. Measured: 26 picks at
# 30 fps x 2 views is ~46 GB, which thrashed the 2 GB swap and a run crawled for
# 16 h before it was killed. `--frames-dir` writes JPEGs and holds paths, and the
# encoder normalises one frame at a time (no `prepared` list). Source-shape pin -
# the flag is exercised end to end by the clips themselves.
# P227ac: the close's chase cap. A re-close follows the fruit to wherever it
# drifted, and until this knob there was no bound: measured, one attempt reached
# 380 mm and the arm's j4 extended 0.85 rad where placements span 0.42-0.46. The
# knob reuses the *existing* abort body (the measured "fruit left the pick station"
# path), so the pin is the branch's shape plus the strict parse - the path itself
# is rare (0 fires at 0.10 m in 16 episodes, 0 at 1 mm in 3, one in the delivered
# clip's 26 picks) and is recorded as not-exercised, not as measured.
# P227ac decision A (owner, 2026-11-24): a bins cell keeps its release ABOVE the
# rim and accepts the ~0.20 m free fall; the accompanied descent would drive the
# pads 0.19 m below the rim, into the box. The branch is explicit now (it used to
# be arithmetic that happens to hold because output_belt_top_z > a bins payload's
# bottom), so a bin-geometry change cannot flip it silently.
# P227ac decision C (owner, 2026-11-24): a SHALLOW rim, so the accompanied descent
# does not take the pads below the rim. Measured: rim 0.16 -> 0.030 moves below_rim
# from -0.105..-0.120 to +0.013..+0.028 while the payload still stops 39-40 mm above
# the bin floor. The margin is paired with FRUIT_PLACE_LOW_CLEARANCE (25 mm) - the
# pin asserts the resolved default and the override, not the arithmetic.
# P227ad: with the goal measured, the FIRE decision must not read the simulator.
# `_fruit_for_trigger` returns the tracker's current-tick estimate (the same numbers
# the policy sees) and tags the source; unset returns the simulator exactly as
# before. The pin is that both fire sites call it and that no `spawner.velocity(`
# remains inside a `should_fire` argument list.
# P227ad (second half): the primitive's PRE-GRASP reads take the estimate, and the
# post-grasp ones do not - after the grasp the payload follows the hand, which the
# code dead-reckons (`_gripper_offset`), so a "replace all 117 reads" change would be
# wrong. The pin is that split, plus the guard (the lever is meaningless without the
# tracker) and the callable contract (the catch-up reads every tick while the estimate
# is published every 4).
run_check "P227ad primitive estimate" "$python" -c "
import re
src = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
lines = src.splitlines()
assert 'def _fruit_state' in src, 'the helper is missing'
assert 'est() if callable(est) else est' in src, 'the callable contract is missing'
i0 = next(i for i,l in enumerate(lines) if l.startswith('    def _grasp_carry_place_impl'))
i1 = next(i for i in range(i0, len(lines)) if 'for _close_attempt in range(close_attempts)' in lines[i])
pre = '\n'.join(lines[i0:i1]); post = '\n'.join(lines[i1:i0+3800])
n_pre = pre.count('self._fruit_state(sample)')
assert n_pre >= 10, f'only {n_pre} pre-grasp reads routed to the estimate'
assert post.count('self.spawner.position(sample)') >= 1, 'the post-grasp payload reads were replaced too (they must stay: the payload follows the hand)'
env = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read()
assert 'FRUIT_PRIMITIVE_ESTIMATE=1 needs FRUIT_GOAL_SOURCE=perception' in env, 'the guard is missing'
assert 'def _estimate_now' in env and 'predict_at(horizon)' in env, 'the live estimator is missing'
assert 'self.task.fruit_estimate = _est' in env and 'self.task.fruit_estimate = None' in env, 'the injection is not cleared'
print(f'primitive estimate ok (pre-grasp {n_pre} reads)')"
# P228 (Stage 0, docs/ARCHITECTURE_4T.md): the latency the WORLD pays. The
# shipped direct loop never steps the simulator while the model runs, so its
# 26 ms costs zero belt travel - the metric inflation ReflexBench/LIBERO-Dynamic
# name. `FRUIT_EVAL_LATENCY=<d>` advances `d` control ticks after each decision's
# inference and before the chunk executes (sync-hold). The leg pins the resolver
# table, the control period against tasks.py's own literal, the injector's
# executed semantics (advance, no observe, no record), the no-inference case and
# the RTC refusal.
# P230: the close-phase trace (`FRUIT_CLOSE_TRACE=1`, default off). It exists to
# separate "the pads closed on air beside the aim" from "the fruit walked out
# during the ramp" - the two readings P229 could not tell apart. The pin is the
# default-off path, the row's site (inside the close tick loop, AFTER the step so
# it is post-step), its fields, and that it adds no articulation read.
# P231: the lift travels with the belt (`FRUIT_LIFT_TRACK_BELT=1`, default off).
# The pin is the default-off path, the lift-only scope, the bound, and that the
# offset is applied to the belt's own axis only.
# P232: the belt-wave instrument must reach **both** tick paths. P135 ticked it
# inside `_step_sim` (the primitive) only, so an armed wave disturbed the contact
# phase and not the approach. The pin is: the env's `advance` ticks it too, the
# call is guarded for the `__init__` prime (no task yet), it is inert unless the
# wave is armed, and `advance`'s stepping rule is unchanged.
# P233: the trigger's approach speed must be the belt it is on
# (`FRUIT_TRIGGER_SURFACE_SPEED=1`, default off). P232 measured the defect: the
# fire row printed a constant `speed=` under a wave because the trigger read
# `encoder_speed`, a setpoint echo (P141). The pin is the default-off read, the
# two field names, and that both `should_fire` sites share the one variable.
# P236: the direct lane's block report. `_cycle_begin`/`_cycle_mark` live in the
# impl but `_cycle_report` is only called by `note_result`, which the direct entry
# never runs - so `FRUIT_CYCLE_REPORT=1` printed nothing for the policy handover
# (P235's gap). The pin is the ownership test (a scripted `_run_impl` already began
# one), the begin before the impl and the report in the finally, and that the
# scripted reporter is untouched.
run_check "P236 direct cycle report" "$python" -c "
src = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
i = src.index('    def grasp_carry_place(')
j = src.index('    def _fruit_state(', i)
blk = src[i:j]
assert '_cycle_owned' in blk
assert 'self._cycle_marks is not None and not self._cycle_marks' in blk, 'ownership test'
assert blk.index('self._cycle_begin()') < blk.index('self._grasp_carry_place_impl('), 'begin before the impl'
assert 'if _cycle_owned:' in blk and 'self._cycle_report()' in blk
assert src.count('self._cycle_report()') == 2, 'note_result keeps its own report'
print('direct cycle report ok (owned by the env, scripted path unchanged)')"

# P249: the axis-aware catch-up exit is **scoped to the direct presentation**
# (P248's powered cell: 40/40 vs 38/40, catch 200 -> 21 ticks, cycle -1.42 s). The
# pin is the resolver table, the caller-owned attribute, and that the row is
# suppressed on a scope-off path (so the scripted acceptance's stream is unchanged).
# P254: the continuous return's blend clock can be sized from the motion it has to
# make (default off; the shipped fixed 90+60 is byte-identical). The pin is the
# arithmetic (min-jerk peak 1.875x, the arm's 5.445 rad/s), the clamps, and that the
# knob is read only inside the continuous return.
# P256: the per-instance physics row (mass + friction from `FruitSample`, no new
# simulator read), default off, one print per pick.
# P258: the release's 60-tick retreat/settle is redundant in a continuous episode
# (the return's own `_lift_clear` raises the hand anyway). Caller-owned, so the
# scripted single arm and the two-line cannot read it; default OFF until a cell.
# P260: the release block's second-level marks (default off, so the shipped
# `[cycle]` row keeps its shape for every existing report).
# P261: the lift height reaches only the left arm; the both-arms form is opt-in.
# P266: the catch-up's behind-the-fruit stall guard (default off, no note, bounded).
# P268: the catch-up's force exit ("pushing, not closing"): off by default, and with the
# knob off not even the tactile read exists.
# P275: the truth-free grasp judge (force + measured pad span), default off.
# P275: the truth-read census, and the two elements it forced (diameter, start x).
# P275: the selector can be built from one camera frame instead of the spawner.
# P275: `detect_all` executed on a synthetic frame (labels -> mask -> fit -> ROI -> bias).
run_check "P275 detect all" "$python" scripts/291_p275_detect_selftest.py

run_check "P275 select from percept" "$python" -c "
p = open('src/fruit_sorting/perception.py', encoding='utf-8').read()
assert 'def detect_all(' in p
# it must not disturb the tracked target's filter state
body = p[p.index('def detect_all('):]
body = body[:body.index('def summary(')]
for forbidden in ('last_radius =', 'last_centre =', 'last_estimate ='):
    assert forbidden not in body, forbidden
assert 'instance_id_segmentation' in body and '_fit_sphere(' in body
r = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read()
assert 'FRUIT_SELECT_FROM' in r
assert 'os.environ.get(\"FRUIT_SELECT_FROM\", \"truth\")' in r, 'default truth'
assert 'def _selector_states(' in r and 'def _percept_states(' in r
# both selector call sites go through the resolver
assert r.count('self._selector_states()') == 3
assert 'self.spawner.state(), reach_anywhere=False' not in r
# a fallback can never be silent
assert 'truth_fallbacks=' in r
print('select from percept ok (off by default, both sites, fallback named)')"

run_check "P275 truth census" "$python" -c "
f = open('src/fruit_sorting/fruits.py', encoding='utf-8').read()
assert '_TRUTH_AUDIT' in f and 'FRUIT_TRUTH_AUDIT' in f
assert 'def print_truth_read_census(' in f and 'def truth_read_census(' in f
# the two simulator fruit-state reads are the two that count
for name in ('def position(self, sample: FruitSample)', 'def velocity(self, sample: FruitSample)'):
    i = f.index(name)
    j = f.index('return', i)
    assert '_truth_read(' in f[i:j], name
# off by default
assert 'os.environ.get(\"FRUIT_TRUTH_AUDIT\", \"0\")' in f
r = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read()
assert 'print_truth_read_census(' in r, 'the env must print it'
# the diameter leak: perception mode must not keep the caller's (truth) value
g = r[r.index('def _goal_vector('):]
g = g[:g.index('return', g.index('FRUIT_GOAL_NOMINAL_DIA'))]
assert 'FRUIT_GOAL_NOMINAL_DIA' in g, 'the nominal diameter fallback'
# the start-pose x source
assert 'FRUIT_START_ALIGN_FROM' in r
print('truth census ok (off by default, nominal diameter, start-x source)')"

# P276: the pre-grasp contact reads go through the one estimate door; the
# post-grasp / evaluation / recovery reads must NOT (the payload follows the hand,
# and a belt estimate there is a lie).
# P277: the wrist view executed on a synthetic frame - the prior as a preference,
# the raster control missing by 8 cm, the paper preset's field of view.
# P278: the force-first sweep - off by default, gated on all three terms, millimetres,
# a stall guard, and it only skips the ramp's fast phase when the tactile loaded.
# P279: the segmenter's plumbing - the channel order (the trainer/loader once
# pooled the *channel* axis as height and produced 241 input channels), the
# checkpoint's key set against the deploy builder, and a real forward pass.
# P281: the pad mount - jaw-relative by default, and on the pad it is built from the
# hand's own measured span and grasp standoff (a constant put the eye on the belt).
# P282: the two light knobs are inert at their defaults (dome x1, no ring light).
run_check "P282 lighting" "$python" -c "
t = open('src/fruit_sorting/scene.py', encoding='utf-8').read()
assert 'os.environ.get(\"FRUIT_LIGHT_DOME\", \"1.0\")' in t, 'dome default 1.0'
assert 'dome.set_intensities(140.0 * _amb)' in t
assert 'os.environ.get(\"FRUIT_LIGHT_WRIST\", \"0\")' in t, 'ring light default off'
i = t.index('if _ring > 0.0:')
j = t.index('self._wrist_light_ops[side]', i)
assert 'SphereLight' in t[i:j] or 'SphereLight(' in t[i:j], 'the ring is a real light'
assert '_wrist_light_ops' in t and '_lops.Set(' in t, 'the ring follows the camera'
print('lighting ok (dome x1 and no ring by default, the ring rides the camera')"

run_check "P281 wrist mount" "$python" -c "
w = open('src/fruit_sorting/wrist.py', encoding='utf-8').read()
assert 'FRUIT_WRIST_MOUNT' in w
assert 'os.environ.get(\"FRUIT_WRIST_MOUNT\", \"jaw\")' in w, 'default is the shipped mount'
i = w.index('        if _mount == \"pad\":')
blk = w[i:w.index('        _sign = -1.0 if os.environ.get(', i)]
assert 'self.task._hand_separation(self.side)' in blk, 'span from the hand'
assert 'self.task._pad_standoff(True, sample)' in blk, 'height from the hand'
assert 'set_wrist_pose' in blk
# the projection gate must not reach the 3-D modes
j = w.index('if self.mode == \"raster\" and float(p_cam[2]) >= -0.03:')
assert j > 0
print('wrist mount ok (jaw default, pad from robot state, raster-only projection gate')"

run_check "P279 wrist segmenter" "$python" -c "
import sys; sys.path.insert(0, 'src')
import numpy as np
from fruit_sorting import wrist as W
img = W.pool_rgb(np.zeros((240, 424, 3), dtype=np.uint8), 120, 160)
assert img.shape == (3, 120, 160), img.shape
assert W.pool_depth(np.zeros((240, 424), dtype=np.float32), 120, 160).shape == (120, 160)
m = W.upscale_mask(np.zeros((120, 160), dtype=bool), (240, 424))
assert m.shape == (240, 424), m.shape
assert 'learned' in W.MODES
import json, os
ck = 'checkpoints/wrist_seg.pt'
if os.path.exists(ck):
    meta = json.load(open(os.path.splitext(ck)[0] + '.json'))
    net = W._build_seg_net(meta['h'], meta['w'], meta)
    import torch
    net.load_state_dict(torch.load(ck, map_location='cpu')); net.eval()
    x = torch.zeros(1, 4, meta['h'], meta['w'])
    with torch.no_grad():
        y = net(x)
    assert tuple(y.shape) == (1, 1, meta['h'], meta['w']), y.shape
    print('   forward ok at', meta['h'], 'x', meta['w'], 'val IoU', meta['val_iou'])
else:
    print('   (no checkpoint yet - shape checks only)')
print('segmenter ok (channels-first, mask upscale, forward)')"

run_check "P278 close sweep" "$python" -c "
t = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
assert 'FRUIT_CLOSE_SWEEP' in t
assert 'os.environ.get(\"FRUIT_CLOSE_SWEEP\", \"0\")\n            ) / 1000.0' in t, 'millimetres, default off'
i = t.index('                if (\n                    self._close_sweep > 0.0')
blk = t[i:t.index('                for _close_step, gap in enumerate(close_ramp):', i)]
assert 'and dynamic_capture' in blk
assert 'self._estimate_age_s() >= self._close_sweep_stale' in blk, 'only when the estimate is stale'
assert 'self._tactile_force(arm_name) >= self._close_sweep_force' in blk, 'force decides'
assert 'follow_centre(_ctr, quat, float(wide))' in blk, 'the pads stay open while sweeping'
assert '_y0 - _step * (_k + 1)' in blk, 'downstream is -y'
assert 'if _stall >= 12:' in blk, 'a workspace stall ends the sweep'
assert 'close_ramp[int(fast_ticks):]' in blk, 'the fast phase is skipped only on contact'
assert 'contact=' in blk and 'achieved' in blk, 'the row reports what moved, not what was asked'
print('close sweep ok (mm, off by default, tactile-gated, downstream, stall-guarded)')"

run_check "P277 wrist view" "$python" scripts/292_p277_wrist_selftest.py

run_check "P276 contact estimate" "$python" -c "
import re
src = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
start = src.index('def _grasp_carry_place_impl(')
nxt = src.index(chr(10) + '    def ', start)   # the next method's def
body = src[start:nxt]
# 17 doors were already here (P227ad), P276 added 14 (18 reads) and P278's
# sweep adds one more inside the same function
calls = body.count('self._fruit_state(sample)')
assert calls == 33, calls
assert body.count('fruit_now, fruit_v_now = self._fruit_state(sample)') == 4
# the evaluation and the judge keep the simulator
assert 'z_before = float(self.spawner.position(sample)[2])' in body
assert 'z_after = float(self.spawner.position(sample)[2])' in body
assert '_took = float(self.spawner.position(sample)[2]) - z_before > 0.004' in body
# the close's drift verification deliberately stays on truth: a belt estimate
# would make it vacuous (both terms move with the belt)
assert 'fruit_end = np.asarray(self.spawner.position(sample), dtype=float)' in body
# the fallback is bit-for-bit the simulator, so the unarmed path is inert
i = src.index('def _fruit_state(')
assert 'return (' in src[i:i+2200]
assert 'np.asarray(self.spawner.position(sample), dtype=float),' in src[i:i+2200]
print('contact estimate ok (14 doors = 18 reads; evaluation, judge and drift stay on truth)')"

run_check "P275 grasp judge" "$python" -c "
t = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
assert 'FRUIT_GRASP_JUDGE' in t
assert 'os.environ.get(\"FRUIT_GRASP_JUDGE\", \"truth\")' in t, 'default truth'
assert 'def _grasp_judge_held(' in t
assert 'self._hand_separation(side)' in t, 'the pad span term'
assert 'self.tactile.read()' in t[t.index('def _grasp_judge_held('):t.index('def _grasp_judge_held(')+900]
assert 'if self._grasp_judge == \"force\":' in t
# the truth read must be in the else branch of the probe gate
i = t.index('if self._grasp_judge == \"force\":')
j = t.index('_took = float(self.spawner.position(sample)[2]) - z_before > 0.004')
assert i < j, 'the truth read must sit after the force branch'
# the matched settle: 0 by default, and it only ever runs in the truth branch
assert 'FRUIT_GRASP_JUDGE_SETTLE' in t
assert 'os.environ.get(\"FRUIT_GRASP_JUDGE_SETTLE\", \"0\")' in t, 'settle default 0'
# the probe decision prints its own numbers, with no truth column
assert '[task] grasp probe idx=' in t
_pe = t.index('[task] grasp probe idx=')
assert t.rindex('if self._grasp_judge == \"force\":', 0, _pe) > t.rindex('else:', 0, _pe), \
    'the probe row belongs to the force branch'
# the matched settle must sit INSIDE the truth branch, before the truth read
_else = t.index('else:', i)
assert _else < t.index('if self._grasp_judge_settle:', _else) < j, \
    'the matched settle belongs to the truth branch'
print('grasp judge ok (off by default, sensors only when armed)')"

run_check "P268 catch force exit" "$python" -c "
t = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
assert 'FRUIT_CATCH_FORCE_EXIT' in t
assert 'os.environ.get(\"FRUIT_CATCH_FORCE_EXIT\", \"0\")' in t, 'default off'
assert 'if force_exit > 0.0:' in t, 'the whole block is gated'
assert 'force_slow >= 30' in t and 'force_trace[-31] - 0.0005' in t, 'both conditions'
assert 'self.tactile.read()' in t[t.index('if force_exit > 0.0:'):t.index('if force_exit > 0.0:')+400], \
    'the read is inside the gate'
print('catch force exit ok (off by default, gated read, force AND plateau)')"

run_check "P266 catch stall guard" "$python" -c "
t = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
assert 'FRUIT_CATCH_STALL_TICKS' in t
assert 'os.environ.get(\"FRUIT_CATCH_STALL_TICKS\", \"0\")' in t, 'default off'
assert 'if stall_window > 0:' in t
assert 'float(tip[1]) > float(fruit_now[1])' in t, 'the upstream test'
assert '_ref - 0.0005' in t, 'the improvement bar'
assert 'notes.append' not in t[t.index('P266: behind the fruit'):t.index('P266: behind the fruit')+600], \
    'the guard adds no note'
print('catch stall guard ok (off by default, upstream-only, no note)')"

run_check "P261 lift dz both" "$python" -c "
import os
src = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read()
assert 'FRUIT_LIFT_DZ_BOTH' in src
assert 'def _lift_dz_arms(' in src, 'the one arm-set helper'
assert 'return {\"left\": float(dz), \"right\": float(dz)}' in src, 'both by default'
assert 'return {\"left\": float(dz)}' in src, 'the left-only restore'
assert 'os.environ.get(\"FRUIT_LIFT_DZ_BOTH\", \"1\")' in src, 'default on since P261'
assert 'must be ' in src
# both return sites go through the helper
assert src.count('_lift_dz_arms(') == 3, src.count('_lift_dz_arms(')
print('lift dz both ok (both by default, left-only restore, one helper)')"

run_check "P260 cycle sub" "$python" -c "
t = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
assert 'FRUIT_CYCLE_SUB' in t
assert t.count('if self._cycle_sub:') == 7, t.count('if self._cycle_sub:')
for name in ('rel_low','rel_pads','rel_fing','lift_takeoff','lift_settle',
             'place_clear','place_blend'):
    assert f'self._cycle_mark(\"{name}\")' in t, name
# the sub-marks sit inside the release block: after the place mark, before release
i_place = t.index('self._cycle_mark(\"place\")')
i_low = t.index('self._cycle_mark(\"rel_low\")')
i_release = t.index('self._cycle_mark(\"release\")')
assert i_place < i_low < i_release
print('cycle sub ok (3 gated marks inside release, default off)')"

run_check "P258 skip release settle" "$python" -c "
t = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
e = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read()
assert 'self.skip_release_settle = False' in t, 'default off in the task'
assert 'elif self.skip_release_settle:' in t, 'the branch'
# the branch must sit BEFORE the retreat and the plain settle
assert t.index('elif self.skip_release_settle:') < t.index('elif retreat > 0.0:')
assert 'self.task.skip_release_settle = bool(self._continuous_picks)' in e
assert 'FRUIT_CONTINUOUS_SKIP_SETTLE' in e
# applied only AFTER the task exists (P249's defect class, pinned there too)
assert e.index('self.task = PickAndPlaceTask(') < e.index('self.task.skip_release_settle')
print('skip release settle ok (default off, continuous only, after construction)')"

run_check "P256 instance diag" "$python" -c "
src = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read()
assert 'FRUIT_INSTANCE_DIAG' in src
assert 'sample.mass * 1000' in src and 'float(sample.friction)' in src, 'both fields'
assert src.index('FRUIT_INSTANCE_DIAG') < src.index('[inst] idx='), 'the gate precedes the row'
assert 'if os.environ.get(\"FRUIT_INSTANCE_DIAG\", \"0\") == \"1\":' in src, 'default off'
print('instance diag ok (mass + friction, default off)')"

run_check "P254 blend adapt" "$python" -c "
import math
src = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read()
assert 'FRUIT_CONTINUOUS_BLEND_ADAPT' in src
assert 'if self._blend_adapt:' in src
assert '1.875 * _delta_q / _step' in src, 'the min-jerk peak factor'
assert 'self._blend_vmax / 120.0' in src, 'the control rate'
assert 'max(self._blend_min, min(self._blend_max, _need))' in src, 'clamped'
assert 'ticks = int(os.environ.get(' in src and \
    'FRUIT_CONTINUOUS_TRANSIT_TICKS' in src, 'the shipped fixed clock still exists'
# the arithmetic, executed: the arm's own numbers
step = 5.445 / 120.0
for delta, want_lo, want_hi in ((0.36, 14, 16), (2.30, 94, 96)):
    need = math.ceil(1.875 * delta / step)
    assert want_lo <= need <= want_hi, (delta, need)
print('blend adapt ok (1.875 peak, 5.445 rad/s, clamped, off by default)')"

run_check "P249 catch tol scope" "$python" -c "
src = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read()
assert 'FRUIT_CATCH_TOL_AXIS' in src
assert 'self._catch_tol_axis = presentation == \"direct\"' in src
assert 'scope-off' in src and 'explicit' in src
assert 'self.task.catch_tol_axis = bool(self._catch_tol_axis)' in src
# P249's own defect: the first attempt applied it **before** `self.task` existed,
# the getattr guard swallowed it and the lever was silently inert. Pin the order.
assert src.index('self.task = PickAndPlaceTask(') < src.index(
    'self.task.catch_tol_axis = bool(self._catch_tol_axis)'
), 'the apply must be after task construction'
assert 'must be ' in src and 'got {_cta_raw' in src, 'strict parsing'
assert 'if self._catch_tol_axis_origin != \"scope-off\":' in src, 'the row is gated'
t = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
assert 'self.catch_tol_axis = os.environ.get' in t, 'the task attribute is caller-owned'
assert 'if self.catch_tol_axis:' in t
print('catch tol scope ok (direct default, explicit wins, row gated)')"

run_check "P233 trigger speed" "$python" -c "
src = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read()
assert 'FRUIT_TRIGGER_SURFACE_SPEED' in src
assert 'self._trigger_surface_speed = (' in src
i = src.index('_field = (')
blk = src[i:i + 260]
assert 'surface_speed' in blk and 'encoder_speed' in blk, 'both sources must be named'
assert 'self._trigger_surface_speed' in blk, 'the knob must select the field'
assert src.count('encoder_speed=encoder') == 2, 'both should_fire sites share it'
print('trigger speed ok (default off, surface_speed routed, one variable)')"

run_check "P232 belt wave" "$python" -c "
src = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read()
i = src.index('    def advance(self, steps: int) -> None:')
blk = src[i:i + 1400]
assert 'self._SimulationManager.step(steps=int(steps))' in blk
assert 'self._app_utils.update_app(steps=0)' in blk, 'the stepping rule must not change'
assert 'getattr(self, \"task\", None)' in blk, 'the __init__ prime has no task yet'
assert '_belt_wave_on' in blk and '_belt_wave_tick()' in blk
assert 'update_app(steps=' in blk and 'update_app(steps=steps)' not in blk
print('belt wave ok (both tick paths, guarded, inert unless armed)')"

run_check "P231 lift track" "$python" -c "
src = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
assert 'FRUIT_LIFT_TRACK_BELT' in src
assert 'self._lift_track_belt = os.environ.get(\"FRUIT_LIFT_TRACK_BELT\", \"0\") == \"1\"' in src
i = src.index('if name == \"grasp_lift\" and self._lift_track_belt:')
blk = src[i:i + 900]
assert 'FRUIT_LIFT_TRACK_MAX' in blk and 'np.clip' in blk, 'the offset must be bounded'
assert 'commands[:, 1] +=' in blk, 'only the belt axis may move'
assert '_belt_speed_estimate()' in blk, 'the offset must use the measured belt speed'
j = src.index('if name == \"grasp_lift\" and self._lift_track_belt:')
assert 'place' not in src[j:j + 120].split('grasp_lift')[0]
print('lift track ok (default off, lift-only, bounded, belt axis)')"

run_check "P230 close trace" "$python" -c "
src = open('src/fruit_sorting/tasks.py', encoding='utf-8').read()
assert 'FRUIT_CLOSE_TRACE' in src
assert 'self._close_trace = os.environ.get(\"FRUIT_CLOSE_TRACE\", \"0\") == \"1\"' in src
lines = src.splitlines()
i0 = next(i for i, l in enumerate(lines) if 'for _close_step, gap in enumerate(close_ramp)' in l)
i1 = next(i for i in range(i0, len(lines)) if 'if self._close_trace:' in lines[i])
assert any('self._step_sim(close_substeps)' in lines[i1 - k] for k in (1, 2, 3)), 'the row must be post-step'
row = '\n'.join(lines[i1:i1 + 20])
for field in ('cmd=', 'aim_minus_fruit=', 'x_off=', 'n=', 'f='):
    assert field in row, field
assert 'tactile.read()' in row and 'define_dof' not in row
print('close trace ok (default off, post-step, one tactile read)')"

run_check "P228 eval latency" "$python" scripts/287_p228_latency_selftest.py

run_check "P227ad trigger source" "$python" -c "src = open('src/fruit_sorting/rl_env.py', encoding='utf-8').read(); assert 'def _fruit_for_trigger' in src, 'the helper is missing'; assert src.count('self._fruit_for_trigger(') >= 2, 'a fire site does not use it'; assert '[fire] source=' in src, 'the source tag is missing'; tail = src.split('intercept, intercept_info = should_fire(')[1][:400]; assert 'measured_velocity=_fire_vel' in tail, 'the selected-fruit fire still reads the simulator'; tail2 = src.split('p_fire, p_info = should_fire(')[1][:400]; assert 'measured_velocity=p_vel' in tail2, 'the presented-fruit fire still reads the simulator'; print('trigger source ok')"
run_check "P227ac shallow rim" "$python" -c "import os, sys; sys.path.insert(0, 'src'); from fruit_sorting.assets import SceneConfig; c = SceneConfig(); assert abs(float(c.bin_wall_height) - 0.030) < 1e-9, f'default rim {c.bin_wall_height} is not shallow (0.030)'; assert abs((float(c.bin_floor_top_z) + float(c.bin_wall_height)) - 1.130) < 1e-6; os.environ['FRUIT_BIN_WALL_HEIGHT'] = '0.16'; c2 = SceneConfig(); assert abs(float(c2.bin_wall_height) - 0.16) < 1e-9, 'the deep form is not reachable'; del os.environ['FRUIT_BIN_WALL_HEIGHT']; print('shallow rim ok')"
run_check "P227ac place floor (bin)" "$python" -c "src = open('src/fruit_sorting/tasks.py', encoding='utf-8').read(); assert 'decision B' in src, 'the decision is not recorded in the code'; assert 'floor = float(self.cfg.bin_floor_top_z)' in src, 'the bin floor is not used'; assert 'bin_index=None' in src, 'the destination is not threaded into _place_low'; assert 'bin_index=bin_index,' in src, 'the call site does not pass the destination'; assert 'floor=float(self.cfg.output_belt_top_z)' not in src.split('def _place_low')[1].split('def ')[0].split('clearance =')[0], 'the floor is still the belt'; print('place floor ok')"
run_check "P227ac close chase cap" "$python" -c "src = open('src/fruit_sorting/tasks.py', encoding='utf-8').read(); assert 'FRUIT_CLOSE_DRIFT_MAX' in src, 'the knob is missing'; assert '_capped = _drift_cap > 0.0 and drift > _drift_cap' in src, 'the cap term is missing'; assert 'if _close_attempt + 1 >= close_attempts or _capped:' in src, 'the cap does not share the abort body (that body is the measured one)'; assert 'chase cap {_drift_cap * 1000' in src, 'the note does not name the cap'; assert 'is not a number' in src and 'finite number >= 0' in src, 'the parse is not strict'; print('close chase cap ok')"
run_check "P227ab disk frame buffer" "$python" -c "src = open('scripts/121_policy_video.py', encoding='utf-8').read(); assert '--frames-dir' in src, 'the flag is missing'; assert 'def _save(view: str, frame' in src, 'the store helper is missing'; assert 'def _load(item):' in src, 'the loader is missing'; assert 'prepared = [normalise(' not in src, 'the encoder still materialises the clip (that is the 46 GB path)'; assert 'write_with_ffmpeg(path, images, width, height)' in src; assert 'frame buffer on disk' in src; print('disk frame buffer ok')"
run_check "P227z video views" "$python" -c "src = open('scripts/121_policy_video.py', encoding='utf-8').read(); assert '--views' in src, 'the capture-set flag is missing'; assert '\"observer\" not in _views' in src, 'the observer guard is missing'; assert 'if \"close\" in _views:' in src and 'if \"overhead\" in _views:' in src, 'the cameras are authored unconditionally again (a 5-minute clip then pays 4 buffers)'; assert 'is simply absent' in src, 'the view-aware capture comment is missing'; assert 'if frames.get(\"head\")' in src, 'the side_by_side guard is missing'; print('video --views shape ok')"
# P73: the `[carry]` row's **rotation schedule** (`tilt0=`, `tilt_end=`,
# `tilt_max=`, `t45=`, `t75=`, `tilt_rate=`) - the instrument the place-leg
# question needs, because the leg-end `[attitude]` tilt is saturated by the place
# pose (80.8-94.6 deg across BOTH the placed and the lost legs of the P71 corpus,
# and the right reaches it too). The leg pins the six fields and their order
# (between `jaw_z=` and `drift_on=`), the `guard_armed` containment
# (`FRUIT_CARRY_DIAG`, default off), that the tilt is `[attitude]`'s own
# `acos(-rot[2,2])`, that the accumulation adds **no articulation read**
# (`rot_now` is the block's existing one), the first-crossing/max/signed-step
# arithmetic, and the printed row parsing back. No simulator.
run_check "P73 rotation schedule" "$python" scripts/240_p73_tilt_selftest.py
# P75: the **place-onset trace** (`FRUIT_PLACE_ONSET_TRACE=<ticks>`, default 0 =
# off) - one `[place-trace]` row per tick for the first `<ticks>` ticks of every
# `place*` leg, for the question P73/P74 left open (where in the first ~40 ticks
# the payload leaves the pinch, and in what ORDER the symptoms appear). The leg
# pins the resolver (`unset`/blank/non-numeric/negative -> off), the
# `guard_armed` term that makes it self-sufficient, the `place*`-only scope, the
# field order and the round-trip through the report's own reader
# (`scripts/242_p75_classify.py`), that **no articulation read is added** (the
# block's own `rot_now`/`pads`/`_tcp_pos` are reused; the two reporting readers
# it adds are named), the `|v|ach` first-tick convention, and the four
# classification cases (a)/(b)/(c)/none plus the flat-error and same-tick
# controls. No simulator.
run_check "P75 place-onset trace" "$python" scripts/241_p75_place_trace_selftest.py
# P76: the `[carry]` row's **pry/crush** group (`dia=`, `sep_max=…@t<tick>`,
# `gap@sep_max=`, `sep_min=`, `fmax=`) - the force-ladder phase's instrument.
# `sep@loss` is sampled at the loss tick while P75 measured the pads reaching
# their 98.1 mm stop 9 ticks later, so the pry needs the leg's EXTREME separation
# plus the gap the servo commanded at that tick; `sep_min` against the fruit's own
# `dia` is the crush's interference form and `fmax`/`force_min` its force form.
# The leg pins the field order, the `guard_armed` containment (`FRUIT_CARRY_DIAG`,
# default off), that the separation read is `arm.jaw_separation()` (the same call
# as `sep@onset`/`sep@loss`/`sep_end` and P41's offline `sep_max`), that the stored
# gap is the per-tick command, the n/a forms, the first-tick convention (an
# inherited firing site STARTS at the stop) and the row parsing back. No simulator.
run_check "P76 pry/crush fields" "$python" scripts/243_p76_sep_selftest.py
# P78: the **contained** form of P77's 60 N count win - a runtime finger-drive
# force cap raised for the left arm's `place*` legs only and restored at each
# leg's end (`FRUIT_FINGER_MAXFORCE_SCOPE=place-left`, default OFF). P77 measured
# the win (left placed 11/21 -> 17/20, p = 0.043, 3/3 seeds) and the global cap's
# price (a build-time property of both arms of every presentation: the scripted
# acceptance moves at attempt 0, `fingerprint: DIFFERS`), and that every escape
# and every pry is a left `place0` leg. The leg pins the resolution table
# (non-`direct` is `(None, None)` before any value is read, an explicit global
# `FRUIT_FINGER_MAXFORCE` wins, `place-left` -> `{"left:place": cap}`,
# every strict raise), the **two disjoint leg classes** (`place*` for
# `place-left`, `grasp_lift` for P79's `grasp-left`, so neither token can arm the
# other's leg), the `_carry` wrapper's `try`/`finally` (the leg is inside the try
# and the restore in the finally), the live-view `set_dof_max_efforts` write site
# (one, and the restore target is the cap READ at the leg's start, never a
# hard-coded 10 N), the two dispatch sites, the untouched build-time global
# writer, and the manifest field (which keeps the exact `<side>:<legs>` keys).
# No simulator.
run_check "P78/P79 scoped finger force" "$python" scripts/244_p78_scope_selftest.py
# P83: **fail fast** (`FRUIT_FAIL_FAST=<mm>`, default unset/0 = off, `scripted`
# only) - the cell pays a full attempt for every failure (P80: all 7 failures were
# `cnp` and each cost the whole 15.1 s attempt), so the attempt ends the tick the
# payload's in-hand displacement (`clean_slip_max`, the `[carry]` row's own
# operand) reaches the threshold. The leg pins the resolver (`0`/unset is off,
# `>= 100` mm becomes metres, and the `0 < mm < 100` band raises - the census's
# worst **placed** leg is 76.3 mm over 249 attempts, `logs/p83/census.txt`), the
# single trip site (one `>=` on the tracker's operand, gated by the per-attempt
# `threshold > 0 and scripted` flag, latching once and **breaking** the leg loop),
# the attempt-local latch cleared at every attempt start, that the knob is the
# fourth arm of the W8-B `guard_armed` disjunction (its operand is computed
# there), that both early-exit sites read the one `_attempt_ended_early()`
# predicate (so the abort reuses the shipped P7-2b fast-skip machinery), that the
# trip adds **no** `result.notes` entry (the class stays `cnp`), the audit row's
# fields, and the restored `arm.max_step`/wrist hold on the tail. No simulator.
run_check "P83 fail fast" "$python" scripts/245_p83_failfast_selftest.py
# P67: the **place-leg climb** (`FRUIT_LIFT_CLIMB`, metres of vertical raise at the
# place leg's start, `direct` + left only, default OFF) - the re-shape of P66 phase
# 4's failed rail-crossing gate: the crossing is only 0.175:1 with the lift height
# and 1:1 with the height the transit starts at. The leg pins the resolver (strict,
# `<= 0` and non-finite raise, every other presentation `None`), the place-leg-only
# scope (a `grasp_lift` leg cannot be touched), the **prepended waypoint** by
# building the real `tasks.lift_climb_commands` offline (its last sample IS
# `start + climb*z`, x/y untouched, z monotone, the place profile's caps), the
# `transit_start = start` byte-identity when off, the crossing arithmetic
# (f = 0.825, the `(1 - f)` leverage, the solved 0.179 m for the +33 mm floor), the
# row / manifest, and that no scripted entry can reach the env that arms it.
run_check "P67 place-leg climb" "$python" scripts/237_p67_climb_selftest.py
# P62 phase 2: the left-only, direct-scoped grasp-attitude override
# (`FRUIT_GRASP_LEFT_TOPDOWN`, default off). The resolver is offline and inert by
# default; the real `_grasp_quat` body (extracted with `ast`, so no pxr import)
# is honoured per arm with `None` = the file exactly; the shipped file branch,
# the single construction site and the untouched `configs/` are pinned; and the
# finding that decides the knob's meaning is pinned as a tree property - the file
# the direct env loads (`configs/waypoints.json`) already carries T0 for both
# arms, and the never-stop catch's own installed hold IS that left value, so the
# armed run commands what the shipped run commands.
run_check "P62 grasp attitude" "$python" scripts/232_p62_grasp_selftest.py
# P64 phase 1: the pre-compensated left carry attitude
# (`FRUIT_GRASP_LEFT_PRECOMP`, default off, `direct` + left only). The resolver
# is offline and inert by default; the **composition** `q_cmd = q_drift^-1 (x)
# q_T0` is recomputed from the measured axis/angle constant and checked against
# the module value (and against the tool-frame alternative, which it is not);
# the real `tasks.carry_hold_override_for` (extracted with `ast`) returns `None`
# for `None`, an empty dict, an unnamed side and every leg but `grasp_lift`, and
# a copy for the armed one, so a knob-off task writes no hold at all. The site is
# the one guarded `arm.hold_quaternion` write in `_carry` - a *different* channel
# from P62's `grasp_quat_override`, which P62 measured inert on the achieved
# attitude - and the row / manifest / untouched `configs/` are pinned.
run_check "P64 left precomp" "$python" scripts/234_p64_precomp_selftest.py
# P85: **the shipped scripted cell is the bimanual two-line**. The leg runs the
# real resolvers and the real supply plan: the 1/1 defaults with their origin
# flags (`FRUIT_BIARM=0` the pre-P85 single arm, `FRUIT_BIARM=1
# FRUIT_BIARM_TWOLINE=0` the unchanged shared-station pipeline), the two-line's
# supply package (dense wave sheet + balanced A:B:C, and the single arm's 50/30/20
# restore), `two_line=None` keeping the pre-P85 raw read for every non-scripted
# consumer, `two_line_enabled()` being **session-scoped** (so the single-arm and
# shared-station paths cannot move) against the ambient `two_line_resolved()`,
# the three scripted entries passing the resolution while `rl_env` and the hybrid
# canary pin `two_line=False`, the collector manifest's four new provenance keys,
# and `accept.sh` gating a two-line session through `190`.
run_check "P85 two-line default" "$python" scripts/246_p85_selftest.py
# P87: the release trim as a **two-line-scoped shipped default**. P86 measured
# the S2 cell (dwell 20 -> 0, the pad/finger settles 3 -> 2 = -76 ticks) as a
# clean positive on the two-line, but the knob is read at a site **every**
# presentation shares - so the flip is scoped, not global. The leg runs the real
# resolver and the real provenance builder: unset + no scope is `_SPEED_SHIPPED`
# **exactly** (the single arm / shared station / canary / direct env cannot
# move), unset + two-line is P86's 0/2/2, the override table (`=0` restores even
# on the two-line, `=1` and `FRUIT_SPEED_ALL` still win globally, `=0` beats the
# union, `FRUIT_SPEED_RELEASE_SETTLE` moves the settle only when the cell is on),
# the clock arithmetic (188 / 112 / saved 76), the scope being the **session**
# predicate at exactly one call site, the `[biarm] release profile:` row printing
# only inside `run_bimanual`, and `physics.release` in both manifest writers.
run_check "P87 release scope" "$python" scripts/247_p87_release_scope_selftest.py
# P88: the **place** cap as a two-line-scoped cell, measured and NOT shipped.
# After P87's release trim the place block is the largest remaining one
# (3.19 s vs 1.70 and
# 1.65), and P44's S1 cell (0.35 -> 0.52 at the shipped `a_max`) is the only
# unspent cell of the three. The cap is read at the shared `_carry_leg`, so the
# cell is scoped exactly like the release's **but its default is OFF** (P88's
# gate failed on delivery), so the shipped tree is inert. The leg runs the real
# resolver and the real provenance builder: unset is `_SPEED_SHIPPED` exactly on
# every path (the two-line included), the explicit `=0.52` is the measured arm
# (362 -> 244 ticks at the named 0.55 m reference, saved 118), the override
# table (`=0`, an explicit speed and `FRUIT_SPEED_ALL` globally, `=0` beats the
# union, `..._AMAX` pins the acceleration), the profile clock reproducing
# `motion.jerk_limited` at both the speed- and acceleration-limited regimes, the
# scope being the **session** predicate at both scoped consumers, the
# `[biarm] place profile:` row printing only inside `run_bimanual`, and
# `physics.place` in both manifest writers.
run_check "P88 place scope" "$python" scripts/248_p88_place_scope_selftest.py
# P89: the **lift** cap as a two-line-scoped cell, measured and NOT shipped - the
# last unspent profile block (1.65-1.70 s against the shipped release 1.70 and
# place 3.14-3.19), and P44's **S3-v** (0.30 -> 0.37 with the shipped `a_max`
# **1.0**: the acceleration raise bought 0.00 s and spent transient) is its
# measured arm. The cap is read at the shared `_carry_leg` `grasp_lift` branch,
# so the cell is scoped exactly like the release's **but its default is OFF**
# (P89's gate failed on delivery), so the shipped tree is inert. The leg runs the
# real resolver and the real provenance builder: unset is `_SPEED_SHIPPED`
# exactly on every path (the two-line included), the explicit `=0.37` is the
# measured arm (162 -> 136 ticks at the named 0.21 m reference, saved 26), the
# **S3/S13 pairs are not moved** (`=1` and `FRUIT_SPEED_ALL` keep 0.36/1.9) while
# 0.37 means 1.0 however it is written, `FRUIT_SPEED_LIFT_AMAX` pins the
# acceleration, the profile clock reproduces `motion.jerk_limited` at both
# regimes and the short-leg null, the scope being the **session** predicate at
# both scoped consumers, the `[biarm] lift profile:` row printing only inside
# `run_bimanual`, and `physics.lift` in both manifest writers.
run_check "P89 lift scope" "$python" scripts/249_p89_lift_scope_selftest.py
# P91: the **take-off validation ramp** as a two-line-scoped tick cell
# (`FRUIT_DYNAMIC_PROBE_TICKS` 60 -> 24), measured and NOT shipped. It is not a
# `FRUIT_SPEED_*` cell but a loop count, and it is the largest genuinely
# speedable item the P91 audit found among the five never-profiled blocks: the
# descent is *schedule invariant* (its wait exits at `speed*(t_desc+margin)`, so
# `block = lead/speed - margin` and a faster leg just waits longer), the hover
# and prepose are IK-capped transits, and the grip block's 60 of a clean 210
# ticks is the one real profile left - with the 54-tick belt-break beside it a
# measured anti-shear constant. The leg runs the real resolver and the real
# provenance builder: unset is 40 on the single arm and 60 in a two-line session
# (so the shipped tree is inert - the default is OFF), the cell is 24 ticks
# (saved 36 = -0.300 s at 120 Hz) in the two-line scope only, an explicit value
# wins on both scopes, the ramp's *height* is untouched, the probe loop reads the
# one resolver at the **session** predicate, the `[biarm] take-off profile:` row
# prints only inside `run_bimanual`, and `physics.takeoff` is in both manifest
# writers.
run_check "P91 probe scope" "$python" scripts/250_p91_probe_scope_selftest.py

# P94 (`FRUIT_CARRY_OFFSET_MAX=<m>`, unset/0 = off = the pre-P94 path): the bound
# on the `_gripper_offset` that `_carry`'s assisted branch may apply as a *tool*
# offset on the jaw hand. The reading is `rot.T @ (payload - tcp)` taken at the
# grasp routine's entry, so on a hand whose pads are the fingers it is a tool
# offset only while the payload was there then; P93 measured a 1313 mm reading on
# one leg (18.8x the hand's own 70 mm `_pad_standoff`) with a 419 N / 1.545 m/s /
# 2361 mm-slip arm flight, and the same-seed control carrying the path at 116 mm.
# Past the bound the branch commands the pads (`centre`) - the coherent branch's
# own command for this hand, i.e. the same `hand_is_jaw` guard the coherent branch
# and the `_carry` tail already apply. The leg runs the real resolver and the
# shipped guard expressions: unset is the shipped 0.20 m bound (the measured arm),
# `0` restores the pre-P94 path bit for bit, the command inside the bound is
# `centre - rot @ offset` bit for bit, above it it is `centre`, the kinematic-pad
# hand keeps its offset at any magnitude (the guard is jaw-hand only), and the diag
# row prints the issued target so the census reads the applied jump with no new
# field.
run_check "P94 offset bound" "$python" scripts/251_p94_offset_selftest.py

# P95 (`FRUIT_FRUIT_TRACE=<max rows>`, off by default): the *selected fruit's*
# per-tick trace of its whole attempt - the pre-pose blend, the hover move, the
# descent's own hover wait and the catch - which is the window P93 could not see
# (`FRUIT_DYNAMIC_TRACE`'s first row *is* the descent leg's start). The row is
# the fruit's position, linear and angular velocity and every live fruit within
# 0.15 m; **fruit reads only**, the branch-neutral class of AGENTS section 2,
# proved by a 970/970 and a 974/974 `[fruit]`-stream replay in `logs/p95`. The
# opt-in `FRUIT_FRUIT_TRACE_ARM=1` adds each arm's link positions and is the
# declared branch-moving probe cell; `FRUIT_FRUIT_TRACE_NOOP=1` is the
# instrument's own no-readback control. The leg runs the real tick body on stubs:
# the switch table, the one `_step_sim` hook (never inside `ik_step`), the
# fruit-only default path, the no-op arm returning before any read, the single
# arming/disarm/flush sites (attempt-local: the two-line runs two attempts on two
# threads), the row shape, the 0.15 m neighbour filter and the arm gate.
run_check "P95 fruit trace" "$python" scripts/252_p95_ftrace_selftest.py

# P96/P97/P98: the clearance pre-pose - the resolver table (unset/no-session is
# `scope-off`, unset/two-line follows the **False** scoped default P98 restored
# - the pre-P96 path - `=1` arms P96's measured clearance pose, the height band
# raises outside [0.155, 0.25]), the height arithmetic the phase-0 map measured
# (0.165 - 6 mm clears the invariant, 0.155 - 6 mm does not), the one solve site
# with the pick-point skip bypassed, the two hold forms, the gated print (the
# pre-P96 path adds no line) and the collector's three provenance keys.
run_check "P96/P97/P98 pre-pose clearance" "$python" scripts/253_p96_prepose_selftest.py

# P100: the **park return's fixed clock**. `_biarm_park` -> `go_ready` ->
# `_ready_move` -> `_transit_to` -> `_ready_transit` is `_catch_up_drive` (20/40)
# + `_lift_clear` + `_blend_to`'s min-jerk **ramp** (90) + its **settle** hold
# (120); only the last two are fixed and the arm carries nothing, so they are the
# cell. The leg pins: unset/no-session **is** the shipped 90/120 exactly, the env
# is **not read** without a two-line session (the driver's pre-session prime
# transit keeps the shipped clock), unset/two-line is also the shipped pair
# because the default is **False**, the explicit `60/75` is the measured arm with
# its **135-of-210-tick** clock (-0.625 s at 120 Hz), the halves are independent
# overrides with the read sites' clamps, the flip's 45/45 resolves in the
# two-line scope only, the shipped pair **is** `READY_TRANSIT_BLEND_TICKS` and
# `_ready_settle`'s own default, one consumer on the session predicate with the
# hardcoded `else 120` gone, `q_step` is arithmetic inside the diag block (no
# read added to the shipped path), and `physics.park` in both writers.
run_check "P100 park scope" "$python" scripts/254_p100_park_selftest.py
# P102: the **contact-patch** tactile statistic a vision tactile would report -
# `docs/PLATFORM_SURVEY.md` §5.1's stage (i), run in sim before any hardware is
# bought. The tree's tactile channel is 2 normal-force scalars and W5-C measured
# that where the force collapses the payload is gone within 0-3 ticks, so the
# survey's hypothesis is that a **spatial** channel (the patch's centroid moving
# on the pad) leads the collapse. `FRUIT_TACTILE_PATCH=<ticks>` (default **0 =
# off**) derives that channel from geometry the sim already has. The leg pins:
# the resolver (unset/blank/typo/`<= 0` -> off, so the shipped path is one integer
# test per leg), the `guard_armed` term that makes it self-sufficient, that the
# row block adds **no `ik_step` work and no articulation read** (the two readers
# it does add are named), the exact geometry (the centroid is invariant under a
# wrist rotation about the jaw axis and under a translation along it; the two
# pads' `h` sum to the measured span; the parallel-plane degeneracy is declared),
# the occupancy arithmetic (1 inside / 0 outside / monotone / zero-radius), the
# pad rectangle's **long-axis origin** (`finger_length - half_long`, because a
# rectangle centred on the link origin scores a good seat as off the pad - the
# measured `frac` 0.062), and the row parsing back through `logs/p102/census.py`'s
# own reader (a dropped field must fail). No simulator.
run_check "P102 tactile patch" "$python" scripts/255_p102_tactile_selftest.py

# --------------------------------------------------------------------------- #
# P103: the patch-triggered **slip re-grip** (`FRUIT_SLIP_REGRIP=<mm>`, default
# **0 = off = the shipped path**). P102 measured the signal (a patch tactile sees
# the loaded slide 21-113 ticks before the pinch is lost, 6/6 escapes) and priced
# the reaction without building it. This build takes the trigger from P102's
# channel - `dc >= <mm>` on a **seated** leg, P102's own seat test - and the
# action from the tree's shipped `slip_enabled` re-seat: the pad centre that
# restores the leg-start relation, applied in one go and re-based into the rest
# of the profile, so the re-seat costs no tick and adds no control law. The leg
# pins: the resolver (unset/blank/`0` -> off; `0 < mm < 1` raises, because a held
# leg's patch moves 0.02 mm median over 60 legs), the flag's `False` default, the
# `guard_armed` term that makes the trigger self-sufficient, the trigger's four
# terms in the registered order (P102's seat, the threshold, the shipped abort
# ceiling, and **no** cooldown or per-leg cap), that the `[regrip]` branch uses
# the same six expressions the shipped block does and adds **no `ik_step` and no
# `_step_sim`** (so no tick and no new profile), the two-line session scope, and
# the two row grammars parsed back through `logs/p103/p103_report.py`'s own
# readers. No simulator.
run_check "P103 slip re-grip" "$python" scripts/256_p103_regrip_selftest.py

# --------------------------------------------------------------------------- #
# P111: the cage's **compliant closure with a hard stop** (P110's item 1). P110
# measured why the four-pad ring cannot enclose: one radial synergy on four
# force-capped *position* pads gives the near pad `cap/k = 0.049 mm` of yield and
# leaves the far pad `2*delta` short, so a 6-20 mm arrival is launched instead of
# pushed. The owner's item is per-pad compliance - a soft drive yields `cap/k`
# instead, so the four pads can balance toward the ring's centre. The leg pins:
# the two regimes (`min(k*s, cap)`: the rigid drive is AT the cap at the shipped
# 1 % squeeze and k=1e3 is at 0.6 N/pad on a 60 mm fruit, i.e. 4-7x weaker - which
# is why the arm needs the **hard stop**), the freeze's shift (the 0.5 N trigger
# is reached at 0.005 mm of penetration at k=1e5 and 0.5 mm at k=1e3, so the
# compliant close is gentler AND shallower), the stop executed on the real
# methods (off = a no-op; on = all four drives rewritten at the hold k with
# `c = 2 sqrt(k m)`, the **target and the cap untouched** - a bottoming-out
# spring loads the pad, it does not move it; idempotent inside one close; released
# by an OPEN command so the next close is soft again), the **one** call site in
# the dynamic close's tail gated on the hand's *kind* and **not** on
# `FRUIT_CAGE_PROBE` (a diagnostic must not own a behaviour), the `[cage]` row's
# `off0`/`off` centring fields (the payload's radial distance to the ring's axis,
# from reads the probe already takes), and `TASKS_MD5`. No simulator.
run_check "P111 cage compliance" "$python" scripts/257_p111_cage_compliance_selftest.py
run_check "P112 three-jaw ring" "$python" scripts/258_p112_cage3_selftest.py

# P114: the scenario descriptor + the sort instruction - the **data layer** that
# makes a new pipeline a JSON plus a solve, and the **instruction layer** that
# makes a fruit's destination independent of the arm that carries it. The leg is
# offline: the strict descriptor schema (unknown keys, duplicate ids, a
# side/target contradiction, an unknown reach status/schedule all raise), the
# cached unset resolution (`FRUIT_SCENARIO` unset -> None, no file, no print),
# the instruction grammar (precedence, `skip`, millimetre sizes, the inline `;`
# separator) and every refusal (unknown/negative destination, a destination no
# arm serves, an unknown attribute/operator/grade/species, a second `default`, a
# rule after `default`, an empty file), the **capability model** (left = +y,
# right = -y; `unreachable` refused; `auto` provisional until the solve), the
# **shipped-path fallbacks** in `tasks.py` (`_arm_for_destination` keeps
# `0 -> left`, `_place_xy_for` keeps `cfg.output_belt_drop_points`, the place leg
# and both diagnostics read it, both selectors gate on the instruction, the
# ledger runs only under it, only `auto` destinations are solved, the worker
# dispatches the fruit's own destination), the descriptor's SceneConfig /
# SupplyPlan application (armed moves the fields, unset restores them, an
# explicit env knob wins), and the scope refusals (the direct env and the hybrid
# canary have no dispatcher; both scripted drivers consult `sort_destination`).
run_check "P114 scenario descriptor" "$python" scripts/259_p114_scenario_selftest.py
# P114, the instruction half: a rule file is parsed into an ordered
# `condition => destination` list, validated against the descriptor's
# destinations and the pool's vocabulary, and resolved through the capability
# map (left = +y, right = -y; `unreachable` refused, `auto` provisional until
# its solve). The leg pins the grammar (`grade=`, `species=`, `size<` in
# millimetres, `default`, `skip`, the inline `;` separator), precedence, the
# unset resolver (one env read, None, no parse) and every refusal (unknown /
# negative destination, a destination no arm serves, one declared unreachable,
# an unknown attribute or operator, a grade/species the pool cannot produce, a
# second default, a rule after default, an empty file).
run_check "P114 sort instruction" "$python" scripts/260_p114_instruction_selftest.py
# P115: the instruction becomes writable as a sorting **spec**. `and` conjoins
# up to three attribute terms in one rule (`species=apple and size>=66 => 1`,
# every term must match; `or` stays written as more rules because the first
# match wins), the four canonical files in `configs/instructions/` parse against
# the shipped descriptor, and `FRUIT_SORT_STRICT=1` turns an instruction that
# drops fruit into a startup refusal. The leg also pins the `tasks.py` shape:
# one `[sort] rule N` row per rule, one environment read, the guard called at
# construction (before the first attempt), and the guard tripping on an
# unmatched fruit (None) rather than on a deliberate `skip`.
run_check "P115 instruction and" "$python" scripts/261_p115_instruction_selftest.py
# P116: the plan/lint tool - the owner's two-rule example ("A-grade left,
# apples right") contains a real overlap (an A-grade apple matches both), and
# the tool must report it, plus the partition and the cells that match no rule.
# The precise form (`species=apple and grade!=A`) must report no overlap.
run_check "P116 sort plan" bash -c \
    "'$python' scripts/262_sort_plan.py --instruction configs/instructions/owner_a_left_apples_right.txt | grep -q 'OVERLAP: 1 pair' && '$python' scripts/262_sort_plan.py --instruction configs/instructions/owner_precise.txt | grep -q 'OVERLAP: none' && '$python' scripts/262_sort_plan.py --instruction configs/instructions/owner_a_left_apples_right.txt --strict-overlap > /dev/null; test \$? -eq 1"
# P121: the DIRECT/POLICY env uses the instruction (it used to refuse it). The
# leg pins the offline dispatch table (un-instructed = shipped grade lane;
# today's routing = the same table; a non-grade rule; skip/unmatched refused),
# the goal channel's OOD gate (destination 2 needs FRUIT_SORT_THIRD_DEST=1),
# the capability map (including the unreachable tray), and the source wiring:
# `_begin_pick` dispatch, `_run_primitive`'s thread-local place target + ledger,
# the 7+1 action, the reseed arm check and the manifest block.
run_check "P121 direct env sort" "$python" scripts/263_p121_env_sort_selftest.py
# P123: the third output body (FRUIT_OUTPUT_LANES=3, default off). The leg pins
# the unset path (the two shipped lanes reproduce every shipped scalar, and the
# generalised belt/tray/discharge tests equal the pre-P123 expressions on a
# dense grid), the third lane's measured geometry and the invariants it rests on
# (no interpenetration, its own tray, the delivered point 7 sd inside its slab,
# the body upstream-clear of every transit and downstream of the fruit's band),
# the tray census (`output_tray_of` names the tray and agrees with the boolean),
# and the source shape (one layout reader, the builder and the scene on it).
run_check "P123 output lanes" "$python" scripts/264_p123_output_lanes_selftest.py

if [ -n "$run_log" ] && [ -f "$run_log" ]; then
    # P85: the log decides the scenario (and therefore the reference and the
    # floor), exactly as `scripts/accept.sh` does.
    if grep -q '\[fruit\] \[biarm\] two-line scheduler:' "$run_log"; then
        run_check "motion budgets" bash scripts/190_twoline_gate.sh \
            -r configs/motion_reference.json -m "${TWOLINE_FLOOR:-0.60}" "$run_log"
    else
        run_check "motion budgets" "$python" scripts/105_motion_regression.py "$run_log" \
            --fingerprint configs/motion_reference_single.json
    fi
else
    skipped=$((skipped + 1))
    printf '%-26s %-4s %6s\n' "motion budgets" "SKIP" "-"
    {
        echo "### motion budgets: SKIP"
        if [ -z "$run_log" ]; then
            echo "    no run log given; pass one to judge a pick-and-place run:"
        else
            echo "    $run_log not found; pass a log that exists:"
        fi
        echo "      scripts/accept.sh            # produces logs/accept.log"
        echo "      scripts/selfcheck.sh logs/accept.log"
        echo "    this is not a failure: the run it judges is a separate ten-attempt command"
        echo
    } >> "$log"
fi

total_end=$(date +%s.%N)
total=$(awk -v a="$total_start" -v b="$total_end" 'BEGIN { printf "%.2f", b - a }')

{
    echo "### summary"
    echo "    failed=$failed skipped=$skipped total=${total}s"
} >> "$log"

echo
if [ "$failed" -ne 0 ]; then
    echo "FAIL: $failed check(s) failed (log: $log)"
    exit 1
fi
if [ "$skipped" -ne 0 ]; then
    echo "PASS: ${failed} failures, $skipped skipped (log: $log)"
else
    echo "PASS: all checks (log: $log)"
fi
