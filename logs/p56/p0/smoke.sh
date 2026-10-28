#!/usr/bin/env bash
# P56 phase 2, step 1: the **mechanical smoke** of `FRUIT_DIRECT_CONTINUOUS=3`.
#
#   bash logs/p56/p0/smoke.sh
#
# Three runs, all on the P54/P43 patch scenario, `moe_v13s` (`61da390a`), seed 77:
#   R_repeat      the knob-off policy run a SECOND time on the post-change tree -
#                 the reproducibility probe for the 1-tick / 1-mm difference the
#                 pre/post pair showed (two runs of an unchanged tree are the only
#                 way to attribute it, since the policy loop conditions on
#                 rendered frames).
#   C3            `--episodes 1` + `FRUIT_DIRECT_CONTINUOUS=3`, `--record`:
#                 the `[cont]`/`[bed-sel]`/`[grasp]` rows, 3 distinct outcome
#                 rows, the recorder's 3 distinct npz + index rows (P5's
#                 overwrite test at n = 3).
#   C3_norec      the same without `--record` (the timing shape the battery runs).
#
# Instrumentation (`FRUIT_BED_DIAG`, `FRUIT_GRASP_DIAG`) is on in **both** the
# continuous and the reproducibility probe where it is read; the knob-off
# byte-identity runs (base_before/base_after) carry neither.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
mkdir -p logs/p56/p0

CKPT=checkpoints/moe_v13s/policy_best.pt
PATCH_ENV="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25"
SCEN_ENV="FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1"
FIX_ENV="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_SIZE_FILTER= FRUIT_POLICY_SEED=11 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1"
ARM_A="FRUIT_DIRECT_FEED=1"
EXTRA_ENV=""
EPISODES=1

# `run_one <label> <driver-args>` - the env assignments are the shell variables
# below; the driver args go after the script (the claim wrapper runs `env "$@"`
# up to the script, so a `--flag` in the env position is a hard error: that is
# what killed the first C3 attempt, exit 127).
run_one() {
    local label=$1 driver=$2
    echo "[smoke] $label start $(date '+%F %T')"
    # shellcheck disable=SC2086
    RUN_LIMIT=1800 scripts/154_claim_run.sh "logs/p56/p0/${label}.log" \
        $PATCH_ENV $SCEN_ENV $FIX_ENV $ARM_A $EXTRA_ENV \
        scripts/run.sh scripts/110_rl_rollout.py --presentation direct \
        --ckpt "$CKPT" --episodes "$EPISODES" --seeds 77 $driver
    echo "[smoke] $label exit=$? $(date '+%F %T')"
}

# 1. the continuous smoke at n = 5: several transitions, both arm cases, and any
#    starvation round (the mechanical items only)
EXTRA_ENV="FRUIT_DIRECT_CONTINUOUS=5 FRUIT_BED_DIAG=1 FRUIT_GRASP_DIAG=1"
EPISODES=1
run_one C5 ""

# 2. the recorder certificate at n = 3 (P5's overwrite test, cheap)
EXTRA_ENV="FRUIT_DIRECT_CONTINUOUS=3 FRUIT_BED_DIAG=1 FRUIT_GRASP_DIAG=1"
run_one C3 "--record --out logs/p56/p0/rec_smoke2"

echo "[smoke] done $(date '+%F %T')"
