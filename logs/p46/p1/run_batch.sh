#!/usr/bin/env bash
# P46 phase 1 battery: the P44 speed union on the two-line, one claim, 4 runs.
#
#   bash logs/p46/p1/run_batch.sh        # seeds 5 and 6, C -> U each (~25 min)
#
# The claim wraps the whole battery (not each arm): no other lane can slip a
# simulator between the control and the treatment, so the pair is one session.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
OUT=logs/p46/p1
mkdir -p "$OUT"

{
    echo "# P46 phase 1 battery header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/motion.py \
        src/fruit_sorting/control.py src/fruit_sorting/scene.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/rl_env.py \
        configs/motion_reference.json configs/motion_reference_twoline.json
    echo "# scenario: HEADLESS=1 ATTEMPTS=10 FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 SEED=5|6"
    echo "# arms (interleaved, per seed): C U"
    echo "# instruments on every arm: MOTION_REPORT CYCLE_REPORT CARRY_DIAG PLACE_TRACE"
    echo "# prior of record: logs/p44/p2/twoline_s5_{C,S13}.log (seed 5, no diag)"
} | tee -a "$OUT/batch_header.txt"

t0=$(date +%s)
# 4 runs x ~5 min = ~20-25 min; 2700 s bounds the whole battery, not each arm.
RUN_LIMIT=2700 scripts/154_claim_run.sh "$OUT/driver.log" \
    bash logs/p46/p1/run_arms.sh
echo "[p46] battery claim returned $? wall=$(( $(date +%s) - t0 ))s $(date '+%H:%M:%S')"
