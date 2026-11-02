#!/usr/bin/env bash
# P93 gates: the per-leg motion budgets on every cell of the phase.
#
#   bash logs/p93/gates.sh
#
# The two-line scenario gate (`scripts/190_twoline_gate.sh`) is the canonical
# form, but its `--fingerprint` clause is **recorded, not gated** on this tree:
# every 20-attempt two-line reference predates P87's release clock, so every
# post-P87 cell - the controls included - reads `DIFFERS` by construction (P91
# and P92 both recorded that clause). What gates a cell here is the per-leg
# motion budget, exactly as P92's `gates.sh` did, plus the `190` scenario pin.
#
# Seeds 5 and 6 keep P92's per-seed 20-attempt references so the C cells'
# fingerprint clause is comparable across phases. Seeds 101 and 202 have **no**
# 20-attempt reference on the tree, and P84's rule applies: a fresh seed is its
# own scenario, so its fingerprint is read against nothing and only the budgets
# gate it.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
rc=0
ref5=logs/p80/motion_reference_twoline_p80_20.json
ref6=logs/p86/motion_reference_twoline_C6_20.json
for t in C101 T101 C202 T202; do
    log="logs/p93/${t}.log"
    if [ ! -s "$log" ]; then echo "[p93gates] $t: no log"; rc=1; continue; fi
    case "$t" in *5) ref=$ref5 ;; *6) ref=$ref6 ;; *) ref= ;; esac
    out="logs/p93/${t}.budgets"
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
    echo "[p93gates] $t: ${legs} descent legs, ${over} over budget | ${cone:-cone n/a} | ${fp:-fp n/a}"
    if [ "${over:-1}" -gt 0 ]; then
        echo "[p93gates] $t FAIL - a descent left its budget"
        grep -E "^ +[0-9]+ +[0-9.]+c" "$out" | grep -v " ok$"
        rc=1
    fi
done
echo "[p93gates] done rc=$rc (the fingerprint clause is recorded above, never gated:"
echo "  no 20-attempt post-P87 reference exists in the tree, and 101/202 have none at all)"
exit "$rc"
