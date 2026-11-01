#!/usr/bin/env python3
"""P83 census: the in-hand displacement (`clean_slip_max`) of placed vs failed
scripted attempts, from the `[carry]` rows the tree already prints.

    python3 logs/p83/census.py [logs/... ]

No simulator, no new instrumentation: it reads the `[fruit]` stream of scripted
`20_pick_place.py` runs (those carry `[fruit] [run] attempt N:` rows) and joins
each attempt's `[carry]` legs to that attempt's outcome. This is the offline
calendar the P83 threshold has to sit in: a fail-fast threshold is only
admissible if the placed population never reaches it.

Read rules (P83 PREREG §3):
  * an attempt is "placed" from its own `[run] attempt N: ... placed=True` row;
  * a leg's `clean_slip_max` is the `[carry]` row's own field (0.1 mm print);
  * a **recycled-payload artifact** (P76-A3: `force_min=0.00N` *and*
    `contacts@onset None/0` *and* a >100 m slip) is listed separately: it is a
    payload the pads never touched, not a slip measurement.
"""

from __future__ import annotations

import glob
import os
import re
import sys

ROW = re.compile(
    r"\[carry\] (?P<side>left|right) (?P<leg>\S+): ticks=(?P<ticks>\d+)/(?P<total>\d+) "
    r"clean_slip_max=(?P<slip>[0-9.]+)mm"
)
RUN_PICK = re.compile(r"\[run\] attempt (?P<n>\d+): picking ")
RUN_END = re.compile(
    r"\[run\] attempt (?P<n>\d+): grasped=(?P<g>\w+) placed=(?P<p>\w+)"
)


def legs_of(path: str):
    """[(attempt_number, leg_row)] for one scripted log, in order."""
    out = []
    attempt = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            m = RUN_PICK.search(line)
            if m:
                attempt = int(m.group("n"))
                continue
            m = ROW.search(line)
            if m:
                row = {
                    "side": m.group("side"),
                    "leg": m.group("leg"),
                    "ticks": int(m.group("ticks")),
                    "total": int(m.group("total")),
                    "slip": float(m.group("slip")),
                }
                # Optional fields the row carries when the diag block was armed.
                for key, pat in (
                    ("force_min", r"force_min=(-?[0-9.]+)N"),
                    ("sep_max", r"sep_max=([0-9.]+)@t(\d+)"),
                    ("onset_row", r"onset_row=(\S+)"),
                    ("loss_row", r"loss_row=(\S+)"),
                    ("contacts", r"contacts@onset=(\S+)"),
                    ("vmax", r"in-hand_vmax=([0-9.]+)"),
                ):
                    mm = re.search(pat, line)
                    row[key] = None if mm is None else mm.group(1)
                if row["force_min"] is not None:
                    row["force_min"] = float(row["force_min"])
                if row["vmax"] is not None:
                    row["vmax"] = float(row["vmax"])
                row["artifact"] = bool(
                    row.get("force_min") == 0.0
                    and (row.get("contacts") in (None, "None", "0"))
                    and row["slip"] > 100000.0
                )
                out.append((attempt, row))
                continue
            m = RUN_END.search(line)
            if m:
                out.append(
                    (
                        int(m.group("n")),
                        {
                            "placed": m.group("p") == "True",
                            "grasped": m.group("g") == "True",
                        },
                    )
                )
                attempt = None
    return out


def attempts_of(path: str):
    """{attempt: {"placed":bool, "legs":[row]}} plus a list of unattributed legs."""
    attempts: dict[int, dict] = {}
    pending: list[dict] = []
    loose: list[dict] = []
    for key, payload in legs_of(path):
        if "placed" in payload:
            slot = attempts.setdefault(key, {"legs": []})
            slot["placed"] = payload["placed"]
            slot["grasped"] = payload["grasped"]
            slot["legs"] = list(pending)
            pending = []
        else:
            pending.append(payload)
    if pending:
        loose = pending
    return attempts, loose


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        paths = sorted(glob.glob("logs/**/*.log", recursive=True))
    placed_rows, failed_rows = [], []
    n_logs = 0
    for path in paths:
        if "clean_slip_max" not in open(path, encoding="utf-8", errors="ignore").read(200000):
            continue
        attempts, loose = attempts_of(path)
        if not attempts:
            continue
        n_logs += 1
        for number in sorted(attempts):
            slot = attempts[number]
            legs = [leg for leg in slot["legs"] if not leg["artifact"]]
            if not legs:
                continue
            top = max(legs, key=lambda leg: leg["slip"])
            record = {
                "file": os.path.relpath(path),
                "attempt": number,
                "leg": top["leg"],
                "side": top["side"],
                "slip": top["slip"],
                "ticks": f"{top['ticks']}/{top['total']}",
                "force_min": top.get("force_min"),
                "sep_max": top.get("sep_max"),
                "vmax": top.get("vmax"),
            }
            (placed_rows if slot.get("placed") else failed_rows).append(record)
    placed_rows = [r for r in placed_rows if r["slip"] < 100000.0]
    failed_rows = [r for r in failed_rows if r["slip"] < 100000.0]

    def summary(name, rows):
        values = sorted(r["slip"] for r in rows)
        if not values:
            print(f"{name}: n=0")
            return
        n = len(values)
        q = lambda f: values[min(n - 1, max(0, int(round(f * (n - 1)))))]
        print(
            f"{name}: n={n}  min={values[0]:.1f}  p50={q(0.5):.1f}  "
            f"p90={q(0.9):.1f}  p99={q(0.99):.1f}  max={values[-1]:.1f} mm"
        )
        over = [r for r in rows if r["slip"] >= 150.0]
        print(f"    >= 150 mm: {len(over)}/{n}")
        for r in sorted(over, key=lambda r: r["slip"], reverse=True)[:12]:
            print(
                f"      {r['slip']:9.1f}mm {r['side']:5s} {r['leg']:10s} "
                f"ticks={r['ticks']:>9s} force_min={r['force_min']} "
                f"sep_max={r['sep_max']} {r['file']}#{r['attempt']}"
            )

    print(f"# P83 census: {n_logs} scripted logs with [carry] rows")
    summary("PLACED attempts  (max leg clean_slip_max)", placed_rows)
    summary("FAILED attempts  (max leg clean_slip_max)", failed_rows)
    if placed_rows:
        worst = max(placed_rows, key=lambda r: r["slip"])
        print(
            f"#   worst placed leg: {worst['slip']:.1f} mm "
            f"({worst['side']} {worst['leg']}, {worst['file']}#{worst['attempt']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
