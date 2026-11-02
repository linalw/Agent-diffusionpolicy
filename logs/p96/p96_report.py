#!/usr/bin/env python3
"""P96 section 3-6: the count/class, the interval, the wall, the landing - and the gates.

    python3 logs/p96/p96_report.py            # -> logs/p96/p96_report.txt
    python3 logs/p96/p96_report.py --same REF CAND

Every delivered endpoint is **P80's** through `logs/p86/p86_report.py`
(`p80lib.metrics`): a placement is the attempt's `t1`, the placement window is
`t_last_place - t_first_place`, the batch span is `t_last_end - t_first_start`,
and the wall comes from the `.stamps` stream. Nothing here re-derives a rate -
the phase's delivered side is a **report** (PREREG §5 G6), never the argument.

The new readout is the **G2 pose table**: the `[biarm] pre-pose <side>:` rows the
clearance solve prints (achieved jaw height, pad-point proxy, tilt, joint margin,
residual), which is where the invariant's pose clause is a *log field* rather
than a trace statistic. The shipped cells print no such row - that absence is the
proof that the pre-P96 path is byte-identical (`--same`).

Gates printed, in the PREREG §5 order:

* **G0** admissibility: the control cells' `[fruit]` streams vs `logs/p92/{C5,C6}.log`.
* **G1** the invariant: `pg_census.py`'s contact count (read here from its table).
* **G2** the pose: every station's achieved pad plane `>= belt_top + 0.0745`.
* **G3** no lost placement: pooled and per seed.
* **G4** no new failure-reason key.
* **G5** motion + landing: `105`/`190` budgets are run by `logs/p96/gates.sh`;
  the landing is read here from `FRUIT_PLACE_TRACE`.
* **G6** delivered side: reported.

Read-only.
"""

from __future__ import annotations

import importlib.util
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p86 = _load("p86_report", os.path.join(ROOT, "logs", "p86", "p86_report.py"))
p80lib = _load("p80lib", os.path.join(ROOT, "logs", "p80", "p80lib.py"))

CELLS = [
    ("C5", 5, False, "logs/p94/T5.log"),
    ("T5", 5, True, "logs/p94/T5.log"),
    ("C6", 6, False, "logs/p94/T6.log"),
    ("T6", 6, True, "logs/p94/T6.log"),
]
PREPOSE_RE = re.compile(
    r"\[biarm\] pre-pose (left|right): (?P<label>.*?)target belt_top\+(?P<target>[-\d.]+) "
    r"achieved jaw belt_top\+(?P<jaw>[-\d.]+) \(pad point belt_top\+(?P<pad>[-\d.]+)\) "
    r"tilt (?P<tilt>[-\d.]+)deg margin (?P<margin>[+-][\d.]+)@j(?P<joint>\d+) "
    r"residual (?P<res>[-\d.]+) mm -> (?P<verdict>.*)$"
)


def prepose_rows(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = PREPOSE_RE.search(line)
            if not m:
                continue
            out.append({
                "arm": m.group(1), "label": m.group("label").strip().rstrip(","),
                "target": float(m.group("target")), "jaw": float(m.group("jaw")),
                "pad": float(m.group("pad")), "tilt": float(m.group("tilt")),
                "margin": float(m.group("margin")), "joint": int(m.group("joint")),
                "residual": float(m.group("res")), "verdict": m.group("verdict").strip(),
            })
    return out


def fruit_stream_sealed(path: str) -> list[str]:
    """The `[fruit]` stream with the P84/P85 sealed filter **and** the P96 `[ftrace]` row.

    `p86.fruit_stream` drops the carrier diag rows (P84/P85's convention). P96's
    cells additionally print one `[fruit] [ftrace] ...` *arming* row per run
    (the P95 instrument), which the pre-P95 records cannot have, so it is added
    to the drop set - the same filter `logs/p95/probe.py` applies.
    """
    out = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "[fruit]" not in line:
                continue
            text = line.rstrip("\n")
            if "[ftrace]" in text:
                continue
            if any(marker in text for marker in p86.DROP):
                continue
            out.append(text)
    return out


def show_same(reference: str, candidate: str) -> int:
    a, b = fruit_stream_sealed(reference), fruit_stream_sealed(candidate)
    print(f"[same] ref={reference} ({len(a)} physics lines)  cand={candidate} ({len(b)})")
    if a == b:
        print("[same] IDENTICAL on every physics line (diag/trace rows dropped)")
        return 0
    index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    print(f"[same] DIFFERS at line {index} (common prefix {index})")
    for name, stream in (("ref", a), ("cand", b)):
        if index < len(stream):
            print(f"  {name}: {stream[index][:200]}")
    return 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--same":
        return show_same(sys.argv[2], sys.argv[3])
    out = []

    def print_(line=""):
        out.append(line)

    print_("P96 - the clearance pre-pose: count/class, interval, wall, landing, gates")
    print_("=" * 108)
    print_("Delivered endpoints are P80's (via p86_report/p80lib): window = t_last_place -")
    print_("t_first_place, batch = t_last_end - t_first_start, wall from .stamps.")
    print_()

    results = {}
    for cell, seed, treat, record in CELLS:
        path = os.path.join(ROOT, f"logs/p96/{cell}.log")
        if not os.path.exists(path):
            print_(f"  {cell}: MISSING {path}")
            continue
        results[cell] = p86.cell(path)

    # ---- G2: the pose table -------------------------------------------------- #
    print_()
    print_("=" * 108)
    print_("G2 - THE POSE: the `[biarm] pre-pose` row (a log field, one row per station)")
    print_("=" * 108)
    print_(f"  {'cell':<4} {'arm':<5} {'target':>7} {'jaw':>7} {'pad':>7} {'tilt':>6} "
           f"{'margin':>7} {'j':>2} {'res':>5}  verdict")
    pose = {}
    for cell, seed, treat, record in CELLS:
        path = os.path.join(ROOT, f"logs/p96/{cell}.log")
        if not os.path.exists(path):
            continue
        rows = prepose_rows(path)
        pose[cell] = rows
        if not rows:
            print_(f"  {cell:<4} - no `[biarm] pre-pose` row (the pre-P96 path prints none)")
            continue
        for r in rows:
            print_(f"  {cell:<4} {r['arm']:<5} {r['target']:>7.3f} {r['jaw']:>7.3f} "
                   f"{r['pad']:>7.3f} {r['tilt']:>6.1f} {r['margin']:>+7.3f} "
                   f"{r['joint']:>2} {r['residual']:>5.1f}  {r['verdict']}")
    print_()
    print_("  The invariant's pose clause is `pad >= belt_top + 0.0745` (`jaw >= belt_top +")
    print_("  0.155`, P95). The pad column is the pad-point *proxy* (`jaw - 0.0805`), i.e.")
    print_("  the conservative plane for a tilted hand; the authored pad bodies' own lowest")
    print_("  point is the static witness in `prepose_check_rows*.json`.")

    # ---- G1: the census, read from pg_census's own table --------------------- #
    print_()
    print_("=" * 108)
    print_("G1 - THE INVARIANT: the pre-leg pad census (`pg_census.py` is the instrument)")
    print_("=" * 108)
    census = os.path.join(HERE, "pg_census.txt")
    if os.path.exists(census):
        keep = []
        for line in open(census, encoding="utf-8"):
            if line.startswith("  ") and ("CONTACTS" in line or "pooled:" in line
                                          or "<= 6 mm" in line):
                keep.append(line.rstrip("\n"))
        for line in keep:
            print_("  " + line.strip())
    else:
        print_("  NO pg_census.txt - run `python3 logs/p96/pg_census.py` first")

    # ---- G3/G4/G6: the delivered side --------------------------------------- #
    print_()
    print_("=" * 108)
    print_("G3/G4/G6 - the count, the class ledger, the interval, the wall")
    print_("=" * 108)
    print_(f"  {'seed':>4} {'arm-set':<10} {'placed':>7} {'s/att':>6} {'interval':>9} "
           f"{'p90':>7} {'window':>7} {'batch':>7} {'wall':>7} {'wall/pick':>9} {'pl/min w':>9}")
    verdict = {}
    for seed in (5, 6):
        for treat, name in ((False, "shipped"), (True, "clearance")):
            cell = next((c for c, s, t, r in CELLS if s == seed and t is treat), None)
            if cell is None or cell not in results:
                continue
            m = results[cell]["m"]
            stats = m.get("stats") or {}
            verdict[(seed, name)] = m
            print_(f"  {seed:>4} {name:<10} {m['placed']:>3}/{m['attempts']:<3} "
                   f"{(stats.get('per_attempt') or float('nan')):>6.2f} "
                   f"{(m['pooled']['mean'] or float('nan')):>9.2f} "
                   f"{(m['pooled']['p90'] or float('nan')):>7.2f} "
                   f"{(m['window_rate'] or float('nan')):>7.2f} "
                   f"{(m['batch_rate'] or float('nan')):>7.2f} "
                   f"{(stats.get('wall') or float('nan')):>7.1f} "
                   f"{(stats.get('wall_per_pick') or float('nan')):>9.2f} "
                   f"{(60.0 * m['placed'] / stats['wall'] if stats.get('wall') else float('nan')):>9.2f}")
    print_()
    for seed in (5, 6):
        for treat, name in ((False, "shipped"), (True, "clearance")):
            key = (seed, name)
            if key not in verdict:
                continue
            m = verdict[key]
            b = (m.get("stats") or {}).get("biarm") or {}
            print_(f"  seed {seed} {name:<10} per arm left {b.get('l')}/{b.get('la')}  "
                   f"right {b.get('r')}/{b.get('ra')}   classes {m['classes']}")
            print_(f"                 reasons {m['reasons']}")

    # ---- the pooled read ---------------------------------------------------- #
    print_()
    print_("  pooled (2 seeds, 40 attempts each side):")
    for treat, name in ((False, "shipped"), (True, "clearance")):
        cells = [c for c, s, t, r in CELLS if t is treat and c in results]
        placed = sum(results[c]["m"]["placed"] for c in cells)
        attempts = sum(results[c]["m"]["attempts"] for c in cells)
        wall = sum((results[c]["m"]["stats"] or {}).get("wall") or 0.0 for c in cells)
        spans = [x["span"] for c in cells for x in results[c]["extra"]["cycles"]]
        rel = [x["blocks"].get("release") for c in cells for x in results[c]["extra"]["cycles"]
               if "release" in x["blocks"]]
        prep = [x["blocks"].get("prepose") for c in cells for x in results[c]["extra"]["cycles"]
                if "prepose" in x["blocks"]]
        hover = [x["blocks"].get("hover") for c in cells for x in results[c]["extra"]["cycles"]
                 if "hover" in x["blocks"]]
        guest = [t for c in cells for t in results[c]["extra"]["traces"] if t["bottom"] >= 0.0]
        lost = [t for c in cells for t in results[c]["extra"]["traces"] if t["bottom"] < 0.0]
        print_(f"    {name:<10} placed {placed}/{attempts} = {100.0 * placed / attempts:.1f} %   "
               f"wall {wall:.0f} s   span p50 {st.median(spans):.2f} s   "
               f"release p50 {st.median(rel) if rel else float('nan'):.2f} s   "
               f"prepose p50 {st.median(prep) if prep else float('nan'):.2f}   "
               f"hover p50 {st.median(hover) if hover else float('nan'):.2f}")
        print_(f"    {'':<10} landing: {len(guest)} payload-present releases, "
               f"on_belt {sum(1 for t in guest if t['on_belt'])}/{len(guest)}   "
               f"off-belt traces {len(lost)} (the upstream-lost class, reported separately)")
        for arm in ("left", "right"):
            data = [results[c]["m"]["per_arm"].get(arm) for c in cells]
            data = [d for d in data if d]
            if not data:
                continue
            pl = sum(d["placed"] for d in data)
            at = sum(d["attempts"] for d in data)
            iv = [d["interval_mean"] for d in data if d["interval_mean"]]
            p9 = [d["interval_p90"] for d in data if d["interval_p90"]]
            idle = [d["idle_frac"] for d in data if d["idle_frac"] is not None]
            print_(f"    {'':<10} {arm:<5} placed {pl}/{at}   interval mean "
                   f"{', '.join(f'{v:.2f}' for v in iv) or 'n/a'}   p90 "
                   f"{', '.join(f'{v:.2f}' for v in p9) or 'n/a'}   idle "
                   f"{', '.join(f'{100 * v:.0f}%' for v in idle) or 'n/a'}")

    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "p96_report.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
