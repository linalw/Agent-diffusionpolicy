#!/usr/bin/env bash
# A policy A/B that means something: N runs per arm, back to back, one session.
#
#   scripts/140_policy_ab.sh                     # 12 episodes x 3 runs per arm
#   EPISODES=12 RUNS=2 scripts/140_policy_ab.sh
#   ARM_A="FRUIT_CLOSE_ON_EXTENT=0" ARM_B="FRUIT_CLOSE_ON_EXTENT=1" scripts/140_policy_ab.sh
#
# Why it is built this way (WORKLOG "the hybrid loop's variation is the rendered
# frames"): the policy loop is outcome-stable but *not* bit-reproducible, because the
# policy conditions on rendered frames and RTX rendering varies run to run. A single
# run per arm therefore proves nothing, and the statistic to aggregate is the
# per-episode outcome, not a continuous quantity like peak lift. So: several runs per
# arm, in one session, with the sampler seeded, then compare the arms' per-episode
# success rates and their spread.
#
# Both arms run the small-fruit pool by default, because that is where the difference
# under test (the closing target) lives: a strawberry's extent along the closing axis
# is well under its nominal diameter while a lychee's is exact.
set -uo pipefail

cd "$(dirname "$0")/.."

episodes=${EPISODES:-12}
runs=${RUNS:-3}
seed=${AB_SEED:-11}
arm_a=${ARM_A:-"FRUIT_CLOSE_ON_EXTENT=0"}
arm_b=${ARM_B:-"FRUIT_CLOSE_ON_EXTENT=1"}
out=${AB_DIR:-logs/policy_ab}
size=${AB_SIZE_FILTER:-small}
ckpt=${FRUIT_CKPT:-checkpoints/policy_kin_v3all/policy_best.pt}
#: Extra environment for both arms, e.g. `FRUIT_CLOSURE_DEBUG=1` to record the grip
#: geometry alongside the outcomes (one set of runs then answers both "which arm wins"
#: and "why").
extra=${AB_EXTRA_ENV:-}

mkdir -p "$out"
echo "policy A/B: ${episodes} episodes x ${runs} runs per arm, seed=${seed}, pool=${size}"
echo "  arm A: ${arm_a}"
echo "  arm B: ${arm_b}"

run_arm() {
    local label=$1 envs=$2 i log
    for i in $(seq 1 "$runs"); do
        log="$out/${label}_${i}.log"
        env $envs HEADLESS=1 FRUIT_HYBRID_EVAL=1 FRUIT_SIZE_FILTER="$size" \
            FRUIT_POLICY_SEED="$seed" FRUIT_CKPT="$ckpt" FRUIT_EPISODES="$episodes" \
            $extra \
            scripts/run.sh scripts/60_eval_policy.py > "$log" 2>&1
        printf '  %s run %d: %s\n' "$label" "$i" \
            "$(grep -oE 'policy success [0-9]+/[0-9]+' "$log" | tail -1)"
    done
}

run_arm A "$arm_a"
run_arm B "$arm_b"

python3 scripts/141_policy_ab_report.py "$out" --runs "$runs"
