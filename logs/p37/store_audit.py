#!/usr/bin/env python3
"""P37 store audit - the park-collected rollout store against its own index.

    python3 logs/p37/store_audit.py datasets/rl_rollouts/p37_park \
        --parts datasets/rl_rollouts/p37_parts

The `scripts/106_index_audit.py` checks (every index row's file exists, `frames`
matches the npz, no unlisted file, no duplicate entry, no byte-identical
content) **plus** the fields 106 does not know: the RL bookkeeping
(`ok / carried-not-placed / no-grasp` per arm, states, rewards), the window count
the fine-tune's loader will see (`length - 16 - 1`, the `EpisodeStore`
convention), and the provenance chain the store must carry for a training run -
the merge manifest's shard md5s and each shard's `manifest.json`
(`arm_park`, `checkpoint_md5`, `tasks_md5`, `belt_speed`, `camera_res`,
`trigger`, `policy_seed`).

Exit 1 on a bookkeeping failure (an index row with no file, a stale `frames`, an
unlisted file, a duplicate entry, a missing `arm_park`, a shard whose manifest
names a different checkpoint or park). Report-only numbers are printed, not
gated: the composition, the per-class table, the window count.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import statistics
import sys

import numpy as np

ACTION_HORIZON = 16
OBS_HORIZON = 2


def md5(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            return hashlib.md5(fh.read()).hexdigest()
    except OSError:
        return ""


def rows_of(path: str) -> int:
    with np.load(path) as data:
        return int(data["action"].shape[0])


def windows_of(length: int) -> int:
    return max(0, length - ACTION_HORIZON - (OBS_HORIZON - 1))


def class_of(row: dict) -> str:
    if row.get("success") or row.get("placed"):
        return "ok"
    if not row.get("grasped"):
        return "no-grasp"
    return "carried-not-placed"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("store")
    ap.add_argument("--parts", default="", help="the shard dirs the merge consumed")
    ap.add_argument("--expect-park", default="back")
    args = ap.parse_args()

    root = args.store.rstrip("/")
    name = os.path.basename(root)
    problems: list[str] = []
    index_path = os.path.join(root, "index.json")
    if not os.path.exists(index_path):
        print(f"FAIL {root}: no index.json")
        return 1
    entries = json.load(open(index_path, encoding="utf-8"))
    files = sorted(f for f in os.listdir(root) if f.endswith(".npz"))
    listed = [e["file"] for e in entries]

    print(f"store {name}: entries={len(entries)} files={len(files)}")

    # --- 106-style bookkeeping -------------------------------------------- #
    dup_entries = sorted({f for f in listed if listed.count(f) > 1})
    missing = [f for f in listed if not os.path.exists(os.path.join(root, f))]
    unlisted = [f for f in files if f not in listed]
    stale, lengths = [], {}
    for entry in entries:
        path = os.path.join(root, entry["file"])
        if not os.path.exists(path):
            continue
        rows = rows_of(path)
        lengths[entry["file"]] = rows
        if int(entry.get("frames", -1)) != rows:
            stale.append((entry["file"], entry.get("frames"), rows))
    by_size: dict[int, list[str]] = collections.defaultdict(list)
    for f in files:
        by_size[os.path.getsize(os.path.join(root, f))].append(f)
    content_dupes = []
    for same in by_size.values():
        if len(same) < 2:
            continue
        groups: dict[str, list[str]] = collections.defaultdict(list)
        for f in same:
            groups[md5(os.path.join(root, f))].append(f)
        content_dupes.extend(g for g in groups.values() if len(g) > 1)
    for label, items in (
        ("duplicate index entries", dup_entries),
        ("index rows with no file", missing),
        ("files not in the index", unlisted),
        ("frames mismatch", [f"{f}: index={a} file={b}" for f, a, b in stale]),
        ("byte-identical content", content_dupes),
    ):
        if items:
            problems.append(f"{label}: {items[:6]}{' ...' if len(items) > 6 else ''}")
    print(f"  bookkeeping: {'OK' if not problems else 'FAIL'} "
          f"(entries {len(entries)} / files {len(files)}, "
          f"index_frames {sum(int(e.get('frames', 0)) for e in entries)}, "
          f"file_frames {sum(lengths.values())})")

    # --- the training windows ---------------------------------------------- #
    windows = sum(windows_of(n) for n in lengths.values())
    frames = sorted(lengths.values())
    print(f"  windows={windows}  frames/episode min/median/max="
          f"{frames[0]}/{int(statistics.median(frames))}/{frames[-1]}")

    # --- the class and composition table ----------------------------------- #
    per_arm: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    species: collections.Counter = collections.Counter()
    grades: collections.Counter = collections.Counter()
    diameters: list[float] = []
    states = collections.Counter()
    rewards: list[float] = []
    for entry in entries:
        cls = class_of(entry)
        per_arm[entry.get("arm", "?")][cls] += 1
        per_arm[entry.get("arm", "?")]["n"] += 1
        species[entry.get("category", "?")] += 1
        grades[entry.get("grade", "?")] += 1
        diameters.append(float(entry.get("diameter", 0.0)))
        states[f"{entry.get('success')}/{entry.get('grasped')}/{entry.get('placed')}"] += 1
        rewards.append(float(entry.get("reward", 0.0)))
    ok = sum(c["ok"] for c in per_arm.values())
    n = sum(c["n"] for c in per_arm.values())
    carried = sum(c["carried-not-placed"] for c in per_arm.values())
    nograsp = sum(c["no-grasp"] for c in per_arm.values())
    print(f"  classes (pooled n={n}): ok={ok} carried-not-placed={carried} no-grasp={nograsp}"
          f"  success={ok / n:.1%}")
    for arm in sorted(per_arm):
        c = per_arm[arm]
        print(f"    {arm:5s} n={c['n']:3d}  ok={c['ok']:3d} "
              f"carried-not-placed={c['carried-not-placed']:3d} no-grasp={c['no-grasp']:3d} "
              f"({c['ok'] / c['n']:.1%} ok)")
    print(f"  grades {dict(grades)}")
    print(f"  species {dict(species)}")
    if diameters:
        print(f"  diameter cm min/median/max = {min(diameters) * 100:.2f}/"
              f"{statistics.median(diameters) * 100:.2f}/{max(diameters) * 100:.2f}")
    print(f"  (success/grasped/placed) states {dict(states)}")
    print(f"  reward: mean {statistics.mean(rewards):.3f}, 0.0 count "
          f"{sum(1 for r in rewards if r == 0.0)}")

    # --- provenance --------------------------------------------------------- #
    print("  provenance:")
    merge_path = os.path.join(root, "merge_manifest.json")
    merged_eps = merged_ok = None
    if os.path.exists(merge_path):
        merge = json.load(open(merge_path, encoding="utf-8"))
        merged_eps = int(merge.get("episodes", -1))
        merged_ok = int(merge.get("successes", -1))
        print(f"    merge_manifest: kind={merge.get('kind')} episodes={merged_eps} "
              f"successes={merged_ok} inputs={len(merge.get('inputs', []))}")
        for item in merge.get("inputs", []):
            print(f"      - {os.path.basename(item.get('dir', ''))}: "
                  f"episodes={item.get('episodes')} index_md5={item.get('index_md5')}")
        if merged_eps != len(entries):
            problems.append(f"merge_manifest episodes {merged_eps} != index {len(entries)}")
        if merged_ok is not None and merged_ok != ok:
            problems.append(f"merge_manifest successes {merged_ok} != index ok {ok}")
    else:
        print("    raw shard: no merge_manifest.json (a shard dir of a run)")

    manifests: list[tuple[str, str]] = []
    own = os.path.join(root, "manifest.json")
    if os.path.exists(own):
        manifests.append(("(own)", own))
    for shard in sorted({str(e["shard"]) for e in entries if e.get("shard")}):
        candidates = [
            os.path.join(shard, "manifest.json"),
            os.path.join(os.path.dirname(root), shard, "manifest.json"),
            os.path.join(args.parts, shard, "manifest.json") if args.parts else "",
        ]
        path = next((p for p in candidates if p and os.path.exists(p)), None)
        if path is None:
            problems.append(f"shard manifest not found for {shard}")
            continue
        manifests.append((shard, path))

    parks = collections.Counter()
    checkpoint_md5s = collections.Counter()
    tasks_md5s = collections.Counter()
    belt = collections.Counter()
    cam = collections.Counter()
    trigger = collections.Counter()
    parks_sides: dict[str, list] = {}
    for label, path in manifests:
        man = json.load(open(path, encoding="utf-8"))
        park = man.get("arm_park") or {}
        parks[str(park.get("name") or "none")] += 1
        parks_sides[label] = list(park.get("sides") or [])
        checkpoint_md5s[str(man.get("checkpoint_md5", ""))[:8]] += 1
        tasks_md5s[str(man.get("tasks_md5", ""))[:8]] += 1
        belt[str(man.get("belt_speed", ""))] += 1
        cam[str(man.get("camera_res", ""))] += 1
        trig = man.get("trigger") or {}
        trigger[f"{trig.get('mode')}/lead={trig.get('lead')}/lat={trig.get('lateral')}"
                f"/acq={trig.get('acq')}/frame={trig.get('frame')}"] += 1
        print(f"    {label}: park={park.get('name')} sides={park.get('sides')} "
              f"ckpt={str(man.get('checkpoint_md5'))[:8]} tasks={str(man.get('tasks_md5'))[:8]} "
              f"belt={man.get('belt_speed')} cam={man.get('camera_res')} "
              f"policy_seed={man.get('policy_seed')!r} trigger={trig.get('mode')} "
              f"index_md5={md5(os.path.join(os.path.dirname(path), 'index.json'))}")
        if park.get("name") != args.expect_park:
            problems.append(f"{label}: manifest arm_park={park.get('name')!r} "
                            f"!= {args.expect_park!r}")
    if not manifests:
        problems.append("no manifest.json in the store or its shards")
    print(f"    parks {dict(parks)} sides {parks_sides}  belt {dict(belt)}  camera {dict(cam)}")
    print(f"    checkpoint md5 {dict(checkpoint_md5s)}")
    print(f"    tasks.py md5 {dict(tasks_md5s)}")
    print(f"    trigger {dict(trigger)}")

    print()
    if problems:
        print("FAIL:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("OK: the store's index, files, class counts and provenance agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
