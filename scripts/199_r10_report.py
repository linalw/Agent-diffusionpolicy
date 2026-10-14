"""R10-A report: the reach-anywhere readouts (coverage, intercepts, mechanism).

    python3 scripts/199_r10_report.py logs/r10/30_control.log logs/r10/31_reach.log ...
    python3 scripts/199_r10_report.py --self-test

Pure text parsing (no simulator), the read-only re-derivation the repo's
phases leave behind. Per log it prints:

* the attempt table (`[run] attempt`): arm, grasped/placed, lift, the notes;
* the supply stats (`[stats]`): reached_end / fell_off / recirculated,
  queue_peak, gate_open - the coverage context;
* the R10-A `[reach] select` rows (`FRUIT_REACH_DIAG=1`): per selection the
  feasible-candidate count under the reach-anywhere rule and under the shipped
  floor - the **coverage delta**, summed;
* the R10-A `[reach] catch` rows: the intercept distribution and the
  feasibility/fallback counts;
* the R10-A `[reach] met` rows: the realized descent-end error
  (`fruit_y - aim_y`) - positive means the fruit arrived downstream of the aim;
* the `[task] dynamic catch-up: residual=` rows: the acquisition residuals;
* the failure-note classes (the taxonomy comparison input).

The interval / lock-on / placement-window numbers come from
`scripts/186_w6_report.py` on the same logs (this script does not duplicate
that math).
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ATTEMPT_RE = re.compile(
    r"\[run\] attempt (\d+)(?: \((\w+)\))?: grasped=(\w+) placed=(\w+) "
    r"lift=([+-][0-9.]+) m force=([0-9.]+) N"
)
STATS_RE = re.compile(r"\[stats\] (.*)")
SELECT_RE = re.compile(
    r"\[reach\] select station=([+-][0-9.]+) candidates_feasible=(\d+) "
    r"shipped_floor_ok=(\d+) chosen=(\w+) along=([0-9.]+|None) t_c=([0-9.]+|None)s"
)
CATCH_RE = re.compile(
    r"\[reach\] catch (\w+) idx=(\d+) y_fruit=([+-][0-9.]+) vy=([+-][0-9.]+) "
    r"y_int=([+-][0-9.]+) eq=([+-][0-9.]+) feasible=(\d+) "
    r"band=\[([+-][0-9.]+),([+-][0-9.]+)\] t_desc=([0-9.]+)s"
)
MET_RE = re.compile(
    r"\[reach\] met (\w+) idx=(\d+) aim_y=([+-][0-9.]+) station=([+-][0-9.]+) "
    r"fruit_y=([+-][0-9.]+) err=([+-][0-9.]+) waited=(-?\d+)(?: catchup=(\d+))?"
)
CATCHUP_RE = re.compile(r"\[task\] dynamic catch-up: residual=([0-9.]+) mm")
CATCHUP_TICKS_RE = re.compile(
    r"\[reach\] catchup (\w+) idx=(\d+) ticks=(\d+) residual=([0-9.]+)mm"
)


def parse(path: str) -> dict:
    attempts: list[dict] = []
    stats: dict[str, str] = {}
    selects: list[dict] = []
    catches: list[dict] = []
    mets: list[dict] = []
    catchups: list[float] = []
    catchup_ticks: list[int] = []
    for line in Path(path).read_text(errors="replace").splitlines():
        m = ATTEMPT_RE.search(line)
        if m:
            notes_match = re.search(r"notes=\[(.*?)\]\s*(?:sim=|$)", line)
            notes_raw = notes_match.group(1) if notes_match else ""
            notes = [n.strip(" '") for n in notes_raw.split(",") if n.strip(" '")]
            attempts.append(
                dict(
                    index=int(m.group(1)), arm=m.group(2),
                    grasped=m.group(3) == "True", placed=m.group(4) == "True",
                    lift=float(m.group(5)),
                    notes="; ".join(notes),
                )
            )
            continue
        m = STATS_RE.search(line)
        if m:
            stats = dict(
                kv.split("=", 1) for kv in m.group(1).split() if "=" in kv
            )
            continue
        m = SELECT_RE.search(line)
        if m:
            selects.append(
                dict(
                    station=float(m.group(1)), n=float(m.group(2)),
                    shipped=float(m.group(3)), chosen=m.group(4) != "None",
                    yi=None if m.group(6) == "None" else float(m.group(6)),
                )
            )
            continue
        m = CATCH_RE.search(line)
        if m:
            catches.append(
                dict(
                    arm=m.group(1), idx=int(m.group(2)), y_fruit=float(m.group(3)),
                    vy=float(m.group(4)), y_int=float(m.group(5)), eq=float(m.group(6)),
                    feasible=m.group(7) == "1", t_desc=float(m.group(9)),
                )
            )
            continue
        m = MET_RE.search(line)
        if m:
            mets.append(
                dict(
                    arm=m.group(1), idx=int(m.group(2)), aim=float(m.group(3)),
                    station=float(m.group(4)), fruit=float(m.group(5)),
                    err=float(m.group(6)), waited=int(m.group(7)),
                    catchup=int(m.group(8)) if m.lastindex and m.lastindex >= 8 and m.group(8) else None,
                )
            )
            continue
        m = CATCHUP_TICKS_RE.search(line)
        if m:
            catchup_ticks.append(int(m.group(3)))
            continue
        m = CATCHUP_RE.search(line)
        if m:
            catchups.append(float(m.group(1)))
    return dict(
        attempts=attempts, stats=stats, selects=selects, catches=catches,
        mets=mets, catchups=catchups, catchup_ticks=catchup_ticks,
    )


def summarize(path: str) -> None:
    data = parse(path)
    attempts = data["attempts"]
    print(f"==== {path}")
    if attempts:
        success = sum(1 for a in attempts if a["placed"])
        print(f"  attempts={len(attempts)} placed={success} "
              f"({success / len(attempts) * 100:.0f}%)")
        classes = Counter()
        for a in attempts:
            for note in (a["notes"].split("; ") if a["notes"] else []):
                note = note.strip()
                if note:
                    classes[re.sub(r"[0-9.+-]+", "#", note)] += 1
        if classes:
            print("  note classes: " + "; ".join(f"{c} x{n}" for c, n in classes.most_common()))
        print("  attempt table: " + " ".join(
            f"{a['index']}:{a['arm'][0] if a['arm'] else '?'}{'P' if a['placed'] else '-'}"
            for a in attempts
        ))
    stats = data["stats"]
    if stats:
        keys = ("attempts", "successes", "reached_end", "fell_off", "recirculated",
                "queue_peak", "gate_open", "diverted")
        print("  stats: " + " ".join(f"{k}={stats[k]}" for k in keys if k in stats))
    selects = data["selects"]
    if selects:
        with_cand = sum(1 for s in selects if s["n"] > 0)
        with_shipped = sum(1 for s in selects if s["shipped"] > 0)
        print(f"  reach select: instants={len(selects)} "
              f"reach_anywhere_candidates={with_cand} shipped_floor_candidates={with_shipped} "
              f"gain={with_cand - with_shipped:+d}")
        print("    " + " ".join(
            f"[n={int(s['n'])} shipped={int(s['shipped'])}]" for s in selects
        ))
    catches = data["catches"]
    if catches:
        feas = sum(1 for c in catches if c["feasible"])
        print(f"  reach catch: aims={len(catches)} feasible={feas} "
              f"fallback={len(catches) - feas}")
        if feas:
            ys = sorted(c["y_int"] for c in catches if c["feasible"])
            print(f"    intercepts: min={ys[0]:+.4f} p50={ys[len(ys)//2]:+.4f} "
                  f"max={ys[-1]:+.4f}")
    mets = data["mets"]
    if mets:
        errs = sorted(m["err"] for m in mets)
        print(f"  reach met: n={len(mets)} err min={errs[0]:+.4f} "
              f"p50={errs[len(errs)//2]:+.4f} max={errs[-1]:+.4f} "
              f"(negative = fruit upstream of the aim)")
        def _met_label(m: dict) -> str:
            tail = "" if m["catchup"] is None else f"/c{m['catchup']}"
            return f"{m['arm'][0]}{m['idx']}:{m['err'] * 1000:+.0f}mm(w{m['waited']}{tail})"

        print("    " + " ".join(_met_label(m) for m in mets))
    if data["catchups"]:
        cus = sorted(data["catchups"])
        print(f"  catch-up residual: n={len(cus)} min={cus[0]:.1f} "
              f"p50={cus[len(cus)//2]:.1f} max={cus[-1]:.1f} mm")
    if data["catchup_ticks"]:
        tks = sorted(data["catchup_ticks"])
        print(f"  catch-up ticks: n={len(tks)} min={tks[0]} "
              f"p50={tks[len(tks)//2]} max={tks[-1]} (cap 200)")


def self_test() -> int:
    sample = "\n".join(
        [
            "[fruit] [run] attempt 0: picking apple grade A into output lane 0 at (0.9, 0.55)",
            "[fruit] [run] attempt 0: grasped=True placed=True lift=+0.251 m "
            "force=5.00 N notes=[] sim=13.4-28.1",
            "[fruit] [stats] attempts=20 successes=13 reached_end=9 fell_off=0 "
            "recirculated=2 queue_peak=0 gate_open=0.0",
            "[fruit] [reach] select station=+0.00 candidates_feasible=2 "
            "shipped_floor_ok=1 chosen=4 along=0.321 t_c=1.917s",
            "[fruit] [reach] catch left idx=4 y_fruit=+0.3200 vy=-0.1200 "
            "y_int=+0.1000 eq=+0.1000 feasible=1 band=[-0.060,+0.130] t_desc=0.70s",
            "[fruit] [reach] met left idx=4 aim_y=+0.1000 station=+0.0000 "
            "fruit_y=+0.0980 err=-0.0020 waited=42",
            "[fruit] [task] dynamic catch-up: residual=2.1 mm (tol 6 mm)",
            "[fruit] [reach] catchup left idx=4 ticks=17 residual=5.9mm",
        ]
    )
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as handle:
        handle.write(sample)
        path = handle.name
    data = parse(path)
    assert len(data["attempts"]) == 1 and data["attempts"][0]["placed"], "attempt parse"
    assert data["stats"]["successes"] == "13", "stats parse"
    assert data["selects"][0]["n"] == 2 and data["selects"][0]["shipped"] == 1, "select parse"
    assert data["catches"][0]["feasible"] and abs(data["catches"][0]["y_int"] - 0.1) < 1e-9, "catch parse"
    assert abs(data["mets"][0]["err"] + 0.002) < 1e-9 and data["mets"][0]["waited"] == 42, "met parse"
    assert data["catchups"] == [2.1], "catch-up parse"
    assert data["catchup_ticks"] == [17], "catch-up ticks parse"
    summarize(path)
    print("199_r10_report self-test PASS")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    logs = [a for a in argv[1:] if not a.startswith("-")]
    if not logs:
        print(__doc__)
        return 2
    for path in logs:
        summarize(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
