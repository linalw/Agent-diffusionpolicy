#!/usr/bin/env bash
# P37 phase 2 step 1: the park-collected fine-tune + the fidelity readout.
#
#   bash scripts/222_p37_finetune.sh         # fine-tune (skips if it exists) + 119
#
# The pre-registration is `logs/p37/PREREG.md` section 4, the phase-2 contract:
#
#   scripts/111_rl_finetune.py --ckpt checkpoints/moe_v13s/policy_best.pt \
#       --rollouts datasets/rl_rollouts/p37_park --base datasets/demos_v11 \
#       --out checkpoints/p37_park --epochs 6 --lr 5e-5 --weight-mode ones \
#       --base-weight 1.0 --batch-size 32 --seed 0
#
# `ones` is the lineage recollection mode (moe_v13s, moe_v13p); the `success`
# and `awr` modes carry measured negatives on this interface (RWR-1, R9). The
# candidate's md5 and `finetune_history.json` are recorded into
# `logs/p37/P_ckpt_md5.txt` **before** the A/B batch starts, one-way.
#
# Step 2 is `scripts/119_rl_fidelity.py` (offline, no simulator): base vs
# candidate on the park store and on `demos_v11`, 192 windows, DDIM-16, fixed
# per-window noise - the PREREG section 4 diagnostic (not a gate).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/p37

LINGBOT=${LINGBOT:-/home/ubuntu/linalw/App/minconda3/envs/lingbot/bin/python}
INIT=${INIT:-checkpoints/moe_v13s/policy_best.pt}
STORE=${STORE:-datasets/rl_rollouts/p37_park}
BASE=${BASE:-datasets/demos_v11}
CKPT=${CKPT:-checkpoints/p37_park}

if [ ! -f "$INIT" ]; then echo "[p37ft] FAIL: no init checkpoint $INIT"; exit 1; fi
if [ ! -f "$STORE/index.json" ]; then echo "[p37ft] FAIL: no store $STORE"; exit 1; fi
if [ ! -f "$BASE/index.json" ]; then echo "[p37ft] FAIL: no base $BASE"; exit 1; fi
if [ ! -f "$LINGBOT" ]; then echo "[p37ft] FAIL: no lingbot python $LINGBOT"; exit 1; fi

{
    echo "# P37 phase 2 pins ($(date '+%F %T'))"
    md5sum "$INIT" "$STORE/index.json" "$STORE/merge_manifest.json" "$BASE/index.json"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/policy/trigger.py src/fruit_sorting/policy/runtime.py \
        src/fruit_sorting/meshes.py src/fruit_sorting/fruits.py \
        configs/arm_parks.json configs/motion_reference.json
    md5sum logs/p37/p37_report.py scripts/112_rl_ab.sh scripts/113_rl_report.py \
        logs/p35/park_ab_report.py
    git rev-parse HEAD
} > logs/p37/P_tree_md5_before.txt
cat logs/p37/P_tree_md5_before.txt

if [ -f "$CKPT/policy_best.pt" ]; then
    echo "[p37ft] $CKPT/policy_best.pt exists - keeping it (rm to force)"
else
    mkdir -p "$CKPT"
    echo "[p37ft] fine-tune $INIT -> $CKPT ($(date +%H:%M:%S))"
    "$LINGBOT" scripts/111_rl_finetune.py \
        --ckpt "$INIT" \
        --rollouts "$STORE" \
        --base "$BASE" \
        --out "$CKPT" \
        --epochs 6 --lr 5e-5 --weight-mode ones --base-weight 1.0 \
        --batch-size 32 --seed 0 \
        > logs/p37/P_finetune.log 2>&1
    code=$?
    echo "[p37ft] fine-tune exit=$code $(date +%H:%M:%S)"
    [ "$code" -ne 0 ] && { tail -30 logs/p37/P_finetune.log; exit "$code"; }
fi

md5sum "$CKPT/policy_best.pt" > logs/p37/P_ckpt_md5.txt
cat logs/p37/P_ckpt_md5.txt
if [ -f "$CKPT/finetune_history.json" ]; then
    cp "$CKPT/finetune_history.json" logs/p37/P_finetune_history.json
    python3 - "$CKPT/finetune_history.json" <<'PY'
import json, sys
h = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"[p37ft] epochs={h['epochs']} lr={h['lr']} mode={h['weight_mode']} "
      f"base_weight={h['base_weight']} windows={h['rollout_windows']} + "
      f"{h['base_windows']} base (share "
      f"{100.0 * h['rollout_windows'] / (h['rollout_windows'] + h['base_windows']):.1f}%)")
print(f"[p37ft] final_weighted_loss={h['final_weighted_loss']:.6f} "
      f"router_acc(final)={h['history'][-1]['router_acc']:.4f}")
for row in h["history"]:
    print(f"[p37ft] epoch {row['epoch']}: mse={row['mse']:.6f} "
          f"weighted={row['weighted_loss']:.6f} router_ce={row['router_ce']:.4f} "
          f"router_acc={row['router_acc']:.4f} demo_val={row['demo_val']:.6f}")
PY
fi

echo "[p37ft] fidelity readout -> logs/p37/fidelity.txt"
"$LINGBOT" scripts/119_rl_fidelity.py \
    --base "$INIT" --candidate "$CKPT/policy_best.pt" \
    --data "$STORE" --data "$BASE" \
    --windows 192 --ddim 16 \
    --out logs/p37/fidelity.txt > logs/p37/P_fidelity.log 2>&1
code=$?
echo "[p37ft] fidelity exit=$code"
grep -E "paired delta|action delta|=== fidelity|feeds" logs/p37/fidelity.txt 2>/dev/null

{
    echo "# P37 phase 2 pins after the fine-tune ($(date '+%F %T'))"
    md5sum checkpoints/p37_park/policy_best.pt logs/p37/fidelity.txt 2>/dev/null
} >> logs/p37/P_tree_md5_after.txt
exit "$code"
