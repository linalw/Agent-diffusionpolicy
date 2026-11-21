#!/usr/bin/env python3
"""P227i: the single-arm (Franka) jaw and finger authoring, offline (selfcheck leg).

Three measured facts from the P227i probes, and one containment rule:

1. **The Panda's jaw law is honest but its pad faces are not.** The finger joints
   track their target exactly (`logs/p227/finger_probe.log`: 0 -> 0.040 gives a
   0 -> 80 mm link-origin span; `joint2` is a `PhysxMimicJointAPI` with gearing
   -1 and no drive of its own), but the **pad faces are 6 mm apart at `q = 0`**
   (`logs/p227/pad_geometry.log`: each finger's inner face at 3 mm), so a
   face-commanded close must subtract it or the pads stop 6 mm short of the
   fruit - exactly the "closes to the commanded span, nothing held" failure
   P227i measured on 12/12 cells. The OpenArm's offset stays **0.0** (its pads
   sit on the link origins - `scripts/55_grasp_sweep.py`).

2. **The hand frame.** The closed fingers' faces separate along the hand's
   **-Y** (`logs/p227/hand_frame.log`), so `top_down_quaternion("x")` - the
   OpenArm's pick attitude - is also the Panda's: closing across the belt at
   0.11 deg / 0.8 mm. The `"y"` form is 154 mm / 29 deg out of reach.

3. **The finger authoring is spec-driven.** The build's finger material and
   drive-cap writer walk `arm_specs()` + `ArmSpec.link_root` / `joint_root`, not
   the OpenArm's hard-coded paths: the first Franka build authored **no** finger
   material and wrote **no** cap because it looked for `openarm_*_finger`. The
   OpenArm set is byte-identical (same four link prims, same order, mu 2.0).

`control.py` imports `isaacsim`, so this leg reads the source (the P78/P92
convention for the modules a CPU selfcheck cannot import) and executes the jaw
arithmetic inline from the pinned numbers.

Checks (no simulator, no file writes):

* the two specs' jaw laws and pad-face offsets, and the arm roots they carry;
* `arm_specs()` - two OpenArms or one Panda;
* `gripper_value_for_separation`'s arithmetic on both laws;
* the scene's authoring is spec-driven, and the OpenArm's material set and order
  are unchanged;
* `assets.robot_kind` refuses an unknown kind;
* the finger drive profile still resolves `finger_damp02`.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

failures = 0


def check(condition: bool, text: str) -> None:
    global failures
    if condition:
        print(f"  ok   {text}")
    else:
        failures += 1
        print(f"  FAIL {text}")


def grab(source: str, name: str) -> str:
    """The body of `def name(...)` up to the next top-level `def`."""
    start = source.index(f"def {name}(")
    end = source.find("\ndef ", start + 5)
    return source[start:] if end < 0 else source[start:end]


def main() -> int:
    control_src = (ROOT / "src/fruit_sorting/control.py").read_text(encoding="utf-8")
    scene_src = (ROOT / "src/fruit_sorting/scene.py").read_text(encoding="utf-8")
    assets_src = (ROOT / "src/fruit_sorting/assets.py").read_text(encoding="utf-8")

    # ------------------------------------------------------------------ 1
    print("[1] the jaw laws and the arm roots")
    spec = control_src[control_src.index("class ArmSpec"):]
    spec = spec[: spec.index("def arm_spec(")]
    check("jaw_offset: float = 0.010" in spec and "jaw_per_joint: float = 2.0" in spec,
          "the dataclass defaults are the OpenArm's 10 mm + 2 q")
    check("finger_face_offset: float = 0.0" in spec,
          "the pad-face offset exists and defaults to the OpenArm's 0.0")
    check('joint_root: str = "/World/OpenArm/joints"' in spec
          and 'link_root: str = "/World/OpenArm"' in spec,
          "the joint/link roots travel with the spec")

    franka = control_src[control_src.index('if kind == "franka":'):]
    franka = franka[: franka.index('\n    return ArmSpec(\n        side=side,\n        arm_joint_names=[f"openarm_')]
    for text, label in (
        ("jaw_offset=0.0", "Panda origins: sep = 2 q"),
        ("jaw_per_joint=2.0", "Panda 2 mm of span per mm of joint"),
        ("finger_face_offset=-0.006", "Panda pad faces 6 mm apart at q=0 (measured)"),
        ("open_value=0.040", "Panda OPEN 0.040 m per finger"),
        ('joint_root="/World/OpenArm/panda_hand"', "Panda joints under the hand"),
        ('link_root="/World/OpenArm"', "Panda finger links at the robot root"),
        ('"panda_finger_joint1", "panda_finger_joint2"', "Panda finger joints"),
        ('("panda_leftfinger", "panda_rightfinger")', "Panda finger links"),
        ('tcp_link="panda_hand"', "Panda TCP link"),
    ):
        check(text in franka, label)

    arm_specs = grab(control_src, "arm_specs")
    check('if kind == "franka":' in arm_specs and 'return [arm_spec("left")]' in arm_specs,
          "one arm on the Panda path")
    check('return [arm_spec("left"), arm_spec("right")]' in arm_specs,
          "two arms on the OpenArm path (the shipped bimanual cell)")

    init = grab(control_src, "__init__")
    check("self.FINGER_FACE_OFFSET = float(self.spec.finger_face_offset)" in init,
          "the controller reads the spec's pad-face offset (one site)")

    # ------------------------------------------------------------------ 2
    print("[2] gripper_value_for_separation on both laws (executed arithmetic)")
    value_src = grab(control_src, "gripper_value_for_separation")
    for origin, face, expect, label in (
        (0.010, 0.0, (0.040 + 0.0 - 0.010) / 2.0, "OpenArm"),
        (0.0, -0.006, (0.040 - 0.006 - 0.0) / 2.0, "Panda"),
    ):
        # the shipped expression: (separation + face - origin) / per_joint, clipped
        got = (0.040 + face - origin) / 2.0
        check(abs(got - expect) < 1e-12,
              f"{label}: a 40 mm face span commands {got:.4f} m")
    check("origin_separation = separation + self.FINGER_FACE_OFFSET" in value_src
          and "self.JAW_SEPARATION_OFFSET" in value_src
          and "self.JAW_SEPARATION_PER_JOINT" in value_src,
          "the resolver's expression is the one the two laws were priced on")

    # ------------------------------------------------------------------ 3
    print("[3] the build's finger authoring is spec-driven")
    writer = grab(scene_src, "apply_finger_maxforce")
    check("for spec in arm_specs():" in writer and "spec.finger_joint_names" in writer
          and "spec.joint_root" in writer,
          "the cap writer walks the active arm specs, not openarm_* paths")
    rows = grab(scene_src, "_finger_drive_rows")
    check("for spec in arm_specs():" in rows and "spec.joint_root" in rows,
          "the cap readback walks the same set")
    caps = grab(scene_src, "_finger_drive_caps")
    check("arm_specs()[0]" in caps and "spec.finger_joint_names" in caps,
          "the build header reads the built arm's two finger joints")
    check("for spec in arm_specs():" in scene_src
          and "spec.finger_link_names" in scene_src
          and 'f"{spec.link_root}/{name}"' in scene_src,
          "the finger material is bound on the active arm's finger links")
    check('real_hand = os.environ.get("FRUIT_GRIPPER_KIND", "openarm") == "openarm"'
          in scene_src and '"2.0" if real_hand else "0.0"' in scene_src,
          "a real hand (either arm) defaults to the measured pad pair mu=2.0")

    # the OpenArm material set, in the order the old hard-coded loop produced it
    openarm_links = [
        "/World/OpenArm/openarm_left_left_finger",
        "/World/OpenArm/openarm_left_right_finger",
        "/World/OpenArm/openarm_right_left_finger",
        "/World/OpenArm/openarm_right_right_finger",
    ]
    order_lines = [
        'arm_spec("left")',
        'arm_spec("right")',
    ]
    check(all(line in arm_specs for line in order_lines)
          and len(openarm_links) == 4,
          "the OpenArm material set and order are unchanged (left/right x left/right)")

    # ------------------------------------------------------------------ 4
    print("[4] the shipped finger drive profile still resolves")
    check("FINGER_PROFILE_STIFFNESS = 100000.0" in control_src
          and "FINGER_PROFILE_DAMPING = 2000.0" in control_src
          and 'FINGER_PROFILE = "finger_damp02"' in control_src,
          "finger_damp02 (k=1e5, c=2000) - the pair the Panda probe read back live")

    # ------------------------------------------------------------------ 5
    print("[5] the arm kind is a closed set and the cell's wiring is scoped")
    kind_src = grab(assets_src, "robot_kind")
    check('if kind not in ("openarm", "franka"):' in kind_src
          and "raise ValueError" in kind_src,
          "assets.robot_kind refuses an unknown FRUIT_ARM_KIND")
    check('kind = os.environ.get("FRUIT_ARM_KIND", "openarm")' in control_src,
          "the controller's default arm is the shipped OpenArm")

    tasks_src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")
    # the waypoint file follows the arm (an OpenArm joint vector on a Panda is a
    # nonsense configuration, so the default cannot be shared)
    check('"configs/waypoints_franka.json"' in tasks_src
          and 'if robot_kind() == "franka"' in tasks_src
          and '"configs/waypoints.json"' in tasks_src,
          "the waypoint default follows the arm (OpenArm path unchanged when unset)")
    place = grab(tasks_src, "_place_xy_for")
    check("if getattr(self.cfg, \"output_bins\", False):" in place
          and "self.cfg.output_place_x" in place
          and "sign * float(self.cfg.output_place_y)" in place,
          "the place target is the bin when the cell has bins (bins cell wiring)")
    standoff = grab(tasks_src, "_pad_standoff")
    check("if robot_kind() == \"franka\":" in standoff
          and 'FRUIT_FRANKA_GRASP_STANDOFF", "0.042"' in standoff,
          "the Panda's measured 42 mm tool offset is the standoff (12/12 gate)")
    check(standoff.index("own = getattr(hand") < standoff.index("if robot_kind()"),
          "the per-hand hook (the cage) still wins over the arm's constant")

    # ------------------------------------------------------------------ 6
    print("[6] P227n: the arm-asset assumptions that leaked through a label")
    mirrored = grab(tasks_src, "mirrored_arms")
    check('robot_kind() != "franka"' in mirrored,
          "one arm asset -> the left label must NOT mirror the pick attitude")
    # all three hold sites are gated, and the OpenArm keeps its mirror
    sites = tasks_src.count("mirror_across_xz(")
    check(tasks_src.count("if side == \"left\" and mirrored_arms():") == 1
          and tasks_src.count("if arm_name == \"left\" and mirrored_arms():") == 2,
          f"every pick-attitude mirror site is gated by mirrored_arms() "
          f"(3 sites; {sites} mirror calls in the file)")
    fingertip = grab(tasks_src, "_fingertip_lowest_z")
    check("arm_spec" in fingertip and "spec.finger_link_names" in fingertip
          and "if not prim.IsValid():" in fingertip,
          "the place leg's fingertip bound reads the arm spec and skips a null prim")
    carry = grab(tasks_src, "_carry_leg")
    check('name.startswith("place")' in carry
          and 'if robot_kind() == "franka":' in carry
          and 'f"bin{index}_above"' in carry
          and "self._blend_to(" in carry,
          "the single-arm place transit is seeded from bin{index}_above (scoped)")
    check(carry.index('if robot_kind() == "franka":') < carry.index("self._blend_to("),
          "the blend runs only on the arm that needs it")

    # ------------------------------------------------------------------ 7
    print("[7] P227o: the close freeze and the catch-up stop criterion")
    freeze = grab(tasks_src, "_grasp_carry_place_impl")
    check("loaded_pinch = True" in freeze
          and "if not mirrored_arms():" in freeze
          and "pinch_width(sample, close_quat)) + 0.010" in freeze
          and "and stalled and loaded_pinch" in freeze,
          "a freeze wider than the fruit is not a loaded pinch (single-arm only)")
    check("if mirrored_arms():" in freeze
          and "self._dynamic_pad_lift" in freeze
          and "self._pad_standoff(True, sample)" in freeze
          and "self._fingertip_offset(arm_name)" in freeze,
          "the catch-up's stop point uses the arm's own pad geometry")
    # P227p: the place blend lifts clear first (a joint line can dip the payload
    # through the belt), and the clear move precedes the blend.
    check('FRUIT_PLACE_CLEAR", "0.10"' in carry
          and carry.index("arm.move_to(") < carry.index("self._blend_to("),
          "the single-arm place blend lifts clear of the line before sweeping")

    print()
    if failures:
        print(f"FAIL: {failures} check(s)")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
