#!/usr/bin/env bash
# P77: the 60 N clamp at three seeds, as a FORCE-CEILING SENSITIVITY (owner cell).
#   logs/p77/PREREG.md, md5 d31c3e4ab8881ae63e33a54e81adff7b (pinned before any run)
#
#   bash logs/p77/run_p77.sh            # phase 1 (6 direct cells) + phase 2 (the price)
#   PHASE=1 bash logs/p77/run_p77.sh    # the 3-seed interleaved batch only
#   PHASE=2 bash logs/p77/run_p77.sh    # accept.sh @60N + the two-line @60N only
#
# The one variable is `FRUIT_FINGER_MAXFORCE` (the per-joint drive cap the build
# writes on both arms' `joint1`, scene.py resolve_finger_maxforce /
# apply_finger_maxforce):
#   C = unset  -> the shipped asset cap (10 N)
#   T = 60     -> the P76 F60 declared-extension rung
# Nothing is adopted, no default moves, configs/* untouched.
#
# Arms interleaved BY SEED so each treatment cell is read against an adjacent
# control cell; the order within a seed alternates by seed (77 C->T, 101 T->C,
# 202 C->T) so a monotone wall-clock drift cannot load onto one arm.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p77/direct logs/p77/rollouts
PHASE=${PHASE:-12}

CKPT=checkpoints/moe_v13s/policy_best.pt
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
# the P66 phase-3 / P71 phase-2 / P73 / P74 / P75 / P76 cell, verbatim
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1"

{
    echo "# P77 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + no source change (env-only phase)"
    echo "# prereg: $(tr '\n' ' ' < logs/p77/PREREG.md5)"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/assets.py src/fruit_sorting/conveyor.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/meshes.py src/fruit_sorting/control.py \
        src/fruit_sorting/motion.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        configs/arm_parks.json configs/waypoints.json \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/110_rl_rollout.py scripts/154_claim_run.sh \
        scripts/243_p76_sep_selftest.py scripts/selfcheck.sh
    echo "# arms: C (FRUIT_FINGER_MAXFORCE unset = 10 N) / T (FRUIT_FINGER_MAXFORCE=60)"
    echo "# batch: seeds 77 101 202 x 15 picks, interleaved by seed, order 77 C->T, 101 T->C, 202 C->T"
    echo "# scenario (P66 phase-3 / P71 phase-2 / P73 / P74 / P75 / P76 verbatim): $SCEN_ENV"
    echo "# harness: $HARNESS_ENV"
} > logs/p77/header.txt
cat logs/p77/header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p77] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

arm_env() {
    case "$1" in
        C) echo "FRUIT_FINGER_MAXFORCE=" ;;   # explicit empty = the shipped 10 N
        T) echo "FRUIT_FINGER_MAXFORCE=60" ;;
        *) echo "?"; return 1 ;;
    esac
}

fail=0

# --------------------------------------------------------------------------- #
# Phase 1: the 3-seed interleaved direct batch (the primary + the mechanism)
# --------------------------------------------------------------------------- #
if [[ "$PHASE" == *1* ]]; then
    for pair in "77 C T" "101 T C" "202 C T"; do
        set -- $pair
        seed=$1; shift
        for arm in "$@"; do
            log="logs/p77/direct/${arm}_${seed}.log"
            extra=$(arm_env "$arm") || exit 1
            wait_for_sim
            echo "  [p77] direct $arm (${extra:-FRUIT_FINGER_MAXFORCE unset}) seed $seed start $(date +%H:%M:%S)"
            RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
                $HARNESS_ENV $SCEN_ENV $extra \
                scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
                --presentation direct --episodes 15 --seeds "$seed" \
                --out "logs/p77/rollouts/${arm}_${seed}"
            rc=$?
            echo "  [p77] direct $arm seed $seed exit=$rc $(date +%H:%M:%S)"
            tail -3 "$log"
            [ "$rc" -eq 0 ] || fail=1
        done
    done
fi

# --------------------------------------------------------------------------- #
# Phase 2: the PRICE of an adoption (report only, NO re-record)
# --------------------------------------------------------------------------- #
if [[ "$PHASE" == *2* ]]; then
    # P1: the scripted acceptance at 60 N, against the shipped-cap archive
    # logs/p76/accept_noharm_full.log (346 [fruit] lines, md5 d0079a23).
    wait_for_sim
    echo "  [p77] P1 accept @60N start $(date +%H:%M:%S)"
    SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p77/p1_accept_mf60.log \
        env FRUIT_FINGER_MAXFORCE=60 scripts/accept.sh \
        > logs/p77/p1_accept_mf60.driver 2>&1
    rc=$?
    echo "  [p77] P1 accept @60N exit=$rc $(date +%H:%M:%S)"
    tail -6 logs/p77/p1_accept_mf60.driver
    # a rate-only FAIL is the standing branch; the PRICE is the stream + fingerprint
    [ "$rc" -eq 0 ] || echo "  [p77] P1 exit=$rc (read the driver: rate and/or fingerprint)"

    # P2: the two-line at 60 N, against configs/motion_reference_twoline.json
    # (eb697f23) - no re-record, so a fingerprint mismatch IS the price.
    log="logs/p77/p2_twoline_mf60.log"
    wait_for_sim
    echo "  [p77] P2 twoline @60N start $(date +%H:%M:%S)"
    RUN_LIMIT=2400 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV FRUIT_MOTION_REPORT=1 ATTEMPTS=10 \
        FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 \
        FRUIT_FINGER_MAXFORCE=60 \
        scripts/run.sh scripts/20_pick_place.py
    rc=$?
    echo "  [p77] P2 twoline @60N exit=$rc $(date +%H:%M:%S)"
    if [ -f "$log" ]; then
        scripts/190_twoline_gate.sh "$log" > logs/p77/p2_twoline_mf60.gate 2>&1
        echo "  [p77] P2 gate exit=$? (see logs/p77/p2_twoline_mf60.gate)"
        tail -12 logs/p77/p2_twoline_mf60.gate
    fi
fi

echo "[p77] end $(date '+%F %T') fail=$fail"
exit "$fail"
