#!/usr/bin/env bash
# P38 phase 2 step 4: the scripted no-harm (M4, PREREG_A1 A6).
#
#   bash scripts/226_p38_m4.sh
#
# `accept.sh` twice - knobs unset, then all four set (`DIAG=1 END=1 RESEED=1
# MAX=2`) - plus `selfcheck.sh`. The knobs are `presentation == "direct"` only
# and validate that at construction, so the scripted line cannot reach them:
# the check is **byte-identity of the `[fruit]` stream**, `fingerprint:
# matches`, and a PASS from the offline self-check. For *this* change that is
# **near-tautological** - the scripted path never evaluates the `if
# self._refuse_knobs` branch - so the meaningful pin for the `trigger.py` edit
# is `scripts/811_trigger_test.py` (the new lateral truth table + the END
# predicate) plus the analytic reorder equivalence (`logs/p38/P2_RESULTS.md`
# section 2). **`accept_policy.sh` is not run here**: the four knobs raise on
# any presentation other than `direct`, so the hybrid canary cannot read them -
# an omission of coverage of the shipped default, not of the direct interface.
# One claim for the whole sequence (one simulator process at a time).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/p38/M4

ACCEPT_LOG=logs/p38/M4/A_knobs_off.log SKIP_SELFCHECK=1 \
    scripts/154_claim_run.sh logs/p38/M4/A_driver.log scripts/accept.sh
echo "[p38m4] knobs-off accept exit=$?"

ACCEPT_LOG=logs/p38/M4/B_knobs_on.log SKIP_SELFCHECK=1 \
    FRUIT_POLICY_REFUSE_DIAG=1 FRUIT_POLICY_REFUSE_END=1 \
    FRUIT_POLICY_RESEED=1 FRUIT_POLICY_RESEED_MAX=2 \
    scripts/154_claim_run.sh logs/p38/M4/B_driver.log scripts/accept.sh
echo "[p38m4] knobs-on accept exit=$?"

grep -E '^\[fruit\]' logs/p38/M4/A_knobs_off.log > logs/p38/M4/A_fruit.txt
grep -E '^\[fruit\]' logs/p38/M4/B_knobs_on.log > logs/p38/M4/B_fruit.txt
if cmp -s logs/p38/M4/A_fruit.txt logs/p38/M4/B_fruit.txt; then
    echo "[p38m4] [fruit] stream: IDENTICAL ($(wc -l < logs/p38/M4/A_fruit.txt) lines)"
else
    echo "[p38m4] [fruit] stream: DIFFERS"
    diff logs/p38/M4/A_fruit.txt logs/p38/M4/B_fruit.txt | head -20
fi
grep -E "fingerprint|motion gate|PASS|FAIL" logs/p38/M4/A_knobs_off.log | tail -6
grep -E "fingerprint|motion gate|PASS|FAIL" logs/p38/M4/B_knobs_on.log | tail -6

RUN_LIMIT=900 scripts/154_claim_run.sh logs/p38/M4/selfcheck.log \
    scripts/selfcheck.sh
echo "[p38m4] selfcheck exit=$?"
tail -2 logs/p38/M4/selfcheck.log
echo "[p38m4] done $(date +%H:%M:%S)"
