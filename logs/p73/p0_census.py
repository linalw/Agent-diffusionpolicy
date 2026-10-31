#!/usr/bin/env python3
"""P73 phase 0: the offline baseline census (no simulator).

Reads the P71 direct logs (the shipped package's tree) and prints, per arm, the
place-leg shape the P73 screen is about: `clean_slip_max`, the onset/loss rows,
the end `tilt` from `[attitude]`, `q_step_max`, `clr`/`clr_win`/`clr_edge`, and
the per-arm placed counts from the `[rl] episode` rows.

The `[carry]` row is parsed as `key=value` tokens (no value contains a space),
which is immune to field order - the row has grown six times since P41.

Usage: python3 logs/p73/p0_census.py logs/p71/direct/*.log
"""
from __future__ import annotations

import re
import sys

CARRY = re.compile(r"\[carry\] (?P<side>left|right) (?P<leg>\w+): (?P<rest>.*)$")
ATT = re.compile(
    r"\[attitude\] (?P<side>left|right) (?P<leg>\w+): tilt=(?P<tilt>[-+\d.]+)deg "
    r"from world -Z, tool_axis=\((?P<tx>[-+\d.]+),(?P<ty>[-+\d.]+),(?P<tz>[-+\d.]+)\)"
)
EP = re.compile(
    r"\[rl\] episode (?P<i>\d+): (?P<sp>\w+) d=(?P<d>[\d.]+)cm bin=\d "
    r"arm=(?P<arm>\w+) success=(?P<ok>\w+) grasped=(?P<g>\w+) placed=(?P<p>\w+) "
    r"ticks=(?P<ticks>\d+)"
)


def num(field: str | None) -> float | None:
    if field is None:
        return None
    m = re.match(r"([-+]?\d+(?:\.\d+)?)", field)
    return float(m.group(1)) if m else None


def main(paths: list[str]) -> int:
    for path in paths:
        rows: list[dict] = []
        eps: list[dict] = []
        pending: dict | None = None
        with open(path, errors="replace") as fh:
            for line in fh:
                if m := CARRY.search(line):
                    row = {"side": m["side"], "leg": m["leg"]}
                    for token in m["rest"].split():
                        if "=" in token:
                            key, _, value = token.partition("=")
                            row[key] = value
                    pending = row
                    rows.append(row)
                elif (m := ATT.search(line)) and pending is not None:
                    pending["tilt"] = float(m["tilt"])
                    pending["tool_y"] = float(m["ty"])
                    pending = None
                elif m := EP.search(line):
                    eps.append(m.groupdict())
        left = [r for r in rows if r["side"] == "left" and r["leg"].startswith("place")]
        right = [r for r in rows if r["side"] == "right" and r["leg"].startswith("place")]
        lp = sum(1 for e in eps if e["arm"] == "left" and e["p"] == "True")
        ln = sum(1 for e in eps if e["arm"] == "left")
        rp = sum(1 for e in eps if e["arm"] == "right" and e["p"] == "True")
        rn = sum(1 for e in eps if e["arm"] == "right")
        ticks = [int(e["ticks"]) for e in eps]
        print(f"\n=== {path}")
        print(f"  left placed {lp}/{ln}  right placed {rp}/{rn}  "
              f"ep ticks median {sorted(ticks)[len(ticks)//2] if ticks else '-'} "
              f"sum {sum(ticks)}")
        for side, group in (("left", left), ("right", right)):
            if not group:
                continue
            slides = sum(1 for r in group if (num(r.get("clean_slip_max")) or 0) > 800)
            print(f"  {side}: {len(group)} place legs, {slides} loaded slides (>800mm)")
            for r in group:
                tilt = r.get("tilt")
                print(
                    "    {leg:7s} slip={slip:>8s} tilt={tilt:>5s} "
                    "step={step:>6s} jawmax={jz:>6s} loss={loss:>5s} "
                    "onset={o:>5s} f@on={f:>7s} fmin={fm:>5s} vmax={v:>5s} "
                    "clr={clr:>13s} win={win:>13s} edge={edge:>13s} "
                    "em={em:>13s}".format(
                        leg=r["leg"], slip=r.get("clean_slip_max", "-"),
                        tilt=f"{tilt:.1f}" if tilt is not None else "n/a",
                        step=r.get("q_step_max", "-"),
                        jz=r.get("jaw_z", "-").split("/")[-1],
                        loss=r.get("loss_row", "-"), o=r.get("onset_row", "-"),
                        f=r.get("force@onset", "-"), fm=r.get("force_min", "-"),
                        v=r.get("in-hand_vmax", "-"),
                        clr=r.get("clr", "-"), win=r.get("clr_win", "-"),
                        edge=r.get("clr_edge", "-"),
                        em=r.get("clr_edge_min", "-"),
                    )
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
