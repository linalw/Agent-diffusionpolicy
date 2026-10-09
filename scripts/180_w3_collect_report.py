"""Report a W3 two-line collection shard (offline; log + index.json).

    python3 scripts/180_w3_collect_report.py datasets/v12w_s0 logs/w3/40_collect_twoline.log

Prints, from the collector log:

* attempts/successes per arm and per grade (the pure-routing purity check:
  left must be A-only, right B-only, C picked must be 0);
* the failure-reason histogram and the `no eligible fruit` (starvation) count;
* the inter-chunk and stall-guard lines (the stall guard prints only on a
  wedge, so their absence is the healthy state);

and from the shard's `index.json`:

* the saved episode count, per-arm/per-grade counts and the station labels
  (the collection's ground truth);
* the frame count and the mean episode length.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re

ATTEMPT = re.compile(
    r"\[collect\] two-line attempt (?P<n>\d+): (?P<fruit>\w+) grade=(?P<grade>\w+) "
    r"arm=(?P<arm>\w+) station_y=(?P<y>[+\-\d.]+) grasped=(?P<grasped>True|False) "
    r"placed=(?P<placed>True|False) lift=(?P<lift>[+\-\d.]+) notes=(?P<notes>\[.*\])"
)
RESULT = re.compile(
    r"\[biarm\] result (?P<arm>\w+) index=(?P<index>\d+) (?P<fruit>\w+) "
    r"grasped=(?P<grasped>True|False) placed=(?P<placed>True|False)"
)
SAVED = re.compile(r"saved .*episode_(?P<index>\d+)\.npz \((?P<frames>\d+) frames")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shard")
    parser.add_argument("log")
    args = parser.parse_args()

    attempts = collections.Counter()
    wins = collections.Counter()
    reasons = collections.Counter()
    grades = {"left": collections.Counter(), "right": collections.Counter()}
    starved = 0
    stalls: list[str] = []
    with open(args.log, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "no eligible fruit" in line:
                starved += 1
            if "[collect] STALL" in line:
                stalls.append(line.strip())
            found = ATTEMPT.search(line)
            if found:
                values = found.groupdict()
                attempts[values["arm"]] += 1
                grades[values["arm"]][values["grade"]] += 1
                if values["grasped"] == "True" and values["placed"] == "True":
                    wins[values["arm"]] += 1
                if values["grasped"] == "False":
                    reasons["grip loss (grasped=False)"] += 1
                elif values["placed"] == "False":
                    reasons["grasped, not placed"] += 1
                continue
            found = RESULT.search(line)
            if found:
                # Fallback for a collector whose attempt line was cut by a
                # stall; the result line still carries the attempt.
                values = found.groupdict()
                attempts.setdefault(values["arm"], 0)
    print(f"== {args.log}: attempts={sum(attempts.values())} starved-slots={starved}")
    for arm in ("left", "right"):
        grade_text = ", ".join(f"{g}={n}" for g, n in sorted(grades[arm].items())) or "-"
        print(
            f"   {arm:<5}: {wins[arm]}/{attempts[arm]} placed; grades {grade_text}"
        )
    c_picked = grades["left"].get("C", 0) + grades["right"].get("C", 0)
    print(f"   C picked={c_picked} (pure routing requires 0)")
    if reasons:
        print("   failure reasons: " + ", ".join(f"{k}={v}" for k, v in reasons.items()))

    index_path = os.path.join(args.shard, "index.json")
    if os.path.exists(index_path):
        entries = json.load(open(index_path, encoding="utf-8"))
        per_arm = collections.Counter(e.get("arm") for e in entries)
        per_grade = collections.Counter(e.get("grade") for e in entries)
        frames = [int(e.get("frames", 0)) for e in entries]
        stations = sorted({float(e.get("station_y", 0.0)) for e in entries})
        print(
            f"   index: {len(entries)} episodes, per arm {dict(per_arm)}, "
            f"per grade {dict(per_grade)}, station labels {stations}, "
            f"frames {sum(frames)} (mean {sum(frames) / max(1, len(frames)):.0f})"
        )
        missing = [e["file"] for e in entries if not os.path.exists(os.path.join(args.shard, e["file"]))]
        if missing:
            print(f"   index lists {len(missing)} missing files")
    else:
        print("   index: (none yet)")
    if stalls:
        print("   STALL GUARD FIRED:")
        for line in stalls:
            print(f"     {line}")
    else:
        print("   stall guard: not fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
