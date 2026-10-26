#!/usr/bin/env bash
# P44 phase 2 batch: the speed cells, arms interleaved C -> S1 -> S2 -> S3 -> S13.
#
#   bash logs/p44/p2/run_batch.sh A        # acceptance seed 5   (5 arms)
#   bash logs/p44/p2/run_batch.sh B        # acceptance seed 6   (5 arms)
#   bash logs/p44/p2/run_batch.sh C        # pear seed 5         (5 arms)
#   bash logs/p44/p2/run_batch.sh D        # two-line dense      (5 arms)
#
# One `scripts/154_claim_run.sh` claim per run, strictly sequential (one
# simulator). One instrumentation set on every arm (`FRUIT_MOTION_REPORT=1`
# `FRUIT_CYCLE_REPORT=1` - both proven run-neutral on these scenarios: P43's
# `d0_accept_A_s5` is byte-identical to `post_revert_accept_unset`), so the
# instrument sits inside the contrast (AGENTS 3b). No carry diag here: the
# pillar is the *guard* (any new `fruit did not follow the gripper` row), which
# the neutral instruments measure exactly; the force detail is a follow-up run
# on a failing cell only.
#
#   C    = the shipped tree (unset)              -> must be byte-identical to
#                                                 logs/p43/p2/post_revert_accept_unset.log
#   S1   = FRUIT_SPEED_PLACE=0.52                place v_max 0.35 -> 0.52 (a stays 1.089)
#   S2   = FRUIT_SPEED_RELEASE=1                 dwell 20 -> 0, pad/finger 3 -> 2
#   S3   = FRUIT_SPEED_LIFT=0.36                 lift 0.30/1.0 -> 0.36/1.9
#   S13  = FRUIT_SPEED_ALL=1                     the union (the adoption candidate)
#
# Nothing here writes `configs/`, `datasets/` or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
BATTERY=${1:?usage: run_batch.sh A|B|C|D}
OUT=logs/p44/p2
mkdir -p "$OUT"

CLAIM=scripts/154_claim_run.sh
PICK="scripts/run.sh scripts/20_pick_place.py"
BASE="HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1"
# `P44_ARMS` overrides the arm list (S1 is dropped from batteries B-D after the
# E4 guard fired on it in battery A - PREREG F1: a cell with a new grip-loss row
# is stopped, not carried on).
read -r -a ARMS <<< "${P44_ARMS:-C S1 S2 S3 S13}"

case "$BATTERY" in
    A) SEED=5; SCEN=""; PREFIX=accept_s5 ;;
    B) SEED=6; SCEN=""; PREFIX=accept_s6 ;;
    C) SEED=5; SCEN="FRUIT_SUPPLY_SPECIES=pear"; PREFIX=pear_s5 ;;
    D) SEED=5; SCEN="FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1"; PREFIX=twoline_s5 ;;
    *) echo "[batch] unknown battery $BATTERY" >&2; exit 2 ;;
esac


{
    echo "# P44 phase 2 battery $BATTERY header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/control.py src/fruit_sorting/scene.py \
        src/fruit_sorting/motion.py src/fruit_sorting/fruits.py \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/225_p44_speed_selftest.py scripts/selfcheck.sh
    echo "# scenario: $BASE SEED=$SEED $SCEN"
    echo "# arms (interleaved): ${ARMS[*]}"
} | tee -a "$OUT/batch_header.txt"

for arm in "${ARMS[@]}"; do
    case "$arm" in
        C)   ARM_ENV="" ;;
        S1)  ARM_ENV="FRUIT_SPEED_PLACE=0.52" ;;
        S2)  ARM_ENV="FRUIT_SPEED_RELEASE=1" ;;
        S3)  ARM_ENV="FRUIT_SPEED_LIFT=0.36" ;;
        S13) ARM_ENV="FRUIT_SPEED_ALL=1" ;;
        *)   echo "[batch] unknown arm $arm" >&2; exit 2 ;;
    esac
    log="$OUT/${PREFIX}_${arm}.log"
    t0=$(date +%s)
    # shellcheck disable=SC2086
    env RUN_LIMIT=1500 "$CLAIM" "$log" $BASE SEED="$SEED" $SCEN $ARM_ENV $PICK
    code=$?
    echo "[batch] $BATTERY $arm exit=$code wall=$(( $(date +%s) - t0 ))s $(date '+%H:%M:%S') log=$log"
done

echo "[batch] battery $BATTERY all done $(date '+%H:%M:%S')"
