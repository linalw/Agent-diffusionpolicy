#!/usr/bin/env bash
# P102 battery: the tactile patch channel on the SHIPPED cell (one claim/run).
#
#   bash logs/p102/run_p102.sh            # both cells, sequential
#   bash logs/p102/run_p102.sh T5         # a subset
#
# The question (docs/PLATFORM_SURVEY.md §5.1): does a **spatial** tactile - the
# contact patch's centroid moving on the pad - lead the force collapse by enough
# to react, in sim, before any hardware is bought? The tree's 2-scalar channel
# cannot (logs/w5/C_RESULTS.md: 0-3 ticks), so this is the survey's stage (i)
# and its kill criterion is "slip visible >= 10 ticks early, or cnp does not
# fall >= 30 %".
#
# Cells (20 attempts, the shipped two-line default, one run each):
#   T5  seed 5, FRUIT_TACTILE_PATCH=800   (the instrument; everything else unset)
#   T6  seed 6, FRUIT_TACTILE_PATCH=800
#
# The instrumentation is P91/P92's control cell verbatim (FRUIT_MOTION_REPORT
# FRUIT_CYCLE_REPORT FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE) **plus** the new knob,
# so each cell's neutrality proof is a line-identity replay against
# logs/p91/{C5,C6}.log with the phase's own `[tactile]` rows dropped:
#
#   python3 logs/p102/census.py --same logs/p102/T5.log logs/p91/C5.log
#
# 800 ticks is the per-leg row cap: the longest carry leg on this cell is
# ~560 ticks (P73's place legs), so nothing is truncated and `ticks=` on the
# census's per-leg table shows it if one is.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p102

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1 FRUIT_TACTILE_PATCH=800)

if [ ! -s logs/p102/header.txt ]; then
    {
        echo "# P102 header ($(date '+%F %T'))"
        echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
        md5sum src/fruit_sorting/tasks.py src/fruit_sorting/tactile.py \
            src/fruit_sorting/scene.py src/fruit_sorting/assets.py \
            src/fruit_sorting/control.py src/fruit_sorting/bimanual.py \
            configs/motion_reference.json configs/motion_reference_single.json \
            configs/motion_reference_twoline.json \
            scripts/20_pick_place.py scripts/selfcheck.sh \
            scripts/105_motion_regression.py scripts/190_twoline_gate.sh \
            logs/p102/census.py \
            logs/p91/C5.log logs/p91/C6.log
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6>"
        echo "# the change: the default-off FRUIT_TACTILE_PATCH=800 (reporting only)"
    } | tee logs/p102/header.txt
fi

fail=0
note() { echo "[p102] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p102/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "logs/p102/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p102/${tag}.stamps"
    local rc=$?
    note "exit=$rc $(date +%H:%M:%S) $tag"
    if [ "$rc" -ne 0 ] || [ ! -s "$log" ]; then
        note "FAIL $tag (rc=$rc)"; fail=$((fail + 1))
    fi
}

sel=("$@")
run() {
    local tag=$1; shift
    if [ "${#sel[@]}" -eq 0 ] || [[ " ${sel[*]} " == *" $tag "* ]]; then
        claim_run "$tag" "$@"
    fi
}

run T5 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run T6 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
