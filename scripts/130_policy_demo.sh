#!/usr/bin/env bash
# One-command live demo of the *trained model* sorting fruit in the causal
# `direct` interface (P4/v7 tree), with the encoder intercept trigger on.
#
#   scripts/130_policy_demo.sh                    # GUI, 20 episodes, seed 77
#   HEADLESS=1 scripts/130_policy_demo.sh         # same run, no window
#   EPISODES=5 scripts/130_policy_demo.sh         # a short look (20-30 min total
#                                                 # for 20 episodes; 5 is ~6 min)
#
# What runs: `scripts/110_rl_rollout.py` drives `SortingRLEnv(presentation=
# "direct")` - the fruit keeps moving on the belt and the scripted primitive is
# triggered by the belt encoder's predicted arrival at the pick station
# (`FRUIT_POLICY_TRIGGER=arrival`), not by the station hand-off teleport. This
# is the interface the v5/v7 RL work measured; see `src/fruit_sorting/rl_env.py`.
#
# Fixed configuration (override with the same-named env vars):
#   CKPT                      checkpoints/moe_v10/policy_best.pt
#                             (the openarm-hand recollection + retrain,
#                             `datasets/demos_v9`; manifest records its md5)
#   FRUIT_CAMERA_RES          240,424   (height,width - the A/B resolution, half
#                             the 480x848 default, kept so the loop is fast)
#   FRUIT_POLICY_TRIGGER      arrival   (default in code is `off`; `arrival`
#                             fires the primitive when the encoder predicts the
#                             fruit reaches the station in <= LEAD seconds)
#   FRUIT_POLICY_TRIGGER_LEAD 0.9 s     (the B1 A/B setting; other trigger
#                             defaults are lateral 0.06 m, reach 0.20 m,
#                             finger 0.040, encoder on, frame=station,
#                             present off - `policy/trigger.py`)
#   FRUIT_POLICY_SEED         11        (removes the unseeded torch.randn in DDIM)
#   FRUIT_NO_ATTACH=1         causal direct interface (no teleport attach)
#   FRUIT_NO_SLEEP=1          fruit never sleep under the approaching jaws
#   EPISODES=20 SEEDS=77      the request's run shape; one `[rl] episode ...`
#                             line per episode, then a success summary
#
# The environment refuses to start unless `src/fruit_sorting/tasks.py` is the
# frozen v7 revision (`TASKS_MD5=ae841a17bbacdb19180451315193486c`), so this
# demo runs the exact scenario the checkpoint was measured on.
#
# GUI notes. `HEADLESS=0` opens the Isaac window on the display
# (`DISPLAY` defaults to `:1` if unset). The policy phase renders and pumps the
# app at the observation cadence (30 Hz, `RenderingManager.render()` in
# `_observe`), and `FRUIT_GUI_SMOOTH=1` pumps the UI during the scripted
# grasp/carry at 60 Hz while keeping the average physics tick at 1/120 s. No
# capture-cadence change is needed - the window tracks the run, it does not
# record it. Expect the wall clock to be about the simulated time (DDIM-16 is
# ~26 ms per 4-tick control chunk); a 20-episode demo is a ~25-45 min session.
#
# One simulator at a time (AGENTS.md): this script refuses to start if any
# `python.sh` process is already running. Watch the window; stop with Ctrl-C.
# The measured trigger arm is ~30-50 % success per episode (B1: 23/45 = 51 %
# with LEAD 0.9; P4b2 re-run: 13/45 = 29 %) - a single run is one sample, the
# per-episode table above the summary is what to read.
set -euo pipefail

cd "$(dirname "$0")/.."

headless=${HEADLESS:-0}
episodes=${EPISODES:-20}
seeds=${SEEDS:-77}
ckpt=${CKPT:-checkpoints/moe_v10/policy_best.pt}
out=${OUT_DIR:-datasets/rl_rollouts_demo}

if [ "$(pgrep -fc "[p]ython.sh" 2>/dev/null || true)" -gt 0 ]; then
    echo "FAIL: another Isaac process (python.sh) is running; one simulator at a time." >&2
    echo "      Wait for it (poll: pgrep -af '[p]ython.sh') and try again." >&2
    exit 1
fi
if [ ! -f "$ckpt" ]; then
    echo "FAIL: checkpoint not found: $ckpt" >&2
    exit 1
fi

export HEADLESS="$headless"
export FRUIT_CAMERA_RES="${FRUIT_CAMERA_RES:-240,424}"
export FRUIT_POLICY_TRIGGER="${FRUIT_POLICY_TRIGGER:-arrival}"
export FRUIT_POLICY_TRIGGER_LEAD="${FRUIT_POLICY_TRIGGER_LEAD:-0.9}"
export FRUIT_POLICY_SEED="${FRUIT_POLICY_SEED:-11}"
export FRUIT_NO_ATTACH="${FRUIT_NO_ATTACH:-1}"
export FRUIT_NO_SLEEP="${FRUIT_NO_SLEEP:-1}"
if [ "$headless" = "0" ]; then
    export DISPLAY="${DISPLAY:-:1}"
    export FRUIT_GUI_SMOOTH="${FRUIT_GUI_SMOOTH:-1}"
fi

echo "=== policy demo: ${episodes} episodes, seed(s) ${seeds}, HEADLESS=${headless} ==="
echo "ckpt=${ckpt}"
echo "camera=${FRUIT_CAMERA_RES} trigger=${FRUIT_POLICY_TRIGGER} " \
     "lead=${FRUIT_POLICY_TRIGGER_LEAD}s policy_seed=${FRUIT_POLICY_SEED} " \
     "gui_smooth=${FRUIT_GUI_SMOOTH:-0}"
echo "output=${out}"
echo

SCRIPTS_RUN=scripts/run.sh
"$SCRIPTS_RUN" scripts/110_rl_rollout.py \
    --ckpt "$ckpt" \
    --presentation direct \
    --episodes "$episodes" \
    --seeds "$seeds" \
    --out "$out"
