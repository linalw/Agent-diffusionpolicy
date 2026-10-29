#!/usr/bin/env python3
"""P60 phase 3 report: the `[carry]` onset cell on the direct left.

Reads the registered cell (`logs/p60/p3/D_{77,101,202}.log`, FRUIT_CARRY_DIAG=1),
the F3 control (`logs/p59/p3/C_{77,101,202}.log`, diag off), the scripted
comparator (`logs/p41/p2/accept_profile.log`) and the P43 direct-left context
corpus (`logs/p43/p3/{A,B}_*.log`).

    python3 logs/p60/p3/report.py            # print
    python3 logs/p60/p3/report.py --check    # + structural assertions

Definitions are fixed in `logs/p60/PREREG_P3.md` §3 (written before the run):
a leg's class from its own `[carry]` row, an attempt's signature from its FIRST
escaping leg (a payload lost in `grasp_lift` necessarily starts `place0` already
out of the hand - the scripted comparator's own place0 rows show that).
"""

from __future__ import annotations

import argparse
import glob
import re
import statistics
import sys

CELL = ["logs/p60/p3/D_77.log", "logs/p60/p3/D_101.log", "logs/p60/p3/D_202.log"]
CTRL = ["logs/p59/p3/C_77.log", "logs/p59/p3/C_101.log", "logs/p59/p3/C_202.log"]
SCRIPTED = "logs/p41/p2/accept_profile.log"
CONTEXT = sorted(glob.glob("logs/p43/p3/A_*.log")) + sorted(glob.glob("logs/p43/p3/B_*.log"))

FORCE_CARRY = 2.0  # N, PREREG §3.3

_RE_OPEN = re.compile(
    r"\[rl\] episode (\d+): (\w+) grade=(\w) d=([\d.]+)cm bin=(\d) arm=(\w+) y="
)
_RE_CLOSE = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(\d) arm=(\w+) success=(\w+) "
    r"grasped=(\w+) placed=(\w+) ticks=(\d+) decision=(\d+) reward=([-\d.]+) "
    r"notes=\[(.*)\](?:\s+presentation=\S+)?(?:\s+ablate=\S+)?\s*$"
)
_RE_CARRY = re.compile(r"\[carry\] (\w+) (\w+): (.*)$")
_RE_FIELD = {
    "ticks": r"ticks=(\d+)/(\d+)",
    "clean_slip": r"clean_slip_max=([\d.]+)mm",
    "in_hand_vmax": r"in-hand_vmax=([\d.]+)",
    "onset_row": r"onset_row=(\d+|None)",
    "force_onset": r"force@onset=([\d.]+|n/a)N",
    "sep_onset": r"sep@onset=([\d.]+|n/a)mm",
    "contacts_onset": r"contacts@onset=(\d+|None)",
    "min_contacts": r"min_contacts=(\d+)",
    "force_min": r"force_min=([-\d.]+)N",
    "loss_row": r"loss_row=(\d+|None)",
    "sep_loss": r"sep@loss=([\d.]+|n/a)mm",
    "sep_end": r"sep_end=([\d.]+)mm",
    "guard": r"guard=(\d+)",
    "events": r"events=(\d+)",
    "holds": r"holds=(\d+)",
    "reseat": r"reseat=([\d.]+)mm",
    "relief": r"relief=(\d+)",
}
_RE_SCRIPTED_RELEASE = re.compile(r"released at \[[^\]]*\], placed=(\w+)")


def _num(tok: str, cast=float):
    return None if tok in (None, "None", "n/a") else cast(tok)


def parse_leg(rest: str) -> dict:
    out = {}
    for key, pat in _RE_FIELD.items():
        m = re.search(pat, rest)
        if not m:
            continue
        if key == "ticks":
            out["ticks"] = int(m.group(1))
            out["ticks_total"] = int(m.group(2))
        elif key in ("onset_row", "loss_row"):
            out[key] = _num(m.group(1), int)
        elif key in ("force_onset", "sep_onset", "sep_loss"):
            out[key] = _num(m.group(1))
        elif key in ("contacts_onset",):
            out[key] = _num(m.group(1), int)
        elif key in ("min_contacts",):
            out[key] = int(m.group(1))
        elif key in ("guard", "events", "holds", "relief"):
            out[key] = int(m.group(1))
        else:
            out[key] = float(m.group(1))
    return out


def leg_class(leg: dict) -> str:
    """PREREG §3.3."""
    if leg.get("onset_row") is None:
        return "no_slip"
    if leg.get("contacts_onset", 0) == 0:
        return "never_seated"
    f = leg.get("force_onset")
    if f is None:
        return "unknown"
    return "seated_then_slid" if f >= FORCE_CARRY else "marginal_contact"


def attempt_class(ep: dict) -> str:
    """PREREG §3.4: the first escaping leg's class, else no_slip."""
    for leg in ep["legs"]:
        c = leg_class(leg)
        if c != "no_slip":
            return c
    return "no_slip"


def parse_direct(path: str) -> list[dict]:
    eps: list[dict] = []
    cur = None
    with open(path, errors="replace") as fh:
        for line in fh:
            m = _RE_CLOSE.search(line)
            if m:
                if cur is None or cur["idx"] != int(m.group(1)):
                    cur = cur or {}
                cur.update(
                    idx=int(m.group(1)), fruit=m.group(2), d=float(m.group(3)),
                    bin=int(m.group(4)), arm=m.group(5),
                    success=m.group(6) == "True", grasped=m.group(7) == "True",
                    placed=m.group(8) == "True", ticks=int(m.group(9)),
                    decision=int(m.group(10)), reward=float(m.group(11)),
                    notes=m.group(12),
                )
                cur["grade"] = cur.get("grade", "?")
                eps.append(cur)
                cur = None
                continue
            m = _RE_OPEN.search(line)
            if m:
                cur = dict(
                    idx=int(m.group(1)), fruit=m.group(2), grade=m.group(3),
                    d=float(m.group(4)), bin=int(m.group(5)), arm=m.group(6),
                    legs=[],
                )
                continue
            m = _RE_CARRY.search(line)
            if m and cur is not None:
                leg = parse_leg(m.group(3))
                leg.update(side=m.group(1), name=m.group(2), line=line.rstrip())
                cur["legs"].append(leg)
    for ep in eps:
        ep.setdefault("legs", [])
    return eps


def outcome(ep: dict) -> str:
    if ep.get("placed"):
        return "placed"
    return "cnp" if ep.get("grasped") else "never-held"


def parse_scripted(path: str) -> list[dict]:
    """Scripted acceptance: attempts are groups of `[carry]` rows, ordered.

    A new attempt opens at a `grasp_lift` row; the outcome comes from the first
    `released at ... placed=<bool>` line after it.
    """
    rows = []
    with open(path, errors="replace") as fh:
        for line in fh:
            m = _RE_CARRY.search(line)
            if m:
                leg = parse_leg(m.group(3))
                leg.update(side=m.group(1), name=m.group(2), line=line.rstrip())
                rows.append(leg)
    attempts: list[dict] = []
    for leg in rows:
        if leg["name"] == "grasp_lift" or not attempts:
            attempts.append(dict(legs=[], released=None, fruit=None))
        attempts[-1]["legs"].append(leg)
    # outcome per attempt: the nth `released at` line belongs to the nth attempt
    releases = []
    with open(path, errors="replace") as fh:
        for line in fh:
            m = _RE_SCRIPTED_RELEASE.search(line)
            if m:
                releases.append(m.group(1) == "True")
    for i, att in enumerate(attempts):
        if i < len(releases):
            att["placed"] = releases[i]
    return attempts


def fmt_vals(vals, nd=2):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "n/a"
    if len(vals) == 1:
        return f"{vals[0]:.{nd}f}"
    return f"{statistics.median(vals):.{nd}f} [{min(vals):.{nd}f}-{max(vals):.{nd}f}]"


def table(eps: list[dict]) -> str:
    """Per-leg onset table (side, name, class, key fields)."""
    out = []
    for ep in eps:
        for leg in ep["legs"]:
            out.append((ep, leg, leg_class(leg)))
    return out


def leg_lost(leg: dict) -> bool:
    """W8-B escape evidence: contact loss recorded, or the force fell to zero."""
    return leg.get("loss_row") is not None or (leg.get("force_min") or 0.0) <= 0.0


def section_legs(title: str, eps: list[dict], arm: str = "left") -> None:
    print(f"\n== {title}: every {arm} carry leg ==")
    print("  ep fruit       outcome    leg         class             onset contacts "
          "F@on[N] Fmin[N] loss slip[mm] ticks")
    for ep in eps:
        if ep["arm"] != arm:
            continue
        if not ep["legs"]:
            print(f"  {ep['idx']:2d} {ep['fruit']:11s} {outcome(ep):10s} -           "
                  f"(no [carry] row: the primitive ran no carry leg)")
        for l in ep["legs"]:
            print(f"  {ep['idx']:2d} {ep['fruit']:11s} {outcome(ep):10s} "
                  f"{l['name']:11s} {leg_class(l):17s} "
                  f"{str(l.get('onset_row')):5s} {str(l.get('contacts_onset')):8s} "
                  f"{('%.2f' % l['force_onset']) if l.get('force_onset') is not None else 'n/a':>7s} "
                  f"{l.get('force_min', float('nan')):7.2f} "
                  f"{str(l.get('loss_row')):4s} {l.get('clean_slip', float('nan')):8.1f} "
                  f"{l.get('ticks')}/{l.get('ticks_total')}"
                  + ("  SPIKE" if (l.get("force_onset") or 0) > 30 else "")
                  + ("  LOST" if leg_lost(l) else ""))


def section_episodes(title: str, eps: list[dict]) -> None:
    print(f"\n== {title} ==")
    arms = sorted({e["arm"] for e in eps})
    for arm in arms:
        sub = [e for e in eps if e["arm"] == arm]
        counts = {k: sum(1 for e in sub if outcome(e) == k)
                  for k in ("placed", "cnp", "never-held")}
        print(f"  {arm:5s} n={len(sub):3d}  placed={counts['placed']:2d} "
              f"cnp={counts['cnp']:2d} never-held={counts['never-held']:2d}")
        # attempts with no carry leg, by outcome
        nol = [e for e in sub if not e["legs"]]
        if nol:
            print(f"        attempts with NO [carry] row: {len(nol)} "
                  f"({', '.join(sorted({outcome(e) for e in nol}))})")
        # attempt signature (rowless attempts are their own bucket, not no_slip)
        sig = {}
        for e in sub:
            key = attempt_class(e) if e["legs"] else "no_row"
            sig.setdefault(outcome(e), {}).setdefault(key, 0)
            sig[outcome(e)][key] += 1
        for oc in ("cnp", "placed", "never-held"):
            if oc in sig:
                items = ", ".join(f"{k}={v}" for k, v in sorted(sig[oc].items()))
                print(f"        {oc:10s} signature: {items}")
        # per-class fields
        for oc in ("cnp", "placed"):
            sel = [l for e in sub if outcome(e) == oc for l in e["legs"]
                   if leg_class(l) != "no_slip"]
            if sel:
                print(f"        {oc:10s} escaping legs n={len(sel)}: "
                      f"onset_row {fmt_vals([l.get('onset_row') for l in sel], 1)}; "
                      f"force@onset {fmt_vals([l.get('force_onset') for l in sel])}N; "
                      f"contacts@onset {fmt_vals([l.get('contacts_onset') for l in sel], 0)}; "
                      f"clean_slip {fmt_vals([l.get('clean_slip') for l in sel], 1)}mm; "
                      f"force_min {fmt_vals([l.get('force_min') for l in sel])}N; "
                      f"lost {sum(1 for l in sel if leg_lost(l))}/{len(sel)}")
        # leg-level counts by name
        per = {}
        for e in sub:
            for l in e["legs"]:
                per.setdefault(l["name"], {}).setdefault(leg_class(l), 0)
                per[l["name"]][leg_class(l)] += 1
        for name, cc in sorted(per.items()):
            print(f"        leg {name:11s}: " + ", ".join(f"{k}={v}" for k, v in sorted(cc.items())))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--cell", default="", help="override the registered cell logs")
    ap.add_argument("--ctrl", default="", help="override the F3 control logs")
    args = ap.parse_args()
    global CELL, CTRL
    if args.cell:
        CELL = args.cell.split(",")
    if args.ctrl:
        CTRL = args.ctrl.split(",")

    cell = [e for p in CELL for e in parse_direct(p)]
    ctrl = [e for p in CTRL for e in parse_direct(p)]
    if not cell:
        print("!! no episodes parsed from the registered cell", file=sys.stderr)
        return 2

    print("P60 phase 3 - the [carry] onset cell on the direct left")
    print(f"legs: onset trigger 2 mm; seated_then_slid needs contacts@onset >= 1 "
          f"and force@onset >= {FORCE_CARRY} N")

    # ---- P1 coverage ----
    print("\n== P1 coverage (registered cell) ==")
    for p in CELL:
        eps = parse_direct(p)
        legs = sum(len(e["legs"]) for e in eps)
        rows = sum(1 for e in eps for _ in e["legs"])
        fields = {"onset_row": 0, "contacts@onset": 0, "force@onset": 0, "clean_slip_max": 0}
        for e in eps:
            for l in e["legs"]:
                for f in fields:
                    key = {"clean_slip_max": "clean_slip"}.get(f, f.replace("@", "_"))
                    if key in l:
                        fields[f] += 1
        print(f"  {p}: episodes={len(eps)} carry_legs={legs} rows={rows} "
              f"fields={fields}")
    # per-leg names present, and the no-leg attempts' reason
    names = sorted({l["name"] for e in cell for l in e["legs"]})
    print(f"  leg names seen: {names}")
    nol = [e for e in cell if not e["legs"]]
    if nol:
        print(f"  no-row attempts: {len(nol)} -> "
              + ", ".join(f"{e['arm']}/{outcome(e)}" for e in nol))
    left = [e for e in cell if e["arm"] == "left"]
    print(f"  left attempts={len(left)} with_legs={sum(1 for e in left if e['legs'])}")
    # the knob must not actuate (PREREG §2: guard/relief unset -> guard=0 events=0 ...)
    all_legs = [l for e in cell for l in e["legs"]]
    actu = [l for l in all_legs
            if (l.get("guard") or 0) or (l.get("events") or 0) or (l.get("holds") or 0)
            or (l.get("reseat") or 0.0) or (l.get("relief") or 0)]
    print(f"  actuation check: {len(all_legs)} rows, rows with guard/events/holds/"
          f"reseat/relief != 0: {len(actu)} (want 0)")

    # ---- P2 split ----
    section_episodes("P2 split (registered cell, 3 seeds x 15)", cell)
    section_legs("P2 evidence (registered cell)", cell, "left")
    section_legs("P2 evidence (registered cell, the control arm)", cell, "right")

    # ---- P3 comparator ----
    print("\n== P3 comparator: scripted left (logs/p41/p2/accept_profile.log) ==")
    satt = parse_scripted(SCRIPTED)
    sleft = [a for a in satt if a["legs"][0]["side"] == "left"]
    print(f"  attempts={len(satt)} left_attempts={len(sleft)}")
    for i, a in enumerate(sleft):
        oc = "placed" if a.get("placed") else "escape"
        sig = "no_slip"
        for l in a["legs"]:
            if leg_class(l) != "no_slip":
                sig = f"{leg_class(l)} @{l['name']}"
                break
        legs = "; ".join(
            f"{l['name']}: onset={l.get('onset_row')} contacts={l.get('contacts_onset')}"
            f" F={l.get('force_onset')}N slip={l.get('clean_slip')}mm fmin={l.get('force_min')}N"
            for l in a["legs"]
        )
        print(f"  left attempt {i}: {oc:6s} signature={sig:24s} {legs}")
    sigs = {}
    for a in sleft:
        oc = "placed" if a.get("placed") else "escape"
        s = "no_slip"
        for l in a["legs"]:
            if leg_class(l) != "no_slip":
                s = leg_class(l)
                break
        sigs.setdefault(oc, {}).setdefault(s, 0)
        sigs[oc][s] += 1
    for oc, d in sigs.items():
        print(f"    scripted left {oc}: " + ", ".join(f"{k}={v}" for k, v in sorted(d.items())))

    # ---- P3b context: the P43 direct-left corpus ----
    print("\n== P3b context (not an endpoint): P43 direct-left, pre-P58 scenario ==")
    ctx = [e for p in CONTEXT for e in parse_direct(p)]
    if ctx:
        section_episodes("P43 A/B (context)", ctx)
    else:
        print("  (no episodes parsed)")

    # ---- F3 ----
    print("\n== F3 diag-vs-control class counts (instrumentation check) ==")
    section_episodes("P59 p3 control (diag off)", ctrl)

    # ---- checks ----
    if args.check:
        print("\n== structural assertions ==")
        ok = True
        for p in CELL:
            eps = parse_direct(p)
            cond = [
                (len(eps) == 15, f"{p}: episodes={len(eps)} (want 15)"),
                (all(e.get("ticks") for e in eps), f"{p}: every episode has ticks"),
                (all(outcome(e) != "cnp" or e["legs"] for e in eps),
                 f"{p}: every cnp attempt ran a carry leg"),
                (all(leg_class(l) != "unknown" for e in eps for l in e["legs"]),
                 f"{p}: every escaping leg classifies"),
                (not [l for e in eps for l in e["legs"]
                      if (l.get("guard") or 0) or (l.get("events") or 0)
                      or (l.get("holds") or 0) or (l.get("reseat") or 0.0)
                      or (l.get("relief") or 0)],
                 f"{p}: the diag did not actuate (guard/events/holds/reseat/relief all 0)"),
            ]
            for good, msg in cond:
                print(f"  {'PASS' if good else 'FAIL'}  {msg}")
                ok = ok and good
        if ok:
            print("  all assertions PASS")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
