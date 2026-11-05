#!/usr/bin/env bash
# P115 - the instruction as an operator tool (default off; no shipped change).
#
#   bash logs/p115/run_p115.sh
#
# Three cells:
#   1 compound   - `species=apple and size>=66 => 1`, `size<45 => 1`,
#                  `default => 0`, 20 attempts. The endpoint is the ledger's
#                  assignment accuracy and the per-rule histogram, never a rate.
#   2 strict     - `grade=A => 0` with FRUIT_SORT_STRICT=1: B and C are
#                  unassigned, so the run must refuse at construction (before
#                  the first attempt) and name what it dropped.
#   3 unset      - the shipped acceptance, byte-identical to P110's record.
#
# ~20-25 min on the RTX 5090 box. Each run keeps its own .driver; the batch
# writes an rc summary and the reports.
set -uo pipefail

cd "$(dirname "$0")/../.."
OUT=logs/p115
mkdir -p "$OUT"
: > "$OUT/rc.txt"

run() {
    local name=$1
    shift
    echo "=== $name: $*" | tee -a "$OUT/rc.txt"
    "$@" > "$OUT/$name.driver" 2>&1
    echo "rc=$? $name" | tee -a "$OUT/rc.txt"
}

# (1) the compound cell: a real sorting spec with an `and` rule
run compound env ATTEMPTS=20 \
    FRUIT_SORT_INSTRUCTION=configs/instructions/compound.txt \
    SKIP_SELFCHECK=1 ACCEPT_LOG="$OUT/compound.log" scripts/accept.sh

# (2) the strict guard: an instruction that drops fruit must refuse at startup
run strict env ATTEMPTS=1 FRUIT_SORT_STRICT=1 \
    FRUIT_SORT_INSTRUCTION="grade=A => 0" \
    SKIP_SELFCHECK=1 ACCEPT_LOG="$OUT/strict.log" scripts/accept.sh

# (3) the unset replay (the shipped cell; byte-identity)
run unset env SKIP_SELFCHECK=1 ACCEPT_LOG="$OUT/accept_unset.log" scripts/accept.sh

# the compound branch is a different fruit sequence: budgets-only, no fingerprint
python3 scripts/105_motion_regression.py "$OUT/compound.log" \
    --min-success-rate 0.0 > "$OUT/compound.budgets" 2>&1
echo "rc=$? compound budgets" | tee -a "$OUT/rc.txt"

python3 "$OUT/p115_report.py" --ledger "$OUT/compound.log" \
    > "$OUT/ledger_compound.txt" 2>&1
echo "rc=$? ledger_compound" | tee -a "$OUT/rc.txt"

python3 "$OUT/p115_report.py" --same "$OUT/accept_unset.log" \
    logs/p110/accept_noharm.log > "$OUT/compare_unset.txt" 2>&1
echo "rc=$? compare_unset" | tee -a "$OUT/rc.txt"

grep -aE "ScenarioError|REFUSED" logs/20_pick_place_traceback.txt \
    > "$OUT/refusal.txt" 2>&1
echo "rc=$? refusal" | tee -a "$OUT/rc.txt"

echo "DONE" | tee -a "$OUT/rc.txt"
