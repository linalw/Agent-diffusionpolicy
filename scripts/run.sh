#!/usr/bin/env bash
# Launch an Isaac Sim script with a safe file-descriptor limit.
#
# Why this exists: Isaac Sim only *raises* RLIMIT_NOFILE to a floor of 2450
# when the calling shell asks for less, and this 6.0.1-rc build opens a burst
# of ~2 100 `/dev/nvidiactl` descriptors the first time the head camera's
# synthetic-data annotators are read. From a desktop terminal (soft limit
# 1024) that burst overruns the 2450 floor: `dup failed ... Too many open
# files`, then the crash reporter itself cannot open its dump pipe, so the
# process hangs and the GUI window looks frozen. Raising the soft limit before
# starting the simulator removes the ceiling entirely.
#
# Usage:
#   scripts/run.sh scripts/20_pick_place.py
#   HEADLESS=0 FRUIT_GUI_SMOOTH=1 scripts/run.sh scripts/20_pick_place.py
#   scripts/run.sh --check          # print the limits this wrapper would use

set -euo pipefail

: "${ISAAC_SIM_DIR:=/home/ubuntu/linalw/App/isaacsim/_build/linux-x86_64/release}"
fd_target=${FRUIT_FD_LIMIT:-1048576}

hard=$(ulimit -Hn)
if [ "$hard" != "unlimited" ] && [ "$fd_target" -gt "$hard" ]; then
    fd_target=$hard
fi
ulimit -Sn "$fd_target" 2>/dev/null || echo "warning: could not raise ulimit -n to $fd_target" >&2

if [ "${1:-}" = "--check" ]; then
    echo "ISAAC_SIM_DIR=$ISAAC_SIM_DIR"
    echo "soft nofile=$(ulimit -Sn) hard nofile=$(ulimit -Hn)"
    exit 0
fi

if [ "$#" -eq 0 ]; then
    echo "usage: $0 <script.py> [args...]" >&2
    exit 2
fi

echo "[run.sh] soft nofile=$(ulimit -Sn) -> $ISAAC_SIM_DIR/python.sh $*"
exec "$ISAAC_SIM_DIR/python.sh" "$@"
