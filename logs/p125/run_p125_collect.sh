#!/usr/bin/env bash
# P125 step 1: the **three-lane** two-line recollection.
#
# Scenario (the shipped collector scenario, P124's scene):
#   * `FRUIT_OUTPUT_LANES=3` - the third output body (P123). The scripted
#     two-line routes grade A left / B right / C skipped, so the third lane is
#     never a target: it is geometry, a collider and a camera-visible body. That
#     is exactly the input change the recollection has to teach (P124 measured
#     the canary at 4/10 on this scene against 8/10 on two lanes).
#   * `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1` - the shipped two-line branch;
#   * `FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_WAVE=1` + the balanced A:B:C mix -
#     the shipped two-line supply package, pinned explicitly (`logs/p33` recipe);
#   * camera 240,424 (the collection/training/eval view), shipped belt 0.12.
#
# **Sequential** shards with a per-run success cap, the P33 shape: the 2026-10-12
# W7-C batch hit the known blocking `RenderingManager.render()` wedge in all
# three parallel shards at once; a sequential run collected cleanly. Each run is
# bounded (`P125_PER_RUN=24` successes) so a wedge costs at most one run; the
# collector's own soft watchdog skips an over-budget attempt without stopping the
# belt, and a hard wedge exits the shard and this loop advances the seed.
#
#   nohup bash logs/p125/run_p125_collect.sh > logs/p125/collect_driver.log 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
mkdir -p logs/p125

QUOTA=${P125_QUOTA:-54}      # successes per shard (3 x 54 = 162 target)
# 17 successes per process, measured on the 2026-11-07 smoke: one process runs
# two chunks of 17 attempts and records ~28 successes (the last chunk's
# successes overshoot the target by design, `collect_two_line`), so two runs a
# shard land at ~56 and the store at ~168 - the dense store's 158 / P33's 180.
PER_RUN=${P125_PER_RUN:-17}
SEEDS=(${P125_SEEDS:-501 601 701})
NAMES=(${P125_SHARDS:-s0 s1 s2})

USED_SEEDS=" "
CLAIMED_SEED=""
claim_seed() {  # claim_seed <candidate> -> sets CLAIMED_SEED to an unused seed
    local seed=$1 guard=0
    while [[ " $USED_SEEDS " == *" $seed "* ]]; do
        echo "[p125] seed $seed already used in this driver; advancing" >&2
        seed=$((seed + 1))
        guard=$((guard + 1))
        if [ "$guard" -gt 32 ]; then
            echo "[p125] no distinct seed within 32 steps of $1" >&2
            exit 1
        fi
    done
    USED_SEEDS+="$seed "
    CLAIMED_SEED=$seed
}

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/meshes.py \
    src/fruit_sorting/fruits.py src/fruit_sorting/bed.py \
    src/fruit_sorting/bimanual.py src/fruit_sorting/scene.py \
    src/fruit_sorting/assets.py src/fruit_sorting/conveyor.py \
    scripts/40_collect_demos.py > logs/p125/collect_md5_before.txt

count_one() { python3 -c "import json;print(len(json.load(open('$1/index.json'))))" 2>/dev/null || echo 0; }
count_dirs() { local t=0 d; for d in "$@"; do t=$((t + $(count_one "$d"))); done; echo "$t"; }

collect_into() {  # collect_into <dir> <seed> <log>
    local dir=$1 seed=$2 log=$3 code=0
    mkdir -p "$dir"
    echo "[p125] collect dir=$dir seed=$seed $(date +%H:%M:%S)"
    HEADLESS=1 FRUIT_CAMERA_RES=240,424 SEED=$seed \
        FRUIT_EPISODES=$PER_RUN FRUIT_DEMO_DIR="$dir" \
        FRUIT_OUTPUT_LANES=3 \
        FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 \
        FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_WAVE=1 \
        FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 \
        RUN_LIMIT=5400 scripts/154_claim_run.sh "$log" \
        scripts/run.sh scripts/40_collect_demos.py > "${log%.log}.out" 2>&1 || code=$?
    echo "[p125] collect exit=$code dir=$dir n=$(count_one "$dir") $(date +%H:%M:%S)"
    return 0
}

run_shard() {  # run_shard <name> <base-dir> <seed>
    local name=$1 base=$2 seed=$3
    local dirs=("$base") attempt=0 total dir extra
    for extra in "${base}"_r*/; do
        [ -f "${extra}index.json" ] && dirs+=("${extra%/}")
    done
    total=$(count_dirs "${dirs[@]}")
    echo "[p125] $name start: $total/$QUOTA in ${dirs[*]}"
    while [ "$total" -lt "$QUOTA" ]; do
        attempt=$((attempt + 1))
        if [ "$attempt" -gt 8 ]; then
            echo "[p125] $name GAVE UP at $total/$QUOTA after $((attempt - 1)) runs"
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
        collect_into "$dir" "$CLAIMED_SEED" "logs/p125/collect_${name}_${attempt}.log"
        total=$(count_dirs "${dirs[@]}")
        echo "[p125] $name attempt $attempt -> $total/$QUOTA"
    done
    printf '%s\n' "${dirs[@]}" > "logs/p125/dirs_${name}.txt"
}

echo "[p125] start $(date +%H:%M:%S) quota=$QUOTA/shard per_run=$PER_RUN"
for i in "${!NAMES[@]}"; do
    run_shard "${NAMES[$i]}" "datasets/p125_three_lane_${NAMES[$i]}" "${SEEDS[$i]}"
done

md5sum src/fruit_sorting/tasks.py src/fruit_sorting/meshes.py \
    src/fruit_sorting/fruits.py src/fruit_sorting/bed.py \
    src/fruit_sorting/bimanual.py src/fruit_sorting/scene.py \
    src/fruit_sorting/assets.py src/fruit_sorting/conveyor.py \
    scripts/40_collect_demos.py > logs/p125/collect_md5_after.txt
if ! diff -q logs/p125/collect_md5_before.txt logs/p125/collect_md5_after.txt >/dev/null; then
    echo "[p125] WARNING: the tree changed while the shards ran"
fi

for n in "${NAMES[@]}"; do
    rows=$(grep -h 'two-line attempt' logs/p125/collect_${n}_*.log 2>/dev/null | wc -l)
    echo "[p125] shard $n: $(count_dirs $(cat logs/p125/dirs_${n}.txt)) episodes, ${rows} attempt rows"
done

# Merge exactly the directories that produced episodes, in shard order.
ALL=""
for n in "${NAMES[@]}"; do
    while read -r d; do
        [ -n "$d" ] || continue
        if [ -f "$d/index.json" ]; then ALL="$ALL $d"; else echo "[p125] skip missing $d"; fi
    done < "logs/p125/dirs_${n}.txt"
done
echo "[p125] merge -> datasets/p125_three_lane from:$ALL"
rm -rf datasets/p125_three_lane
# shellcheck disable=SC2086
python3 scripts/41_merge_demos.py --inputs $ALL --out datasets/p125_three_lane | tee logs/p125/merge.log
python3 scripts/106_index_audit.py --root datasets > logs/p125/index_audit.txt 2>&1
echo "[p125] index audit exit=$?"

# The provenance the phase turns on: every shard's scene block.
python3 - <<'PY' | tee logs/p125/shards_scene.txt
import glob, json, os
for path in sorted(glob.glob("datasets/p125_three_lane_*/manifest.json")):
    m = json.load(open(path, encoding="utf-8"))
    scene = m.get("scene") or {}
    lanes = scene.get("output_lanes")
    print(
        f"{os.path.dirname(path)}: "
        f"lanes={len(lanes) if lanes is not None else 'MISSING'} "
        f"target={m.get('episodes_target')} seed={m.get('seed')} "
        f"camera={m.get('camera_res')} "
        f"two_line={m.get('collection', {}).get('biarm_twoline_resolved')} "
        f"supply={m.get('supply', {}).get('band', {}).get('schedule')}"
    )
PY
echo "[p125] done $(date +%H:%M:%S)"
