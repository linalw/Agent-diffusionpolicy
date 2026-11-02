#!/usr/bin/env bash
# P94 battery: the `_gripper_offset` command-jump fix (one claim per run).
#
#   bash logs/p94/run_p94.sh              # all cells, sequential
#   bash logs/p94/run_p94.sh N5 T5        # a subset (the tree check first)
#   bash logs/p94/run_p94.sh P5           # the post-flip replay (only if it ships)
#
# PREREG: logs/p94/PREREG.md (md5 in logs/p94/PREREG.md5), pinned before any run.
#
# Cells (20 attempts, the shipped two-line default, one run each):
#   N5    seed 5,   unset                          the tree check == logs/p92/C5.log
#   T5    seed 5,   FRUIT_CARRY_OFFSET_MAX=0.20    the fix
#   T6    seed 6,   FRUIT_CARRY_OFFSET_MAX=0.20    the fix
#   T101  seed 101, FRUIT_CARRY_OFFSET_MAX=0.20    the fix (fresh seed, P93)
#   T202  seed 202, FRUIT_CARRY_OFFSET_MAX=0.20    the fix (fresh seed, P93)
#   P5    seed 5,   unset, AFTER the default flip  must replay T5
#
# The instrumentation is P92/P93's four cells verbatim (`FRUIT_MOTION_REPORT
# FRUIT_CYCLE_REPORT FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`) so the tree check, the
# leg census and the class census are read on the same rows. Wall via
# logs/p80/stamp.py, one claim via scripts/154_claim_run.sh. Nothing here writes
# src/, configs/, datasets/ or a checkpoint; the only difference between a
# control-record replay and a treatment cell is the one env value, which the
# `[diag] carry-assist ... jaw_target=` row shows on every leg it acts on.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p94

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1)

if [ ! -s logs/p94/header.txt ]; then
    {
        echo "# P94 header ($(date '+%F %T'))"
        echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
        md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
            src/fruit_sorting/bimanual.py src/fruit_sorting/fruits.py \
            src/fruit_sorting/scene.py src/fruit_sorting/control.py \
            src/fruit_sorting/conveyor.py src/fruit_sorting/assets.py \
            configs/motion_reference.json configs/motion_reference_single.json \
            configs/motion_reference_twoline.json \
            scripts/20_pick_place.py scripts/accept.sh scripts/selfcheck.sh \
            scripts/190_twoline_gate.sh scripts/105_motion_regression.py \
            scripts/154_claim_run.sh logs/p80/one_run.sh logs/p80/stamp.py \
            logs/p80/p80lib.py logs/p92/census.py logs/p94/PREREG.md \
            logs/p94/census.py logs/p94/run_p94.sh
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6|101|202> [FRUIT_CARRY_OFFSET_MAX=0.20]"
        echo "# the change: tasks.parse_carry_offset_max + _carry's assisted branch falls"
        echo "#   back to the coherent command (centre) when the jaw hand's reading is"
        echo "#   above the bound (0.20 m = FRUIT_RELEASE_ARM_TRACK's own pad/arm bound)"
    } | tee logs/p94/header.txt
fi

fail=0
note() { echo "[p94] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p94/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=2400 scripts/154_claim_run.sh "logs/p94/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p94/${tag}.stamps"
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

run N5   "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run T5   "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5   FRUIT_CARRY_OFFSET_MAX=0.20
run T6   "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6   FRUIT_CARRY_OFFSET_MAX=0.20
run T101 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=101 FRUIT_CARRY_OFFSET_MAX=0.20
run T202 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=202 FRUIT_CARRY_OFFSET_MAX=0.20
run P5   "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
