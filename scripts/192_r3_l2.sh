#!/usr/bin/env bash
# W8-R3 L2 battery: the adaptive selection lead on the W6-B patch scenario.
#
#   nohup bash scripts/192_r3_l2.sh > logs/w8/R3_l2_driver.log 2>&1 &
#
# Scenario (identical to scripts/187_w6_battery.sh / logs/w6/SPEC.md):
#   FRUIT_SUPPLY_PATCH=1, ATTEMPTS=20, SEED=5, HEADLESS=1, Tier A solo via
#   scripts/154_claim_run.sh, two-line opt-in (FRUIT_BIARM=1
#   FRUIT_BIARM_TWOLINE=1), balanced mix (the two-line patch default).
#
# Configs (all two-line, all carry FRUIT_BIARM_SELECT_DIAG=1 for the mechanism):
#   control = no lever; expect physics-identical to logs/w7/20_patch_battery_1.log
#             (the W7-A default record) with the reporting lines stripped
#   adapt   = FRUIT_BIARM_SELECT_LEAD_ADAPT=1  (measured per-arm EWMA setup)
#   tight   = FRUIT_BIARM_SELECT_LEAD_S=1.0    (the plumbed explicit override:
#             the shipped floor is 1.5 s, so this binds a shorter lead)
#   * the second run of each lever config carries FRUIT_BIARM_TRACE=1 (the
#     clearance reading); the pair counts as the determinism proof only if the
#     physics [fruit] streams are identical (compare_streams drops the trace
#     lines), otherwise the trace run is a mechanism run and a plain repeat
#     takes its place.
#
# Outputs: logs/w8/R3_l2_control.log, R3_l2_adapt_{1,2_trace}.log,
# R3_l2_tight_{1,2_trace}.log, R3_l2_checks.txt (determinism + control-vs-W7A),
# R3_l2_report.txt (186), R3_l2_mech.txt (R3_lead_analysis), R3_tree_md5_*.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/w8

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/fruits.py \
    scripts/186_w6_report.py > logs/w8/R3_tree_md5_before.txt

BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
PATCH=(FRUIT_SUPPLY_PATCH=1)
DIAG=(FRUIT_BIARM_SELECT_DIAG=1)

status=0

check_log() {  # check_log <log> <exit-code>
    local log=$1 code=$2
    if [ "$code" -ne 0 ]; then
        echo "[r3-l2] FAIL: exit=$code log=$log"
        status=1
        return 1
    fi
    if [ ! -s "$log" ]; then
        echo "[r3-l2] FAIL: missing or empty log=$log (exit=0 but no output)"
        status=1
        return 1
    fi
    echo "[r3-l2] ok: exit=0 log=$log"
    return 0
}

run() {  # run <log> <run-limit-s> <env...>
    local log=$1 limit=$2 code
    shift 2
    echo "[r3-l2] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[r3-l2] exit=$code $(date +%H:%M:%S) $log"
    check_log "$log" "$code"
}

strip_l2() {  # drop the W8-R3 L2 pure-reporting lines for cross-config compares
    grep -v -e "select diag" -e "lead diag" "$1" > "$2"
}

echo "[r3-l2] battery start $(date +%H:%M:%S)"

# --- the control (reporting only; the current two-line default) ------------ #
run logs/w8/R3_l2_control.log 7200 "${TWO[@]}" "${PATCH[@]}" "${DIAG[@]}"

# --- the adaptive lead ------------------------------------------------------ #
run logs/w8/R3_l2_adapt_1.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_SELECT_LEAD_ADAPT=1
run logs/w8/R3_l2_adapt_2_trace.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_SELECT_LEAD_ADAPT=1 FRUIT_BIARM_TRACE=1

# --- the explicit tight floor (the plumbed override) ------------------------ #
run logs/w8/R3_l2_tight_1.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_SELECT_LEAD_S=1.0 "${DIAG[@]}"
run logs/w8/R3_l2_tight_2_trace.log 7200 "${TWO[@]}" "${PATCH[@]}" \
    FRUIT_BIARM_SELECT_LEAD_S=1.0 "${DIAG[@]}" FRUIT_BIARM_TRACE=1

if [ "$status" -ne 0 ]; then
    echo "[r3-l2] battery incomplete: at least one run failed; checks skipped."
    exit 1
fi

echo "[r3-l2] checks (physics [fruit] stream; L2 reporting lines stripped)"
: > logs/w8/R3_l2_checks.txt
{
    echo "== determinism: adapt_1 vs adapt_2_trace"
    python3 logs/w4/compare_streams.py --physics-only \
        logs/w8/R3_l2_adapt_1.log logs/w8/R3_l2_adapt_2_trace.log
    echo "== determinism: tight_1 vs tight_2_trace"
    python3 logs/w4/compare_streams.py --physics-only \
        logs/w8/R3_l2_tight_1.log logs/w8/R3_l2_tight_2_trace.log
} | tee -a logs/w8/R3_l2_checks.txt

# cross-config: strip the reporting lines, then compare
mkdir -p /tmp/opencode
strip_l2 logs/w8/R3_l2_control.log /tmp/opencode/r3_l2_control.strip
strip_l2 logs/w8/R3_l2_adapt_1.log /tmp/opencode/r3_l2_adapt_1.strip
strip_l2 logs/w8/R3_l2_tight_1.log /tmp/opencode/r3_l2_tight_1.strip
echo "== no-harm: control (reporting stripped) vs logs/w7/20_patch_battery_1.log"
python3 logs/w4/compare_streams.py --physics-only \
    /tmp/opencode/r3_l2_control.strip logs/w7/20_patch_battery_1.log \
    | tee -a logs/w8/R3_l2_checks.txt
control_code=${PIPESTATUS[0]}
echo "== lever: adapt vs control (reporting stripped)"
python3 logs/w4/compare_streams.py --physics-only \
    /tmp/opencode/r3_l2_adapt_1.strip /tmp/opencode/r3_l2_control.strip \
    | tee -a logs/w8/R3_l2_checks.txt
echo "== lever: tight vs control (reporting stripped)"
python3 logs/w4/compare_streams.py --physics-only \
    /tmp/opencode/r3_l2_tight_1.strip /tmp/opencode/r3_l2_control.strip \
    | tee -a logs/w8/R3_l2_checks.txt

if [ "$control_code" -ne 0 ]; then
    echo "[r3-l2] WARNING: the control does not replay the W7-A patch record"
    status=1
fi

echo "[r3-l2] W6 report"
python3 scripts/186_w6_report.py --label r3-l2 \
    logs/w8/R3_l2_control.log logs/w8/R3_l2_adapt_1.log \
    logs/w8/R3_l2_tight_1.log | tee logs/w8/R3_l2_report.txt
report_code=${PIPESTATUS[0]}
echo "[r3-l2] report exit=$report_code"
[ "$report_code" -ne 0 ] && status=1

echo "[r3-l2] L2 mechanism readout"
python3 logs/w8/R3_lead_analysis.py \
    logs/w8/R3_l2_control.log logs/w8/R3_l2_adapt_1.log \
    logs/w8/R3_l2_tight_1.log | tee logs/w8/R3_l2_mech.txt

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/fruits.py \
    scripts/186_w6_report.py > logs/w8/R3_tree_md5_after.txt
if ! diff -q logs/w8/R3_tree_md5_before.txt logs/w8/R3_tree_md5_after.txt \
        >/dev/null; then
    echo "[r3-l2] WARNING: the tree changed while the battery ran"
    status=1
fi

echo "[r3-l2] battery done $(date +%H:%M:%S) status=$status"
exit "$status"
