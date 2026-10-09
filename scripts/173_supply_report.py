"""Report the delivered starvation from a pick-and-place log (v9/V1).

    python3 scripts/173_supply_report.py logs/v1/40_rate_biarm_supply_1.log ...
    python3 scripts/173_supply_report.py logs/g/10_rate_biarm_1.log --label before

Counts, per file:

* the `[stats]` line (attempts/successes/cycle/queue_peak);
* single-arm "no eligible fruit" driver events and the attempt span spread;
* bimanual `[biarm] ... no eligible fruit; station released` events per arm
  (the delivered starvation: each is one station slot the arm could not fill)
  and `[biarm] result` per-arm counts;
* the `[supply]` provenance line when the log has one.

Pure text parsing, no simulator.
"""

from __future__ import annotations

import argparse
import re
import sys


def report(path: str, label: str) -> None:
    stats = None
    supply = None
    no_eligible: dict[str, int] = {}
    acquisitions: dict[str, int] = {}
    results: dict[str, int] = {}
    single_no_eligible = 0
    spans: list[float] = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "[stats]" in line:
                stats = line.strip()
            if "[supply]" in line and "scatter" in line:
                supply = line.strip()
            found = re.search(r"\[biarm\] (\w+): no eligible fruit", line)
            if found:
                no_eligible[found.group(1)] = no_eligible.get(found.group(1), 0) + 1
            found = re.search(r"\[biarm\] (\w+): station acquired", line)
            if found:
                acquisitions[found.group(1)] = acquisitions.get(found.group(1), 0) + 1
            found = re.search(r"\[biarm\] result (\w+)[^\n]*sim=([\d.]+)s", line)
            if found:
                results[found.group(1)] = results.get(found.group(1), 0) + 1
                spans.append(float(found.group(2)))
            if re.search(r"\[run\] attempt \d+: no eligible fruit", line):
                single_no_eligible += 1
    print(f"== {label}: {path}")
    if supply:
        print(f"   {supply}")
    if stats:
        print(f"   {stats}")
    if single_no_eligible:
        print(f"   single-arm driver: no-eligible events={single_no_eligible}")
    if no_eligible or acquisitions:
        spins = sum(no_eligible.values())
        total_acq = sum(acquisitions.values())
        share = f"{spins / total_acq * 100:.1f}%" if total_acq else "n/a"
        print(
            "   bimanual station slots: "
            f"acquired={total_acq} no-eligible={spins} ({share} of slots) "
            f"per arm " + ", ".join(
                f"{arm}={no_eligible.get(arm, 0)}/{acquisitions.get(arm, 0)}"
                for arm in ("left", "right")
            )
        )
        print(
            "   bimanual attempts: "
            + ", ".join(f"{arm}={results.get(arm, 0)}" for arm in ("left", "right"))
            + f" (total {sum(results.values())})"
        )
    if spans:
        spans.sort()
        print(
            f"   attempt spans: n={len(spans)} min={spans[0]:.1f}s "
            f"median={spans[len(spans) // 2]:.1f}s max={spans[-1]:.1f}s"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+")
    parser.add_argument("--label", default=None)
    args = parser.parse_args()
    for path in args.logs:
        report(path, args.label or path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
