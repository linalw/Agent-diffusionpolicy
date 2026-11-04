#!/usr/bin/env bash
# P111 - the phase's gates: the controls replay, the counters, the no-harm.
#
#   bash logs/p111/gates.sh
#
# rc=0 only if every gate passes.  The numbers behind each gate are in
# logs/p111/RESULTS.md; this script re-derives them from the logs.
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=logs/p111
fail=0
ok()   { printf '%-34s %s\n' "$1" "$2"; }
bad()  { printf '%-34s %s\n' "$1" "FAIL: $2"; fail=1; }

# G0 - the two controls are `[fruit]`-stream replays of P108's cells (this is what
# makes P108's other seeds admissible, so it is the first gate).
for pair in "C_s5 S_s5" "R_s5 E_s5"; do
    set -- $pair
    if python3 ${OUT}/p111_report.py --same "${OUT}/$1.log" "logs/p108/$2.log" \
        --drop '[cage],[cycle],[carry],place trace' | grep -q "^  IDENTICAL"; then
        ok "G0 replay $1 = p108/$2" PASS
    else
        bad "G0 replay $1 = p108/$2" "stream moved"
    fi
done

# G1 - the phase's own instrumentation is inert on the shipped path.
if python3 ${OUT}/p111_report.py --same ${OUT}/accept_noharm.log \
    logs/p110/accept_noharm.log --drop '[cage]' | grep -q "^  IDENTICAL"; then
    ok "G1 acceptance [fruit] stream" PASS
else
    bad "G1 acceptance [fruit] stream" "moved"
fi

# G2 - the census's own numbers (the phase's claims, re-derived).
python3 ${OUT}/census.py > ${OUT}/census.txt 2>&1
if grep -q "the exact two-sided Fisher test" ${OUT}/census.txt; then
    ok "G2 census table" PASS
else
    bad "G2 census table" "no Fisher block"
fi

# G3 - the crush guard: no leg with sep@loss - dia < -15 mm (P76's rule).
crush=$(python3 - <<'PY'
import re, glob
n = 0
for p in glob.glob("logs/p111/[CRT][0-9]*_s*.log") + glob.glob("logs/p111/R_s*.log"):
    t = open(p, errors="replace").read()
    for m in re.finditer(r"\[carry\] \w+ place\d*: .*?sep@loss=([-+0-9.]+)mm.*?dia=([0-9.]+)", t):
        if float(m.group(1)) - float(m.group(2)) < -15.0:
            n += 1
print(n)
PY
)
[ "${crush}" = "0" ] && ok "G3 crush guard" PASS || bad "G3 crush guard" "${crush} leg(s)"

# G4 - the offline checks.
bash scripts/selfcheck.sh > ${OUT}/selfcheck.log 2>&1 \
    && ok "G4 selfcheck" PASS || bad "G4 selfcheck" "see ${OUT}/selfcheck.log"
python3 scripts/106_index_audit.py > /dev/null 2>&1 \
    && ok "G4 index audit" PASS || bad "G4 index audit" "see scripts/106"
python3 scripts/107_collect_merge_test.py > /dev/null 2>&1 \
    && ok "G4 collect/merge" PASS || bad "G4 collect/merge" "see scripts/107"

echo
[ "${fail}" = "0" ] && echo "P111 gates: PASS" || echo "P111 gates: FAIL"
exit ${fail}
