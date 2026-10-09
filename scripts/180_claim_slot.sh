#!/usr/bin/env bash
# Claim one slot of the simulator pool, run one command, log to $1.
#
#   scripts/180_claim_slot.sh <logfile> ENV=... scripts/run.sh scripts/20_pick_place.py
#
# Unlike scripts/154_claim_run.sh (one global simulator, enforced by
# `pgrep -f python.sh`), this claims one of FRUIT_CLAIM_SLOTS slots so several
# simulator lanes can run at once. Slot i is the flock-held file
# `$FRUIT_CLAIM_DIR/slot$i.lock`; the holder's pid/label/log are written to
# `slot$i.owner` for reporting. flock is released by the kernel when the holder
# (or its child, which inherits the descriptor) dies, so a dead lane's slot is
# reclaimed with no operator action - the property the X1 measurement requires
# (scripts/181_claim_slot_selftest.sh pins it offline).
#
# The pool size default (3) is the measured safe concurrency of this 5090
# (`logs/x1/REPORT.md`); override with FRUIT_CLAIM_SLOTS. Waiting for a free
# slot is bounded by FRUIT_CLAIM_TIMEOUT seconds (default 3600), after which the
# claim exits 2.
#
#   scripts/180_claim_slot.sh --status      # print each slot's owner/liveness
#
# Namespace rule - never share a stream, manifest or log path across concurrent
# lanes. Pass a unique <logfile> and a unique output namespace per lane
# (FRUIT_DEMO_DIR / FRUIT_RECORD_DIR / FRUIT_POSTURE_DIR); the script refuses a
# log path that a live slot owner already has. This is not optional: the known
# corruption incident is two probes interleaving JSON into one shared
# `logs/461_posture/stream.jsonl`, which made the analyzer fail at char 113.
#
# Environment:
#   FRUIT_CLAIM_SLOTS=N   pool size (default 3)
#   FRUIT_CLAIM_TIMEOUT=N seconds to wait for a free slot (default 3600; 0=forever)
#   FRUIT_CLAIM_DIR=path  slot directory (default logs/claims)
#   FRUIT_CLAIM_LABEL=str owner label for status/owner file (default: log basename)
#   FRUIT_CLAIM_GLOBAL=1  additionally wait until no other `python.sh` is up
#                         (the old exclusive 154 contract; only meaningful with
#                         FRUIT_CLAIM_SLOTS=1)
#   RUN_LIMIT=N           kill the command's session after N s (default 1800,
#                         0=off). Long collections must raise this.
#
# Compatibility: scripts/154_claim_run.sh stays the exclusive path for lanes
# that cannot overlap; the two claims do not see each other (a 154 holder is
# invisible to a slot claim), so migrate a lane only when it is safe to overlap
# the remaining 154 lanes.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

claim_dir=${FRUIT_CLAIM_DIR:-logs/claims}
slots=${FRUIT_CLAIM_SLOTS:-3}
timeout=${FRUIT_CLAIM_TIMEOUT:-3600}
limit=${RUN_LIMIT:-1800}
global=${FRUIT_CLAIM_GLOBAL:-0}
poll=${FRUIT_CLAIM_POLL:-10}
case "$slots" in ''|*[!0-9]*) slots=3 ;; esac
[ "$slots" -lt 1 ] && slots=1
case "$timeout" in ''|*[!0-9]*) timeout=3600 ;; esac
case "$limit" in ''|*[!0-9]*) limit=1800 ;; esac
case "$poll" in ''|*[!0-9]*) poll=10 ;; esac
[ "$poll" -lt 1 ] && poll=1

owner_path() { printf '%s/slot%s.owner' "$claim_dir" "$1"; }
lock_path() { printf '%s/slot%s.lock' "$claim_dir" "$1"; }

owner_field() { grep -m1 "^$2=" "$1" 2>/dev/null | cut -d= -f2-; }

print_status() {
    local i f pid label log
    for i in $(seq 0 $((slots - 1))); do
        f=$(owner_path "$i")
        if [ ! -f "$f" ]; then
            exec 8>"$(lock_path "$i")"
            if flock -n 8; then
                printf 'slot %s: free\n' "$i"
            else
                printf 'slot %s: locked (holder has no owner file)\n' "$i"
            fi
            exec 8>&-
            continue
        fi
        pid=$(owner_field "$f" pid)
        label=$(owner_field "$f" label)
        log=$(owner_field "$f" log)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            printf 'slot %s: held pid=%s label=%s log=%s since=%s\n' \
                "$i" "$pid" "$label" "$log" "$(owner_field "$f" start)"
        else
            printf 'slot %s: stale owner (pid=%s label=%s; lock released by the kernel)\n' \
                "$i" "${pid:-?}" "${label:-?}"
        fi
    done
}

if [ "${1:-}" = "--status" ]; then
    mkdir -p "$claim_dir"
    print_status
    exit 0
fi

log=${1:-}
if [ -z "$log" ]; then
    echo "usage: $0 <logfile> ENV=... command... | --status" >&2
    exit 2
fi
shift

mkdir -p "$claim_dir"

# --- duplicate namespace guard: refuse a log a live slot owner already has ---
# Scan past the configured pool: a lane with a smaller FRUIT_CLAIM_SLOTS must
# still see an owner in a higher slot (the alternative is two lanes writing one
# stream, the corruption the namespace rule exists to prevent).
scan=$((slots > 16 ? slots : 16))
for i in $(seq 0 $((scan - 1))); do
    f=$(owner_path "$i")
    [ -f "$f" ] || continue
    opid=$(owner_field "$f" pid)
    olog=$(owner_field "$f" log)
    if [ -n "$opid" ] && [ "$olog" = "$log" ] && kill -0 "$opid" 2>/dev/null; then
        echo "[claim_slot] refusing: log '$log' is already owned by live pid $opid" >&2
        exit 2
    fi
done

start=$(date +%s)
while :; do
    for i in $(seq 0 $((slots - 1))); do
        exec 9>"$(lock_path "$i")"
        if flock -n 9; then
            if [ "$global" = "1" ]; then
                while pgrep -f '[p]ython.sh' >/dev/null 2>&1; do
                    echo "[claim_slot] exclusive mode: another simulator is up; waiting"
                    sleep 10
                done
            fi
            printf 'pid=%s\nlabel=%s\nlog=%s\nstart=%s\ncmd=%s\n' \
                "$$" "${FRUIT_CLAIM_LABEL:-$(basename "$log")}" "$log" \
                "$(date -Iseconds)" "$*" > "$(owner_path "$i")"
            echo "[claim_slot] slot $i/$((slots - 1)) claimed (${FRUIT_CLAIM_LABEL:-$(basename "$log")}) at $(date +%H:%M:%S)"
            break 2
        fi
        exec 9>&-
    done

    now=$(date +%s)
    if [ "$timeout" != "0" ] && [ $((now - start)) -ge "$timeout" ]; then
        echo "[claim_slot] TIMEOUT: no free slot in ${timeout}s (slots=$slots)" >&2
        print_status >&2
        exit 2
    fi
    # poll quickly at first, then back off; never sleep past the deadline
    wait_for=$((poll))
    if [ "$timeout" != "0" ]; then
        left=$((start + timeout - now))
        [ "$left" -lt "$wait_for" ] && wait_for=$left
        [ "$wait_for" -lt 1 ] && wait_for=1
    fi
    sleep "$wait_for"
done

setsid env "$@" > "$log" 2>&1 &
pid=$!
if [ "$limit" != "0" ]; then
    # The watchdog must not inherit the slot lock (fd 9): close it first, and
    # run in its own session so `kill -- -$watchdog` takes the sleep with it.
    setsid bash -c '
        exec 9>&-
        sleep "$0"
        if kill -0 "$1" 2>/dev/null; then
            echo "[claim_slot] TIMEOUT $0s; killing session $1" | tee -a "$2"
            kill -TERM -- "-$1" 2>/dev/null || kill -TERM "$1" 2>/dev/null
            sleep 30
            kill -KILL -- "-$1" 2>/dev/null || kill -KILL "$1" 2>/dev/null
        fi
    ' "$limit" "$pid" "$log" &
    watchdog=$!
fi

wait "$pid"
code=$?
if [ -n "${watchdog:-}" ]; then
    kill -- "-$watchdog" 2>/dev/null || kill "$watchdog" 2>/dev/null
    wait "$watchdog" 2>/dev/null
fi
rm -f "$(owner_path "$i")"
exec 9>&-
echo "[claim_slot] exit=$code $(date +%H:%M:%S) log=$log"
exit $code
