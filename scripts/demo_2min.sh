#!/usr/bin/env bash
# One-command demonstration of the sorting cell.
#
#   scripts/demo_2min.sh            # headless: 3 picks + a video, prints the numbers
#   HEADLESS=0 scripts/demo_2min.sh # watch it in the Isaac window (GUI)
#
# Everything goes through scripts/run.sh, which raises the file-descriptor limit
# first: without that this Isaac build crashes with "dup failed ... Too many open
# files" about 40 s into the first camera read (see WORKLOG 2026-09-27).
#
# The demo ends by running the motion regression gate on its own log, and exits
# non-zero if it fails, so a demo that looks fine but breaks the budgets is not
# reported as a success. For the full ten-attempt acceptance (which also checks
# the baseline fingerprint) use scripts/accept.sh.
#
# It also runs scripts/selfcheck.sh first (the simulator-free checks), so a broken
# tree fails in seconds rather than after the simulator has started. Set
# SKIP_SELFCHECK=1 to skip that.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "${SKIP_SELFCHECK:-0}" != "1" ]; then
    echo "=== pre-flight self-check (SKIP_SELFCHECK=1 to skip) ==="
    if ! scripts/selfcheck.sh; then
        echo
        echo "FAIL: fix the self-check before running the demo"
        exit 1
    fi
    echo
fi

headless=${HEADLESS:-1}
attempts=${ATTEMPTS:-3}
cycles=${FRUIT_CYCLES:-1}

echo "=== 1/3  scripted pick-and-place (${attempts} picks, HEADLESS=${headless}) ==="
if [ "$headless" = "0" ]; then
    HEADLESS=0 FRUIT_GUI_SMOOTH=1 ATTEMPTS="${attempts}" FRUIT_MOTION_REPORT=1 \
        scripts/run.sh scripts/20_pick_place.py | tee "logs/demo_picks.log" | \
        grep -E "\[stats\]|\[run\] summary|grasped=|\[motion\]" || true
else
    HEADLESS=1 ATTEMPTS="${attempts}" FRUIT_MOTION_REPORT=1 \
        scripts/run.sh scripts/20_pick_place.py | tee "logs/demo_picks.log" | \
        grep -E "\[stats\]|\[run\] summary|grasped=" || true
fi

echo
echo "=== 2/3  record a clip (${cycles} cycle(s)) ==="
HEADLESS=1 FRUIT_CYCLES="${cycles}" FRUIT_VIDEO_DIR=logs/video_demo \
    scripts/run.sh scripts/70_record_video.py > logs/demo_video.log 2>&1 || true
grep -E "wrote |cycle .* result" logs/demo_video.log | tail -4 || true
for file in logs/video_demo/*.mp4; do
    [ -e "$file" ] && ffprobe -v error -show_entries stream=codec_name,width,height \
        -of default=noprint_wrappers=1 "$file" | tr '\n' ' ' && echo " <- $file"
done

echo
echo "=== 3/3  headline numbers this run ==="
grep -E "\[stats\]" logs/demo_picks.log | tail -1 || true
echo "reference results: scripted 18/20 = 90% (logs/355), hybrid 12/15 = 80% (logs/336),"
echo "                   kinematic gripper 10/10 isolated (logs/164_kinematic.log)"
echo "report: 项目总结报告.md   decision doc: 决策与交付.md"

echo
echo "=== motion gate  (descent speed vs the reference, a_win5 vs the friction budget) ==="
gate=0
# The success floor is relaxed to 2/3 here: a three-pick smoke test is not the
# ten-attempt acceptance, and the shipped suite's own rate is 9/10, so demanding
# 3/3 would make the demo flaky. The *motion* budgets stay strict - they are what
# this demo is for. `scripts/accept.sh` keeps the full floor and the fingerprint.
python3 scripts/105_motion_regression.py logs/demo_picks.log --min-success-rate 0.66 || gate=$?
if [ "$gate" -ne 0 ]; then
    echo
    echo "FAIL: this demo broke the motion budgets - do not report it as a pass"
    exit "$gate"
fi
echo "PASS: demo is inside the budgets. Full acceptance: scripts/accept.sh"
