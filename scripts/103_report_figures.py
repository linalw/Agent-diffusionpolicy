"""Generate the two figures used by 项目总结报告.md.

    python3 scripts/103_report_figures.py

Figure 1 compares the old constant-velocity carry with the jerk-limited profile
the cell uses now (computed with the real `fruit_sorting.motion` code, so the
numbers match `logs/236/238`).
Figure 2 is the headline results chart, with the numbers taken from the logs cited
in the report.
"""

from __future__ import annotations

import os
import sys

import matplotlib
import matplotlib.font_manager as font_manager

matplotlib.use("Agg")
# Use a CJK font when available so the figures can carry Chinese labels.
for _font in ("Noto Sans CJK SC", "Noto Sans CJK TC", "WenQuanYi Zen Hei", "Noto Sans SC"):
    if any(_font.lower() in name.lower() for name in font_manager.get_font_names()):
        matplotlib.rcParams["font.family"] = _font
        break
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.motion import TrajectoryLimits, jerk_limited  # noqa: E402

OUT = os.path.join("logs", "report")
DT = 1.0 / 120.0


def figure_motion() -> str:
    distance = 0.40                      # the 40 cm transfer leg
    old_steps = 400                      # legacy: constant velocity, 400 ticks
    limits = TrajectoryLimits.from_env(DT)
    pos, vel, acc = jerk_limited(distance, limits)

    old_vel = np.full(old_steps, distance * 120.0 / old_steps)
    old_time = np.arange(1, old_steps + 1) * DT
    new_time = np.arange(len(pos)) * DT

    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=False)
    axes[0].plot(old_time, old_vel, label="before: constant velocity", color="#c1440e")
    axes[0].plot(new_time[:len(vel)], vel, label="now: jerk-limited S-curve", color="#1f6f8b")
    axes[0].axhline(0.0, color="#888", lw=0.6)
    axes[0].set_ylabel("velocity [m/s]")
    axes[0].set_title("40 cm transfer leg: before, full speed instantly and a dead stop")
    axes[0].legend(loc="upper right", fontsize=9)
    axes[0].grid(alpha=0.25)

    # Pad with rest at both ends so the legacy profile's velocity *steps* show up
    # as impulse-like acceleration spikes (+-14.3 m/s^2 at this leg length).
    old_padded = np.r_[0.0, old_vel, 0.0]
    old_acc = np.diff(old_padded) / DT
    old_time_padded = np.r_[0.0, old_time, old_time[-1] + DT]
    axes[1].set_yscale("symlog", linthresh=1.0)
    axes[1].plot(old_time_padded[1:], old_acc, color="#c1440e",
                 label="before: +-14.3 m/s^2 step at both ends",
                 drawstyle="steps-post")
    new_acc = np.diff(vel) / DT
    axes[1].plot(new_time[1:], new_acc, label="now: bounded jerk",
                 color="#1f6f8b")
    axes[1].set_xlabel("time [s]")
    axes[1].set_ylabel("acceleration [m/s$^2$]")
    axes[1].legend(loc="upper right", fontsize=9)
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    path = os.path.join(OUT, "fig_motion.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"wrote {path}")
    return path


def figure_results() -> str:
    labels = [
        "scripted cell\n(20 picks)",
        "hybrid closed loop\n(15 episodes)",
        "small fruit\n(8 picks)",
        "kinematic gripper\n(isolated)",
        "actuated gripper\n(best isolated)",
    ]
    rates = [90, 80, 88, 100, 60]
    counts = ["18/20", "12/15", "7/8", "10/10", "3/5"]
    colors = ["#1f6f8b", "#3f8ea6", "#79b3c4", "#2e7d32", "#c1440e"]

    fig, ax = plt.subplots(figsize=(9, 4.2))
    bars = ax.bar(labels, rates, color=colors)
    for bar, note in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5, note,
                ha="center", fontsize=10)
    ax.set_ylim(0, 115)
    ax.set_ylabel("success rate [%]")
    ax.set_title("Measured success rates (log ids in the project report)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    path = os.path.join(OUT, "fig_results.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    print(f"wrote {path}")
    return path


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    figure_motion()
    figure_results()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
