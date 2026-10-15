set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/p2d
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
status=0
run() {
    local log=$1 limit=$2 code; shift 2
    echo "[p2d] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[p2d] exit=$code $(date +%H:%M:%S) $log"
    [ "$code" -ne 0 ] || [ ! -s "$log" ] && { echo "[p2d] FAIL log=$log exit=$code"; status=1; }
    return 0
}
PATCH=(FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1)
WAVE=(FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_WAVE=1)
# the ladder peak: determinism + a dose double
run logs/p2d/54_d160_b.log 7200 "${TWO[@]}" "${PATCH[@]}" FRUIT_SUPPLY_PATCH_DENSITY=1.60
# the wave-sheet transfer, now that D reaches the wave schedule
run logs/p2d/62_wave_d150.log 7200 "${TWO[@]}" "${WAVE[@]}" FRUIT_SUPPLY_PATCH_DENSITY=1.50
run logs/p2d/63_wave_d160.log 7200 "${TWO[@]}" "${WAVE[@]}" FRUIT_SUPPLY_PATCH_DENSITY=1.60
[ "$status" -ne 0 ] && { echo "[p2d] incomplete"; exit 1; }
echo "[p2d] determinism (D=1.60 patch double)"
python3 logs/w4/compare_streams.py --physics-only logs/p2d/52_d160.log logs/p2d/54_d160_b.log | tail -1
exit "$status"
