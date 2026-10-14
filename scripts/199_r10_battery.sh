#!/usr/bin/env bash
# R10-A battery: the reach-anywhere catch against the shipped station-fixed
# catch on the W6-A 2D patch sheet (single arm, 20 attempts, seed 5).
#
#   bash scripts/199_r10_battery.sh > logs/r10/00_battery_driver.log 2>&1
#
# Pre-registered in `logs/r10/PREREGISTRATION.md` section 3. Tier A solo: all
# runs go through the run-claim wrapper, one simulator at a time.
#
#   * control   - the shipped tree (FRUIT_REACH_ANYWHERE unset/0), also the
#                 no-harm fingerprint check against
#                 `configs/motion_reference_patch.json` (the W6/W7 single-arm
#                 patch branch this tree should still reproduce);
#   * treatment - FRUIT_REACH_ANYWHERE=1 FRUIT_REACH_DIAG=1;
#   * double    - the treatment double-run, bit-identical physics check;
#   * control2  - the control double-run (the branch the comparison stands on).
#
# Outputs: logs/r10/30_control.log, 31_reach.log, 32_reach_b.log,
# 33_control_b.log, 40_compare_*.txt, 41_motion_*.txt, 42_w6report_*.txt.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/r10

BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5)
PATCH=(FRUIT_SUPPLY_PATCH=1)
MIX=(FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25)
SINGLE=(FRUIT_BIARM=0)
TREAT=(FRUIT_REACH_ANYWHERE=1 FRUIT_REACH_DIAG=1)

status=0

check_log() {  # check_log <log> <exit-code>
    local log=$1 code=$2
    if [ "$code" -ne 0 ]; then
        echo "[r10] FAIL: exit=$code log=$log"
        status=1
        return 1
    fi
    if [ ! -s "$log" ]; then
        echo "[r10] FAIL: missing or empty log=$log (exit=0 but no output)"
        status=1
        return 1
    fi
    echo "[r10] ok: exit=0 log=$log"
    return 0
}

run() {  # run <log> <run-limit-s> <env...>
    local log=$1 limit=$2 code
    shift 2
    echo "[r10] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[r10] exit=$code $(date +%H:%M:%S) $log"
    check_log "$log" "$code"
}

echo "[r10] battery start $(date +%H:%M:%S)"
echo "[r10] tree: tasks.py $(md5sum src/fruit_sorting/tasks.py | cut -d' ' -f1)"

run logs/r10/30_control.log 5400 "${SINGLE[@]}" "${PATCH[@]}" "${MIX[@]}" || true
run logs/r10/31_reach.log 5400 "${SINGLE[@]}" "${PATCH[@]}" "${MIX[@]}" "${TREAT[@]}" || true
run logs/r10/32_reach_b.log 5400 "${SINGLE[@]}" "${PATCH[@]}" "${MIX[@]}" "${TREAT[@]}" || true
run logs/r10/33_control_b.log 5400 "${SINGLE[@]}" "${PATCH[@]}" "${MIX[@]}" || true

if [ "$status" -ne 0 ]; then
    echo "[r10] battery incomplete: at least one run failed; the checks are"
    echo "[r10] skipped (fix the run first)."
    exit 1
fi

echo "[r10] treatment double-run determinism (physics [fruit] stream)"
python3 logs/w4/compare_streams.py --physics-only \
    logs/r10/31_reach.log logs/r10/32_reach_b.log \
    > logs/r10/40_compare_treatment.txt 2>&1
cmp_code=$?
cat logs/r10/40_compare_treatment.txt
[ "$cmp_code" -ne 0 ] && status=1

echo "[r10] control double-run determinism"
python3 logs/w4/compare_streams.py --physics-only \
    logs/r10/30_control.log logs/r10/33_control_b.log \
    > logs/r10/40_compare_control.txt 2>&1
cmp2_code=$?
cat logs/r10/40_compare_control.txt
[ "$cmp2_code" -ne 0 ] && status=1

echo "[r10] motion budgets (control, with the patch fingerprint)"
python3 scripts/105_motion_regression.py logs/r10/30_control.log \
    --fingerprint configs/motion_reference_patch.json \
    > logs/r10/41_motion_control.txt 2>&1
m1_code=$?
tail -25 logs/r10/41_motion_control.txt
echo "[r10] motion budgets (treatment; a different branch by construction)"
python3 scripts/105_motion_regression.py logs/r10/31_reach.log \
    > logs/r10/41_motion_treatment.txt 2>&1
m2_code=$?
tail -25 logs/r10/41_motion_treatment.txt
[ "$m1_code" -ne 0 ] && status=1
[ "$m2_code" -ne 0 ] && status=1

echo "[r10] interval / lock-on report (186)"
python3 scripts/186_w6_report.py logs/r10/30_control.log logs/r10/31_reach.log \
    logs/r10/32_reach_b.log logs/r10/33_control_b.log --label r10-a \
    > logs/r10/42_w6report.txt 2>&1
r_code=$?
grep -E "attempts|placements|placed/min|interval|pooled|success" logs/r10/42_w6report.txt | head -40
[ "$r_code" -ne 0 ] && status=1

echo "[r10] R10-A readouts (199)"
python3 scripts/199_r10_report.py logs/r10/30_control.log logs/r10/31_reach.log \
    logs/r10/32_reach_b.log logs/r10/33_control_b.log \
    > logs/r10/43_r10_report.txt 2>&1
p_code=$?
cat logs/r10/43_r10_report.txt
[ "$p_code" -ne 0 ] && status=1

echo "[r10] battery done $(date +%H:%M:%S) status=$status"
exit "$status"
