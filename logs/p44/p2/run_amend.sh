#!/usr/bin/env bash
# P44 phase 2 AMEND (Oracle): S1 first, then S3-v (lift v only), S2 last.
#
#   bash logs/p44/p2/run_amend.sh E    # C, S1, S3v   (+ FRUIT_CARRY_DIAG=1 on all arms)
#   bash logs/p44/p2/run_amend.sh F    # C, S2        (+ CARRY_DIAG + RELEASE_DEBUG + PLACE_TRACE)
#
# Existing knobs only, no `src/` edit:
#   S1   FRUIT_DYNAMIC_PLACE_VMAX=0.52           place 0.35 -> 0.52, `a` untouched (1.089)
#   S3v  FRUIT_DYNAMIC_LIFT_VMAX=0.37            lift 0.30 -> 0.37 **v only**, `a` untouched (1.0)
#   S2   FRUIT_RELEASE_DWELL=0 PAD_HOLD=1 FINGER_HOLD=1
#                                                the release clock's **floor** form (the holds are
#                                                opening RATES: 40- and 16-step ramps x the hold)
#
# Instrumentation sits inside every contrast (AGENTS 3b): `FRUIT_CARRY_DIAG=1`
# on every arm (E4's `[carry]` row carries `clean_slip_max`, `force_min`,
# `loss_row`, `sep@loss`), and battery F adds `FRUIT_RELEASE_DEBUG=1` +
# `FRUIT_PLACE_TRACE=1` on both of its arms (the release cut's landing check).
#
# Acceptance scenario, seed 5, 10 attempts - the same branch phase 2 read, so the
# per-leg tick deltas are comparable. One claim per run, strictly sequential.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
BATTERY=${1:?usage: run_amend.sh E|F}
OUT=logs/p44/p2
mkdir -p "$OUT"
CLAIM=scripts/154_claim_run.sh
PICK="scripts/run.sh scripts/20_pick_place.py"
BASE="HEADLESS=1 ATTEMPTS=10 SEED=5 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1"

case "$BATTERY" in
    E) ARMS=(C S1 S3v); EXTRA="" ;;
    F) ARMS=(C S2); EXTRA="FRUIT_RELEASE_DEBUG=1 FRUIT_PLACE_TRACE=1" ;;
    *) echo "[amend] unknown battery $BATTERY" >&2; exit 2 ;;
esac

{
    echo "# P44 phase 2 amend battery $BATTERY ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/control.py src/fruit_sorting/scene.py \
        src/fruit_sorting/motion.py configs/motion_reference.json \
        configs/motion_reference_twoline.json
    echo "# scenario: $BASE $EXTRA"
    echo "# arms: ${ARMS[*]}"
} | tee -a "$OUT/amend_header.txt"

for arm in "${ARMS[@]}"; do
    case "$arm" in
        C)   ARM_ENV="" ;;
        S1)  ARM_ENV="FRUIT_DYNAMIC_PLACE_VMAX=0.52" ;;
        S3v) ARM_ENV="FRUIT_DYNAMIC_LIFT_VMAX=0.37" ;;
        S2)  ARM_ENV="FRUIT_RELEASE_DWELL=0 FRUIT_RELEASE_PAD_HOLD=1 FRUIT_RELEASE_FINGER_HOLD=1" ;;
        *)   echo "[amend] unknown arm $arm" >&2; exit 2 ;;
    esac
    log="$OUT/amend_${BATTERY}_${arm}.log"
    t0=$(date +%s)
    # shellcheck disable=SC2086
    env RUN_LIMIT=1500 "$CLAIM" "$log" $BASE $EXTRA $ARM_ENV $PICK
    echo "[amend] $BATTERY $arm exit=$? wall=$(( $(date +%s) - t0 ))s $(date '+%H:%M:%S') log=$log"
done
echo "[amend] battery $BATTERY all done $(date '+%H:%M:%S')"
