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
