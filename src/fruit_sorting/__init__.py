"""Agent + diffusion-policy fruit sorting on a dynamic conveyor line.

Package layout:

* :mod:`fruit_sorting.common` -- small shared helpers (arrays, quaternions, logging).
* :mod:`fruit_sorting.assets` -- asset URLs and robot constants.
* :mod:`fruit_sorting.scene` -- builds the sorting cell (table, robot, conveyor, bins, head camera).
* :mod:`fruit_sorting.fruits` -- randomized fruit objects and the conveyor spawner.
* :mod:`fruit_sorting.tactile` -- point-tactile sensors on the gripper fingers.
"""

from __future__ import annotations

__all__ = ["assets", "common", "fruits", "scene", "tactile"]
