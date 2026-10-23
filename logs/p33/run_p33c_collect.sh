#!/usr/bin/env bash
# P33 phase 3 step 1: the **post-pear** two-line patch recollection.
#
# Scenario (the W7-C `demos_v13p` recipe, on the current tree with the P32 pear):
#   * `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1` - the two-line branch (the balanced
#     choice: Gate 2 measured the single-arm/carry-class store as left-poor,
#     14/60; the two-line records both arms on their own stations);
#   * `FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1` - the W6-A 2D patch sheet;
#   * `FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25` - the balanced mix the
#     two-line pure routing needs (B arm);
#   * camera 240,424 (the collection/training/eval view), shipped belt 0.12;
#   * the pear is on (the shipped `meshes.py` on this tree) - that is the point:
#     every prior store is pre-pear and its per-instance RNG stream moved.
#
# **Sequential**, not the 3-way parallel shape: the 2026-10-12 W7-C batch hit
# the known blocking `RenderingManager.render()` wedge in all three shards at
# once; the sequential resume collected cleanly. Each run is bounded
# (`P33_PER_RUN=24` successes) so a wedge costs at most ~one run; the guard
# exits, the shard's flushed episodes stay indexed, and this loop starts a new
# directory with a fresh seed (the W7-C resume shape). The per-episode soft
# watchdog (`FRUIT_COLLECT_EPISODE_S`, default 600 s) is left at its default:
# it skips and retries an over-budget attempt without stopping the belt.
#
#   nohup bash logs/p33/run_p33c_collect.sh > logs/p33/C_collect_driver.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p33

QUOTA=${P33_QUOTA:-54}      # successes per shard (3 x 54 = 162 target)
PER_RUN=${P33_PER_RUN:-24}  # successes per collector process
# Gate 3 (L1): the P33 store was collected with `SEEDS=(41 42 43)` and
# `seed + attempt - 1`, so s1's first run got 42 (s0's second run's seed) and
# s2's first got 62 (s1's second run's seed) - both replayed an existing stream
# and both runs were killed and restarted (s1 at 9 recorded episodes, s2's
# count unrecorded; neither partial is in `datasets/p33_pear`). The defaults
# below give each shard a distinct 30-seed block, and `claim_seed` refuses any
# seed already handed out in this driver process. A resumed driver is a new
# process, so cross-process uniqueness is still the operator's job: do not
# reuse a block an earlier launch consumed.
SEEDS=(${P33_SEEDS:-41 71 101})
NAMES=(${P33_SHARDS:-s0 s1 s2})

# The used-seed set for this driver process (space-delimited, so the substring
# test is safe under `set -u`). `claim_seed` writes the accepted seed to the
# global `CLAIMED_SEED` - it must not run in a `$(...)` subshell, whose copy of
# `USED_SEEDS` would be discarded and every call would hand out its candidate.
USED_SEEDS=" "
CLAIMED_SEED=""
claim_seed() {  # claim_seed <candidate> -> sets CLAIMED_SEED to an unused seed
    local seed=$1 guard=0
    while [[ " $USED_SEEDS " == *" $seed "* ]]; do
        echo "[p33c] seed $seed already used in this driver; advancing" >&2
        seed=$((seed + 1))
        guard=$((guard + 1))
        if [ "$guard" -gt 32 ]; then
            echo "[p33c] no distinct seed within 32 steps of $1" >&2
            exit 1
        fi
    done
    USED_SEEDS+="$seed "
    CLAIMED_SEED=$seed
}

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/meshes.py \
    src/fruit_sorting/fruits.py src/fruit_sorting/bed.py \
    src/fruit_sorting/bimanual.py src/fruit_sorting/scene.py \
    > logs/p33/C_collect_md5_before.txt

count_one() { python3 -c "import json;print(len(json.load(open('$1/index.json'))))" 2>/dev/null || echo 0; }
count_dirs() { local t=0 d; for d in "$@"; do t=$((t + $(count_one "$d"))); done; echo "$t"; }

collect_into() {  # collect_into <dir> <seed> <log>
    local dir=$1 seed=$2 log=$3 code=0
    mkdir -p "$dir"
    echo "[p33c] collect dir=$dir seed=$seed $(date +%H:%M:%S)"
    HEADLESS=1 FRUIT_CAMERA_RES=240,424 SEED=$seed \
        FRUIT_EPISODES=$PER_RUN FRUIT_DEMO_DIR="$dir" \
        FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 \
        FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 \
        FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 \
        RUN_LIMIT=7200 scripts/154_claim_run.sh "$log" \
        scripts/run.sh scripts/40_collect_demos.py > "${log%.log}.out" 2>&1 || code=$?
    echo "[p33c] collect exit=$code dir=$dir n=$(count_one "$dir") $(date +%H:%M:%S)"
    return 0
}

run_shard() {  # run_shard <name> <base-dir> <seed>
    local name=$1 base=$2 seed=$3
    local dirs=("$base") attempt=0 total dir extra
    # A resumed driver must re-adopt the retry directories an earlier launch
    # already filled (the s0 shard needed two runs; without this its second
    # directory would be dropped from the merge).
    for extra in "${base}"_r*/; do
        [ -f "${extra}index.json" ] && dirs+=("${extra%/}")
    done
    total=$(count_dirs "${dirs[@]}")
    echo "[p33c] $name start: $total/$QUOTA in ${dirs[*]}"
    while [ "$total" -lt "$QUOTA" ]; do
        attempt=$((attempt + 1))
        if [ "$attempt" -gt 6 ]; then
            echo "[p33c] $name GAVE UP at $total/$QUOTA after $((attempt - 1)) runs"
            break
        fi
        if [ "$attempt" -eq 1 ]; then
            dir="$base"
            [ -d "$dir" ] || mkdir -p "$dir"
        else
            dir="${base}_r${attempt}"
            dirs+=("$dir")
        fi
        claim_seed "$((seed + attempt - 1))"
        collect_into "$dir" "$CLAIMED_SEED" "logs/p33/C_collect_${name}_${attempt}.log"
        total=$(count_dirs "${dirs[@]}")
        echo "[p33c] $name attempt $attempt -> $total/$QUOTA"
    done
    printf '%s\n' "${dirs[@]}" > "logs/p33/C_dirs_${name}.txt"
}

echo "[p33c] start $(date +%H:%M:%S) quota=$QUOTA/shard per_run=$PER_RUN"
for i in "${!NAMES[@]}"; do
    run_shard "${NAMES[$i]}" "datasets/p33_pear_${NAMES[$i]}" "${SEEDS[$i]}"
done

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/meshes.py \
    src/fruit_sorting/fruits.py src/fruit_sorting/bed.py \
    src/fruit_sorting/bimanual.py src/fruit_sorting/scene.py \
    > logs/p33/C_collect_md5_after.txt
if ! diff -q logs/p33/C_collect_md5_before.txt logs/p33/C_collect_md5_after.txt >/dev/null; then
    echo "[p33c] WARNING: the tree changed while the shards ran"
fi

for n in "${NAMES[@]}"; do
    rows=$(grep -h 'two-line attempt' logs/p33/C_collect_${n}_*.log 2>/dev/null | wc -l)
    echo "[p33c] shard $n: $(count_dirs $(cat logs/p33/C_dirs_${n}.txt)) episodes, ${rows} attempt rows"
done

# Merge exactly the directories that produced episodes, in shard order.
ALL=""
for n in "${NAMES[@]}"; do
    while read -r d; do
        [ -n "$d" ] || continue
        if [ -f "$d/index.json" ]; then ALL="$ALL $d"; else echo "[p33c] skip missing $d"; fi
    done < "logs/p33/C_dirs_${n}.txt"
done
echo "[p33c] merge -> datasets/p33_pear from:$ALL"
rm -rf datasets/p33_pear
# shellcheck disable=SC2086
python3 scripts/41_merge_demos.py --inputs $ALL --out datasets/p33_pear | tee logs/p33/C_merge.log
python3 scripts/106_index_audit.py --root datasets > logs/p33/C_index_audit.txt 2>&1
echo "[p33c] index audit exit=$?"
echo "[p33c] done $(date +%H:%M:%S)"
