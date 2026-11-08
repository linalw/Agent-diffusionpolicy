#!/usr/bin/env bash
# P131 gates - the phase's checks, runnable without a fresh simulator run.
#
#   bash logs/p131/gates.sh
#
# G0 the P131 selfcheck leg (the shipped expression bit for bit, the modes, the
#    one task route, the probe fields)
# G1 the pre-registered D1 (the over-closure is the law) and D2 (the enclosure
#    bar), the landing letter, the crush proxy and the reason set -
#    `p131_report.py --check`
# G2 the descent budgets on all five cells (`105 --min-success-rate 0.0`)
# G3 the no-harm acceptance: 8/10 + `fingerprint: matches` + 421/421 identical
#    to `logs/p127/accept_restored.log` (the record is `accept_noharm.log`)
# G4 `scripts/selfcheck.sh` PASS
#
# The report's G3 (the P5 landing letter) is a *recorded* failure: one
# payload-present release left the belt on a place-leg ejection (a 2.0 m fling),
# not a release-clock miss.  The other four cells are 100 %.  The script exits 1
# on it, the P103 convention.
set -uo pipefail
cd "$(dirname "$0")/../.."
fails=0
note() { printf '%-58s %s\n' "$1" "$2"; }

if python3 scripts/266_p131_cage_aperture_selftest.py > /tmp/p131_g0.log 2>&1; then
    note "G0 P131 cage aperture law (selfcheck leg)" "PASS"
else
    note "G0 P131 cage aperture law (selfcheck leg)" "FAIL"; fails=$((fails+1))
fi

if python3 logs/p131/p131_report.py --check > logs/p131/p131_report.txt 2>&1; then
    note "G1 D1/D2 + landing/crush/reason (report --check)" "PASS"
else
    note "G1 D1/D2 + landing/crush/reason (report --check)" "FAIL (see the report)"; fails=$((fails+1))
fi

budget_fail=0
for f in logs/p131/U_s5.log logs/p131/U_s6.log logs/p131/P_s5.log \
         logs/p131/P_s6.log logs/p131/M_s5.log; do
    if python3 scripts/105_motion_regression.py "$f" --min-success-rate 0.0 \
        > "/tmp/p131_budget_$(basename "$f").txt" 2>&1; then
        :
    else
        budget_fail=$((budget_fail+1))
    fi
done
if [ "$budget_fail" -eq 0 ]; then
    note "G2 descent budgets (105) on the five cells" "PASS"
else
    note "G2 descent budgets (105) on the five cells" "FAIL ($budget_fail cell(s))"
    fails=$((fails+1))
fi

if python3 - <<'PY'
import hashlib, sys
def stream(p):
    return [l for l in open(p, errors="replace").read().splitlines() if l.startswith("[fruit]")]
a = stream("logs/p127/accept_restored.log")
b = stream("logs/p131/accept_noharm.log")
ok = len(a) == len(b) == 421 and a == b
print(f"accept streams: {len(a)} / {len(b)} identical={a == b} "
      f"md5={hashlib.md5(chr(10).join(b).encode()).hexdigest()}")
sys.exit(0 if ok else 1)
PY
then
    note "G3 no-harm acceptance (421/421 vs logs/p127)" "PASS"
else
    note "G3 no-harm acceptance (421/421 vs logs/p127)" "FAIL"; fails=$((fails+1))
fi

if scripts/selfcheck.sh > /tmp/p131_selfcheck.log 2>&1; then
    note "G4 scripts/selfcheck.sh" "PASS ($(tail -1 /tmp/p131_selfcheck.log))"
else
    note "G4 scripts/selfcheck.sh" "FAIL ($(tail -1 /tmp/p131_selfcheck.log))"
    fails=$((fails+1))
fi

echo
echo "gates rc=$fails (G1's landing letter is the P5 place-leg ejection; see logs/p131/RESULTS.md)"
exit "$fails"
