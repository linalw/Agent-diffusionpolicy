#!/usr/bin/env python3
"""P188: the authored finger plate's width, static (P66's instrument, no physics).

    FRUIT_FINGER_TIP_DELTA=0 FRUIT_FINGER_PAD_WIDE=0.078 scripts/run.sh logs/p188_probe.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from isaacsim import SimulationApp

from fruit_sorting.fdlimit import raise_fd_limit

raise_fd_limit()
simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

import isaacsim.core.experimental.utils.app as app_utils  # noqa: E402
from fruit_sorting.assets import SceneConfig  # noqa: E402
from fruit_sorting.common import install_failure_handler, say  # noqa: E402
from fruit_sorting.scene import SortingScene  # noqa: E402

install_failure_handler("p188_probe")


def main() -> int:
    cfg = SceneConfig()
    scene = SortingScene(cfg).build(parts=("robot",))
    say(f"[p188] tip_delta={os.environ.get('FRUIT_FINGER_TIP_DELTA','')!r} "
        f"pad_wide={os.environ.get('FRUIT_FINGER_PAD_WIDE','0')!r}")
    app_utils.pause()
    say("DONE")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
