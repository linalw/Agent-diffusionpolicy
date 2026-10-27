#!/usr/bin/env bash
# P45 phase 2 battery driver: ONE claim per battery, five arms interleaved inside it.
#
#   bash logs/p45/p2/run_batch.sh A    # the acceptance, seed 5    (~25-30 min)
#   bash logs/p45/p2/run_batch.sh B    # the pear battery, seed 5  (~25-30 min)
#
# The claim wraps `run_arms.sh` rather than each arm (`logs/p44/p2/run_batch.sh`
# claimed per arm), which is stronger: no other lane can slip a simulator between
# two arms of the same battery, so the control and the treatment are one session
# and one branch probe.
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1
BATTERY=${1:?usage: run_batch.sh A|B}
OUT=logs/p45/p2
mkdir -p "$OUT"

{
    echo "# P45 phase 2 battery $BATTERY header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)  dirty=$(git status --porcelain | wc -l)"
    md5sum src/fruit_sorting/fruits.py src/fruit_sorting/meshes.py \
        src/fruit_sorting/tasks.py src/fruit_sorting/control.py \
        src/fruit_sorting/scene.py src/fruit_sorting/rl_env.py \
        configs/motion_reference.json configs/motion_reference_twoline.json \
        scripts/227_p45_mass_selftest.py scripts/selfcheck.sh
    echo "# arms (interleaved): ${P45_ARMS:-C M50 M25 M50S M25S}"
    echo "# instruments on every arm: MOTION_REPORT CYCLE_REPORT CARRY_DIAG RELEASE_DEBUG PLACE_TRACE"
} | tee -a "$OUT/batch_header.txt"

t0=$(date +%s)
RUN_LIMIT=3000 scripts/154_claim_run.sh "$OUT/driver_${BATTERY}.log" \
    bash logs/p45/p2/run_arms.sh "$BATTERY"
echo "[p45] battery $BATTERY claim returned $? wall=$(( $(date +%s) - t0 ))s $(date '+%H:%M:%S')"
