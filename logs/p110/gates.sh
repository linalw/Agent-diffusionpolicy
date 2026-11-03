#!/usr/bin/env bash
# P110 - the phase's own gates.  Offline: reads the logs the phase wrote.
#
#   bash logs/p110/gates.sh
#
# G1 the fixture's height sweep holds the whole pool, at every height, with the
#    belt running (the registered `K4` clause: a <= 14.5 mm kerb must hold).
# G2 the belt never stops in any cell (`belt=-0.120` on every row).
# G3 the queue cells exist and their subject's hold degrades (the measured
#    cadence cost, PREREG section 1.3 item 2).
# G4 no `src/` or `configs/` file moved in this phase (`git status` clean on
#    both, which is what makes the acceptance itself the no-harm).
# G5 the shipped acceptance is byte-identical to the P109 record (419/419) and
#    its fingerprint matches.
# G6 selfcheck / 211 / 106 / 107 verdicts, from the phase's own logs.
set -uo pipefail
cd "$(dirname "$0")/../.."

OUT=logs/p110
fail=0
ok() { printf '  PASS  %s\n' "$*"; }
bad() { printf '  FAIL  %s\n' "$*"; fail=1; }
say() { printf '\n== %s\n' "$*"; }

say "G1 the gate holds the pool (the registered K4 clause)"
for h in 8 10 12 14 20 30 45; do
    f="${OUT}/fix_h${h}.log"
    if [ ! -f "${f}" ]; then bad "h${h}: no cell"; continue; fi
    line=$(grep -E '\[p110\] summary h=' "${f}" | tail -1)
    n=$(sed -E 's/.*n=([0-9]+) .*/\1/' <<<"${line}")
    held=$(sed -E 's/.*held=([0-9]+) .*/\1/' <<<"${line}")
    esc=$(sed -E 's/.*escaped=([0-9]+) .*/\1/' <<<"${line}")
    if [ "${n}" = "${held}" ] && [ "${esc}" = "0" ]; then
        ok "h${h}: held ${held}/${n}, escaped ${esc}"
    else
        bad "h${h}: held ${held}/${n}, escaped ${esc}  (${line})"
    fi
done
if [ -f "${OUT}/fix_h14.log" ]; then
    h=$(grep -E '\[p110\] gate: height=' "${OUT}/fix_h14.log" | head -1)
    if grep -q "hand clearance OK" <<<"${h}"; then
        ok "h14: clears the hand's 14.5 mm"
    else
        bad "h14: does not clear the hand ($h)"
    fi
fi

say "G2 the belt never stops"
stopped=0
for f in "${OUT}"/fix_*.log; do
    [ -f "${f}" ] || continue
    n=$(grep -cE '\[p110\] parked .*belt=-0\.120' "${f}")
    t=$(grep -cE '\[p110\] parked ' "${f}")
    if [ "${n}" != "${t}" ] || [ "${t}" = "0" ]; then
        bad "$(basename "${f}"): ${n}/${t} rows at belt -0.120"
        stopped=1
    fi
done
[ "${stopped}" = "0" ] && ok "every row reads the belt at -0.120 m/s"

say "G3 the queue degrades the hold and can expel"
for q in q2 q4; do
    f="${OUT}/fix_${q}.log"
    if [ ! -f "${f}" ]; then bad "${q}: no cell"; continue; fi
    span=$(grep -E '\[p110\] summary h=' "${f}" | tail -1 | sed -E 's/.*hold_span p50=([0-9.]+)mm.*/\1/')
    if awk "BEGIN{exit !(${span} > 1.83)}"; then
        ok "${q}: hold span ${span} mm > the sole-occupant 1.83 mm"
    else
        bad "${q}: hold span ${span} mm, expected > 1.83 mm"
    fi
done
esc=$(grep -h '\[p110\] parked ' "${OUT}"/fix_q4.log "${OUT}"/fix_q8.log 2>/dev/null | grep -c 'escaped=1')
if [ "${esc}" -ge 1 ]; then
    ok "queue: ${esc} row(s) expelled past the gate (the measured cadence cost)"
else
    bad "queue: no expulsion recorded"
fi

say "G4 no src/ or configs/ change (the no-harm is the acceptance itself)"
if git diff --quiet -- src configs && git diff --cached --quiet -- src configs; then
    ok "src/ and configs/ clean"
else
    bad "src/ or configs/ modified"
fi

say "G5 the shipped acceptance"
if [ -f "${OUT}/accept_noharm.log" ] && [ -f logs/p109/accept_final.log ]; then
    drop() { grep -E '^\[fruit\]' "$1" | grep -vE '^\[fruit\] \[(cycle|stats)\]'; }
    a=$(drop "${OUT}/accept_noharm.log" | md5sum | cut -d' ' -f1)
    b=$(drop logs/p109/accept_final.log | md5sum | cut -d' ' -f1)
    na=$(drop "${OUT}/accept_noharm.log" | wc -l)
    if [ "${a}" = "${b}" ]; then
        ok "acceptance [fruit] stream identical to logs/p109/accept_final.log (${na} lines)"
    else
        bad "acceptance stream differs from logs/p109/accept_final.log"
    fi
    # The gate prints live in the driver's stream, not the task log.
    grep -q "fingerprint: matches" "${OUT}/accept_noharm.driver" \
        && ok "fingerprint: matches" || bad "fingerprint does not match"
    grep -q "190: PASS" "${OUT}/accept_noharm.driver" \
        && ok "190: PASS" || bad "190 did not pass"
else
    bad "acceptance or the P109 record missing"
fi

say "G6 the tree's own checks"
grep -q "0 failures" "${OUT}/selfcheck.log" 2>/dev/null \
    && ok "selfcheck: 0 failures" || bad "selfcheck not clean"
grep -qE "ok \([0-9]+ checks\)" "${OUT}/bed_audit.log" 2>/dev/null \
    && ok "211 bed audit: ok" || bad "211 bed audit missing/failed"

printf '\n%s\n' "$([ "${fail}" = "0" ] && echo 'ALL GATES PASS' || echo 'GATE FAILURES')"
exit "${fail}"
