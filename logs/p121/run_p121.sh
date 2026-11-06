#!/usr/bin/env bash
# P121: the direct/policy line's instruction cells.
#   C   un-instructed control
#   T1  today's routing as an instruction (grade=A=>0, B=>1, C=>skip)
#   T2  a non-grade instruction (size<40 => 1, default => 0)
#   T3  the third destination (A=>2, B=>1) + the three_dest scenario, OOD flag on
#
# 3 seeds x 10 episodes per cell (77/101/202), the shipped direct config. The
# direct loop is not reproducible (rendered frames), so this is one batch of
# branch draws: the endpoint is the [sort] ledger's assignment accuracy, never a
# rate (logs/p121/PREREG.md, pinned before the cells).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p121/direct logs/p121/rollouts

CKPT=checkpoints/moe_v13s/policy_best.pt
{
    echo "# P121 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD) + the P121 working-tree edit"
    echo "# prereg: $(tr '\n' ' ' < logs/p121/PREREG.md5)"
    md5sum "$CKPT" \
        src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/scenario.py src/fruit_sorting/assets.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        src/fruit_sorting/control.py src/fruit_sorting/conveyor.py \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        configs/motion_reference_single.json \
        logs/p114/instructions/today.txt logs/p114/instructions/size40.txt \
        logs/p114/instructions/three_dest.txt logs/p114/scenarios/three_dest.json \
        scripts/263_p121_env_sort_selftest.py
    echo "# cells: C unset / T1 today / T2 size<40 / T3 three_dest + FRUIT_SORT_THIRD_DEST=1"
    echo "# batch: seeds 77,101,202 x 10 episodes per cell (one session per cell)"
} > logs/p121/header.txt
cat logs/p121/header.txt

run_cell() {
    local name=$1; shift
    echo "  [p121] $name start $(date +%H:%M:%S)"
    RUN_LIMIT=3000 logs/p121/one_run.sh "logs/p121/direct/${name}.log" 10 77,101,202 "$@"
    echo "  [p121] $name exit=$? $(date +%H:%M:%S)"
    grep -E "\[sort\] ledger|\[rl\] rollout success|\[rl\] seed" "logs/p121/direct/${name}.log" | tail -8
}

run_cell C
run_cell T1 FRUIT_SORT_INSTRUCTION=logs/p114/instructions/today.txt
run_cell T2 FRUIT_SORT_INSTRUCTION=logs/p114/instructions/size40.txt
run_cell T3 FRUIT_SCENARIO=logs/p114/scenarios/three_dest.json \
    FRUIT_SORT_INSTRUCTION=logs/p114/instructions/three_dest.txt \
    FRUIT_SORT_THIRD_DEST=1

echo "[p121] batch end $(date '+%F %T')"
