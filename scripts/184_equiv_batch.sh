#!/usr/bin/env bash
# X1 equivalence batch: the same acceptance-style run sequential vs concurrent.
#
#   scripts/184_equiv_batch.sh            # 10 attempts each way
#   ATTEMPTS=5 scripts/184_equiv_batch.sh
#
# Way 1: one instance (scripts/183_concurrency_probe.sh 1) - "alone" as far as
# the machine allows; a co-lane on the legacy 154 claim may still be running
# (the report states which).
# Way 2: three distinct instances, each claiming a slot through
# scripts/180_claim_slot.sh with FRUIT_CLAIM_SLOTS=3 - the shipped parallel path.
#
# Every instance has its own log and output namespace; scripts/182_run_equiv.py
# then compares the [fruit] streams line-for-line. Exit is 182's verdict.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

attempts=${ATTEMPTS:-10}
out=${EQUIV_OUT:-logs/x1}
mkdir -p "$out"

echo "[equiv] way 1: sequential, ${attempts} attempts, $(date +%H:%M:%S)"
if [ "${SKIP_SEQ:-0}" = "1" ]; then
    echo "[equiv] sequential skipped (SKIP_SEQ=1); reusing $out/eqseq_i1.log"
else
    TAG=eqseq ATTEMPTS="$attempts" scripts/183_concurrency_probe.sh 1 "$attempts" || true
fi

echo "[equiv] way 2: 3 concurrent slots, ${attempts} attempts each, $(date +%H:%M:%S)"
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used \
    --format=csv,noheader,nounits -l 1 > "$out/gpu_eq3.csv" 2>/dev/null &
gpu_pid=$!
pids=()
for i in 1 2 3; do
    mkdir -p "$out/inst_eq3_$i"
    FRUIT_CLAIM_SLOTS=3 FRUIT_CLAIM_LABEL="eq3_$i" RUN_LIMIT=0 \
        scripts/180_claim_slot.sh "$out/eq3_i$i.log" \
        HEADLESS=1 ATTEMPTS="$attempts" SEED=5 \
        FRUIT_DEMO_DIR="$out/inst_eq3_$i/demo" \
        FRUIT_RECORD_DIR="$out/inst_eq3_$i/record" \
        FRUIT_POSTURE_DIR="$out/inst_eq3_$i/posture" \
        scripts/run.sh scripts/20_pick_place.py &
    pids+=("$!")
done
scripts/180_claim_slot.sh --status
codes=()
for p in "${pids[@]}"; do
    wait "$p"
    codes+=("$?")
done
kill "$gpu_pid" 2>/dev/null || true
wait "$gpu_pid" 2>/dev/null || true
echo "[equiv] concurrent exits: ${codes[*]} ($(date +%H:%M:%S))"

echo "[equiv] comparison"
python3 scripts/182_run_equiv.py "$out/eqseq_i1.log" "$out/eq3_i1.log" \
    "$out/eq3_i2.log" "$out/eq3_i3.log"
