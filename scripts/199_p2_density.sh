set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/p2d
# P2: the density's dose grid + the transfer (pre-registration: logs/p2d/PREREGISTRATION.md)
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
PATCH=(FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_SCATTER=1)
status=0

run() {  # run <log> <limit> <env...>
    local log=$1 limit=$2 code
    shift 2
    echo "[p2] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[p2] exit=$code $(date +%H:%M:%S) $log"
    if [ "$code" -ne 0 ] || [ ! -s "$log" ]; then
        echo "[p2] FAIL log=$log exit=$code"; status=1
    fi
}

# the dose ladder (two-line, patch sheet)
run logs/p2d/50_d125.log 7200 "${TWO[@]}" "${PATCH[@]}" FRUIT_SUPPLY_PATCH_DENSITY=1.25
run logs/p2d/51_d140.log 7200 "${TWO[@]}" "${PATCH[@]}" FRUIT_SUPPLY_PATCH_DENSITY=1.40
run logs/p2d/52_d160.log 7200 "${TWO[@]}" "${PATCH[@]}" FRUIT_SUPPLY_PATCH_DENSITY=1.60
run logs/p2d/53_d175.log 7200 "${TWO[@]}" "${PATCH[@]}" FRUIT_SUPPLY_PATCH_DENSITY=1.75
# the transfer to the two-line's other default supply (the dense wave sheet)
run logs/p2d/61_wave_control.log 7200 "${TWO[@]}" FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_WAVE=1
run logs/p2d/60_wave_d150.log      7200 "${TWO[@]}" FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_WAVE=1 \
    FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_PATCH_DENSITY=1.5
# the transfer to the single-arm line (patch sheet)
run logs/p2d/71_single_control.log 7200 "${PATCH[@]}"
run logs/p2d/70_single_d150.log    7200 "${PATCH[@]}" FRUIT_SUPPLY_PATCH_DENSITY=1.5

[ "$status" -ne 0 ] && { echo "[p2] battery incomplete"; exit 1; }

echo "[p2] the interval/lock-on report"
python3 scripts/186_w6_report.py --label p2 \
    logs/p/00_control.log logs/p/10_density15.log \
    logs/p2d/50_d125.log logs/p2d/51_d140.log logs/p2d/52_d160.log logs/p2d/53_d175.log \
    logs/p2d/61_wave_control.log logs/p2d/60_wave_d150.log \
    logs/p2d/71_single_control.log logs/p2d/70_single_d150.log \
    | tee logs/p2d/80_battery_report.txt
[ "${PIPESTATUS[0]}" -ne 0 ] && status=1

echo "[p2] the success/throughput curve"
{
    printf "%-26s %-12s %-10s %-8s\n" config success s_per_attempt placed_per_min
    for pair in "p/00_control:control" "p/10_density15:D1.50" \
                "p2/50_d125:D1.25" "p2/51_d140:D1.40" "p2/52_d160:D1.60" "p2/53_d175:D1.75" \
                "p2/61_wave_control:wave-D1.00" "p2/60_wave_d150:wave-D1.50" \
                "p2/71_single_control:single-D1.00" "p2/70_single_d150:single-D1.50"; do
        f="logs/${pair%%:*}"; label="${pair##*:}"
        rate=$(grep -oE "success_rate=[0-9]+%" "$f.log" 2>/dev/null | tail -1 | cut -d= -f2)
        spa=$(grep -oE "[0-9.]+s/attempt" "$f.log" 2>/dev/null | tail -1 | cut -d= -f2)
        ppm=$(grep -oE "[0-9.]+ (fruits|placed)/min" "$f.log" 2>/dev/null | tail -1 | cut -d' ' -f1)
        printf "%-26s %-12s %-10s %-8s\n" "$label" "${rate:--}" "${spa:--}" "${ppm:--}"
    done
} | tee logs/p2d/81_curve.txt

echo "[p2] done status=$status"
exit "$status"
# P2.1 follow-up (written after the first pass): the ladder's peak moved to
# D=1.60 (90 %, 11.25 s), so it needs the determinism double; and the wave
# transfer has to be re-measured with the density now reaching the wave
# schedule (the first attempt's "wave D=1.5" re-ran the patch sheet - the
# numbers were bit-identical to the patch run, which is how it was caught).
