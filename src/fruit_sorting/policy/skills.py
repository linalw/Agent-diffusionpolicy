"""Automatic skill labelling.

The design discussion calls for a Skill-Routed Diffusion Policy whose router
picks between phase experts. The labels come from robot state alone, so no human
annotation is needed - the same rules the design document specifies:

    approach  gripper open, fruit still on the belt
    grasp     gripper closing/closed on the fruit
    lift      fruit off the belt (carried)
    place     fruit over the destination output conveyor
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
    bin_positions: tuple[tuple[float, float], ...] = ((0.43, 0.55), (0.43, -0.55)),
    lift_height: float = 0.06,
    bin_radius: float = 0.30,
    closed_threshold: float = 0.030,
    close_ramp_frames: int = 5,
) -> np.ndarray:
    """Return an int array of skill indices, one per frame."""
    positions = np.asarray(fruit_positions, dtype=np.float64)
    fingers = np.asarray(finger_opening, dtype=np.float64).reshape(len(positions), -1)[:, 0]
    bins = np.asarray(goal, dtype=np.float64).reshape(len(positions), -1)[:, -1]

    # The belt rest height is the lowest the fruit ever sits in this episode.
    rest_z = float(np.percentile(positions[:, 2], 5))
    labels = np.zeros(len(positions), dtype=np.int64)

    # P145d.12: the **lift** class starts when the committed close ramp settles
    # (the demos' plateau is ~5 frames after the command first crosses the close
    # threshold), not when the fruit is 6 cm up. Measured on the demos: the
    # `carried` rule leaves the whole post-close hold and the test lift ("pop" at
    # close+17) inside the `grasp` class, so no expert ever sees "closed at the
    # belt -> track -> lift", which is exactly the segment the deployed policy
    # must act in. `FRUIT_SKILL_LIFT_RAMP=1` opts in; the labels are computed at
    # load, so a retrain is the whole change (no recollection).
    import os as _os

    _lift_ramp = _os.environ.get("FRUIT_SKILL_LIFT_RAMP", "0") == "1"
    _close_idx = None
    if _lift_ramp:
        _below = np.flatnonzero(fingers < closed_threshold)
        if _below.size:
            _close_idx = int(_below[0])
    _lift_from = None if _close_idx is None else _close_idx + int(close_ramp_frames)

    for i in range(len(positions)):
        x, y, z = positions[i]
        bin_index = int(round(bins[i])) if 0 <= bins[i] < len(bin_positions) else 0
        bx, by = bin_positions[bin_index]
        over_bin = float(np.hypot(x - bx, y - by)) < bin_radius
        carried = z > rest_z + lift_height
        closing = fingers[i] < closed_threshold

        if over_bin and carried:
            labels[i] = SKILL_TO_INDEX["place"]
        elif carried or (_lift_from is not None and i >= _lift_from):
            labels[i] = SKILL_TO_INDEX["lift"]
        elif closing:
            labels[i] = SKILL_TO_INDEX["grasp"]
        else:
            labels[i] = SKILL_TO_INDEX["approach"]
    return labels
