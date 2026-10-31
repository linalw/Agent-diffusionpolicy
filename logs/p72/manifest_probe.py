import importlib.util, json, os, sys
sys.path.insert(0, "src")
spec = importlib.util.spec_from_file_location("collect40", "scripts/40_collect_demos.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
from fruit_sorting.assets import SceneConfig

for tag, cfg in (("shipped", SceneConfig()),
                 ("prep71", SceneConfig(output_rails="both"))):
    out = f"/tmp/p72_manifest_{tag}"
    os.makedirs(out, exist_ok=True)
    mod.write_manifest(out, cfg)
    with open(os.path.join(out, "manifest.json")) as fh:
        m = json.load(fh)
    print(tag, "->", json.dumps(m.get("scene"), sort_keys=True))
