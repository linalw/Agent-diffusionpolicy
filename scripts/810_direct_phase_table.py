"""Direct-phase table from an `RL_ENV_DEBUG=1` rollout log (P4b1 step 1).

    python3 scripts/810_direct_phase_table.py logs/810_diag_moe_v10_debug.log

Parses the env's `[rl]   step=... finger=... |jaw-fruit|xy=... fruit=(...)
jaw=(...)` lines (printed every 25 applied actions and on every tick with
finger < 0.030) into a per-episode table:

* the closest jaw-fruit approach and the finger command there;
* the first tick the finger command crosses 0.030, with the distance then;
* the finger and distance at the last recorded tick (where the episode was at
  the timeout, if it timed out);
* the jaw's own drift: its y range over the episode.

The trace is instrumentation (a jaw link readback every 25 ticks), so it is
mechanism-only - never a rate.
"""

from __future__ import annotations

import argparse
import re

LINE = re.compile(
    r"step=(\d+) finger=([\d.]+) \|jaw-fruit\|xy=([\d.]+)cm "
    r"fruit=\(([-+0-9.]+),([-+0-9.]+),([-+0-9.]+)\) "
    r"jaw=\(([-+0-9.]+),([-+0-9.]+),([-+0-9.]+)\)"
)
EPISODE = re.compile(r"\[rl\] episode (\d+): (\w+) grade=(\w+) d=([\d.]+)cm bin=(-?\d) arm=(\w+)")
RESULT = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=[\d.]+cm bin=-?\d arm=(\w+) success=(\w+) "
    r"grasped=(\w+) placed=(\w+) ticks=(\d+) decision=(\d+)"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log")
    args = parser.parse_args()

    current = None
    episodes: list[dict] = []
    for line in open(args.log, encoding="utf-8", errors="replace"):
        start = EPISODE.search(line)
        if start and "success=" not in line:
            current = {
                "index": int(start.group(1)),
                "category": start.group(2),
                "arm": start.group(6),
                "rows": [],
            }
            episodes.append(current)
            continue
        hit = LINE.search(line)
        if hit and current is not None:
            current["rows"].append(
                {
                    "step": int(hit.group(1)),
                    "finger": float(hit.group(2)),
                    "dist": float(hit.group(3)) / 100.0,
                    "fruit_y": float(hit.group(5)),
                    "jaw_y": float(hit.group(8)),
                }
            )
            continue
        result = RESULT.search(line)
        if result and current is not None and current["index"] == int(result.group(1)):
            current["success"] = result.group(4) == "True"
            current["ticks"] = int(result.group(7))
            current["notes"] = line.split("notes=", 1)[-1].split(" presentation")[0]

    print(f"{'ep':>3} {'cat':<11} {'arm':<5} {'ok':>5} {'rows':>5} "
          f"{'min_d':>6} {'f@min_d':>7} {'1st<.03':>7} {'d@1st':>6} "
          f"{'last_step':>9} {'f@last':>7} {'d@last':>6} {'jaw_y_rng':>9}")
    for episode in episodes:
        rows = episode["rows"]
        if not rows:
            print(f"{episode['index']:>3} {episode['category']:<11} {episode['arm']:<5} "
                  f"{str(episode.get('success', '?')):>5} {0:>5}  (no debug rows)")
            continue
        best = min(rows, key=lambda r: r["dist"])
        first_close = next((r for r in rows if r["finger"] < 0.030), None)
        last = rows[-1]
        jaw_lo = min(r["jaw_y"] for r in rows)
        jaw_hi = max(r["jaw_y"] for r in rows)
        print(
            f"{episode['index']:>3} {episode['category']:<11} {episode['arm']:<5} "
            f"{str(episode.get('success', '?')):>5} {len(rows):>5} "
            f"{best['dist'] * 100:>5.1f}c {best['finger']:>7.4f} "
            f"{(first_close['step'] if first_close else -1):>7} "
            f"{(first_close['dist'] * 100 if first_close else float('nan')):>5.1f}c "
            f"{last['step']:>9} {last['finger']:>7.4f} {last['dist'] * 100:>5.1f}c "
            f"{(jaw_hi - jaw_lo) * 100:>8.1f}c"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
