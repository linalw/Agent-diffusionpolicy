#!/usr/bin/env bash
# P103 gates: what has to be true before any number in RESULTS.md is admissible.
#
#   bash logs/p103/gates.sh
#
# Six gates and none of them is a rate:
#
#   G1  **off-path inertness** - with `FRUIT_SLIP_REGRIP` unset the shipped
#       acceptance's `[fruit]` stream must be **byte-identical** to the record
#       this tree already had (`logs/p98/accept_revert.log`, the P98 revert's
#       same-batch acceptance), with P100's `[biarm] park profile:` row dropped -
#       the tree's own sealed filter - and the gate's own verdict
#       (`fingerprint: matches`, `190: PASS`) must be in the driver log. This is
#       the proof the feature is one bool when it is off.
#   G2  **the archived control is admissible** - `C5`/`C6` (this batch,
#       `FRUIT_CARRY_DIAG=1`, no knob) must replay `logs/p102/{C5,C6}.log` line
#       for line on the `[fruit]` stream. Then the A/B against the archived
#       controls is the *action*, not the instrumentation or the batch.
#   G3  **landing** - every release that still had the payload (`release_bottom
#       >= 0`) must read `on_belt=True` on every cell. The `release_bottom < 0`
#       rows are the upstream-lost class (P86/P87's own), counted apart.
#   G4  **the descent budgets** - `105 --min-success-rate 0.0` on every cell.
#       Budgets only: this tree's 20-attempt two-line references predate P87's
#       release clock, so **every** post-P87 cell reads `fingerprint: DIFFERS`
#       by construction (P92/P93 recorded the same clause), and a treatment cell
#       is a different scenario on top of that.
#   G5  **no new failure reason** - in `p103_report.py ab` (the reason-key table).
#   G6  **accounting** - in `p103_report.py ab` (placed + class counts == attempts).
#
# It also prints the **false-positive ledger** the PREREG asks for (a leg that
# re-seated and stayed held, and whether its attempt placed) via `ledge`.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
rc=0
run() {  # run <label> <cmd...>
    local label=$1; shift
    echo "[p103gates] $label"
    if "$@"; then echo "[p103gates]   PASS"; else echo "[p103gates]   FAIL"; rc=1; fi
}

echo "[p103gates] G1 off-path inertness (acceptance, knob unset)"
run "acceptance stream vs logs/p98/accept_revert.log (sealed)" \
    python3 logs/p103/p103_report.py --same logs/p98/accept_revert.log \
        logs/p103/accept_final.log
if grep -q "fingerprint: matches configs/motion_reference.json" \
        logs/p103/accept_final.driver \
   && grep -q "^190: PASS" logs/p103/accept_final.driver; then
    echo "[p103gates]   PASS fingerprint: matches + 190: PASS"
    grep -oE "success: [0-9]+/[0-9]+" logs/p103/accept_final.driver | tail -1 \
        | sed 's/^/[p103gates]   /'
else
    echo "[p103gates]   FAIL the acceptance gate verdict is not in the driver log"
    rc=1
fi

echo "[p103gates] G2 the archived controls are admissible (line identity)"
run "C5 vs logs/p102/C5.log" \
    python3 logs/p103/p103_report.py --same logs/p102/C5.log logs/p103/C5.log
run "C6 vs logs/p102/C6.log" \
    python3 logs/p103/p103_report.py --same logs/p102/C6.log logs/p103/C6.log

echo "[p103gates] G3 landing (every payload-present release on the belt)"
run "all cells" python3 logs/p103/p103_report.py --landing \
    logs/p103/C5.log logs/p103/T5.log logs/p103/C6.log logs/p103/T6.log \
    logs/p103/C101.log logs/p103/T101.log logs/p103/C202.log logs/p103/T202.log

echo "[p103gates] G4 descent budgets (budgets only; the fingerprint is recorded)"
for t in C5 T5 C6 T6 C101 T101 C202 T202; do
    log="logs/p103/${t}.log"
    if [ ! -s "$log" ]; then echo "[p103gates]   $t: no log"; rc=1; continue; fi
    out="logs/p103/${t}.budgets"
    python3 scripts/105_motion_regression.py "$log" --min-success-rate 0.0 \
        > "$out" 2>&1
    legs=$(grep -cE "^ +[0-9]+ +[0-9.]+c" "$out" || true)
    over=$(grep -E "^ +[0-9]+ +[0-9.]+c" "$out" | grep -vc " ok" || true)
    cone=$(grep -oE "worst held-grip cone: [0-9.]+x budget" "$out" | tail -1)
    echo "[p103gates]   $t: ${legs} descent legs, ${over} over budget | ${cone:-cone n/a}"
    if [ "${over:-1}" -gt 0 ]; then
        echo "[p103gates]   $t FAIL - a descent left its budget"
        grep -E "^ +[0-9]+ +[0-9.]+c" "$out" | grep -v " ok"
        rc=1
    fi
done

echo "[p103gates] the conversions (did the re-seated legs' attempts place?)"
python3 logs/p103/p103_report.py conv \
    logs/p103/C5.log logs/p103/T5.log logs/p103/C6.log logs/p103/T6.log \
    logs/p103/C101.log logs/p103/T101.log logs/p103/C202.log logs/p103/T202.log \
    || rc=1

echo "[p103gates] the trigger ledger (G5/G6 and the false-positive ledger are in 'ab')"
python3 logs/p103/p103_report.py ledge \
    logs/p103/T5.log logs/p103/T6.log logs/p103/T101.log logs/p103/T202.log \
    || rc=1

echo "[p103gates] done rc=$rc"
exit "$rc"
