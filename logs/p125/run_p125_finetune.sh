#!/usr/bin/env bash
# P125 step 2: the three-lane fine-tune (moe_v12 -> checkpoints/p125_three_lane).
#
# Recipe (the record's): the W7-C/W3 deployed shape - 6 epochs, lr 5e-5, batch
# 32, seed 0, `--weight-mode ones`, the checkpoint's own normalizer kept, last
# epoch saved. Init `checkpoints/moe_v12/policy_best.pt` - the checkpoint
# `scripts/accept_policy.sh` defaults to, i.e. the canary of record - so the
# A/B differs by the store alone (PREREG section 3).
#
# Data: the three-lane two-line recollection (`datasets/p125_three_lane`) as the
# rollout store + the single-arm base anchor `datasets/demos_v11` (the W4
# wrong-anchor lesson: a two-line store must not also be the direct anchor).
#
#   bash logs/p125/run_p125_finetune.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p125

LINGBOT=${LINGBOT:-/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python}
MERGED=${MERGED:-datasets/p125_three_lane}
CKPT=${CKPT:-checkpoints/p125_three_lane}
INIT=${INIT:-checkpoints/moe_v12/policy_best.pt}

if [ ! -f "$MERGED/index.json" ]; then
    echo "[p125-ft] FAIL: no merged store at $MERGED"
    exit 1
fi
if [ ! -f "$INIT" ]; then
    echo "[p125-ft] FAIL: no init checkpoint at $INIT"
    exit 1
fi
if [ -f "$CKPT/policy_best.pt" ]; then
    echo "[p125-ft] $CKPT/policy_best.pt exists; keeping it (rm to force)"
else
    mkdir -p "$CKPT"
    md5sum "$INIT" "$MERGED/index.json" | tee logs/p125/finetune_init_md5.txt
    echo "[p125-ft] fine-tune $INIT -> $CKPT ($(date +%H:%M:%S))"
    "$LINGBOT" scripts/111_rl_finetune.py \
        --ckpt "$INIT" \
        --rollouts "$MERGED" \
        --base datasets/demos_v11 \
        --out "$CKPT" \
        --epochs 6 --lr 5e-5 --batch-size 32 --weight-mode ones \
        --base-weight 1.0 --seed 0 \
        > logs/p125/finetune.log 2>&1
    code=$?
    echo "[p125-ft] exit=$code $(date +%H:%M:%S)"
    if [ "$code" -ne 0 ]; then tail -30 logs/p125/finetune.log; exit "$code"; fi
fi

md5sum "$CKPT/policy_best.pt" | tee logs/p125/ckpt_md5.txt
if [ -f "$CKPT/finetune_history.json" ]; then
    cp "$CKPT/finetune_history.json" logs/p125/finetune_history.json
    python3 - "$CKPT/finetune_history.json" <<'PY' | tee logs/p125/finetune_summary.txt
import json, sys
h = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"epochs={h['epochs']} lr={h['lr']} mode={h['weight_mode']} "
      f"base={h['base']} init={h['base_checkpoint']}")
print(f"rollout_episodes={h['rollout_episodes']} windows={h['rollout_windows']} "
      f"+ base {h['base_windows']} windows")
print(f"final_weighted_loss={h['final_weighted_loss']:.6f} "
      f"router_acc(final)={h['history'][-1]['router_acc']:.4f}")
for row in h["history"]:
    print(f"epoch {row['epoch']}: mse={row['mse']:.6f} "
          f"weighted={row['weighted_loss']:.6f} router_ce={row['router_ce']:.4f} "
          f"router_acc={row['router_acc']:.4f} demo_val={row['demo_val']:.6f}")
PY
else
    echo "[p125-ft] FAIL: no finetune_history.json at $CKPT" | tee logs/p125/finetune_summary.txt
    exit 1
fi
