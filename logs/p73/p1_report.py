#!/usr/bin/env python3
"""P73 phase 1 report: the place-transfer-height screen.

Reads `logs/p73/direct/{C,T1,T2}_<seed>.log` (one claim per arm) and prints, per
arm, the registered endpoints of `logs/p73/PREREG.md` §4:

  primary   the left's place-leg loaded slides (`clean_slip_max > 800 mm`, with
            the >10 m / >5 m/s instrument blow-ups counted separately) and the
            left's placed count
  secondary the rotation schedule (`tilt0`/`tilt_end`/`tilt_max`/`t45`/`t75`/
            `tilt_rate`), the slide onset against `t45` (before/after the
            rotation), `clr`/`clr_win`/`clr_edge`/`clr_edge_min`, the landing
            class, the place-leg and episode ticks, and the right arm

`--check` asserts the manipulation: every arm's left place legs carry the tilt
fields, and the median `need` of the `place low` descent rises with the arm's
transfer height (C < T1 < T2, >= 40 mm per step) - the knob's own in-log
signature, since the transfer z is not printed anywhere else.

Usage:
    python3 logs/p73/p1_report.py logs/p73/direct/{C,T1,T2}_77.log
    python3 logs/p73/p1_report.py --check logs/p73/direct/{C,T1,T2}_77.log
"""
from __future__ import annotations

import re
import statistics as st
import sys

CARRY = re.compile(r"\[carry\] (?P<side>left|right) (?P<leg>\w+): (?P<rest>.*)$")
EP = re.compile(
    r"\[rl\] episode (?P<i>\d+): (?P<sp>\w+)(?: grade=(?P<g>\w+))? d=(?P<d>[\d.]+)cm "
    r"bin=\d arm=(?P<arm>\w+) success=(?P<ok>\w+) grasped=(?P<gra>[\w]+) "
    r"placed=(?P<place>\w+) ticks=(?P<ticks>\d+)"
)
PLOW = re.compile(
    r"\[task\] place low: bottom (?P<bottom>\d+) -> (?P<end>\d+) mm "
    r"\(target \d+\), drop (?P<drop>\d+)/(?P<need>\d+) mm"
    r"(?:, FINGER FLOOR budget (?P<budget>\d+) mm)?"
    r", residual (?P<res>[\d.]+) mm, (?P<ticks>\d+) ticks"
)
ATT = re.compile(r"\[attitude\] (?P<side>left|right) (?P<leg>\w+): tilt=(?P<tilt>[-+\d.]+)deg")
BLOWUP_MM = 10_000.0
BLOWUP_VMS = 5.0
SLIDE_MM = 800.0


def num(value: str | None) -> float | None:
    if value is None or value in ("n/a", "None", "-"):
        return None
    m = re.match(r"([-+]?\d+(?:\.\d+)?)", value)
    return float(m.group(1)) if m else None


def mm(field: str | None) -> float | None:
    """`+34mm@obelt/t330` -> 34.0 (None on n/a)."""
    if not field:
        return None
    m = re.match(r"([-+]?\d+)mm", field)
    return float(m.group(1)) if m else None


def parse(path: str) -> dict:
    """One log -> the per-leg, per-episode and per-descent tables."""
    rows: list[dict] = []
    eps: list[dict] = []
    lows: list[dict] = []
    attitudes: dict[int, dict] = {}
    landing = {"did_not_land": 0, "fell_off": 0, "discharged": 0}
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
                pending["att_tilt"] = float(m["tilt"])
                pending = None
            elif m := EP.search(line):
                eps.append(m.groupdict())
            elif m := PLOW.search(line):
                lows.append(m.groupdict())
            elif "grasp did not land on the belt" in line:
                landing["did_not_land"] += 1
            elif "fell off the line" in line and "[rl] episode" not in line:
                landing["fell_off"] += 1
            elif "discharged to the tray" in line:
                landing["discharged"] += 1
    return {"path": path, "rows": rows, "eps": eps, "lows": lows, "landing": landing}


def classify(row: dict) -> str:
    slip = num(row.get("clean_slip_max")) or 0.0
    vmax = num(row.get("in-hand_vmax")) or 0.0
    if slip > BLOWUP_MM or vmax > BLOWUP_VMS:
        return "blowup"
    if slip > SLIDE_MM:
        return "slide"
    return "held"


def place_legs(data: dict, side: str) -> list[dict]:
    return [
        r for r in data["rows"]
        if r["side"] == side and r["leg"].startswith("place")
    ]


def summary(data: dict) -> dict:
    left = place_legs(data, "left")
    right = place_legs(data, "right")
    left_cls = [(classify(r), r) for r in left]
    # the left place legs' descents, in leg order (one per left place leg that
    # reached _place_low; a lost payload can still reach it)
    out = {
        "left_legs": len(left),
        "left_slides": sum(1 for c, _ in left_cls if c == "slide"),
        "left_blowups": sum(1 for c, _ in left_cls if c == "blowup"),
        "left_slide_rows": [r for c, r in left_cls if c == "slide"],
        "left_held_rows": [r for c, r in left_cls if c == "held"],
        "right_legs": len(right),
        "right_slides": sum(1 for r in right if classify(r) == "slide"),
        "right_placed": sum(1 for e in data["eps"] if e["arm"] == "right" and e["place"] == "True"),
        "right_n": sum(1 for e in data["eps"] if e["arm"] == "right"),
        "left_placed": sum(1 for e in data["eps"] if e["arm"] == "left" and e["place"] == "True"),
        "left_n": sum(1 for e in data["eps"] if e["arm"] == "left"),
        "ep_ticks": [int(e["ticks"]) for e in data["eps"]],
        "place_ticks": [int(r["ticks"].split("/")[0]) for r in left if "ticks" in r],
        "need": [int(low["need"]) for low in data["lows"]],
        "low_ticks": [int(low["ticks"]) for low in data["lows"]],
        "low_drop": [int(low["drop"]) for low in data["lows"]],
        "low_bottom": [int(low["bottom"]) for low in data["lows"]],
        "landing": data["landing"],
        "grasped_not_placed": sum(
            1 for e in data["eps"] if e["gra"] == "True" and e["place"] == "False"
        ),
        "notes": [e for e in data["eps"] if e["ok"] == "False"],
    }
    return out


def med(values: list[float]) -> str:
    return f"{st.median(values):.1f}" if values else "-"


def rng(values: list[float]) -> str:
    return f"{min(values):.1f}..{max(values):.1f}" if values else "-"


def show(arm: str, data: dict) -> None:
    s = summary(data)
    print(f"\n========== arm {arm}  ({data['path']})")
    print(
        f"  LEFT placed {s['left_placed']}/{s['left_n']}   "
        f"place legs {s['left_legs']}: {s['left_slides']} loaded slides, "
        f"{s['left_blowups']} blow-ups"
    )
    print(
        f"  RIGHT placed {s['right_placed']}/{s['right_n']}   "
        f"place legs {s['right_legs']}: {s['right_slides']} loaded slides"
    )
    print(
        f"  episode ticks: median {med(s['ep_ticks'])} sum {sum(s['ep_ticks'])}   "
        f"left place-leg ticks: median {med(s['place_ticks'])}"
    )
    print(
        f"  `place low`: need median {med(s['need'])} range {rng(s['need'])}  "
        f"bottom median {med(s['low_bottom'])} [{rng(s['low_bottom'])}]  "
        f"drop median {med(s['low_drop'])}  descent ticks median {med(s['low_ticks'])} "
        f"[{rng(s['low_ticks'])}] (n={len(s['need'])})"
    )
    print(
        f"  landing: discharged {s['landing']['discharged']}, "
        f"did-not-land {s['landing']['did_not_land']}, "
        f"fell-off rows {s['landing']['fell_off']}; "
        f"grasped-not-placed {s['grasped_not_placed']}"
    )

    def tilt_table(rows: list[dict], label: str) -> None:
        if not rows:
            print(f"    {label}: none")
            return
        e = [num(r.get("tilt_end")) for r in rows if num(r.get("tilt_end")) is not None]
        mx = [num(r.get("tilt_max")) for r in rows if num(r.get("tilt_max")) is not None]
        t45 = [num(r.get("t45")) for r in rows if num(r.get("t45")) is not None]
        t75 = [num(r.get("t75")) for r in rows if num(r.get("t75")) is not None]
        rate = [num(r.get("tilt_rate")) for r in rows if num(r.get("tilt_rate")) is not None]
        print(
            f"    {label} (n={len(rows)}): tilt_end {med(e)} [{rng(e)}]  "
            f"tilt_max {med(mx)}  t45 {med(t45)} [{rng(t45)}] (n={len(t45)})  "
            f"t75 {med(t75)} (n={len(t75)})  |rate| {med([abs(v) for v in rate])}"
        )
        for r in rows:
            onset = num(r.get("onset_row"))
            t45v = num(r.get("t45"))
            when = (
                "n/a" if onset is None or t45v is None
                else ("before 45deg" if onset < t45v else "after 45deg")
            )
            print(
                "      {leg:7s} slip={slip:>9s} tilt0={t0:>4s} tilt_end={te:>5s} "
                "t45={t45:>4s} t75={t75:>4s} rate={rate:>15s} onset={on:>5s} "
                "loss={ls:>5s} onset-vs-t45={when:12s} clr={clr:>13s} "
                "edge={edge:>13s} step={stp:>6s} f@on={fon:>7s} fmin={fmin:>5s} "
                "contacts@{con:>3s} sep_end={se:>6s}".format(
                    leg=r["leg"], slip=r.get("clean_slip_max", "-"),
                    t0=r.get("tilt0", "-"), te=r.get("tilt_end", "-"),
                    t45=r.get("t45", "-"), t75=r.get("t75", "-"),
                    rate=r.get("tilt_rate", "-"), on=r.get("onset_row", "-"),
                    ls=r.get("loss_row", "-"), when=when,
                    clr=r.get("clr", "-"), edge=r.get("clr_edge", "-"),
                    stp=r.get("q_step_max", "-"), fmin=r.get("force_min", "-"),
                    fon=r.get("force@onset", "-"), con=r.get("contacts@onset", "-"),
                    se=r.get("sep_end", "-"),
                )
            )

    tilt_table(s["left_slide_rows"], "LEFT loaded slides")
    tilt_table(s["left_held_rows"], "LEFT held (<=800mm)")
    tilt_table(place_legs(data, "right"), "RIGHT place legs")

    clr = [mm(r.get("clr")) for r in s["left_held_rows"] if mm(r.get("clr")) is not None]
    edge = [mm(r.get("clr_edge")) for r in s["left_held_rows"] if mm(r.get("clr_edge")) is not None]
    print(
        f"    LEFT held legs crossing: clr median {med(clr)} range {rng(clr)} "
        f"(>=0: {sum(1 for v in clr if v >= 0)}/{len(clr)})   "
        f"clr_edge median {med(edge)} range {rng(edge)} "
        f"(>=0: {sum(1 for v in edge if v >= 0)}/{len(edge)})"
    )
    fails = s["notes"]
    if fails:
        print("  failing episodes:")
        for e in fails:
            print(
                f"    ep{e['i']} {e['sp']} arm={e['arm']} "
                f"grasped={e['gra']} placed={e['place']}"
            )


def check(arms_data: list[tuple[str, dict]]) -> int:
    """The manipulation check: the knob is in effect, per arm, in-log."""
    ok = True
    needs = {}
    for arm, data in arms_data:
        left = place_legs(data, "left")
        missing = [r["leg"] for r in left if "tilt0" not in r]
        if missing:
            print(f"FAIL: {arm}: {len(missing)} left place legs carry no tilt fields")
            ok = False
        else:
            print(f"ok: {arm}: all {len(left)} left place legs carry the rotation schedule")
        s = summary(data)
        if s["need"]:
            needs[arm] = st.median(s["need"])
        else:
            print(f"FAIL: {arm}: no `place low` rows -> the transfer height is unverified")
            ok = False
    for a, b, step in (("C", "T1", 40), ("T1", "T2", 40)):
        if a in needs and b in needs:
            delta = needs[b] - needs[a]
            if delta >= step:
                print(
                    f"ok: `place low` need {a} {needs[a]:.0f} -> {b} {needs[b]:.0f} mm "
                    f"(+{delta:.0f}, the {a}->{b} transfer raise is in effect)"
                )
            else:
                print(
                    f"FAIL: `place low` need {a} {needs[a]:.0f} -> {b} {needs[b]:.0f} mm "
                    f"(+{delta:.0f} < {step}: the raise is NOT in effect)"
                )
                ok = False
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    do_check = "--check" in argv
    paths = [a for a in argv if not a.startswith("--")]
    # the arm label is the log's filename stem up to the first underscore
    arms_data = [(p.rsplit("/", 1)[-1].split("_")[0], parse(p)) for p in paths]
    for arm, data in arms_data:
        show(arm, data)
    if do_check:
        print("\n---- manipulation check ----")
        return check(arms_data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
