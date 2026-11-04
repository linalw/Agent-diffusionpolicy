#!/usr/bin/env bash
# P112 - the closure fixture: hand kind x hard-stop x protocol, one fruit per
# app session (the ring's height is set by the payload's own radius at the seat).
#
#   bash logs/p112/run_p112_fixture.sh            # all 18 sessions
#   bash logs/p112/run_p112_fixture.sh cage3      # one kind (9 sessions)
#
# Two may run at once on this box (the sim is not GPU bound, files are disjoint).
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=logs/p112
KINDS=${1:-"cage3 cage4"}
FRUITS=${P112_FRUIT_IDS:-"0 1 2"}
for kind in ${KINDS}; do
    for spec in "0 1" "100000 1" "0 0"; do
        hold=${spec%% *}; freeze=${spec##* }
        for fruit in ${FRUITS}; do
            log="${OUT}/fixture_${kind}_hold${hold}_frz${freeze}_f${fruit}.log"
            if grep -q '^\[fruit\] \[p112\] done' "${log}" 2>/dev/null; then
                echo "=== ${kind} hold=${hold} frz=${freeze} f${fruit} (complete)"
                continue
            fi
            echo "=== ${kind} hold=${hold} frz=${freeze} fruit=${fruit}"
            env P112_KIND="${kind}" P112_HOLD="${hold}" P112_FREEZE="${freeze}" \
                P112_FRUIT="${fruit}" \
                scripts/run.sh logs/p112/fixture_cage3.py > "${log}.tmp" 2>&1 || true
            mv "${log}.tmp" "${log}"
            grep -E '^\[fruit\] \[p112\] done' "${log}" || echo "  (no done - see ${log})"
        done
    done
done
