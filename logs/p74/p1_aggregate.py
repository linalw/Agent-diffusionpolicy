#!/usr/bin/env python3
"""P74 aggregate: the pooled 3-seed ledger of the place-profile speed test.

The per-arm detail is `logs/p74/p1_report.py`; this script is the *pooled* read
the phase's verdict needs, and it exists because the seed-77 direction did not
survive seeds 101/202 (PREREG section 5, falsifier F1).

What it prints, per corpus (the six P74 logs plus the P71/P73 reference runs):

  * the left's place-leg **class ledger**: `slide` = the registered primary
    (`clean_slip_max > 800 mm`), `near` = `100..800 mm` (a payload loss held by
    the threshold), `micro` = crossed the 2 mm crossing but recoiled inside
    100 mm, `held` = no crossing, `blowup` = the instrument's `> 10 m` /
    `> 5 m/s` class (never counted as a loss). **The mechanism count is
    `loss = slide + near`** - a payload that left the pinch;
  * the **walk rate** `clean_slip_max / (ticks - loss_row)` [mm per remaining
    tick], which is why the `> 800` count is speed-biased: the walk is the
    payload's free travel over the leg that is *left*, so a faster leg has both
    a higher rate and fewer ticks left;
  * `t45 / ticks` and `loss_row / ticks` (the registered path-fixed vs
    time-fixed discriminator);
  * the acquisition guard (`grasped=False`), the `cnp` count, the landing class,
    the right arm, and the pooled place-landing ticks.

Fisher exact tests (two-sided) on the escape and `> 800` ledgers are computed
without scipy.

Usage:
    python3 logs/p74/p1_aggregate.py logs/p74/direct/{C,S}_{77,101,202}.log
"""
from __future__ import annotations

import re
import statistics as st
import sys
from math import comb

CARRY = re.compile(r"\[carry\] (?P<side>left|right) (?P<leg>\w+): (?P<rest>.*)$")
EP = re.compile(
    r"\[rl\] episode (?P<i>\d+): (?P<sp>\w+).*?arm=(?P<arm>\w+) success=(?P<ok>\w+) "
    r"grasped=(?P<gra>\w+) placed=(?P<pl>\w+)"
)
PLOW = re.compile(r"\[task\] place low: .*?, (?P<ticks>\d+) ticks")
SLIDE_MM = 800.0
NEAR_MM = 100.0
BLOWUP_MM = 10_000.0
BLOWUP_VMS = 5.0


def num(v, cast=float):
    if v is None or v in ("n/a", "None", "-", ""):
        return None
    m = re.match(r"([-+]?\d+(?:\.\d+)?)", str(v))
    return cast(m.group(1)) if m else None


def parse(path: str) -> dict:
    legs, eps, lows = [], [], []
    dn = fell = 0
    open_row = None
    for line in open(path, errors="replace"):
        if m := CARRY.search(line):
            d = {"side": m["side"], "leg": m["leg"]}
            for tok in m["rest"].split():
                if "=" in tok:
                    k, _, v = tok.partition("=")
                    d[k] = v
            legs.append(d)
            open_row = d
        elif m := EP.search(line):
            eps.append(m.groupdict())
        elif m := PLOW.search(line):
            lows.append(int(m["ticks"]))
        elif "grasp did not land on the belt" in line:
            dn += 1
        elif "fell off the line" in line and "[rl] episode" not in line:
            fell += 1
    return {"path": path, "legs": legs, "eps": eps, "lows": lows,
            "did_not_land": dn, "fell_off": fell}


def klass(r: dict) -> str:
    slip = num(r.get("clean_slip_max")) or 0.0
    vmax = num(r.get("in-hand_vmax")) or 0.0
    if slip > BLOWUP_MM or vmax > BLOWUP_VMS:
        return "blowup"
    if slip > SLIDE_MM:
        return "slide"
    if slip > NEAR_MM:
        return "near"
    return "held"


def ledger(d: dict, side: str = "left") -> dict:
    rows = [r for r in d["legs"] if r["side"] == side and r["leg"].startswith("place")]
    out = {"n": len(rows), "rows": rows, "slide": [], "near": [], "held": [],
           "blowup": [], "micro": [], "loss": []}
    for r in rows:
        k = klass(r)
        onset = r.get("onset_row") not in (None, "None")
        if k == "held" and onset and (num(r.get("clean_slip_max")) or 0.0) > 2.0:
            # crossed the 2 mm crossing but came back inside 100 mm: a transient,
            # not a payload loss (the C_202 6.3 mm leg)
            k = "micro"
        out[k].append(r)
        if k in ("slide", "near"):
            out["loss"].append(r)
    return out


def walk_rate(r: dict) -> float | None:
    slip = num(r.get("clean_slip_max"))
    ticks = num((r.get("ticks") or "").split("/")[0])
    loss = num(r.get("loss_row"))
    if slip is None or ticks is None or loss is None or ticks <= loss:
        return None
    return slip / (ticks - loss)


def fisher(a: int, na: int, b: int, nb: int) -> float:
    """Two-sided Fisher exact p for a 2x2 (no scipy)."""
    def pmf(k: int, n: int, K: int, N: int) -> float:
        return comb(K, k) * comb(N - K, n - k) / comb(N, n)
    lo, hi = max(0, a + b - nb - na + min(na, nb)), min(a + b, na)
    tot = 0.0
    obs = pmf(a, na, a + b, na + nb)
    for k in range(0, min(na, a + b) + 1):
        p = pmf(k, na, a + b, na + nb)
        if p <= obs + 1e-12:
            tot += p
    return min(1.0, tot)


def med(vals):
    vals = [v for v in vals if v is not None]
    return st.median(vals) if vals else None


def fmt(v, f="{:.1f}") -> str:
    return f.format(v) if v is not None else "-"


def arm_of(path: str) -> str:
    return path.rsplit("/", 1)[-1].split("_")[0]


def seed_of(path: str) -> str:
    return path.rsplit("/", 1)[-1].split("_")[1].split(".")[0]


def show_ledger(label: str, d: dict) -> dict:
    L = ledger(d, "left")
    print(
        f"  {label:12s} legs {L['n']:2d}  loss {len(L['loss']):2d}/{L['n']:2d}  "
        f"| >800 {len(L['slide']):2d}  near {len(L['near']):2d}  "
        f"micro {len(L['micro']):2d}  held {len(L['held']):2d}  "
        f"blowup {len(L['blowup']):2d}"
    )
    return L


def main(argv: list[str]) -> int:
    paths = [a for a in argv if not a.startswith("--")]
    data = {p: parse(p) for p in paths}

    print("==== per (arm, seed) left place-leg ledger [loss = slide + near; "
          ">800 = the PREREG primary]")
    ledgers: dict[str, dict] = {}
    for p, d in data.items():
        label = f"{arm_of(p)}_{seed_of(p)}"
        ledgers[label] = show_ledger(label, d)

    print("\n==== the walk rate `clean_slip_max / (ticks - loss_row)` [mm/tick]")
    for p, d in data.items():
        esc = ledger(d)["loss"]
        rates = [walk_rate(r) for r in esc]
        ticks = [num((r.get("ticks") or "").split("/")[0]) for r in esc]
        print(
            f"  {arm_of(p)}_{seed_of(p):10s} rate median "
            f"{fmt(med(rates), '{:.2f}')} range "
            f"{fmt(min([v for v in rates if v is not None]), '{:.2f}')}.."
            f"{fmt(max([v for v in rates if v is not None]), '{:.2f}')}"
            f"   leg ticks median {fmt(med(ticks), '{:.0f}')}"
        )

    print("\n==== the schedule discriminator (registered, PREREG section 4.7)")
    for p, d in data.items():
        legs = ledger(d)["loss"]
        fr = []
        for r in legs:
            loss = num(r.get("loss_row"))
            ticks = num((r.get("ticks") or "").split("/")[0])
            if loss and ticks:
                fr.append(round(loss / ticks, 2))
        t45fr = []
        for r in ledger(d)["rows"]:
            t45 = num(r.get("t45"))
            ticks = num((r.get("ticks") or "").split("/")[0])
            if t45 and ticks:
                t45fr.append(round(t45 / ticks, 2))
        print(f"  {arm_of(p)}_{seed_of(p):10s} loss_row/ticks {fr}"
              f"   t45/ticks {t45fr}")

    print("\n==== pooled by arm")
    for arm in ("C", "S"):
        rows = [d for p, d in data.items() if arm_of(p) == arm]
        n = sum(ledger(d)["n"] for d in rows)
        esc = sum(len(ledger(d)["loss"]) for d in rows)
        sl = sum(len(ledger(d)["slide"]) for d in rows)
        nr = sum(len(ledger(d)["near"]) for d in rows)
        bu = sum(len(ledger(d)["blowup"]) for d in rows)
        lp = sum(1 for d in rows for e in d["eps"]
                 if e["arm"] == "left" and e["pl"] == "True")
        ln = sum(1 for d in rows for e in d["eps"] if e["arm"] == "left")
        rp = sum(1 for d in rows for e in d["eps"]
                 if e["arm"] == "right" and e["pl"] == "True")
        rn = sum(1 for d in rows for e in d["eps"] if e["arm"] == "right")
        ng = sum(1 for d in rows for e in d["eps"] if e["gra"] == "False")
        cnp = sum(1 for d in rows for e in d["eps"]
                  if e["gra"] == "True" and e["pl"] == "False")
        dn = sum(d["did_not_land"] for d in rows)
        fell = sum(d["fell_off"] for d in rows)
        lows = [v for d in rows for v in d["lows"]]
        ticks = [num((r.get("ticks") or "").split("/")[0])
                 for d in rows for r in ledger(d)["rows"]]
        print(
            f"  {arm}: left place legs {n}  escape {esc} ({esc / n:.0%})  "
            f">800 {sl} ({sl / n:.0%})  near {nr}  blowup {bu}  |  "
            f"left placed {lp}/{ln}  right placed {rp}/{rn}  "
            f"never-grasped {ng}  cnp {cnp}  did-not-land {dn}  fell-off {fell}"
        )
        print(
            f"       left place-leg ticks median {fmt(med(ticks), '{:.0f}')} "
            f"({fmt(min(ticks), '{:.0f}')}..{fmt(max(ticks), '{:.0f}')})  "
            f"`place low` descent ticks median {fmt(med(lows), '{:.0f}')} "
            f"(n={len(lows)})"
        )

    # the two registered contrasts, pooled
    pc = [d for p, d in data.items() if arm_of(p) == "C"]
    ps = [d for p, d in data.items() if arm_of(p) == "S"]
    nc = sum(ledger(d)["n"] for d in pc)
    ns = sum(ledger(d)["n"] for d in ps)
    ec = sum(len(ledger(d)["loss"]) for d in pc)
    es = sum(len(ledger(d)["loss"]) for d in ps)
    sc = sum(len(ledger(d)["slide"]) for d in pc)
    ss = sum(len(ledger(d)["slide"]) for d in ps)
    print("\n==== the two registered contrasts (pooled over 3 seeds)")
    print(f"  loss (slide+near, the mechanism):  C {ec}/{nc} vs S {es}/{ns}  "
          f"Fisher two-sided p = {fisher(ec, nc, es, ns):.3f}")
    print(f"  >800 mm (the PREREG primary):  C {sc}/{nc} vs S {ss}/{ns}  "
          f"Fisher two-sided p = {fisher(sc, nc, ss, ns):.3f}")

    print("\n==== per seed, the registered primary and the mechanism count")
    print("  seed   C >800 / legs   S >800 / legs   C loss    S loss")
    seeds = sorted({seed_of(p) for p in data})
    for s in seeds:
        c = next((d for p, d in data.items()
                  if arm_of(p) == "C" and seed_of(p) == s), None)
        t = next((d for p, d in data.items()
                  if arm_of(p) == "S" and seed_of(p) == s), None)
        if c is None or t is None:
            continue
        lc, lt = ledger(c), ledger(t)
        print(
            f"  {s:5s}  {len(lc['slide']):2d} / {lc['n']:2d}"
            f"          {len(lt['slide']):2d} / {lt['n']:2d}"
            f"          {len(lc['loss']):2d} / {lc['n']:2d}"
            f"     {len(lt['loss']):2d} / {lt['n']:2d}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
