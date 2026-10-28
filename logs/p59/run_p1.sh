#!/usr/bin/env bash
# P59 phase 1: the four checks of logs/p59/PREREG.md, one claim each.
#
#   bash logs/p59/run_p1.sh 1     # the profile is what runs (2 eps, --record)
#   bash logs/p59/run_p1.sh 2     # the pre-P58 recipe (1 ep, three knobs = 0)
#   bash logs/p59/run_p1.sh 3     # --continuous 10, pick-level summary
#   bash logs/p59/run_p1.sh 4     # the continuous video (8 picks, shipped profile)
#
# Nothing here writes src/, configs/, datasets/ or a checkpoint.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p59/p1

CKPT=checkpoints/moe_v13s/policy_best.pt
SCEN="FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1 FRUIT_BED_DIAG=1"
HARNESS="HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 FRUIT_POLICY_SEED=11"
PRE58="FRUIT_FEED_CADENCE=0 FRUIT_SUPPLY_BAND_INTERLOCK=0 FRUIT_DIRECT_FEED=0"

check=${1:?check id 1-4}
case "$check" in
1)
    log=logs/p59/p1/01_profile.log
    RUN_LIMIT=1800 scripts/154_claim_run.sh "$log" \
        $HARNESS $SCEN \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --episodes 2 --seeds 77 --record --out /tmp/p59_prof
    ;;
2)
    log=logs/p59/p1/02_pre58_recipe.log
    RUN_LIMIT=1800 scripts/154_claim_run.sh "$log" \
        $HARNESS $SCEN $PRE58 \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --episodes 1 --seeds 77
    ;;
2b)
    # Check 2 re-run with `--out`: the default scratch dir
    # (`datasets/rl_rollouts/direct_none_seed77`) is shared with every
    # non-`--out` run, so check 3 overwrote check 2's manifest. Same command,
    # same env; only the manifest path differs, so the pre-profile manifest
    # survives for `verify_demo.py`.
    log=logs/p59/p1/02b_pre58_manifest.log
    RUN_LIMIT=1800 scripts/154_claim_run.sh "$log" \
        $HARNESS $SCEN $PRE58 \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --episodes 1 --seeds 77 --out /tmp/p59_pre58
    ;;
3)
    log=logs/p59/p1/03_continuous10.log
    RUN_LIMIT=2400 scripts/154_claim_run.sh "$log" \
        $HARNESS $SCEN \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$CKPT" \
        --episodes 1 --seeds 77 --continuous 10
    ;;
4)
    log=logs/p59/p1/04_video_shipped.log
    RUN_LIMIT=2700 scripts/154_claim_run.sh "$log" \
        $HARNESS $SCEN \
        scripts/run.sh scripts/121_policy_video.py --ckpt "$CKPT" \
        --episodes 1 --continuous 8 --seed 77 --capture-every 2 \
        --out-dir logs/p59/video_shipped
    ;;
*)
    echo "check id must be 1..4" >&2
    exit 2
    ;;
esac
rc=$?
echo "[p59] check $check exit=$rc log=$log"
exit $rc
