#!/usr/bin/env bash
# P107 - reproduce the radial four-pad cage's three cells.
#
#   bash logs/p107/run_p107.sh          # M1 census + M2b (15) + M3 (2 seeds) + the controls
#   bash logs/p107/run_p107.sh m1       # the asset census only (~2 min)
#
# Every cell goes through `scripts/run.sh` (the file-descriptor limit) and the
# scripted entry point, so the tree's fixed stepping applies. `FRUIT_BIARM=0` is
# the scenario: the *hand* is the variable, not the two-line scheduler (which
# refuses a non-`openarm` hand by construction, `tasks.py:9543`).
set -euo pipefail
cd "$(dirname "$0")/../.."

what=${1:-all}

if [ "$what" = "all" ] || [ "$what" = "m1" ]; then
    echo "=== M1: the asset census (no attempt loop) ==="
    FRUIT_GRIPPER_KIND=cage4 scripts/run.sh logs/p107/m1_cage.py \
        > logs/p107/m1_cage.txt 2>&1
    grep -E '^\[fruit\] \[m1\]' logs/p107/m1_cage.txt
fi

if [ "$what" = "all" ] || [ "$what" = "m2b" ]; then
    echo "=== M2b: 15 attempts, seed 5 ==="
    FRUIT_GRIPPER_KIND=cage4 FRUIT_BIARM=0 SEED=5 ATTEMPTS=15 \
        FRUIT_CAGE_PROBE=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1 \
        scripts/run.sh scripts/20_pick_place.py > logs/p107/m2b_s5.log 2>&1
    grep -E '\[stats\]' logs/p107/m2b_s5.log
fi

if [ "$what" = "all" ] || [ "$what" = "m3" ]; then
    for seed in 5 6; do
        echo "=== M3: 10 attempts, seed ${seed} ==="
        FRUIT_GRIPPER_KIND=cage4 FRUIT_BIARM=0 SEED="${seed}" ATTEMPTS=10 \
            FRUIT_CAGE_PROBE=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1 \
            scripts/run.sh scripts/20_pick_place.py > "logs/p107/m3_s${seed}.log" 2>&1
        grep -E '\[stats\]' "logs/p107/m3_s${seed}.log"
        echo "--- same-tree control, shipped hand"
        FRUIT_BIARM=0 SEED="${seed}" ATTEMPTS=10 FRUIT_MOTION_REPORT=1 \
            FRUIT_CARRY_DIAG=1 scripts/run.sh scripts/20_pick_place.py \
            > "logs/p107/ctl_s${seed}.log" 2>&1
        grep -E '\[stats\]' "logs/p107/ctl_s${seed}.log"
    done
    python3 logs/p107/p107_report.py logs/p107/m2b_s5.log \
        logs/p107/m3_s5.log logs/p107/m3_s6.log > logs/p107/table.txt
fi

echo "=== no-harm: the shipped acceptance must be byte-identical to the record ==="
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p107/accept_noharm.log scripts/accept.sh \
    > logs/p107/accept_noharm.driver 2>&1 || true
tail -3 logs/p107/accept_noharm.driver
python3 - <<'PY'
a = [l for l in open("logs/p107/accept_noharm.log", errors="replace") if "[fruit]" in l]
b = [l for l in open("logs/p103/accept_final.log", errors="replace") if "[fruit]" in l]
same = sum(1 for x, y in zip(a, b) if x == y)
print(f"[fruit] lines {len(a)} vs the P103 record {len(b)}: {same} identical")
PY
