#!/usr/bin/env bash
# P96 phase-2 battery: the pre-leg pad census, count/class, interval and landing
# on the same four cells (one claim per run).
#
#   bash logs/p96/run_p96.sh            # all four cells
#   bash logs/p96/run_p96.sh C5 T5      # a subset
#
# PREREG: logs/p96/PREREG.md (md5 in logs/p96/PREREG.md5), + logs/p96/PREREG_A1.md.
#
# Cells (20 attempts each, the shipped two-line default):
#   C5  seed 5, FRUIT_BIARM_PREPOSE_CLEAR=0   the pre-P96 pre-pose (replay target
#   C6  seed 6, FRUIT_BIARM_PREPOSE_CLEAR=0   logs/p92/{C5,C6}.log)
#   T5  seed 5, FRUIT_BIARM_PREPOSE_CLEAR=1   the clearance pre-pose (moved branch)
#   T6  seed 6, FRUIT_BIARM_PREPOSE_CLEAR=1
#
# Instrumentation is identical in all four, so the census, the count, the class
# ledger, the interval and the landing all come from one cell each - the cells
# that can read the invariant are the cells the count is read on. P95 proved the
# trace read set branch-neutral (fruit-only 970/970; the two-arm link read
# 970/970 / 974/974 on the same seeds), P83 the carry tracker (D5 = C5,
# 710/710) and P86 the place trace, so the stack's admissibility is checked per
# cell (`pg_census.py --admissible`, `p96_report.py --same`) rather than assumed.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p96

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1
            FRUIT_FRUIT_TRACE=2500 FRUIT_FRUIT_TRACE_ARM=1)

if [ ! -s logs/p96/header.txt ]; then
    {
        echo "# P96 header ($(date '+%F %T'))"
        echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
        md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
            src/fruit_sorting/bimanual.py src/fruit_sorting/fruits.py \
            src/fruit_sorting/scene.py src/fruit_sorting/assets.py \
            configs/motion_reference.json configs/motion_reference_single.json \
            configs/motion_reference_twoline.json \
            scripts/20_pick_place.py scripts/run.sh scripts/selfcheck.sh \
            scripts/190_twoline_gate.sh scripts/105_motion_regression.py \
            scripts/154_claim_run.sh scripts/40_collect_demos.py \
            logs/p80/one_run.sh logs/p80/stamp.py \
            logs/p96/PREREG.md logs/p96/PREREG_A1.md logs/p96/run_p96.sh
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6> PREPOSE_CLEAR=<0|1>"
        echo "# the change: tasks.prepose_clear_resolution + _prepare_two_line_stations'"
        echo "#   clearance solve (default off = the pre-P96 path)"
    } | tee logs/p96/header.txt
fi

fail=0
note() { echo "[p96] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p96/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "logs/p96/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p96/${tag}.stamps"
    local rc=$?
    note "exit=$rc $(date +%H:%M:%S) $tag"
    if [ "$rc" -ne 0 ] || [ ! -s "$log" ]; then
        note "FAIL $tag (rc=$rc)"; fail=$((fail + 1))
    fi
}

sel=("$@")
run() {  # run <tag> <env...>
    local tag=$1; shift
    if [ "${#sel[@]}" -eq 0 ] || [[ " ${sel[*]} " == *" $tag "* ]]; then
        claim_run "$tag" "$@"
    fi
}

run C5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5 FRUIT_BIARM_PREPOSE_CLEAR=0 \
       FRUIT_FRUIT_TRACE_DIR=logs/p96/tr5c
run T5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5 FRUIT_BIARM_PREPOSE_CLEAR=1 \
       FRUIT_FRUIT_TRACE_DIR=logs/p96/tr5t
run C6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6 FRUIT_BIARM_PREPOSE_CLEAR=0 \
       FRUIT_FRUIT_TRACE_DIR=logs/p96/tr6c
run T6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6 FRUIT_BIARM_PREPOSE_CLEAR=1 \
       FRUIT_FRUIT_TRACE_DIR=logs/p96/tr6t

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
