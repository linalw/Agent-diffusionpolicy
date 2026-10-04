#!/usr/bin/env bash
# Run N single-attempt probes and report which "branch" each one takes.
#
#   scripts/126_branch_probe.sh 5
#   HEADLESS=0 scripts/126_branch_probe.sh 3          # GUI/render path
#   FRUIT_CAMERA_ANNOTATORS=none scripts/126_branch_probe.sh 3
#
# Why: the scripted pipeline is not reproducible - the same command on the same code
# lands its first fruit at 8.5 cm from the pick point (a 328-tick descent), 8.7 cm
# (334 ticks) or 7.8 cm (302 ticks), and the whole run follows that branch. One
# attempt is enough to see which, in about two minutes instead of twelve, and the
# sequence of outcomes across N consecutive runs is what distinguishes "random" from
# "stable for a while, then changes" (WORKLOG "the run is not reproducible").
#
# Any pending comparison must be done inside one such stretch: probe, run both arms,
# probe again, and throw the comparison away if the branch changed.
set -uo pipefail

cd "$(dirname "$0")/.."

n=${1:-5}
out_dir=${PROBE_DIR:-logs/branch_probe}
mkdir -p "$out_dir"

echo "probing ${n}x  (HEADLESS=${HEADLESS:-1} CAMERA_ANNOTATORS=${FRUIT_CAMERA_ANNOTATORS:-rgb,distance_to_image_plane} PAUSE=${FRUIT_PAUSE_TIMELINE:-0})"
for i in $(seq 1 "$n"); do
    log="$out_dir/probe_$(date +%H%M%S)_$i.log"
    ATTEMPTS=1 FRUIT_MOTION_REPORT=1 scripts/run.sh scripts/20_pick_place.py > "$log" 2>&1
    first=$(grep -oE 'approach\(cartesian\): [0-9.]+ cm, [0-9]+ samples' "$log" | head -1)
    printf '  %2d/%d: %-44s %s\n' "$i" "$n" "${first:-no descent recorded}" "$(basename "$log")"
done
