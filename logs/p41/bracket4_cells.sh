set -uo pipefail
cd /home/ubuntu/linalw/Projects/opencode/Agent-diffusionpolicy || exit 1
BASE=(HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_GRIP_EFFORT=1 ATTEMPTS=2 SEED=5)
cell() {
    local name=$1 tmo=$2 log code t0; shift 2
    log="logs/p41/sweep_bracket/${name}.log"
    echo "[p41e] START $(date +%H:%M:%S) cell=${name} $*"
    t0=$(date +%s)
    timeout -k 30 "$tmo" env "${BASE[@]}" "$@" scripts/run.sh scripts/20_pick_place.py > "$log" 2>&1
    code=$?
    echo "[p41e] CELL ${name} exit=${code} wall=$(( $(date +%s) - t0 ))s log=${log}"
    printf '%s\t%s\t%s\n' "$name" "$(( $(date +%s) - t0 ))" "$log" >> logs/p41/sweep_bracket/wall4.tsv
}
: > logs/p41/sweep_bracket/wall4.tsv
cell k1e5_c1000 900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=100000 FRUIT_FINGER_DAMPING=1000
cell k3e5_c1000 900 FRUIT_SUBSTEPS=1 FRUIT_FINGER_STIFFNESS=300000 FRUIT_FINGER_DAMPING=1000
echo "[p41e] done $(date +%H:%M:%S)"
