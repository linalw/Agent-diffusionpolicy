#!/usr/bin/env bash
# P96 gates: the per-leg motion budgets on every cell (fingerprint recorded, not
# gated), plus the two admissibility replays.
#
#   bash logs/p96/gates.sh
#
# Budgets-only, for P92's reason, which still holds: P87 moved the two-line's
# release clock, so **every** 20-attempt two-line reference in the tree is a
# pre-P87-clock record (`logs/p80/motion_reference_twoline_p80_20.json`,
# `logs/p86/motion_reference_twoline_C6_20.json`). A post-P87 cell therefore
# reads `fingerprint: DIFFERS` against them by construction.
#
# The control proof is the **line-identity replay** against `logs/p94/{T5,T6}.log`
# (PREREG_A2): the control cells must equal that record end to end with the
# phase's own `[ftrace]` row and the P84/P85 sealed diag rows dropped. A
# treatment cell is a moved branch **by construction** (the pre-pose is held for
# 65 ticks on every attempt), so it is budgets-only and its `DIFFERS` is the
# registered expectation.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
rc=0
ref5=logs/p80/motion_reference_twoline_p80_20.json
ref6=logs/p86/motion_reference_twoline_C6_20.json

echo "== G0: the control cells replay their post-P94 record =="
for pair in "C5:logs/p94/T5.log" "C6:logs/p94/T6.log"; do
    cell=${pair%%:*}; ref=${pair#*:}
    if [ ! -s "logs/p96/${cell}.log" ]; then echo "[p96gates] $cell: no log"; rc=1; continue; fi
    if python3 logs/p96/p96_report.py --same "$ref" "logs/p96/${cell}.log" \
            > "logs/p96/${cell}.same"; then
        echo "[p96gates] $cell: IDENTICAL to $ref"
    else
        echo "[p96gates] $cell: DIFFERS from $ref"
        sed -n 1,6p "logs/p96/${cell}.same"
        rc=1
    fi
done
echo

echo "== G5: the motion budgets, every cell (the fingerprint is recorded) =="
# A **control** cell must reproduce its own record's budget rows: `logs/p94/T6.log`
# carries the P86/P87 documented branch leg (leg 12, a 5.9 cm descent at 0.164
# against 0.160), so the control is compared to that, not to a clean sheet. A
# **treatment** cell must be clean (0 over budget) - it is a moved branch, and an
# added over-budget leg would be the phase's.
for t in C5 T5 C6 T6; do
    log="logs/p96/${t}.log"
    if [ ! -s "$log" ]; then echo "[p96gates] $t: no log"; rc=1; continue; fi
    case "$t" in *5) ref=$ref5; rec=logs/p94/T5.log ;; *) ref=$ref6; rec=logs/p94/T6.log ;; esac
    out="logs/p96/${t}.budgets"
    python3 scripts/105_motion_regression.py "$log" --min-success-rate 0.0 \
        --fingerprint "$ref" > "$out" 2>&1
    python3 scripts/105_motion_regression.py "$rec" --min-success-rate 0.0 \
        --fingerprint "$ref" > "logs/p96/${t}.record.budgets" 2>&1
    legs=$(grep -cE "^ +[0-9]+ +[0-9.]+c" "$out" || true)
    over=$(grep -E "^ +[0-9]+ +[0-9.]+c" "$out" | grep -vc " ok$" || true)
    rover=$(grep -E "^ +[0-9]+ +[0-9.]+c" "logs/p96/${t}.record.budgets" | grep -vc " ok$" || true)
    cone=$(grep -oE "worst held-grip cone: [0-9.]+x budget" "$out" | tail -1)
    fp=$(grep -oE "fingerprint: (matches|DIFFERS)" "$out" | tail -1)
    echo "[p96gates] $t: ${legs} descent legs, ${over} over budget (record ${rover}) |" \
         "${cone:-cone n/a} | ${fp:-fp n/a}"
    case "$t" in
        C*)
            if [ "${over:-1}" -gt "${rover:-0}" ]; then
                echo "[p96gates] $t FAIL - the control added an over-budget leg its record does not have"
                grep -E "^ +[0-9]+ +[0-9.]+c" "$out" | grep -v " ok$"
                rc=1
            fi ;;
        *)
            if [ "${over:-1}" -gt 0 ]; then
                echo "[p96gates] $t FAIL - a treatment descent left its budget"
                grep -E "^ +[0-9]+ +[0-9.]+c" "$out" | grep -v " ok$"
                rc=1
            fi ;;
    esac
done
echo "[p96gates] done rc=$rc"
exit "$rc"
