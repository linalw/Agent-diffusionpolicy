#!/usr/bin/env python3
"""P97: the shipped scenario's shard manifest, without a collection run.

    scripts/run.sh logs/p97/manifest_probe.py

P97 PREREG §6: the acceptance is a scripted run and writes no manifest, so the
shard manifest is exercised directly through the **same** `write_manifest` the
collector calls (`scripts/40_collect_demos.py`), with the shipped config and the
unset environment. It prints the three `collection.prepose_clear*` keys and the
two blocks a store also needs (`scene`, `supply.band`), and writes
`logs/p97/shard_manifest_probe.json` for the record.

Run under the simulator's python: `fruit_sorting.assets` imports `isaacsim`
(this is the P72 `manifest_probe.py` pattern). Read-only beyond the probe file.
"""

import importlib.util
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

spec = importlib.util.spec_from_file_location(
    "collect40", os.path.join(ROOT, "scripts", "40_collect_demos.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from fruit_sorting.assets import SceneConfig  # noqa: E402

out = "/tmp/p97_manifest"
os.makedirs(out, exist_ok=True)
mod.write_manifest(out, SceneConfig())
with open(os.path.join(out, "manifest.json"), encoding="utf-8") as fh:
    manifest = json.load(fh)
shutil.copyfile(os.path.join(out, "manifest.json"),
                os.path.join(ROOT, "logs", "p97", "shard_manifest_probe.json"))

coll = manifest.get("collection") or {}
summary = {
    "collection.prepose_clear": coll.get("prepose_clear"),
    "collection.prepose_clear_defaulted": coll.get("prepose_clear_defaulted"),
    "collection.prepose_clear_z": coll.get("prepose_clear_z"),
    "collection.mode": coll.get("mode"),
    "collection.biarm_twoline_resolved": coll.get("biarm_twoline_resolved"),
    "scene": manifest.get("scene"),
    "supply.band": (manifest.get("supply") or {}).get("band"),
    "physics.release": (manifest.get("physics") or {}).get("release"),
}
print(json.dumps(summary, indent=2, sort_keys=True))
