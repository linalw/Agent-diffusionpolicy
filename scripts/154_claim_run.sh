#!/usr/bin/env bash
# Claim the single simulator, run one command, log to $1.
#   scripts/154_claim_run.sh <logfile> ENV=... scripts/run.sh scripts/20_pick_place.py
#
# Same contract as logs/fast/run_one.sh: never kills another lane's run, polls
# while a simulator is up, aborts its own attempt if it overlapped one, and has
# a stall guard for the known contact-grind wedge. The F2 rates script uses it.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
log=$1; shift

claim() {
    local idle=0
    while :; do
        if pgrep -f '[p]ython.sh' >/dev/null 2>&1; then
            idle=0
            sleep 60
        else
            idle=$((idle + 1))
            if [ "$idle" -ge 2 ]; then
                if ! pgrep -f '[p]ython.sh' >/dev/null 2>&1; then
                    echo "[claim_run] claimed the simulator $(date +%H:%M:%S)"
                    return 0
                fi
                idle=0
            fi
            sleep 20
        fi
    done
}

attempt=0
limit=${RUN_LIMIT:-1800}
while :; do
    attempt=$((attempt + 1))
    claim
    setsid env "$@" > "$log" 2>&1 &
    pid=$!
    (
        sleep "$limit"
        if kill -0 "$pid" 2>/dev/null; then
            echo "[claim_run] TIMEOUT ${limit}s; killing session $pid" | tee -a "$log"
            kill -TERM -- "-$pid" 2>/dev/null
            sleep 30
            kill -KILL -- "-$pid" 2>/dev/null
        fi
    ) &
    watchdog=$!
    sleep 5
    n=$(pgrep -fc '[p]ython.sh' || true)
    if [ "${n:-1}" -gt 1 ]; then
        echo "[claim_run] overlap (${n}); aborting own attempt ${attempt}" | tee -a "$log"
        kill -- "-${pid}" 2>/dev/null || kill "$pid" 2>/dev/null || true
        kill "$watchdog" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        [ "$attempt" -ge 4 ] && { echo "[claim_run] gave up"; exit 1; }
        sleep 60
        continue
    fi
    wait "$pid"
    code=$?
    # Reap the watchdog CHILD FIRST, then the subshell: a non-interactive bash
    # subshell does not forward signals to the `sleep` it is blocked on, so
    # killing only "$watchdog" leaves an orphaned `sleep $limit` that (a) holds
    # any inherited stdout pipe open - a caller piping through `tee` blocks for
    # the full limit after the run has finished (observed: a 40-min stall on
    # RUN_LIMIT=2400) - and (b) can fire its stale `kill -0 $pid` against a
    # REUSED pid later. `pkill -P` must run while the subshell still exists as
    # the sleep's parent.
    pkill -P "$watchdog" 2>/dev/null || true
    kill "$watchdog" 2>/dev/null || true
    wait "$watchdog" 2>/dev/null || true
    echo "[claim_run] exit=$code $(date +%H:%M:%S) log=$log"
    exit $code
done
