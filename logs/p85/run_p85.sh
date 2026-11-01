#!/usr/bin/env bash
# P85 battery: the flip's own evidence (one claim per run, sequential).
#
#   nohup bash logs/p85/run_p85.sh > logs/p85/battery_driver.log 2>&1 &
#
# PREREG: logs/p85/PREREG.md (md5 in logs/p85/PREREG.md5) and
#         logs/p85/PREREG_ACCEL.md (md5 in PREREG_ACCEL.md5), both pinned before
#         any run here.
#
# Arms:
#   A1  accept10   the acceptance scenario, 10 attempts, SHIPPED DEFAULT (two-line)
#   A2  single10   the same, FRUIT_BIARM=0 (the pre-P85 restore)
#   C5  base20_s5  20 attempts, seed 5, shipped default   (P80 T20 replay)
#   U5  speed20_s5 the union on the default, seed 5         (accel treatment)
#   C6  base20_s6  20 attempts, seed 6, shipped default   (P80 T6 replay)
#   U6  speed20_s6 the union on the default, seed 6
#
# Every cell is wall-stamped with `logs/p80/stamp.py` (the P80/P82 wall clock) and
# keeps its plain log byte-identical to a plain redirect. Nothing here writes
# src/, configs/, datasets/ or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p85

#: The gate cells carry **exactly** `scripts/accept.sh`'s instrumentation, so the
#: re-recorded reference (and the single-arm archive comparison) is produced by
#: the shipped command, not by a longer report set.
GATE=(HEADLESS=1 FRUIT_MOTION_REPORT=1)
RATE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1)
#: The carry tracker (`[carry]` rows) is this phase's instrument for E3's slip
#: guard. It is run-neutral on the two-line - P84's D5/D6 replay `logs/p80/T20`
#: and `T6` at 865/865 and 814/814 `[fruit]` lines with exactly these rows
#: dropped (`logs/p84/RESULTS.md` §1) - so the T20/T6 comparison below drops
#: them (and the one new scheduler banner) instead of giving up the read.
DIAG=(FRUIT_CARRY_DIAG=1)
SPEED=(FRUIT_SPEED_ALL=1)

{
    echo "# P85 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/bimanual.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/assets.py src/fruit_sorting/conveyor.py \
        src/fruit_sorting/scene.py src/fruit_sorting/control.py \
        configs/motion_reference.json configs/motion_reference_single.json \
        configs/motion_reference_twoline.json \
        scripts/20_pick_place.py scripts/40_collect_demos.py scripts/accept.sh \
        scripts/190_twoline_gate.sh scripts/105_motion_regression.py \
        scripts/246_p85_selftest.py scripts/selfcheck.sh \
        logs/p85/PREREG.md logs/p85/PREREG_ACCEL.md
    echo "# gate cells: ${GATE[*]}  (accept.sh own set)"
    echo "# 20-attempt cells: ${RATE[*]} + ${DIAG[*]}"
    echo "# A1/A2 add ATTEMPTS=10; A2 adds FRUIT_BIARM=0; U* add ${SPEED[*]}"
} | tee logs/p85/header.txt

fail=0
note() { echo "[p85] $*"; }

claim_run() {  # claim_run <tag> <limit> <env...>
    local tag=$1 limit=$2; shift 2
    local log="logs/p85/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "logs/p85/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p85/${tag}.stamps"
    local rc=$?
    note "exit=$rc $(date +%H:%M:%S) $tag"
    if [ "$rc" -ne 0 ] || [ ! -s "$log" ]; then
        note "FAIL $tag (rc=$rc)"; fail=$((fail + 1))
    fi
}

claim_run accept10 1800 "${GATE[@]}" ATTEMPTS=10
claim_run single10 1800 "${GATE[@]}" ATTEMPTS=10 FRUIT_BIARM=0
claim_run base20_s5 2400 "${RATE[@]}" ATTEMPTS=20 SEED=5 "${DIAG[@]}"
claim_run speed20_s5 2400 "${RATE[@]}" ATTEMPTS=20 SEED=5 "${DIAG[@]}" "${SPEED[@]}"
claim_run base20_s6 2400 "${RATE[@]}" ATTEMPTS=20 SEED=6 "${DIAG[@]}"
claim_run speed20_s6 2400 "${RATE[@]}" ATTEMPTS=20 SEED=6 "${DIAG[@]}" "${SPEED[@]}"

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
