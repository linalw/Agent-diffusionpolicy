#!/usr/bin/env bash
# P37 phase 2 step 2: the N = 5 x 15 adoption A/B (both arms parked) + the report.
#
#   nohup bash scripts/223_p37_ab.sh > logs/p37/B_outer.log 2>&1 &
#
# The pre-registration is `logs/p37/PREREG.md` section 5, the phase-2 contract:
# A = `checkpoints/moe_v13s/policy_best.pt` (`61da390a`), B =
# `checkpoints/p37_park/policy_best.pt` (the park-collected fine-tune), **both
# arms parked** (`FRUIT_ARM_PARK=back`, the deployment configuration), the
# PREREG section-2 scenario block verbatim, N = 5 runs x 15 episodes, seeds
# 77/101/202/303/404, sampler seed 11, A-then-B inside each run, one
# `scripts/154_claim_run.sh` claim, the same instrumentation on both arms
# (`FRUIT_ACQ_DIAG` / `FRUIT_CARRY_DIAG` / `FRUIT_PARK_DIAG`, AGENTS 3b).
#
# The gate is `logs/p37/p37_report.py` (H1/H2): the pooled right-arm placed
# non-inferiority at margin 0.10, S1-S5, the exact p/interval and the realized
# n. `scripts/113_rl_report.py` and `logs/p35/park_ab_report.py` are run beside
# it as cross-checks; **they are not the gate** (113 tests improvement, which
# the base's ~94 % ceiling cannot deliver; the P35 report's M1-applied reads
# `q_settled`, the P37 H2 reads the row's own `q`).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/p37/B_ab

CKPT_A=checkpoints/moe_v13s/policy_best.pt
CKPT_B=checkpoints/p37_park/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCEN_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_DYNAMIC_PICK=1"
DIAG_ENV="FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_PARK_DIAG=1"

for f in "$CKPT_A" "$CKPT_B" logs/p37/fidelity.txt logs/p37/p37_report.py; do
    if [ ! -f "$f" ]; then echo "[p37ab] FAIL: missing $f - run scripts/222_p37_finetune.sh first"; exit 1; fi
done

{
    echo "# P37 phase 2 batch header ($(date '+%F %T'))"
    echo "# scenario: FRUIT_ARM_PARK=back (both arms) $PATCH_ENV $SCEN_ENV $DIAG_ENV"
    echo "# A=$CKPT_A  B=$CKPT_B  RUNS=5 EPISODES=15 SEEDS=77/101/202/303/404 policy_seed=11"
    md5sum "$CKPT_A" "$CKPT_B" logs/p37/fidelity.txt logs/p37/p37_report.py \
        scripts/112_rl_ab.sh scripts/113_rl_report.py logs/p35/park_ab_report.py \
        "$0" 2>/dev/null
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        src/fruit_sorting/meshes.py src/fruit_sorting/fruits.py \
        configs/arm_parks.json configs/motion_reference.json
    git rev-parse HEAD
} > logs/p37/B_ab/B_header.txt
cat logs/p37/B_ab/B_header.txt

export RUNS=5
export EPISODES=15
export AB_SEEDS="77 101 202 303 404"
export AB_POLICY_SEED=11
export AB_DIR=logs/p37/B_ab
export ARM_A="--ckpt $CKPT_A"
export ARM_B="--ckpt $CKPT_B"
export ARM_A_ENV=""
export ARM_B_ENV=""
export AB_EXTRA_ENV="FRUIT_ARM_PARK=back $PATCH_ENV $SCEN_ENV $DIAG_ENV"

echo "[p37ab] start $(date +%H:%M:%S)"
RUN_LIMIT=25200 scripts/154_claim_run.sh logs/p37/B_ab/B_driver.log \
    bash -c 'bash scripts/112_rl_ab.sh'
code=$?
echo "[p37ab] batch exit=$code $(date +%H:%M:%S)"

python3 logs/p37/p37_report.py --dir logs/p37/B_ab --a A --b B \
    --fidelity logs/p37/fidelity.txt > logs/p37/B_ab/B_report.txt 2>&1
echo "[p37ab] p37 report exit=$?"

python3 scripts/113_rl_report.py logs/p37/B_ab --a A --b B \
    > logs/p37/B_ab/B_113.txt 2>&1
echo "[p37ab] 113 cross-check exit=$?"

python3 logs/p35/park_ab_report.py --dir logs/p37/B_ab --a A --b B \
    > logs/p37/B_ab/B_park_ab.txt 2>&1
echo "[p37ab] P35 park report cross-check exit=$?"

python3 logs/w7/B_ab_report.py --dir logs/p37/B_ab --a A --b B \
    > logs/p37/B_ab/B_mech.txt 2>&1
echo "[p37ab] W7-B mechanism cross-check exit=$?"

{
    echo "# P37 phase 2 batch pins after ($(date '+%F %T'))"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        src/fruit_sorting/meshes.py src/fruit_sorting/fruits.py \
        configs/arm_parks.json configs/motion_reference.json
} > logs/p37/B_ab/B_tree_md5_after.txt
echo "[p37ab] done $(date +%H:%M:%S) batch_exit=$code"
exit "$code"
