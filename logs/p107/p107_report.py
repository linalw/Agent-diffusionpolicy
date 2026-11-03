#!/usr/bin/env python3
"""P107 per-attempt table: the cage cells, joined to their own `[run]` outcome."""

from __future__ import annotations

import re
import sys

CAGE = re.compile(
    r"\[cage\] idx=(\d+) arm=(\w+) species=(\w+) dia=(\d+)mm approach=(\d+)t "
    r"clr=([-+0-9.]+)mm aper_min=([0-9.]+)mm close=(\d+)t "
    r"bat=([-+0-9.]+)mm bat_rel=([-+0-9.]+)mm pads=(\d)/4 "
    r"f=\(([^)]*)\) F=([0-9.]+)N aper=([0-9.]+)mm no_contact=(\d)"
)
RUN = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([-+0-9.]+) m "
    r"force=([0-9.]+) N notes=\[(.*?)\]"
)


def read(path: str):
    cage: dict[int, dict] = {}
    run: dict[int, dict] = {}
    attempt = 0
    for line in open(path, errors="replace"):
        m = RUN.search(line)
        if m:
            attempt = int(m.group(1))
            run[attempt] = {
                "grasped": m.group(2) == "True",
                "placed": m.group(3) == "True",
                "lift": float(m.group(4)),
                "force": float(m.group(5)),
                "notes": m.group(6),
            }
            continue
        m = CAGE.search(line)
        if m:
            # The cage row prints inside the attempt whose index is `attempt`.
            cage[attempt] = {
                "clr": float(m.group(6)),
                "aper_min": float(m.group(7)),
                "bat": float(m.group(9)),
                "bat_rel": float(m.group(10)),
                "pads": int(m.group(11)),
                "f": [float(v) for v in m.group(12).split(",")],
                "F": float(m.group(13)),
                "no_contact": m.group(15) == "1",
            }
    return cage, run


def main(paths: list[str]) -> int:
    print(
        "| cell | attempt | species | dia | clr mm | bat mm | bat_rel mm | "
        "pads | F N | no-contact | grasped | placed | lift m |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    total = placed = nc = enclose = 0
    for path in paths:
        cell = path.split("/")[-1].replace(".log", "")
        cage, run = read(path)
        for idx in sorted(run):
            r = run[idx]
            c = cage.get(idx)
            if c is None:
                print(f"| {cell} | {idx} | - | - | - | - | - | - | - | - | "
                      f"{int(r['grasped'])} | {int(r['placed'])} | {r['lift']:+.3f} |")
                total += 1
                placed += int(r["placed"])
                continue
            total += 1
            placed += int(r["placed"])
            nc += int(c["no_contact"])
            enclose += int(c["pads"] >= 3)
            print(
                f"| {cell} | {idx} | - | - | {c['clr']:+.1f} | {c['bat']:+.1f} | "
                f"{c['bat_rel']:+.1f} | {c['pads']}/4 | {c['F']:.2f} | "
                f"{int(c['no_contact'])} | {int(r['grasped'])} | {int(r['placed'])} | "
                f"{r['lift']:+.3f} |"
            )
    print()
    print(f"attempts={total} placed={placed} no_contact={nc} pads>=3={enclose}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
