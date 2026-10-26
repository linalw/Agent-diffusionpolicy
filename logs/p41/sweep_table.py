#!/usr/bin/env python3
"""P41 phase 1 - the 8-cell finger-drive fidelity table, re-derived from the logs.

Read-only. For each cell log it prints the cell's runtime finger gains (the
`[effort]` banner read-back, i.e. whether the env knob actually took), the
`close_freeze` rows' tactile sum / projected joint reaction / target error, the
`[task] dynamic close` freeze tick + single-tick force, the attempt outcomes,
the sim span and the wall, then the pooled comparisons the sweep exists to make:

  * **delivered / cap** - P40's definition, `|j1proj| / maxForce[joint1]` (each
    face is driven by one joint capped at 10 N; the tactile sum spans the two
    faces of the pinch, so the per-joint fraction and the pinch sum are both
    printed and they are one number up to the 2x face count);
  * **implied F/err** - `|j1proj| / |err|` at the operating point (a ratio, not a
    stiffness; P40 §4);
  * **stability** - the spread across the cell's grabs and the 5-tick median vs
    the single-tick `[task]` force at the freeze tick (a spike would separate
    them).

    python3 logs/p41/sweep_table.py [--detail] > logs/p41/sweep_table.txt
"""

from __future__ import annotations

import re
import statistics as st
import sys
from pathlib import Path

SWEEP = Path("logs/p41/sweep")
BRACKET = Path("logs/p41/sweep_bracket")

#: The pre-registered 8-cell grid (one claim, `logs/p41/sweep_cells.sh`).
CELLS = (
    ("sub1_k0", 1, "asset", "sub1_k0"),
    ("sub1_k300000", 1, "300000", "sub1_k300000"),
    ("sub1_k100000", 1, "100000", "sub1_k100000"),
    ("sub1_k50000", 1, "50000", "sub1_k50000"),
    ("sub4_k0", 4, "asset", "sub4_k0"),
    ("sub4_k300000", 4, "300000", "sub4_k300000"),
    ("sub4_k100000", 4, "100000", "sub4_k100000"),
    ("sub4_k50000", 4, "50000", "sub4_k50000"),
)

#: The post-hoc bracket (`logs/p41/bracket_cells.sh` + the k=1e6 pair cell):
#: the step's edges, the sub-cap regime, and both joints at the asset's own k.
BRACKET_CELLS = (
    ("k1000000", SWEEP.parent / "claim_bracket_k1e6.log"),
    ("k700000", BRACKET / "k700000.log"),
    ("k500000", BRACKET / "k500000.log"),
    ("k1000", BRACKET / "k1000.log"),
)

BANNER = re.compile(
    r"\[effort\] FRUIT_GRIP_EFFORT=1 reporting only.*?joints=\['([^']+)', '([^']+)'\] "
    r"k=([\d.]+)/([\d.]+)N/m c=([\d.]+)/([\d.]+)Ns/m maxForce=([\d.]+)/([\d.]+)N"
)
EFFORT = re.compile(
    r"\[effort\] (?P<arm>\w+) idx=(?P<idx>-?\d+) (?P<label>\S+) sub=(?P<sub>\d+) "
    r"t=(?P<t>[\d.]+)s n=(?P<n>\d+) \| "
    r"tact\[N\]=(?P<f0>[-\d.]+),(?P<f1>[-\d.]+) sum=(?P<sum>[-\d.]+) "
    r"contacts=(?P<contacts>\d+) \| "
    r"(?P<j1>[^:]+): eff\[N\]=(?P<j1eff>\S+) proj\[N\]=(?P<j1proj>\S+) "
    r"kpc\[N\]=(?P<j1kpc>\S+) Fsat\[N\]=(?P<j1fsat>\S+) q\[mm\]=(?P<j1q>\S+) "
    r"tgt\[mm\]=(?P<j1tgt>\S+) err\[mm\]=(?P<j1err>\S+) \| "
    r"(?P<j2>[^:]+): eff\[N\]=(?P<j2eff>\S+) proj\[N\]=(?P<j2proj>\S+) "
    r"kpc\[N\]=(?P<j2kpc>\S+) Fsat\[N\]=(?P<j2fsat>\S+) q\[mm\]=(?P<j2q>\S+) "
    r"tgt\[mm\]=(?P<j2tgt>\S+) err\[mm\]=(?P<j2err>\S+)"
)
CLOSE = re.compile(
    r"\[task\] dynamic close: sustained contact after (\d+) ticks "
    r"\(force=([\d.]+) N, span=([\d.]+) mm\); freezing the closing command at "
    r"([\d.]+) mm"
)
ATTEMPT = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([+-][\d.]+) m "
    r"force=([\d.]+) N notes=(.*?) sim=([\d.]+)-([\d.]+)s"
)
STATS = re.compile(
    r"\[stats\] attempts=(\d+) successes=(\d+) diverted=(\d+) success_rate=(\d+)% "
    r"sim=([\d.]+)s total, ([\d.]+)s/attempt"
)


def med(xs: list[float]) -> float:
    return float(st.median(xs)) if xs else float("nan")


def log_for(name: str) -> Path | None:
    for cand in (SWEEP / f"{name}.retry.log", SWEEP / f"{name}.log"):
        if cand.is_file() and "[stats]" in cand.read_text(errors="replace"):
            return cand
    for cand in (SWEEP / f"{name}.log", SWEEP / f"{name}.retry.log"):
        if cand.is_file():
            return cand
    return None


def walls() -> dict[str, int]:
    out: dict[str, int] = {}
    for path in (SWEEP / "wall.tsv", BRACKET / "wall.tsv"):
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1].strip().isdigit():
                out[parts[0]] = int(parts[1])
    # the k=1e6 pair cell was run straight through the claim (no cell script)
    out.setdefault("k1000000", 72)
    return out


def read_cell(name: str, path: Path | None = None) -> dict:
    path = path if path is not None else log_for(name)
    d: dict = {"name": name, "path": path}
    if path is None:
        return d
    text = path.read_text(errors="replace")
    b = BANNER.search(text)
    if b:
        d["gains"] = (
            b.group(1), b.group(2), float(b.group(3)), float(b.group(4)),
            b.group(5), b.group(6), float(b.group(7)), float(b.group(8)),
        )
    rows = []
    for line in text.splitlines():
        m = EFFORT.search(line)
        if m:
            rows.append(m.groupdict())
    d["freeze"] = [r for r in rows if r["label"] == "close_freeze"]
    d["all"] = rows
    d["closes"] = [tuple(map(float, m.groups())) for m in CLOSE.finditer(text)]
    d["attempts"] = [m.groups() for m in ATTEMPT.finditer(text)]
    s = STATS.search(text)
    d["stats"] = s.groups() if s else None
    d["wedged"] = "[stats]" not in text
    return d


def cell_line(d: dict, wall: int | None, wall0: int | None) -> str:
    fz = d.get("freeze", [])
    if not fz:
        return f"{d['name']:14s} (no close_freeze rows yet / wedged: {d.get('path')})"
    sums = [float(r["sum"]) for r in fz]
    j1 = [abs(float(r["j1proj"])) for r in fz if r["j1proj"] != "n/a"]
    errs = [abs(float(r["j1err"])) for r in fz]
    caps = [abs(float(r["j1fsat"])) for r in fz if r["j1fsat"] != "n/a"]
    k_eff = (med(j1) / (med(errs) * 1e-3)) if med(errs) else float("nan")
    # the cap is the drive's own maxForce (the [effort] banner read-back), NOT the
    # clipped law `Fsat`: at a very soft k the law (k*err) sits below the cap, and
    # grading against it would report a meaningless 50 %.
    g = d.get("gains")
    cap = g[6] if g and g[6] > 0 else 10.0
    load = med(j1) if j1 else float("nan")
    closes = d.get("closes", [])
    ticks = [c[0] for c in closes]
    tforce = [c[1] for c in closes]
    att = d.get("attempts", [])
    placed = sum(1 for a in att if a[2] == "true")
    stats = d.get("stats")
    span = float(stats[4]) if stats else float("nan")
    g = d.get("gains")
    k_read = f"{g[2]:.0f}/{g[3]:.0f}" if g else "?"
    ratio = f"{wall / wall0:.2f}x" if wall and wall0 else "-"
    fx = f"{med(sums) / 4.38:.2f}x" if sums else "-"
    return (
        f"{d['name']:14s} k={k_read:>15s} n={len(fz):d} "
        f"tact={med(sums):5.2f}[{min(sums):.2f},{max(sums):.2f}] x{fx:<5s} "
        f"j1={load:5.2f} load/cap={load / cap:5.3f} "
        f"err={med(errs):5.2f}mm F/err={k_eff:6.0f}N/m "
        f"close={','.join(f'{t:.0f}' for t in ticks) or '-':>7s} "
        f"tforce={','.join(f'{t:.2f}' for t in tforce) or '-':>14s} "
        f"placed={placed}/{len(att)} span={span:6.1f}s wall={wall if wall else 0:5d}s {ratio}"
    )


def main(argv: list[str]) -> int:
    detail = "--detail" in argv
    w = walls()
    wall0 = w.get("sub1_k0")
    print("P41 phase 1 - the finger-drive fidelity sweep (acceptance scenario,")
    print("ATTEMPTS=2 SEED=5, FRUIT_GRIP_EFFORT=1; 5-tick-median close_freeze rows)")
    print("generated by logs/p41/sweep_table.py")
    print()
    print("k= is the runtime read-back (joint1/joint2 N/m) from the [effort] banner:")
    print("it is the provenance that the env knob took, not the env string.")
    print("load/cap is |j1proj| / maxForce[joint1] (one face vs its own 10 N cap).")
    print()
    print(
        "cell           k[N/m]            n  tact  [min,max] xship j1   load/cap  err      "
        "F/err  close_ticks  close_force[N]  placed span     wall  vs ship"
    )
    print("-" * 168)
    for name, _sub, _k, _log in CELLS:
        d = read_cell(name)
        print(cell_line(d, w.get(name), wall0))

    print()
    print("post-hoc bracket (same scenario, same 120 Hz physics; separate claim):")
    print("the step's edges, the sub-cap regime, and BOTH joints at the asset's own k")
    print("-" * 168)
    for name, path in BRACKET_CELLS:
        d = read_cell(name, path)
        print(cell_line(d, w.get(name), wall0))

    print()
    print("pooled: close_freeze rows per substeps group (median over the group's grabs)")
    print("-" * 168)
    for sub in (1, 4):
        rows = []
        for name, s, _k, _l in CELLS:
            if s != sub:
                continue
            rows.extend(read_cell(name).get("freeze", []))
        if not rows:
            print(f"sub={sub}: (no close_freeze rows yet)")
            continue
        sums = [float(r["sum"]) for r in rows]
        j1 = [abs(float(r["j1proj"])) for r in rows if r["j1proj"] != "n/a"]
        errs = [abs(float(r["j1err"])) for r in rows]
        print(
            f"sub={sub}: n={len(rows):2d} tact_med={med(sums):5.2f} "
            f"[{min(sums):.2f},{max(sums):.2f}] j1_med={med(j1):5.2f} "
            f"load/cap={med(j1) / 10.0:5.3f} err_med={med(errs):5.2f}mm "
            f"F/err={med(j1) / (med(errs) * 1e-3):6.0f}N/m"
        )

    print()
    print("stability: the cell's grabs as a list, and the 5-tick median vs the")
    print("single-tick [task] force at the freeze tick (same grab, same freeze):")
    print("-" * 168)
    for name, _sub, _k, _l in CELLS:
        d = read_cell(name)
        fz = d.get("freeze", [])
        if not fz:
            print(f"{name:14s} (no close_freeze rows)")
            continue
        per = ", ".join(
            f"{r['arm']}:{float(r['sum']):.2f}" for r in fz
        )
        print(f"{name:14s} per-grab tact sum: {per}")

    if detail:
        print()
        print("per-row detail (all [effort] events):")
        print("-" * 168)
        for name, _sub, _k, _l in CELLS:
            d = read_cell(name)
            print(f"[{name}] {d.get('path')}")
            for r in d.get("all", []):
                print(
                    f"  {r['arm']:5s} idx={r['idx']:>3s} {r['label']:<22s} "
                    f"tact={float(r['f0']):5.2f}/{float(r['f1']):5.2f} "
                    f"sum={float(r['sum']):5.2f} j1proj={r['j1proj']:>7s} "
                    f"j2proj={r['j2proj']:>7s} err={r['j1err']:>6s} "
                    f"kpc={r['j1kpc']:>10s} Fsat={r['j1fsat']:>7s}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
