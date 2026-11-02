#!/usr/bin/env bash
# P99 gates: the two admissibility proofs, the references, and the guards.
#   bash logs/p99/gates.sh   (offline; exit 0 = all gates pass)
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
fail=0
note() { echo "[p99] $*"; }

note "G1 the census cells replay their same-seed P94 record (instrument neutral)"
python3 logs/p99/p99_report.py --check || fail=$((fail + 1))

note "G2 the references are untouched"
for f in configs/motion_reference.json configs/motion_reference_twoline.json; do
    m=$(md5sum "$f" | cut -c1-8)
    [ "$m" = "30fb99f8" ] && note "  $f $m ok" || { note "  $f $m MISMATCH"; fail=$((fail + 1)); }
done
m=$(md5sum configs/motion_reference_single.json | cut -c1-8)
[ "$m" = "8952c320" ] && note "  single $m ok" || { note "  single $m MISMATCH"; fail=$((fail + 1)); }

note "G3 the pricing cells' motion budgets (a moved branch: budgets only)"
for t in G5 G6; do
    if python3 scripts/105_motion_regression.py "logs/p99/${t}.log" \
        --min-success-rate 0.0 > "/tmp/p99_${t}.budgets" 2>&1; then
        note "  $t budgets PASS"
    else
        note "  $t budgets FAIL"; fail=$((fail + 1))
    fi
done

note "G4 the acceptance is inert on the scripted path"
if python3 - <<'PY'
import sys
a = [l for l in open("logs/p99/accept_noharm_sim.log", errors="replace")
     if l.startswith("[fruit]")]
b = [l for l in open("logs/p98/accept_revert.log", errors="replace")
     if l.startswith("[fruit]")]
print(f"   {len(a)} vs {len(b)} [fruit] lines:",
      "IDENTICAL" if a == b else "DIFFERS")
sys.exit(0 if a == b else 1)
PY
then
    :
else
    note "  the acceptance stream DIFFERS"; fail=$((fail + 1))
fi

note "G5 the demand census is reproducible"
python3 logs/p99/census.py logs/p99/C5.log logs/p99/C6.log >/dev/null 2>&1 \
    && note "  census.py ok" || { note "  census.py FAILED"; fail=$((fail + 1)); }

note "gates done failures=$fail"
exit "$fail"
