#!/usr/bin/env bash
# P43 phase 3 (PREREG L3): the arm park re-measured on the P41 grip-profile tree.
#
#   nohup bash logs/p43/p3/run_batch.sh > logs/p43/p3/batch_outer.log 2>&1 &
#
# The registered design (PREREG_DRAFT.md L3.1, PARK_STATUS.md 2.1):
#
#   A = the shipped direct env (no park)      ARM_A_ENV="FRUIT_ARM_PARK=ready"
#   B = FRUIT_ARM_PARK=back                   ARM_B_ENV="FRUIT_ARM_PARK=back"
#
# both on `checkpoints/moe_v13s/policy_best.pt` (`61da390a`), the P35/P36/P37
# scenario block verbatim (the W6-A/W8-A patch sheet, balanced A:B:C, trigger
# arrival + lead 0.9 + ACQ=1, dynamic pick), N = 5 runs x 15 episodes per arm,
# seeds 77/101/202/303/404, policy seed 11, interleaved A-then-B per seed pair,
# one `scripts/154_claim_run.sh` claim, one instrumentation set on both arms
# (`FRUIT_ACQ_DIAG` / `FRUIT_CARRY_DIAG` / `FRUIT_PARK_DIAG` /
# `FRUIT_RESET_ALIGN_DIAG`, AGENTS 3b: the instrument sits inside the contrast).
#
# Why `moe_v13s` on both arms and not the shipped `moe_v12`: the whole park
# corpus (P35/P36/P37) is on `moe_v13s`, and the hybrid canary
# (`scripts/60_eval_policy.py`) never constructs `SortingRLEnv`, so
# `FRUIT_ARM_PARK` has no code path there - a `moe_v12` park arm would measure a
# configuration that cannot be deployed (PARK_STATUS 2.1/3).
#
# Nothing here writes `configs/`, `datasets/` or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p43/p3

CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCEN_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_DYNAMIC_PICK=1"
DIAG_ENV="FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_PARK_DIAG=1 FRUIT_RESET_ALIGN_DIAG=1"

{
    echo "# P43 phase 3 batch header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/control.py src/fruit_sorting/scene.py \
        src/fruit_sorting/policy/runtime.py src/fruit_sorting/policy/trigger.py \
        src/fruit_sorting/meshes.py src/fruit_sorting/fruits.py \
        configs/arm_parks.json configs/waypoints.json \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/112_rl_ab.sh scripts/113_rl_report.py scripts/154_claim_run.sh \
        logs/p35/park_ab_report.py logs/p37/p37_report.py logs/w7/B_ab_report.py \
        logs/p43/p3/run_batch.sh logs/p43/p3/p3_report.py
    echo "# scenario: $PATCH_ENV $SCEN_ENV $DIAG_ENV"
    echo "# A = FRUIT_ARM_PARK=ready (the pre-park arm, explicit: A2) ; B = FRUIT_ARM_PARK=back ; ckpt=$CKPT on BOTH arms"
    echo "# RUNS=5 EPISODES=15 SEEDS=77/101/202/303/404 policy_seed=11, interleaved A then B"
} > logs/p43/p3/P3_header.txt
cat logs/p43/p3/P3_header.txt

export RUNS=5
export EPISODES=15
export AB_SEEDS="77 101 202 303 404"
export AB_POLICY_SEED=11
export AB_DIR=logs/p43/p3
export ARM_A="--ckpt $CKPT"
export ARM_B="--ckpt $CKPT"
# P43 phase 4 (A2): A is the *pre-park* arm, so it must say so. Since the P43
# flip the direct presentation's default is `back`; an unset `FRUIT_ARM_PARK`
# would make A == B and turn this batch into a park-vs-park null. `ready`
# restores the shipped pose exactly (and is what the P43 phase-3 A arm ran).
export ARM_A_ENV="FRUIT_ARM_PARK=ready"
export ARM_B_ENV="FRUIT_ARM_PARK=back"
export AB_EXTRA_ENV="$PATCH_ENV $SCEN_ENV $DIAG_ENV"

t0=$(date +%s)
echo "[p3] batch start $(date '+%F %T')"
RUN_LIMIT=25200 scripts/154_claim_run.sh logs/p43/p3/batch_driver.log \
    bash -c 'bash scripts/112_rl_ab.sh'
code=$?
t1=$(date +%s)
echo "[p3] batch exit=$code wall=$((t1 - t0))s $(date '+%F %T')"

{
    echo "# P43 phase 3 batch pins after ($(date '+%F %T'))"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/control.py src/fruit_sorting/scene.py \
        configs/arm_parks.json configs/motion_reference.json \
        configs/motion_reference_twoline.json
    echo "# batch wall $((t1 - t0))s"
} > logs/p43/p3/P3_tree_md5_after.txt

echo "[p3] reports"
python3 logs/p43/p3/p3_report.py --dir logs/p43/p3 --a A --b B \
    > logs/p43/p3/P3_report.txt 2>&1
echo "[p3] p3 report exit=$?"
python3 logs/p35/park_ab_report.py --dir logs/p43/p3 --a A --b B \
    > logs/p43/p3/P3_park_ab.txt 2>&1
echo "[p3] P35 park report cross-check exit=$?"
python3 scripts/113_rl_report.py logs/p43/p3 --a A --b B \
    > logs/p43/p3/P3_113.txt 2>&1
echo "[p3] 113 cross-check exit=$?"
echo "[p3] done $(date '+%F %T') batch_exit=$code"
exit "$code"
