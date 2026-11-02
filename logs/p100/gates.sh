#!/usr/bin/env bash
# P100 gates: the admissibility proofs, the budgets, the references.
#   bash logs/p100/gates.sh   (offline; exit 0 = all gates pass)
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
fail=0
note() { echo "[p100] $*"; }

note "G1 the controls replay the P99 census cells ([ready]/park-row/bed-sel dropped)"
python3 logs/p100/p100_report.py --same logs/p100/C5.log logs/p99/C5.log \
    || fail=$((fail + 1))
python3 logs/p100/p100_report.py --same logs/p100/C6.log logs/p99/C6.log \
    || fail=$((fail + 1))

note "G2 every cell names its own park clock"
for t in C5 T5 C6 T6 C101 T101 C202 T202; do
    row=$(grep -m1 "\[biarm\] park profile:" "logs/p100/${t}.log" 2>/dev/null)
    [ -n "$row" ] || { note "  $t MISSING"; fail=$((fail + 1)); continue; }
    case "$t" in
        C*) want="(0)(scope-off)"; clocks="blend=90 settle=120 (210 ticks" ;;
        T*) want="(1)(explicit)"; clocks="blend=60 settle=75 (135 ticks" ;;
    esac
    if [[ "$row" == *"$want"* && "$row" == *"$clocks"* ]]; then
        note "  $t ok"
    else
        note "  $t MISMATCH: $row"; fail=$((fail + 1))
    fi
done

note "G3 the motion budgets (each cell's own branch: budgets only)"
for t in C5 T5 C6 T6 C101 T101 C202 T202; do
    if python3 scripts/105_motion_regression.py "logs/p100/${t}.log" \
        --min-success-rate 0.0 > "logs/p100/${t}.budgets" 2>&1; then
        note "  $t budgets PASS"
    else
        note "  $t budgets FAIL"; fail=$((fail + 1))
    fi
done

note "G4 the references are untouched"
for f in configs/motion_reference.json configs/motion_reference_twoline.json; do
    m=$(md5sum "$f" | cut -c1-8)
    [ "$m" = "30fb99f8" ] && note "  $f $m ok" || { note "  $f $m MISMATCH"; fail=$((fail + 1)); }
done
m=$(md5sum configs/motion_reference_single.json | cut -c1-8)
[ "$m" = "8952c320" ] && note "  single $m ok" || { note "  single $m MISMATCH"; fail=$((fail + 1)); }

note "G5 the acceptance is inert on the shipped tree (knob unset; P100's own row dropped)"
if [ -s logs/p100/accept_noharm.log ]; then
    python3 - <<'PY' || fail=$((fail + 1))
import sys
a = [l for l in open("logs/p100/accept_noharm.log", errors="replace")
     if l.startswith("[fruit]") and "[biarm] park profile:" not in l]
b = [l for l in open("logs/p94/accept_final.log", errors="replace")
     if l.startswith("[fruit]")]
print(f"   {len(a)} vs {len(b)} [fruit] lines:",
      "IDENTICAL" if a == b else "DIFFERS")
sys.exit(0 if a == b else 1)
PY
    grep -E "fingerprint: (matches|DIFFERS)|^\[gate\]|190: (PASS|FAIL)" \
        logs/p100/accept_noharm.log 2>/dev/null | tail -4
else
    note "  logs/p100/accept_noharm.log missing"; fail=$((fail + 1))
fi

note "G6 the report's registered clauses"
python3 logs/p100/p100_report.py --check > logs/p100/p100_report.txt 2>&1 \
    && note "  p100_report --check PASS" \
    || { note "  p100_report --check FAIL (see p100_report.txt)"; fail=$((fail + 1)); }

note "gates done failures=$fail"
exit "$fail"
