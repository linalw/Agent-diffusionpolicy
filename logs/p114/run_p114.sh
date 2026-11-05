#!/usr/bin/env bash
# P114 - the validation batch (default off, the shipped routing as an
# instruction, the size-class rule, the 3-destination cell, the tray refusal).
#
#   bash logs/p114/run_p114.sh
#
# ~15-20 min on the RTX 5090 box. Every cell is a 10- or 20-attempt scripted
# run; the endpoints are the [sort] ledger's assignment accuracy and the
# [fruit]-stream identity, never a rate claim. Each run keeps its own .driver
# and the batch writes an rc summary.
set -uo pipefail

cd "$(dirname "$0")/../.."
OUT=logs/p114
mkdir -p "$OUT"
: > "$OUT/rc.txt"

run() {
    local name=$1
    shift
    echo "=== $name: $*" | tee -a "$OUT/rc.txt"
    "$@" > "$OUT/$name.driver" 2>&1
    echo "rc=$? $name" | tee -a "$OUT/rc.txt"
}

# (i) the shipped scenario, default off - byte-identity and the reference gate
run accept_off env SKIP_SELFCHECK=1 ACCEPT_LOG="$OUT/accept_off.log" scripts/accept.sh

# (ii) the instruction that reproduces today's routing (A->0, B->1, C->skip)
run accept_today env FRUIT_SORT_INSTRUCTION=logs/p114/instructions/today.txt \
    SKIP_SELFCHECK=1 ACCEPT_LOG="$OUT/accept_today.log" scripts/accept.sh

# (iii-b) the size-class rule on the shipped geometry (size<40 -> 1, else 0)
run accept_size40 env FRUIT_SORT_INSTRUCTION=logs/p114/instructions/size40.txt \
    SKIP_SELFCHECK=1 ACCEPT_LOG="$OUT/accept_size40.log" scripts/accept.sh

# (iii-a) the 3-destination cell: the +Y belt's upstream zone at (0.38,+0.55),
# reach=auto (solved at startup), grade A -> 2, B -> 1, C unassigned
run accept_three_dest env \
    FRUIT_SCENARIO=logs/p114/scenarios/three_dest.json \
    FRUIT_SORT_INSTRUCTION=logs/p114/instructions/three_dest.txt \
    SKIP_SELFCHECK=1 ATTEMPTS=20 ACCEPT_LOG="$OUT/accept_three_dest.log" \
    scripts/accept.sh

# (iv) the refusal cell: the tray destination (auto) must be measured
# UNREACHABLE and the instruction must be refused before the first attempt
run refuse_tray env \
    FRUIT_SCENARIO=logs/p114/scenarios/tray_unreachable.json \
    FRUIT_SORT_INSTRUCTION=logs/p114/instructions/tray.txt \
    SKIP_SELFCHECK=1 ATTEMPTS=1 ACCEPT_LOG="$OUT/refuse_tray.log" \
    scripts/accept.sh

# budgets-only for the two moved branches (a different fruit sequence cannot
# match the shipped fingerprint; the motion budgets are still the gate)
python3 scripts/105_motion_regression.py "$OUT/accept_size40.log" \
    --min-success-rate 0.0 > "$OUT/accept_size40.budgets" 2>&1
echo "rc=$? accept_size40 budgets" | tee -a "$OUT/rc.txt"
python3 scripts/105_motion_regression.py "$OUT/accept_three_dest.log" \
    --min-success-rate 0.0 > "$OUT/accept_three_dest.budgets" 2>&1
echo "rc=$? accept_three_dest budgets" | tee -a "$OUT/rc.txt"

# the reports
python3 logs/p114/p114_report.py --same "$OUT/accept_off.log" \
    "$OUT/accept_today.log" > "$OUT/compare_off_vs_today.txt" 2>&1
echo "rc=$? compare_off_vs_today" | tee -a "$OUT/rc.txt"
for name in accept_off accept_today accept_size40 accept_three_dest; do
    python3 logs/p114/p114_report.py --ledger "$OUT/$name.log" \
        > "$OUT/ledger_$name.txt" 2>&1
    echo "rc=$? ledger_$name" | tee -a "$OUT/rc.txt"
done
python3 logs/p114/p114_report.py --accept "$OUT/accept_off.log" \
    > "$OUT/accept_off.summary" 2>&1
echo "rc=$? accept_off summary" | tee -a "$OUT/rc.txt"
grep -n "REFUSED\|reach arm=left dest=3" "$OUT/refuse_tray.log" \
    > "$OUT/refusal.txt" 2>&1
echo "rc=$? refusal" | tee -a "$OUT/rc.txt"
echo "DONE" | tee -a "$OUT/rc.txt"
