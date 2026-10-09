#!/usr/bin/env bash
# Launch N concurrent scripted pick-and-place instances and measure the ceiling.
#
#   scripts/183_concurrency_probe.sh 3            # 3 concurrent ATTEMPTS=1 runs
#   ATTEMPTS=10 TAG=eq scripts/183_concurrency_probe.sh 3
#
# Each instance runs `scripts/20_pick_place.py` in its own namespace
# (`logs/x1/inst_<tag>_<i>/{demo,record,posture}`) and its own log
# `logs/x1/<tag>_i<i>.log`; the wall time per instance goes to
# `logs/x1/<tag>_wall.txt` and a 1 Hz `nvidia-smi` sample to
# `logs/x1/gpu_<tag>.csv`. The driver kills only the process groups it started
# (`PROBE_LIMIT`, default 1800 s) and never touches a process it did not spawn.
#
# This is the X1 measurement path: it deliberately does NOT go through
# `scripts/154_claim_run.sh` (whose global `pgrep python.sh` claim is exactly
# what forbids concurrency today). After the ceiling is known, lanes use
# `scripts/180_claim_slot.sh` with `FRUIT_CLAIM_SLOTS=N*`.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

n=${1:?usage: $0 N [attempts]}
attempts=${2:-${ATTEMPTS:-1}}
tag=${TAG:-n$n}
seed=${SEED:-5}
limit=${PROBE_LIMIT:-1800}
out=${PROBE_OUT:-logs/x1}
mkdir -p "$out"

wall="$out/${tag}_wall.txt"
: > "$wall"
: > "$out/${tag}_pid.txt"

pids=()
for i in $(seq 1 "$n"); do
    inst="$out/inst_${tag}_$i"
    mkdir -p "$inst"
    setsid env HEADLESS=1 ATTEMPTS="$attempts" SEED="$seed" \
        FRUIT_DEMO_DIR="$inst/demo" FRUIT_RECORD_DIR="$inst/record" \
        FRUIT_POSTURE_DIR="$inst/posture" \
        X1_WALL="$wall" X1_IDX="$i" \
        bash -c '
            s=$(date +%s.%N)
            scripts/run.sh scripts/20_pick_place.py
            c=$?
            e=$(date +%s.%N)
            echo "$X1_IDX $s $e $c" >> "$X1_WALL"
            exit $c
        ' > "$out/${tag}_i$i.log" 2>&1 &
    p=$!
    pids+=("$p")
    echo "$i $p" >> "$out/${tag}_pid.txt"
done
echo "[probe] launched N=$n attempts=$attempts tag=$tag pids=${pids[*]}"

nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,power.draw \
    --format=csv,noheader,nounits -l 1 > "$out/gpu_$tag.csv" 2>/dev/null &
gpu_pid=$!

(
    sleep "$limit"
    for p in "${pids[@]}"; do
        if kill -0 "$p" 2>/dev/null; then
            echo "[probe] TIMEOUT ${limit}s; killing group $p" >> "$wall"
            kill -TERM -- "-$p" 2>/dev/null || kill -TERM "$p" 2>/dev/null
        fi
    done
) &
wd=$!

t0=$(date +%s.%N)
codes=()
for p in "${pids[@]}"; do
    wait "$p"
    codes+=("$?")
done
t1=$(date +%s.%N)
kill "$wd" 2>/dev/null || true
kill "$gpu_pid" 2>/dev/null || true
wait "$wd" 2>/dev/null || true
wait "$gpu_pid" 2>/dev/null || true

awk -v t0="$t0" -v t1="$t1" -v n="$n" -v a="$attempts" 'BEGIN {
    printf "[probe] N=%d attempts=%d wall_total=%.1fs\n", n, a, t1 - t0
}'
sort -n "$wall" | while read -r idx s e c; do
    awk -v i="$idx" -v s="$s" -v e="$e" -v c="$c" 'BEGIN {
        printf "[probe] instance %s wall=%.1fs exit=%s\n", i, e - s, c
    }'
done

if [ -n "${REF:-}" ]; then
    echo "[probe] equivalence vs REF=$REF"
    # shellcheck disable=SC2086
    python3 scripts/182_run_equiv.py "$REF" "$out/${tag}_i"*.log || true
fi
