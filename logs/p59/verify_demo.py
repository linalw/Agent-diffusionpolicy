#!/usr/bin/env python3
"""Re-check every line DEMO.md quotes, from the logs themselves.

    python3 logs/p59/verify_demo.py

Read-only: parses `logs/p59/p1/*.log`, `/tmp/p59_prof/.../manifest.json`,
`datasets/rl_rollouts/direct_none_seed77/manifest.json` and
`logs/p59/video_shipped/video.json`, asserts the pre-registered checks, and
prints one PASS/FAIL line per assertion. Exit 1 if any assertion fails, so the
phase-1 gate can be re-run after any tree move.
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P1 = os.path.join(ROOT, "logs", "p59", "p1")
PROFILE_ROW = (
    "[supply] direct profile: cadence=on(default) band=on(4)(default) feed=on(default)"
)
PRE58_ROW = (
    "[supply] direct profile: cadence=off(explicit) band=off(4)(explicit) feed=off(explicit)"
)

failures: list[str] = []
checks = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)


def text(log: str) -> str:
    with open(os.path.join(P1, log), encoding="utf-8", errors="replace") as fh:
        return fh.read()


def manifest(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["supply"]


print("check 1 - the profile is what runs (01_profile.log)")
t1 = text("01_profile.log")
check("profile row is byte-exact", PROFILE_ROW in t1)
check("not one member reads (explicit)", "explicit" not in t1)
check("park=back(default)", "park=back(default)" in t1)
check("acq=on(", "acq=on(" in t1)
m1 = manifest("/tmp/p59_prof/direct_none_seed77/manifest.json")
check("manifest cadence/band/feed true",
      m1["cadence"] and m1["band_interlock"] and m1["direct_feed"])
check("manifest band_max 4 / continuous 0", m1["band_max"] == 4 and m1["continuous"] == 0)
check("manifest defaulted all true", all(m1["defaulted"].values()))
store = "/tmp/p59_prof/direct_none_seed77"
check("recorded store has 2 npz + index",
      sorted(f for f in os.listdir(store) if f.endswith(".npz")) ==
      ["rollout_00000.npz", "rollout_00001.npz"] and "index.json" in os.listdir(store))

print("check 2 - the pre-P58 recipe (02_pre58_recipe.log)")
t2 = text("02_pre58_recipe.log")
t2b = text("02b_pre58_manifest.log")
check("profile row is off(explicit) x3", PRE58_ROW in t2)
check("re-run (preserving --out) reads the same row", PRE58_ROW in t2b)
#: The default scratch out dir is shared with every non-`--out` run, so check 3
#: overwrote check 2's manifest; 2b is the same command with a private `--out`.
m2 = manifest("/tmp/p59_pre58/direct_none_seed77/manifest.json")
check("manifest members false",
      not m2["cadence"] and not m2["band_interlock"] and not m2["direct_feed"])
check("their defaulted flags false",
      not m2["defaulted"]["cadence"] and not m2["defaulted"]["band_interlock"]
      and not m2["defaulted"]["feed"])
check("band_max exception is the predicted inert one (4 / true, keyed to BAND_MAX)",
      m2["band_max"] == 4 and m2["defaulted"]["band_max"] is True)
m = re.search(r"\[bed-sel\] attempt 0 .*on_belt=(\d+) .*window=(\d+)", t2)
mb = re.search(r"\[bed-sel\] attempt 0 .*on_belt=(\d+) .*window=(\d+)", t2b)
check("pre-profile sample recorded (both runs agree)",
      bool(m) and bool(mb) and (m.group(1), m.group(2)) == (mb.group(1), mb.group(2)),
      f"on_belt={m.group(1)} window={m.group(2)}" if m else "")

print("check 3 - --continuous 10 is explicit and pick-level (03_continuous10.log)")
t3 = text("03_continuous10.log")
check("cont enabled picks_target=10", "[cont] enabled: picks_target=10" in t3)
rows = re.findall(r"\[rl\] episode (\d+): \w+ d=.*? success=(\w+) grasped=(\w+) placed=(\w+)",
                  t3)
check("10 per-pick outcome rows", len(rows) == 10, f"n={len(rows)}")
transitions = len(re.findall(r"\[cont\] pick \d+/10:", t3))
check("9 [cont] pick transitions (pick 1 has none by construction)",
      transitions == 9, f"n={transitions}")
check("pick-level 'picks placed' line",
      bool(re.search(r"\[rl\] picks placed \d+/10 \(continuous mode", t3)))
check("summary is not 0/1", "rollout success 0/1" not in t3)
placed = sum(1 for r in rows if r[3] == "True")
succ = sum(1 for r in rows if r[1] == "True")
check("per-pick success rows == placed rows", succ == placed == 7, f"success={succ} placed={placed}")
check("summary agrees with the rows",
      f"[rl] picks placed {placed}/10" in t3 and f"rollout success {placed}/10" in t3)

print("check 4 - the continuous video at the shipped profile (04_video_shipped.log)")
t4 = text("04_video_shipped.log")
check("profile row is the shipped one", PROFILE_ROW in t4)
check("no waiting/no candidate lines",
      "waiting for a candidate" not in t4 and "no candidate on the belt" not in t4)
rows4 = re.findall(r"\[rl\] episode (\d+): (\w+) d=.*? success=(\w+) grasped=\w+ placed=(\w+)", t4)
check("8 per-pick outcome rows", len(rows4) == 8, f"n={len(rows4)}")
gaps = re.search(r"\[cont\] episode \d+: picks=(\d+)/(\d+) placed=(\d+) .*gap_ticks=([0-9.]+) gaps=\[([0-9, ]+)\]", t4)
check("cont episode summary present", bool(gaps), gaps.group(0)[:80] if gaps else "")
if gaps:
    gl = [int(x) for x in gaps.group(5).split(",")]
    check("gap classes are {50, 80} only", set(gl) <= {50, 80} and len(gl) == 7,
          f"gaps={gl}")
    check("picks placed agrees with the rows",
          int(gaps.group(3)) == sum(1 for r in rows4 if r[3] == "True") == 6)
windows = [int(w) for w in re.findall(r"\[bed-sel\] attempt \d+ .*window=(\d+)", t4)]
check("catchable window never 0 across the 8 selections",
      len(windows) == 8 and min(windows) >= 2, f"window={windows}")
on_belt = [int(w) for w in re.findall(r"\[bed-sel\] attempt \d+ .*on_belt=(\d+)", t4)]
check("belt population grows from 4 to 11-14", on_belt[0] == 4 and min(on_belt[1:]) >= 11,
      f"on_belt={on_belt}")

vid = json.load(open(os.path.join(ROOT, "logs/p59/video_shipped/video.json")))
want = {"observer.mp4", "head.mp4", "gripper.mp4", "side_by_side.mp4"}
check("four mp4s written", want <= set(vid["videos"]))
check("all clips are the same 1686-frame clip",
      {v["frames"] for v in vid["videos"].values()} == {1686})
check("video.json records one episode (the last pick) - the 121 limitation",
      len(vid["episodes"]) == 1 and vid["episodes"][0]["category"] == "orange")

print()
if failures:
    print(f"FAIL: {len(failures)}/{checks} assertion(s) failed: {failures}")
    sys.exit(1)
print(f"OK: {checks}/{checks} assertions PASS")
