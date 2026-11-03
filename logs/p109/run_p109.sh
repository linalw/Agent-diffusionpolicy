#!/usr/bin/env bash
# P109 - the descent margin (0.15 / 0.075 / 0), its cells, the acceptance A/B
# and the phase's gates.
#
#   bash logs/p109/run_p109.sh battery   # the 12 cells (two streams)
#   bash logs/p109/run_p109.sh accept    # the acceptance A/B (unset vs M1)
#   bash logs/p109/run_p109.sh report    # the endpoint table + the decision rule
#   bash logs/p109/run_p109.sh gates     # the no-harm / replay / budget checks
#
# The values are the ones `logs/p109/PREREG.md` (md5 192a0c1b..., `PREREG.md5`)
# pinned: three arms - the shipped 0.15 (M0, unset), 0.075 (M05, the dose axis)
# and 0 (M1) - four seeds, 20 attempts, the scripted single arm.
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT=logs/p109
ATTEMPTS=${ATTEMPTS:-20}
SEEDS_A=${SEEDS_A:-"5 101"}
SEEDS_B=${SEEDS_B:-"6 202"}

what=${1:-report}

if [ "$what" = "battery" ]; then
    # Two streams, one GPU (the sim is not GPU bound - P108 measured 32 %
    # utilisation, 4.4 GB of 32 GB).  Disjoint files, nothing interleaved.
    for seed in $SEEDS_A; do bash "${OUT}/cells.sh" "M0:${seed}" "M05:${seed}" "M1:${seed}"; done &
    for seed in $SEEDS_B; do bash "${OUT}/cells.sh" "M0:${seed}" "M05:${seed}" "M1:${seed}"; done &
    wait
fi

if [ "$what" = "accept" ]; then
    # The catch's own gate.  The shipped session is the two-line (P85), so this
    # is also the one place the phase reads the two-line's catch under the knob.
    # M0 must replay this tree's branch: 8/10 + `fingerprint: matches 30fb99f8`.
    echo "=== acceptance, margin unset (the shipped 0.15) ==="
    ACCEPT_LOG="${OUT}/accept_m0.log" scripts/accept.sh > "${OUT}/accept_m0.driver" 2>&1 || true
    grep -E "\[stats\]|\[biarm\] two-line scheduler:|fingerprint|PASS|FAIL|budget|over" \
        "${OUT}/accept_m0.driver" | tail -12
    echo
    echo "=== acceptance, M1 (FRUIT_DYNAMIC_DESCEND_MARGIN=0) ==="
    # Its fingerprint DIFFERS by construction (the knob moves every attempt's
    # arrival), so this arm is gated on the rate + the budgets (PREREG section 5).
    FRUIT_DYNAMIC_DESCEND_MARGIN=0 SKIP_SELFCHECK=1 ACCEPT_LOG="${OUT}/accept_m1.log" \
        scripts/accept.sh > "${OUT}/accept_m1.driver" 2>&1 || true
    grep -E "\[stats\]|\[biarm\] two-line scheduler:|fingerprint|PASS|FAIL|budget|over" \
        "${OUT}/accept_m1.driver" | tail -12
fi

if [ "$what" = "report" ]; then
    python3 "${OUT}/p109_report.py" | tee "${OUT}/p109_report.txt"
fi

if [ "$what" = "gates" ]; then
    echo "=== G0 the tree is inert: M0 (this batch) vs the P108 record, [cycle] dropped ==="
    python3 "${OUT}/p109_report.py" --same "${OUT}/M0_s5.log" logs/p108/S_s5.log || true
    python3 "${OUT}/p109_report.py" --same "${OUT}/M0_s6.log" logs/p108/S_s6.log || true
    echo
    echo "=== G1 the acceptance's unset arm is this tree's branch ==="
    grep -E "\[stats\]|fingerprint|PASS|FAIL" "${OUT}/accept_m0.driver" | tail -6 || true
    echo
    echo "=== G2 budgets per cell (105, the rate floor disabled - the count is not this gate's) ==="
    for arm in M0 M05 M1; do
        for seed in 5 6 101 202; do
            log="${OUT}/${arm}_s${seed}.log"
            [ -f "${log}" ] || continue
            printf '%-10s ' "${arm}/s${seed}"
            python3 scripts/105_motion_regression.py "${log}" --min-success-rate 0 \
                2>&1 | grep -E "budget|over|fingerprint|PASS|FAIL" | tr '\n' ' ' | cut -c1-160
            echo
        done
    done
    echo
    echo "=== G3 selfcheck + the data checks ==="
    scripts/selfcheck.sh | tail -3
    python3 scripts/106_index_audit.py | tail -2
    python3 scripts/107_collect_merge_test.py | tail -2
fi
