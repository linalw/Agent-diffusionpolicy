#!/usr/bin/env bash
# W8-R3 L3 battery: the hot-arm residency on the W6-B patch scenario.
#
#   nohup bash scripts/193_r3_l3.sh > logs/w8/R3_l3_driver.log 2>&1 &
#
# Scenario (identical to scripts/187_w6_battery.sh / logs/w6/SPEC.md):
#   FRUIT_SUPPLY_PATCH=1, ATTEMPTS=20, SEED=5, HEADLESS=1, Tier A solo via
#   scripts/154_claim_run.sh, two-line opt-in, balanced mix.
#
# Configs:
#   control = trance + park trace (all levers off); must replay the W7-A patch
#             record (logs/w7/20_patch_battery_1.log) with the trace lines
#             dropped, and gives the per-config clearance + idle split.
#   hot     = FRUIT_BIARM_HOT_ARM=1 (the bounded hot-arm residency: with an
#             imminent target after the attempt-boundary feed and the other arm
#             not carrying, the park is replaced by a station-side hold, and the
#             next attempt's pre-pose blend is skipped; starvation / clearance /
#             budget / locked pre-pose park as shipped).
#   * the second hot run carries the clearance + park traces.
#
# Outputs: logs/w8/R3_l3_control_trace.log, R3_l3_hot_{1,2_trace}.log,
# R3_l3_{control,hot}_trace.jsonl, R3_l3_checks.txt, R3_l3_report.txt,
# R3_l3_clearance.txt, R3_tree_md5_*.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/w8

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/fruits.py \
    scripts/186_w6_report.py > logs/w8/R3_tree_md5_before_l3.txt

BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
PATCH=(FRUIT_SUPPLY_PATCH=1)
TRACE=(FRUIT_BIARM_TRACE=1 FRUIT_BIARM_PARK_TRACE=1)

status=0

check_log() {
    local log=$1 code=$2
    if [ "$code" -ne 0 ]; then
        echo "[r3-l3] FAIL: exit=$code log=$log"; status=1; return 1
    fi
    if [ ! -s "$log" ]; then
        echo "[r3-l3] FAIL: missing or empty log=$log"; status=1; return 1
    fi
    echo "[r3-l3] ok: exit=0 log=$log"
    return 0
}

run() {
    local log=$1 limit=$2 code
    shift 2
    echo "[r3-l3] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[r3-l3] exit=$code $(date +%H:%M:%S) $log"
    check_log "$log" "$code"
}

echo "[r3-l3] battery start $(date +%H:%M:%S)"

run logs/w8/R3_l3_control_trace.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    "${TRACE[@]}" FRUIT_BIARM_TRACE_FILE=logs/w8/R3_l3_control_trace.jsonl
run logs/w8/R3_l3_hot_1.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_HOT_ARM=1
run logs/w8/R3_l3_hot_2_trace.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_HOT_ARM=1 "${TRACE[@]}" \
    FRUIT_BIARM_TRACE_FILE=logs/w8/R3_l3_hot_trace.jsonl

if [ "$status" -ne 0 ]; then
    echo "[r3-l3] battery incomplete: at least one run failed; checks skipped."
    exit 1
fi

echo "[r3-l3] checks (physics [fruit] stream)"
: > logs/w8/R3_l3_checks.txt
echo "== control trace vs logs/w7/20_patch_battery_1.log (no-harm)" \
    | tee -a logs/w8/R3_l3_checks.txt
python3 logs/w4/compare_streams.py --physics-only \
    logs/w8/R3_l3_control_trace.log logs/w7/20_patch_battery_1.log \
    2>&1 | tee -a logs/w8/R3_l3_checks.txt
control_code=${PIPESTATUS[0]}
echo "== determinism: hot_1 vs hot_2_trace" | tee -a logs/w8/R3_l3_checks.txt
python3 logs/w4/compare_streams.py --physics-only \
    logs/w8/R3_l3_hot_1.log logs/w8/R3_l3_hot_2_trace.log \
    2>&1 | tee -a logs/w8/R3_l3_checks.txt
echo "== lever: hot_1 vs control_trace" | tee -a logs/w8/R3_l3_checks.txt
python3 logs/w4/compare_streams.py --physics-only \
    logs/w8/R3_l3_hot_1.log logs/w8/R3_l3_control_trace.log \
    2>&1 | tee -a logs/w8/R3_l3_checks.txt
if [ "$control_code" -ne 0 ]; then
    echo "[r3-l3] WARNING: the control trace does not replay the W7-A patch record"
    status=1
fi

echo "[r3-l3] W6 report"
python3 scripts/186_w6_report.py --label r3-l3 \
    logs/w8/R3_l3_control_trace.log logs/w8/R3_l3_hot_1.log \
    | tee logs/w8/R3_l3_report.txt
report_code=${PIPESTATUS[0]}
[ "$report_code" -ne 0 ] && { echo "[r3-l3] report exit=$report_code"; status=1; }

echo "[r3-l3] clearance"
python3 logs/w8/R3_clearance.py \
    logs/w8/R3_l3_control_trace.jsonl logs/w8/R3_l3_hot_trace.jsonl \
    | tee logs/w8/R3_l3_clearance.txt

echo "[r3-l3] hot-arm accounting (per-arm hold/decision lines)"
grep -c -e "hot hold" logs/w8/R3_l3_hot_1.log \
    | sed 's/^/   hot_1 hold lines: /'
grep -e "hot arm:" logs/w8/R3_l3_hot_1.log | tail -3

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/fruits.py \
    scripts/186_w6_report.py > logs/w8/R3_tree_md5_after_l3.txt
if ! diff -q logs/w8/R3_tree_md5_before_l3.txt logs/w8/R3_tree_md5_after_l3.txt \
        >/dev/null; then
    echo "[r3-l3] WARNING: the tree changed while the battery ran"
    status=1
fi

echo "[r3-l3] battery done $(date +%H:%M:%S) status=$status"
exit "$status"
