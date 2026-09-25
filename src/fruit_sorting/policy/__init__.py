"""Diffusion policy trained on the scripted demonstrations.

Self-contained implementation (no LeRobot dependency) so the pipeline has few
moving parts: a small convolutional visual encoder over head-camera RGB-D, an
MLP encoder over the goal and proprioception, and a conditional 1-D UNet that
denoises an action chunk.
"""

from __future__ import annotations

__all__ = ["data", "diffusion", "model", "train"]
