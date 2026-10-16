set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/p1c
# P1c: the composition-controlled control (pre-registration: logs/p1c/PREREGISTRATION.md).
# A single-grade supply holds the presented multiset fixed BY CONSTRUCTION, so D
# is the only thing that varies. Single arm (the two-line's pure grade routing
# would starve one arm on a single-grade supply).
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5)
SUP=(FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_SPECIES=apple)
status=0
run() {
    local log=$1 limit=$2 code; shift 2
    echo "[p1c] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[p1c] exit=$code $(date +%H:%M:%S) $log"
    [ "$code" -ne 0 ] || [ ! -s "$log" ] && { echo "[p1c] FAIL log=$log"; status=1; }
    return 0
}
run logs/p1c/D0_apple_d100.log 7200 "${SUP[@]}"
run logs/p1c/D1_apple_d160.log 7200 "${SUP[@]}" FRUIT_SUPPLY_PATCH_DENSITY=1.60
run logs/p1c/D2_apple_d160_b.log 7200 "${SUP[@]}" FRUIT_SUPPLY_PATCH_DENSITY=1.60
[ "$status" -ne 0 ] && { echo "[p1c] incomplete"; exit 1; }

echo "[p1c] the per-attempt readout with the class held fixed"
{
    printf "%-14s %-10s %-8s %-10s %-16s %-10s\n" config real_attempts placed s_per_attempt \
        "empty_slots/attempt" picks_per_min
    for pair in "D0_apple_d100:D=1.00" "D1_apple_d160:D=1.60" "D2_apple_d160_b:D=1.60-b"; do
        f="logs/p1c/${pair%%:*}.log"; label="${pair##*:}"
        at=$(grep -oE "attempts=[0-9]+" "$f" | tail -1 | cut -d= -f2)
        pl=$(grep -oE "successes=[0-9]+" "$f" | tail -1 | cut -d= -f2)
        spa=$(grep -oE "[0-9.]+s/attempt" "$f" | tail -1 | tr -d 's/attempt')
        ne=$(grep -c "no eligible fruit" "$f")
        ppm=$(grep -oE "[0-9.]+ (fruits|placed)/min" "$f" | tail -1 | cut -d' ' -f1)
        awk -v l="$label" -v p="$pl" -v a="$at" -v s="$spa" -v n="$ne" \
            'BEGIN{printf "%-22s %-8s %-10s %-12s %-14s %-10s\n", l, p"/"a, s, \
                (a>0? sprintf("%.2f", n/a):"-"), (s>0? sprintf("%.2f", p*60/s):"-")}'
    done
} | tee logs/p1c/80_readout.txt

echo "[p1c] determinism (D=1.60 apple double)"
diff <(grep "^\[fruit\]" logs/p1c/D1_apple_d160.log | grep -v "\[supply\]") \
     <(grep "^\[fruit\]" logs/p1c/D2_apple_d160_b.log | grep -v "\[supply\]") \
    > logs/p1c/81_d160_diff.txt 2>&1 \
    && echo "[p1c] PHYSICS IDENTICAL" || echo "[p1c] differs ($(wc -l < logs/p1c/81_d160_diff.txt) lines)"
echo "[p1c] done status=$status"
exit "$status"
