set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs/p
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 ATTEMPTS=20 SEED=5)
TWO=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1)
PATCH=(FRUIT_SUPPLY_PATCH=1)
status=0
run() {  # run <log> <limit> <env...>
    local log=$1 limit=$2 code
    shift 2
    echo "[p1] START $(date +%H:%M:%S) $log $*"
    RUN_LIMIT="$limit" scripts/154_claim_run.sh "$log" "${BASE[@]}" "${TWO[@]}" \
        "${PATCH[@]}" "$@" scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[p1] exit=$code $(date +%H:%M:%S) $log"
    if [ "$code" -ne 0 ] || [ ! -s "$log" ]; then
        echo "[p1] FAIL log=$log exit=$code"; status=1
    fi
}

# 00 control + 10/11 D=1.5 + 20/21 D=2.0
run logs/p/00_control.log        7200
run logs/p/10_density15.log      7200 FRUIT_SUPPLY_PATCH_DENSITY=1.5
run logs/p/11_density15_b.log    7200 FRUIT_SUPPLY_PATCH_DENSITY=1.5
run logs/p/20_density20.log      7200 FRUIT_SUPPLY_PATCH_DENSITY=2.0
run logs/p/21_density20_b.log    7200 FRUIT_SUPPLY_PATCH_DENSITY=2.0
# 30 density+speed ; 40 aggressive + re-calibrated floor (the travel time kept ~1.5 s:
# the floor = pick_lead + v*lead + margin, so at 0.18 the shipped 1.5 s is already time-
# constant; the override keeps it explicit for the lane)
run logs/p/30_density15_spd015.log 7200 FRUIT_SUPPLY_PATCH_DENSITY=1.5 FRUIT_BELT_SPEED=0.15
run logs/p/40_density20_spd018.log 7200 FRUIT_SUPPLY_PATCH_DENSITY=2.0 FRUIT_BELT_SPEED=0.18 \
    FRUIT_BIARM_SELECT_LEAD_S=1.5

[ "$status" -ne 0 ] && { echo "[p1] battery incomplete"; exit 1; }

echo "[p1] report"
python3 scripts/186_w6_report.py --label p1-battery \
    logs/p/00_control.log logs/p/10_density15.log logs/p/11_density15_b.log \
    logs/p/20_density20.log logs/p/21_density20_b.log \
    logs/p/30_density15_spd015.log logs/p/40_density20_spd018.log \
    | tee logs/p/50_battery_report.txt
[ "${PIPESTATUS[0]}" -ne 0 ] && status=1

echo "[p1] determinism (double-run bit-identity)"
for pair in 10 11 20 21; do
    a="logs/p/${pair:0:2}"; b="logs/p/${pair: -2}"
    python3 logs/w4/compare_streams.py --physics-only "logs/p/${pair}.log" \
        "logs/p/${pair}b.log" 2>/dev/null && echo "[p1] $pair OK" || status=1
done 2>/dev/null || true
# the double-run pairs above are named 10/11 and 20/21; compare them explicitly
python3 logs/w4/compare_streams.py --physics-only logs/p/10_density15.log logs/p/11_density15_b.log \
    | tail -1 || status=1
python3 logs/w4/compare_streams.py --physics-only logs/p/20_density20.log logs/p/21_density20_b.log \
    | tail -1 || status=1

echo "[p1] done status=$status"
exit "$status"
