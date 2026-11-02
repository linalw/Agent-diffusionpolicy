#!/usr/bin/env bash
# P98 - the P97 revert: the two acceptance cells and their gates.
#
#   bash logs/p98/run_p98.sh            # every stage (skips existing logs)
#   bash logs/p98/run_p98.sh accept     # the two acceptance runs
#
# PREREG: logs/p98/PREREG.md (md5 in logs/p98/PREREG.md5), pinned before any run.
# The revert is one constant (True -> False) + the restored references, so
# P1 is the acceptance reproducing `8/10 + matches 30fb99f8 + 419/419 vs
# logs/p94/accept_final.log`, and P3 is the `=1` A/B reproducing P97's arm
# (budgets only; the fingerprint differs by construction).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p98

stage=${1:-all}
fail=0
note() { echo "[p98] $*"; }

accept() {  # accept <tag> <env...>
    local tag=$1; shift
    if [ -s "logs/p98/${tag}.log" ]; then note "SKIP $tag (exists)"; return 0; fi
    note "START $(date +%H:%M:%S) $tag"
    SKIP_SELFCHECK=1 ACCEPT_LOG="logs/p98/${tag}.log" env "$@" \
        scripts/accept.sh > "logs/p98/${tag}.out" 2>&1
    local rc=$?
    note "accept rc=$rc (a fingerprint FAIL is expected for the =1 arm only)"
    return 0
}

if [ "$stage" = all ] || [ "$stage" = accept ]; then
    # 1. the reverted default: must be 8/10 + matches 30fb99f8 + 419/419
    accept accept_revert
    # 2. the opt-in A/B: P97's arm, budgets only (the reference moved back)
    accept accept_clear1 FRUIT_BIARM_PREPOSE_CLEAR=1
fi

if [ "$stage" = all ] || [ "$stage" = gates ]; then
    scripts/190_twoline_gate.sh logs/p98/accept_revert.log \
        > logs/p98/gate_accept_revert.txt 2>&1 || fail=$((fail + 1))
    # the =1 arm: budgets only. `190` is expected to FAIL on the fingerprint
    # alone (the restored 30fb99f8 is the pre-P97 branch), so it is recorded,
    # never counted as a gate; 105 with a 0 floor is the budget read.
    python3 scripts/105_motion_regression.py logs/p98/accept_clear1.log \
        --min-success-rate 0.0 > logs/p98/accept_clear1.budgets 2>&1 || true
    scripts/190_twoline_gate.sh logs/p98/accept_clear1.log \
        > logs/p98/gate_accept_clear1.txt 2>&1 || true
    python3 logs/p98/p98_report.py --check > logs/p98/p98_check.txt 2>&1 || fail=$((fail + 1))
fi

if [ "$stage" = all ] || [ "$stage" = qa ]; then
    scripts/selfcheck.sh > logs/p98/selfcheck.log 2>&1 || fail=$((fail + 1))
    python3 scripts/211_bed_audit.py > logs/p98/bed_audit.log 2>&1 || fail=$((fail + 1))
    python3 scripts/106_index_audit.py > logs/p98/index_audit.log 2>&1 || fail=$((fail + 1))
    python3 scripts/107_collect_merge_test.py > logs/p98/merge_test.log 2>&1 \
        || fail=$((fail + 1))
fi

if [ "$stage" = all ] || [ "$stage" = report ]; then
    python3 logs/p98/p98_report.py > logs/p98/p98_report.txt 2>&1 || \
        { note "FAIL report"; fail=$((fail + 1)); }
fi

note "done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
