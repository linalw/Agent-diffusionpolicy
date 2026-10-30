#!/usr/bin/env bash
# P68 secondary runs:
#   1. the scripted acceptance with every P68 knob **unset** (no-harm): expect
#      6/10 + `fingerprint: matches` + 377/377 `[fruit]` lines identical to
#      logs/p66/p2/accept_noharm.log (the tree's recorded pear-on branch);
#   2. one **mixed-supply** run of arm A (the P67 *registered* cell's scenario
#      verbatim: A:0.375/B:0.375/C:0.25, 15 picks, seed 77) so the **right**
#      arm's place legs are exercised - the population cell's all-A supply has
#      no right attempt at all, and `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S` is NOT
#      side-scoped (`tasks.py` `_carry`: `hand_is_jaw and
#      _dynamic_capture_active and name.startswith("place")`). The control is
#      P67's own `logs/p67/B_77.log` (same scenario, same seed, the same pair
#      without the hold).
#
#   bash logs/p68/run_p68_extra.sh          # both
#   ONLY=mixed bash logs/p68/run_p68_extra.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p68/rollouts_mixed
ONLY=${ONLY:-all}

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p68] simulator busy (${n}); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

if [ "$ONLY" = "all" ] || [ "$ONLY" = "accept" ]; then
    wait_for_sim
    echo "  [p68] acceptance (knobs unset) start $(date +%H:%M:%S)"
    SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p68/accept_noharm.log \
        scripts/accept.sh > logs/p68/accept_noharm_gate.txt 2>&1
    echo "  [p68] acceptance exit=$? $(date +%H:%M:%S)"
    tail -12 logs/p68/accept_noharm_gate.txt
fi

if [ "$ONLY" = "all" ] || [ "$ONLY" = "mixed" ]; then
    CKPT=checkpoints/moe_v13s/policy_best.pt
    SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1"
    HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
    wait_for_sim
    echo "  [p68] mixed-supply arm A seed 77 start $(date +%H:%M:%S)"
    RUN_LIMIT=3600 scripts/154_claim_run.sh logs/p68/mixed_A_77.log \
        $HARNESS_ENV $SCEN_ENV FRUIT_LIFT_DZ=-0.08 FRUIT_LIFT_CLIMB=0.18 \
        FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S=1.0 \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes 15 --seeds 77 \
        --out logs/p68/rollouts_mixed
    echo "  [p68] mixed-supply arm A exit=$? $(date +%H:%M:%S)"
fi
