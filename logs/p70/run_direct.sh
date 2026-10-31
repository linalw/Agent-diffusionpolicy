#!/usr/bin/env bash
# P70 task 4: the direct line, the **low lift** with the rails/height choice
# (`logs/p70/RESULTS.md`).
#
#   bash logs/p70/run_direct.sh            # D0 (shipped rails) -> D1 (the choice)
#   TREAT_ENV="FRUIT_OUTPUT_RAILS=none" bash logs/p70/run_direct.sh   # cell A only
#
# The question: on the *left* arm the shipped lift ends at 1.530 m and the low
# lift (`FRUIT_LIFT_DZ=-0.08`, lift end 1.370) is the only lever that fixes the
# left's 25 deg carry rotation (P66 phase 3: placed 0/25 -> 14/25 at N=5) - and
# it fails the +33 mm crossing floor (P66 phase 4: left `clr` +5 / `clr_win`
# +0 mm at the one held leg). P70's rails/height choice is the geometry that
# could restore the floor **without** spending that carry.
#
# Scenario: the P66 phase-4 / P67 cell verbatim (all-A supply so every attempt is
# a left place leg, the shipped direct profile, `moe_v13s`, seed 77, 15
# episodes). `FRUIT_LIFT_DZ=-0.08` is **explicit in both arms** - `+0.08` is the
# shipped direct default (P66 P4 reverted the phase-3 flip), so unset is the
# control here, but explicit is what the record does and it prints its own
# height. `FRUIT_MOTION_REPORT=1` on **both** arms: the `|a|max` channel is the
# contact instrument G0 calibrated (P66/P67 left it off), and it is a reporting
# read (G0's control was `[fruit]`-identical with it on).
#
# The direct loop is **not** bit-reproducible (rendered frames), so both arms run
# in one stretch and every count is a branch draw, never a rate (AGENTS §3b).
#
# D0 pins the rails **explicitly**: the batch ran it with the env unset (when
# `both` was the scene default) and D1 after the concurrent P71 lane had made
# `none` the default - `logs/p70/TREE.md` records that tree state, and each log's
# own surface code (`@rail` vs `@obelt`) proves which geometry it ran.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p70/direct

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.96,B:0.02,C:0.02 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_SEED=11 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1 FRUIT_MOTION_REPORT=1 FRUIT_LIFT_DZ=-0.08"
HARNESS_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
TREAT_ENV=${TREAT_ENV:-"FRUIT_OUTPUT_RAILS=none"}   # cell A: the minimum geometry that clears; see RESULTS §2
SEED=${SEED:-77}
EPISODES=${EPISODES:-15}

{
    echo "# P70 direct header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    md5sum "$CKPT" src/fruit_sorting/tasks.py src/fruit_sorting/assets.py \
        src/fruit_sorting/conveyor.py src/fruit_sorting/rl_env.py \
        configs/waypoints.json configs/arm_parks.json
    echo "# scenario (the P66 phase-4 cell): $SCEN_ENV"
    echo "# D0 control : the shipped rails (both, 1.35) + FRUIT_LIFT_DZ=-0.08"
    echo "# D1 treatment: $TREAT_ENV + FRUIT_LIFT_DZ=-0.08"
    echo "# crossing   : |payload y| >= the inner rail's centreline (0.4125 m)"
    echo "# floor      : +33 mm; contact boundary (+7, +14] mm (logs/p69/G0_RESULTS.md)"
} > logs/p70/direct/header.txt
cat logs/p70/direct/header.txt

run_one() {
    local arm=$1 envs=$2
    echo "  [p70d] $arm start $(date +%H:%M:%S)"
    RUN_LIMIT=3600 scripts/154_claim_run.sh "logs/p70/direct/${arm}.log" \
        $HARNESS_ENV $SCEN_ENV $envs \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --presentation direct --episodes "$EPISODES" --seeds "$SEED" \
        --out logs/p70/direct/rollouts
    local rc=$?
    echo "  [p70d] $arm exit=$rc $(date +%H:%M:%S)"
    return $rc
}

fail=0
run_one D0 "FRUIT_OUTPUT_RAILS=both" || fail=1
run_one D1 "$TREAT_ENV" || fail=1
echo "[p70d] direct end $(date '+%F %T') fail=$fail"
exit "$fail"
