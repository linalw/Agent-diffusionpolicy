#!/usr/bin/env bash
# P121 addendum: T1b - exactly *today's direct routing* as an instruction.
#
# T1 (logs/p114/instructions/today.txt) is the P114 file: A=>0, B=>1, C=>skip,
# i.e. the *scripted two-line's* pure routing. The direct/policy env's shipped
# expression is `bin_index = 0 if grade == "A" else 1`, so it also sends grade C
# to the right lane. This cell is therefore the true same-destination
# reproduction of the un-instructed control:
#
#     grade=A => 0; default => 1
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
echo "  [p121] T1b start $(date +%H:%M:%S)"
RUN_LIMIT=3000 logs/p121/one_run.sh logs/p121/direct/T1b.log 10 77,101,202 \
    "FRUIT_SORT_INSTRUCTION=grade=A => 0; default => 1"
echo "  [p121] T1b exit=$? $(date +%H:%M:%S)"
grep -E "\[sort\] ledger|\[rl\] rollout success|\[rl\] seed" logs/p121/direct/T1b.log | tail -8
