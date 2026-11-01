#!/usr/bin/env bash
# P89 battery: the lift raise as a two-line-scoped default (one claim per run).
#
#   bash logs/p89/run_p89.sh                 # all four cells, sequential
#   bash logs/p89/run_p89.sh C5 T5           # a subset (the admissibility pair first)
#
# PREREG: logs/p89/PREREG.md (md5 in logs/p89/PREREG.md5), pinned before any run.
#
# Cells (20 attempts, the shipped two-line default, one run each):
#   C5  seed 5, FRUIT_SPEED_LIFT=0   the shipped 0.30/1.0 cap == P88's T5
#   T5  seed 5, unset                the scoped default (P44's S3-v, 0.37/1.0)
#   C6  seed 6, FRUIT_SPEED_LIFT=0   == P88's T6
#   T6  seed 6, unset
#
# The instrumentation is P88's four cells verbatim (`FRUIT_MOTION_REPORT
# FRUIT_CYCLE_REPORT FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`) - identical on both
# arms - which is what makes G0 (`--same` against P88's logs, the three profile
# rows dropped) admissible. The release cell is unset everywhere (its own
# two-line default) and the place cell is unset (off by default), so the
# comparison is the lift alone. Wall via logs/p80/stamp.py, one claim via
# scripts/154_claim_run.sh. Nothing here writes src/, configs/, datasets/ or a
# checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p89

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1)

if [ ! -s logs/p89/header.txt ]; then
    {
        echo "# P89 header ($(date '+%F %T'))"
        echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
        md5sum src/fruit_sorting/tasks.py src/fruit_sorting/bimanual.py \
            src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
            src/fruit_sorting/control.py src/fruit_sorting/conveyor.py \
            src/fruit_sorting/assets.py src/fruit_sorting/rl_env.py \
            configs/motion_reference.json configs/motion_reference_single.json \
            configs/motion_reference_twoline.json \
            scripts/20_pick_place.py scripts/accept.sh \
            scripts/190_twoline_gate.sh scripts/105_motion_regression.py \
            scripts/selfcheck.sh scripts/154_claim_run.sh \
            logs/p80/one_run.sh logs/p80/stamp.py logs/p80/p80lib.py \
            logs/p80/motion_reference_twoline_p80_20.json \
            logs/p86/motion_reference_twoline_C6_20.json \
            logs/p88/T5.log logs/p88/T6.log \
            logs/p89/PREREG.md logs/p89/PREREG.md5 logs/p89/p89_report.py
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6> [FRUIT_SPEED_LIFT=0]"
        echo "# LIFT_TWO_LINE_DEFAULT (battery form): $(grep -m1 '^LIFT_TWO_LINE_DEFAULT = ' src/fruit_sorting/tasks.py)"
    } | tee logs/p89/header.txt
fi

fail=0
note() { echo "[p89] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p89/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=2400 scripts/154_claim_run.sh "logs/p89/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p89/${tag}.stamps"
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

run C5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5 FRUIT_SPEED_LIFT=0
run T5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run C6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6 FRUIT_SPEED_LIFT=0
run T6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
