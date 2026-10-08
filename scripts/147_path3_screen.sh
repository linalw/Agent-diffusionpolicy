#!/usr/bin/env bash
# Path-3 frontier screen: base vs track / event / vlash / a2c2 on one checkpoint.
#
#   scripts/147_path3_screen.sh
#
# Run-major interleaved: for each run (seed) all five arms run in order
# base, track, event, vlash, a2c2, so the comparison pairs the same spawner seed
# and the same simulator session stretch. One simulator at a time (polls
# `pgrep -fc python.sh` before every run; never kills a foreign process). Each
# run has a wall timeout (`RATE_TIMEOUT`, default 1500 s) that signals only this
# batch's run (the known contact-grind wedge); a timed-out run is recorded and
# retried once, then left as DROPPED. Completed runs are resumed (skipped) if
# the driver is re-invoked.
#
# Pre-registered in logs/path3/PREREGISTRATION.md. Env:
#   RUNS EPISODES SEEDS OUT RATE_TIMEOUT TIMING SKIP_TIMING
#   FRUIT_CKPT_PATH (base), FRUIT_VLASH_CKPT_PATH, FRUIT_A2C2_PATH
set -uo pipefail

cd "$(dirname "$0")/.."

runs=${RUNS:-3}
episodes=${EPISODES:-15}
seeds=(${SEEDS:-77 101 202})
out=${OUT:-logs/path3}
ckpt=${FRUIT_CKPT_PATH:-checkpoints/moe_v11/policy_best.pt}
vlash_ckpt=${FRUIT_VLASH_CKPT_PATH:-checkpoints/moe_v11_vlash/policy_best.pt}
a2c2_path=${FRUIT_A2C2_PATH:-checkpoints/moe_v11_correction/correction.pt}
policy_seed=${AB_POLICY_SEED:-11}
timeout_s=${RATE_TIMEOUT:-1500}
timing=${TIMING:-1}
skip_timing=${SKIP_TIMING:-0}
#: Which arms to run; the full pre-registered set is the default. A subset is
#: allowed for staging (e.g. while a fine-tune is still training); it is a
#: deviation only if the missing arm is never run in the same session.
arms_env=${ARMS:-"base track event vlash a2c2"}
read -ra arms <<< "$arms_env"

if [ "${#seeds[@]}" -lt "$runs" ]; then
    echo "FAIL: need at least $runs seeds (have ${#seeds[@]})" >&2
    exit 1
fi
required=("$ckpt")
for arm in "${arms[@]}"; do
    case "$arm" in
        vlash) required+=("$vlash_ckpt") ;;
        a2c2)  required+=("$a2c2_path") ;;
        combo) required+=("${COMBO_CKPT:-$ckpt}") ;;
    esac
done
for required_path in "${required[@]}"; do
    if [ ! -f "$required_path" ]; then
        echo "FAIL: required artifact missing: $required_path" >&2
        exit 1
    fi
done

mkdir -p "$out"
common="FRUIT_CAMERA_RES=240,424 FRUIT_POLICY_SEED=$policy_seed FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 FRUIT_POLICY_TRIGGER=arrival"

arm_spec() {  # $1 arm -> prints "<ckpt>|<extra env>"
    case "$1" in
        base)  echo "$ckpt|" ;;
        track) echo "$ckpt|FRUIT_POLICY_TRACK=1" ;;
        event) echo "$ckpt|FRUIT_POLICY_EVENT=1" ;;
        vlash) echo "$vlash_ckpt|FRUIT_VLASH=1" ;;
        a2c2)  echo "$ckpt|FRUIT_A2C2=$a2c2_path" ;;
        combo) echo "${COMBO_CKPT:-$ckpt}|${COMBO_ENV:-}" ;;
        *)     echo "|" ;;
    esac
}

wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [147] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

# run_one <label> <seed> <episodes> <extra_env> <extra_args> <log> <report>
run_one() {
    local label=$1 seed=$2 eps=$3 extra=$4 args=$5 log=$6 report=$7 rc
    wait_for_sim
    # shellcheck disable=SC2086
    env $common $extra HEADLESS=1 $report \
        scripts/run.sh scripts/110_rl_rollout.py $args --presentation direct \
        --episodes "$eps" --seeds "$seed" --out "$out/raw/${label}" \
        > "$log" 2>&1 &
    local pid=$!
    local waited=0
    while kill -0 "$pid" 2>/dev/null; do
        if [ "$waited" -ge "$timeout_s" ]; then
            echo "  [147] $label seed $seed TIMEOUT after ${timeout_s}s - signalling $pid"
            kill -INT "$pid" 2>/dev/null || true
            sleep 20
            kill -KILL "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
            echo "[147] TIMEOUT ${label} seed ${seed} at $(date +%F\ %H:%M:%S)" >> "$log"
            return 124
        fi
        sleep 10
        waited=$((waited + 10))
    done
    wait "$pid"; rc=$?
    return "$rc"
}

run_arm() {  # <arm> <run index> <seed> <suffix> <episodes> <report>
    local arm=$1 i=$2 seed=$3 suffix=$4 eps=$5 report=$6
    local spec arm_ckpt extra label log success retried
    spec=$(arm_spec "$arm")
    arm_ckpt=${spec%%|*}
    extra=${spec#*|}
    args="--ckpt $arm_ckpt"
    label="$arm"
    if [ "$suffix" = "timing" ]; then
        label="timing_${arm}"
    fi
    log="$out/${label}_${i}.log"
    if [ "$suffix" = "timing" ]; then
        log="$out/${label}.log"
    fi
    if [ -f "$log" ] && grep -q "\[rl\] rollout success" "$log"; then
        echo "  [147] $label run $i already complete - skip"
        return 0
    fi
    if [ -f "$log" ]; then
        mv "$log" "${log}.partial.$(date +%s)"
    fi
    for retried in 0 1; do
        echo "  [147] $label run $i seed $seed (episodes $eps) $(date +%H:%M:%S)"
        run_one "$label" "$seed" "$eps" "$extra" "$args" "$log" "$report"
        if grep -q "\[rl\] rollout success" "$log"; then
            success=$(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' "$log" | tail -1)
            echo "  [147] $label run $i: $success"
            return 0
        fi
        echo "  [147] $label run $i did not complete (rc=direct); retry=$retried"
        [ "$retried" -eq 0 ] && mv "$log" "${log}.failed.$(date +%s)"
    done
    echo "  [147] $label run $i DROPPED"
    return 1
}

echo "path-3 screen: $runs runs x $episodes episodes x ${#arms[@]} arms, seeds ${seeds[*]:0:$runs}"
echo "  base=${ckpt}"
echo "  vlash=${vlash_ckpt}"
echo "  a2c2=${a2c2_path}"

if [ "$timing" = "1" ] && [ "$skip_timing" = "0" ]; then
    for arm in "${arms[@]}"; do
        run_arm "$arm" 1 "${seeds[0]}" timing 3 \
            "FRUIT_RTC_REPORT=1" || true
    done
fi

for i in $(seq 1 "$runs"); do
    seed=${seeds[$((i - 1))]}
    for arm in "${arms[@]}"; do
        run_arm "$arm" "$i" "$seed" rate "$episodes" "" || true
    done
done

echo "path-3 screen driver DONE $(date +%F\ %H:%M:%S)"
