"""What does the belt actually do to the fruit? Measure it, don't argue about it.

    scripts/run.sh scripts/170_transport_probe.py

Watching the sorting cell raises three questions that impressions cannot settle:

1. **Is the belt speed constant, and does an *encoder* read the same?** The belt
   surface is commanded through `PhysxSurfaceVelocityAPI`, so "the commanded value"
   is not evidence of what the surface does. This probe reads a *belt encoder* the
   way a real one works - from how far the cleats (the belt furniture, which is
   driven at the same surface speed) actually travel per tick - and reports both.
2. **Do the fruit travel with the belt or roll on it?** A sphere carried by a
   friction belt is *spun up* by the friction force at its contact patch, so it
   rolls; a fruit pushed by a cleat that meets it at its own centre height feels no
   torque about the centre and slides along without rotating. The probe reports
   `roll = |omega| * r / |v|` per fruit: **1.0 is rolling without slipping, 0 is not
   rotating at all.**
3. **Do they stop and wait at the pick station?** The probe counts the ticks each
   fruit spends below `FRUIT_STALL_SPEED` (default 0.02 m/s) between its spawn point
   and the pick point.

Output is one line every `FRUIT_TRANSPORT_LOG_EVERY` ticks (default 30, i.e. 0.25 s)
plus a summary, and it exits non-zero if any fruit stalled - so it can be used as a
regression check on the transport model.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()

simulation_app = SimulationApp({"headless": True, "width": 640, "height": 480})

import numpy as np

import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.core.simulation_manager import SimulationManager
from fruit_sorting.assets import SceneConfig
from fruit_sorting.common import install_failure_handler, say
from fruit_sorting.fruits import FruitSpawner
from fruit_sorting.scene import SortingScene

install_failure_handler("170_transport_probe")

DT = 1.0 / 120.0
SECONDS = float(os.environ.get("FRUIT_TRANSPORT_SECONDS", "14"))
TICKS = int(SECONDS / DT)
LOG_EVERY = int(os.environ.get("FRUIT_TRANSPORT_LOG_EVERY", "30"))
STALL_SPEED = float(os.environ.get("FRUIT_STALL_SPEED", "0.02"))
PRIME = int(os.environ.get("FRUIT_TRANSPORT_PRIME", "3"))


def main() -> int:
    cfg = SceneConfig()
    # Transport-mechanism knobs, so the probe can attribute "the fruit are not
    # carried" to a specific piece of the belt rather than to "the belt".
    cfg.cleat_height = float(os.environ.get("FRUIT_CLEAT_HEIGHT", cfg.cleat_height))
    cfg.cleat_spacing = float(os.environ.get("FRUIT_CLEAT_SPACING", cfg.cleat_spacing))
    cfg.cleat_width = float(os.environ.get("FRUIT_CLEAT_WIDTH", cfg.cleat_width))
    cfg.belt_friction = float(os.environ.get("FRUIT_BELT_FRICTION", cfg.belt_friction))
    scene = SortingScene(cfg).build()
    scene.start(physics_dt=DT, warmup_steps=60)

    spawner = FruitSpawner(scene.stage, cfg, seed=int(os.environ.get("SEED", "5")))
    spawner.create_pool()
    app_utils.update_app(steps=30)
    spawner.refresh_rigids()
    spawner.belt = scene.belt
    spawner.reset()
    spawner.prime(count=PRIME)

    belt = scene.belt
    say(
        f"[transport] belt commanded surface velocity {cfg.belt_speed:+.3f} m/s, "
        f"ramp={belt.ramp_enabled}, cleats={belt.cleat_count} @ "
        f"{cfg.cleat_spacing:.3f} m, cleats start at y={belt.cleat_start:+.3f}"
    )

    def encoder_from_cleats() -> float:
        """The same quantity `CleatedBelt.encoder_speed` maintains."""
        return float(belt.encoder_speed)

    def cleat_x() -> float:
        if not belt.cleats:
            return float("nan")
        return float(
            np.asarray(belt.cleats[0].get_world_poses()[0][0].numpy(), dtype=float)[1]
        )

    # An encoder counts how far the belt *travelled*, so reading it means
    # differencing the furniture, not the commanded velocity.
    previous_cleat = cleat_x()
    span = max(belt.cleat_span, 1e-6)
    encoder = float("nan")
    samples = []  # (encoder, speed_cmd)

    if os.environ.get("FRUIT_TRANSPORT_CONTACTS", "1") == "1":
        say(f"[transport] contact tracking on {spawner.enable_contact_tracking()} fruit")

    stalls: dict[int, int] = {}
    rolls: dict[int, list[float]] = {}
    ratios: dict[int, list[float]] = {}
    spinning: dict[int, list[float]] = {}
    forces: dict[int, list[float]] = {}
    for tick in range(TICKS):
        spawner.enforce_transport(DT)
        SimulationManager.step(steps=1)
        app_utils.update_app(steps=0)

        now = cleat_x()
        if np.isfinite(now) and np.isfinite(previous_cleat):
            delta = now - previous_cleat
            # The cleats wrap around the belt loop; unwrap before differencing.
            if delta > span / 2.0:
                delta -= span
            elif delta < -span / 2.0:
                delta += span
            encoder = delta / DT
        previous_cleat = now

        contact_forces = spawner.net_contact_forces()
        for sample in list(spawner.active):
            if sample.parked or sample.held:
                continue
            velocity = np.asarray(spawner.velocity(sample), dtype=float)[:3]
            position = np.asarray(spawner.position(sample), dtype=float)
            if position[1] < cfg.pick_y:
                continue  # already past the pick point (-Y is downstream)
            # `|v|/|enc|` compares the fruit's *translation* with the belt. The
            # `spin` column is what a rolling contact predicts: a sphere carried
            # without slipping satisfies |omega| * r == |v| (and `roll`, the ratio
            # of those two, is 1.0 for pure rolling and 0 for pure sliding).
            ratio = float(np.linalg.norm(velocity) / max(abs(encoder), 1e-6))
            ratios.setdefault(sample.index, []).append(ratio)
            rolls.setdefault(sample.index, []).append(abs(float(velocity[1])))
            spin = float(
                np.linalg.norm(np.asarray(spawner.angular(sample), dtype=float)[:3])
            ) * (sample.diameter / 2.0)
            spinning.setdefault(sample.index, []).append(spin)
            forces.setdefault(sample.index, []).append(
                float(
                    np.linalg.norm(
                        np.asarray(
                            contact_forces.get(sample.index, [0.0, 0.0, 0.0]), dtype=float
                        )
                    )
                )
            )
            if abs(float(velocity[1])) < STALL_SPEED and position[1] > cfg.spawn_y - 0.6:
                stalls[sample.index] = stalls.get(sample.index, 0) + 1

        if tick % LOG_EVERY == 0:
            samples.append((encoder, float(belt.speed)))
            parts = []
            for sample in sorted(spawner.active, key=lambda s: s.index):
                if sample.parked or sample.held:
                    continue
                position = np.asarray(spawner.position(sample), dtype=float)
                velocity = np.asarray(spawner.velocity(sample), dtype=float)[:3]
                spin_now = float(
                    np.linalg.norm(np.asarray(spawner.angular(sample), dtype=float)[:3])
                ) * (sample.diameter / 2.0)
                force = float(
                    np.linalg.norm(
                        np.asarray(
                            contact_forces.get(sample.index, [0.0, 0.0, 0.0]), dtype=float
                        )
                    )
                )
                parts.append(
                    f"#{sample.index} {sample.category[:4]} "
                    f"y={position[1]:+.3f} x={position[0]:+.3f} z={position[2]:.3f} "
                    f"(belt+r={cfg.belt_center[2] + cfg.belt_size[2] / 2.0 + sample.diameter / 2.0:.3f}) "
                    f"vy={velocity[1]:+.3f} "
                    f"|v|={np.linalg.norm(velocity):.3f} "
                    f"spin={spin_now:.3f} F={force:5.1f}N"
                )
            say(
                f"[transport] t={tick * DT:5.2f}s cmd={belt.speed:+.3f} "
                f"enc={encoder:+.3f} | " + " | ".join(parts)
            )

    say("[transport] ---- summary ----")
    encoders = np.asarray([value for value, _ in samples], dtype=float)
    commanded = np.asarray([value for _, value in samples], dtype=float)
    say(
        f"[transport] encoder: mean {np.nanmean(encoders):+.4f} m/s, "
        f"min {np.nanmin(encoders):+.4f}, max {np.nanmax(encoders):+.4f}, "
        f"spread {np.nanmax(encoders) - np.nanmin(encoders):.4f} m/s"
    )
    say(
        f"[transport] commanded: min {commanded.min():+.4f}, max {commanded.max():+.4f} m/s"
    )
    for index in sorted(ratios):
        values = np.asarray(ratios[index], dtype=float)
        spin = np.asarray(spinning[index], dtype=float)
        force = np.asarray(forces[index], dtype=float)
        speed = np.asarray([abs(v) for v in rolls[index]], dtype=float)
        say(
            f"[transport] fruit #{index}: |v|/|enc| median {np.median(values):.2f} "
            f"(1.0 = travels with the belt), spin |omega|*r median {np.median(spin):.3f} "
            f"vs |vy| median {np.median(speed):.3f} m/s -> roll ratio "
            f"{np.median(spin) / max(np.median(speed), 1e-6):.2f}, "
            f"contact force median {np.median(force):.1f} N "
            f"(in contact {np.mean(force > 0.01) * 100:.0f}% of ticks), "
            f"min |vy| {min(rolls[index]):.3f} m/s, stalled {stalls.get(index, 0)} ticks"
        )
    stalled = sum(stalls.values())
    say(f"[transport] total stalled ticks: {stalled}")
    say("[transport] DONE")
    return 1 if stalled else 0


if __name__ == "__main__":
    raise SystemExit(main())
