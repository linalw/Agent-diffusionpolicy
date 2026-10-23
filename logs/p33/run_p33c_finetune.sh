#!/usr/bin/env bash
# P33 phase 3 step 2: the post-pear fine-tune (moe_v13s -> checkpoints/p33_pear).
#
# Recipe: the W7-C/W3 deployed shape - 6 epochs, lr 5e-5, batch 32, seed 0,
# `--weight-mode ones`, the checkpoint's own normalizer kept, last epoch saved.
# Init: `checkpoints/moe_v13s/policy_best.pt` (the direct anchor, md5 61da390a).
# Data: the post-pear two-line patch recollection (`datasets/p33_pear`) as the
# rollout store + the single-arm base anchor `datasets/demos_v11` (the W4
# wrong-anchor lesson: a two-line store must not also be the direct anchor).
#
#   bash logs/p33/run_p33c_finetune.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p33

LINGBOT=${LINGBOT:-/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python}
MERGED=${MERGED:-datasets/p33_pear}
CKPT=${CKPT:-checkpoints/p33_pear}
INIT=${INIT:-checkpoints/moe_v13s/policy_best.pt}

if [ ! -f "$MERGED/index.json" ]; then
    echo "[p33c-ft] FAIL: no merged store at $MERGED"
    exit 1
fi
if [ -f "$CKPT/policy_best.pt" ]; then
    echo "[p33c-ft] $CKPT/policy_best.pt exists; skipping (use rm to force)"
    exit 0
fi

mkdir -p "$CKPT"
md5sum "$INIT" "$MERGED/index.json" > logs/p33/D_init_md5.txt
echo "[p33c-ft] fine-tune $INIT -> $CKPT ($(date +%H:%M:%S))"
"$LINGBOT" scripts/111_rl_finetune.py \
    --ckpt "$INIT" \
    --rollouts "$MERGED" \
    --base datasets/demos_v11 \
    --out "$CKPT" \
    --epochs 6 --lr 5e-5 --batch-size 32 --weight-mode ones --seed 0 \
    > logs/p33/D_finetune.log 2>&1
code=$?
echo "[p33c-ft] exit=$code $(date +%H:%M:%S)"
md5sum "$CKPT/policy_best.pt" > logs/p33/D_ckpt_md5.txt 2>/dev/null
cat logs/p33/D_ckpt_md5.txt 2>/dev/null
tail -20 logs/p33/D_finetune.log
exit "$code"
