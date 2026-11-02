#!/usr/bin/env bash
# P103 battery: the **sim-only perfect-detector re-grip** on the shipped cell.
#
#   bash logs/p103/run_p103.sh              # all eight cells, interleaved
#   bash logs/p103/run_p103.sh C5 T5        # a subset
#
# The question (`docs/PLATFORM_SURVEY.md` §5.1, P102 §6): P102 measured that a
# patch tactile sees the loaded slide 21-113 ticks (median 60 = 0.50 s) before
# the pinch is lost, on 6 of 6 escapes, and that all 6 are `cnp` attempts - but
# it did not build the reaction. This battery builds it: trigger on the patch at
# 2.12 mm (5 % of the pad's half-length) **on a seated leg**, act with the tree's
# own shipped slip re-seat, and score the survey's P2 (`cnp` 6 -> <= 4 of 40,
# placed +8 points) and P3 (interval <= +5 %).
#
# Cells (20 attempts, the shipped two-line default, one claim per run):
#   C5  / T5    seed 5     diag only  /  diag + FRUIT_SLIP_REGRIP=2.12
#   C6  / T6    seed 6
#   C101/ T101  seed 101   (fresh - P93's rule: two seeds cannot separate a
#   C202/ T202  seed 202    lever from a branch draw)
#
# `FRUIT_CARRY_DIAG=1` is on **both** arms, so the A/B differs by the knob alone
# (P83's G2 shape). Two proofs make the pair admissible:
#
#   python3 logs/p103/p103_report.py --same logs/p103/C5.log logs/p102/C5.log
#       the archived current-tree control replays line for line -> the A/B is
#       the action, not the instrumentation or the batch
#   scripts/accept.sh                       (knob unset -> byte-identical)
#
# The 2.12 mm is **not** tuned: P102 §3 measured the lead to be insensitive to
# the threshold (1 / 2.12 / 4.25 / 8.49 / 10 mm -> median 61 / 60 / 53 / 46 / 44
# ticks, all six escapes >= 10 ticks at every value), so the 5 %-of-half-length
# value is taken rather than fitted.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p103

ENV_COMMON=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
            FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1)

if [ ! -s logs/p103/header.txt ]; then
    {
        echo "# P103 header ($(date '+%F %T'))"
        echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
        md5sum src/fruit_sorting/tasks.py src/fruit_sorting/tactile.py \
            src/fruit_sorting/scene.py src/fruit_sorting/assets.py \
            src/fruit_sorting/control.py src/fruit_sorting/bimanual.py \
            src/fruit_sorting/fruits.py \
            configs/motion_reference.json configs/motion_reference_single.json \
            configs/motion_reference_twoline.json \
            scripts/20_pick_place.py scripts/selfcheck.sh \
            scripts/105_motion_regression.py scripts/190_twoline_gate.sh \
            logs/p103/PREREG.md logs/p103/p103_report.py \
            logs/p102/C5.log logs/p102/C6.log logs/p102/T5.log logs/p102/T6.log \
            logs/p98/accept_revert.log
        echo "# cells: ${ENV_COMMON[*]} ATTEMPTS=20 SEED=<5|6|101|202>"
        echo "# treatment adds: FRUIT_SLIP_REGRIP=2.12"
        echo "# PREREG md5: $(cut -d' ' -f1 logs/p103/PREREG.md5)"
    } | tee logs/p103/header.txt
fi

fail=0
note() { echo "[p103] $*"; }

claim_run() {  # claim_run <tag> <env...>
    local tag=$1; shift
    local log="logs/p103/${tag}.log"
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "logs/p103/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "$log" "logs/p103/${tag}.stamps"
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

# Interleaved by seed, the C/T order alternating (P77's convention: a monotone
# drift over a ~45 min battery cannot masquerade as an arm effect).
run C5   "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=5
run T5   "${ENV_COMMON[@]}" FRUIT_SLIP_REGRIP=2.12 ATTEMPTS=20 SEED=5
run T6   "${ENV_COMMON[@]}" FRUIT_SLIP_REGRIP=2.12 ATTEMPTS=20 SEED=6
run C6   "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=6
run C101 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=101
run T101 "${ENV_COMMON[@]}" FRUIT_SLIP_REGRIP=2.12 ATTEMPTS=20 SEED=101
run T202 "${ENV_COMMON[@]}" FRUIT_SLIP_REGRIP=2.12 ATTEMPTS=20 SEED=202
run C202 "${ENV_COMMON[@]}" ATTEMPTS=20 SEED=202

note "battery done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
