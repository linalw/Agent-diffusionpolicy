#!/usr/bin/env bash
# P56 phase 2: the knob-off baseline, recorded **before** the `src/` edit, so the
# refactor of `reset` -> `_begin_pick` can be checked byte-for-byte afterwards.
#
#   bash logs/p56/p0/base_before.sh
#
# Two runs, both on the P54/P43 protocol scenario (arm A's shape: the feeder
# explicit, the population defaults of the P54 flip):
#   S_scripted  `--ablate scripted --episodes 1`  - deterministic (fixed stepping)
#               and it exercises exactly the two functions the refactor moves
#               (`reset` and `_finalize`), so THIS is the byte-identity gate.
#   P_policy    `--ablate none --episodes 1`      - the same path with the model in
#               the loop; the rendered frames make the policy loop
#               non-reproducible (AGENTS section 3b), so it is recorded as a
#               shape/instrument check, not as a bit-identity claim.
#
# No `FRUIT_BED_DIAG` and no `FRUIT_DIRECT_CONTINUOUS` here on purpose: this run
# is the *pre-change* tree, where neither is read, and the post-change re-run
# must use the identical command line.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p56/p0

CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCEN_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1"
FIX_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_POLICY_SEED=11 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
ARM_A="FRUIT_DIRECT_FEED=1"

{
    echo "# P56 phase 2 pre-change baseline ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    md5sum "$CKPT" src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        src/fruit_sorting/policy/runtime.py src/fruit_sorting/policy/trigger.py \
        scripts/110_rl_rollout.py
    echo "# scenario: $PATCH_ENV $SCEN_ENV"
    echo "# arm A env: $ARM_A   (population defaults: ACQ on, park back)"
} > logs/p56/p0/P0_before_header.txt
cat logs/p56/p0/P0_before_header.txt

run_one() {
    local label=$1; shift
    echo "[p0] $label start $(date '+%F %T')"
    # shellcheck disable=SC2086
    RUN_LIMIT=1800 scripts/154_claim_run.sh "logs/p56/p0/${label}.log" \
        $PATCH_ENV $SCEN_ENV $FIX_ENV $ARM_A \
        scripts/run.sh scripts/110_rl_rollout.py --presentation direct \
        --episodes 1 --seeds 77 "$@"
    echo "[p0] $label exit=$? $(date '+%F %T')"
}

run_one S_scripted --ablate scripted --ckpt "$CKPT"
run_one P_policy --ablate none --ckpt "$CKPT"
echo "[p0] done $(date '+%F %T')"
