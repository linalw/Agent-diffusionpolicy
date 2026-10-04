"""Probe file-descriptor accounting inside Isaac Sim.

Answers two questions raised by the `Too many open files` crash:

  * what is `RLIMIT_NOFILE` for the Kit process itself, and
  * does the RTX/CUDA-interop path leak `/dev/nvidiactl` handles per frame?

    $ISAAC_SIM_DIR/python.sh scripts/92_fd_probe.py
"""

from __future__ import annotations

import os
import resource

from isaacsim import SimulationApp


def snapshot() -> tuple[int, int, int]:
    fds = os.listdir("/proc/self/fd")
    nvidiactl = 0
    for entry in fds:
        try:
            if os.readlink(f"/proc/self/fd/{entry}").endswith("nvidiactl"):
                nvidiactl += 1
        except OSError:
            pass
    return len(fds), nvidiactl, len(os.listdir("/dev/shm"))


def main() -> int:
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    print(f"[probe] RLIMIT_NOFILE before SimulationApp: soft={soft} hard={hard}", flush=True)
    app = SimulationApp({"headless": True})

    import isaacsim.core.experimental.utils.app as app_utils

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    print(f"[probe] RLIMIT_NOFILE after SimulationApp: soft={soft} hard={hard}", flush=True)

    fds, nv, shm = snapshot()
    print(f"[probe] after boot: fds={fds} nvidiactl={nv} shm={shm}", flush=True)

    for chunk in (50, 50, 100, 100, 200):
        for _ in range(chunk):
            app_utils.update_app(steps=1)
        fds, nv, shm = snapshot()
        print(f"[probe] after {chunk} more update_app: fds={fds} nvidiactl={nv} shm={shm}", flush=True)

    app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
