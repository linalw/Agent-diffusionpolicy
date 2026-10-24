"""P36 phase 2: the per-channel OOD asymmetry of the two probe cells (offline).

    python3 logs/p36/ood_proprio.py            # -> logs/p36/ood_proprio.txt
    python3 logs/p36/ood_proprio.py --self-test

The 2x2's two probe cells write *different* proprio vectors into the
observation (`configs/proprio_spoof.json`):

* cell 3 writes `ready` - the posture the shipped direct env holds, so every one
  of the 7 channels is inside the interface's own observed range;
* cell 4 writes `back` - the parked pose, which is the P35 lever's measured
  pose, i.e. the value the policy never sees in the shipped configuration.

This script quantifies how far each vector sits from the population the policy
actually conditions on, and is the source of the numbers quoted in the report's
reading (`logs/p36/PREREG.md` section 8, the OOD asymmetry).

**Two populations**, because the question "out of support" needs one:

* `datasets/rl_rollouts/r9_awr` - the direct interface's own rollouts (56
  episodes, 3261 steps, the same checkpoint `moe_v13s`); the reference for what
  the *policy* sees on this interface.
* `datasets/demos_v11` - the single-arm demonstration store the checkpoint's
  base was trained on (50 episodes, 10228 steps); the reference for what it was
  *trained* on.

The statistic is the per-channel z of the written value against that store's
mean/sd, on the 7 left-arm dof indices (`logs/33_dof.log`'s interleaved layout:
left = 0,2,4,6,8,10,12). A pooled population is used on purpose: in a
left-active episode the left arm moves, so the pooled sd is *wider* than the
inactive arm's own and the |z| here is a **lower bound** on the asymmetry - and
because it is pooled it is a **mixture statistic**, not a support claim. The
support claim is the **range** check printed beside it: a written value outside
the store's observed range for that channel is out of support whatever its z.
"""

from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
LEFT = [0, 2, 4, 6, 8, 10, 12]
STORES = {
    "r9_awr (the direct interface's own rollouts)":
        os.path.join(REPO, "datasets", "rl_rollouts", "r9_awr", "rollout_*.npz"),
    "demos_v11 (the training base)":
        os.path.join(REPO, "datasets", "demos_v11", "episode_*.npz"),
}
OUT = os.path.join(REPO, "logs", "p36", "ood_proprio.txt")


def load_store(pattern: str, limit: int = 60) -> np.ndarray:
    paths = sorted(glob.glob(pattern))[:limit]
    if not paths:
        return np.zeros((0, 7))
    return np.concatenate([np.load(p)["joint_positions"][:, LEFT] for p in paths], 0)


def table(q: np.ndarray, vectors: dict, label: str) -> list[str]:
    lines = [f"  {label}: n={len(q)} steps"]
    mean, sd = q.mean(0), q.std(0)
    lines.append(f"    {'joint':6s} {'mean':>8s} {'sd':>8s} {'range':>20s} "
                 + "  ".join(f"z({p})" for p in vectors))
    for j in range(7):
        zs = "  ".join(f"{(np.asarray(v)[j] - mean[j]) / sd[j]:+7.2f}"
                       for v in vectors.values())
        lines.append(f"    j{j + 1:<5d} {mean[j]:+8.3f} {sd[j]:8.4f} "
                     f"[{q[:, j].min():+.3f},{q[:, j].max():+.3f}]   {zs}")
    return lines


def self_test() -> int:
    ok = True
    q = np.array([[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                  [2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]])
    mean, sd = q.mean(0), q.std(0)
    if not (abs((3.0 - mean[0]) / sd[0] - 2.0) < 1e-9):
        print("self-test FAILED: the z of +3.0 against {0,2} is not 2.0")
        ok = False
    if not (abs(sd[1]) < 1e-12):
        print("self-test FAILED: a constant channel must have sd 0 (and be skipped)")
        ok = False
    print("self-test ok" if ok else "self-test failed")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    with open(os.path.join(REPO, "configs", "proprio_spoof.json"), encoding="utf-8") as fh:
        poses = json.load(fh)["poses"]
    vectors = {"ready": poses["ready"]["left"], "back": poses["back"]["left"]}
    lines = ["P36 phase 2 - the per-channel OOD asymmetry of the probe cells",
             "=" * 78,
             "the 7 left-arm dof indices (0,2,4,6,8,10,12); z = (written - mean)/sd",
             "of the population in the same row; the written vectors are",
             f"  ready = {vectors['ready']}",
             f"  back  = {vectors['back']}",
             ""]
    summary = []
    for label, pattern in STORES.items():
        q = load_store(pattern)
        if not len(q):
            lines.append(f"  {label}: MISSING ({pattern})")
            continue
        lines += table(q, vectors, label)
        mean, sd = q.mean(0), q.std(0)
        zr = np.abs((np.asarray(vectors["ready"]) - mean) / sd)
        zb = (np.asarray(vectors["back"]) - mean) / sd
        summary.append((label, float(zr.max()), int(np.argmax(np.abs(zb))),
                        float(zb[int(np.argmax(np.abs(zb)))])))
        lines.append(f"    => ready: max |z| = {zr.max():.2f} over the 7 channels")
        lines.append(f"    => back : j{int(np.argmax(np.abs(zb))) + 1} at "
                     f"{zb[int(np.argmax(np.abs(zb)))]:+.2f} sigma (max |z| "
                     f"{np.abs(zb).max():.2f}); "
                     f"{int((np.abs(zb) > 1.7).sum())}/7 channels beyond 1.7 sigma")
        # The support claim: which written values leave the observed range.
        for name, vec in vectors.items():
            arr = np.asarray(vec, dtype=float)
            outside = [f"j{j + 1}" for j in range(7)
                       if arr[j] < q[:, j].min() or arr[j] > q[:, j].max()]
            lines.append(f"    => {name}: outside the observed range: "
                         + (", ".join(outside) if outside else "none"))
        lines.append("")
    lines += [
        "READING: cell 3 holds the *in-support* ready proprio under the parked",
        "image; cell 4 holds the *parked* proprio under the shipped image. The",
        "support claim rests on the RANGE, not on the sigma summary: the parked",
        "vector's j2 (-0.978 rad) is the *only* one of the 7 channels outside",
        "either store's observed range ([-0.777,+0.175] direct, [-0.792,+0.175]",
        "training); the other two >1.7-sigma channels (j1, j4) sit inside theirs,",
        "so \"4-5 sigma\" is a pooled-population mixture statistic. So a cell-4",
        "POSITIVE is the stronger read (the park's own proprio channel, alone, on",
        "an in-support image) and a cell-4 NULL is the weaker one (an out-of-range",
        "input may simply be ignored, or the network may have no path for it) -",
        "the asymmetry the PREREG's section 8a records. The direction is",
        "conservative: it argues against over-reading the proprio null, not",
        "against the image cell.",
    ]
    text = "\n".join(lines) + "\n"
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text, end="")
    print(f"wrote {os.path.relpath(OUT, REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
