#!/usr/bin/env bash
# P70: the rails/height cells on the scripted line (`logs/p70/RESULTS.md`).
#
#   bash logs/p70/run_cells.sh            # C -> A -> B, one claim each
#
# The owner's directive: **remove the output belts' side rails (both sides) and
# lower the output belt's height as appropriate.** The brief's three cells, the
# acceptance-shaped scripted line (`scripts/20_pick_place.py`), ten attempts,
# `FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1`:
#
#   C (control)  the shipped `both` at 1.35
#   A            `FRUIT_OUTPUT_RAILS=none` at 1.35 - the owner's "remove the ledges"
#   B            `FRUIT_OUTPUT_RAILS=none FRUIT_OUTPUT_BELT_TOP_Z=1.31` - a
#                "moderately lower" belt. 1.31 is *derived*, not picked: the
#                lowering is a 0.175:1 lever on the crossing (the payload
#                descends 82.5 % of the drop, the obstacle 1:1) and it spends 1:1
#                of the slab-underside audit, which is 40 mm at the shipped top
#                (the tallest main-belt fruit: pear 1.20 W x 0.070 m x the 1.0706
#                instance scale) - so -40 mm is the lever's **endpoint** and the
#                largest effect a height change can have. `scripts/238` pins the
#                arithmetic (`+7.0 mm` at -40 mm; the rails are `+35 mm` at 1:1).
#
# C first, then the two treatments: C is the same-tree control, and the shaped
# scene moves the branch anyway (P30-A: the first divergence is a placed fruit's
# discharge row), so every count is **one draw of a new branch**, never a rate.
#
# C pins the rails **explicitly** (`FRUIT_OUTPUT_RAILS=both`): the batch ran it
# with the env unset, when `both` was the default, and the concurrent P71 lane has
# since made `none` the default (see `logs/p70/TREE.md`). The batch's own C log
# proves its mode from inside (`clr=...@rail`).
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p70

COMMON="HEADLESS=1 ATTEMPTS=10 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1"

{
    echo "# P70 header ($(date '+%F %T'))"
    echo "# tree: $(git rev-parse HEAD)"
    md5sum src/fruit_sorting/tasks.py src/fruit_sorting/assets.py \
        src/fruit_sorting/conveyor.py src/fruit_sorting/rl_env.py \
        src/fruit_sorting/fruits.py src/fruit_sorting/scene.py \
        scripts/238_p70_belt_top_selftest.py scripts/selfcheck.sh \
        configs/motion_reference.json
    echo "# crossing: |payload y| >= the inner rail's centreline (0.4125 m, _output_rail_y)"
    echo "# floor   : +33 mm (logs/p30a/RAILS_DESIGN.md); contact boundary (+7, +14] mm (logs/p69/G0_RESULTS.md)"
    echo "# C control  : (shipped) rails=both, belt top 1.35"
    echo "# A          : FRUIT_OUTPUT_RAILS=none, belt top 1.35"
    echo "# B          : FRUIT_OUTPUT_RAILS=none FRUIT_OUTPUT_BELT_TOP_Z=1.31"
} > logs/p70/header.txt
cat logs/p70/header.txt

run_one() {
    local arm=$1 envs=$2
    echo "  [p70] $arm start $(date +%H:%M:%S)"
    RUN_LIMIT=1800 scripts/154_claim_run.sh "logs/p70/${arm}.log" \
        $COMMON $envs scripts/run.sh scripts/20_pick_place.py
    local rc=$?
    echo "  [p70] $arm exit=$rc $(date +%H:%M:%S)"
    return $rc
}

fail=0
run_one C "FRUIT_OUTPUT_RAILS=both" || fail=1
run_one A "FRUIT_OUTPUT_RAILS=none" || fail=1
run_one B "FRUIT_OUTPUT_RAILS=none FRUIT_OUTPUT_BELT_TOP_Z=1.31" || fail=1
echo "[p70] cells end $(date '+%F %T') fail=$fail"
exit "$fail"
