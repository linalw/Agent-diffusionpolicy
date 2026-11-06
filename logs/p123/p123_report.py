"""P123 report: the tray census, the ledger, the guards, and the no-harm replay.

    python3 logs/p123/p123_report.py --cells C5 T5 C6 T6 > logs/p123/p123_report.txt
    python3 logs/p123/p123_report.py --same logs/p123/C5.log logs/p92/C5.log
    python3 logs/p123/p123_report.py --check        # assert the invariants

Reads only the logs. The **endpoint is the tray**: a payload's destination is the
physical tray it was discharged into (`logs/p122/SPEC.md` R0), so the census joins
each `[sort] attempt ... idx=N ... dest=D` to the `[belt] ... (index N) discharged
to the tray ... [tray T]` row that the spawner prints when the fruit settles in a
tray (P123 adds `[tray T]` only when a third lane exists, so a two-lane log is
unchanged). The `in_dest` field is the ledger's own geometric read of the
*release*; the two are compared, never conflated.
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

#: the lane geometry, so a logged `final=` position can be named a belt offline.
LANES = {
    0: {"centre": (0.65, 0.55), "size": (1.10, 0.25), "tray_y": (0.380, 0.720)},
    1: {"centre": (0.65, -0.55), "size": (1.10, 0.25), "tray_y": (0.470, 0.720)},
    2: {"centre": (0.84, -0.3375), "size": (0.72, 0.115), "tray_y": (0.260, 0.400)},
}

#: the printed numbers are `{x}` / `{y:+.2f}` in different places, so every
#: numeric field takes an optional sign.
_N = r"[-+]?[\d.]+"
ATTEMPT = re.compile(
    r"\[sort\] attempt (?P<n>\d+) idx=(?P<idx>-?\d+) (?P<sp>\w+) "
    r"d=(?P<d>[\d.]+)cm grade=(?P<grade>\w*) .*?arm=(?P<arm>\w+) "
    rf"rule=(?P<rule>\S+) dest=(?P<dest>\d+) target=\((?P<tx>{_N}),(?P<ty>{_N})\)"
    rf"(?: placed=(?P<placed>[01]).*?release=\((?P<rx>{_N}),(?P<ry>{_N}),"
    rf"(?P<rz>{_N})\) on_belt=(?P<on_belt>[01]) side=(?P<side>\S+) "
    r"nearest=(?P<nearest>\S+) dist=(?P<dist>\d+)mm in_dest=(?P<in_dest>[01]))?"
)
DISCHARGE = re.compile(
    r"\[belt\] (?P<sp>\w+) \(index (?P<idx>\d+)\) discharged to the tray at "
    rf"x=(?P<x>{_N})" r"(?:.*?\[tray (?P<tray>\d+)\])?"
)
LEDGER = re.compile(
    r"\[sort\] ledger(?: dest=(?P<dest>\d+))?: attempts=(?P<a>\d+) "
    r"(?:assigned=(?P<asg>\d+) )?(?:released=(?P<rel>\d+) )?(?:in_destination=(?P<ind>\d+) )?"
    r"(?:mis_sorted=(?P<mis>\d+) )?(?:not_placed=(?P<np>\d+))?"
)
TRACE = re.compile(
    rf"place trace (?P<arm>\w+): release_bottom=(?P<bottom>{_N})mm .*?"
    rf"final=\((?P<fx>{_N}),(?P<fy>{_N}),(?P<fz>{_N})\).*?"
    r"on_belt=(?P<on_belt>\w+)"
)
CARRY = re.compile(
    r"\[carry\] (?P<arm>\w+) (?P<leg>\w+): ticks=(?P<ticks>\S+) .*?"
    r"clr=(?P<clr>\S+) .*?clr_edge=(?P<clr_edge>\S+) .*?clr_edge_min=(?P<clr_edge_min>\S+)"
    r".*?sep@loss=(?P<sep_loss>\S+)"
)


def read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def strip_prefix(line: str) -> str:
    return line.split("] ", 1)[1] if line.startswith("[fruit] ") else line


def stream_lines(path: str, drop: tuple[str, ...] = ()) -> list[str]:
    """The `[fruit]` payload lines, with the phase's own rows dropped."""
    out = []
    for line in read(path).splitlines():
        if not line.startswith("[fruit] "):
            continue
        body = line[len("[fruit] "):]
        if any(token in body for token in drop):
            continue
        out.append(line)
    return out


def lane_of(x: float, y: float):
    """Which output belt a settled position is on (the same band test)."""
    for lid, lane in LANES.items():
        cx, cy = lane["centre"]
        sx, sy = lane["size"]
        if abs(x - cx) <= sx / 2 and abs(y - cy) <= sy / 2:
            return lid
    return None


def tray_of(y: float):
    """Which tray band a |y| falls in (the shipped 0.04 tolerance included)."""
    ay = abs(y)
    for lid, lane in LANES.items():
        lo, hi = lane["tray_y"]
        if lo - 0.04 <= ay <= hi + 0.04:
            return lid
    return None


def cell_report(name: str, path: str) -> dict:
    text = read(path)
    lines = [strip_prefix(x) for x in text.splitlines() if x.startswith("[fruit] ")]
    attempts = []
    for line in lines:
        m = ATTEMPT.search(line)
        if m:
            attempts.append(m.groupdict())
    discharges = [m.groupdict() for m in (DISCHARGE.search(x) for x in lines) if m]
    traces = [m.groupdict() for m in (TRACE.search(x) for x in lines) if m]
    carries = [m.groupdict() for m in (CARRY.search(x) for x in lines) if m]
    ledgers = [m.groupdict() for m in (LEDGER.search(x) for x in lines) if m]
    stats = next((x for x in lines if x.startswith("[stats]")), "")
    summary = next((x for x in lines if x.startswith("[run] summary")), "")
    banner = next((x for x in lines if "two-line scheduler" in x or "scheduler:" in x), "")
    capability = next((x for x in lines if x.startswith("[sort] capability")), "")
    coverage = next((x for x in lines if x.startswith("[sort] coverage")), "")
    reach = [x for x in lines if x.startswith("[sort] reach")]

    # ---- the tray census ------------------------------------------------- #
    tray_by_idx = {}
    for d in discharges:
        tray_by_idx[int(d["idx"])] = None if d["tray"] is None else int(d["tray"])
    per_dest = collections.defaultdict(lambda: {
        "attempts": 0, "placed": 0, "in_dest": 0, "on_belt": 0,
        "tray": collections.Counter(), "tray_mismatch": 0,
    })
    joined = 0
    agreement = 0
    for a in attempts:
        dest = int(a["dest"])
        row = per_dest[dest]
        row["attempts"] += 1
        if a["placed"] != "1":
            continue
        row["placed"] += 1
        row["on_belt"] += int(a["on_belt"] or 0)
        row["in_dest"] += int(a["in_dest"] or 0)
        idx = int(a["idx"])
        if idx in tray_by_idx and tray_by_idx[idx] is not None:
            joined += 1
            tray = tray_by_idx[idx]
            row["tray"][tray] += 1
            if tray == dest:
                agreement += 1
            else:
                row["tray_mismatch"] += 1
    trays = collections.Counter(v for v in tray_by_idx.values() if v is not None)

    # ---- the guards ------------------------------------------------------ #
    present = [t for t in traces if float(t["bottom"]) >= 0.0]
    lost_upstream = [t for t in traces if float(t["bottom"]) < 0.0]
    on_belt = sum(1 for t in present if t["on_belt"] == "True")
    finals = collections.Counter(
        lane_of(float(t["fx"]), float(t["fy"])) for t in present
    )
    placed_legs = [c for c in carries if c["leg"].startswith("place")]
    clr_vals = []
    for c in placed_legs:
        try:
            clr_vals.append(float(c["clr"].split("@")[0].replace("mm", "")))
        except ValueError:
            pass
    edge_vals = []
    for c in placed_legs:
        for key in ("clr_edge", "clr_edge_min"):
            try:
                edge_vals.append(float(c[key].split("@")[0].replace("mm", "")))
            except (ValueError, AttributeError):
                pass

    return {
        "name": name, "path": path, "banner": banner, "stats": stats,
        "summary": summary, "attempts": attempts, "discharges": discharges,
        "traces": traces, "carries": carries, "ledgers": ledgers,
        "capability": capability, "coverage": coverage, "reach": reach,
        "per_dest": per_dest, "trays": trays, "joined": joined,
        "agreement": agreement, "present": len(present),
        "lost_upstream": len(lost_upstream), "on_belt": on_belt,
        "finals": finals, "clr_min": min(clr_vals) if clr_vals else None,
        "edge_min": min(edge_vals) if edge_vals else None,
        "ledger": ledgers[0] if ledgers else None,
    }


def print_cell(r: dict) -> None:
    print(f"== {r['name']}  ({r['path']})")
    print(f"   {r['banner']}")
    print(f"   {r['stats']}")
    print(f"   {r['summary']}")
    if r["capability"]:
        print(f"   {r['capability']}")
    if r["coverage"]:
        print(f"   {r['coverage']}")
    for line in r["reach"]:
        print(f"   {line}")
    print(f"   attempts={len(r['attempts'])} releases(payload present)={r['present']}"
          f" (upstream-lost {r['lost_upstream']}) on_belt={r['on_belt']}")
    if r["finals"]:
        print("   settled belt (from `final=`): " + ", ".join(
            f"lane {k}: {v}" for k, v in sorted(r["finals"].items(), key=lambda kv: (kv[0] is None, kv[0]))))
    print("   per destination:")
    for dest in sorted(r["per_dest"]):
        row = r["per_dest"][dest]
        trays = ", ".join(f"tray{k}={v}" for k, v in sorted(row["tray"].items())) or "-"
        print(f"     dest {dest}: attempts={row['attempts']} placed={row['placed']} "
              f"on_belt={row['on_belt']} in_dest={row['in_dest']} "
              f"tray_census[{trays}] mismatched={row['tray_mismatch']}")
    print(f"   tray census (discharge rows, all samples): "
          + (", ".join(f"tray{k}={v}" for k, v in sorted(r["trays"].items())) or "none")
          + f"; joined to a placed attempt: {r['joined']}, tray == dest: {r['agreement']}")
    if r["ledger"]:
        g = r["ledger"]
        print(f"   ledger total: attempts={g['a']} released={g['rel']} "
              f"in_destination={g['ind']} mis_sorted={g['mis']} not_placed={g['np']}")
    if r["clr_min"] is not None:
        print(f"   clearance: held place legs={len([c for c in r['carries'] if c['leg'].startswith('place')])}"
              f" clr_min={r['clr_min']:+.0f} mm, min(clr_edge, clr_edge_min)="
              f"{r['edge_min']:+.0f} mm" if r["edge_min"] is not None else "")
    print()


def same(a: str, b: str) -> int:
    """Replay identity: the two `[fruit]` streams with the phase's rows dropped."""
    drop = ("[biarm] place profile:", "[biarm] release profile:", "[biarm] two-line scheduler:",
            "[sort] ", "[scenario] ", "[belt]", "output conveyors added")
    left = stream_lines(a, drop)
    right = stream_lines(b, drop)
    n = min(len(left), len(right))
    first = next((i for i in range(n) if left[i] != right[i]), None)
    ok = len(left) == len(right) and first is None
    print(f"{'SAME' if ok else 'DIFFERS'}: {a} ({len(left)} lines) vs {b} ({len(right)} lines)")
    if first is not None:
        print(f"  first difference at line {first}:")
        print(f"    a: {left[first][:200]}")
        print(f"    b: {right[first][:200]}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", nargs="*", default=[])
    ap.add_argument("--same", nargs=2, metavar=("A", "B"))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.same:
        return same(*args.same)
    if not args.cells:
        ap.error("--cells or --same")

    results = {}
    for name in args.cells:
        path = os.path.join(HERE, f"{name}.log")
        if not os.path.exists(path):
            print(f"== {name}: MISSING {path}")
            continue
        results[name] = cell_report(name, path)
        print_cell(results[name])

    if args.check:
        bad = []
        for name, r in results.items():
            for t in r["traces"]:
                if float(t["bottom"]) >= 0.0 and t["on_belt"] != "True":
                    bad.append(f"{name}: a payload-present release not on a belt "
                               f"(final {t['fx']},{t['fy']},{t['fz']})")
            if r["edge_min"] is not None and r["edge_min"] <= 0.0:
                bad.append(f"{name}: a place leg at clr_edge {r['edge_min']:+.0f} mm")
            if r["clr_min"] is not None and r["clr_min"] <= 0.0:
                bad.append(f"{name}: a place leg at clr {r['clr_min']:+.0f} mm")
        print("==", "GUARDS PASS" if not bad else "GUARDS FAIL")
        for line in bad:
            print("  FAIL", line)
        return 0 if not bad else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
