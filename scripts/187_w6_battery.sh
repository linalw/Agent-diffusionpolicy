#!/usr/bin/env bash
# W6-B battery: the two-line 20-attempt battery on the 2D patch sheet, a
# bit-identical double-run check, and the same-scenario single-arm 20-attempt.
#
#   nohup bash scripts/187_w6_battery.sh > logs/w6/00_battery_driver.log 2>&1 &
#
# Scenario (pre-registered in logs/w6/SPEC.md):
#   * supply: FRUIT_SUPPLY_PATCH=1 (the W6-A 2D sheet; env-gated, default off)
#   * attempts: 20 per run, SEED=5, HEADLESS=1, Tier A solo (154_claim_run)
#   * two-line: FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 (opt-in scheduler; the
#     shipped default stays single-arm)
#   * two-line mix: the balanced A:B:C default the two-line patch scenario
#     selects (0.375/0.375/0.25)
#   * single-arm: FRUIT_BIARM=0, the same patch sheet and the same balanced
#     mix (explicit, so the ratio compares the arms, not the supply)
#   * the double run is a *determinism* check (the physics `[fruit]` stream,
#     `--physics-only`: the `[run]` book-keeping rows are not physics), not a
#     second success-rate sample
#   * the worker-cadence supply probe (W6-A follow-up) produces the delivered
#     2D reading next to the free-cadence design reading.
#
# Guard (W6-A follow-up): every run's exit code and log are checked before the
# determinism check and the report; a failed run stops the battery with a
# non-zero exit instead of letting the check judge a missing log.
#
# Outputs: logs/w6/00_probe_supply_worker.log,
# logs/w6/10_battery_twoline_{1,2}.log, logs/w6/20_battery_single.log,
# logs/w6/12_battery_report.txt (the W6 report, scripts/186_w6_report.py).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/w6

BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
PATCH=(FRUIT_SUPPLY_PATCH=1)
MIX=(FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25)

status=0

check_log() {  # check_log <log> <exit-code>
    local log=$1 code=$2
    if [ "$code" -ne 0 ]; then
        echo "[w6] FAIL: exit=$code log=$log"
        status=1
        return 1
    fi
    if [ ! -s "$log" ]; then
        echo "[w6] FAIL: missing or empty log=$log (exit=0 but no output)"
        status=1
        return 1
    fi
    echo "[w6] ok: exit=0 log=$log"
    return 0
}

run() {  # run <log> <run-limit-s> <env...>
    local log=$1 limit=$2 code
    shift 2
    echo "[w6] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[w6] exit=$code $(date +%H:%M:%S) $log"
    check_log "$log" "$code"
}

echo "[w6] battery start $(date +%H:%M:%S)"

# --- the delivered 2D reading (W6-A follow-up) ----------------------------- #
echo "[w6] worker-cadence supply probe (the delivered 2D reading)"
RUN_LIMIT=1800 scripts/154_claim_run.sh logs/w6/00_probe_supply_worker.log \
    HEADLESS=1 FRUIT_SUPPLY_PATCH=1 FRUIT_BIARM_TWOLINE=1 \
    FRUIT_SUPPLY_PROBE_CADENCE=worker FRUIT_SUPPLY_SECONDS=120 \
    scripts/run.sh scripts/171_supply_probe.py
probe_code=$?
check_log logs/w6/00_probe_supply_worker.log "$probe_code" || true
echo "[w6] probe exit=$probe_code $(date +%H:%M:%S)"

# --- the two-line 20-attempt on the patch sheet, twice --------------------- #
run logs/w6/10_battery_twoline_1.log 7200 "${TWO[@]}" "${PATCH[@]}" || true
run logs/w6/10_battery_twoline_2.log 7200 "${TWO[@]}" "${PATCH[@]}" || true

# --- the same-scenario single-arm 20-attempt ------------------------------- #
run logs/w6/20_battery_single.log 5400 FRUIT_BIARM=0 "${PATCH[@]}" "${MIX[@]}" || true

if [ "$status" -ne 0 ]; then
    echo "[w6] battery incomplete: at least one run failed; the determinism"
    echo "[w6] check and the report are skipped (fix the run first)."
    exit 1
fi

echo "[w6] double-run determinism check (physics [fruit] stream)"
python3 logs/w4/compare_streams.py --physics-only \
    logs/w6/10_battery_twoline_1.log logs/w6/10_battery_twoline_2.log
check_code=$?
echo "[w6] double-run exit=$check_code"
if [ "$check_code" -ne 0 ]; then
    echo "[w6] determinism check FAILED; the report below is diagnostic only"
    status=1
fi

echo "[w6] W6 report"
python3 scripts/186_w6_report.py --label w6-battery \
    logs/w6/10_battery_twoline_1.log \
    logs/w6/10_battery_twoline_2.log \
    logs/w6/20_battery_single.log | tee logs/w6/12_battery_report.txt
report_code=${PIPESTATUS[0]}
echo "[w6] report exit=$report_code"
[ "$report_code" -ne 0 ] && status=1

echo "[w6] battery done $(date +%H:%M:%S) status=$status"
exit "$status"
