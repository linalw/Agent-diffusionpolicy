"""Check every dataset's `index.json` against the `.npz` files on disk.

    python3 scripts/106_index_audit.py            # audit
    python3 scripts/106_index_audit.py --repair   # rewrite the frames, drop superseded entries

Why this exists. `EpisodeRecorder.save` names a file from the episode index and
*appends* an index entry, so a collector that is restarted onto an existing
output directory leaves two entries pointing at one file: the older entry
describes content that has since been overwritten. `scripts/41_merge_demos.py`
then copies each entry's file and keeps that entry's recorded `frames`, so the
stale count propagates into the merged dataset. The training logs' window counts
and the documents' data sizes were both off by a few percent because of it
(25,867 training windows vs the 26,838 frames the index claimed - see the
WORKLOG audit).

The metadata that matters for training (category, grade, arm, diameter) exists
only in the index, so `--repair` never invents it: it keeps the *last* entry for
each file, which is the one that matches what is on disk, and rewrites `frames`
from the file itself. Everything it drops or changes is printed.
"""

from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import json
import os

import numpy as np


def rows_of(path: str) -> int:
    with np.load(path) as data:
        return int(data["action"].shape[0])


def windows_of(path: str, obs_horizon: int = 2, action_horizon: int = 16) -> int:
    """Training windows this episode contributes, exactly as the loader counts them.

    `DemonstrationDataset` walks `range(obs_horizon - 1, length - action_horizon)`
    per episode, so the count is `length - action_horizon - (obs_horizon - 1)`.
    Reported per dataset so it can be checked against what a training log printed
    (e.g. `logs/335`: 64 episodes, 25,867 windows).
    """
    with np.load(path, mmap_mode="r") as data:
        length = int(data["action"].shape[0])
    return max(0, length - action_horizon - (obs_horizon - 1))


def content_hash(path: str) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duplicate_content(directory: str, files: list[str]) -> list[list[str]]:
    """Groups of `.npz` files that are byte-identical.

    Different from a duplicate *index entry*: these are distinct episode files
    with the same content, which is what a merge produces when a shard's stale
    index lists one file twice under two names.
    """
    groups: dict[str, list[str]] = collections.defaultdict(list)
    # Group by size first: distinct episodes almost never share a byte size, so
    # only the few same-size candidates have to be hashed.
    by_size: dict[int, list[str]] = collections.defaultdict(list)
    for path in files:
        by_size[os.path.getsize(path)].append(path)
    for same_size in by_size.values():
        if len(same_size) < 2:
            continue
        for path in same_size:
            groups[content_hash(path)].append(os.path.basename(path))
    return [group for group in groups.values() if len(group) > 1]


def audit(
    root: str, hash_content: bool = True
) -> tuple[list[str], list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    report: list[str] = []
    for directory in sorted(glob.glob(os.path.join(root, "*"))):
        if not os.path.isdir(directory):
            continue
        files = sorted(glob.glob(os.path.join(directory, "*.npz")))
        index_path = os.path.join(directory, "index.json")
        if not files and not os.path.exists(index_path):
            continue
        name = os.path.basename(directory.rstrip("/"))
        if not os.path.exists(index_path):
            report.append(f"{name:20s} {len(files):3d} files, no index.json")
            continue
        entries = json.load(open(index_path, encoding="utf-8"))
        listed = [e["file"] for e in entries]
        duplicates = sorted({f for f in listed if listed.count(f) > 1})
        missing = [f for f in listed if not os.path.exists(os.path.join(directory, f))]
        unlisted = [os.path.basename(f) for f in files if os.path.basename(f) not in listed]
        stale = []
        for entry in entries:
            path = os.path.join(directory, entry["file"])
            if not os.path.exists(path):
                continue
            actual = rows_of(path)
            if int(entry.get("frames", -1)) != actual:
                stale.append((entry["file"], entry.get("frames"), actual))
        index_frames = sum(int(e.get("frames", 0)) for e in entries)
        file_frames = sum(rows_of(f) for f in files)
        windows = sum(windows_of(f) for f in files)
        content_dupes = duplicate_content(directory, files) if (files and hash_content) else []
        ok = not (duplicates or missing or unlisted or stale) and len(entries) == len(files)
        report.append(
            f"{name:20s} entries={len(entries):3d} files={len(files):3d} "
            f"index_frames={index_frames:6d} file_frames={file_frames:6d} "
            f"windows={windows:6d} "
            f"unique_content={len(files) - sum(len(g) - 1 for g in content_dupes):3d} "
            f"{'OK' if ok and not content_dupes else ('DUPLICATE CONTENT' if content_dupes and ok else 'MISMATCH')}"
        )
        for label, items in (
            ("duplicate file entries", duplicates),
            ("entries with no file", missing),
            ("files not in the index", unlisted),
            ("frames mismatch", [f"{f}: index={a} file={b}" for f, a, b in stale]),
        ):
            if items:
                problems.append(f"{name}: {label}: {items[:6]}{' ...' if len(items) > 6 else ''}")
        if content_dupes:
            # Reported as a *warning*, not a bookkeeping failure: the shipped
            # datasets contain duplicates that the checkpoints were trained on, and
            # removing them now would make those runs unreproducible (see WORKLOG).
            # `--strict` turns them into a failure, which is what a release gate
            # that only accepts freshly merged data should use.
            warnings.append(
                f"{name}: {len(content_dupes)} group(s) of byte-identical episodes "
                f"(e.g. {content_dupes[0][:4]}) - the merge copied one file under two names"
            )
    return report, problems, warnings


def repair(root: str, dry_run: bool = False) -> list[str]:
    changes: list[str] = []
    for directory in sorted(glob.glob(os.path.join(root, "*"))):
        index_path = os.path.join(directory, "index.json")
        if not os.path.exists(index_path):
            continue
        name = os.path.basename(directory.rstrip("/"))
        entries = json.load(open(index_path, encoding="utf-8"))
        # Keep the last entry for each file: it is the one whose recorded content
        # matches what the file holds now.
        seen: dict[str, int] = {}
        for position, entry in enumerate(entries):
            seen[entry["file"]] = position
        kept = [entry for position, entry in enumerate(entries) if seen[entry["file"]] == position]
        dropped = len(entries) - len(kept)
        rewritten = 0
        for entry in kept:
            path = os.path.join(directory, entry["file"])
            if not os.path.exists(path):
                continue
            actual = rows_of(path)
            if int(entry.get("frames", -1)) != actual:
                entry["frames"] = actual
                rewritten += 1
        if dropped or rewritten:
            changes.append(
                f"{name}: dropped {dropped} superseded entr(y/ies), "
                f"rewrote {rewritten} frame count(s)"
            )
            if not dry_run:
                with open(index_path, "w", encoding="utf-8") as handle:
                    json.dump(kept, handle, indent=2)
    return changes


def dedupe(root: str, dry_run: bool = False) -> list[str]:
    """Move byte-identical episodes aside and drop them from the index.

    Non-destructive: the files are *moved* into `<dataset>/duplicates/`, so they
    can be moved back. Kept explicit rather than automatic because the shipped
    checkpoints were trained with the duplicates present.
    """
    changes: list[str] = []
    for directory in sorted(glob.glob(os.path.join(root, "*"))):
        index_path = os.path.join(directory, "index.json")
        if not os.path.exists(index_path):
            continue
        name = os.path.basename(directory.rstrip("/"))
        entries = json.load(open(index_path, encoding="utf-8"))
        seen: dict[str, str] = {}
        keep: list[dict] = []
        extra: list[str] = []
        for entry in entries:
            path = os.path.join(directory, entry["file"])
            if not os.path.exists(path):
                keep.append(entry)
                continue
            digest = content_hash(path)
            if digest in seen:
                extra.append(entry["file"])
                continue
            seen[digest] = entry["file"]
            keep.append(entry)
        if not extra:
            continue
        spare = os.path.join(directory, "duplicates")
        changes.append(f"{name}: {len(extra)} duplicate episode(s) -> {spare}/ ({extra[:4]})")
        if dry_run:
            continue
        os.makedirs(spare, exist_ok=True)
        for filename in extra:
            os.replace(os.path.join(directory, filename), os.path.join(spare, filename))
        with open(index_path, "w", encoding="utf-8") as handle:
            json.dump(keep, handle, indent=2)
    return changes


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="datasets")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="skip the content hashing (cheap, but cannot see duplicated episodes)",
    )
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help=(
            "move byte-identical episodes into <dataset>/duplicates/ and drop them "
            "from the index. Off by default: the shipped checkpoints were trained "
            "with those duplicates, so removing them changes the dataset"
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat byte-identical episodes as a failure (use for freshly merged data)",
    )
    args = parser.parse_args()

    if args.repair:
        changes = repair(args.root, dry_run=args.dry_run)
        for line in changes:
            print(f"  {'would fix' if args.dry_run else 'fixed'}: {line}")
        if not changes:
            print("  nothing to repair")

    if args.dedupe:
        for line in dedupe(args.root, dry_run=args.dry_run):
            print(f"  {'would dedupe' if args.dry_run else 'deduped'}: {line}")

    report, problems, warnings = audit(args.root, hash_content=not args.fast)
    print(f"{os.path.basename(args.root)}/*: {len(report)} dataset(s) with data or index")
    for line in report:
        print(f"  {line}")
    if warnings:
        print(f"WARNING: {len(warnings)} known data-quality issue(s)")
        for item in warnings:
            print(f"  - {item}")
        if args.strict:
            problems = problems + warnings
    if problems:
        print(f"MISMATCH: {len(problems)} problem(s)")
        for item in problems:
            print(f"  - {item}")
        return 1
    if warnings:
        print("OK: every index matches the files it describes (with the warnings above)")
    else:
        print("OK: every index matches the files it describes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
