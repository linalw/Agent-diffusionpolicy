#!/usr/bin/env python3
"""P229 (Stage 1): read the belt-speed ladder `scripts/288_speed_ladder.sh` ran.

    python3 scripts/289_speed_report.py logs/p229/speed

Per speed and pooled, the columns that decide whether the lead's *time* budget
still holds as the belt speeds up:

* **placed / total**, with the Wilson interval (a 6-episode cell is one draw);
* `t_arrive` at the fire, `lead` and `reach` the trigger itself reported - the
  budget's own numbers, so a cell that fails with `t_arrive` well below `lead`
  failed for a reason **other** than the lead (catch-up, grip), and one that
  fires with `t_arrive` at the cap is lead-bound;
* the **lead distance** the fire implies (`t_arrive x speed`) against the
  shipped `_dynamic_pick_lead`'s own value at that speed;
* the failure keys (digit-normalised).

`nan` means the row was absent, and an absent row is a measurement, not a zero.
"""
from __future__ import annotations

import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

EP = re.compile(
    r"^\[fruit\] \[rl\] episode (\d+): (\w+) d=([\d.]+)cm .*?"
    r"success=(\w+) grasped=(\w+) placed=(\w+)"
)
FIRED = re.compile(
    r"intercept trigger \(dy=([-\d.]+)cm, dx=([-\d.]+)cm, t_arrive=([\d.]+)s, "
    r"speed=([\d.]+)m/s/encoder.*?lead=([\d.]+)s/reach=([\d.]+)\)"
)
NOTE = re.compile(r"'([^']*)'")


def med(xs: list[float]) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (100 * (c - h), 100 * (c + h))


def parse(path: Path) -> dict:
    placed = total = fires = 0
    tarrive: list[float] = []
    lead: list[float] = []
    reach: list[float] = []
    implied: list[float] = []
    notes: Counter[str] = Counter()
    for line in path.read_text(errors="replace").splitlines():
        if m := EP.search(line):
            total += 1
            placed += int(m.group(6) == "True")
            body = line.split("notes=", 1)[-1]
            for f in FIRED.finditer(body):
                fires += 1
                ta = float(f.group(3))
                v = float(f.group(4))
                tarrive.append(ta)
                lead.append(float(f.group(5)))
                reach.append(float(f.group(6)))
                implied.append(ta * v)
            for text in NOTE.findall(body):
                if "intercept trigger" in text:
                    continue
                notes[re.sub(r"[\d.]+", "#", text)[:64]] += 1
    return {
        "placed": placed,
        "total": total,
        "fires": fires,
        "t_arrive": tarrive,
        "lead": lead,
        "reach": reach,
        "implied_lead_m": implied,
        "notes": notes,
    }


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else "logs/p229/speed")
    cells = sorted(root.glob("V*_s*.log"))
    if not cells:
        print(f"no cells under {root} - run scripts/288_speed_ladder.sh first")
        return 1

    by_v: dict[float, list[tuple[str, dict]]] = defaultdict(list)
    for path in cells:
        m = re.match(r"V([\d.]+)_s(\d+)\.log$", path.name)
        if not m:
            continue
        by_v[float(m.group(1))].append((m.group(2), parse(path)))

    print(f"{'v':>6} {'seed':>5} {'placed':>7} {'fires':>6} {'t_arrive':>9} "
          f"{'lead':>6} {'reach':>6} {'impl_m':>7}")
    print("-" * 60)
    for v in sorted(by_v):
        for seed, r in by_v[v]:
            print(f"{v:>6.2f} {seed:>5} {r['placed']:>3}/{r['total']:<3} "
                  f"{r['fires']:>6} {med(r['t_arrive']):>9.2f} "
                  f"{med(r['lead']):>6.2f} {med(r['reach']):>6.2f} "
                  f"{med(r['implied_lead_m']):>7.3f}")
    print("-" * 60)

    print(f"\n{'v':>6} {'placed':>9} {'pct':>6} {'95% CI':>12} {'fires':>6} "
          f"{'t_arrive':>9} {'lead_s':>7} {'dy_m':>7}")
    for v in sorted(by_v):
        arms = by_v[v]
        p = sum(a[1]["placed"] for a in arms)
        t = sum(a[1]["total"] for a in arms)
        lo, hi = wilson(p, t)
        ta = [x for a in arms for x in a[1]["t_arrive"]]
        ld = [x for a in arms for x in a[1]["lead"]]
        im = [x for a in arms for x in a[1]["implied_lead_m"]]
        print(f"{v:>6.2f} {p:>4}/{t:<4} {100.0 * p / max(t, 1):>5.1f}% "
              f"[{lo:>4.0f},{hi:>4.0f}] {sum(a[1]['fires'] for a in arms):>6} "
              f"{med(ta):>9.2f} {med(ld):>7.2f} {med(im):>7.3f}")

    print("\nfailure keys (digit-normalised):")
    keys: Counter[str] = Counter()
    for v in by_v:
        for _seed, r in by_v[v]:
            keys.update(r["notes"])
    if not keys:
        print("  (none)")
    for k, n in keys.most_common(12):
        print(f"  {n:>3}  {k}")

    missing = [v for v in by_v if all(r["fires"] == 0 for _s, r in by_v[v])]
    if missing:
        print(f"\nWARNING: no trigger row in {missing} - those cells never fired")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
