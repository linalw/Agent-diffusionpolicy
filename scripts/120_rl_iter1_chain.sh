#!/usr/bin/env bash
# P4 iteration 1 chain: direct rollouts -> RWR fine-tune -> offline fidelity ->
# paired A/B -> hybrid canary -> selfcheck.  Background driver; one simulator at
# a time (polls for a free simulator, never kills a foreign process).
#
#   nohup bash scripts/120_rl_iter1_chain.sh > logs/760_p4_iter1_chain.log 2>&1 &
#
# Stages (all artifacts under logs/, checkpoints/rl_rwr1/ and
# datasets/rl_rollouts/rwr1/):
#   1. 760_rl_rollout_rwr1.log      4 spawn seeds x 15 direct episodes, --record
#   2. 762_rl_finetune_rwr1.log     RWR: successes 1.0 / failures 0.05 + demos_v8
#   3. 763_rl_fidelity_rwr1.txt     paired DDIM-16 fidelity, base vs candidate
#   4. 770_rl_ab_rwr1.log + 771_... paired A/B (R=5 x E=15, interleaved)
#   5. 780_canary_rwr1.log/.out     hybrid canary on the candidate
#   6. 781_selfcheck_after_rwr1.log selfcheck
set -uo pipefail

cd "$(dirname "$0")/.."

PY=${PY:-/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python}
BASE=checkpoints/moe_v9/policy_best.pt
CAND=checkpoints/rl_rwr1/policy_best.pt
ROLLOUTS=datasets/rl_rollouts/rwr1
ROLLDIR="$ROLLOUTS/direct_none_seed101"
STATUS=logs/760_p4_iter1_chain.status
MARK=logs/760_p4_iter1_chain.done

log() { echo "[chain $(date '+%F %T')] $*" | tee -a "$STATUS"; }

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        log "simulator busy (${n} python.sh): $(pgrep -af '[p]ython.sh' | head -2 | tr '\n' ' ')"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

count_episodes() {
    python3 -c "import json,sys; print(len(json.load(open(sys.argv[1]))))" "$1" 2>/dev/null || echo 0
}

count_successes() {
    python3 -c "import json,sys; rows=json.load(open(sys.argv[1])); print(sum(1 for r in rows if r['success']))" "$1" 2>/dev/null || echo '?'
}

if [ -f "$MARK" ]; then
    log "already complete ($MARK) - nothing to do"
    exit 0
fi

log "P4 iteration 1 chain starting (base=$BASE candidate=$CAND)"

# ---------------------------------------------------------------- 1. rollouts
if [ "$(count_episodes "$ROLLDIR/index.json")" -lt 10 ]; then
    wait_for_sim
    log "stage 1: 4 seeds x 15 direct episodes, unseeded DDIM, --record"
    HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_EPISODES=15 \
        FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 \
        scripts/run.sh scripts/110_rl_rollout.py \
        --ckpt "$BASE" --presentation direct --seeds 101,202,303,404 \
        --execute-steps 4 --ddim 16 --record --out "$ROLLOUTS" \
        > logs/760_rl_rollout_rwr1.log 2>&1
    rc=$?
    log "stage 1 rc=$rc summary: $(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' \
        logs/760_rl_rollout_rwr1.log | tail -1)"
else
    log "stage 1: rollouts already present"
fi
EPISODES=$(count_episodes "$ROLLDIR/index.json")
log "stage 1 data: $EPISODES episodes, successes $(count_successes "$ROLLDIR/index.json")"
if [ "$EPISODES" -lt 5 ]; then
    log "ABORT: too few recorded episodes ($EPISODES)"
    exit 1
fi

# -------------------------------------------------------------- 2. fine-tune
if [ ! -f "$CAND" ]; then
    log "stage 2: RWR fine-tune (success 1.0 / failure 0.05, base 1.0, 4 epochs, lr 5e-5)"
    EPOCHS=4 LR=5e-5 WEIGHT_MODE=success FAILURE_WEIGHT=0.05 BASE_WEIGHT=1.0 \
        "$PY" scripts/111_rl_finetune.py \
        --ckpt "$BASE" --rollouts "$ROLLDIR" --base datasets/demos_v8 \
        --out checkpoints/rl_rwr1 > logs/762_rl_finetune_rwr1.log 2>&1
    rc=$?
    log "stage 2 rc=$rc summary: $(grep -E 'epoch |saved ' logs/762_rl_finetune_rwr1.log | tail -2 | tr '\n' ' ')"
fi
if [ ! -f "$CAND" ]; then
    log "ABORT: no fine-tuned checkpoint at $CAND"
    exit 1
fi

# ---------------------------------------------------------- 3. offline fidelity
log "stage 3: paired offline fidelity (rollouts + demos_v8)"
"$PY" scripts/119_rl_fidelity.py \
    --base "$BASE" --candidate "$CAND" \
    --data "$ROLLDIR" --data datasets/demos_v8 --windows 192 \
    --out logs/763_rl_fidelity_rwr1.txt > logs/763_rl_fidelity_rwr1.log 2>&1
rc=$?
log "stage 3 rc=$rc (logs/763_rl_fidelity_rwr1.txt)"

# --------------------------------------------------------------- 4. paired A/B
log "stage 4: paired A/B R=5 x E=15, seeds 77 101 202 303 404, AB_POLICY_SEED=11"
RUNS=5 EPISODES=15 AB_SEEDS="77 101 202 303 404" AB_POLICY_SEED=11 \
    AB_DIR=logs/rl_ab_rwr1 \
    ARM_A="--ckpt $BASE" ARM_B="--ckpt $CAND" \
    scripts/112_rl_ab.sh > logs/770_rl_ab_rwr1.log 2>&1
log "stage 4 rc=$?"
python3 scripts/113_rl_report.py logs/rl_ab_rwr1 --a A --b B \
    > logs/771_rl_ab_rwr1_report.txt 2>&1
log "stage 4 report rc=$? (logs/771_rl_ab_rwr1_report.txt)"

# ------------------------------------------------------------------ 5. canary
wait_for_sim
log "stage 5: hybrid canary on the candidate (10 episodes)"
FRUIT_CKPT="$CAND" FRUIT_EPISODES=10 ACCEPT_POLICY_LOG=logs/780_canary_rwr1.log \
    scripts/accept_policy.sh > logs/780_canary_rwr1.out 2>&1
rc=$?
log "stage 5 rc=$rc verdict: $(grep -E 'PASS|FAIL' logs/780_canary_rwr1.out | tail -1)"

# --------------------------------------------------------------- 6. selfcheck
scripts/selfcheck.sh > logs/781_selfcheck_after_rwr1.log 2>&1
rc=$?
log "stage 6 selfcheck rc=$rc : $(tail -1 logs/781_selfcheck_after_rwr1.log)"

log "chain complete; marker -> $MARK"
touch "$MARK"
