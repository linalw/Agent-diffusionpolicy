#!/usr/bin/env bash
# P82 profile build (I1): run an entry point under py-spy, with the same env
# `scripts/run.sh` -> `python.sh` sets.
#
#   P82_PSPY=logs/p82/R3.speedscope.json ATTEMPTS=20 SEED=5 \
#     FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 \
#     scripts/154_claim_run.sh logs/p82/R3.driver \
#     bash logs/p82/run_pyspy.sh scripts/20_pick_place.py
#
# Why not `py-spy record -- scripts/run.sh ...`: `python.sh` starts the interpreter
# as a *child*, and this container runs with `ptrace_scope=1` and no root, so a
# tracer that is not an ancestor of the target is refused. Replicating the four
# variables + `setup_python_env.sh` here lets py-spy exec the kit interpreter as
# its own child. The launcher is admissible only if the run's `[fruit]` stream
# still matches the canonical record (METHOD §3) - checked, not assumed.
set -o pipefail
here=$(cd "$(dirname "$0")/../.." && pwd)
cd "$here" || exit 1

ISAAC=${ISAAC_SIM_DIR:-/home/ubuntu/linalw/App/isaacsim/_build/linux-x86_64/release}
out=${P82_PSPY:?usage: P82_PSPY=<speedscope.json> run_pyspy.sh <entry.py> [args...]}
entry=${1:?usage: P82_PSPY=<speedscope.json> run_pyspy.sh <entry.py> [args...]}
shift

rate=${P82_PSPY_RATE:-100}
ulimit -Sn 1048576 2>/dev/null || true

# `python.sh` starts the kit interpreter as a *child* (bash -> python.sh -> python),
# and this container runs with `ptrace_scope=1` and no root, so a tracer must be an
# ancestor of the target: `--subprocesses` follows the tree that `scripts/run.sh`
# starts, and the launcher then needs no environment replication of its own (the
# first attempt to hand-build it dropped `python_packages` from PYTHONPATH and the
# interpreter could not import `isaacsim`).
exec py-spy record --rate "$rate" --idle --subprocesses --format speedscope \
    -o "$out" -- bash "$here/scripts/run.sh" "$entry" "$@"
