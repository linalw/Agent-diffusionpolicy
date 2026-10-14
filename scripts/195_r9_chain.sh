#!/usr/bin/env bash
# R9: the bounded RL/DAgger post-training lane - the AWR-clipped RWR
# iteration-2 fine-tune on fresh *on-policy* direct-env rollouts.
#
#   scripts/195_r9_chain.sh [stage]
#   stages: preflight | rollouts | finetune | fidelity | ab | reports |
#           noharm | all (default)
#
# Phase R9 of the plan (`.slim/deepwork/sorting-pipeline-v3.md` "R9 PLAN",
# the R8-A fallback; mirrored in `logs/r8/A_RESULTS.md` section 7). The lane
# and the not-the-two-nulls argument are in `logs/r9/RESULTS.md`.
#
# Pre-registered interface pins (the run must not move them):
#   * direct env, `FRUIT_POLICY_TRIGGER_ACQ=1` (R5 decision: not shipped);
#   * the R7-A bypass fix in the tree (`tasks.py` 27d0fabd);
#   * `FRUIT_POLICY_TRIGGER=arrival`, lead 0.9 s, station frame (the W8-A
#     scenario of record), patch sheet + balanced A:B:C 0.375/0.375/0.25;
#   * base checkpoint `checkpoints/moe_v13s/policy_best.pt` (61da390a - the
#     screen's probe anchor); base store `datasets/demos_v11` (922ca995 - the
#     single-arm anchor; two-line stores are rollout stores, never the base).
#
# Stages, artifacts under logs/r9/ (Tier A solo for every simulator stage):
#   preflight  tree/ckpt pins + selfcheck + a scripted branch probe
#   rollouts   4 spawn seeds x 15 direct episodes, --record (the AWR data)
#   finetune   WEIGHT_MODE=awr, beta=4, 4 epochs, lr 5e-5, base demos_v11
#   fidelity   paired offline action fidelity (scripts/119_rl_fidelity.py)
#   ab         N=5 x 15 paired A/B, seeds [77,101,202,303,404], sampler seed 11
#   reports    scripts/113 + scripts/196 endpoint readouts
#   noharm     scripted acceptance + two-line gate + byte-identity + selfcheck
#
# Set SKIP_SELFCHECK=1 to skip the pre-flight self-check while iterating.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

PY=${PY:-/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python}
HERE=logs/r9
mkdir -p "$HERE"

BASE=checkpoints/moe_v13s/policy_best.pt
CAND=checkpoints/rl_awr1/policy_best.pt
ROLLOUT_ROOT=datasets/rl_rollouts/r9_awr
ROLL_PARTS=datasets/rl_rollouts/r9_parts
ROLLDIR="$ROLLOUT_ROOT"
AB_DIR=$HERE/A_direct_ab
STATUS=$HERE/r9_chain.status

#: the pre-registered scenario + interface pins (both rollouts and the A/B).
PIN_ENV=(FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9
    FRUIT_DYNAMIC_PICK=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1
    FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER_ACQ=1)
#: instrumentation on BOTH A/B arms (AGENTS section 3b: compare arms inside
#: one instrumented batch): `[acq]` stage times + the W8-B `[carry]` lines.
AB_DIAG=(FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1)

log() { echo "[r9 $(date '+%F %T')] $*" | tee -a "$STATUS"; }

done_log() {  # done_log <log> [marker]
    local log=$1 marker=${2:-"\[stats\]"}
    [ -s "$log" ] && grep -qE "$marker" "$log"
}

count_episodes() {
    "$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1]))))" "$1" 2>/dev/null || echo 0
}

#: Watchdog: kill a frozen sim tree (the renderer-wedge class, OPS.md (b)).
#: The known `multitick.render` stall leaves the driver log frozen with the GPU
#: idle and has no in-process recovery; the whole session is killed so the
#: stage can retry. The frozen log is preserved under logs/r9/frozen/.
#: Only safe under the Tier A solo rule (matches by process name).
watch_sim() {  # watch_sim <log> <pgrep-pattern-fragment> <freeze_s>
    local log=$1 pattern=$2 freeze=$3 waited=0 sim age gpu
    mkdir -p "$HERE/frozen"
    while :; do
        sleep 30
        sim=$(pgrep -f "[p]ython.sh $pattern" | head -1 || true)
        if [ -z "$sim" ]; then
            waited=$((waited + 30))
            [ "$waited" -ge 300 ] && return 0
            continue
        fi
        waited=0
        [ -f "$log" ] || continue
        age=$(( $(date +%s) - $(stat -c %Y "$log") ))
        gpu=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
        if [ "$age" -ge "$freeze" ] && [ "${gpu:-100}" -lt 20 ]; then
            log "watchdog: $log frozen ${age}s, gpu ${gpu}% -> killing the sim tree"
            cp "$log" "$HERE/frozen/$(basename "$log" .log)_frozen_$(date +%H%M%S).log" 2>/dev/null
            kill -TERM -- "-$sim" 2>/dev/null
            sleep 10
            kill -KILL -- "-$sim" 2>/dev/null
            return 0
        fi
    done
}

pins() {  # pins <file>
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        "$BASE" datasets/demos_v11/index.json > "$1"
    git rev-parse HEAD >> "$1"
}

#: Same watchdog, but the monitored log is the *newest* `*.log` under a
#: directory - the A/B batch writes one log per run, so the driver log is quiet
#: for the whole of a healthy run and would trip a fixed-path watchdog.
watch_newest() {  # watch_newest <dir> <pgrep-pattern-fragment> <freeze_s>
    local dir=$1 pattern=$2 freeze=$3 waited=0 sim log age gpu
    mkdir -p "$HERE/frozen"
    while :; do
        sleep 30
        sim=$(pgrep -f "[p]ython.sh $pattern" | head -1 || true)
        if [ -z "$sim" ]; then
            waited=$((waited + 30))
            [ "$waited" -ge 300 ] && return 0
            continue
        fi
        waited=0
        log=$(ls -t "$dir"/*.log 2>/dev/null | head -1)
        [ -n "$log" ] && [ -f "$log" ] || continue
        age=$(( $(date +%s) - $(stat -c %Y "$log") ))
        gpu=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
        if [ "$age" -ge "$freeze" ] && [ "${gpu:-100}" -lt 20 ]; then
            log "watchdog: $log frozen ${age}s, gpu ${gpu}% -> killing the sim tree"
            cp "$log" "$HERE/frozen/$(basename "$log" .log)_frozen_$(date +%H%M%S).log" 2>/dev/null
            kill -TERM -- "-$sim" 2>/dev/null
            sleep 10
            kill -KILL -- "-$sim" 2>/dev/null
            return 0
        fi
    done
}

# ------------------------------------------------------------------ stages --- #
stage_preflight() {
    log "preflight: pins -> $HERE/tree_md5_before.txt; selfcheck; branch probe"
    pins "$HERE/tree_md5_before.txt"
    if [ "${SKIP_SELFCHECK:-0}" != "1" ]; then
        scripts/selfcheck.sh > "$HERE/00_selfcheck.log" 2>&1
        log "selfcheck exit=$? ($(tail -1 "$HERE/00_selfcheck.log"))"
    fi
    if ! done_log "$HERE/01_branch_probe_before.log" "approach"; then
        PROBE_DIR="$HERE/branch_probe_before" scripts/126_branch_probe.sh 1 \
            > "$HERE/01_branch_probe_before.log" 2>&1
        log "branch probe (before) exit=$?"
    fi
}

stage_rollouts() {
    # Sharded recorded collection, one spawn seed per process. Why (measured
    # 2026-10-14): two *multi-seed* recorded runs ground in the RTX
    # `multitick.render` stall ~3.5 min in (OPS.md (b)); single-seed runs of
    # the same shape (non-recorded seed 606, recorded seed 909) ran the full
    # 15 episodes in 6.7-7.0 min. Each shard is a fresh process of up to
    # SHARD_EPISODES; whatever it completed is kept and everything is merged by
    # scripts/197_r9_merge_rollouts.py into the store the fine-tune consumes.
    local seeds=(909 505 606 707 808)
    local shard_eps=${R9_SHARD_EPISODES:-15}
    local target=${R9_ROLLOUT_TARGET:-45}
    local i seed shard n total
    mkdir -p "$ROLL_PARTS"
    for seed in "${seeds[@]}"; do
        shard="$ROLL_PARTS/direct_none_seed$seed"
        total=0
        for d in "$ROLL_PARTS"/direct_none_seed*; do
            [ -d "$d" ] || continue
            total=$((total + $(count_episodes "$d/index.json")))
        done
        [ "$total" -ge "$target" ] && break
        if [ "$(count_episodes "$shard/index.json")" -ge 3 ]; then
            log "rollouts: shard seed$seed already has $(count_episodes "$shard/index.json") episodes"
            continue
        fi
        rm -rf "$shard"
        log "rollouts: shard seed$seed (up to $shard_eps recorded episodes)"
        watch_sim "$HERE/10_rollouts_shard.log" "scripts/110_rl_rollout.py" \
            "${R9_SHARD_FREEZE_S:-300}" &
        local watch=$!
        RUN_LIMIT=1500 scripts/154_claim_run.sh "$HERE/10_rollouts_shard.log" \
            HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_EPISODES="$shard_eps" \
            FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 "${PIN_ENV[@]}" \
            scripts/run.sh scripts/110_rl_rollout.py \
            --ckpt "$BASE" --presentation direct --seeds "$seed" \
            --execute-steps 4 --ddim 16 --record --out "$ROLL_PARTS"
        kill "$watch" 2>/dev/null
        n=$(count_episodes "$shard/index.json")
        log "rollouts: shard seed$seed exit=$?, episodes $n, $(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' \
            "$HERE/10_rollouts_shard.log" | tail -1)"
    done
    total=0
    for d in "$ROLL_PARTS"/direct_none_seed*; do
        [ -d "$d" ] || continue
        total=$((total + $(count_episodes "$d/index.json")))
    done
    if [ "$total" -lt 40 ]; then
        log "rollouts: only $total episodes across shards (< 40) - rerun to add shards"
        return 1
    fi
    rm -rf "$ROLLOUT_ROOT"
    "$PY" scripts/197_r9_merge_rollouts.py --out "$ROLLOUT_ROOT" \
        "$ROLL_PARTS"/direct_none_seed* > "$HERE/11_merge.log" 2>&1
    log "rollouts: merged -> $ROLLOUT_ROOT ($(count_episodes "$ROLLDIR/index.json") episodes); $(grep -c 'direct_none_seed' "$HERE/11_merge.log") shard(s)"
    return 0
}

stage_finetune() {
    if [ -f "$CAND" ]; then
        log "finetune: $CAND already present"
        return 0
    fi
    local n
    n=$(count_episodes "$ROLLDIR/index.json")
    if [ "$n" -lt 5 ]; then
        log "finetune ABORT: only $n recorded episodes in $ROLLDIR"
        return 1
    fi
    log "finetune: AWR (beta=4, clip 0.05..4), 4 epochs, lr 5e-5, base demos_v11"
    EPOCHS=4 LR=5e-5 WEIGHT_MODE=awr BETA=4 BASE_WEIGHT=1.0 \
        "$PY" scripts/111_rl_finetune.py \
        --ckpt "$BASE" --rollouts "$ROLLDIR" --base datasets/demos_v11 \
        --out checkpoints/rl_awr1 --seed 0 \
        > "$HERE/20_finetune.log" 2>&1
    local code=$?
    log "finetune exit=$code; $(grep -E 'saved ' "$HERE/20_finetune.log" | tail -1)"
    return $code
}

stage_fidelity() {
    if [ -s "$HERE/30_fidelity.txt" ]; then
        log "fidelity: already present"
        return 0
    fi
    log "fidelity: paired DDIM-16, base vs candidate, 192 windows x 2 stores"
    "$PY" scripts/119_rl_fidelity.py \
        --base "$BASE" --candidate "$CAND" \
        --data "$ROLLDIR" --data datasets/demos_v11 --windows 192 \
        --out "$HERE/30_fidelity.txt" > "$HERE/30_fidelity.log" 2>&1
    local code=$?
    log "fidelity exit=$code ($HERE/30_fidelity.txt)"
    return $code
}

stage_ab() {
    if [ -s "$AB_DIR/B_5.log" ]; then
        log "ab: batch already present"
        return 0
    fi
    log "ab: N=5 x 15, seeds [77 101 202 303 404], sampler 11, interleaved"
    watch_newest "$AB_DIR" "scripts/110_rl_rollout.py" "${R9_AB_FREEZE_S:-420}" &
    local watch=$!
    RUN_LIMIT=18000 scripts/154_claim_run.sh "$HERE/40_ab_driver.log" \
        RUNS=5 EPISODES=15 AB_SEEDS="77 101 202 303 404" AB_POLICY_SEED=11 \
        AB_DIR="$AB_DIR" ARM_A="--ckpt $BASE" ARM_B="--ckpt $CAND" \
        AB_EXTRA_ENV="${PIN_ENV[*]} ${AB_DIAG[*]}" \
        bash -c 'bash scripts/112_rl_ab.sh'
    kill "$watch" 2>/dev/null
    log "ab: batch exit=$?"
    # Repair any run the wedge killed: the same command `112_rl_ab.sh`'s
    # `run_one` uses, per missing (label, run, seed). Recorded, not hidden.
    local seeds=(77 101 202 303 404) i label ckpt seed
    for i in 1 2 3 4 5; do
        for label in A B; do
            [ -s "$AB_DIR/${label}_${i}.log" ] && grep -q "rollout success" "$AB_DIR/${label}_${i}.log" && continue
            seed=${seeds[$((i - 1))]}
            [ "$label" = A ] && ckpt="$BASE" || ckpt="$CAND"
            log "ab: repairing missing run ${label}_${i} (seed $seed)"
            watch_sim "$AB_DIR/${label}_${i}.log" "scripts/110_rl_rollout.py" \
                "${R9_AB_FREEZE_S:-420}" &
            watch=$!
            RUN_LIMIT=1800 scripts/154_claim_run.sh "$AB_DIR/${label}_${i}.log" \
                HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= \
                FRUIT_POLICY_SEED=11 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 \
                "${PIN_ENV[@]}" "${AB_DIAG[@]}" \
                scripts/run.sh scripts/110_rl_rollout.py --ckpt "$ckpt" \
                --presentation direct --episodes 15 --seeds "$seed" \
                --out "$AB_DIR/raw/${label}_${i}"
            kill "$watch" 2>/dev/null
        done
    done
    log "ab: complete; $(ls "$AB_DIR"/*_[0-9].log 2>/dev/null | wc -l)/10 run logs"
}

stage_reports() {
    log "reports: 113 (P4 verdict) + 195 (R9 endpoint readout)"
    python3 scripts/113_rl_report.py "$AB_DIR" --a A --b B \
        > "$HERE/41_verdict.txt" 2>&1
    log "113 exit=$? (negative verdict exits 1 by design)"
    python3 scripts/196_r9_report.py --dir "$AB_DIR" --a A --b B \
        > "$HERE/42_r9_endpoint.txt" 2>&1
    log "196 exit=$? ($HERE/42_r9_endpoint.txt)"
}

stage_noharm() {
    log "noharm: scripted acceptance (Tier A solo)"
    if ! done_log "$HERE/60_accept_r9.log"; then
        watch_sim "$HERE/60_accept_r9.log" "scripts/20_pick_place.py" \
            "${R9_WATCH_FREEZE_S:-600}" &
        local watch=$!
        RUN_LIMIT=1500 scripts/154_claim_run.sh "$HERE/60_accept_claim.log" \
            ACCEPT_LOG="$HERE/60_accept_r9.log" SKIP_SELFCHECK=1 \
            bash -c "scripts/accept.sh > $HERE/60_accept_r9.out 2>&1"
        kill "$watch" 2>/dev/null
        log "accept exit=$?; $(grep -E 'PASS|FAIL|fingerprint' "$HERE/60_accept_r9.out" \
            | tail -2 | tr '\n' ' ')"
    fi

    log "noharm: two-line dense battery + the two-line gate"
    if ! done_log "$HERE/70_twoline_r9.log"; then
        watch_sim "$HERE/70_twoline_r9.log" "scripts/20_pick_place.py" \
            "${R9_WATCH_FREEZE_S:-600}" &
        local watch=$!
        RUN_LIMIT=3600 scripts/154_claim_run.sh "$HERE/70_twoline_r9.log" \
            HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 SEED=5 \
            FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10 \
            scripts/run.sh scripts/20_pick_place.py
        kill "$watch" 2>/dev/null
        log "twoline exit=$?"
    fi
    scripts/190_twoline_gate.sh "$HERE/70_twoline_r9.log" \
        > "$HERE/71_twoline_gate.txt" 2>&1
    log "190 exit=$? ($HERE/71_twoline_gate.txt)"

    log "noharm: [fruit]-stream byte-identity vs the R7/R8 + W7 records"
    {
        scripts/182_run_equiv.py logs/r7/A_accept.log "$HERE/60_accept_r9.log"
        echo "(vs logs/r8/A_accept.log)"
        scripts/182_run_equiv.py logs/r8/A_accept.log "$HERE/60_accept_r9.log"
        echo "(two-line vs logs/w7/10_dense_twoline_1.log)"
        scripts/182_run_equiv.py logs/w7/10_dense_twoline_1.log "$HERE/70_twoline_r9.log"
    } > "$HERE/72_equiv.txt" 2>&1
    log "182 exit=$? ($HERE/72_equiv.txt)"

    scripts/selfcheck.sh > "$HERE/61_selfcheck_after.log" 2>&1
    log "final selfcheck exit=$? ($(tail -1 "$HERE/61_selfcheck_after.log"))"

    pins "$HERE/tree_md5_after.txt"
    if cmp -s "$HERE/tree_md5_before.txt" "$HERE/tree_md5_after.txt"; then
        log "tree pins identical before/after"
    else
        log "WARNING: tree pins moved during the chain"
    fi

    PROBE_DIR="$HERE/branch_probe_after" scripts/126_branch_probe.sh 1 \
        > "$HERE/62_branch_probe_after.log" 2>&1
    log "branch probe (after) exit=$?"
}

# ------------------------------------------------------------------ driver --- #
case "${1:-all}" in
    preflight) stage_preflight ;;
    rollouts)  stage_rollouts ;;
    finetune)  stage_finetune ;;
    fidelity)  stage_fidelity ;;
    ab)        stage_ab ;;
    reports)   stage_reports ;;
    noharm)    stage_noharm ;;
    all)
        stage_preflight
        stage_rollouts || true
        stage_finetune || true
        stage_fidelity || true
        stage_ab || true
        stage_reports || true
        stage_noharm || true
        log "chain complete"
        ;;
    *)
        echo "usage: $0 [preflight|rollouts|finetune|fidelity|ab|reports|noharm|all]" >&2
        exit 2
        ;;
esac
