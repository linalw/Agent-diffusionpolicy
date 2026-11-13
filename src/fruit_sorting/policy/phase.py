"""P145c: the goal-conditioned phase gate (vision + touch, no arm pose).

The policy's MoE router reads the full condition (image, goal, proprio, time); in
the closed loop its argmax flips to `lift` while the fruit is still on the belt,
because the arm's own early close makes the observation look like the post-grasp
state. This gate replaces the router's phase at inference with a classifier on
the **perceived fruit and the finger only**:

    [fruit xyz, fruit velocity, diameter, finger opening] -> skill

trained on the demonstrations' own `label_episode` rule (`logs/p145/train_phase.py`,
98.1 % on held-out episodes). Every input is available at deployment: the first
seven from the depth-camera goal, the last from the finger channel.

`FRUIT_POLICY_PHASE=goal` (default off) makes `PolicyRunner.act` pass the gate's
class as the diffusion model's hard `skill_labels`; unset is byte-inert.
"""
from __future__ import annotations

import os

import numpy as np

from .skills import SKILLS


class PhaseGate:
    """A tiny MLP over the task-state features."""

    def __init__(self, payload: dict):
        import torch

        self._torch = torch
        self.skills = list(payload.get("skills", SKILLS))
        self.mean = np.asarray(payload["mean"], dtype=np.float32)
        self.std = np.asarray(payload["std"], dtype=np.float32)
        self.net = torch.nn.Sequential(
            torch.nn.Linear(len(self.mean), 64),
            torch.nn.SiLU(),
            torch.nn.Linear(64, 64),
            torch.nn.SiLU(),
            torch.nn.Linear(64, len(self.skills)),
        )
        self.net.load_state_dict(payload["model"])
        self.net.eval()
        self.last_skill = -1
        self.last_probs = None

    @classmethod
    def load(cls, path: str) -> "PhaseGate":
        import torch

        if not os.path.exists(path):
            raise FileNotFoundError(
                f"FRUIT_POLICY_PHASE=goal needs the classifier at {path!r}; train it "
                "with logs/p145/train_phase.py or unset the knob"
            )
        return cls(torch.load(path, map_location="cpu", weights_only=False))

    def features(self, goal: np.ndarray, proprio: np.ndarray) -> np.ndarray:
        """`(pos3, vel3, diameter, finger)` from the observation.

        The finger is the last-but-two entry of the proprio vector: `proprio()`
        assembles 22 joints + the active finger + the two tactile forces.
        """
        g = np.asarray(goal, dtype=np.float32).reshape(-1)
        p = np.asarray(proprio, dtype=np.float32).reshape(-1)
        finger = float(p[22]) if p.size > 22 else 0.044
        if g.size < 7:
            raise ValueError(f"goal has {g.size} dims, need >= 7")
        return np.concatenate(
            [g[0:3], g[3:6], g[6:7], np.array([finger], dtype=np.float32)]
        )

    def predict(self, goal: np.ndarray, proprio: np.ndarray) -> int:
        import torch

        x = (self.features(goal, proprio) - self.mean) / self.std
        with torch.no_grad():
            logits = self.net(torch.from_numpy(x)[None])
            probs = torch.softmax(logits, dim=-1)[0].numpy()
        self.last_probs = probs
        self.last_skill = int(probs.argmax())
        return self.last_skill

    def reset(self) -> None:
        self.last_skill = -1
        self.last_probs = None
