#!/usr/bin/env bash
# P84 gates, run AFTER the four cells (and after `run_p84.sh` wrote the plain
# gate files). Corrects the reference policy for the second seed:
#
#   * D5 (seed 5) is the seed-5 reference's own scenario -> `190` against P80's
#     20-attempt reference must PASS (fingerprint matches + rate at/above 0.5).
#   * D6 (seed 6) is a **different scenario** from that reference: a different
#     seed presents a different fruit sequence, so it cannot match a seed-5
#     fingerprint and P80 never wrote a seed-6 one. Its per-seed reference is
#     written here from P80's own `logs/p80/T6.log` (budgets must be clean) and
#     D6 is then gated against it - the same tree, a different draw.
#   * F5 / F6 (the lever) are their OWN attractor (the abort re-times the
#     presentation, PREREG R0): their `190` comparison against P80's seed-5
#     reference is **recorded** (DIFFERS expected) and they are gated on the
#     motion BUDGETS only (`105 --min-success-rate 0.0`).
#
#   bash logs/p84/gates.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
OUT=logs/p84
REF20="logs/p80/motion_reference_twoline_p80_20.json"
REF6="$OUT/motion_reference_twoline_T6_20.json"
FLOOR=0.5
fail=0
note() { echo "[p84] $*"; }

# 1. the seed-6 per-scenario reference, written from P80's own record
if [ ! -s "$REF6" ]; then
    note "writing the seed-6 reference from logs/p80/T6.log"
    python3 scripts/105_motion_regression.py logs/p80/T6.log \
        --min-success-rate 0.0 --write-fingerprint "$REF6" 2>&1 | tail -6
fi
md5sum "$REF6" 2>/dev/null | sed 's/^/[p84] /'

# 2. the gates
for tag in D5 D6 F5 F6; do
    [ -s "$OUT/$tag.log" ] || { note "MISSING $tag"; fail=1; continue; }
    case "$tag" in
        D5)
            note "190 (seed-5 reference: MUST PASS) $tag"
            TWOLINE_REF="$REF20" scripts/190_twoline_gate.sh -m "$FLOOR" "$OUT/$tag.log" \
                2>&1 | tee "$OUT/$tag.gate"
            [ "${PIPESTATUS[0]}" -ne 0 ] && fail=1
            ;;
        D6)
            note "190 (seed-6 reference from P80 T6: MUST PASS) $tag"
            TWOLINE_REF="$REF6" scripts/190_twoline_gate.sh -m "$FLOOR" "$OUT/$tag.log" \
                2>&1 | tee "$OUT/$tag.gate_t6"
            [ "${PIPESTATUS[0]}" -ne 0 ] && fail=1
            ;;
        F5|F6)
            note "105 budgets (no fingerprint: the treatment is its own attractor) $tag"
            python3 scripts/105_motion_regression.py "$OUT/$tag.log" \
                --min-success-rate 0.0 2>&1 | tee "$OUT/$tag.budgets"
            [ "${PIPESTATUS[0]}" -ne 0 ] && fail=1
            ;;
    esac
done

note "gates fail=$fail"
exit "$fail"
