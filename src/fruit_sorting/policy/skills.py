"""Automatic skill labelling.

The design discussion calls for a Skill-Routed Diffusion Policy whose router
picks between phase experts. The labels come from robot state alone, so no human
annotation is needed - the same rules the design document specifies:

    approach  gripper open, fruit still on the belt
    grasp     gripper closing/closed on the fruit
    lift      fruit off the belt (carried)
    place     fruit over/inside the destination bin
    recovery  a failure is being handled (no failures in the current demos)
"""

from __future__ import annotations

import numpy as np

#: Order matters: index 0..4 is the router's class order.
SKILLS: tuple[str, ...] = ("approach", "grasp", "lift", "place", "recovery")
SKILL_TO_INDEX = {name: i for i, name in enumerate(SKILLS)}


def label_episode(
    fruit_positions: np.ndarray,
    finger_opening: np.ndarray,
    goal: np.ndarray,
    bin_positions: tuple[tuple[float, float], ...] = ((0.34, 0.44), (0.34, -0.44)),
    lift_height: float = 0.06,
    bin_radius: float = 0.20,
    closed_threshold: float = 0.030,
) -> np.ndarray:
    """Return an int array of skill indices, one per frame."""
    positions = np.asarray(fruit_positions, dtype=np.float64)
    fingers = np.asarray(finger_opening, dtype=np.float64).reshape(len(positions), -1)[:, 0]
    bins = np.asarray(goal, dtype=np.float64).reshape(len(positions), -1)[:, -1]

    # The belt rest height is the lowest the fruit ever sits in this episode.
    rest_z = float(np.percentile(positions[:, 2], 5))
    labels = np.zeros(len(positions), dtype=np.int64)

    for i in range(len(positions)):
        x, y, z = positions[i]
        bin_index = int(round(bins[i])) if 0 <= bins[i] < len(bin_positions) else 0
        bx, by = bin_positions[bin_index]
        over_bin = float(np.hypot(x - bx, y - by)) < bin_radius
        carried = z > rest_z + lift_height
        closing = fingers[i] < closed_threshold

        if over_bin and carried:
            labels[i] = SKILL_TO_INDEX["place"]
        elif carried:
            labels[i] = SKILL_TO_INDEX["lift"]
        elif closing:
            labels[i] = SKILL_TO_INDEX["grasp"]
        else:
            labels[i] = SKILL_TO_INDEX["approach"]
    return labels
