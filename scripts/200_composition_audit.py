"""P2 composition audit: is the density effect separable from the fruit mix?

The Oracle review's decisive objection to P1/P2 (`logs/p3/ORACLE_REVIEW.md`):
the density knob changes the release geometry, therefore the *presented class
multiset* changes with D, and the placement rate is class-dominated. Direct
standardisation of each config's observed placements against the pooled
per-(arm, fruit) placement rate should show whether the ladder survives.

Offline, no simulator: reads the slot tables out of the `186` report.

    python3 scripts/200_composition_audit.py logs/p2d/80_battery_report.txt
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict

ROW = re.compile(
    r"^\s*(\d+)\s+(left|right)\s+(\w+)\s+([ABC])\s+(\d+)\s+"
    r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(True|False)\s+(True|False)"
)


def parse(path: str) -> dict[str, list[tuple[str, str, bool]]]:
    """config -> [(arm, fruit, placed)] from the report's slot tables."""
    out: dict[str, list[tuple[str, str, bool]]] = {}
    current = None
    in_table = False
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("== "):
            current = line[3:].strip().replace("logs/", "")
            in_table = False
            continue
        if current is None:
            continue
        if line.lstrip().startswith("slot arm"):
            in_table = True
            continue
        if not in_table:
            continue
        m = ROW.match(line)
        if not m:
            continue
        # group 9 is `grasp`, group 10 is `place` - the audit needs the latter.
        arm, fruit, placed = m.group(2), m.group(3), m.group(10) == "True"
        out.setdefault(current, []).append((arm, fruit, placed))
    return out


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "logs/p2d/80_battery_report.txt"
    data = parse(path)
    if not data:
        print(f"no slot tables parsed from {path}")
        return 1
    two_line = {
        cfg: rows
        for cfg, rows in data.items()
        if any(arm == "left" for arm, _, _ in rows)
        and any(arm == "right" for arm, _, _ in rows)
    }
    if not two_line:
        print("no two-line configs in the report")
        return 1

    # the pooled per-(arm, fruit) placement rate, over every two-line config
    attempts: Counter = Counter()
    placed: Counter = Counter()
    for rows in two_line.values():
        for arm, fruit, ok in rows:
            attempts[(arm, fruit)] += 1
            placed[(arm, fruit)] += 1 if ok else 0
    rate = {
        k: (placed[k] / attempts[k]) for k in attempts if attempts[k] >= 3
    }

    print(f"# the pooled per-(arm, fruit) placement rate "
          f"({len(rate)} cells with >= 3 attempts)")
    for (arm, fruit), r in sorted(rate.items(), key=lambda kv: kv[1]):
        print(f"   {arm:>5} {fruit:<10} {placed[(arm, fruit)]:>3}/{attempts[(arm, fruit)]:<3} "
              f"= {r:.2f}")
    spread = max(rate.values()) - min(rate.values())
    print(f"   -> the class effect spans {min(rate.values()):.2f}..{max(rate.values()):.2f}"
          f" ({spread:.2f}); a flat-config comparison would read {1 / (1 + spread):.2f}")

    print("\n# per config: observed vs class-standardised placements")
    print(f"{'config':<26}{'n':>3}{'placed':>7}{'rate':>7}{'adjusted':>10}{'gap':>7}"
          f"   presented mix")
    rows_out = []
    for cfg in sorted(two_line):
        rows = two_line[cfg]
        n = len(rows)
        obs = sum(1 for _, _, ok in rows if ok)
        exp = sum(rate.get((arm, fruit), obs / n) for arm, fruit, _ in rows)
        mix = Counter(f"{fruit}" for _, fruit, _ in rows)
        rows_out.append((cfg, n, obs, obs / n, exp, exp - obs))
    for cfg, n, obs, r, exp, gap in rows_out:
        mix = " ".join(
            f"{f}x{c}" for f, c in Counter(
                fruit for _, fruit, _ in two_line[cfg]).most_common()
        )
        print(f"{cfg:<26}{n:>3}{obs:>7}{r:>7.2f}{exp:>10.2f}{gap:>+7.2f}   {mix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())