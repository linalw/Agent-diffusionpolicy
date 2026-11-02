#!/usr/bin/env bash
# P98 gates: the revert is resolution-only, the references are restored, and the
# `=1` A/B is P97's arm (budgets only - its fingerprint differs by construction).
#
#   bash logs/p98/gates.sh
#
# G1 = the reverted acceptance is 8/10 + matches 30fb99f8 + 419/419 vs P94.
# G2 = both references are the archived 30fb99f8; the single reference is
#      8952c320 and was never written.
# G3 = the `=1` arm reproduces P97's shipped-default physics stream (pre-pose
#      rows dropped) and passes its budgets; its fingerprint DIFFERS against the
#      restored pre-P97 reference - expected, asserted, never a gate.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
rc=0

echo "== G1: the reverted acceptance vs the P94 record (419/419) =="
if python3 logs/p98/p98_report.py --same logs/p94/accept_final.log \
        logs/p98/accept_revert.log > logs/p98/G1.same 2>&1; then
    echo "[p98gates] G1 IDENTICAL"; tail -2 logs/p98/G1.same
else
    echo "[p98gates] G1 DIFFERS"; rc=1; sed -n 1,6p logs/p98/G1.same
fi
grep -q "fingerprint: matches" logs/p98/accept_revert.out \
    && echo "[p98gates] G1 fingerprint matches 30fb99f8" \
    || { echo "[p98gates] G1 fingerprint NOT matched"; rc=1; }
grep -q "190: PASS" logs/p98/gate_accept_revert.txt \
    && echo "[p98gates] G1 190 PASS" \
    || { echo "[p98gates] G1 190 not PASS"; rc=1; }
echo

echo "== G2: the references =="
arch=$(md5sum logs/p97/motion_reference_pre_p97.json | awk '{print $1}')
for ref in configs/motion_reference.json configs/motion_reference_twoline.json; do
    got=$(md5sum "$ref" | awk '{print $1}')
    if [ "$got" = "$arch" ] && [ "$got" = "30fb99f8824aa4cea906e40ebf5dfa58" ]; then
        echo "[p98gates] $ref = $got (archive, restored)"
    else
        echo "[p98gates] $ref = $got != archive $arch"; rc=1
    fi
done
single=$(md5sum configs/motion_reference_single.json | awk '{print $1}')
if [ "$single" = "8952c320d798ef42e03ba815c9e96b23" ]; then
    echo "[p98gates] configs/motion_reference_single.json = $single (untouched)"
else
    echo "[p98gates] single reference moved: $single"; rc=1
fi
echo

echo "== G3: the =1 A/B reproduces P97's arm (pre-pose rows dropped) =="
if python3 logs/p98/p98_report.py --same-pose logs/p97/accept_final.log \
        logs/p98/accept_clear1.log > logs/p98/G3.same 2>&1; then
    echo "[p98gates] G3 IDENTICAL"; tail -2 logs/p98/G3.same
else
    echo "[p98gates] G3 DIFFERS"; rc=1; sed -n 1,6p logs/p98/G3.same
fi
placed=$(grep -oE "successes=[0-9]+" logs/p98/accept_clear1.log | head -1 | cut -d= -f2)
if [ "${placed:-0}" = "6" ]; then
    echo "[p98gates] G3 =1 arm placed 6/10 (P97's default count)"
else
    echo "[p98gates] G3 =1 arm placed ${placed:-?}/10, expected 6"; rc=1
fi
grep -q "fingerprint: DIFFERS" logs/p98/gate_accept_clear1.txt \
    && echo "[p98gates] G3 fingerprint DIFFERS - by construction (the restored ref is pre-P97)" \
    || { echo "[p98gates] G3 fingerprint did not DIFFER - unexpected"; rc=1; }
grep -qE "PASS|budget" logs/p98/accept_clear1.budgets \
    && echo "[p98gates] G3 budgets recorded" \
    || { echo "[p98gates] G3 no budgets readout"; rc=1; }
echo

echo "== G4: the single arm cannot read the knob =="
if python3 scripts/253_p96_prepose_selftest.py > logs/p98/G4.253 2>&1; then
    grep -E "unset \+ no two-line session|unset inside a two-line session" logs/p98/G4.253 \
        | sed 's/^/[p98gates] /'
    echo "[p98gates] G4 the 253 leg PASSes (no-session scope-off; unset two-line off)"
else
    echo "[p98gates] G4 253 FAIL"; rc=1
fi
echo

echo "== G5: the flip is one constant =="
python3 - <<'PY'
import re
src = open("src/fruit_sorting/tasks.py", encoding="utf-8").read()
m = re.search(r"^PREPOSE_CLEAR_TWO_LINE_DEFAULT = (True|False)$", src, re.M)
print(f"[p98gates] PREPOSE_CLEAR_TWO_LINE_DEFAULT = {m.group(1) if m else '?'}")
assert m and m.group(1) == "False"
print(f"[p98gates] occurrences: {src.count('PREPOSE_CLEAR_TWO_LINE_DEFAULT')}")
PY
[ $? -eq 0 ] || { echo "[p98gates] constant FAIL"; rc=1; }
echo

echo "== the QA gates =="
for f in selfcheck bed_audit index_audit merge_test; do
    if [ -s "logs/p98/${f}.log" ]; then
        tail -2 "logs/p98/${f}.log" | sed "s/^/[p98gates] ${f}: /"
    else
        echo "[p98gates] ${f}: MISSING"; rc=1
    fi
done
echo

echo "[p98gates] done rc=$rc"
exit "$rc"
