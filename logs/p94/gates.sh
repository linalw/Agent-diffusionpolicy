#!/usr/bin/env bash
# P94 gates: the per-leg motion budgets on every cell of the phase.
#
#   bash logs/p94/gates.sh
#
# The fingerprint clause is **recorded, never gated**: every 20-attempt two-line
# reference in the tree predates P87's release clock, so every post-P87 cell -
# the controls included - reads `DIFFERS` by construction (P91/P92/P93's own
# convention, restated in `logs/p93/gates.sh`). What gates a cell is the per-leg
# motion budget plus the `190` scenario pin.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
rc=0
ref5=logs/p80/motion_reference_twoline_p80_20.json
ref6=logs/p86/motion_reference_twoline_C6_20.json
for t in C5 T5 C6 T6 C101 T101 C202 T202 N5 P5; do
    case "$t" in
        C5|C6) log="logs/p92/${t}.log" ;;
        C101|C202) log="logs/p93/${t}.log" ;;
        *) log="logs/p94/${t}.log" ;;
    esac
    if [ ! -s "$log" ]; then echo "[p94gates] $t: no log"; continue; fi
    case "$t" in *5|N5|P5) ref=$ref5 ;; *6|C6|T6) ref=$ref6 ;; *) ref= ;; esac
    out="logs/p94/${t}.budgets"
    if [ -n "$ref" ]; then
        python3 scripts/105_motion_regression.py "$log" --min-success-rate 0.0 \
            --fingerprint "$ref" > "$out" 2>&1
    else
        python3 scripts/105_motion_regression.py "$log" --min-success-rate 0.0 \
            > "$out" 2>&1
    fi
    legs=$(grep -cE "^ +[0-9]+ +[0-9.]+c" "$out" || true)
    over=$(grep -E "^ +[0-9]+ +[0-9.]+c" "$out" | grep -vc " ok$" || true)
    cone=$(grep -oE "worst held-grip cone: [0-9.]+x budget" "$out" | tail -1)
    lurch=$(grep -oE "lurch [0-9.]+ of [0-9.]+" "$out" | tail -1)
    fp=$(grep -oE "fingerprint: (matches|DIFFERS)" "$out" | tail -1)
    echo "[p94gates] $t: ${legs} descent legs, ${over} over budget | ${cone:-cone n/a} | ${fp:-fp n/a}"
    if [ "${over:-1}" -gt 0 ]; then
        echo "[p94gates] $t: a descent left its budget (recorded, not re-tuned - AGENTS 2)"
        grep -E "^ +[0-9]+ +[0-9.]+c" "$out" | grep -v " ok$"
        rc=1
    fi
done
echo "[p94gates] done rc=$rc (the fingerprint clause is recorded above, never gated:"
echo "  no 20-attempt post-P87 reference exists in the tree)"
exit "$rc"
