#!/usr/bin/env bash
# P71: the adoption package (logs/p71/RESULTS.md).
#
#   bash logs/p71/run_p71.sh              # phase 1 (scripted) + phase 2 (direct)
#   PHASE=1 bash logs/p71/run_p71.sh      # the scripted pair only
#   PHASE=2 bash logs/p71/run_p71.sh      # the direct batch only
#
# The two shipped flips:
#   * FRUIT_OUTPUT_RAILS  default `both` -> `none`   (assets.SceneConfig)
#   * FRUIT_LIFT_DZ       direct default `+0.08` -> `-0.08`  (rl_env.LIFT_DZ_DIRECT_DEFAULT)
#
# Every arm is one claim. The **control** arms restore the pre-P71 configuration
# explicitly (`FRUIT_OUTPUT_RAILS=both`, `FRUIT_LIFT_DZ=+0.08`), so a moved branch
# can be attributed to the flip and not to the tree: if the control replays the
# archived reference and the treatment does not, the flip is the cause (the
# P40/P41 same-batch precedent).
#
# Phase 1 (scripted, the scene change): the acceptance (10 attempts) and the
# two-line (10 attempts) each run rails-both then rails-default. Phase 2 (direct,
# the lift change): the P66 phase-3 cell verbatim - the registered cell for the
# low lift (left 0/25 -> 14/25 at N=5, right 100/97.8/88.0 %) - 3 seeds x 15
# picks, both flips in effect, with FRUIT_MOTION_REPORT=1 added so the place
# legs carry the G0 contact channel (|a|max).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p71/direct/rollouts logs/p71/twoline
PHASE=${PHASE:-12}

CKPT=checkpoints/moe_v13s/policy_best.pt
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
# the P66 phase-3 cell, verbatim, plus the G0/P70 contact channel
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1"
SEEDS=${SEEDS:-"77 101 202"}

{
    echo "# P71 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the uncommitted P71 flips"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/assets.py \
        src/fruit_sorting/conveyor.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/meshes.py src/fruit_sorting/control.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        configs/arm_parks.json configs/waypoints.json \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/236_p66_lift_selftest.py scripts/238_p70_belt_top_selftest.py \
        scripts/selfcheck.sh
    echo "# flips: FRUIT_OUTPUT_RAILS default none (was both); FRUIT_LIFT_DZ direct default -0.08 (was +0.08)"
    echo "# control arms: FRUIT_OUTPUT_RAILS=both / FRUIT_LIFT_DZ=+0.08 explicitly (the pre-P71 config)"
    echo "# direct scenario (P66 phase 3 verbatim): $SCEN_ENV"
    echo "# direct seeds: $SEEDS x 15 picks, --presentation direct, ckpt=$CKPT, policy seed 11"
} > logs/p71/header.txt
cat logs/p71/header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p71] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

fail=0

# --------------------------------------------------------------------------- #
# Phase 1: the scripted line (rails both = control, then the new default)
# --------------------------------------------------------------------------- #
if [[ "$PHASE" == *1* ]]; then
    for arm in both none; do
        if [ "$arm" = both ]; then rails="FRUIT_OUTPUT_RAILS=both"; else rails=""; fi
        wait_for_sim
        echo "  [p71] accept $arm start $(date +%H:%M:%S)"
        SKIP_SELFCHECK=1 ACCEPT_LOG="logs/p71/accept_rails_${arm}.log" \
            env $rails scripts/accept.sh > "logs/p71/accept_rails_${arm}.driver" 2>&1
        rc=$?
        echo "  [p71] accept $arm exit=$rc $(date +%H:%M:%S)"
        tail -4 "logs/p71/accept_rails_${arm}.driver"
    done

    for arm in both none; do
        if [ "$arm" = both ]; then rails="FRUIT_OUTPUT_RAILS=both"; else rails=""; fi
        log="logs/p71/twoline/${arm}.log"
        wait_for_sim
        echo "  [p71] twoline $arm start $(date +%H:%M:%S)"
        RUN_LIMIT=1800 scripts/154_claim_run.sh "$log" \
            $HARNESS_ENV FRUIT_MOTION_REPORT=1 ATTEMPTS=10 \
            FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 $rails \
            scripts/run.sh scripts/20_pick_place.py
        rc=$?
        echo "  [p71] twoline $arm exit=$rc $(date +%H:%M:%S)"
        [ "$rc" -eq 0 ] || fail=1
    done
fi

# --------------------------------------------------------------------------- #
# Phase 2: the direct line, both flips in effect (the P66 phase-3 cell)
# --------------------------------------------------------------------------- #
if [[ "$PHASE" == *2* ]]; then
    for seed in $SEEDS; do
        for arm in ctrl treat; do
            if [ "$arm" = ctrl ]; then
                extra="FRUIT_OUTPUT_RAILS=both FRUIT_LIFT_DZ=+0.08"
            else
                extra=""
            fi
            log="logs/p71/direct/${arm}_${seed}.log"
            wait_for_sim
            echo "  [p71] direct $arm seed $seed start $(date +%H:%M:%S)"
            RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
                $HARNESS_ENV $SCEN_ENV $extra \
                scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
                --presentation direct --episodes 15 --seeds "$seed" \
                --out logs/p71/direct/rollouts
            rc=$?
            echo "  [p71] direct $arm seed $seed exit=$rc $(date +%H:%M:%S)"
            [ "$rc" -eq 0 ] || fail=1
        done
    done
fi

echo "[p71] end $(date '+%F %T') fail=$fail"
exit "$fail"
