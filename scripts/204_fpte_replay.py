#!/usr/bin/env python3
"""P7: FPTE Phase-0 offline replay (read-only, no simulator).

    python3 scripts/204_fpte_replay.py
    python3 scripts/204_fpte_replay.py --self-test

Implements the gate pre-registered in `logs/p7/PREREG_FPTE.md`, all of it pure
text parsing of existing logs plus one standalone replica of the R10-A
`_reach_predict` arithmetic (pure Python floats, no `fruit_sorting` import):

* P0.1 - reproduce the R11-A.1 eligible/feasible/chosen splits;
* P0.2 - the per-slot observable record (select / catch / met / catch-up /
  descent / handover / outcome / starved `active=` lists);
* P0.3 - the terminal-quantity separation test (patch battery, per arm);
* P0.4 - the re-rank test on the observed choice-vs-aim pairs
  (X: same aim machinery, different choice; A: same choice, different aim);
* P0.5 - the `_reach_predict` replica validation against every logged catch
  row of the R11-A.1 / R10-A.1 diag logs;
* the cost estimate (replica timing x K = 5, as a fraction of one tick) and
  the starved-slot brackets.

Read-only: writes nothing. The report goes to stdout and is embedded in
`logs/p7/C1_REPLAY.md` (evidence files are not rewritten). Run from the repo
root. Timing numbers are machine-dependent estimates; everything else is
deterministic parsing.
"""

from __future__ import annotations

import math
import re
import statistics
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# Pre-registered constants (logs/p7/PREREG_FPTE.md; tasks.py lines 356-434).
# --------------------------------------------------------------------------- #
REACH_SETUP_S = 0.60          # FRUIT_REACH_SETUP_S default
REACH_SELECT_S = 1.50         # FRUIT_REACH_SELECT_S / FRUIT_DYNAMIC_SELECT_S
REACH_MARGIN_S = 0.15         # FRUIT_REACH_MARGIN_S default
REACH_HOVER_SPEED = 0.80      # FRUIT_REACH_HOVER_SPEED default
SETTLE_S = 0.50               # FRUIT_REACH_HOVER_SETTLE=60 ticks
STATION = 0.0                 # single-arm station (cfg.pick_y), station-relative
FLOOR = 0.399                 # R11-A.1 reference floor: lead 0.189 + 1.5*0.12 + 0.03
BELT = 0.12                   # shipped scenario belt speed [m/s]
T_DESC_MODAL = 0.78           # modal logged descent estimate on the reach batteries [s]

#: The A1 corrected reach bands, `(x_hi, dn, up)` station-relative, per arm
#: (`tasks.py` `_reach_defaults` after the R10-A.1 band fix, inset 0.02).
BANDS = {
    "left": ((0.20, -0.08, 0.13), (0.28, -0.03, 0.08), (None, 0.02, 0.08)),
    "right": ((0.20, -0.08, 0.08), (0.28, -0.08, 0.03), (None, -0.08, -0.02)),
}

#: Per-log configuration: settle seconds armed by the run (0.0 = default off,
#: 0.5 = FRUIT_REACH_HOVER_SETTLE=60), run kind and battery.
LOGS = {
    "acc-floored-diag": ("logs/r11/A1_12_accept_floored_diag.log", 0.5, "reach", "acceptance"),
    "acc-floored-nosettle": ("logs/r11/A1_13_accept_floored_nosettle.log", 0.0, "reach", "acceptance"),
    "acc-control": ("logs/r11/A1_15_accept_control.log", 0.0, "control", "acceptance"),
    "acc-r11-cand": ("logs/r11/12_accept_reach_diag.log", 0.5, "reach", "acceptance"),
    "patch-floored": ("logs/r11/A1_20_patch_floored.log", 0.5, "reach", "patch"),
    "patch-armB": ("logs/r10/35_reach_settle60.log", 0.5, "reach", "patch"),
    "patch-r10-34": ("logs/r10/34_reach_bandfix.log", 0.0, "reach", "patch"),
    "patch-r10-31": ("logs/r10/31_reach.log", 0.0, "reach", "patch"),
    "patch-control": ("logs/r11/A1_25_patch_control.log", 0.0, "control", "patch"),
}

# --------------------------------------------------------------------------- #
# Parsing.
# --------------------------------------------------------------------------- #
RE_BELT = re.compile(r"surface velocity ([+\-0-9.]+) m/s")
RE_SELECT = re.compile(
    r"\[reach\] select station=([+\-0-9.]+) candidates_feasible=(\d+) "
    r"shipped_floor_ok=(\d+)(?: eligible=(\d+))? "
    r"chosen=(\w+|\w*None\w*) along=([0-9.]+|None) t_c=([0-9.]+|None)s"
)
RE_CATCH = re.compile(
    r"\[reach\] catch (\w+) idx=(\d+) y_fruit=([+\-0-9.]+) vy=([+\-0-9.]+) "
    r"y_int=([+\-0-9.]+) eq=([+\-0-9.]+) feasible=(\d) "
    r"band=\[([+\-0-9.]+),([+\-0-9.]+)\] t_desc=([0-9.]+)s"
)
RE_MET = re.compile(
    r"\[reach\] met (\w+) idx=(\d+) aim_y=([+\-0-9.]+) station=([+\-0-9.]+) "
    r"fruit_y=([+\-0-9.]+) err=([+\-0-9.]+) waited=(-?\d+)(?: catchup=(\d+))?"
)
RE_CATCHUP = re.compile(
    r"\[reach\] catchup (\w+) idx=(\d+) ticks=(\d+) residual=([0-9.]+)mm"
)
RE_DESC = re.compile(
    r"dynamic descent: waited (\d+) ticks, intercept=([+\-0-9.]+) m "
    r"\(station ([+\-0-9.]+), shift ([+\-0-9.]+) m\), fruit dy=([+\-0-9.]+) m, "
    r"deadline=([0-9.]+) m, t_desc=([0-9.]+) s"
)
RE_HANDOVER = re.compile(
    r"intercept handover: fruit_y=([+\-0-9.]+) dy=([+\-0-9.]+) m lead=([0-9.]+) m "
    r"at ([+\-0-9.]+) m/s \(fruit \|v_y\|=([0-9.]+) m/s, ratio ([0-9.]+)x, queue=(\d+)\)"
)
RE_PICK = re.compile(
    r"\[run\] attempt (\d+): picking (\w+) grade (\w+) into output lane (\d+)"
)
RE_OUTCOME = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([+\-0-9.]+) m "
    r"force=([0-9.]+) N notes=\[(.*?)\](?: sim=|$)"
)
RE_NOELIG = re.compile(
    r"\[run\] attempt (\d+): no eligible fruit; active=\[(.*?)\] stats="
)
RE_ACTIVE_ITEM = re.compile(r"\('([a-z]+)', ([+\-0-9.]+), ([0-9.]+)\)")
RE_TARGET = re.compile(r"\[task\] target (\w+) \(grade (\w+), ([0-9.]+) cm\) with (left|right) arm")
RE_RELEASE = re.compile(r"\[task\] released at \[(.*?)\], placed=(\w+) \((.*?)\)")


def parse_log(path: Path) -> list[dict]:
    """One entry per `[run] attempt`, with the per-attempt rows attached."""
    attempts: list[dict] = []
    cur: dict | None = None
    pending: dict | None = None
    belt = BELT
    for raw in path.read_text(errors="replace").splitlines():
        m = RE_BELT.search(raw)
        if m:
            belt = abs(float(m.group(1)))
        m = RE_SELECT.search(raw)
        if m:
            pending = dict(
                station=float(m.group(1)),
                n=int(m.group(2)),
                shipped=int(m.group(3)),
                eligible=(int(m.group(4)) if m.group(4) is not None else None),
                chosen=(None if "None" in m.group(5) else int(m.group(5))),
                along=(None if m.group(6) == "None" else float(m.group(6))),
                t_c=(None if m.group(7) == "None" else float(m.group(7))),
            )
            continue
        m = RE_NOELIG.search(raw)
        if m:
            cur = dict(
                index=int(m.group(1)), kind="no_eligible", select=pending,
                active=[
                    dict(cls=c, along=float(y), dia=float(d))
                    for c, y, d in RE_ACTIVE_ITEM.findall(m.group(2))
                ],
            )
            attempts.append(cur)
            pending = None
            continue
        m = RE_PICK.search(raw)
        if m:
            cur = dict(
                index=int(m.group(1)), kind="pick", cls=m.group(2),
                grade=m.group(3), lane=int(m.group(4)), select=pending,
            )
            attempts.append(cur)
            pending = None
            continue
        if cur is None:
            continue
        m = RE_OUTCOME.search(raw)
        if m and int(m.group(1)) == cur["index"] and "grasped" not in cur:
            cur["grasped"] = m.group(2) == "True"
            cur["placed"] = m.group(3) == "True"
            cur["notes"] = m.group(6).strip()
            continue
        m = RE_TARGET.search(raw)
        if m:
            cur["cls"] = m.group(1)
            cur["grade"] = m.group(2)
            cur["dia_cm"] = float(m.group(3))
            cur["arm"] = m.group(4)
            continue
        m = RE_CATCH.search(raw)
        if m:
            cur["catch"] = dict(
                arm=m.group(1), idx=int(m.group(2)), y_fruit=float(m.group(3)),
                vy=float(m.group(4)), y_int=float(m.group(5)), eq=float(m.group(6)),
                feasible=bool(int(m.group(7))),
                dn=float(m.group(8)), up=float(m.group(9)),
                t_desc=float(m.group(10)),
            )
            continue
        m = RE_MET.search(raw)
        if m:
            cur["met"] = dict(
                arm=m.group(1), idx=int(m.group(2)), aim=float(m.group(3)),
                station=float(m.group(4)), fruit_y=float(m.group(5)),
                err=float(m.group(6)), waited=int(m.group(7)),
                catchup=(int(m.group(8)) if m.group(8) else None),
            )
            continue
        m = RE_CATCHUP.search(raw)
        if m:
            cur["catchup"] = dict(ticks=int(m.group(3)), residual=float(m.group(4)))
            continue
        m = RE_DESC.search(raw)
        if m:
            cur["descent"] = dict(
                waited=int(m.group(1)), aim=float(m.group(2)),
                station=float(m.group(3)), shift=float(m.group(4)),
                fruit_dy=float(m.group(5)), deadline=float(m.group(6)),
                t_desc=float(m.group(7)),
            )
            continue
        m = RE_HANDOVER.search(raw)
        if m:
            cur["handover"] = dict(
                fruit_y=float(m.group(1)), dy=float(m.group(2)), lead=float(m.group(3)),
                belt_v=float(m.group(4)), fruit_v=float(m.group(5)),
                ratio=float(m.group(6)), queue=int(m.group(7)),
            )
            continue
        m = RE_RELEASE.search(raw)
        if m:
            cur["release"] = dict(placed=m.group(2) == "True", where=m.group(3))
    return attempts


# --------------------------------------------------------------------------- #
# The standalone `_reach_predict` replica (pure arithmetic; no simulator).
# --------------------------------------------------------------------------- #
def replica_eq(y_fruit: float, vy: float, t_desc: float, base_s: float,
               settle_s: float = 0.0, margin_s: float = REACH_MARGIN_S,
               hover_speed: float = REACH_HOVER_SPEED) -> float:
    """The `_reach_predict` fixed point, exactly as `tasks.py` iterates it."""
    if not math.isfinite(vy) or abs(vy) < 1e-6:
        vy = -BELT
    base = base_s + settle_s
    y = y_fruit + vy * (base + t_desc + margin_s)
    for _ in range(40):
        travel = abs(y - STATION) / hover_speed
        step = y_fruit + vy * (base + travel + t_desc + margin_s)
        if abs(step - y) < 1e-4:
            y = step
            break
        y = step
    return y


def band_for(arm: str, x: float) -> tuple[float, float]:
    for x_hi, dn, up in BANDS[arm]:
        if x_hi is None or float(x) <= float(x_hi) + 1e-9:
            return dn, up
    return BANDS[arm][-1][1], BANDS[arm][-1][2]


def clip(y: float, dn: float, up: float) -> float:
    return max(dn, min(up, y))


def m_band_of(eq: float, dn: float, up: float) -> float:
    """Reach margin of a planned terminal to the nearer band edge [m]."""
    return min(up - eq, eq - dn)


# --------------------------------------------------------------------------- #
# P0.1: the splits.
# --------------------------------------------------------------------------- #
def splits(name: str, attempts: list[dict]) -> None:
    selects = [a["select"] for a in attempts if a.get("select")]
    picks = [a for a in attempts if a["kind"] == "pick"]
    starved = [a for a in attempts if a["kind"] == "no_eligible"]
    inst_n = sum(1 for s in selects if s["n"] > 0)
    inst_sh = sum(1 for s in selects if s["shipped"] > 0)
    inst_el = sum(1 for s in selects if (s["eligible"] or 0) > 0)
    sum_n = sum(s["n"] for s in selects)
    sum_sh = sum(s["shipped"] for s in selects)
    sum_el = sum(s["eligible"] or 0 for s in selects if s["eligible"] is not None)
    alongs = sorted(s["along"] for s in selects if s["along"] is not None)
    aims = sorted(a["catch"]["y_int"] for a in picks if a.get("catch"))
    inside = sum(1 for s in selects if s["along"] is not None and s["along"] < FLOOR)
    max_feas = max((s["n"] for s in selects), default=0)
    max_elig = max(((s["eligible"] or 0) for s in selects if s["eligible"] is not None), default=0)

    def p50(v):
        return v[len(v) // 2] if v else float("nan")

    print(f"  [{name}] attempts={len(attempts)} picks={len(picks)} starved={len(starved)}")
    if selects:
        el_txt = f" eligible={sum_el}" if any(s["eligible"] is not None for s in selects) else " eligible=-"
        el_gain = (sum_el - sum_sh) if any(s["eligible"] is not None for s in selects) else None
        print(
            f"    instants reach/shipped/eligible={inst_n}/{inst_sh}/{inst_el} "
            f"sums feasible={sum_n} shipped={sum_sh}{el_txt}"
            f" instants_gain={inst_n - inst_sh:+d}"
            + ("" if el_gain is None else f" eligible_sums_gain={el_gain:+d}")
        )
        print(
            f"    chosen along min/p50/max="
            f"{min(alongs):.3f}/{p50(alongs):.3f}/{max(alongs):.3f} inside_floor={inside}/{len(alongs)}"
        )
        print(f"    max per-slot feasible={max_feas} eligible={max_elig}")
    if aims:
        print(f"    aims min/p50/max={min(aims):+.3f}/{p50(aims):+.3f}/{max(aims):+.3f}")


# --------------------------------------------------------------------------- #
# P0.2: per-slot record.
# --------------------------------------------------------------------------- #
def slot_line(name: str, a: dict) -> str:
    i = a["index"]
    arm = (a.get("arm") or (a.get("catch") or {}).get("arm") or "?")[0].upper()
    if a["kind"] == "no_eligible":
        act = ", ".join(f"{x['cls']}@{x['along']:.3f}" for x in a.get("active", []))
        return f"  {name} a{i:02d} {arm} NO-ELIGIBLE active=[{act}]"
    cls = a.get("cls", "?")
    s = a.get("select") or {}
    bits = [
        f"sel(along={s.get('along')} t_c={s.get('t_c')} "
        f"f={s.get('n')} sh={s.get('shipped')} el={s.get('eligible')})"
    ]
    c = a.get("catch")
    if c:
        bits.append(
            f"catch(int={c['y_int']:+.4f} eq={c['eq']:+.4f} "
            f"band[{c['dn']:+.3f},{c['up']:+.3f}] d={c['t_desc']:.2f})"
        )
    mt = a.get("met")
    if mt:
        bits.append(f"met(err={mt['err'] * 1000:+.1f}mm w={mt['waited']})")
    cu = a.get("catchup")
    if cu:
        bits.append(f"cu({cu['ticks']}t {cu['residual']:.1f}mm)")
    d = a.get("descent")
    if d:
        bits.append(f"aim={d['aim']:+.4f} fdy={d['fruit_dy']:+.4f} dl={d['deadline']:.4f}")
    placed = a.get("placed")
    bits.append(f"placed={placed}")
    if a.get("notes"):
        bits.append(f"notes=[{a['notes']}]")
    return f"  {name} a{i:02d} {arm} {cls} " + " ".join(bits)


# --------------------------------------------------------------------------- #
# P0.3: separation.
# --------------------------------------------------------------------------- #
def component_table(a: dict) -> dict | None:
    c, mt, d, s = a.get("catch"), a.get("met"), a.get("descent"), a.get("select")
    if a["kind"] != "pick" or a.get("placed") is None:
        return None
    row: dict = {"placed": bool(a["placed"]), "arm": a.get("arm")}
    if c:
        row["m_band"] = m_band_of(c["eq"], c["dn"], c["up"])
        row["m_res"] = abs(c["eq"] - c["y_int"])
    if mt:
        row["err"] = abs(mt["err"])
        row["waited"] = mt["waited"]
    cu = a.get("catchup")
    if cu:
        row["cu_ticks"] = cu["ticks"]
        row["cu_res"] = cu["residual"]
    if d:
        row["deadline_h"] = d["deadline"] - abs(d["fruit_dy"])
    if s and s.get("t_c") is not None:
        row["t_c"] = s["t_c"]
    return row


def separation(name: str, attempts: list[dict]) -> list[str]:
    rows = [component_table(a) for a in attempts]
    rows = [r for r in rows if r]
    keys = ("m_band", "m_res", "err", "waited", "cu_ticks", "cu_res", "deadline_h", "t_c")
    verdicts = []
    print(f"  [{name}] separation (placed vs failed ranges, disjoint = separates)")
    for arm in ("left", "right", None):
        sel = [r for r in rows if r["arm"] == arm] if arm else rows
        if arm is None:
            continue
        ok = [r for r in sel if r["placed"]]
        bad = [r for r in sel if not r["placed"]]
        if len(ok) < 2 or len(bad) < 2:
            print(f"    {arm}: n_placed={len(ok)} n_failed={len(bad)} (not usable)")
            continue
        flags = []
        for k in keys:
            vo = [r[k] for r in ok if k in r]
            vb = [r[k] for r in bad if k in r]
            if not vo or not vb:
                continue
            sep = max(vo) < min(vb) or max(vb) < min(vo)
            flags.append(f"{k}: {'SEP' if sep else 'ovl'} "
                         f"[{min(vo):.3f},{max(vo):.3f}]vs[{min(vb):.3f},{max(vb):.3f}]")
            if sep:
                verdicts.append(f"{name}:{arm}:{k}")
        print(f"    {arm}: n_placed={len(ok)} n_failed={len(bad)} " + " | ".join(flags))
    return verdicts


# --------------------------------------------------------------------------- #
# P0.4: the pair tests.
# --------------------------------------------------------------------------- #
def pair_type_x(name_a: str, att_a: list[dict], name_b: str, att_b: list[dict]) -> list[str]:
    """Same aim machinery, different choice (both reach runs)."""
    by_b = {a["index"]: a for a in att_b}
    first_div = None
    for a in att_a:
        b = by_b.get(a["index"])
        if a["kind"] != "pick" or b is None or b["kind"] != "pick":
            continue
        if (a.get("cls"), a.get("catch", {}).get("idx")) != (b.get("cls"), b.get("catch", {}).get("idx")):
            first_div = a["index"]
            break
    print(f"  [{name_a} vs {name_b}] type X (choice varies, aim held); "
          f"first divergent choice at attempt {first_div}")
    flips = []
    for a in att_a:
        if a["kind"] != "pick" or not a.get("catch"):
            continue
        b = by_b.get(a["index"])
        if b is None or b["kind"] != "pick" or not b.get("catch"):
            continue
        ca, cb = a["catch"], b["catch"]
        ia = (ca["idx"], a.get("cls"))
        ib = (cb["idx"], b.get("cls"))
        sa = (m_band_of(ca["eq"], ca["dn"], ca["up"]), -abs(ca["eq"] - ca["y_int"]),
              -(a["select"]["t_c"] if a.get("select") and a["select"].get("t_c") is not None else 0.0))
        sb = (m_band_of(cb["eq"], cb["dn"], cb["up"]), -abs(cb["eq"] - cb["y_int"]),
              -(b["select"]["t_c"] if b.get("select") and b["select"].get("t_c") is not None else 0.0))
        aligned = first_div is None or a["index"] < first_div
        disc = (a.get("placed") != b.get("placed"))
        pref = name_a if sa > sb else (name_b if sb > sa else "tie")
        verdict = ""
        if disc:
            winner = name_a if a.get("placed") else name_b
            verdict = "CORRECT" if pref == winner else ("tie" if pref == "tie" else "INVERTED")
            if verdict == "CORRECT":
                flips.append((a["index"], a.get("cls"), b.get("cls")))
        print(
            f"    a{a['index']:02d} {'aligned' if aligned else 'cross  '} "
            f"| {name_a}: idx{ca['idx']} along={a['select']['along'] if a.get('select') else '?'} "
            f"t_c={a['select']['t_c'] if a.get('select') else '?'} S=({sa[0] * 1000:+.1f}mm,{sa[1] * 1000:+.1f}mm,{-sa[2]:.2f}s) "
            f"placed={a.get('placed')} "
            f"| {name_b}: idx{cb['idx']} along={b['select']['along'] if b.get('select') else '?'} "
            f"t_c={b['select']['t_c'] if b.get('select') else '?'} S=({sb[0] * 1000:+.1f}mm,{sb[1] * 1000:+.1f}mm,{-sb[2]:.2f}s) "
            f"placed={b.get('placed')} "
            f"| {'disc' if disc else 'both-same-outcome'} pref={pref} {verdict}"
        )
    return [f"{name_a}/{name_b} a{i} {ca}->{cb}" for i, ca, cb in flips]


def pair_type_a(name_r: str, att_r: list[dict], name_c: str, att_c: list[dict]) -> list[str]:
    """Same fruit (arm+class+grade+diameter matched proxy), different aim:
    reach `y_int` vs the other run's descent aim."""
    by_c = {a["index"]: a for a in att_c}
    print(f"  [{name_r} vs {name_c}] type A (aim varies, same-fruit proxy)")
    flips = []
    for a in att_r:
        if a["kind"] != "pick" or not a.get("catch"):
            continue
        c = a["catch"]
        ctl = by_c.get(a["index"])
        if ctl is None or ctl["kind"] != "pick" or not ctl.get("descent"):
            continue
        sig_r = (a.get("cls"), a.get("grade"), a.get("dia_cm"), a.get("arm"))
        sig_c = (ctl.get("cls"), ctl.get("grade"), ctl.get("dia_cm"), ctl.get("arm"))
        if sig_r != sig_c:
            continue
        exact = all(sig_r) and sig_r[:3] == sig_c[:3] and sig_r[3] == sig_c[3]
        aim_r, aim_c = c["y_int"], ctl["descent"]["aim"]
        mr = m_band_of(aim_r, c["dn"], c["up"])
        mc = m_band_of(aim_c, c["dn"], c["up"])
        disc = (a.get("placed") != ctl.get("placed"))
        pref = name_r if mr > mc else (name_c if mc > mr else "tie")
        verdict = ""
        if disc:
            winner = name_r if a.get("placed") else name_c
            verdict = "CORRECT" if pref == winner else ("tie" if pref == "tie" else "INVERTED")
            if verdict == "CORRECT" and exact:
                flips.append(a["index"])
        print(
            f"    a{a['index']:02d} {a.get('cls')}/{a.get('grade')}/{a.get('dia_cm')}/{a.get('arm')} "
            f"sig={'exact' if exact else 'class-only'} "
            f"reach aim={aim_r:+.4f} m_band={mr * 1000:+.1f}mm placed={a.get('placed')} "
            f"| other aim={aim_c:+.4f} m_band={mc * 1000:+.1f}mm placed={ctl.get('placed')} "
            f"| {'disc' if disc else 'both-same-outcome'} pref={pref} {verdict}"
        )
    return flips


# --------------------------------------------------------------------------- #
# Starved-slot brackets.
# --------------------------------------------------------------------------- #
def starved_brackets(name: str, attempts: list[dict], settle: float) -> None:
    for a in attempts:
        if a["kind"] != "no_eligible" or not a.get("active"):
            continue
        print(f"  [{name}] a{a['index']:02d} starved; terminal bracket "
              f"(base={REACH_SELECT_S + settle:.2f}s, t_desc={T_DESC_MODAL}s, vy=-{BELT:.2f}):")
        for item in a["active"]:
            eq = replica_eq(item["along"], -BELT, T_DESC_MODAL, REACH_SELECT_S, settle)
            if item["along"] < FLOOR:
                row = [f"{item['cls']}@{item['along']:.3f} d={item['dia']:.3f} eq={eq:+.4f}"]
                for arm in ("left", "right"):
                    for (x_hi, _dn, _up) in BANDS[arm]:
                        probe_x = 0.40 if x_hi is None else float(x_hi)
                        dn, up = band_for(arm, probe_x)
                        row.append(
                            f"{arm}[x<={'-' if x_hi is None else f'{x_hi:.2f}'}] "
                            f"m_band={m_band_of(eq, dn, up) * 1000:+.0f}mm"
                        )
                print("      " + " | ".join(row))


# --------------------------------------------------------------------------- #
# Main.
# --------------------------------------------------------------------------- #
def main() -> int:
    root = Path(__file__).resolve().parent.parent
    data: dict[str, list[dict]] = {}
    for name, (rel, settle, kind, battery) in LOGS.items():
        path = root / rel
        if not path.exists():
            print(f"  [{name}] MISSING {rel}")
            continue
        data[name] = parse_log(path)

    print("== P0.5 replica validation (`_reach_predict`, base=0.60+settle) ==")
    ok_all = True
    for name, (rel, settle, kind, battery) in LOGS.items():
        if kind != "reach" or name not in data:
            continue
        deltas, exact, n = [], 0, 0
        for a in data[name]:
            c = a.get("catch")
            if not c:
                continue
            eq_rep = replica_eq(c["y_fruit"], c["vy"], c["t_desc"], REACH_SETUP_S, settle)
            d = abs(eq_rep - c["eq"])
            deltas.append(d)
            if abs(clip(eq_rep, c["dn"], c["up"]) - c["y_int"]) < 1.5e-3:
                exact += 1
            n += 1
        if not n:
            continue
        med = statistics.median(deltas) * 1000
        p95 = sorted(deltas)[int(0.95 * (n - 1))] * 1000
        frac = sum(1 for d in deltas if d <= 1.5e-3) / n
        ok = frac >= 0.95
        ok_all &= ok
        print(f"  [{name}] rows={n} median|d|={med:.2f}mm p95={p95:.2f}mm "
              f"max={max(deltas) * 1000:.2f}mm <=1.5mm={frac * 100:.0f}% "
              f"y_int<=1.5mm={exact}/{n} {'PASS' if ok else 'FAIL'}")
    print(f"  P0.5 {'PASS' if ok_all else 'FAIL'}")

    print("\n== P0.1 splits reproduction (R11-A.1 section 2) ==")
    for name in ("acc-floored-diag", "patch-floored", "patch-armB"):
        if name in data:
            splits(name, data[name])

    print("\n== P0.2 per-slot records ==")
    for name in ("acc-floored-diag", "patch-floored", "patch-armB"):
        if name not in data:
            continue
        print(f"  -- {name}")
        for a in data[name]:
            print(slot_line(name, a))

    print("\n== P0.3 separation (patch battery) ==")
    sep_verdicts = []
    for name in ("patch-floored", "patch-armB"):
        if name in data:
            sep_verdicts += separation(name, data[name])
    if not sep_verdicts:
        print("  no component separates (see rows above)")

    print("\n== planned-terminal margins (score m_band of eq) and aim clipping ==")
    for name in ("acc-floored-diag", "patch-floored", "patch-armB"):
        if name not in data:
            continue
        aims = [a["catch"] for a in data[name] if a["kind"] == "pick" and a.get("catch")]
        clipped = sum(1 for c in aims if abs(c["y_int"] - c["up"]) < 1e-9 or abs(c["y_int"] - c["dn"]) < 1e-9)
        print(f"  [{name}] aims={len(aims)} clipped-at-edge={clipped} "
              f"m_band min/p50/max="
              f"{min(m_band_of(c['eq'], c['dn'], c['up']) for c in aims) * 1000:+.1f}/"
              f"{statistics.median(m_band_of(c['eq'], c['dn'], c['up']) for c in aims) * 1000:+.1f}/"
              f"{max(m_band_of(c['eq'], c['dn'], c['up']) for c in aims) * 1000:+.1f} mm")

    print("\n== P0.4 re-rank pairs ==")
    flips_x, flips_a = [], []
    if "patch-floored" in data and "patch-armB" in data:
        flips_x = pair_type_x("patch-floored", data["patch-floored"],
                              "patch-armB", data["patch-armB"])
    if "acc-floored-diag" in data and "acc-control" in data:
        flips_a += pair_type_a("acc-floored-diag", data["acc-floored-diag"],
                               "acc-control", data["acc-control"])
    if "acc-floored-diag" in data and "acc-r11-cand" in data:
        flips_a += pair_type_a("acc-floored-diag", data["acc-floored-diag"],
                               "acc-r11-cand", data["acc-r11-cand"])
    print(f"  correct discriminating flips: type-X={flips_x} type-A={flips_a}")

    print("\n== starved-slot brackets ==")
    for name in ("acc-floored-diag", "patch-floored"):
        if name in data:
            starved_brackets(name, data[name], LOGS[name][1])

    print("\n== cost estimate (replica timing; machine-dependent) ==")
    t0 = time.perf_counter()
    reps = 200000
    acc = 0.0
    for _ in range(reps):
        acc += replica_eq(0.4563, -0.12, 0.78, REACH_SETUP_S, SETTLE_S)
    dt = time.perf_counter() - t0
    per_call = dt / reps
    per_slot = per_call * 5
    tick = 1.0 / 120.0
    print(f"  {reps} replica calls in {dt:.3f}s -> {per_call * 1e6:.2f} us/call; "
          f"K=5 -> {per_slot * 1e6:.1f} us/slot = {per_slot / tick * 100:.4f}% of one tick "
          f"(acc={acc:.3f})")
    print("   cache: one transient pred dict per candidate at selection; the chosen aim "
          "cached per attempt (the `_reach_aim_point` pattern) -> no per-tick reads.")
    return 0


def self_test() -> int:
    sample = "\n".join([
        "[fruit] cleated belt built: 0 cleats, spacing 0.18 m, surface velocity -0.12 m/s, mu=0.9",
        "[fruit] [reach] select station=+0.00 candidates_feasible=2 shipped_floor_ok=1 "
        "eligible=1 chosen=4 along=0.411 t_c=1.917s",
        "[fruit] [run] attempt 0: picking apple grade A into output lane 0 at (0.43, 0.5)",
        "[fruit] [reach] catch left idx=4 y_fruit=+0.3200 vy=-0.1200 y_int=+0.1000 "
        "eq=+0.1000 feasible=1 band=[-0.060,+0.130] t_desc=0.70s",
        "[fruit] [task] dynamic descent: waited 42 ticks, intercept=+0.1000 m "
        "(station +0.0000, shift +0.1000 m), fruit dy=+0.0830 m, deadline=0.1010 m, t_desc=0.68 s",
        "[fruit] [reach] met left idx=4 aim_y=+0.1000 station=+0.0000 fruit_y=+0.0980 "
        "err=-0.0020 waited=42",
        "[fruit] [reach] catchup left idx=4 ticks=17 residual=5.9mm",
        "[fruit] [task] intercept handover: fruit_y=0.3163 dy=+0.1882 m lead=0.189 m "
        "at -0.120 m/s (fruit |v_y|=0.120 m/s, ratio 1.00x, queue=3)",
        "[fruit] [run] attempt 0: grasped=True placed=True lift=+0.251 m force=5.00 N "
        "notes=[] sim=13.4-28.1",
        "[fruit] [reach] select station=+0.00 candidates_feasible=0 shipped_floor_ok=0 "
        "eligible=0 chosen=None along=None t_c=Nones",
        "[fruit] [run] attempt 1: no eligible fruit; active=[('apple', -0.635, 0.07), "
        "('kiwi', 0.374, 0.054)] stats={'released': 21}",
    ])
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as handle:
        handle.write(sample)
        path = Path(handle.name)
    attempts = parse_log(path)
    assert len(attempts) == 2, f"attempts {len(attempts)}"
    a0, a1 = attempts
    assert a0["kind"] == "pick" and a0["select"]["eligible"] == 1
    assert a0["catch"]["eq"] == 0.1 and a0["met"]["waited"] == 42
    assert a0["catchup"]["ticks"] == 17 and a0["descent"]["deadline"] == 0.101
    assert a0["handover"]["ratio"] == 1.0 and a0["placed"] is True
    assert a1["kind"] == "no_eligible" and a1["select"]["chosen"] is None
    assert len(a1["active"]) == 2 and a1["active"][1]["along"] == 0.374
    eq = replica_eq(0.4563, -0.12, 0.78, REACH_SETUP_S, SETTLE_S)
    assert abs(eq - 0.1855) < 1.5e-3, f"replica eq {eq}"
    print("204_fpte_replay self-test PASS")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    raise SystemExit(main())
