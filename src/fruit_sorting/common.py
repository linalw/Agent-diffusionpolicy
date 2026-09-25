"""Shared helpers for the fruit-sorting simulation."""

from __future__ import annotations

import os
import sys
from typing import Any, Sequence

import numpy as np

LOG_PREFIX = os.environ.get("FRUIT_LOG_PREFIX", "fruit")


def say(msg: str) -> None:
    """Print and flush; Isaac Sim's fast shutdown drops buffered stdout."""
    print(f"[{LOG_PREFIX}] {msg}", flush=True)


def to_numpy(value: Any) -> np.ndarray | None:
    """Convert warp arrays / (array, metadata) tuples / numpy arrays to numpy.

    ``wp.array`` objects reject item indexing, so ``numpy.asarray`` cannot be used
    on them directly.
    """
    if value is None:
        return None
    if isinstance(value, tuple):
        value = value[0]
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value)


def look_at_quat(
    eye: Sequence[float],
    target: Sequence[float],
    up: Sequence[float] = (0.0, 0.0, 1.0),
) -> list[float]:
    """Quaternion ``(w, x, y, z)`` for a USD camera at ``eye`` looking at ``target``.

    USD cameras look down ``-Z`` with ``+Y`` up and ``+X`` right.
    """
    eye_arr = np.asarray(eye, dtype=float)
    target_arr = np.asarray(target, dtype=float)
    z_axis = eye_arr - target_arr
    z_axis = z_axis / np.linalg.norm(z_axis)
    x_axis = np.cross(np.asarray(up, dtype=float), z_axis)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    rot = np.stack([x_axis, y_axis, z_axis], axis=1)
    trace = float(np.trace(rot))
    w = np.sqrt(max(1.0 + trace, 0.0)) / 2.0
    if w < 1e-8:
        return [1.0, 0.0, 0.0, 0.0]
    x = (rot[2, 1] - rot[1, 2]) / (4.0 * w)
    y = (rot[0, 2] - rot[2, 0]) / (4.0 * w)
    z = (rot[1, 0] - rot[0, 1]) / (4.0 * w)
    return [float(w), float(x), float(y), float(z)]


def install_failure_handler(script_name: str) -> None:
    """Write an uncaught exception to a log file; Kit's shutdown eats tracebacks."""
    import traceback

    def _hook(exc_type, exc_value, exc_tb):
        os.makedirs("logs", exist_ok=True)
        with open(f"logs/{script_name}_traceback.txt", "w", encoding="utf-8") as fh:
            traceback.print_exception(exc_type, exc_value, exc_tb, file=fh)
        print(f"[{LOG_PREFIX}] FAILED - see logs/{script_name}_traceback.txt", flush=True)

    sys.excepthook = _hook
