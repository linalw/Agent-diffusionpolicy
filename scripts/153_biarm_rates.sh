#!/usr/bin/env bash
# F2 rate batch: N x 10 attempts of one arm configuration, on the frozen tree.
#
#   scripts/153_biarm_rates.sh biarm 5     # FRUIT_BIARM=1 (pipelined two-arm)
#   scripts/153_biarm_rates.sh single 5    # FRUIT_BIARM=0 (the F1 single-arm line)
#
# Every run goes through scripts/154_claim_run.sh (one simulator at a time, a
# stall guard, no killing other lanes). Logs: logs/biarm/<label>_<n>.log.
set -uo pipefail
cd "$(dirname "$0")/.."

mode=${1:-biarm}
runs=${2:-5}
case "$mode" in
    biarm)  label=rate_biarm ;;
    single) label=rate_single ;;
    *) echo "usage: $0 {biarm|single} [runs]"; exit 2 ;;
esac

echo "[rates] mode=$mode runs=$runs tree tasks.py md5=$(md5sum src/fruit_sorting/tasks.py | cut -d' ' -f1)"
for i in $(seq 1 "$runs"); do
    log="logs/biarm/${label}_${i}.log"
    if [ -f "$log" ]; then
        echo "[rates] skip existing $log"
        continue
    fi
    FRUIT_BIARM_env=$([ "$mode" = biarm ] && echo 1 || echo 0)
    scripts/154_claim_run.sh "$log" \
        HEADLESS=1 FRUIT_BIARM="$FRUIT_BIARM_env" FRUIT_MOTION_REPORT=1 \
        FRUIT_CYCLE_REPORT=1 ATTEMPTS=10 \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[rates] run $i/$runs exit=$code"
    [ "$code" -ne 0 ] && exit "$code"
done
echo "[rates] done"
