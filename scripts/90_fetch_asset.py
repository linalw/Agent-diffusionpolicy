"""Mirror the OpenArm asset tree locally, keeping its relative layout.

The robot's finger links are instanced and their collision meshes live in an
instance proxy, so nothing can be authored onto them at runtime (see WORKLOG
2026-09-26/27). The only way to give the gripper real fingertips is to modify the
asset itself, which first means having it on disk.

    $ISAAC_SIM_DIR/python.sh scripts/90_fetch_asset.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from urllib.parse import urljoin

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True, "width": 320, "height": 240})

from pxr import Sdf, Usd

SRC_ROOT = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0/"
ENTRY = "Isaac/Robots/OpenArm/openarm_bimanual/openarm_bimanual.usd"
LOCAL_ROOT = "assets/openarm_local"


def say(msg: str) -> None:
    print(f"[fetch] {msg}", flush=True)


def download(url: str, path: str) -> bool:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return False
    result = subprocess.run(
        ["curl", "-sS", "-L", "--fail", "-o", path, url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        say(f"FAILED {url}: {result.stderr.strip()[:120]}")
        return False
    return True


def references(usd_path: str) -> list[str]:
    stage = Usd.Stage.Open(usd_path, Usd.Stage.LoadAll)
    if stage is None:
        return []
    found: set[str] = set()
    proxies = Usd.TraverseInstanceProxies(Usd.PrimAllPrimsPredicate)
    # Instance proxies matter: the arm's meshes and collision groups hang off an
    # instanced subtree, and a plain traversal (as in the first attempt) walks
    # straight past them - that mirror was 3 files and 52 KB.
    for prim in Usd.PrimRange(stage.GetPseudoRoot(), proxies):
        for key in ("references", "payload"):
            meta = prim.GetMetadata(key)
            if not meta:
                continue
            for item in meta.GetAddedOrExplicitItems():
                asset = str(item.assetPath)
                if asset and not asset.startswith("http"):
                    found.add(asset)
    return sorted(found)


def main() -> int:
    local_entry = os.path.join(LOCAL_ROOT, ENTRY)
    download(urljoin(SRC_ROOT, ENTRY), local_entry)
    pending = [local_entry]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        base_url = urljoin(SRC_ROOT, os.path.relpath(current, LOCAL_ROOT))
        base_dir = os.path.dirname(current)
        for rel in references(current):
            rel = rel.split("[")[0]  # strip any sublayer/prim suffixes
            target = os.path.normpath(os.path.join(base_dir, rel))
            url = urljoin(base_url, rel)
            new = download(url, target)
            say(f"{'new ' if new else 'have'} {rel}")
            pending.append(target)
    total = sum(len(files) for _r, _d, files in os.walk(LOCAL_ROOT))
    say(f"mirrored {total} files under {LOCAL_ROOT}; layers visited {len(seen)}")
    return 0


if __name__ == "__main__":
    code = main()
    simulation_app.close()
    raise SystemExit(code)
