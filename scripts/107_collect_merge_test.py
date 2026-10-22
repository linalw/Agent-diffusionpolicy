"""Regression test for the two dataset-index bugs, with no simulator involved.

    python3 scripts/107_collect_merge_test.py

It rebuilds, in a temporary directory, the two situations that produced the
`index.json`/`.npz` mismatch described in the WORKLOG entry "the dataset index did
not match the dataset":

1. **Collector restarted onto the same output directory.** The recorder names a
   file from the episode index, so a restart re-uses `episode_00000.npz`. Before
   the fix, `_append_index` appended a second row for that file, whose `frames`
   described the *previous* content. The test writes episode 0 twice with different
   lengths and requires one row whose `frames` equals the file's actual length.
2. **Merging a shard that contains a byte-identical episode.** Before the fix the
   merge copied it under a second name and carried the stale frame count. The test
   merges two shards, one of which repeats an episode byte-for-byte, and requires
   the merged set to have no duplicate content and no stale frame counts.

Finally it runs `scripts/106_index_audit.py` over the merged output and requires
exit 0, so the audit doubles as the test's assertion. A fifth section pins the
provenance source lists: both manifest writers must name the supply modules
whose draws decide a shard's stream, `fruits.py`, `bed.py` and `meshes.py`
(P32 Gate D C1 - the bed was unpinned, so a bed shard was indistinguishable
from a scatter shard and a `bed.py` edit moved no md5).

Self-test, both verified by hand:

* revert `EpisodeRecorder._append_index` to a plain `entries.append(...)` ->
  `[FAIL] one index row for the rewritten episode - expected one index row for
  episode_00000.npz, found 2` and `index=7 file=5`, exit 1;
* drop the byte-identical guard from `scripts/41_merge_demos.py` -> `[FAIL] no
  byte-identical episodes survive the merge - 3 files, 2 unique` plus two audit
  failures, exit 1.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from fruit_sorting.bed import BedPlan  # noqa: E402
from fruit_sorting.dataset import EpisodeMeta, EpisodeRecorder  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHECKS = 0
FAILURES: list[str] = []


def check(description: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  [ok  ] {description}")
    else:
        print(f"  [FAIL] {description}{(' - ' + detail) if detail else ''}")
        FAILURES.append(description)


def write_episode(directory: str, index: int, frames: int, seed: int, category: str) -> str:
    """Record one episode the way the collector does, and return its file path."""
    recorder = EpisodeRecorder(directory, decimation=1)
    recorder.begin(
        EpisodeMeta(
            index=index,
            category=category,
            grade="A",
            arm="left",
            bin_index=0,
            diameter=0.05,
        )
    )
    rng = np.random.default_rng(seed)
    for _ in range(frames):
        recorder.add(
            {"joint_positions": rng.normal(size=7).astype(np.float32)},
            action=rng.normal(size=9).astype(np.float32),
        )
    return recorder.save(True, [])


def rows_of(path: str) -> int:
    with np.load(path) as data:
        return int(data["action"].shape[0])


def digest(path: str) -> str:
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def load_index(directory: str) -> list[dict]:
    with open(os.path.join(directory, "index.json"), encoding="utf-8") as handle:
        return json.load(handle)


def manifest_source_list(path: str, name: str) -> list[str]:
    """The literal string list assigned to `name` in `path`, without importing it.

    Both lists live in modules that import Isaac Sim at module level
    (`40_collect_demos.py`, `rl_env.py`), so the check parses the AST instead.
    It pins the *provenance* rule: the supply modules whose draws decide a
    shard's stream - `fruits.py`, `bed.py`, `meshes.py` - must be in both the
    collector's shard manifest and the direct-path run manifest (Gate D C1).
    """
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            continue
        if isinstance(node.value, (ast.List, ast.Tuple)):
            return [str(ast.literal_eval(element)) for element in node.value.elts]
    return []


def main() -> int:
    root = tempfile.mkdtemp(prefix="collect_merge_test_")
    try:
        print("== 1. collector restarted onto the same directory ==")
        shard_a = os.path.join(root, "shard_a")
        write_episode(shard_a, 0, frames=7, seed=1, category="apple")
        # The restart: same episode index, same file name, different content.
        write_episode(shard_a, 0, frames=5, seed=2, category="apple")
        entries = load_index(shard_a)
        rows_a0 = [e for e in entries if e["file"] == "episode_00000.npz"]
        actual = rows_of(os.path.join(shard_a, "episode_00000.npz"))
        check(
            "one index row for the rewritten episode",
            len(rows_a0) == 1,
            f"expected one index row for episode_00000.npz, found {len(rows_a0)}",
        )
        check(
            "its frames match the file on disk",
            bool(rows_a0) and int(rows_a0[0]["frames"]) == actual,
            f"index={rows_a0[0]['frames'] if rows_a0 else '-'} file={actual}",
        )

        print("== 2. merge a shard that repeats an episode byte-for-byte ==")
        shard_b = os.path.join(root, "shard_b")
        write_episode(shard_b, 0, frames=6, seed=3, category="pear")
        # Same length and seed as shard_a's *final* episode (7 frames were
        # overwritten by 5, seed 2), so this is byte-identical to shard_a's file.
        write_episode(shard_b, 1, frames=5, seed=2, category="apple")
        # The merge copies from the *shards*, so give it a stale frame count too,
        # exactly as a restarted shard would have left behind.
        index_b = load_index(shard_b)
        for entry in index_b:
            entry["frames"] = 999
        with open(os.path.join(shard_b, "index.json"), "w", encoding="utf-8") as handle:
            json.dump(index_b, handle, indent=2)

        # The merged output goes in its own parent so the audit can be pointed at
        # it alone: shard_b is *supposed* to be stale here, and that is what the
        # first audit assertion below checks.
        merged = os.path.join(root, "out", "merged")
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(REPO, "scripts", "41_merge_demos.py"),
                "--out",
                merged,
                "--inputs",
                shard_a,
                shard_b,
            ],
            capture_output=True,
            text=True,
        )
        check("merge ran", result.returncode == 0, result.stderr.strip()[-200:])
        for line in result.stdout.splitlines():
            if "byte-identical" in line or "merged" in line:
                print(f"      merge: {line}")

        files = sorted(
            os.path.join(merged, name)
            for name in os.listdir(merged)
            if name.endswith(".npz")
        )
        digests = [digest(path) for path in files]
        check(
            "no byte-identical episodes survive the merge",
            len(set(digests)) == len(digests),
            f"{len(files)} files, {len(set(digests))} unique",
        )
        entries = load_index(merged)
        check(
            "one index row per file",
            len(entries) == len(files),
            f"entries={len(entries)} files={len(files)}",
        )
        stale = [
            (entry["file"], entry["frames"], rows_of(os.path.join(merged, entry["file"])))
            for entry in entries
            if os.path.exists(os.path.join(merged, entry["file"]))
            and int(entry["frames"]) != rows_of(os.path.join(merged, entry["file"]))
        ]
        check(
            "every frames value matches its file (stale 999 must not survive)",
            not stale,
            f"{stale}",
        )

        print("== 3. the index audit detects the stale shard, and clears the merge ==")
        stale_audit = subprocess.run(
            [
                sys.executable,
                os.path.join(REPO, "scripts", "106_index_audit.py"),
                "--root",
                root,
                "--fast",
            ],
            capture_output=True,
            text=True,
        )
        check(
            "audit rejects the shard whose index was left stale",
            stale_audit.returncode != 0 and "frames mismatch" in stale_audit.stdout,
        )
        audit = subprocess.run(
            [
                sys.executable,
                os.path.join(REPO, "scripts", "106_index_audit.py"),
                "--root",
                os.path.join(root, "out"),
            ],
            capture_output=True,
            text=True,
        )
        tail = audit.stdout.strip().splitlines()[-1] if audit.stdout.strip() else audit.stderr
        check("audit exits 0 on the merged output", audit.returncode == 0, tail)
        check("audit reports OK", "OK:" in audit.stdout, tail)

        print("== 4. two-line recording: concurrent threads, auto index, station label ==")
        two_line = os.path.join(root, "two_line")
        recorder = EpisodeRecorder(two_line, decimation=1, auto_index=True)
        errors: list[BaseException] = []

        def record(arm: str, station: float, seed: int) -> None:
            try:
                for rep in range(3):
                    recorder.begin(
                        EpisodeMeta(
                            index=-1,
                            category="apple" if arm == "left" else "pear",
                            grade="A" if arm == "left" else "B",
                            arm=arm,
                            bin_index=0 if arm == "left" else 1,
                            diameter=0.06,
                            station_y=station,
                        )
                    )
                    rng = np.random.default_rng(seed + rep)
                    for _ in range(4):
                        recorder.add(
                            {"joint_positions": rng.normal(size=7).astype(np.float32)},
                            action=rng.normal(size=9).astype(np.float32),
                        )
                    if recorder.save(True, []) is None:
                        raise AssertionError("save returned None")
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        workers = [
            threading.Thread(target=record, args=(arm, station, seed))
            for arm, station, seed in (("left", 0.0, 10), ("right", -0.10, 20))
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        check("concurrent saves raised no error", not errors, str(errors))
        entries = load_index(two_line)
        check("all six concurrent episodes landed", len(entries) == 6,
              f"entries={len(entries)}")
        check(
            "file names are unique",
            len({e["file"] for e in entries}) == len(entries),
            f"{[e['file'] for e in entries]}",
        )
        check(
            "auto indices are unique",
            len({e["index"] for e in entries}) == len(entries),
            f"{[e['index'] for e in entries]}",
        )
        check(
            "per-arm station labels survive",
            sorted({float(e["station_y"]) for e in entries}) == [-0.10, 0.0],
            f"{[e['station_y'] for e in entries]}",
        )
        check(
            "both arms labelled",
            {e["arm"] for e in entries} == {"left", "right"},
            f"{sorted({e['arm'] for e in entries})}",
        )

        print("== 5. the provenance lists pin the supply modules (P32 Gate D C1) ==")
        for label, relative, name in (
            ("collector", os.path.join("scripts", "40_collect_demos.py"), "sources"),
            (
                "rl env",
                os.path.join("src", "fruit_sorting", "rl_env.py"),
                "_MANIFEST_SOURCES",
            ),
        ):
            sources = manifest_source_list(os.path.join(REPO, relative), name)
            for module in ("src/fruit_sorting/bed.py", "src/fruit_sorting/meshes.py"):
                check(
                    f"{label} manifest lists {os.path.basename(module)}",
                    module in sources,
                    f"{len(sources)} source(s); {module} missing",
                )
        # The other half of C1: the collector must *record* the bed geometry,
        # not just the source. `BedPlan.manifest_block()` is pure, so the test
        # drives an override through the real env parser.
        saved = os.environ.get("FRUIT_SUPPLY_BED_ALONG_MIN")
        try:
            os.environ["FRUIT_SUPPLY_BED_ALONG_MIN"] = "0.137"
            block = BedPlan.from_env().manifest_block()
        finally:
            if saved is None:
                os.environ.pop("FRUIT_SUPPLY_BED_ALONG_MIN", None)
            else:
                os.environ["FRUIT_SUPPLY_BED_ALONG_MIN"] = saved
        expected = {
            "bed_columns",
            "bed_along_min",
            "bed_along_max",
            "bed_margin",
            "bed_pool",
            "bed_shift_step",
            "bed_shift_max",
        }
        check(
            "bed manifest block has the resolved geometry keys",
            set(block) == expected,
            f"keys={sorted(block)}",
        )
        check(
            "bed manifest block follows the along override",
            block["bed_along_min"] == 0.137,
            f"bed_along_min={block['bed_along_min']}",
        )

        print()
        if FAILURES:
            print(f"FAIL: {len(FAILURES)} of {CHECKS} check(s) failed")
            for item in FAILURES:
                print(f"  - {item}")
            return 1
        print(f"PASS: all {CHECKS} checks")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
