#!/usr/bin/env bash
# P43 phase 2 batch: L1 (the scoped nearest-above-floor default) + L2 step 1.
#
#   nohup bash logs/p43/p2/run_batch.sh > logs/p43/p2/batch_driver.log 2>&1 &
#
# One `scripts/154_claim_run.sh` claim per run, strictly sequential (one
# simulator). The arms:
#
#   L1  acceptance  A = FRUIT_SELECT_NEAREST_ABOVE_FLOOR=0 (pre-P43 pick)
#                   B = unset (the new scoped default: nearest on the scripted line)
#       seeds 5 and 6, 10 attempts each, FRUIT_CYCLE_REPORT=1 on both arms
#       (the first single-arm `[cycle]` block; the instrument sits inside the
#       comparison, AGENTS 3b), plus FRUIT_BED_DIAG=1 on the seed-5 A run so the
#       D0 census and the no-harm identity (N2) come out of the same battery.
#   L1  pear        the same four runs with FRUIT_SUPPLY_SPECIES=pear.
#   L1  shared      FRUIT_BIARM=1 (shared-station pipeline, ATTEMPTS=10, SEED=5),
#       A vs B: byte-identity is the scope evidence for the non-two-line bimanual.
#   F5  direct      the direct/policy env's episode selection must be untouched:
#       unset vs =0 (both resolve off through `direct=True`) and =1 (the
#       explicit env value, the "wins everywhere" contract).
#   L2  loop        one direct run with the shipped loop (E=4, RTC off) and both
#       wall instruments: FRUIT_RTC_REPORT=1 + FRUIT_LOOP_TIMING=1.
#
# Nothing here writes `configs/`, `datasets/` or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p43/p2

CLAIM=scripts/154_claim_run.sh
PICK="scripts/run.sh scripts/20_pick_place.py"
CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
DIRECT_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_POLICY_TRIGGER_ACQ=1 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11"
KNOB=FRUIT_SELECT_NEAREST_ABOVE_FLOOR

{
    echo "# P43 phase 2 batch header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/control.py src/fruit_sorting/scene.py \
        src/fruit_sorting/policy/runtime.py src/fruit_sorting/policy/trigger.py \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        configs/arm_parks.json "$CKPT" \
        scripts/224_p43_selftest.py logs/p43/p2/run_batch.sh
    echo "# L1 A = $KNOB=0 (pre-P43 pick); B = unset (scoped default, nearest on the scripted line)"
    echo "# acceptance: ATTEMPTS=10 SEED={5,6} FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1"
    echo "# pear: + FRUIT_SUPPLY_SPECIES=pear ; D0 census: + FRUIT_BED_DIAG=1 on the seed-5 A runs"
    echo "# shared-station: FRUIT_BIARM=1 ATTEMPTS=10 SEED=5"
    echo "# direct: $DIRECT_ENV $PATCH_ENV ; ckpt=$CKPT"
} > logs/p43/p2/batch_header.txt
cat logs/p43/p2/batch_header.txt

run() {  # run <log> <env...>
    local log=$1; shift
    local t0 t1 code
    t0=$(date +%s)
    RUN_LIMIT=1500 "$CLAIM" "logs/p43/p2/$log" "$@"
    code=$?
    t1=$(date +%s)
    echo "[batch] $log done exit=$code wall=$((t1 - t0))s $(date '+%H:%M:%S')"
}

BASE_PICK="HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1"

# --- L1a: the acceptance (single arm), A/B x seeds 5, 6 --------------------- #
run d0_accept_A_s5.log $BASE_PICK SEED=5 FRUIT_BED_DIAG=1 $KNOB=0 $PICK
run r_accept_A_s6.log $BASE_PICK SEED=6 $KNOB=0 $PICK
run r_accept_B_s5.log $BASE_PICK SEED=5 $PICK
run r_accept_B_s6.log $BASE_PICK SEED=6 $PICK

# --- L1b: the pear battery (species-locked), A/B x seeds 5, 6 --------------- #
run d0_pear_A_s5.log $BASE_PICK SEED=5 FRUIT_SUPPLY_SPECIES=pear FRUIT_BED_DIAG=1 $KNOB=0 $PICK
run r_pear_A_s6.log $BASE_PICK SEED=6 FRUIT_SUPPLY_SPECIES=pear $KNOB=0 $PICK
run r_pear_B_s5.log $BASE_PICK SEED=5 FRUIT_SUPPLY_SPECIES=pear $PICK
run r_pear_B_s6.log $BASE_PICK SEED=6 FRUIT_SUPPLY_SPECIES=pear $PICK

# --- L1c: the shared-station bimanual (the non-two-line bimanual path) ------ #
run biarm_A_s5.log HEADLESS=1 ATTEMPTS=10 SEED=5 FRUIT_BIARM=1 $KNOB=0 $PICK
run biarm_B_s5.log HEADLESS=1 ATTEMPTS=10 SEED=5 FRUIT_BIARM=1 $PICK

# --- F5: the direct/policy episode selection ------------------------------- #
run f5_direct_unset_e2.log HEADLESS=1 $DIRECT_ENV $PATCH_ENV \
    scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
    --presentation direct --episodes 2 --seeds 77
run f5_direct_off_e2.log HEADLESS=1 $DIRECT_ENV $PATCH_ENV $KNOB=0 \
    scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
    --presentation direct --episodes 2 --seeds 77
run f5_direct_on_e2.log HEADLESS=1 $DIRECT_ENV $PATCH_ENV $KNOB=1 \
    scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
    --presentation direct --episodes 2 --seeds 77

# --- L2 step 1: the loop's wall decomposition (shipped loop, RTC off) ------ #
run l2_loop_timing_e5.log HEADLESS=1 $DIRECT_ENV $PATCH_ENV \
    FRUIT_RTC_REPORT=1 FRUIT_LOOP_TIMING=1 \
    scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
    --presentation direct --episodes 5 --seeds 77

{
    echo "# P43 phase 2 batch tree pins after ($(date '+%F %T'))"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/control.py src/fruit_sorting/scene.py \
        configs/motion_reference.json configs/motion_reference_twoline.json
} > logs/p43/p2/batch_tree_md5_after.txt
echo "[batch] all done $(date '+%H:%M:%S')"
