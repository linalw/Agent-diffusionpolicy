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
#   6. rl report parser               scripts/113_rl_report.py --self-test
#   7. rtc runtime selftest           scripts/128_rtc_selftest.py (no checkpoint)
#   8. trigger intercept test         scripts/811_trigger_test.py (pure geometry)
#   9. claim slot harness             scripts/181_claim_slot_selftest.sh (pure locking)
#  10. motion budgets                 scripts/105_motion_regression.py  (needs a run log)
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
run_check "rl report parser" "$python" scripts/113_rl_report.py --self-test
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
# v9/V2: the two-line selector (per-arm station floor, grade preference with
# the any-grade fallback, protected-fruit exclusion) and the pre-pose-lock
# decision - pure logic over a stubbed task, no simulator.
run_check "two-line selector test" "$python" scripts/176_twoline_selftest.py
# X1: the slot claim (mutual exclusion, pool overlap, stale recovery after
# SIGKILL, wait timeout, duplicate-namespace refusal) is pure locking logic.
run_check "claim slot harness" bash scripts/181_claim_slot_selftest.sh

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
