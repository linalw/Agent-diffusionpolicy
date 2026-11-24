#!/usr/bin/env bash
# P260: the **deployment cell** - the single-arm learned lane in its continuous
# shape, one command, reproducible.
#
#   scripts/290_single_arm_continuous.sh [picks=20] [seed=905] [speed=0.08]
#
# This is the recipe every number in `docs/SINGLE_ARM_SPEC.md` section 2 was
# measured with. It wraps `scripts/110_rl_rollout.py --continuous`, and its
# settings fall into three groups, each with the phase that measured it:
#
#   the cell
#     FRUIT_ARM_KIND=franka FRUIT_OUTPUT_BINS=1 FRUIT_BIARM=0
#     FRUIT_CAMERA_RES=240,424          the store's resolution (P227z)
#     FRUIT_DIRECT_START_ALIGN=family   the demos' frame-0 family (P227y)
#     FRUIT_START_FAMILY=configs/start_pose_family_panda.json
#
#   the interface (each one a measured defect, P227z)
#     FRUIT_POLICY_ACTION_HOLD=4        the demos are 30 Hz (P145b)
#     FRUIT_POLICY_TRIGGER=arrival      the primitive owns the catch (P143)
#     FRUIT_POLICY_TARGET_RATE=5.45     the arm's own maxJointVelocity (P207)
#     FRUIT_POLICY_JOINT_CLAMP=1        P53 C1, free
#     FRUIT_EVAL_LATENCY=auto           P228: a d=0 cell reports a latency this
#                                       machine does not have
#
#   the deployment shape
#     --continuous <picks>              no per-pick reset: the return transit
#                                       instead of the teleport (P225n)
#     FRUIT_CONTINUOUS_TRANSIT=1        ... which is only on with this
#     FRUIT_SKIP_LATE=0                 **single-arm**: the multi-arm handoff
#                                       rule discards here (P252 section 6)
#     FRUIT_RELEASE_PAD_HOLD=1          (P260) the pad/finger ramps at one tick
#     FRUIT_RELEASE_FINGER_HOLD=1       per step: `release` 2.17 -> 1.70 s,
#                                       39/40 placed, the one loss at the grasp
#     FRUIT_CYCLE_REPORT=1              the block report
#
# Everything the caller exports is passed through (a checkpoint, an instruction,
# a profit), so this is also the runner for a different pool or a different
# acceptance instruction.
#
# **Two levers are the shipped defaults and are therefore not named here**: the
# catch-up's axis-aware exit (`FRUIT_CATCH_TOL_AXIS`, on for the direct
# presentation since P249) and the place blend (`FRUIT_PLACE_BLEND_TICKS=90`,
# the Panda-only block, P259).
set -euo pipefail
cd "$(dirname "$0")/.."

picks="${1:-20}"
seed="${2:-905}"
speed="${3:-0.08}"
ckpt="${FRUIT_POLICY_CKPT:-checkpoints/p227_panda156/policy_best.pt}"
log_dir="${CONTINUOUS_LOG_DIR:-logs/single_arm_continuous}"
mkdir -p "$log_dir"
log="${CONTINUOUS_LOG:-$log_dir/cont${picks}_s${seed}_v${speed}.log}"

if [ "${SKIP_SELFCHECK:-0}" != "1" ]; then
    scripts/selfcheck.sh > /dev/null
fi

set +e
FRUIT_ARM_KIND=franka \
FRUIT_OUTPUT_BINS=1 \
FRUIT_BIARM=0 \
FRUIT_CAMERA_RES=240,424 \
FRUIT_BELT_SPEED="$speed" \
FRUIT_DIRECT_START_ALIGN=family \
FRUIT_START_FAMILY=configs/start_pose_family_panda.json \
FRUIT_POLICY_ACTION_HOLD=4 \
FRUIT_POLICY_TRIGGER=arrival \
FRUIT_POLICY_TARGET_RATE=5.45 \
FRUIT_POLICY_JOINT_CLAMP=1 \
FRUIT_EVAL_LATENCY=auto \
FRUIT_CONTINUOUS_TRANSIT=1 \
FRUIT_SKIP_LATE="${FRUIT_SKIP_LATE:-0}" \
FRUIT_RELEASE_PAD_HOLD="${FRUIT_RELEASE_PAD_HOLD:-1}" \
FRUIT_RELEASE_FINGER_HOLD="${FRUIT_RELEASE_FINGER_HOLD:-1}" \
FRUIT_CYCLE_REPORT=1 \
    scripts/run.sh scripts/110_rl_rollout.py \
        --presentation direct --episodes 1 --continuous "$picks" \
        --seeds "$seed" --ckpt "$ckpt" \
        > "$log" 2>&1
rc=$?
set -e

placed=$(grep -oE 'picks placed [0-9]+/[0-9]+' "$log" | tail -1 || true)
if [ -z "$placed" ]; then
    echo "FAIL: no 'picks placed' row - the run did not finish (rc=$rc, log $log)"
    tail -5 "$log" | sed 's/^/  /'
    exit 1
fi
echo "deployment cell: $placed  seed=$seed speed=$speed picks=$picks  ($log)"

# the per-pick ledger, so a loss names its species and its own note
python3 "logs/p253/p253_report.py" "$log" 2>/dev/null || true
