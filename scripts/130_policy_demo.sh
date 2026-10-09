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
# (`FRUIT_POLICY_TRIGGER=arrival`), not by the station hand-off teleport. The
# primitive itself runs the **dynamic never-stop catch** (`FRUIT_DYNAMIC_PICK=1`,
# the P2b left-handover-fixed configuration); `FRUIT_DYNAMIC_PICK=0` restores the
# indexed P1 handover. This is the interface the v5/v7 RL work measured; see
# `src/fruit_sorting/rl_env.py`.
#
# Fixed configuration (override with the same-named env vars):
#   FRUIT_SUPPLY_SCATTER      0         (the pre-v9 fixed supply: the policy is
#                             OOD on the v9/V1 scattered supply - a frozen-tree
#                             canary scored 2/10 there, `logs/v3/80_accept_policy_scatter.log`;
#                             the recollection + fine-tune is the recorded next
#                             step, `FRUIT_SUPPLY_SCATTER=1` opts back in)
#   CKPT                      checkpoints/moe_v12/policy_best.pt
#                             (the P2b left-handover-fixed checkpoint; direct at
#                             belt 0.12: 32/45 = 71.1 %, left 0/17 -> 6/17,
#                             `logs/p2b/ab012/`; manifest records its md5)
#   FRUIT_DYNAMIC_PICK        1         (the dynamic never-stop catch, the
#                             configuration the P2b 71.1 % was measured on; the
#                             env unset would keep the indexed P1 primitive)
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
# pinned integrated revision (`TASKS_MD5` in `src/fruit_sorting/rl_env.py`; now
# the P2b/G tree, the Gate-19 place 0.35 + the P2b handover fix + the 2026-10-08
# docstring-only re-pin), so this demo runs the exact scenario the checkpoint
# was measured on.
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
# The measured trigger arm at belt 0.12 with the fixed dynamic handover is
# 32/45 = 71.1 % (`moe_v12`, P2b; the pre-fix arm was 25/45 = 55.6 % and the
# indexed handover 16/45 = 36 %) - a single run is one sample, the per-episode
# table above the summary is what to read.
set -euo pipefail

cd "$(dirname "$0")/.."

headless=${HEADLESS:-0}
episodes=${EPISODES:-20}
seeds=${SEEDS:-77}
ckpt=${CKPT:-checkpoints/moe_v12/policy_best.pt}
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
export FRUIT_SUPPLY_SCATTER="${FRUIT_SUPPLY_SCATTER:-0}"
export FRUIT_DYNAMIC_PICK="${FRUIT_DYNAMIC_PICK:-1}"
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
echo "camera=${FRUIT_CAMERA_RES} dynamic_pick=${FRUIT_DYNAMIC_PICK} " \
     "trigger=${FRUIT_POLICY_TRIGGER} " \
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
