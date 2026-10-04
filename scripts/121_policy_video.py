"""Record MP4 clips of the *policy* acting in the causal ``direct`` interface.

    scripts/run.sh scripts/121_policy_video.py \
        --ckpt checkpoints/moe_v9/policy_best.pt --episodes 3 --seed 101

`scripts/70_record_video.py` films the *scripted* line; this records the policy
loop instead, driving `SortingRLEnv` directly (the same environment and loop
`scripts/110_rl_rollout.py` runs) with the A/B settings: presentation `direct`,
`--execute-steps 4`, `--ddim 16`, `FRUIT_CAMERA_RES=240,424`, fixed policy seed
and one simulator at a time. The constructor's manifest (checkpoint md5, tasks
md5, camera resolution) lands next to the clips.

Four outputs per run, the same set `70_record_video.py` writes, H.264/yuv420p:

* ``observer.mp4`` - the fixed external view of the whole cell, annotated with
  the episode index, elapsed time, policy control step, the policy's finger
  command, the 2-D ``|jaw-fruit|`` distance (the 6 cm trigger quantity) and the
  episode outcome over the last 1.5 s;
* ``head.mp4`` - the policy's own head camera (clean);
* ``gripper.mp4`` - the pick-station close-up (clean);
* ``side_by_side.mp4`` - observer + head, stacked (the observer half carries the
  annotation).

The clip runs from `env.reset()` (belt feed included, so the causal interface is
visible) through the policy phase, the policy-triggered scripted grasp/carry and
the release, and stops when the episode ends (`env.act` returns `done`). Frames
are captured at least every `--capture-every` control steps (default 1 = every 4
physics ticks, playback at 30 fps, i.e. real time). The capture hook covers both
`env.advance` (policy/reset) and the task's `_step_sim` (the primitive advances
physics in the seat/re-seat settles and close ramps *without* calling
`_tick_frame`, so a `frame_callback`-only recorder drops those frames and
time-lapses the contact work).

Capture cost per captured frame: one explicit `RenderingManager.render()`, the
two extra camera reads, and one jaw/fruit pose read for the overlay. Camera and
fruit-pose reads are the diagnostics AGENTS.md section 2 explicitly allows in
the control loop (the articulation-link readback is the one that shifts the
run); the outcomes printed here are this clip's own, and the direct loop is not
bit-reproducible anyway because the policy conditions on rendered frames.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

# Set HEADLESS=0 to watch the run in the Isaac Sim GUI.
HEADLESS = os.environ.get("HEADLESS", "1") == "1"

from fruit_sorting.fdlimit import raise_fd_limit

# Raise the fd limit before Isaac Sim starts: this build opens ~2100
# `/dev/nvidiactl` descriptors on the first camera read and dies with
# `dup failed ... Too many open files` at the default limit.
raise_fd_limit()

simulation_app = SimulationApp({"headless": HEADLESS, "width": 1280, "height": 720})

import cv2
import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.rendering_manager import RenderingManager
from isaacsim.sensors.experimental.rtx import CameraSensor, RtxCamera
from fruit_sorting.common import install_failure_handler, look_at_quat, say, to_numpy
from fruit_sorting.rl_env import SortingRLEnv

DT = 1.0 / 120.0
#: Frames the outcome banner is drawn on (1.5 s at the default 30 fps).
BANNER_FRAMES = 45


def frame_of(sensor, annotator: str = "rgb"):
    data = sensor.get_data(annotator)
    array = to_numpy(data)
    if array is None:
        return None
    array = np.asarray(array)
    if array.ndim == 4:
        array = array[0]
    # A freshly created sensor can return a 0-d placeholder before its render
    # product has produced a frame; treat anything that is not an image as empty.
    if array.ndim < 3 or array.shape[-1] not in (3, 4):
        return None
    if array.shape[-1] == 4:
        array = array[..., :3]
    return np.ascontiguousarray(array.astype(np.uint8))


def annotate(image: np.ndarray, lines: list[str], banner=None) -> np.ndarray:
    """Draw the observer overlay: a dark strip, the live lines, an outcome banner.

    ``banner`` is ``(text, colour)`` and is only passed on the closing frames.
    """
    out = image.copy()
    height = 22 + 20 * (len(lines) + (1 if banner else 0))
    strip = out.copy()
    cv2.rectangle(strip, (0, 0), (out.shape[1], height), (0, 0, 0), -1)
    out = cv2.addWeighted(strip, 0.45, out, 0.55, 0)
    y = 21
    for text in lines:
        cv2.putText(out, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(out, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (235, 235, 235), 1, cv2.LINE_AA)
        y += 20
    if banner:
        text, colour = banner
        cv2.putText(out, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(out, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.62, colour, 2, cv2.LINE_AA)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ckpt",
        default=os.environ.get("FRUIT_CKPT", "checkpoints/moe_v9/policy_best.pt"),
        help="policy checkpoint to roll out",
    )
    parser.add_argument("--episodes", type=int, default=int(os.environ.get("FRUIT_EPISODES", "3")))
    parser.add_argument(
        "--seed",
        type=int,
        default=int(os.environ.get("FRUIT_VIDEO_SEED", "101")),
        help="spawner seed; episode 0 uses it, later episodes continue the sequence",
    )
    parser.add_argument("--execute-steps", type=int, default=4)
    parser.add_argument("--ddim", type=int, default=16)
    parser.add_argument(
        "--capture-every",
        type=int,
        default=int(os.environ.get("FRUIT_VIDEO_STRIDE", "1")),
        help="control steps per captured frame (1 = every 4 physics ticks, real time)",
    )
    parser.add_argument(
        "--out-dir",
        default=os.environ.get("FRUIT_VIDEO_DIR", "logs/video_policy"),
        help="where the four mp4s, the manifest and video.json are written",
    )
    parser.add_argument("--size-filter", choices=["", "small", "large"], default="")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    install_failure_handler("121_policy_video")

    stride = max(1, int(args.capture_every))
    render_every = 4 * stride
    fps = 30.0 / stride

    # The A/B's environment, exactly (`scripts/112_rl_ab.sh`). setdefault so a
    # caller can still override, but the defaults cannot drift silently.
    os.environ.setdefault("FRUIT_CAMERA_RES", "240,424")
    os.environ.setdefault("FRUIT_NO_ATTACH", "1")
    os.environ.setdefault("FRUIT_NO_SLEEP", "1")
    os.environ.setdefault("FRUIT_POLICY_SEED", "11")

    os.makedirs(args.out_dir, exist_ok=True)
    ckpt_md5 = hashlib.md5(open(args.ckpt, "rb").read()).hexdigest()
    say(
        f"[video] policy clip: ckpt={args.ckpt} (md5 {ckpt_md5[:8]}) episodes={args.episodes} "
        f"seed={args.seed} presentation=direct execute_steps={args.execute_steps} "
        f"ddim={args.ddim} camera={os.environ['FRUIT_CAMERA_RES']} "
        f"capture_every={stride} fps={fps:g} out={args.out_dir}"
    )

    env = SortingRLEnv(
        presentation="direct",
        seed=int(args.seed),
        size_filter=args.size_filter or None,
        ablate="none",
        checkpoint=args.ckpt,
        record=False,
        out_dir=args.out_dir,
        execute_steps=int(args.execute_steps),
        ddim_steps=int(args.ddim),
        verbose=bool(args.verbose),
    )

    # Extra views, exactly the placements `70_record_video.py` uses. They are
    # created after the scene started (the env owns scene construction), which
    # is the one difference from the scripted recorder.
    eye = (1.75, 1.55, 2.35)
    observer = RtxCamera(
        "/World/PolicyObserverCamera",
        tick_rate=0.0,
        positions=[eye],
        orientations=[look_at_quat(eye, (0.34, 0.0, 1.12))],
    )
    observer.camera.set_focal_lengths(0.016)
    observer.camera.set_apertures((0.036, 0.02025))
    observer.camera.set_clipping_ranges(0.01, 50.0)
    observer_sensor = CameraSensor(observer, resolution=(540, 960), annotators=["rgb"])

    close_eye = (0.93, 0.62, 1.42)
    close = RtxCamera(
        "/World/PolicyGripperCamera",
        tick_rate=0.0,
        positions=[close_eye],
        orientations=[look_at_quat(close_eye, (0.34, 0.0, 1.19))],
    )
    close.camera.set_focal_lengths(0.035)
    close.camera.set_apertures((0.036, 0.02025))
    close.camera.set_clipping_ranges(0.01, 50.0)
    close_sensor = CameraSensor(close, resolution=(540, 960), annotators=["rgb"])

    # The extra render products need one render before their first read: a freshly
    # created sensor can return a 0-d placeholder until then. A few warm-up steps
    # here are harmless (they happen before the first `reset`, which feeds the
    # line until a target is in the selector's window anyway).
    original_advance = env.advance
    for name, sensor in (
        ("observer", observer_sensor),
        ("gripper", close_sensor),
        ("head", env.scene.camera_sensor),
    ):
        frame = None
        for _ in range(20):
            RenderingManager.render()
            frame = frame_of(sensor)
            if frame is not None:
                break
            original_advance(1)
        if frame is None:
            say(f"[video] WARNING: {name} camera returned no frame after 20 renders")
        else:
            say(f"[video] {name} camera ready ({frame.shape[1]}x{frame.shape[0]})")

    frames = {"observer": [], "head": [], "close": []}
    labels: list[dict] = []
    episodes: list[dict] = []
    state = {"episode": 0, "phase": "reset"}
    last_tick = [-(10**9)]

    def capture() -> None:
        """Capture the three views every `render_every` physics ticks.

        The throttle is gap-based (`tick - last >= render_every`) rather than
        `tick % render_every == 0`, because some task phases advance two ticks per
        call; gap-based never skips a long stretch, it only samples the nearest
        tick.
        """
        tick = int(round(env._sim_time() / DT))
        if tick - last_tick[0] < render_every:
            return
        last_tick[0] = tick
        RenderingManager.render()
        obs = frame_of(observer_sensor)
        head = frame_of(env.scene.camera_sensor)
        close_up = frame_of(close_sensor)
        if obs is None or head is None or close_up is None:
            return
        finger = None
        if hasattr(env, "_last_finger"):
            finger = float(env._last_finger)
        else:
            action = np.asarray(getattr(env, "_last_action", np.zeros(9)), dtype=float)
            if action.size > 7:
                finger = float(action.reshape(-1)[7])
        distance = None
        if env._sample is not None:
            jaw = np.asarray(env.task.arms[env._active].jaw_centre(), dtype=float)
            fruit = np.asarray(env.spawner.position(env._sample), dtype=float)
            distance = float(np.linalg.norm(fruit[:2] - jaw[:2]))
        phase = "primitive" if getattr(env, "_triggered", False) else state["phase"]
        frames["observer"].append(obs)
        frames["head"].append(head)
        frames["close"].append(close_up)
        labels.append(
            {
                "episode": state["episode"],
                "tick": tick,
                "step": int(env._step),
                "finger": finger,
                "distance": distance,
                "phase": phase,
            }
        )

    # Capture in the policy/reset phase (the env's own advance) and in the
    # scripted primitive, where the task steps through `_step_sim` - several of
    # its loops (the 30-tick seat/re-seat settles, the close ramps) advance
    # physics *without* calling `_tick_frame`, so hooking `frame_callback` alone
    # drops those frames and time-lapses the contact work.
    def advance_with_capture(steps: int) -> None:
        original_advance(steps)
        capture()

    env.advance = advance_with_capture
    env.task.frame_callback = capture

    original_step_sim = env.task._step_sim

    def step_sim_with_capture(steps: int = 1) -> None:
        original_step_sim(steps)
        capture()

    env.task._step_sim = step_sim_with_capture

    episode_notes: dict[int, dict] = {}
    for episode in range(int(args.episodes)):
        state["episode"] = episode
        state["phase"] = "reset"
        ep_start = len(frames["observer"])
        start_tick = int(round(env._sim_time() / DT))
        env.reset(int(args.seed) if episode == 0 else None)
        state["phase"] = "policy"
        done = False
        result = None
        while not done:
            chunk = env.sample_chunk()
            result = env.act(chunk, execute_steps=int(args.execute_steps))
            done = bool(result.done)
        info = dict(result.info) if result is not None else {}
        end_tick = int(round(env._sim_time() / DT))
        record = {
            "index": episode,
            "start": ep_start,
            "end": len(frames["observer"]),
            "start_tick": start_tick,
            "ticks": int(info.get("ticks", end_tick - start_tick)),
            "decision": int(info.get("decision", 0)),
            "category": info.get("category", ""),
            "diameter": float(info.get("diameter", 0.0)),
            "bin_index": int(info.get("bin_index", -1)),
            "arm": info.get("arm", ""),
            "success": bool(info.get("success", False)),
            "grasped": bool(info.get("grasped", False)),
            "placed": bool(info.get("placed", False)),
            "reward": float(info.get("reward", 0.0)),
            "notes": list(info.get("notes", [])),
        }
        episodes.append(record)
        episode_notes[episode] = record
        say(
            f"[video] episode {episode}: {record['category']} d={record['diameter'] * 100:.1f}cm "
            f"success={record['success']} grasped={record['grasped']} placed={record['placed']} "
            f"ticks={record['ticks']} decision={record['decision']} "
            f"frames={record['end'] - record['start']} notes={record['notes']}"
        )

    say(
        f"[video] captured {len(frames['observer'])} frames "
        f"({len(frames['observer']) / fps:.1f}s at {fps:g} fps)"
    )
    if not frames["observer"]:
        say("[video] WARNING: no frames captured; nothing to write")
        app_utils.pause()
        return 1

    # ------------------------------------------------------------------ #
    # Observer annotation (the other views stay clean)
    # ------------------------------------------------------------------ #
    def banner_for(record: dict) -> tuple[str, tuple[int, int, int]]:
        if record["success"]:
            return (
                f"OUTCOME: SUCCESS   grasped=1 placed=1   ticks={record['ticks']} "
                f"({record['ticks'] / 120.0:.1f}s)   decision={record['decision']}",
                (80, 255, 80),
            )
        reason = record["notes"][0] if record["notes"] else "no note"
        return (
            f"OUTCOME: FAIL   {reason[:78]}   ticks={record['ticks']}",
            (80, 80, 255),
        )

    observer_annotated: list[np.ndarray] = []
    for index, image in enumerate(frames["observer"]):
        label = labels[index]
        record = episode_notes[label["episode"]]
        elapsed = (label["tick"] - record["start_tick"]) / 120.0
        finger = "  -   " if label["finger"] is None else f"{label['finger']:.4f}"
        distance = " -  " if label["distance"] is None else f"{label['distance'] * 100:.1f}"
        lines = [
            f"episode {label['episode'] + 1}/{len(episodes)}   t={elapsed:5.1f}s   "
            f"policy_step={label['step']}   tick={label['tick']}   [{label['phase']}]",
            f"finger_cmd {finger} m     |jaw-fruit|xy {distance} cm",
        ]
        banner = banner_for(record) if index >= record["end"] - BANNER_FRAMES else None
        observer_annotated.append(annotate(image, lines, banner))

    # ------------------------------------------------------------------ #
    # Encoders (helpers from 70_record_video.py)
    # ------------------------------------------------------------------ #
    def normalise(image: np.ndarray, width: int, height: int) -> np.ndarray:
        """RGB frame at exactly (height, width) with even dimensions."""
        if image.shape[:2] != (height, width):
            image = cv2.resize(image, (width, height))
        if width % 2 or height % 2:
            image = cv2.copyMakeBorder(
                image, 0, height % 2, 0, width % 2, cv2.BORDER_CONSTANT, value=(0, 0, 0)
            )
        return np.ascontiguousarray(image)

    def write_with_ffmpeg(path: str, images: list[np.ndarray]) -> bool:
        exe = os.environ.get("FRUIT_FFMPEG", "ffmpeg")
        if shutil.which(exe) is None:
            return False
        height, width = images[0].shape[:2]
        # Isaac's python.sh exports LD_PRELOAD=libcarb.so and a kit-only
        # LD_LIBRARY_PATH; both break the system ffmpeg, so drop them.
        env_vars = {
            key: value
            for key, value in os.environ.items()
            if key not in ("LD_PRELOAD", "LD_LIBRARY_PATH")
        }
        command = [
            exe, "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", path,
        ]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, env=env_vars)
        try:
            for image in images:
                process.stdin.write(cv2.cvtColor(image, cv2.COLOR_RGB2BGR).tobytes())
        except BrokenPipeError:
            process.wait()
            return False
        finally:
            if process.stdin is not None:
                process.stdin.close()
        return process.wait() == 0

    def write_with_opencv(path: str, images: list[np.ndarray]) -> None:
        height, width = images[0].shape[:2]
        for fourcc in ("avc1", "mp4v"):
            writer = cv2.VideoWriter(
                path, cv2.VideoWriter_fourcc(*fourcc), fps, (width, height)
            )
            if not writer.isOpened():
                continue
            for image in images:
                writer.write(cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            writer.release()
            if os.path.getsize(path) > 0:
                say(f"[video] ffmpeg unavailable; wrote {path} with OpenCV/{fourcc}")
                return
        say(f"[video] WARNING: could not encode {path}")

    written: dict[str, dict] = {}

    def write(path: str, images: list[np.ndarray]) -> None:
        if not images:
            return
        height, width = images[0].shape[:2]
        if width % 2 or height % 2:
            width += width % 2
            height += height % 2
        prepared = [normalise(image, width, height) for image in images]
        if write_with_ffmpeg(path, prepared):
            say(
                f"[video] wrote {path} ({len(images)} frames, {len(images) / fps:.1f}s, "
                f"H.264 {width}x{height})"
            )
        else:
            write_with_opencv(path, prepared)
        written[os.path.basename(path)] = {
            "frames": len(images),
            "seconds": len(images) / fps,
            "size": (width, height),
        }

    write(os.path.join(args.out_dir, "observer.mp4"), observer_annotated)
    write(os.path.join(args.out_dir, "head.mp4"), frames["head"])
    write(os.path.join(args.out_dir, "gripper.mp4"), frames["close"])

    # Side-by-side: observer + head at a common height.
    height = 480
    paired = []
    for index in range(min(len(observer_annotated), len(frames["head"]))):
        left = cv2.resize(
            observer_annotated[index], (int(observer_annotated[index].shape[1] * height / observer_annotated[index].shape[0]), height)
        )
        right = cv2.resize(
            frames["head"][index], (int(frames["head"][index].shape[1] * height / frames["head"][index].shape[0]), height)
        )
        paired.append(np.hstack([left, right]))
    write(os.path.join(args.out_dir, "side_by_side.mp4"), paired)

    # Provenance beside the clips: manifest (written by the env) + per-episode rows.
    summary = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "checkpoint": args.ckpt,
        "checkpoint_md5": ckpt_md5,
        "presentation": "direct",
        "execute_steps": int(args.execute_steps),
        "ddim_steps": int(args.ddim),
        "camera_res": os.environ["FRUIT_CAMERA_RES"],
        "seed": int(args.seed),
        "episodes_requested": int(args.episodes),
        "capture_every_control_steps": stride,
        "fps": fps,
        "manifest": env.manifest_path or "",
        "episodes": episodes,
        "videos": written,
    }
    summary_path = os.path.join(args.out_dir, "video.json")
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    say(f"[video] summary -> {summary_path}")
    ok = sum(1 for record in episodes if record["success"])
    say(f"[video] outcome {ok}/{len(episodes)} success; DONE")
    app_utils.pause()
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
