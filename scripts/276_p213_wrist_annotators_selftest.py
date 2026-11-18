#!/usr/bin/env python3
"""P213 probe: the wrist camera's annotator list is its own.

P135's two-camera blocker was the second `instance_id_segmentation` product, not
the camera. `FRUIT_WRIST_ANNOTATORS` overrides the wrist list; unset falls back
to `FRUIT_CAMERA_ANNOTATORS` (P135's list), so every existing run is unchanged.
The probe reads no policy; this leg pins the source shape only.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {"passed": 0, "failed": 0}


def check(condition, message):
    if condition:
        CHECKS["passed"] += 1
        print(f"  ok: {message}")
    else:
        CHECKS["failed"] += 1
        print(f"  FAIL: {message}")


def main():
    print("P213: the wrist camera's own annotator list")
    scene = (ROOT / "src" / "fruit_sorting" / "scene.py").read_text(encoding="utf-8")
    start = scene.index("    def _add_wrist_cameras")
    end = scene.index("\n    def ", start + 10)
    body = scene[start:end]
    check("FRUIT_WRIST_ANNOTATORS" in body,
          "the wrist override is read")
    check('os.environ.get(\n                    "FRUIT_CAMERA_ANNOTATORS"' in body,
          "the head list is the fallback")
    check("rgb,distance_to_image_plane,instance_id_segmentation" in body,
          "the fallback keeps P135's list byte for byte")
    check('"FRUIT_WRIST_CAMERA", "0"' in scene,
          "the wrist cameras remain default-off")
    failed = CHECKS["failed"]
    total = CHECKS["passed"] + failed
    print(f"\n{CHECKS['passed']}/{total} checks passed")
    if failed:
        print(f"FAIL: {failed} check(s)")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
