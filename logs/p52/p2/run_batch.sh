#!/usr/bin/env bash
# P52 phase 2, lane A: the contact-gated action time-scale on the direct policy.
#
#   nohup bash logs/p52/p2/run_batch.sh > logs/p52/p2/batch_outer.log 2>&1 &
#
# The registered design (`logs/p52/PREREG_DRAFT.md` section 1, `.slim/deepwork/
# p52-model-lane.md` phase 2), re-scoped by the owner's task to the contact-gated
# cell only:
#
#   T0 = the shipped direct env                     (both knobs unset)
#   TG = FRUIT_POLICY_TIME_SCALE=1.5 FRUIT_POLICY_RETIME_GATE=1
#
# Both on `checkpoints/moe_v13s/policy_best.pt` (`61da390a`), the P43 phase-3
# scenario block verbatim (the W6-A/W8-A patch sheet, balanced A:B:C, trigger
# arrival + lead 0.9 + ACQ=1, dynamic pick), N = 3 runs x 15 episodes per arm,
# seeds 77/101/202, policy seed 11, interleaved T0-then-TG per seed pair, one
# `scripts/154_claim_run.sh` claim, one instrumentation set on both arms
# (FRUIT_ACQ_DIAG / FRUIT_CARRY_DIAG / FRUIT_PARK_DIAG / FRUIT_RESET_ALIGN_DIAG,
# AGENTS.md section 3b: the instrument sits inside the contrast).
#
# Why `moe_v13s` on both arms: the whole park corpus (P35/P36/P37/P43) is
# `moe_v13s`, and the park is the shipped direct default since P43 - a `moe_v12`
# arm could not be compared to the 94.6 % record. `FRUIT_ARM_PARK` is left unset
# on both arms, i.e. the direct presentation's resolved default (`back`).
#
# Nothing here writes `configs/`, `datasets/` or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p52/p2

CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCEN_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_DYNAMIC_PICK=1"
DIAG_ENV="FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_PARK_DIAG=1 FRUIT_RESET_ALIGN_DIAG=1"

{
    echo "# P52 phase 2 lane A batch header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    md5sum "$CKPT" \
        src/fruit_sorting/rl_env.py \
        src/fruit_sorting/tasks.py src/fruit_sorting/control.py \
        src/fruit_sorting/scene.py src/fruit_sorting/policy/runtime.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/meshes.py \
        src/fruit_sorting/fruits.py \
        configs/arm_parks.json configs/waypoints.json \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/112_rl_ab.sh scripts/113_rl_report.py scripts/154_claim_run.sh \
        scripts/228_p52_retime_selftest.py \
        logs/p52/p2/run_batch.sh logs/p52/p2/p2a_report.py
    echo "# scenario: $PATCH_ENV $SCEN_ENV $DIAG_ENV"
    echo "# T0 = the shipped direct env (FRUIT_POLICY_TIME_SCALE unset); TG = FRUIT_POLICY_TIME_SCALE=1.5 FRUIT_POLICY_RETIME_GATE=1 ; ckpt=$CKPT on BOTH arms"
    echo "# park: unset on both arms = the direct presentation's resolved default (back)"
    echo "# RUNS=3 EPISODES=15 SEEDS=77/101/202 policy_seed=11, interleaved T0 then TG"
} > logs/p52/p2/P2A_header.txt
cat logs/p52/p2/P2A_header.txt

export RUNS=3
export EPISODES=15
export AB_SEEDS="77 101 202"
export AB_POLICY_SEED=11
export AB_DIR=logs/p52/p2
export ARM_A="--ckpt $CKPT"
export ARM_B="--ckpt $CKPT"
export ARM_A_ENV=""
export ARM_B_ENV="FRUIT_POLICY_TIME_SCALE=1.5 FRUIT_POLICY_RETIME_GATE=1"
export AB_EXTRA_ENV="$PATCH_ENV $SCEN_ENV $DIAG_ENV"

t0=$(date +%s)
echo "[p2a] batch start $(date '+%F %T')"
RUN_LIMIT=28800 scripts/154_claim_run.sh logs/p52/p2/batch_driver.log \
    bash -c 'bash scripts/112_rl_ab.sh'
code=$?
t1=$(date +%s)
echo "[p2a] batch exit=$code wall=$((t1 - t0))s $(date '+%F %T')"

{
    echo "# P52 phase 2 lane A pins after ($(date '+%F %T'))"
    md5sum "$CKPT" \
        src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json
    echo "# batch wall $((t1 - t0))s exit=$code"
} > logs/p52/p2/P2A_tree_md5_after.txt

echo "[p2a] reports"
python3 logs/p52/p2/p2a_report.py --dir logs/p52/p2 --a A --b B \
    > logs/p52/p2/P2A_report.txt 2>&1
echo "[p2a] p2a report exit=$?"
python3 scripts/113_rl_report.py logs/p52/p2 --a A --b B \
    > logs/p52/p2/P2A_113.txt 2>&1
echo "[p2a] 113 cross-check exit=$?"
echo "[p2a] done $(date '+%F %T') batch_exit=$code"
exit "$code"
