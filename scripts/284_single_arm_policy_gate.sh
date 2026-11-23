#!/usr/bin/env bash
# P227z: the single-arm (Franka Panda + two side bins) **learned** lane's gate.
#
#   scripts/284_single_arm_policy_gate.sh [episodes=6] [seed=901] [floor=0.60]
#
# Runs the learned checkpoint through the direct presentation on the bins cell
# and exits 0 only when the placed count is at or above the floor.
#
# The recipe is SIX interface settings, and each one is a measured defect that
# P227z fixed (`logs/p227/RESULTS.md` section 22). Together they take this lane
# from **0/7 to 11/12**:
#
#   FRUIT_CAMERA_RES=240,424          the store's resolution. The scene default
#                                     is 480x848, i.e. a different image scale
#                                     from every demonstration.
#   FRUIT_DIRECT_START_ALIGN=family   the demos' frame 0 is a family in the
#   FRUIT_START_FAMILY=...panda.json  selected fruit's x. `family` is the arm's
#                                     own fit (rms 0.006-0.018 rad); without it
#                                     the episode starts 0.43 rad away.
#   FRUIT_POLICY_ACTION_HOLD=4        the demonstrations were recorded at 30 Hz
#                                     (one frame per 4 control ticks), so a
#                                     chunk replayed one waypoint per tick runs
#                                     4x fast.
#   FRUIT_POLICY_TRIGGER=arrival      the scripted primitive owns the catch and
#                                     the place; the model only approaches.
#                                     With the trigger off the model's own close
#                                     fires at the 0.15 m gate (P143) and the
#                                     catch-up loses the fruit.
#   FRUIT_POLICY_TARGET_RATE=5.45     the emitted joint target is ramped at the
#                                     arm's own maxJointVelocity. The policy's
#                                     per-tick step reaches 0.89 rad, i.e. 20x
#                                     what the joints can deliver, and on real
#                                     hardware an unfollowable step is the
#                                     dangerous motion. Measured 6/6 at the cap.
#   FRUIT_POLICY_JOINT_CLAMP=1       the 7 targets are clipped to the arm's own
#                                     get_dof_limits() (P53 C1: free).
#   FRUIT_SKIP_LATE=0.5              **the cell's ownership rule.** Several arms
#                                     share a line; a fruit already inside the
#                                     window a descent can meet is another arm's,
#                                     so the attempt ends on the tick the trigger
#                                     fires with too little lead instead of
#                                     chasing it (the chase is the only "weird"
#                                     motion the cell shows: failures carry a
#                                     1.18 rad joint range and 44 reversals
#                                     against 0.10 / 9 on placements).
#
# `FRUIT_ARM_KIND=franka`/`FRUIT_OUTPUT_BINS=1` are the cell itself;
# `FRUIT_BIARM=0` keeps the scripted two-line scheduler out of it.
#
# Everything the caller exports is passed through (a checkpoint, an
# instruction, a supply), so this is also the recipe runner:
#
#   FRUIT_POLICY_CKPT=checkpoints/p227_panda156/policy_best.pt \
#   FRUIT_SORT_INSTRUCTION=logs/p227/bins_two_dest.json \
#     scripts/284_single_arm_policy_gate.sh 6 902
#
# The floor is a **branch floor, not a rate** (P93's rule): the loop conditions
# on rendered frames, so two runs of one configuration differ. The measured arms
# are 5/6 (seed 901) and 6/6 (seed 902); 0.60 allows one third of the attempts to
# be a draw, which is the loose end of that spread. A caller wanting the measured
# value passes 0.80.
set -euo pipefail
cd "$(dirname "$0")/.."

episodes="${1:-6}"
seed="${2:-901}"
floor="${3:-0.60}"
ckpt="${FRUIT_POLICY_CKPT:-checkpoints/p227_panda156/policy_best.pt}"
log_dir="${SINGLE_ARM_POLICY_DIR:-logs/p227}"
mkdir -p "$log_dir"
log="$log_dir/policy_cell_$(date +%Y%m%d_%H%M%S)_s${seed}.log"

if [ "${SKIP_SELFCHECK:-0}" != "1" ]; then
    scripts/selfcheck.sh > /dev/null
fi

set +e
FRUIT_ARM_KIND=franka \
FRUIT_OUTPUT_BINS=1 \
FRUIT_BIARM=0 \
FRUIT_CAMERA_RES=240,424 \
FRUIT_DIRECT_START_ALIGN=family \
FRUIT_START_FAMILY=configs/start_pose_family_panda.json \
FRUIT_POLICY_ACTION_HOLD=4 \
FRUIT_POLICY_TRIGGER=arrival \
FRUIT_POLICY_TARGET_RATE=5.45 \
FRUIT_POLICY_JOINT_CLAMP=1 \
FRUIT_SKIP_LATE="${FRUIT_SKIP_LATE:-0.5}" \
    scripts/run.sh scripts/110_rl_rollout.py \
        --presentation direct --episodes "$episodes" --seeds "$seed" --ckpt "$ckpt" \
        > "$log" 2>&1
rc=$?
set -e

rows=$(grep -E '^\[fruit\] \[rl\] episode [0-9]+: [a-z]+ d=.*success=' "$log" || true)
if [ -z "$rows" ]; then
    echo "FAIL: no finished episode rows - the run did not start (rc=$rc, log $log)"
    tail -5 "$log" | sed 's/^/  /'
    exit 1
fi

placed=$(printf '%s\n' "$rows" | grep -c 'success=True' || true)
total=$(printf '%s\n' "$rows" | wc -l | tr -d ' ')

printf '%s\n' "$rows" | sed -E \
    's/^\[fruit\] \[rl\] episode ([0-9]+): ([a-z]+) d=([0-9.]+cm).*success=(\w+) grasped=(\w+) placed=(\w+).*/  ep\1 \2 \3 success=\4 grasped=\5 placed=\6/'
echo "single-arm learned lane: ${placed}/${total} placed, seed ${seed}, ckpt ${ckpt}"

target=$(awk -v f="$floor" -v n="$total" 'BEGIN { printf "%d", f * n + 0.5 }')
if [ "$placed" -lt "$target" ]; then
    echo "FAIL: ${placed}/${total} is below the ${floor} floor (${target}/${total})"
    exit 1
fi
echo "PASS (${placed}/${total} >= floor ${floor}; log ${log})"
