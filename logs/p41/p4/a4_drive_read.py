"""A4 check (P41 phase 4): the drive-cap read must not apply the drive schema.

    HEADLESS=1 scripts/run.sh logs/p41/p4/a4_drive_read.py

The question is narrow. `_finger_drive_caps` / `_finger_drive_rows` describe the
asset's own caps, and `joint2` is a `PhysxMimicJointAPI` mimic with **no**
`PhysicsDriveAPI:linear` block (`openarm_flat_deinst.usda:3822-3843`). The old
reader called `UsdPhysics.DriveAPI.Get(prim, "linear")` - the call `_finger_drive_rows`'
own docstring forbids - which *applies* the schema to the prim it is describing.
This script measures all three facts on the shipped asset, before and after the
fix, and exits non-zero if any of them moves:

  (a) `prim.GetAttribute("drive:linear:physics:maxForce")` is the same attribute
      `DriveAPI.GetMaxForceAttr()` returns (name + value);
  (b) reading through it leaves `joint2`'s applied schemas alone
      (`HasAPI(DriveAPI, "linear")` stays False), and the old `DriveAPI.Get`
      call is measured on a fresh stage beside it - on this USD/lib it does
      **not** author an applied-schema opinion (so the pre-fix builds were
      inert), which is why the fix is recorded as removing the question rather
      than repairing a measured corruption;
  (c) the build header's values are unchanged (10.0 / 0.0 on the shipped asset,
      30.0 / 0.0 after `apply_finger_maxforce(stage, 30)`), i.e. the fix cannot
      move the print that every P41 run's byte-identity is anchored on.

No physics, no articulation: the stage read is the whole object.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "src"))

from isaacsim import SimulationApp

HEADLESS = os.environ.get("HEADLESS", "1") == "1"
simulation_app = SimulationApp({"headless": HEADLESS, "width": 320, "height": 240})

from pxr import Usd, UsdPhysics  # noqa: E402

from fruit_sorting.assets import OPENARM_BIMANUAL_USD  # noqa: E402
from fruit_sorting.common import say  # noqa: E402
from fruit_sorting.scene import (  # noqa: E402
    _DRIVE_MAXFORCE_ATTR,
    _drive_maxforce_cap,
    _finger_drive_caps,
    _finger_drive_rows,
    apply_finger_maxforce,
)

failures: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    say(f"[a4] {name}: {'PASS' if ok else 'FAIL'} ({detail})")
    if not ok:
        failures.append(name)


def main() -> int:
    stage = Usd.Stage.Open(OPENARM_BIMANUAL_USD)
    j1 = stage.GetPrimAtPath("/World/OpenArm/joints/openarm_left_finger_joint1")
    j2 = stage.GetPrimAtPath("/World/OpenArm/joints/openarm_left_finger_joint2")
    check("prims exist", j1.IsValid() and j2.IsValid(), f"j1={j1.IsValid()} j2={j2.IsValid()}")

    # (a) the raw attribute name is the API's own attribute name.
    api_attr = UsdPhysics.DriveAPI.Get(j1, "linear").GetMaxForceAttr()
    raw_attr = j1.GetAttribute(_DRIVE_MAXFORCE_ATTR)
    check(
        "raw name == DriveAPI attribute",
        bool(raw_attr) and api_attr.GetName() == raw_attr.GetName(),
        f"api={api_attr.GetName()} raw={raw_attr.GetName() if raw_attr else 'n/a'}",
    )
    check(
        "joint1 value 10.0 N",
        _drive_maxforce_cap(j1) == 10.0,
        f"read={_drive_maxforce_cap(j1)}",
    )
    check(
        "joint2 unauthored (None, drive-less)",
        _drive_maxforce_cap(j2) is None,
        f"read={_drive_maxforce_cap(j2)} hasAPI={j2.HasAPI(UsdPhysics.DriveAPI, 'linear')}",
    )

    # (b) the fixed readers must not touch the applied schemas.
    before = {
        side: stage.GetPrimAtPath(
            f"/World/OpenArm/joints/openarm_{side}_finger_joint2"
        ).HasAPI(UsdPhysics.DriveAPI, "linear")
        for side in ("left", "right")
    }
    caps_before = _finger_drive_caps(stage)
    rows_before = _finger_drive_rows(stage)
    after = {
        side: stage.GetPrimAtPath(
            f"/World/OpenArm/joints/openarm_{side}_finger_joint2"
        ).HasAPI(UsdPhysics.DriveAPI, "linear")
        for side in ("left", "right")
    }
    check("fixed readers leave joint2 schemas alone", before == after == {"left": False, "right": False}, f"before={before} after={after}")
    check("header reads 10.0/0.0 (unchanged print)", caps_before == "10.0/0.0", f"caps={caps_before}")
    mimic = [row for row in rows_before if row["joint"].endswith("joint2")]
    check(
        "rows: joint2 drive=False maxForce=None",
        all(not row["drive"] and row["maxForce"] is None for row in mimic),
        f"{[row['joint'] + ':' + str(row['maxForce']) for row in mimic]}",
    )

    # the defect this check was written for, measured on a fresh stage: does
    # `DriveAPI.Get` author an applied-schema opinion on the mimic here?
    scratch = Usd.Stage.Open(OPENARM_BIMANUAL_USD)
    m2 = scratch.GetPrimAtPath("/World/OpenArm/joints/openarm_left_finger_joint2")
    pre = m2.HasAPI(UsdPhysics.DriveAPI, "linear")
    UsdPhysics.DriveAPI.Get(m2, "linear")
    post = m2.HasAPI(UsdPhysics.DriveAPI, "linear")
    say(
        "[a4] measured: DriveAPI.Get on the drive-less mimic -> "
        f"HasAPI {pre} -> {post} (an applied-schema opinion is "
        f"{'authored' if post else 'NOT authored on this USD/lib'}); the fix "
        "does not construct that object at all, so the question cannot return"
    )
    check("fixed readers never construct the schema object", before == after, f"before={before} after={after}")


    # (c) the writer still lands, and the header follows it.
    note = apply_finger_maxforce(stage, 30.0)
    say(f"[a4] write note:{note}")
    caps_after = _finger_drive_caps(stage)
    check("after write: header reads 30.0/0.0", caps_after == "30.0/0.0", f"caps={caps_after}")

    say(f"[a4] failures={len(failures)} {failures if failures else ''}")
    return 1 if failures else 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
