#!/usr/bin/env bash
# P36 phase 2: the 2x2 - the park's image x the proprio spoof (the mediator test).
#
#   RUN_LIMIT=25200 scripts/154_claim_run.sh logs/p36/A_driver.log \
#       scripts/219_p36_cells.sh
#
# **`RUN_LIMIT=25200` is part of the invocation.** The claim's watchdog defaults
# to 1800 s, which kills this batch after ~4 of the 12 runs; the driver therefore
# *refuses to start* without a limit >= 7200 s. It is not exported here: the
# limit belongs to the claim's env, so it is on the recorded command line.
#
# Four cells (`logs/p36/PREREG.md` section 2), the ONLY difference being the two
# knobs:
#   1  ready / ready          (the P35 C-batch scenario + the four diags) - control
#   2  park  / park           FRUIT_ARM_PARK=back                       - the lever
#   3  park  / ready-proprio  FRUIT_ARM_PARK=back FRUIT_PROPRIO_SPOOF=ready
#   4  ready / park-proprio   FRUIT_ARM_PARK=ready FRUIT_PROPRIO_SPOOF=back
#
# P43 phase 4 (A2): cells 1 and 4 pass `FRUIT_ARM_PARK=ready` **explicitly**.
# They are the "ready arm" cells, and since the P43 flip the direct
# presentation's default is `back` - an unset value would silently turn cells
# 1 and 4 into park cells and void the 2x2. `ready` restores the shipped pose
# exactly (cells 2 and 3 are unchanged: they were already explicit).
#
# Cell 1 is **not the shipped default**: it is the P35 C batch's arm A verbatim
# (the patch sheet, `FRUIT_POLICY_TRIGGER_ACQ=1`, the same seeds) with the four
# manipulation diags on - instrumentation is part of the measurement (AGENTS
# section 3b), so all four cells run the identical instrumented scenario.
#
# The cell order is a **randomised rotation** (`P36_ORDER_SEED`): one seeded
# permutation of the four cells is drawn once and rotated by one position per
# run, so every cell takes three *distinct* positions across the three runs (the
# pre-registered balance) without the plain `1,2,3,4 / 2,3,4,1 / 3,4,1,2` order's
# fixed "cell 1 is first in run 1" alias. The drawn order is printed in the
# header and in the driver log, and `220` prints it back.
#
# Env: RUN_LIMIT (required, >= 7200), RUNS=3 EPISODES=15 AB_SEEDS="77 101 202"
#      AB_POLICY_SEED=11 P36_ORDER_SEED=20261024 P36_DIR=logs/p36/A_ab
#      P36_CKPT=checkpoints/moe_v13s/policy_best.pt
#      P36_ONLY="2_1 3_2"  re-run only those cell_run pairs (keeps the rest)
# The header pins the **driver itself** (`md5sum "$0"`) beside the tree, so a
# later batch records which version of this script produced it.
# After the runs: scripts/220_p36_report.py "$P36_DIR".
set -uo pipefail

cd "$(dirname "$0")/.."

runs=${RUNS:-3}
episodes=${EPISODES:-15}
seeds=(${AB_SEEDS:-77 101 202})
policy_seed=${AB_POLICY_SEED:-11}
out=${P36_DIR:-logs/p36/A_ab}
ckpt=${P36_CKPT:-checkpoints/moe_v13s/policy_best.pt}
order_seed=${P36_ORDER_SEED:-20261024}
only=${P36_ONLY:-}

# --- H1: the claim's watchdog must outlive the batch ----------------------- #
limit=${RUN_LIMIT:-0}
if [ "${limit:-0}" -lt 7200 ]; then
    echo "FAIL: RUN_LIMIT=${limit} - this batch needs >= 7200 s (12 runs x 15"
    echo "      episodes; the P35 rate puts it at ~1.5 h, the 1800 s default"
    echo "      kills it after ~4 runs). Invoke as:"
    echo "      RUN_LIMIT=25200 scripts/154_claim_run.sh logs/p36/A_driver.log scripts/219_p36_cells.sh"
    exit 1
fi

cells=(
    "1|FRUIT_ARM_PARK=ready"
    "2|FRUIT_ARM_PARK=back"
    "3|FRUIT_ARM_PARK=back FRUIT_PROPRIO_SPOOF=ready"
    "4|FRUIT_ARM_PARK=ready FRUIT_PROPRIO_SPOOF=back"
)

if [ "${#seeds[@]}" -lt "$runs" ]; then
    echo "FAIL: need at least $runs seeds in AB_SEEDS (have ${#seeds[@]})"
    exit 1
fi

# The randomised rotation: one seeded permutation, rotated per run.
base=$(python3 - "$order_seed" <<'PY'
import random
import sys
print(*random.Random(int(sys.argv[1])).sample([1, 2, 3, 4], 4))
PY
)
if [ -z "$base" ]; then
    echo "FAIL: could not draw the cell order (python3)"
    exit 1
fi
base_arr=($base)

order_of() {
    local run=$1 k=$((($1 - 1) % 4)) i
    for i in 0 1 2 3; do
        printf '%s ' "${base_arr[$(( (i + k) % 4 ))]}"
    done
    echo
}

mkdir -p "$out"
{
    echo "P36 2x2 (the park image x the proprio spoof) $(date -Iseconds)"
    echo "  ${episodes} episodes x ${runs} runs per cell, policy seed=${policy_seed}"
    echo "  seeds: ${seeds[*]:0:$runs}"
    echo "  checkpoint: ${ckpt}  md5 $(md5sum "$ckpt" | cut -d' ' -f1)"
    echo "  claim RUN_LIMIT=${limit} s (the batch's wall ceiling)"
    echo "  cell order: randomised rotation, seed ${order_seed}, base ${base}"
    for i in $(seq 1 "$runs"); do
        echo "    run ${i} order: $(order_of "$i")"
    done
    echo "  cells:"
    for spec in "${cells[@]}"; do
        echo "    ${spec%%|*}  env='${spec#*|}'"
    done
    echo "  driver: scripts/219_p36_cells.sh md5 $(md5sum "$0" | cut -d' ' -f1)"
    echo "  tree:"
    md5sum src/fruit_sorting/rl_env.py src/fruit_sorting/tasks.py \
           configs/arm_parks.json configs/proprio_spoof.json \
           configs/motion_reference.json | sed 's/^/    /'
} | tee "${out}/A_header.txt"
echo

# One simulator at a time (AGENTS.md): another lane may hold it, so poll for a
# free one before each session and never kill a foreign process.
wait_for_sim() {
    local n
    n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    while [ "${n:-0}" -gt 0 ]; do
        echo "  [cells] simulator busy (${n} python.sh); waiting 60 s ($(date +%H:%M:%S))"
        sleep 60
        n=$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)
    done
}

run_one() {
    local label=$1 env_extra=$2 run=$3 seed=$4
    local log="$out/C${label}_${run}.log" started
    wait_for_sim
    started=$(date +%s)
    # shellcheck disable=SC2086
    env HEADLESS=1 FRUIT_CAMERA_RES=240,424 FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1 \
        FRUIT_POLICY_SEED="$policy_seed" FRUIT_SIZE_FILTER= \
        FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 \
        FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 \
        FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 \
        FRUIT_DYNAMIC_PICK=1 FRUIT_POLICY_TRIGGER_ACQ=1 \
        FRUIT_ACQ_DIAG=1 FRUIT_RESET_ALIGN_DIAG=1 FRUIT_PARK_DIAG=1 \
        FRUIT_SPOOF_DIAG=1 $env_extra \
        scripts/run.sh scripts/110_rl_rollout.py --ckpt "$ckpt" \
        --presentation direct --episodes "$episodes" --seeds "$seed" \
        --out "$out/raw/C${label}_${run}" > "$log" 2>&1
    printf '  cell %s run %d (seed %s, %ds): %s | spoof %s applied | park rows %s | episodes %s\n' \
        "$label" "$run" "$seed" "$(( $(date +%s) - started ))" \
        "$(grep -oE '\[rl\] rollout success [0-9]+/[0-9]+' "$log" | tail -1)" \
        "$(grep -c '\[spoof\].*applied=1' "$log")" \
        "$(grep -c '\[park\] episode' "$log")" \
        "$(grep -c '\[rl\] episode [0-9]*: .* success=' "$log")" \
        | tee -a "${out}/A_driver.txt"
}

batch_start=$(date +%s)
for i in $(seq 1 "$runs"); do
    seed=${seeds[$((i - 1))]}
    printf '  run %d order: %s (seed %s, %s)\n' "$i" "$(order_of "$i")" "$seed" \
        "$(date +%H:%M:%S)" | tee -a "${out}/A_driver.txt"
    for k in 0 1 2 3; do
        cell_id=${base_arr[$(( (k + i - 1) % 4 ))]}
        spec=${cells[$((cell_id - 1))]}
        if [ -n "$only" ] && [[ " $only " != *" ${cell_id}_${i} "* ]]; then
            printf '  cell %s run %d: skipped (P36_ONLY)\n' "$cell_id" "$i" \
                | tee -a "${out}/A_driver.txt"
            continue
        fi
        run_one "${cell_id}" "${spec#*|}" "$i" "$seed"
    done
done
printf '  batch wall %d s\n' "$(( $(date +%s) - batch_start ))" \
    | tee -a "${out}/A_driver.txt"

echo
python3 scripts/220_p36_report.py "$out" | tee "${out}/A_report.txt"
