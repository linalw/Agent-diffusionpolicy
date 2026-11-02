#!/usr/bin/env bash
# P92 gates: the per-leg motion budgets on every cell, with the fingerprint read
# recorded rather than gated.
#
#   bash logs/p92/gates.sh
#
# Why budgets-only here. P87 moved the two-line's release clock, so **every
# 20-attempt two-line reference in the tree is a pre-P87-clock record**
# (`logs/p80/motion_reference_twoline_p80_20.json` and
# `logs/p86/motion_reference_twoline_C6_20.json` were both written with the trim
# off). A post-P87 cell therefore reads `fingerprint: DIFFERS` against them by
# construction - P91 recorded the same clause (`logs/p91/RESULTS.md`, its
# gates). The control proof for this phase is not the fingerprint but the
# **line-identity replay** against `logs/p91/C5.log` / `C6.log`, which
# `p92_report.py` section 5 prints (G5).
#
# A treatment cell is a *different scenario* (the lateral band moved), so its
# fingerprint is DIFFERS by construction too and only the budgets can gate it.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
rc=0
ref5=logs/p80/motion_reference_twoline_p80_20.json
ref6=logs/p86/motion_reference_twoline_C6_20.json
for t in C5 T5 C6 T6 R5 R6; do
    log="logs/p92/${t}.log"
    if [ ! -s "$log" ]; then echo "[p92gates] $t: no log"; rc=1; continue; fi
    case "$t" in *5) ref=$ref5 ;; *) ref=$ref6 ;; esac
    out="logs/p92/${t}.budgets"
    python3 scripts/105_motion_regression.py "$log" --min-success-rate 0.0 \
        --fingerprint "$ref" > "$out" 2>&1
    legs=$(grep -cE "^ +[0-9]+ +[0-9.]+c" "$out" || true)
    over=$(grep -E "^ +[0-9]+ +[0-9.]+c" "$out" | grep -vc " ok$" || true)
    cone=$(grep -oE "worst held-grip cone: [0-9.]+x budget" "$out" | tail -1)
    lurch=$(grep -oE "lurch [0-9.]+ of [0-9.]+" "$out" | tail -1)
    fp=$(grep -oE "fingerprint: (matches|DIFFERS)" "$out" | tail -1)
    echo "[p92gates] $t: ${legs} descent legs, ${over} over budget | ${cone:-cone n/a} | ${fp:-fp n/a}"
    if [ "${over:-1}" -gt 0 ]; then
        echo "[p92gates] $t FAIL - a descent left its budget"
        grep -E "^ +[0-9]+ +[0-9.]+c" "$out" | grep -v " ok$"
        rc=1
    fi
done
echo "[p92gates] done rc=$rc (the fingerprint clause is recorded above, never gated:"
echo "  no 20-attempt post-P87 reference exists in the tree)"
exit "$rc"
