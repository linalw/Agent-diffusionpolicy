#!/usr/bin/env bash
# P79: **where** P77's 60 N count win comes from - the pick or the place - and at
# what force. The lever is the P78 runtime finger-drive cap, scoped to the left
# arm's **`grasp_lift`** leg only (`FRUIT_FINGER_MAXFORCE_SCOPE=grasp-left`), so
# the place transfer runs at the shipped cap.
#   logs/p79/PREREG.md, md5 0cdfd227267400e1c2ef79a94a32775c (pinned before any run)
#
#   SMOKE=1 bash logs/p79/run_p79.sh          # 2-episode manipulation pre-check (not a cell)
#   PHASE=1 bash logs/p79/run_p79.sh          # seed 77: C -> G30 -> G60
#   PHASE=2 bash logs/p79/run_p79.sh          # seeds 101/202, interleaved C -> G30 -> G60
#   PHASE=3 bash logs/p79/run_p79.sh          # the blast radius (armed scripted + two-line)
#
# The one variable is the **runtime** finger-drive cap the task raises for the
# left arm's `grasp_lift` leg (`FRUIT_FINGER_MAXFORCE_SCOPED=<N>`), restored at
# the leg's end:
#   C   = the scope unset (explicit empty) -> the shipped build-time 10 N cap
#   G30 / G60 = the lift-only cap at 30 / 60 N
# Nothing is adopted, no default moves, configs/* untouched, no reference is
# re-recorded. The global arm is P77's record and the place arm P78's - neither
# is re-run (PREREG §3).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p79/direct logs/p79/rollouts
PHASE=${PHASE:-1}
SMOKE=${SMOKE:-0}

CKPT=checkpoints/moe_v13s/policy_best.pt
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
# the P66 phase-3 / P71 phase-2 / P73 / P74 / P75 / P76 / P77 / P78 cell, verbatim
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1"

{
    echo "# P79 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the P79 grasp-left scope (see the md5s below)"
    echo "# prereg: $(tr '\n' ' ' < logs/p79/PREREG.md5)"
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
        scripts/244_p78_scope_selftest.py scripts/selfcheck.sh
    echo "# arms: C (scope unset = the shipped 10 N build cap)"
    echo "#       G30/G60 (FRUIT_FINGER_MAXFORCE_SCOPE=grasp-left, ..._SCOPED=30/60)"
    echo "#       the global 60 N arm is P77's record; the place-only arm P78's - not re-run"
    echo "# batch: seeds 77/101/202 x 15 picks, interleaved within a seed C -> G30 -> G60"
    echo "# scenario (P66 phase-3 / P71 phase-2 / P73 / P74 / P75 / P76 / P77 / P78 verbatim): $SCEN_ENV"
    echo "# harness: $HARNESS_ENV"
} > "logs/p79/header_phase${PHASE}${SMOKE}.txt"
cat "logs/p79/header_phase${PHASE}${SMOKE}.txt"

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p79] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

arm_env() {
    case "$1" in
        C) echo "FRUIT_FINGER_MAXFORCE_SCOPE= FRUIT_FINGER_MAXFORCE_SCOPED=" ;;
        G30) echo "FRUIT_FINGER_MAXFORCE_SCOPE=grasp-left FRUIT_FINGER_MAXFORCE_SCOPED=30" ;;
        G60) echo "FRUIT_FINGER_MAXFORCE_SCOPE=grasp-left FRUIT_FINGER_MAXFORCE_SCOPED=60" ;;
        *) echo "?"; return 1 ;;
    esac
}

one_cell() {
    local arm=$1 seed=$2 out=$3 episodes=${4:-15}
    local log="logs/p79/direct/${arm}_${seed}.log"
    local extra rc
    extra=$(arm_env "$arm") || return 1
    wait_for_sim
    echo "  [p79] direct $arm seed $seed start $(date +%H:%M:%S)"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV $SCEN_ENV $extra \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes "$episodes" --seeds "$seed" --out "$out"
    rc=$?
    echo "  [p79] direct $arm seed $seed exit=$rc $(date +%H:%M:%S)"
    tail -3 "$log"
    return "$rc"
}

fail=0

# --------------------------------------------------------------------------- #
# Smoke: the manipulation pre-check (NOT a cell - PREREG §3)
# --------------------------------------------------------------------------- #
if [ "$SMOKE" = "1" ]; then
    one_cell G60 77 logs/p79/rollouts/smoke_77 2 || fail=1
    echo "[p79] smoke done $(date '+%F %T')"
    exit "$fail"
fi

# --------------------------------------------------------------------------- #
# Phase 1: seed 77, C -> G30 -> G60
# --------------------------------------------------------------------------- #
if [[ "$PHASE" == *1* ]]; then
    for arm in C G30 G60; do
        one_cell "$arm" 77 "logs/p79/rollouts/${arm}_77" || fail=1
    done
fi

# --------------------------------------------------------------------------- #
# Phase 2: seeds 101 / 202, interleaved within each seed
# --------------------------------------------------------------------------- #
if [[ "$PHASE" == *2* ]]; then
    for seed in 101 202; do
        for arm in C G30 G60; do
            one_cell "$arm" "$seed" "logs/p79/rollouts/${arm}_${seed}" || fail=1
        done
    done
fi

# --------------------------------------------------------------------------- #
# Phase 3: the blast-radius proof (PREREG §8) - the scope ARMED on both
# scripted paths, which must move nothing at all.
# --------------------------------------------------------------------------- #
if [[ "$PHASE" == *3* ]]; then
    ARMED="FRUIT_FINGER_MAXFORCE_SCOPE=grasp-left FRUIT_FINGER_MAXFORCE_SCOPED=60"
    wait_for_sim
    echo "  [p79] B1 accept.sh with the scope ARMED start $(date +%H:%M:%S)"
    SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p79/b1_accept_armed.log \
        env $ARMED scripts/accept.sh > logs/p79/b1_accept_armed.driver 2>&1
    rc=$?
    echo "  [p79] B1 exit=$rc $(date +%H:%M:%S)"
    tail -6 logs/p79/b1_accept_armed.driver

    wait_for_sim
    echo "  [p79] B2 two-line with the scope ARMED start $(date +%H:%M:%S)"
    RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p79/b2_twoline_armed.log \
        $HARNESS_ENV FRUIT_MOTION_REPORT=1 ATTEMPTS=10 \
        FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 $ARMED \
        scripts/run.sh scripts/20_pick_place.py
    rc=$?
    echo "  [p79] B2 exit=$rc $(date +%H:%M:%S)"
    if [ -f logs/p79/b2_twoline_armed.log ]; then
        scripts/190_twoline_gate.sh logs/p79/b2_twoline_armed.log \
            > logs/p79/b2_twoline_armed.gate 2>&1
        echo "  [p79] B2 gate exit=$? (see logs/p79/b2_twoline_armed.gate)"
        tail -12 logs/p79/b2_twoline_armed.gate
    fi
fi

echo "[p79] end $(date '+%F %T') fail=$fail"
exit "$fail"
