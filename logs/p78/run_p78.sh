#!/usr/bin/env bash
# P78: the **site-scoped** clamp force (left `place*` legs only) and its dose.
#   logs/p78/PREREG.md, md5 01077e1a8d857cbc2f5db1b06dbc5c25 (pinned before any run)
#
#   bash logs/p78/run_p78.sh                 # phase 1 (the 4-cell ladder, seed 77)
#   PHASE=2 RUNG=S60 bash logs/p78/run_p78.sh   # seeds 101/202 for C + one rung
#   PHASE=3 bash logs/p78/run_p78.sh         # the blast radius (scripted + two-line)
#
# The one variable is the **runtime** finger-drive cap the task raises for the
# left arm's `place*` legs (`FRUIT_FINGER_MAXFORCE_SCOPE=place-left`,
# `FRUIT_FINGER_MAXFORCE_SCOPED=<N>`), restored at each leg's end:
#   C   = the scope unset (explicit empty) -> the shipped build-time 10 N cap
#   S30 / S45 / S60 = the scoped cap at 30 / 45 / 60 N
# Nothing is adopted, no default moves, configs/* untouched.
#
# The control runs first in the same stretch, so each treatment cell is read
# against an adjacent control cell; the doses ascend, so a monotone wall-clock
# drift can only load onto the later (higher) arms - stated, not corrected for.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p78/direct logs/p78/rollouts
PHASE=${PHASE:-1}
RUNG=${RUNG:-S60}

CKPT=checkpoints/moe_v13s/policy_best.pt
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
# the P66 phase-3 / P71 phase-2 / P73 / P74 / P75 / P76 / P77 cell, verbatim
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1"

{
    echo "# P78 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the P78 scoped-force change (see the md5s below)"
    echo "# prereg: $(tr '\n' ' ' < logs/p78/PREREG.md5)"
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
    echo "#       S30/S45/S60 (FRUIT_FINGER_MAXFORCE_SCOPE=place-left, ..._SCOPED=30/45/60)"
    echo "# batch: seed 77 x 15 picks, order C -> S30 -> S45 -> S60 (dose ascending)"
    echo "# scenario (P66 phase-3 / P71 phase-2 / P73 / P74 / P75 / P76 / P77 verbatim): $SCEN_ENV"
    echo "# harness: $HARNESS_ENV"
} > logs/p78/header.txt
cat logs/p78/header.txt

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [p78] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

arm_env() {
    case "$1" in
        C) echo "FRUIT_FINGER_MAXFORCE_SCOPE= FRUIT_FINGER_MAXFORCE_SCOPED=" ;;
        S30) echo "FRUIT_FINGER_MAXFORCE_SCOPE=place-left FRUIT_FINGER_MAXFORCE_SCOPED=30" ;;
        S45) echo "FRUIT_FINGER_MAXFORCE_SCOPE=place-left FRUIT_FINGER_MAXFORCE_SCOPED=45" ;;
        S60) echo "FRUIT_FINGER_MAXFORCE_SCOPE=place-left FRUIT_FINGER_MAXFORCE_SCOPED=60" ;;
        *) echo "?"; return 1 ;;
    esac
}

one_cell() {
    local arm=$1 seed=$2 out=$3
    local log="logs/p78/direct/${arm}_${seed}.log"
    local extra rc
    extra=$(arm_env "$arm") || return 1
    wait_for_sim
    echo "  [p78] direct $arm seed $seed start $(date +%H:%M:%S)"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "$log" \
        $HARNESS_ENV $SCEN_ENV $extra \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes 15 --seeds "$seed" --out "$out"
    rc=$?
    echo "  [p78] direct $arm seed $seed exit=$rc $(date +%H:%M:%S)"
    tail -3 "$log"
    return "$rc"
}

fail=0

# --------------------------------------------------------------------------- #
# Phase 1: the dose ladder, seed 77
# --------------------------------------------------------------------------- #
if [[ "$PHASE" == *1* ]]; then
    for arm in C S30 S45 S60; do
        one_cell "$arm" 77 "logs/p78/rollouts/${arm}_77" || fail=1
    done
fi

# --------------------------------------------------------------------------- #
# Phase 2: seeds 101 / 202 for the control and the rung that dominated
# --------------------------------------------------------------------------- #
if [[ "$PHASE" == *2* ]]; then
    for seed in 101 202; do
        for arm in C "$RUNG"; do
            one_cell "$arm" "$seed" "logs/p78/rollouts/${arm}_${seed}" || fail=1
        done
    done
fi

# --------------------------------------------------------------------------- #
# Phase 3: the blast-radius proof (PREREG §4) - the scope ARMED on both
# scripted paths, which must move nothing at all.
# --------------------------------------------------------------------------- #
if [[ "$PHASE" == *3* ]]; then
    ARMED="FRUIT_FINGER_MAXFORCE_SCOPE=place-left FRUIT_FINGER_MAXFORCE_SCOPED=60"
    wait_for_sim
    echo "  [p78] B1 accept.sh with the scope ARMED start $(date +%H:%M:%S)"
    SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p78/b1_accept_armed.log \
        env $ARMED scripts/accept.sh > logs/p78/b1_accept_armed.driver 2>&1
    rc=$?
    echo "  [p78] B1 exit=$rc $(date +%H:%M:%S)"
    tail -6 logs/p78/b1_accept_armed.driver

    wait_for_sim
    echo "  [p78] B2 two-line with the scope ARMED start $(date +%H:%M:%S)"
    RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p78/b2_twoline_armed.log \
        $HARNESS_ENV FRUIT_MOTION_REPORT=1 ATTEMPTS=10 \
        FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 $ARMED \
        scripts/run.sh scripts/20_pick_place.py
    rc=$?
    echo "  [p78] B2 exit=$rc $(date +%H:%M:%S)"
    if [ -f logs/p78/b2_twoline_armed.log ]; then
        scripts/190_twoline_gate.sh logs/p78/b2_twoline_armed.log \
            > logs/p78/b2_twoline_armed.gate 2>&1
        echo "  [p78] B2 gate exit=$? (see logs/p78/b2_twoline_armed.gate)"
        tail -12 logs/p78/b2_twoline_armed.gate
    fi
fi

echo "[p78] end $(date '+%F %T') fail=$fail"
exit "$fail"
