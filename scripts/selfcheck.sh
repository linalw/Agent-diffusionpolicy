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

if [ -n "$run_log" ] && [ -f "$run_log" ]; then
    run_check "motion budgets" "$python" scripts/105_motion_regression.py "$run_log" \
        --fingerprint configs/motion_reference.json
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
