#!/usr/bin/env python3
"""P125 report: the three-lane store, the fine-tune and the canary A/B.

    python3 logs/p125/p125_report.py --store
    python3 logs/p125/p125_report.py --check

Reads each `logs/p125/canary_{A,B}_{i}.log` with the *same* classification
`scripts/accept_policy.sh` uses (grip loss / grasped-not-placed with empty notes
/ unexpected), so the pre-registered P2 clause is judged by the gate's own rule.
`--check` exits 1 unless P1/P2 pass (the bar is in `logs/p125/PREREG.md`).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#: `P125_LOG_DIR` lets the parser be exercised on another batch's logs (the
#: P124 canaries were used as the parser's own smoke before this batch ran).
LOGS = os.environ.get("P125_LOG_DIR", os.path.join(ROOT, "logs", "p125"))
GRIP = "fruit did not follow the gripper"


def read_sample(path: str):
    text = open(path, encoding="utf-8", errors="ignore").read()
    targets = {}
    for line in text.splitlines():
        m = re.search(r"\[eval\] episode (\d+): (\w+) grade=(\w+) d=([\d.]+)cm lane=(\d+)", line)
        if m:
            targets[int(m.group(1))] = (m.group(2), float(m.group(4)), int(m.group(5)))
    results = []
    for line in text.splitlines():
        m = re.search(r"\[eval\] episode (\d+): hybrid grasped=(\w+) placed=(\w+) .*notes=(\[.*\])", line)
        if not m:
            continue
        index = int(m.group(1))
        grasped = m.group(2) == "True"
        placed = m.group(3) == "True"
        notes = m.group(4)
        category, diameter, lane = targets.get(index, ("?", 0.0, -1))
        if placed:
            verdict = "ok"
        elif GRIP in notes:
            verdict = "grip loss"
        elif grasped and notes == "[]":
            verdict = "grasped, not placed"
        else:
            verdict = "unexpected"
        results.append((index, category, diameter, lane, verdict, notes))
    summary = re.search(r"policy success (\d+)/(\d+)", text)
    return results, (int(summary.group(1)), int(summary.group(2))) if summary else (0, 0)


def gate_log(path: str) -> str:
    gate = path[:-4] + ".gate"
    if not os.path.exists(gate):
        return ""
    text = open(gate, encoding="utf-8", errors="ignore").read()
    out = []
    for line in text.splitlines():
        if line.strip().startswith(("PASS:", "FAIL:", "  - ")) or "rate:" in line or "failures:" in line:
            out.append(line.strip())
    return "\n".join(out)


def canary(check: bool) -> int:
    arms = {}
    for arm in ("A", "B", "C"):
        samples = sorted(glob.glob(os.path.join(LOGS, f"canary_{arm}_*.log")))
        samples = [p for p in samples if "_driver" not in p]
        rows = []
        for path in samples:
            results, (ok, total) = read_sample(path)
            if not total:
                continue
            counts = {}
            for row in results:
                counts[row[4]] = counts.get(row[4], 0) + 1
            rows.append({
                "path": path,
                "ok": ok,
                "total": total,
                "counts": counts,
                "unexpected": [r for r in results if r[4] == "unexpected"],
            })
        arms[arm] = rows

    print("=== the canary (three-lane scene, accept_policy.sh, 10 episodes/sample) ===")
    for arm in ("A", "B"):
        rows = arms[arm]
        if not rows:
            print(f"  arm {arm}: no samples")
            continue
        for row in rows:
            name = os.path.basename(row["path"])
            print(f"  {name:<22s} {row['ok']:2d}/{row['total']:<2d} "
                  f"{row['ok'] / row['total']:6.0%}  {row['counts']}")
        ok = sum(r["ok"] for r in rows)
        total = sum(r["total"] for r in rows)
        rates = [r["ok"] / r["total"] for r in rows]
        print(f"  arm {arm}: pooled {ok}/{total} = {ok / total:.1%}, "
              f"mean {statistics.mean(rates):.1%}, median {statistics.median(rates):.1%}, "
              f"range {min(rates):.0%}-{max(rates):.0%}")
        for row in rows:
            for r in row["unexpected"]:
                print(f"    UNEXPECTED {os.path.basename(row['path'])} #{r[0]} "
                      f"{r[1]} {r[2]:.1f}cm lane={r[3]} notes={r[5]}")

    print()
    print("=== the gate's own verdict per sample ===")
    for arm in ("A", "B", "C"):
        for row in arms[arm]:
            verdict = gate_log(row["path"]) or "(no .gate file)"
            print(f"  {os.path.basename(row['path'])}: {verdict}")

    if not (arms["A"] and arms["B"]):
        print("\nPENDING: both arms need samples")
        return 0 if not check else 1

    ok_a = sum(r["ok"] for r in arms["A"])
    tot_a = sum(r["total"] for r in arms["A"])
    ok_b = sum(r["ok"] for r in arms["B"])
    tot_b = sum(r["total"] for r in arms["B"])
    rate_a = ok_a / tot_a
    rate_b = ok_b / tot_b
    unexpected_b = [r for row in arms["B"] for r in row["unexpected"]]
    enough = len(arms["A"]) >= 3 and len(arms["B"]) >= 3

    p1 = rate_b >= 0.80 and rate_b > rate_a
    p2 = not unexpected_b
    print()
    print("=== PREREG decision (logs/p125/PREREG.md section 4) ===")
    print(f"  P1 rate: pooled B {ok_b}/{tot_b} = {rate_b:.1%} >= 80.0% and > A {rate_a:.1%}"
          f" -> {'PASS' if p1 else 'FAIL'}")
    print(f"  P2 reasons: {len(unexpected_b)} unexpected failure(s) in B"
          f" -> {'PASS' if p2 else 'FAIL'}")
    print(f"  N: A {len(arms['A'])} sample(s), B {len(arms['B'])} sample(s)"
          f" -> {'complete' if enough else 'PENDING (needs 3 each)'}")
    verdict = "FLIP" if (p1 and p2 and enough) else "DO NOT FLIP"
    print(f"  verdict: {verdict}")
    if arms["C"]:
        ok_c = sum(r["ok"] for r in arms["C"])
        tot_c = sum(r["total"] for r in arms["C"])
        print()
        print("=== report only (PREREG_A2): the same-batch TWO-lane control ===")
        print(f"  C (2 lanes, moe_v12) pooled {ok_c}/{tot_c} = {ok_c / tot_c:.1%}; "
              f"A (3 lanes, moe_v12) {rate_a:.1%} -> "
              f"scene effect {100 * (rate_a - ok_c / tot_c):+.1f} points "
              f"(unresolvable at this N; the loop's recorded spread is 5-8/10)")
    if check:
        return 0 if verdict == "FLIP" else 1
    return 0


def store() -> int:
    path = os.path.join(ROOT, "datasets", "p125_three_lane")
    index_path = os.path.join(path, "index.json")
    if not os.path.exists(index_path):
        print(f"no merged store at {path}")
        return 1
    index = json.load(open(index_path, encoding="utf-8"))
    print(f"=== store {path}: {len(index)} episodes ===")
    from collections import Counter
    print(f"  arms: {dict(Counter(e['arm'] for e in index))}")
    print(f"  grades: {dict(Counter(e['grade'] for e in index))}")
    print(f"  success: {dict(Counter(e['success'] for e in index))}")
    merged = json.load(open(os.path.join(path, "manifest.json"), encoding="utf-8"))
    print(f"  merge inputs: {merged.get('inputs')}")
    print(f"  index_md5: {merged.get('index_md5')}")
    print()
    for shard in sorted(glob.glob(os.path.join(ROOT, "datasets", "p125_three_lane_*", "manifest.json"))):
        m = json.load(open(shard, encoding="utf-8"))
        scene = m.get("scene") or {}
        lanes = scene.get("output_lanes")
        print(f"  {os.path.basename(os.path.dirname(shard))}: "
              f"target={m.get('episodes_target')} seed={m.get('seed')} "
              f"camera={m.get('camera_res')} "
              f"lanes={len(lanes) if lanes is not None else 'MISSING'} "
              f"two_line={m.get('collection', {}).get('biarm_twoline_resolved')} "
              f"supply={m.get('supply', {}).get('band', {}).get('schedule')} "
              f"episodes={len(json.load(open(os.path.join(os.path.dirname(shard), 'index.json'), encoding='utf-8')))}")
        if lanes is not None:
            third = [lane for lane in lanes if int(lane.get("index", -1)) == 2]
            if third:
                print(f"      lane2 place={third[0]['place']} tray={third[0]['tray_center']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.store:
        return store()
    return canary(args.check)


if __name__ == "__main__":
    sys.exit(main())
