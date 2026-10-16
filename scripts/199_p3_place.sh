set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/p3
# P3: the place-leg shortening screen (pre-registration: logs/p3/PREREGISTRATION.md)
# Runs on the adoption-candidate branch (the two-line at D=1.60) - both supplies.
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
PATCH=(FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_PATCH_DENSITY=1.60)
WAVE=(FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_WAVE=1 FRUIT_SUPPLY_PATCH_DENSITY=1.60)
status=0

run() {
    local log=$1 limit=$2 code; shift 2
    echo "[p3] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "$@" \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[p3] exit=$code $(date +%H:%M:%S) $log"
    if [ "$code" -ne 0 ] || [ ! -s "$log" ]; then
        echo "[p3] FAIL log=$log exit=$code"; status=1
    fi
}

# candidate A (10 cm) and B (the cap-adjacent 11 cm), patch sheet; B double-run
run logs/p3/10_patch_shift10.log 7200 "${TWO[@]}" "${PATCH[@]}" FRUIT_PLACE_INNER_SHIFT=0.10
run logs/p3/11_patch_shift11.log 7200 "${TWO[@]}" "${PATCH[@]}" FRUIT_PLACE_INNER_SHIFT=0.11
run logs/p3/12_patch_shift11_b.log 7200 "${TWO[@]}" "${PATCH[@]}" FRUIT_PLACE_INNER_SHIFT=0.11
# the transfer of the winner to the wave sheet (its control: logs/p2d/63_wave_d160.log)
run logs/p3/20_wave_shift11.log 7200 "${TWO[@]}" "${WAVE[@]}" FRUIT_PLACE_INNER_SHIFT=0.11

[ "$status" -ne 0 ] && { echo "[p3] incomplete"; exit 1; }

echo "[p3] the span/interval report"
python3 scripts/186_w6_report.py --label p3 \
    logs/p2d/52_d160.log logs/p3/10_patch_shift10.log \
    logs/p3/11_patch_shift11.log logs/p3/12_patch_shift11_b.log \
    logs/p2d/63_wave_d160.log logs/p3/20_wave_shift11.log \
    | tee logs/p3/80_report.txt
[ "${PIPESTATUS[0]}" -ne 0 ] && status=1

echo "[p3] the place-leg length and the span table"
{
    printf "%-28s %-10s %-12s %-10s %-10s\n" config success s_per_attempt place_cm place_ticks
    for pair in "p2d/52_d160:patch-control" "p3/10_patch_shift10:patch-shift0.10" \
                "p3/11_patch_shift11:patch-shift0.11" "p3/12_patch_shift11_b:patch-shift0.11-b" \
                "p2d/63_wave_d160:wave-control" "p3/20_wave_shift11:wave-shift0.11"; do
        f="logs/${pair%%:*}"; label="${pair##*:}"
        rate=$(grep -oE "success_rate=[0-9]+%" "$f.log" 2>/dev/null | tail -1 | cut -d= -f2)
        spa=$(grep -oE "[0-9.]+s/attempt" "$f.log" 2>/dev/null | tail -1 | cut -d/ -f1)
        pcm=$(grep -oE "\[motion\] carry place[01]: [0-9.]+ cm" "$f.log" 2>/dev/null \
            | awk '{s+=$(NF-1); n++} END{if(n) printf "%.1f", s/n; else print "-"}')
        pticks=$(grep -oE "\[motion\] carry place[01]: [0-9.]+ cm, [0-9]+ ticks" "$f.log" 2>/dev/null \
            | awk '{s+=$NF; n++} END{if(n) printf "%.0f", s/n; else print "-"}')
        printf "%-28s %-10s %-12s %-10s %-10s\n" "$label" "${rate:--}" "${spa:--}" "${pcm:--}" "${pticks:--}"
    done
} | tee logs/p3/81_place_table.txt

echo "[p3] determinism (shift 0.11 double)"
diff <(grep "^\[fruit\]" logs/p3/11_patch_shift11.log | grep -v "\[supply\]") \
     <(grep "^\[fruit\]" logs/p3/12_patch_shift11_b.log | grep -v "\[supply\]") \
    > logs/p3/82_shift11_diff.txt 2>&1 \
    && echo "[p3] shift 0.11 double: PHYSICS IDENTICAL" \
    || { echo "[p3] shift 0.11 double: differs ($(wc -l < logs/p3/82_shift11_diff.txt) lines)"; }

echo "[p3] the motion gate on every screen run"
for f in logs/p3/10_patch_shift10.log logs/p3/11_patch_shift11.log \
         logs/p3/20_wave_shift11.log; do
    echo -n "[p3] gate $(basename "$f"): "
    python3 scripts/105_motion_regression.py "$f" 2>&1 | grep -E "^(PASS|FAIL)" | head -1
done

echo "[p3] done status=$status"
exit "$status"