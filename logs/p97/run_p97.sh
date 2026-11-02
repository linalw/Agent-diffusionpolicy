#!/usr/bin/env bash
# P97 adoption package - the exact runs, in order, with the claim guard.
#
#   bash logs/p97/run_p97.sh              # every cell (skips existing logs)
#   bash logs/p97/run_p97.sh accept       # one stage
#
# PREREG: logs/p97/PREREG.md (md5 in logs/p97/PREREG.md5), pinned before any run.
# The flip is resolution-only: `=0` must reproduce the pre-P97 record bit for
# bit, the single arm must be untouched, and the shipped default is P96's
# measured arm (`FRUIT_BIARM_PREPOSE_CLEAR=1`).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p97

stage=${1:-all}
fail=0
note() { echo "[p97] $*"; }

claim() {  # claim <tag> <env...>
    local tag=$1; shift
    if [ -s "logs/p97/${tag}.log" ]; then note "SKIP $tag (exists)"; return 0; fi
    note "START $(date +%H:%M:%S) $tag  $*"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "logs/p97/${tag}.driver" "$@" \
        bash logs/p80/one_run.sh "logs/p97/${tag}.log" "logs/p97/${tag}.stamps"
    local rc=$?
    note "exit=$rc $(date +%H:%M:%S) $tag"
    [ "$rc" -ne 0 ] && fail=$((fail + 1))
}

accept() {  # accept <tag> <env...>
    local tag=$1; shift
    if [ -s "logs/p97/${tag}.log" ]; then note "SKIP $tag (exists)"; return 0; fi
    note "START $(date +%H:%M:%S) $tag"
    SKIP_SELFCHECK=1 ACCEPT_LOG="logs/p97/${tag}.log" env "$@" \
        scripts/accept.sh > "logs/p97/${tag}.out" 2>&1
    note "accept rc=$? (a rate/fingerprint FAIL is expected before the re-record)"
}

if [ "$stage" = all ] || [ "$stage" = accept ]; then
    # 1. the shipped default (the pre-P97 reference will DIFFER - expected)
    accept accept_default
    # 2. its own second run: the two-line reference is re-recorded from this
    accept twoline_ref
    # 3. the =0 A/B: must reproduce 30fb99f8 + logs/p94/accept_final.log
    accept accept_pre97 FRUIT_BIARM_PREPOSE_CLEAR=0
    # 4. the single arm: must be 346/346 + the single reference
    accept accept_single FRUIT_BIARM=0
fi

if [ "$stage" = all ] || [ "$stage" = cell ]; then
    # 5. the sanity cell: the shipped default at seed 5, P96's census stack
    claim S5 HEADLESS=1 ATTEMPTS=20 SEED=5 FRUIT_MOTION_REPORT=1 \
        FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1 \
        FRUIT_FRUIT_TRACE=2500 FRUIT_FRUIT_TRACE_ARM=1 \
        FRUIT_FRUIT_TRACE_DIR=logs/p97/trS5
fi

if [ "$stage" = all ] || [ "$stage" = collect ]; then
    # 6. a fresh one-episode shard: the manifest's provenance keys
    if [ ! -s logs/p97/shard_manifest.json ]; then
        claim collect_shard HEADLESS=1 FRUIT_EPISODES=1 \
            FRUIT_DEMO_DIR=/tmp/p97_shard
        if [ -s /tmp/p97_shard/manifest.json ]; then
            cp /tmp/p97_shard/manifest.json logs/p97/shard_manifest.json
        else
            note "FAIL collect_shard produced no manifest"; fail=$((fail + 1))
        fi
    fi
    # 6b. the same builder, without a collection run (the acceptance's witness)
    scripts/run.sh logs/p97/manifest_probe.py > logs/p97/manifest_probe.log 2>&1 \
        || { note "FAIL manifest_probe"; fail=$((fail + 1)); }
fi

if [ "$stage" = all ] || [ "$stage" = gates ]; then
    # 7. re-record both two-line-side references from the same-batch runs
    if [ ! -s logs/p97/motion_reference_pre_p97.json ]; then
        cp configs/motion_reference.json logs/p97/motion_reference_pre_p97.json
        cp configs/motion_reference_twoline.json \
           logs/p97/motion_reference_twoline_pre_p97.json
    fi
    if [ -s logs/p97/accept_default.log ] && \
       [ ! -s logs/p97/write_ref_accept.txt ]; then
        python3 scripts/105_motion_regression.py logs/p97/accept_default.log \
            --write-fingerprint configs/motion_reference.json \
            --min-success-rate 0.60 > logs/p97/write_ref_accept.txt 2>&1
        python3 scripts/105_motion_regression.py logs/p97/twoline_ref.log \
            --write-fingerprint configs/motion_reference_twoline.json \
            --min-success-rate 0.60 > logs/p97/write_ref_twoline.txt 2>&1
    fi
    scripts/190_twoline_gate.sh logs/p97/accept_default.log \
        > logs/p97/gate_accept_default.txt 2>&1 || fail=$((fail + 1))
    scripts/190_twoline_gate.sh logs/p97/twoline_ref.log \
        > logs/p97/gate_twoline_ref.txt 2>&1 || fail=$((fail + 1))
    python3 scripts/105_motion_regression.py logs/p97/S5.log \
        --min-success-rate 0.0 > logs/p97/S5.budgets 2>&1 || true
    python3 logs/p97/census.py > logs/p97/census.run.txt 2>&1 || \
        { note "FAIL census"; fail=$((fail + 1)); }
    python3 logs/p97/p97_report.py > logs/p97/p97_report.run.txt 2>&1 || \
        { note "FAIL report"; fail=$((fail + 1)); }
fi

note "done $(date +%H:%M:%S) failures=$fail"
exit "$fail"
