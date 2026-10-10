#!/usr/bin/env bash
# W6-C lever battery: the two default-off, two-line-only levers on the W6-B
# patch scenario, each config twice (determinism), plus the park-trace baseline
# and the single-arm no-harm run.
#
#   nohup bash scripts/188_w6c_levers.sh > logs/w6/40_levers_driver.log 2>&1 &
#
# Scenario (identical to scripts/187_w6_battery.sh / logs/w6/SPEC.md):
#   * supply: FRUIT_SUPPLY_PATCH=1, ATTEMPTS=20, SEED=5, HEADLESS=1, Tier A
#     solo via scripts/154_claim_run.sh, two-line opt-in (FRUIT_BIARM=1
#     FRUIT_BIARM_TWOLINE=1), balanced mix (the two-line patch default)
#   * configs:
#       park   = FRUIT_BIARM_PARK_EARLY=1    (the park-gate lever)
#       pref   = FRUIT_BIARM_PREFETCH=1      (L1 prefetch + reserve)
#       both   = both knobs
#   * the second run of each config carries FRUIT_BIARM_TRACE=1 (the clearance
#     reading); the pair counts as the determinism proof only if the physics
#     [fruit] streams are identical, otherwise the trace run is a mechanism run
#   * the park-trace baseline (all knobs off + FRUIT_BIARM_PARK_TRACE=1) is the
#     idle-split mechanism run; pure reporting, expected byte-no-harm vs the
#     W6-B battery log
#   * the single-arm no-harm run repeats logs/w6/20_battery_single.log's
#     scenario (FRUIT_BIARM=0, patch, balanced mix) on the W6-C tree
#
# Outputs: logs/w6/30_parktrace_baseline.log, logs/w6/3{1,2}_lever_park_*.log,
# logs/w6/3{3,4}_lever_prefetch_*.log, logs/w6/3{5,6}_lever_both_*.log,
# logs/w6/20_single_noharm.log, logs/w6/41_levers_report.txt,
# logs/w6/42_determinism_check.txt.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/w6

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/fruits.py \
    scripts/186_w6_report.py > logs/w6/43_tasks_md5_before.txt

BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
PATCH=(FRUIT_SUPPLY_PATCH=1)
MIX=(FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25)

status=0

check_log() {  # check_log <log> <exit-code>
    local log=$1 code=$2
    if [ "$code" -ne 0 ]; then
        echo "[w6c] FAIL: exit=$code log=$log"
        status=1
        return 1
    fi
    if [ ! -s "$log" ]; then
        echo "[w6c] FAIL: missing or empty log=$log (exit=0 but no output)"
        status=1
        return 1
    fi
    echo "[w6c] ok: exit=0 log=$log"
    return 0
}

run() {  # run <log> <run-limit-s> <env...>
    local log=$1 limit=$2 code
    shift 2
    echo "[w6c] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[w6c] exit=$code $(date +%H:%M:%S) $log"
    check_log "$log" "$code"
}

echo "[w6c] levers start $(date +%H:%M:%S)"

# --- the idle split (park trace) on the baseline config -------------------- #
run logs/w6/30_parktrace_baseline.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_PARK_TRACE=1

# --- the park-gate lever --------------------------------------------------- #
run logs/w6/31_lever_park_1.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_PARK_EARLY=1
run logs/w6/32_lever_park_2_trace.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_PARK_EARLY=1 FRUIT_BIARM_TRACE=1

# --- L1 prefetch ----------------------------------------------------------- #
run logs/w6/33_lever_prefetch_1.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_PREFETCH=1
run logs/w6/34_lever_prefetch_2_trace.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_PREFETCH=1 FRUIT_BIARM_TRACE=1

# --- the combined config --------------------------------------------------- #
run logs/w6/35_lever_both_1.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_PARK_EARLY=1 FRUIT_BIARM_PREFETCH=1
run logs/w6/36_lever_both_2_trace.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_PARK_EARLY=1 FRUIT_BIARM_PREFETCH=1 FRUIT_BIARM_TRACE=1

# --- the same-scenario single-arm no-harm run ------------------------------ #
run logs/w6/20_single_noharm.log 5400 FRUIT_BIARM=0 "${PATCH[@]}" "${MIX[@]}"

if [ "$status" -ne 0 ]; then
    echo "[w6c] levers incomplete: at least one run failed; checks skipped."
    exit 1
fi

echo "[w6c] determinism checks (physics [fruit] stream)"
: > logs/w6/42_determinism_check.txt
for pair in "31_lever_park_1 32_lever_park_2_trace" \
            "33_lever_prefetch_1 34_lever_prefetch_2_trace" \
            "35_lever_both_1 36_lever_both_2_trace" \
            "30_parktrace_baseline 10_battery_twoline_1" \
            "20_single_noharm 20_battery_single"; do
    set -- $pair
    {
        echo "== logs/w6/$1.log vs logs/w6/$2.log"
        python3 logs/w4/compare_streams.py --physics-only \
            "logs/w6/$1.log" "logs/w6/$2.log"
    } | tee -a logs/w6/42_determinism_check.txt
    code=${PIPESTATUS[0]}
    if [ "$code" -ne 0 ]; then
        echo "[w6c] pair $1/$2 differs"
    fi
done

echo "[w6c] W6 report"
python3 scripts/186_w6_report.py --label w6c-levers \
    logs/w6/30_parktrace_baseline.log \
    logs/w6/31_lever_park_1.log \
    logs/w6/33_lever_prefetch_1.log \
    logs/w6/35_lever_both_1.log \
    logs/w6/20_single_noharm.log | tee logs/w6/41_levers_report.txt
report_code=${PIPESTATUS[0]}
echo "[w6c] report exit=$report_code"

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/fruits.py \
    scripts/186_w6_report.py > logs/w6/44_tasks_md5_after.txt
if ! diff -q logs/w6/43_tasks_md5_before.txt logs/w6/44_tasks_md5_after.txt \
        >/dev/null; then
    echo "[w6c] WARNING: the tree changed while the battery ran"
    status=1
fi

echo "[w6c] levers done $(date +%H:%M:%S) status=$status"
exit "$status"
