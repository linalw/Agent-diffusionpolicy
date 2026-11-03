#!/usr/bin/env bash
# P108 - the aim census, the four-arm aperture/spacing battery, and the no-harm.
#
#   bash logs/p108/run_p108.sh census     # the traced aim-census cell (15, seed 5)
#   bash logs/p108/run_p108.sh battery    # S / B / E (4 seeds) + C (2 seeds)
#   bash logs/p108/run_p108.sh noharm     # the acceptance with every knob unset
#
# The cell is the **scripted single arm** (`FRUIT_BIARM=0`): the two-line
# scheduler refuses a non-`openarm` hand by construction (`tasks.py`), so the
# cage only ever runs here.  Every cell carries the *same* instrumentation
# (`FRUIT_CAGE_PROBE` is a no-op on the shipped hand; `FRUIT_PLACE_TRACE` and
# `FRUIT_CARRY_DIAG` are the landing / loaded-slide guards) so the arms are
# compared inside one instrumented batch - the tree's own rule.
#
# The values are the ones `logs/p108/PREREG.md` (md5 7ea66620...) pinned:
#   aperture 200 mm  = 2*(58.1 mm arrival + 35 mm r_max + 4 mm margin), the
#                      smallest 10 mm multiple above the census's need
#   gap_min  0.150 m = 100 (A/2) + 10 (plate) + 35 (r_max) + 4 (margin) mm
set -euo pipefail
cd "$(dirname "$0")/../.."

APERTURE=${APERTURE:-0.100}      # face radius -> a 200 mm aperture
GAP_MIN=${GAP_MIN:-0.150}        # the shipped scatter is 0.10-0.35 m
SEEDS=${SEEDS:-"5 6 101 202"}
ATTEMPTS=${ATTEMPTS:-20}
OUT=logs/p108

# B is the *shipped* 120 mm cage: the aperture knob must stay unset there, or
# the "control" would be the treatment.
cage_env() { echo "FRUIT_GRIPPER_KIND=cage4 ${1:+FRUIT_CAGE_OPEN_FACE_R=$1}"; }
inst() { echo "FRUIT_CAGE_PROBE=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_PLACE_TRACE=1"; }

run_cell() {  # name seed extra-env...
    local name=$1 seed=$2; shift 2
    if grep -q '^\[fruit\] \[stats\]' "${OUT}/${name}_s${seed}.log" 2>/dev/null; then
        echo "=== ${name} seed ${seed} (already complete, skipped)"
        return 0
    fi
    echo "=== ${name} seed ${seed} $*"
    env FRUIT_BIARM=0 SEED="${seed}" ATTEMPTS="${ATTEMPTS}" $(inst) "$@" \
        scripts/run.sh scripts/20_pick_place.py > "${OUT}/${name}_s${seed}.log" 2>&1
    grep -E '^\[fruit\] \[stats\]' "${OUT}/${name}_s${seed}.log" || true
}

what=${1:-battery}

if [ "$what" = "census" ]; then
    # `FRUIT_FRUIT_TRACE_ARM=1` is the declared branch-moving read: a *mechanism*
    # cell, its rates are not quoted.
    echo "=== census cage, 15 attempts, seed 5"
    env FRUIT_GRIPPER_KIND=cage4 FRUIT_BIARM=0 SEED=5 ATTEMPTS=15 $(inst) \
        FRUIT_CYCLE_REPORT=1 FRUIT_FRUIT_TRACE=2000 FRUIT_FRUIT_TRACE_ARM=1 \
        FRUIT_FRUIT_TRACE_DIR="${OUT}/tr_cage_s5" \
        scripts/run.sh scripts/20_pick_place.py > "${OUT}/cage_s5_traced.log" 2>&1
    python3 logs/p108/census.py "${OUT}/tr_cage_s5" > "${OUT}/census.txt" 2>&1
    sed -n '/^1\./,$p' "${OUT}/census.txt"
fi

if [ "$what" = "battery" ]; then
    for seed in $SEEDS; do
        run_cell S "${seed}"                              # shipped hand, shipped supply
        run_cell B "${seed}" $(cage_env)                  # cage120, shipped supply
        run_cell E "${seed}" $(cage_env "$APERTURE")      # cage200, shipped supply
        case " $SEEDS " in
            *" 101 "*|*" 202 "*) ;;                       # C is the 2-seed spacing arm
        esac
    done
    for seed in 5 6; do
        run_cell C "${seed}" $(cage_env "$APERTURE") FRUIT_SUPPLY_GAP_MIN="${GAP_MIN}"
    done
    python3 logs/p108/p108_report.py \
        ${OUT}/S_s5.log ${OUT}/S_s6.log ${OUT}/S_s101.log ${OUT}/S_s202.log \
        ${OUT}/B_s5.log ${OUT}/B_s6.log ${OUT}/B_s101.log ${OUT}/B_s202.log \
        ${OUT}/E_s5.log ${OUT}/E_s6.log ${OUT}/E_s101.log ${OUT}/E_s202.log \
        ${OUT}/C_s5.log ${OUT}/C_s6.log > ${OUT}/p108_report.txt 2>&1 || true
    tail -30 ${OUT}/p108_report.txt
fi

if [ "$what" = "noharm" ]; then
    SKIP_SELFCHECK=1 ACCEPT_LOG=${OUT}/accept_noharm.log scripts/accept.sh \
        > ${OUT}/accept_noharm.driver 2>&1 || true
    tail -4 ${OUT}/accept_noharm.driver
    python3 logs/p108/p108_report.py --same \
        ${OUT}/accept_noharm.log logs/p107/accept_noharm.log \
        --drop '[cage],[ftrace],[cycle],place trace'
fi
