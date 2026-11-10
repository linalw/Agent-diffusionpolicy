#!/usr/bin/env bash
# P138 - the canary pair: the init (moe_v13s) vs the fine-tune (p138_track), the
# same interface (the hybrid, which P136 left on the pre-tracker catch), same
# seed, 3 episodes each. A smoke, not a rate.
set -u
cd "$(dirname "$0")/../.." || exit 1
for arm in init cand; do
  ckpt=checkpoints/moe_v13s/policy_best.pt
  [ "$arm" = "cand" ] && ckpt=checkpoints/p138_track/policy_best.pt
  echo "== $arm $ckpt"
  env FRUIT_CKPT="$ckpt" FRUIT_EPISODES=3 SEED=77 SKIP_SELFCHECK=1 \
      ACCEPT_POLICY_LOG="logs/p138/canary_$arm.log" bash scripts/accept_policy.sh \
      > "logs/p138/canary_$arm.out" 2>&1
  grep -aE "success|episodes:|reasons" "logs/p138/canary_$arm.out" | tail -3 | sed 's/^/  /'
done
echo "== done"
