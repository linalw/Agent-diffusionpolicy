#!/usr/bin/env python3
"""P74 phase 1 report: the place-profile **speed** vs the left's place-leg slide.

Reads `logs/p74/direct/{C,S}_<seed>.log` (one claim per arm) and prints, per arm,
the registered endpoints of `logs/p74/PREREG.md` section 4:

  primary    the left's place-leg loaded slides (`clean_slip_max > 800 mm`, the
             >10 m / >5 m/s instrument blow-ups counted separately) and the
             left's placed count
  mechanism  every left place leg's `ticks`, its `[motion] carry place*`
             `|v|cmd` / `|a|cmd` / `|v|max` / `cone=`, the rotation schedule
             (`tilt0`/`tilt_end`/`t45`/`t75`/`tilt_rate`), and the escape's
             `onset_row`/`loss_row` as both an absolute tick and a *fraction* of
             the leg (the registered path-fixed vs time-fixed discriminator)
  guards     `clr`/`clr_win`/`clr_edge`/`clr_edge_min`, the escape signature
             (`contacts@onset`/`force@onset`/`force_min`/`sep@*`), the class split
             (`cnp` vs the `grasped=False` acquisition class), any new failure
             reason, the `place low` descent ticks, the landing class, the
             episode ticks, and the right arm

`--check` asserts the MANIPULATION (PREREG section 1.3), not the outcome:
  1. the diag is on in both arms (every left place leg carries the schedule);
  2. the left place legs' `|v|cmd` lands in the arm's own window
     (C <= 0.360, S >= 0.490) - the knob's in-log signature;
  3. the measured place-leg ticks match the arm's own profile arithmetic
     (`motion.jerk_limited` at the printed distance, +-4 %) - so the leg is the
     cap the arm claims and not some other profile;
  4. the S/C ticks ratio on distance-matched legs is `0.673 +- 0.06`;
  5. the `place low` descent ticks do NOT move (transit-only knob, +-20 %).

Usage:
    python3 logs/p74/p1_report.py logs/p74/direct/{C,S}_77.log
    python3 logs/p74/p1_report.py --check logs/p74/direct/{C,S}_77.log
"""
from __future__ import annotations

import re
import statistics as st
import sys

sys.path.insert(0, "src")
try:  # the shipped profile model, for the per-leg arithmetic prediction
    from fruit_sorting import motion as _motion
except Exception:  # pragma: no cover - the report degrades to measured-only
    _motion = None

CARRY = re.compile(r"\[carry\] (?P<side>left|right) (?P<leg>\w+): (?P<rest>.*)$")
MOTION = re.compile(
    r"\[motion\] carry (?P<leg>\w+): (?P<cm>\d+) cm, (?P<ticks>\d+) ticks, "
    r"\|v\|cmd=(?P<vcmd>[\d.]+) \|a\|cmd=(?P<acmd>[\d.]+),"
)
MOTION2 = re.compile(
    r"\|v\|max=(?P<vmax>[\d.]+) m/s, \|a\|max=(?P<amax>[\d.]+) m/s\^2.*?"
    r"cone=(?P<cone>[\d.]+)x budget.*?a_win5=(?P<aw5>[\d.]+) m/s\^2"
)
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
#: the registered caps (PREREG section 2): C = shipped, S = the P44 S1 cell
CAPS = {"C": 0.35, "S": 0.52}
AMAX = 1.089
JMAX = 10.89


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
    rows: list[dict] = []
    eps: list[dict] = []
    lows: list[dict] = []
    landing = {"did_not_land": 0, "fell_off": 0, "discharged": 0}
    pending: dict | None = None
    open_carry: dict | None = None
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
                open_carry = row
            elif m := MOTION.search(line):
                # `_carry` prints the `[carry]` row, then its `[motion]` profile
                # row, one pair per leg instance - so attach to the open row.
                if open_carry is not None and "vcmd" not in open_carry:
                    open_carry.update(m.groupdict())
                    if m2 := MOTION2.search(line):
                        open_carry.update(m2.groupdict())
                    open_carry = None
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
    return {
        "path": path, "rows": rows, "eps": eps,
        "lows": lows, "landing": landing,
    }


def classify(row: dict) -> str:
    slip = num(row.get("clean_slip_max")) or 0.0
    vmax = num(row.get("in-hand_vmax")) or 0.0
    if slip > BLOWUP_MM or vmax > BLOWUP_VMS:
        return "blowup"
    if slip > SLIDE_MM:
        return "slide"
    return "held"


def place_legs(data: dict, side: str) -> list[dict]:
    return [r for r in data["rows"] if r["side"] == side and r["leg"].startswith("place")]


def predict_ticks(cm: float, cap: float) -> int | None:
    """The arm's own profile arithmetic: `_carry`'s `jerk_limited` leg length."""
    if _motion is None:
        return None
    lim = _motion.TrajectoryLimits(v_max=cap, a_max=AMAX, j_max=JMAX)
    a = min(AMAX, 4.273)          # the place leg's cone budget (P44 section 2.4)
    j = min(lim.j_max, max(a * 10.0, 1.0))
    v = min(cap, 2.0 * a)
    real = _motion.TrajectoryLimits(v_max=v, a_max=a, j_max=j)
    positions, velocities, _ = _motion.jerk_limited(cm / 100.0, real)
    return len(positions)


def summary(data: dict, arm: str) -> dict:
    left = place_legs(data, "left")
    right = place_legs(data, "right")
    left_cls = [(classify(r), r) for r in left]
    cap = CAPS.get(arm, 0.35)

    def leg_row(r: dict) -> dict:
        cm = num(r.get("cm"))
        return {
            "row": r, "cm": cm,
            "vcmd": num(r.get("vcmd")), "acmd": num(r.get("acmd")),
            "vmax": num(r.get("vmax")), "cone": num(r.get("cone")),
            "aw5": num(r.get("aw5")),
            "pred": predict_ticks(cm, cap) if cm is not None else None,
        }

    return {
        "arm": arm,
        "left_legs": len(left),
        "left_slides": sum(1 for c, _ in left_cls if c == "slide"),
        "left_blowups": sum(1 for c, _ in left_cls if c == "blowup"),
        "left_slide_rows": [r for c, r in left_cls if c == "slide"],
        "left_held_rows": [r for c, r in left_cls if c == "held"],
        #: held by the 800 mm rule but a payload loss by mechanism (P73's
        #: 793.3 mm leg) - printed so a threshold cannot hide an event
        "left_near_rows": [
            r for c, r in left_cls
            if c == "held" and (num(r.get("clean_slip_max")) or 0.0) > 100.0
        ],
        "left_leg_rows": [leg_row(r) for r in left],
        "right_legs": len(right),
        "right_slides": sum(1 for r in right if classify(r) == "slide"),
        "right_leg_rows": [leg_row(r) for r in right],
        "right_placed": sum(1 for e in data["eps"] if e["arm"] == "right" and e["place"] == "True"),
        "right_n": sum(1 for e in data["eps"] if e["arm"] == "right"),
        "left_placed": sum(1 for e in data["eps"] if e["arm"] == "left" and e["place"] == "True"),
        "left_n": sum(1 for e in data["eps"] if e["arm"] == "left"),
        "ep_ticks": [int(e["ticks"]) for e in data["eps"]],
        "place_ticks": [int(r["ticks"].split("/")[0]) for r in left if "ticks" in r],
        "need": [int(low["need"]) for low in data["lows"]],
        "low_ticks": [int(low["ticks"]) for low in data["lows"]],
        "landing": data["landing"],
        "grasped_not_placed": sum(
            1 for e in data["eps"] if e["gra"] == "True" and e["place"] == "False"
        ),
        "never_grasped": sum(
            1 for e in data["eps"] if e["gra"] == "False" and e["place"] == "False"
        ),
        "notes": [e for e in data["eps"] if e["ok"] == "False"],
    }


def med(values, fmt: str = "{:.1f}") -> str:
    vals = [v for v in values if v is not None]
    return fmt.format(st.median(vals)) if vals else "-"


def rng(values, fmt: str = "{:.1f}") -> str:
    vals = [v for v in values if v is not None]
    return (fmt + ".." + fmt).format(min(vals), max(vals)) if vals else "-"


def leg_table(rows: list[dict]) -> None:
    print(
        "      leg     cm  ticks pred  ratio  |v|cmd |a|cmd |v|max cone "
        "tilt_end  t45  slip        onset loss  o/T    l/T   clr   edge  f@on "
        "fmin contacts sep_end"
    )
    for e in rows:
        r = e["row"]
        ticks = num(r.get("ticks", "").split("/")[0]) if "ticks" in r else None
        ratio = (
            f"{ticks / e['pred']:.3f}"
            if ticks is not None and e["pred"] else "-"
        )
        onset = num(r.get("onset_row"))
        loss = num(r.get("loss_row"))
        print(
            "      {leg:7s} {cm:>3s} {tk:>5s} {pd:>4s} {ra:>6s} {vc:>6s} {ac:>6s} "
            "{vm:>6s} {cn:>4s} {te:>8s} {t45:>4s} {slip:>10s} {on:>5s} {ls:>5s} "
            "{of:>5s} {lf:>5s} {clr:>5s} {edge:>5s} {fon:>5s} {fmin:>5s} "
            "{con:>8s} {se:>6s}".format(
                leg=r["leg"],
                cm=f"{e['cm']:.0f}" if e["cm"] is not None else "-",
                tk=f"{ticks:.0f}" if ticks is not None else "-",
                pd=str(e["pred"]) if e["pred"] else "-",
                ra=ratio,
                vc=f"{e['vcmd']:.3f}" if e["vcmd"] is not None else "-",
                ac=f"{e['acmd']:.3f}" if e["acmd"] is not None else "-",
                vm=f"{e['vmax']:.3f}" if e["vmax"] is not None else "-",
                cn=f"{e['cone']:.2f}" if e["cone"] is not None else "-",
                te=r.get("tilt_end", "-"),
                t45=r.get("t45", "-"),
                slip=r.get("clean_slip_max", "-"),
                on=r.get("onset_row", "-"),
                ls=r.get("loss_row", "-"),
                of=f"{onset / ticks:.2f}" if onset is not None and ticks else "-",
                lf=f"{loss / ticks:.2f}" if loss is not None and ticks else "-",
                clr=r.get("clr", "-"),
                edge=r.get("clr_edge", "-"),
                fon=r.get("force@onset", "-"),
                fmin=r.get("force_min", "-"),
                con=f"{r.get('contacts@onset', '-')}/{r.get('min_contacts', '-')}",
                se=r.get("sep_end", "-"),
            )
        )


def show(arm: str, data: dict) -> dict:
    s = summary(data, arm)
    print(f"\n========== arm {arm}  ({data['path']})")
    print(
        f"  LEFT placed {s['left_placed']}/{s['left_n']}   "
        f"place legs {s['left_legs']}: {s['left_slides']} loaded slides "
        f"(>800mm), {s['left_blowups']} blow-ups"
    )
    print(
        f"  RIGHT placed {s['right_placed']}/{s['right_n']}   "
        f"place legs {s['right_legs']}: {s['right_slides']} loaded slides"
    )
    vcmd = [e["vcmd"] for e in s["left_leg_rows"]]
    acmd = [e["acmd"] for e in s["left_leg_rows"]]
    cone = [e["cone"] for e in s["left_leg_rows"]]
    print(
        f"  LEFT place legs: ticks median {med(s['place_ticks'], '{:.0f}')} "
        f"[{rng(s['place_ticks'], '{:.0f}')}]   |v|cmd {med(vcmd, '{:.3f}')} "
        f"[{rng(vcmd, '{:.3f}')}]   |a|cmd {med(acmd, '{:.3f}')}   cone {med(cone, '{:.2f}')}x"
    )
    print(
        f"  episode ticks: median {med(s['ep_ticks'], '{:.0f}')} "
        f"sum {sum(s['ep_ticks'])}   "
        f"`place low` descent ticks median {med(s['low_ticks'], '{:.0f}')} "
        f"[{rng(s['low_ticks'], '{:.0f}')}] (n={len(s['low_ticks'])})"
    )
    print(
        f"  landing: discharged {s['landing']['discharged']}, "
        f"did-not-land {s['landing']['did_not_land']}, "
        f"fell-off rows {s['landing']['fell_off']}"
    )
    print(
        f"  classes: cnp (grasped, not placed) {s['grasped_not_placed']}, "
        f"never-grasped {s['never_grasped']}, failing episodes {len(s['notes'])}"
    )
    print("  LEFT place legs:")
    leg_table(s["left_leg_rows"])
    print("  RIGHT place legs:")
    leg_table(s["right_leg_rows"])
    edge = [mm(r.get("clr_edge")) for r in s["left_held_rows"]]
    clr = [mm(r.get("clr")) for r in s["left_held_rows"]]
    print(
        f"  LEFT held legs: clr median {med(clr, '{:+.0f}')} [{rng(clr, '{:+.0f}')}] "
        f"(>=0 {sum(1 for v in clr if v is not None and v >= 0)} of "
        f"{sum(1 for v in clr if v is not None)}, n/a {sum(1 for v in clr if v is None)})   "
        f"clr_edge median {med(edge, '{:+.0f}')} [{rng(edge, '{:+.0f}')}] "
        f"(>=0 {sum(1 for v in edge if v is not None and v >= 0)} of "
        f"{sum(1 for v in edge if v is not None)})"
    )
    if s["notes"]:
        print("  failing episodes:")
        for e in s["notes"]:
            print(
                f"    ep{e['i']} {e['sp']} arm={e['arm']} "
                f"grasped={e['gra']} placed={e['place']}"
            )
    return s


def check(arms_data: list[tuple[str, dict]]) -> int:
    """PREREG section 1.3: the manipulation, not the outcome."""
    ok = True
    sums = {}
    for arm, data in arms_data:
        s = summary(data, arm)
        sums[arm] = s
        left = place_legs(data, "left")
        missing = [r["leg"] for r in left if "tilt0" not in r]
        if missing:
            print(f"FAIL: {arm}: {len(missing)} left place legs carry no schedule")
            ok = False
        else:
            print(f"ok: {arm}: all {len(left)} left place legs carry the P73 schedule")
        vcmd = [e["vcmd"] for e in s["left_leg_rows"] if e["vcmd"] is not None]
        if not vcmd:
            print(f"FAIL: {arm}: no `[motion] carry place*` rows -> cap unverified")
            ok = False
            continue
        m = st.median(vcmd)
        lo, hi = (0.0, 0.360) if arm == "C" else (0.490, 10.0)
        if lo <= m <= hi:
            print(f"ok: {arm}: |v|cmd median {m:.3f} is inside [{lo}, {hi}]")
        else:
            print(f"FAIL: {arm}: |v|cmd median {m:.3f} NOT inside [{lo}, {hi}]")
            ok = False
        # the leg is its own cap's profile (measured vs offline arithmetic)
        bad = []
        for e in s["left_leg_rows"]:
            ticks = None
            if "ticks" in e["row"]:
                ticks = num(e["row"]["ticks"].split("/")[0])
            if ticks is None or e["pred"] is None:
                continue
            if abs(ticks / e["pred"] - 1.0) > 0.04:
                bad.append((e["row"]["leg"], ticks, e["pred"]))
        if bad:
            print(f"FAIL: {arm}: {len(bad)} left place legs miss their profile "
                  f"arithmetic by >4 %: {bad}")
            ok = False
        else:
            n = sum(1 for e in s["left_leg_rows"] if e["pred"] is not None)
            print(f"ok: {arm}: all {n} left place legs match `jerk_limited` at "
                  f"v_max {CAPS.get(arm, 0.35)} within 4 %")

    # the ratio on distance-matched legs, and the descent's non-movement
    if "C" in sums and "S" in sums:
        c_by_cm: dict[float, list[float]] = {}
        for e in sums["C"]["left_leg_rows"]:
            if e["cm"] is not None and "ticks" in e["row"]:
                c_by_cm.setdefault(e["cm"], []).append(
                    num(e["row"]["ticks"].split("/")[0])
                )
        ratios = []
        for e in sums["S"]["left_leg_rows"]:
            if e["cm"] in c_by_cm and "ticks" in e["row"]:
                s_ticks = num(e["row"]["ticks"].split("/")[0])
                for c_ticks in c_by_cm[e["cm"]]:
                    if s_ticks and c_ticks:
                        ratios.append(s_ticks / c_ticks)
        if ratios:
            m = st.median(ratios)
            if 0.673 - 0.06 <= m <= 0.673 + 0.06:
                print(f"ok: S/C place-leg ticks on {len(ratios)} distance-matched "
                      f"pairs: median {m:.3f} (predicted 0.673 +- 0.06)")
            else:
                print(f"FAIL: S/C place-leg ticks median {m:.3f} outside "
                      f"0.673 +- 0.06 on {len(ratios)} matched pairs")
                ok = False
        else:
            print("note: no distance-matched place legs between the arms; the "
                  "per-leg arithmetic check above carries the proof")
        c_low = st.median(sums["C"]["low_ticks"]) if sums["C"]["low_ticks"] else None
        s_low = st.median(sums["S"]["low_ticks"]) if sums["S"]["low_ticks"] else None
        if c_low and s_low:
            rel = abs(s_low / c_low - 1.0)
            if rel <= 0.20:
                print(f"ok: `place low` descent ticks unchanged "
                      f"(C {c_low:.0f} -> S {s_low:.0f}, {rel * 100:.0f} %)")
            else:
                print(f"FAIL: `place low` descent ticks moved "
                      f"(C {c_low:.0f} -> S {s_low:.0f}, {rel * 100:.0f} %): the "
                      f"knob is transit-only")
                ok = False
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    do_check = "--check" in argv
    paths = [a for a in argv if not a.startswith("--")]
    arms_data = [(p.rsplit("/", 1)[-1].split("_")[0], parse(p)) for p in paths]
    sums = [(arm, show(arm, data)) for arm, data in arms_data]

    if len(sums) == 2:
        (a1, s1), (a2, s2) = sums
        print(f"\n---- {a1} vs {a2} ----")
        for key, label, fmt in (
            ("left_placed", "left placed", "{:.0f}"),
            ("left_legs", "left place legs", "{:.0f}"),
            ("left_slides", "left loaded slides (>800mm)", "{:.0f}"),
            ("left_blowups", "left blow-ups", "{:.0f}"),
            ("right_placed", "right placed", "{:.0f}"),
            ("right_legs", "right place legs", "{:.0f}"),
            ("right_slides", "right loaded slides", "{:.0f}"),
        ):
            print(f"  {label:32s} {fmt.format(s1[key]):>6s} -> {fmt.format(s2[key]):>6s}")
        for key, label in (
            ("place_ticks", "left place-leg ticks (median)"),
            ("low_ticks", "`place low` descent ticks (median)"),
            ("ep_ticks", "episode ticks (median)"),
        ):
            m1 = st.median(s1[key]) if s1[key] else None
            m2 = st.median(s2[key]) if s2[key] else None
            d = f"{m2 - m1:+.0f}" if m1 is not None and m2 is not None else "-"
            print(
                f"  {label:32s} "
                f"{(f'{m1:.0f}' if m1 is not None else '-'):>6s} -> "
                f"{(f'{m2:.0f}' if m2 is not None else '-'):>6s}   ({d})"
            )
        for arm, s in sums:
            print(f"  SLIDE rows (arm {arm}), `clean_slip_max > 800 mm`:")
            for r in s["left_slide_rows"] + s["left_near_rows"]:
                ticks = num(r.get("ticks", "").split("/")[0]) if "ticks" in r else None
                onset = num(r.get("onset_row"))
                loss = num(r.get("loss_row"))
                slip = (r.get("clean_slip_max") or "-").removesuffix("mm")
                head = (
                    f"    {arm} {r['leg']:7s} slip={slip:>9s} mm"
                    f" ticks={ticks:.0f}"
                    if ticks else
                    f"    {arm} {r['leg']:7s} slip={slip:>9s} mm"
                )
                if ticks and onset is not None:
                    head += f" onset={onset:.0f} ({onset / ticks:.2f} of the leg)"
                if ticks and loss is not None:
                    head += f" loss={loss:.0f} ({loss / ticks:.2f} of the leg)"
                print(head)
                print(f"        f@on={r.get('force@onset')} fmin={r.get('force_min')} "
                      f"contacts@on={r.get('contacts@onset')} "
                      f"sep@on={r.get('sep@onset')} sep@loss={r.get('sep@loss')} "
                      f"sep_end={r.get('sep_end')}")

    if do_check:
        print("\n---- manipulation check (PREREG section 1.3) ----")
        return check(arms_data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
