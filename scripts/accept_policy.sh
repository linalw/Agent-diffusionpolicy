#!/usr/bin/env bash
# One-command acceptance for the *policy* closed loop (hybrid evaluation).
#
#   scripts/accept_policy.sh                      # ten hybrid episodes, deployed checkpoint
#   FRUIT_EPISODES=15 scripts/accept_policy.sh    # a longer run
#   SKIP_SELFCHECK=1 scripts/accept_policy.sh     # skip the offline pre-flight
#   JUDGE_ONLY=1 ACCEPT_POLICY_LOG=logs/336_hybrid_v3all.log scripts/accept_policy.sh
#                                                 # judge an existing log, no simulator
#
# `scripts/accept.sh` gates the *scripted* line; this gates the policy in the loop,
# which is the number the learning side is judged on. It runs
# `scripts/60_eval_policy.py` in hybrid mode with the deployed checkpoint, writes
# `logs/accept_policy.log`, and judges two things:
#
#   1. the success rate is at least `MIN_RATE` (default 0.60);
#   2. every failure has a reason the recorded baseline also produced - a grip loss
#      ("fruit did not follow the gripper"), or a grasp that was not placed with no
#      note attached. Anything else is listed and fails the gate, because a new
#      failure *reason* is the interesting signal, not the count.
#
# Default checkpoint: `checkpoints/moe_v12/policy_best.pt` (the P2b deployment
# checkpoint; override with `FRUIT_CKPT=...`). **At the v7 scenario (belt 0.12,
# openarm hand, dynamic scripted default) the recorded hybrid-canary samples for
# this path spread 5-8/10**: `moe_v11` 8/10 (F2), `moe_v12` 6/10 (P2), then
# 5/10 and 6/10 (P2b) - all failures baseline grip losses, inside the one-run
# spread of an unchanged path. The 0.60 floor therefore passes some samples and
# trips on others; a single canary is one sample, and the direct A/B batches
# (`logs/p2b/ab012/`) are the rate evidence, not the canary.
#
# Baseline: `logs/336_hybrid_v3all.log` scores 12/15 - 2 grip losses and 1 place
# failure with an empty note.
#
# **One run is one sample.** Unlike the scripted line, the policy loop is *not*
# bit-identical run to run: with the same spawn seed the ten targets come out in the
# same order, but the outcomes differ. Five recorded runs score
# 100 / 90 / 90 / 70 / 90 % - mean 88 %, worst 70 %, spread 30 % - and the failures
# concentrate on one fruit: the 3.4 cm strawberry fails in 3 of the 5 (twice as a
# grip loss, once grasped-but-not-placed), while the lychee, tomato and peach fail
# once each (WORKLOG: "five runs of the policy loop").
#
# Two consequences for how to read a verdict:
#
# * `MIN_RATE` defaults to **0.60**, not 0.70: the worst of five healthy runs landed
#   exactly on 0.70, so a 0.70 single-run floor would fail a fine tree roughly one
#   run in fourteen. For a number you intend to publish, average over runs instead
#   of trusting one (the loop and snippet are below; ~13 minutes per run);
# * a verdict above the floor is not by itself a vindication - check *which* fruit
#   failed, because one of them fails reproducibly:
#
#   for i in 1 2 3; do ACCEPT_POLICY_LOG=logs/ap_$i.log scripts/accept_policy.sh; done
#   python3 - <<'EOF'
#   import re, glob
#   rates = []
#   for path in sorted(glob.glob("logs/ap_*.log")):
#       ok, total = map(int, re.search(r"policy success (\d+)/(\d+)", open(path).read()).groups())
#       rates.append(ok / total)
#   print(f"{len(rates)} runs, mean {sum(rates)/len(rates):.0%}, worst {min(rates):.0%}")
#   EOF
#
# (each run is about 13 minutes, so N runs is a deliberate cost).
set -uo pipefail

cd "$(dirname "$0")/.."

checkpoint=${FRUIT_CKPT:-checkpoints/moe_v12/policy_best.pt}
episodes=${FRUIT_EPISODES:-10}
min_rate=${MIN_RATE:-0.60}
log=${ACCEPT_POLICY_LOG:-logs/accept_policy.log}

# Fail on a missing checkpoint before starting a simulator, which is the single
# most common way to waste a run here.
if [ ! -f "$checkpoint" ]; then
    echo "FAIL: no checkpoint at $checkpoint"
    echo "      pass one with FRUIT_CKPT=...; available:"
    ls -1 checkpoints/*/policy_best.pt 2>/dev/null | sed 's/^/        /'
    exit 1
fi

if [ "${SKIP_SELFCHECK:-0}" != "1" ]; then
    echo "=== pre-flight self-check (SKIP_SELFCHECK=1 to skip) ==="
    if ! scripts/selfcheck.sh; then
        echo
        echo "FAIL: fix the self-check before spending a simulator run"
        exit 1
    fi
    echo
fi

echo "=== policy closed loop (hybrid): ${episodes} episodes, $checkpoint ==="
if [ "${JUDGE_ONLY:-0}" = "1" ]; then
    echo "(JUDGE_ONLY=1: judging $log, not running the simulator)"
else
    # `FRUIT_NO_ATTACH=1 FRUIT_NO_SLEEP=1` match how the demonstrations are
    # recorded (physical contact, no modelled attach); without them the evaluator
    # would grade a physical-contact policy with the old attach model.
    # The camera resolution is pinned to the collection/training resolution: the
    # policy downsamples the frame to its training view, so an eval built at the
    # scene default (480x848) would feed it a different crop (the P3 gate found
    # exactly that - the canary and the P4 A/B must share one view).
    [ -f "$log" ] && cp -f "$log" "$log.prev"
    HEADLESS="${HEADLESS:-1}" FRUIT_HYBRID_EVAL=1 FRUIT_CKPT="$checkpoint" \
        FRUIT_NO_ATTACH="${FRUIT_NO_ATTACH:-1}" FRUIT_NO_SLEEP="${FRUIT_NO_SLEEP:-1}" \
        FRUIT_CAMERA_RES="${FRUIT_CAMERA_RES:-240,424}" \
        FRUIT_EPISODES="$episodes" scripts/run.sh scripts/60_eval_policy.py \
        > "$log" 2>&1 || true
fi
grep -E "\[eval\] policy success|loaded " "$log" | tail -2 || true

echo
echo "=== policy gate ==="
python3 - "$log" "$min_rate" <<'PY'
import re
import sys

log, min_rate = sys.argv[1], float(sys.argv[2])
text = open(log, encoding="utf-8", errors="ignore").read()

results = [
    line.strip()
    for line in text.splitlines()
    if re.search(r"\[eval\] episode \d+: hybrid ", line)
]
# The target-selection line that precedes each result, so the table below can be
# checked without opening the raw log.
targets = {}
for line in text.splitlines():
    found = re.search(
        r"\[eval\] episode (\d+): (\w+) grade=(\w+) d=([\d.]+)cm lane=(\d+)", line
    )
    if found:
        targets[int(found.group(1))] = (
            found.group(2), float(found.group(4)), int(found.group(5))
        )
summary = re.search(r"\[eval\] policy success (\d+)/(\d+) \(attempts=(\d+)\)", text)
if not results or summary is None:
    print(f"  no '[eval] policy success N/M' line in {log}")
    print("FAIL: the evaluation did not produce a verdict")
    raise SystemExit(1)

successes, total = int(summary.group(1)), int(summary.group(2))
rate = successes / total if total else 0.0

# Reason sets observed in the recorded baseline (`logs/336_hybrid_v3all.log`).
GRIP = "fruit did not follow the gripper"

grip_losses, place_failures, unexpected = [], [], []
rows = []
for line in results:
    index = int(re.search(r"\[eval\] episode (\d+):", line).group(1))
    category, diameter, bin_index = targets.get(index, ("?", 0.0, -1))
    placed = "grasped=True placed=True" in line
    if placed:
        rows.append((index, category, diameter, bin_index, "ok", ""))
        continue
    if GRIP in line:
        grip_losses.append(line)
        rows.append((index, category, diameter, bin_index, "FAIL", "grip loss"))
    elif "grasped=True placed=False" in line and "notes=[]" in line:
        place_failures.append(line)
        rows.append((index, category, diameter, bin_index, "FAIL", "grasped, not placed"))
    else:
        unexpected.append(line)
        rows.append((index, category, diameter, bin_index, "FAIL", "unexpected reason"))

print(f"  {'#':>2s} {'fruit':<11s} {'d':>5s} {'bin':>3s}  {'result':<6s} reason")
for index, category, diameter, bin_index, verdict, reason in sorted(rows):
    print(f"  {index:2d} {category:<11s} {diameter:4.1f}c {bin_index:3d}  {verdict:<6s} {reason}")

print(f"  episodes: {total}, successes {successes}")
print(f"  rate: {rate:.0%} (floor {min_rate:.0%})")
print(f"  failures: {len(grip_losses)} grip loss, {len(place_failures)} grasped-not-placed")
for line in place_failures:
    print(f"    note: {line}")

problems = []
if rate < min_rate:
    problems.append(f"rate {rate:.0%} below {min_rate:.0%}")
for line in unexpected:
    problems.append(f"failure reason not seen in the baseline: {line}")

if problems:
    print(f"FAIL: {len(problems)} problem(s)")
    for item in problems:
        print(f"  - {item}")
    raise SystemExit(1)
print("PASS: policy closed loop at or above the floor, with only baseline failure reasons")
PY
