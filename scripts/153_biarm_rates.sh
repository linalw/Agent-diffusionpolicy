#!/usr/bin/env bash
# F2 rate batch: N x 10 attempts of one arm configuration, on the frozen tree.
#
#   scripts/153_biarm_rates.sh two-line 5  # FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 (shipped since P85)
#   scripts/153_biarm_rates.sh shared 5    # FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0 (the F2 shared station)
#   scripts/153_biarm_rates.sh single 5    # FRUIT_BIARM=0 (the pre-P85 single arm)
#
# P85: the modes are explicit, because unset `FRUIT_BIARM`/`FRUIT_BIARM_TWOLINE`
# now mean the two-line. `two-line` is the shipped cell; `logs/biarm/` (pre-P85)
# is the **shared-station** branch and is reproduced with `shared`. `biarm` is
# kept as an alias of `two-line` for the old invocations.
#
# Every run goes through scripts/154_claim_run.sh (one simulator at a time, a
# stall guard, no killing other lanes). Logs: logs/biarm/<label>_<n>.log.
set -uo pipefail
cd "$(dirname "$0")/.."

mode=${1:-two-line}
runs=${2:-5}
case "$mode" in
    two-line|biarm) label=rate_biarm; sched=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1) ;;
    shared)         label=rate_shared; sched=(FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=0) ;;
    single)         label=rate_single; sched=(FRUIT_BIARM=0) ;;
    *) echo "usage: $0 {two-line|shared|single} [runs]"; exit 2 ;;
esac

echo "[rates] mode=$mode runs=$runs tree tasks.py md5=$(md5sum src/fruit_sorting/tasks.py | cut -d' ' -f1)"
for i in $(seq 1 "$runs"); do
    log="logs/biarm/${label}_${i}.log"
    if [ -f "$log" ]; then
        echo "[rates] skip existing $log"
        continue
    fi
    scripts/154_claim_run.sh "$log" \
        HEADLESS=1 "${sched[@]}" FRUIT_MOTION_REPORT=1 \
        FRUIT_CYCLE_REPORT=1 ATTEMPTS=10 \
        scripts/run.sh scripts/20_pick_place.py
    code=$?
    echo "[rates] run $i/$runs exit=$code"
    [ "$code" -ne 0 ] && exit "$code"
done
echo "[rates] done"
