#!/usr/bin/env python3
"""P62 phase 2 report: re-derives every number in `logs/p62/P2_RESULTS.md`.

    python3 logs/p62/p2_report.py            # print
    python3 logs/p62/p2_report.py --check    # print + assert (exit 0 = PASS)

Reads gate P0 / P0b (`logs/p62/p2/P0{A,B}.log` at seed 77 on the measured tree,
`logs/p62/p2/P0b{A,B}.log` at seed 101 on the final tree), the acceptance
(`logs/p62/p2/accept_wall.log` + its gate output `motion_gate.txt`) and the P41
reference it is compared against. Nothing here runs a simulator or writes a file.
"""
from __future__ import annotations

import hashlib
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P2 = ROOT / "logs/p62/p2"

#: The registered gate (`logs/p62/PREREG_P2.md` section 3): the left's achieved
#: `grasp_lift` belt projection must move by at least this much for E1 to be
#: evaluable at all.
GATE = 0.05

#: The phase-1 candidate table's left projection, for the contrast print.
ORIENTED_LEFT_PROJ = 0.513236

#: (label, seed, header file) - the two independent draws of the same pair.
PAIRS = (
    ("P0", "77", "p0_header.txt"),
    ("P0b", "101", "p0b_header.txt"),
)

RE_ATT = re.compile(
    r"\[attitude\] (left|right) (grasp_lift|place[01]): tilt=([\d.]+)deg from "
    r"world -Z, tool_axis=\(([-+\d.]+),([-+\d.]+),([-+\d.]+)\)"
)
RE_CARRY = re.compile(
    r"\[carry\] (left|right) (grasp_lift|place[01]): ticks=\d+/\d+ "
    r"clean_slip_max=([\d.]+)mm slip_xyz=\(([-+\d.]+),([-+\d.]+),([-+\d.]+)\)mm"
)
#: `[rl] episode 0: pear d=6.1cm bin=0 arm=left success=False grasped=True placed=False`
#: (the *outcome* row; the selection row carries `grade=` and no `success=`).
RE_EP = re.compile(
    r"\[rl\] episode (\d+): (\w+)(?: grade=(\w))? d=([\d.]+)cm bin=(\d) arm=(\w+) "
    r".*success=(True|False) grasped=(True|False) placed=(True|False)"
)
GRASP_ROW = "[grasp] left attitude override:"
SUPPLY_ROW = "[supply] direct profile:"


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def attitude_rows(path: Path) -> dict[tuple[str, str], list[dict]]:
    out: dict[tuple[str, str], list[dict]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RE_ATT.search(line)
        if not m:
            continue
        axis = [float(m.group(4)), float(m.group(5)), float(m.group(6))]
        out.setdefault((m.group(1), m.group(2)), []).append(
            {"tilt": float(m.group(3)), "axis": axis, "belt": -axis[1]}
        )
    return out


def carry_rows(path: Path) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RE_CARRY.search(line)
        if not m:
            continue
        vec = [float(m.group(4)), float(m.group(5)), float(m.group(6))]
        norm = math.dist((0.0, 0.0, 0.0), vec)
        out[(m.group(1), m.group(2))] = {
            "clean_slip_max": float(m.group(3)),
            "vec": vec,
            "norm": norm,
            "tool_share": vec[2] / norm if norm > 0 else float("nan"),
        }
    return out


def episodes(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RE_EP.search(line)
        if m:
            out.append(
                {
                    "ep": int(m.group(1)),
                    "fruit": m.group(2),
                    "arm": m.group(6),
                    "success": m.group(7) == "True",
                    "placed": m.group(9) == "True",
                }
            )
    return out


def fruit_stream(path: Path) -> list[str]:
    """The `[fruit]` physics stream with the *reference's* own instrument rows out.

    `logs/p41/p2/accept_profile.log` was recorded with a carry diagnostic on, so
    it carries 60 `[fruit] [diag]` + 20 `[fruit] [carry]` rows that a knobs-off
    run cannot produce; removing them leaves the 377 both runs share.
    """
    return [
        line
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if "[fruit]" in line
        and "[fruit] [diag]" not in line
        and "[fruit] [carry]" not in line
    ]


def main() -> int:
    checks: list[tuple[bool, str]] = []

    def check(cond: bool, what: str) -> None:
        checks.append((bool(cond), what))
        print(f"  [{'PASS' if cond else 'FAIL'}] {what}")

    print("P62 phase 2 — the T0 left attitude: gate P0/P0b, and the acceptance identity")
    print("=" * 78)

    # ------------------------------------------------------------ the arms
    for label, seed, header in PAIRS:
        logs = {arm: P2 / f"{label}_{arm}.log" for arm in ("A", "B")}
        print(f"\n{label}. the two arms — seed {seed}, 2 episodes each, "
              f"`{label}` = {'control' if label == 'P0' else 'final tree'}")
        if label == "P0":
            print(f"    header: logs/p62/p2/{header} (carries the run's pins)")
        eps = {arm: episodes(p) for arm, p in logs.items()}
        for arm in ("A", "B"):
            rows = " ".join(
                f"{e['ep']}:{e['fruit']}/{e['arm']}/"
                f"{'placed' if e['placed'] else 'cnp'}"
                for e in eps[arm]
            )
            print(f"    {arm}: {sum(e['placed'] for e in eps[arm])}/{len(eps[arm])} placed  [{rows}]")
        check([e["fruit"] for e in eps["A"]] == [e["fruit"] for e in eps["B"]]
              and [e["arm"] for e in eps["A"]] == [e["arm"] for e in eps["B"]],
              f"{label}: both arms drew the same fruit sequence on the same arms")
        check([e["placed"] for e in eps["A"]] == [e["placed"] for e in eps["B"]],
              f"{label}: both arms placed the same episodes (the treatment is the control)")

        # F2
        txt = {arm: p.read_text(encoding="utf-8", errors="replace") for arm, p in logs.items()}
        check(GRASP_ROW not in txt["A"], f"{label}: control arm prints no `[grasp]` override row")
        check(GRASP_ROW in txt["B"], f"{label}: armed arm prints the `[grasp]` override row")
        check(SUPPLY_ROW in txt["A"] and SUPPLY_ROW in txt["B"],
              f"{label}: both arms ran the shipped direct supply profile")

        # the gate
        att = {arm: attitude_rows(p) for arm, p in logs.items()}
        for arm in ("A", "B"):
            for (side, leg), lst in sorted(att[arm].items()):
                for r in lst:
                    print(
                        f"    {arm} {side:5s} {leg:10s} tilt={r['tilt']:5.1f}deg "
                        f"belt_proj={r['belt']:+.4f} axis="
                        f"({r['axis'][0]:+.4f},{r['axis'][1]:+.4f},{r['axis'][2]:+.4f})"
                    )
        key, rk = ("left", "grasp_lift"), ("right", "grasp_lift")
        a, b = att["A"][key][0]["belt"], att["B"][key][0]["belt"]
        ra, rb = att["A"][rk][0]["belt"], att["B"][rk][0]["belt"]
        print(f"    left  grasp_lift belt_proj {a:+.4f} -> {b:+.4f}  delta {b - a:+.4f} "
              f"(gate |delta| >= {GATE})")
        print(f"    right grasp_lift belt_proj {ra:+.4f} -> {rb:+.4f}  delta {rb - ra:+.4f} "
              f"(NOT touched by the knob)")
        check(abs(b - a) < GATE, f"{label} F3: the treated arm's projection moved "
                                f"{abs(b - a):.4f} < {GATE}")
        check(abs(rb - ra) > abs(b - a),
              f"{label}: the untouched arm moved more than the treated one")

        # the mechanism row
        car = {arm: carry_rows(p) for arm, p in logs.items()}
        sa = car["A"].get(key)
        sb = car["B"].get(key)
        for arm, r in (("A", sa), ("B", sb)):
            if r:
                print(
                    f"    {arm} left `grasp_lift` slip: clean_slip_max="
                    f"{r['clean_slip_max']:7.1f}mm  slip_xyz="
                    f"({r['vec'][0]:+.1f},{r['vec'][1]:+.1f},{r['vec'][2]:+.1f})mm  "
                    f"tool-axis share={r['tool_share']:+.3f}"
                )
        check(sa is not None and sb is not None,
              f"{label}: both arms produced a left `grasp_lift` slip row")
        if sa and sb:
            check(abs(sa["tool_share"] - sb["tool_share"]) < 0.10,
                  f"{label}: the slip's tool-axis share is unchanged (P61 mean +0.905, n=14)")

    # ------------------------------------------------------------ the row once
    print("\n3. the armed row as printed (seed 77 arm B)")
    row = next(
        l for l in (P2 / "P0_B.log").read_text(encoding="utf-8", errors="replace").splitlines()
        if GRASP_ROW in l
    )
    print(f"   {row.strip()}")
    check("file_same=1" in row, "the override equals the waypoints file's left value")
    check("hold_same=1" in row, "the override equals the hold the never-stop catch installs")
    check("belt_proj=+0.0000" in row.split("|")[0],
          "the armed attitude's belt projection is 0.0000")
    check(f"belt_proj={ORIENTED_LEFT_PROJ:+.4f}" not in row.split("|")[1],
          "the row's `file=` field is NOT the +0.513 oriented attitude")

    # ------------------------------------------------------------ acceptance
    print("\n4. A1 - the scripted line is byte-identical by construction")
    acc = P2 / "accept_wall.log"
    ref = ROOT / "logs/p41/p2/accept_profile.log"
    mine, theirs = fruit_stream(acc), fruit_stream(ref)
    stream_md5 = hashlib.md5(("\n".join(mine) + "\n").encode()).hexdigest()
    print(f"   [fruit] physics rows: ours {len(mine)}  reference {len(theirs)}")
    check(mine == theirs, f"the `[fruit]` stream is {len(mine)}/{len(theirs)} IDENTICAL "
                          f"(stream md5 {stream_md5[:8]})")
    gtxt = (P2 / "motion_gate.txt").read_text(encoding="utf-8", errors="replace")
    check("fingerprint: matches configs/motion_reference.json" in gtxt,
          "the motion gate reads `fingerprint: matches`")
    check("success: 6/10 = 60%" in gtxt and "success 6/10 below 75%" in gtxt,
          "the gate FAILs on the rate only (6/10 is this tree's documented count)")
    atxt = acc.read_text(encoding="utf-8", errors="replace")
    stats = [l for l in atxt.splitlines() if "[stats]" in l]
    print(f"   {stats[-1].strip()[:170] if stats else '(no [stats] row)'}")
    check("gate_open=0.0s" in (stats[-1] if stats else ""),
          "the shipped never-stop invariant holds (gate_open=0.0 s)")

    # ------------------------------------------------------------ pins
    print("\n5. pins")
    for rel, want in (
        ("src/fruit_sorting/tasks.py", "fe11910a169949e118e82be252e459fa"),
        ("configs/waypoints.json", "d81c6f1ccad96254264b62331968716b"),
        ("configs/waypoints_oriented.json", "0ea08ebb6bdbd1e78a2402ca263ded01"),
        ("configs/motion_reference.json", "8a399626c12a4e9205ce10e630b94ce9"),
        ("configs/motion_reference_twoline.json", "2246f83c336f7fd6e1f8fe43d0ee8644"),
    ):
        got = md5(ROOT / rel)
        print(f"   {rel:44s} {got}")
        check(got == want, f"{rel} unchanged ({want[:8]})")

    print("\n" + "=" * 78)
    bad = [w for ok, w in checks if not ok]
    if bad:
        print(f"RESULT: FAIL ({len(bad)} of {len(checks)} checks)")
        for w in bad:
            print(f"  - {w}")
        return 1
    print(f"RESULT: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
