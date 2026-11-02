#!/usr/bin/env bash
# P99 census cell: the candidate set the two-line selector saw at every slot.
#
#   bash logs/p99/run_p99.sh            # both seeds
#   bash logs/p99/run_p99.sh C5         # a subset
#
# Two 20-attempt cells on the shipped default, one per seed. The instrumentation
# is P94's four knobs verbatim (`FRUIT_MOTION_REPORT FRUIT_CYCLE_REPORT
# FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`) so the replay target is the SAME-KNOB
# record (`logs/p94/{T5,T6}.log`), plus two reporting-only additions:
#
#   FRUIT_BIARM_PARK_TRACE=1  the attempt-end timestamp and the park gate split
#                             (`park wait start` / `moving` / `done`). P84 proved
#                             it line-neutral (D5 = logs/p80/T20.log 865/865).
#   FRUIT_BED_DIAG=2           P99: one row per live fruit with its grade and
#                             `along`, plus the selector floor at that decision.
#                             `=1` (the shipped P33 row) is unchanged; `=2` adds
#                             the per-fruit rows after it.
#
# Both are pure reporting: neither touches `select_target`, the floor, the aim
# or any control input. The neutrality proof is the replay against
# `logs/p94/{T5,T6}.log` with the instrument's own rows dropped
# (`logs/p99/census.py --same`).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p99

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1
            FRUIT_BIARM_PARK_TRACE=1 FRUIT_BED_DIAG=2)

if [ ! -s logs/p99/header.txt ]; then
    {
        echo "# P99 header ($(date '+%F %T'))"
        echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
        md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
            src/fruit_sorting/bimanual.py src/fruit_sorting/fruits.py \
            src/fruit_sorting/scene.py src/fruit_sorting/assets.py \
            src/fruit_sorting/control.py src/fruit_sorting/conveyor.py \
            configs/motion_reference.json configs/motion_reference_single.json \
            configs/motion_reference_twoline.json \
            scripts/20_pick_place.py scripts/run.sh scripts/selfcheck.sh \
            scripts/190_twoline_gate.sh scripts/105_motion_regression.py \
            scripts/154_claim_run.sh \
            logs/p80/one_run.sh logs/p80/stamp.py \
            logs/p99/run_p99.sh logs/p99/census.py
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6>"
        echo "# the change: tasks._biarm_bed_census's FRUIT_BED_DIAG=2 detail rows"
        echo "#   (reporting only; =1 and unset are byte-unchanged)"
    } | tee logs/p99/header.txt
fi

fail=0
note() { echo "[p99] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p99/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "logs/p99/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p99/${tag}.stamps"
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

run C5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run C6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
