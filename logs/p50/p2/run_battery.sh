#!/usr/bin/env bash
# P50 phase 2 battery - one claim per arm, arms C -> O.
#
# Run from the repo root:  bash logs/p50/p2/run_battery.sh
#
# Arms (PREREG section 3):
#   M1-O   the isolated offset probe (16 instances x 3 planned x x 2 passes),
#          knob ON; M1-C is the phase-1 log logs/p50/p1/offset_probe_s5.log
#   M1b-O  the live (release-attributed) probe, 120 s, knob ON; M1b-C is
#          logs/p50/p1/offset_live_s5.log - the planned-x sequences must match
#   M2     the shipped acceptance, SEED=5, 10 attempts: C (=0) then O (=1)
#   M3     the pear pool, SEED=5, 10 attempts: C then O (the inertness control)
#   M4     the acceptance with every P50 knob UNSET (the no-harm arm)
#
# Every run goes through scripts/154_claim_run.sh (the single-simulator claim;
# it requeues its own attempt if another lane's run overlaps).
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

OUT=logs/p50/p2
TABLE=configs/release_offsets_accept_s5.json
TABLE_PEAR=configs/release_offsets_pear_s5.json
CLAIM=scripts/154_claim_run.sh
ENTRY_RUN=scripts/run.sh

run() {
    local name=$1 entry=$2
    shift 2
    echo "=== ${name} start $(date +%H:%M:%S)  entry=${entry}  $*"
    env "$@" RUN_LIMIT=2400 "${CLAIM}" "${OUT}/${name}.log" "${ENTRY_RUN}" "${entry}"
    local code=$?
    echo "=== ${name} exit=${code} $(date +%H:%M:%S)"
    echo "${name} ${code}" >> "${OUT}/battery_exit.txt"
}

# -- M1-O: the compensated isolated table ---------------------------------- #
run m1o_probe logs/p50/p1/offset_probe.py \
    SEED=5 FRUIT_RELEASE_OFFSET=1 FRUIT_RELEASE_OFFSET_TABLE="${TABLE}"

# -- M1b-O: the compensated live line (the planned draws must not move) ----- #
run m1bo_live logs/p50/p1/offset_probe.py \
    SEED=5 FRUIT_OFFSET_MODE=live FRUIT_RELEASE_OFFSET=1 \
    FRUIT_RELEASE_OFFSET_TABLE="${TABLE}"

# -- M2: the shipped acceptance, seed 5 ------------------------------------ #
run m2_c scripts/20_pick_place.py \
    SEED=5 ATTEMPTS=10 HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 \
    FRUIT_RELEASE_OFFSET=0 FRUIT_RELEASE_OFFSET_DIAG=1
run m2_o scripts/20_pick_place.py \
    SEED=5 ATTEMPTS=10 HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 \
    FRUIT_RELEASE_OFFSET=1 FRUIT_RELEASE_OFFSET_TABLE="${TABLE}" \
    FRUIT_RELEASE_OFFSET_DIAG=1

# -- M3: the pear pool (identity table, the inertness control) -------------- #
run m3_c scripts/20_pick_place.py \
    SEED=5 ATTEMPTS=10 HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 \
    FRUIT_SUPPLY_SPECIES=pear FRUIT_RELEASE_OFFSET=0 FRUIT_RELEASE_OFFSET_DIAG=1
run m3_o scripts/20_pick_place.py \
    SEED=5 ATTEMPTS=10 HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 \
    FRUIT_SUPPLY_SPECIES=pear FRUIT_RELEASE_OFFSET=1 \
    FRUIT_RELEASE_OFFSET_TABLE="${TABLE_PEAR}" FRUIT_RELEASE_OFFSET_DIAG=1

# -- M4: the no-harm arm (every P50 knob unset) ---------------------------- #
run m4_unset scripts/20_pick_place.py \
    SEED=5 ATTEMPTS=10 HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1

echo "=== battery done $(date +%H:%M:%S)"
