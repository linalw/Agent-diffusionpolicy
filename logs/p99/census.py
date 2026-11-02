"""P99 census: the two-line slot wait, its split, and the candidate set.

Two layers:

* **timeline** (every record, no new row needed): per arm, the slot chain
  attempt -> park -> feed -> polls -> next attempt. The attempt END is the
  `park wait start` timestamp (`FRUIT_BIARM_PARK_TRACE=1`), the attempt SPAN is
  the `result ... sim=` value, and the placement instant is the attempt end
  minus the `[cycle]` `return`+`end` blocks, so the inter-placement interval is
  recomputable and can be checked against the published value.
* **decision** (only the `FRUIT_BED_DIAG=2` cells): at every slot's selection,
  the live fruit list with grade / along / x / z / r and the first predicate
  that refused each one, plus the selector floor. That is the candidate set the
  question is about: was there a fruit this arm could have taken under a
  different assignment?

Reported, per cell and pooled:

  A. the wait the arm paid, split into park-gate / park-motion / feed /
     starved polls / selection;
  B. the candidate read: how often the arm's own lane had nothing at/above the
     floor while a cross-lane fruit did, and by how much sooner that fruit
     would have arrived (both in metres of belt and in seconds);
  C. the convertible seconds per mechanism, and each as a share of the
     inter-placement interval.

Run:  python3 logs/p99/census.py logs/p99/C5.log logs/p99/C6.log
      python3 logs/p99/census.py --same <cell.log> <record.log>
"""
from __future__ import annotations

import argparse
import re
import sys

# ---------------------------------------------------------------- parsers ----
ACQ = re.compile(r"\[biarm\] (\w+): station acquired at t=([0-9.]+)s")
POLL = re.compile(r"\[biarm\] (\w+): no eligible fruit")
PARK = re.compile(
    r"\[biarm\] (\w+): park (wait start|moving|done) t=([0-9.]+)s"
    r"(?: \(waited (\d+) ticks\))?"
)
CYCLE = re.compile(r"\[cycle\] attempt (\d+): (.+?) total=([0-9.]+)s")
RESULT = re.compile(
    r"\[biarm\] result (\w+) index=(\d+) (\w+) grasped=(\w+) placed=(\w+) "
    r"lift=([+-][0-9.]+) force=([0-9.]+) sim=([0-9.]+)s(?: notes=(\[.*\]))?"
)
SEL_SUM = re.compile(
    r"\[bed-sel\] arm=(\w+) slot=(\d+) t=([0-9.]+) live=(\d+) on_belt=(\d+) "
    r"admitted=(\d+) window=(\d+) band=(\d+)/(\d+) pick=(\S+)"
)
SEL_HDR = re.compile(
    r"\[bed-sel\]\s+arm=(\w+) t=([0-9.]+) floor=([+-][0-9.]+) "
    r"station=([+-][0-9.]+) v=([0-9.]+) belt_top=([0-9.]+) pure=(\d+) "
    r"prot=\[([^\]]*)\]"
)
SEL_ROW = re.compile(
    r"\[bed-sel\]\s+arm=(\w+) idx=(\d+) grade=(\w) (\w+)\s+along=([+-][0-9.]+) "
    r"x=([0-9.]+) z=([0-9.]+) r=([0-9.]+) -> (.*)"
)
TARGET = re.compile(r"\[task\] target (\w+) \(grade (\w), ([0-9.]+) cm\) with (\w+) arm")
BLOCK = re.compile(r"(\w+)=([0-9.]+)s")

#: The pools' largest fruit is 6.9 cm (`FRUIT_GRIPPER_MAX_OBJECT` admits every
#: supplied instance; the census reports any `too big` / `off belt` row so the
#: class cannot be silently non-empty).
GRIPPER_MAX = 0.080


def _blocks(text: str) -> dict[str, float]:
    return {k: float(v) for k, v in BLOCK.findall(text)}


def parse(path: str) -> dict:
    rec = {
        "path": path,
        "slots": {"left": [], "right": []},
        "cycles": [],
        "results": [],
        "parks": {"left": [], "right": []},
        "decisions": [],
    }
    pending = {"left": None, "right": None}
    cur = None  # the decision being assembled
    for line in open(path, errors="replace"):
        if not line.startswith("[fruit]"):
            continue
        m = ACQ.search(line)
        if m:
            arm, t = m.group(1), float(m.group(2))
            slot = {"t": t, "arm": arm, "poll": False, "target": None,
                    "span": None, "res": None, "decision": None}
            pending[arm] = slot
            rec["slots"][arm].append(slot)
            cur = None
            continue
        m = POLL.search(line)
        if m and pending[m.group(1)] is not None:
            pending[m.group(1)]["poll"] = True
            continue
        m = PARK.search(line)
        if m:
            rec["parks"][m.group(1)].append(
                (m.group(2), float(m.group(3)),
                 int(m.group(4)) if m.group(4) else None)
            )
            continue
        m = TARGET.search(line)
        if m and pending[m.group(4)] is not None:
            pending[m.group(4)]["target"] = (m.group(1), m.group(2), float(m.group(3)))
            continue
        m = CYCLE.search(line)
        if m:
            rec["cycles"].append((int(m.group(1)), _blocks(m.group(2)),
                                  float(m.group(3))))
            continue
        m = RESULT.search(line)
        if m:
            rec["results"].append(
                dict(arm=m.group(1), index=int(m.group(2)), category=m.group(3),
                     grasped=m.group(4) == "True", placed=m.group(5) == "True",
                     lift=float(m.group(6)), force=float(m.group(7)),
                     span=float(m.group(8)), notes=m.group(9) or "")
            )
            continue
        m = SEL_SUM.search(line)
        if m:
            cur = {
                "arm": m.group(1), "slot": int(m.group(2)), "t": float(m.group(3)),
                "live": int(m.group(4)), "on_belt": int(m.group(5)),
                "admitted": int(m.group(6)), "window": int(m.group(7)),
                "band": (int(m.group(8)), int(m.group(9))), "pick": m.group(10),
                "floor": None, "station": None, "v": None, "belt_top": None,
                "pure": None, "prot": [], "rows": [],
            }
            rec["decisions"].append(cur)
            continue
        m = SEL_HDR.search(line)
        if m and cur is not None:
            cur.update(arm=m.group(1), floor=float(m.group(3)),
                       station=float(m.group(4)), v=float(m.group(5)),
                       belt_top=float(m.group(6)), pure=int(m.group(7)),
                       prot=[int(x) for x in re.findall(r"\d+", m.group(8))])
            continue
        m = SEL_ROW.search(line)
        if m and cur is not None:
            cur["rows"].append(
                dict(arm=m.group(1), idx=int(m.group(2)), grade=m.group(3),
                     cat=m.group(4), along=float(m.group(5)), x=float(m.group(6)),
                     z=float(m.group(7)), r=float(m.group(8)),
                     reason=m.group(9).strip())
            )
            continue

    # join results to attempt slots (in order, per arm) and cycles
    for arm in ("left", "right"):
        rs = [r for r in rec["results"] if r["arm"] == arm]
        att = [s for s in rec["slots"][arm] if not s["poll"]]
        for slot, res in zip(att, rs):
            slot["span"] = res["span"]
            slot["res"] = res
    # the cycles are in global order; each names the arm via its result
    for cyc, res in zip(rec["cycles"], rec["results"]):
        res["cycle"] = cyc[1]
        res["cycle_total"] = cyc[2]
    # attach each decision to the slot at the same (arm, tick). The slot's
    # timestamp is printed with one decimal and the census row's with two, so
    # the join is nearest-within-0.1 s, not an equality on the rounded text.
    for arm in ("left", "right"):
        slots = sorted(rec["slots"][arm], key=lambda x: x["t"])
        for d in (x for x in rec["decisions"] if x["arm"] == arm):
            best = None
            for s in slots:
                dt = abs(s["t"] - d["t"])
                if dt <= 0.10 and (best is None or dt < best[0]):
                    best = (dt, s)
            if best is not None and best[1]["decision"] is None:
                best[1]["decision"] = d
    return rec


# ------------------------------------------------------------- timeline ------
def timeline(rec: dict) -> dict:
    """Per-arm slot chain: the wait between two attempt starts, split."""
    out = {"left": [], "right": []}
    for arm in ("left", "right"):
        slots = rec["slots"][arm]
        parks = rec["parks"][arm]
        pw_ticks = None
        pi = 0
        for i, s in enumerate(slots):
            if s["poll"] or s["span"] is None:
                continue
            end = s["t"] + s["span"]
            # the park that belongs to this attempt: the `wait start` at/after
            # the attempt's end, then its own `moving` and `done`. The pointer
            # advances past the consumed `done`, so a slot whose park never
            # printed (the arm was already at ready) cannot borrow the next one.
            pw = pm = pd = None
            while pi < len(parks) and parks[pi][0] != "wait start":
                pi += 1
            if pi < len(parks) and abs(parks[pi][1] - end) <= 2.0:
                pw = parks[pi][1]
                j = pi + 1
                while j < len(parks) and parks[j][0] != "done":
                    if parks[j][0] == "moving" and pm is None:
                        pm = parks[j][1]
                        pw_ticks = parks[j][2]
                    j += 1
                if j < len(parks):
                    pd = parks[j][1]
                    pi = j + 1
            # the next attempt slot of this arm
            nxt = None
            for s2 in slots[i + 1:]:
                if not s2["poll"]:
                    nxt = s2
                    break
            polls = [s2 for s2 in slots[i + 1:]
                     if s2["poll"] and (nxt is None or s2["t"] < nxt["t"])]
            row = {
                "arm": arm, "t": s["t"], "span": s["span"], "end": end,
                "park_wait": (pm - pw) if (pw is not None and pm is not None) else 0.0,
                "park_move": (pd - pm) if (pm is not None and pd is not None) else 0.0,
                "park_present": pd is not None,
                "polls": len(polls),
                "next_t": nxt["t"] if nxt is not None else None,
                "park_wait_ticks": pw_ticks,
            }
            if nxt is not None:
                row["gap"] = nxt["t"] - end
                # gap = park_gate + park_move + feed + 0.5s per starved poll
                row["feed"] = (row["gap"] - row["park_wait"] - row["park_move"]
                               - 0.5 * row["polls"])
            out[arm].append(row)
    return out


def placements(rec: dict) -> list[tuple[float, str, str, bool]]:
    """(t_place, arm, category, placed) per attempt, from the attempt's marks."""
    out = []
    for s in sorted(rec["slots"]["left"] + rec["slots"]["right"], key=lambda x: x["t"]):
        if s["poll"] or s["res"] is None:
            continue
        cyc = s["res"].get("cycle") or {}
        tail = cyc.get("return", 0.0) + cyc.get("end", 0.0)
        out.append((s["t"] + s["span"] - tail, s["arm"], s["res"]["category"],
                    s["res"]["placed"]))
    out.sort()
    return out


def interval(rec: dict, arm: str | None = None) -> dict:
    pl = [p for p in placements(rec) if p[3] and (arm is None or p[1] == arm)]
    if len(pl) < 2:
        return {"n": len(pl), "mean": float("nan"), "p90": float("nan")}
    d = [b[0] - a[0] for a, b in zip(pl, pl[1:])]
    d.sort()
    return {"n": len(pl), "mean": sum(d) / len(d),
            "p50": d[len(d) // 2], "p90": d[int(0.9 * (len(d) - 1))],
            "min": d[0], "max": d[-1]}


# ------------------------------------------------------------- decisions -----
def _main_belt(row: dict, belt_top: float) -> str:
    """Would this fruit pass the non-grade predicates? (empty-class check)."""
    if row["z"] < belt_top - 0.02:
        return "below belt"
    if row["z"] > belt_top + 0.12:
        return "output belt"
    if 2 * row["r"] > GRIPPER_MAX:
        return "too big"
    return "ok"


def decision_rows(rec: dict) -> list[dict]:
    """One row per slot decision with the own-lane / any-lane arrival read."""
    out = []
    for d in rec["decisions"]:
        if d["floor"] is None or not d["rows"]:
            continue
        grade = "A" if d["arm"] == "left" else "B"
        v = d["v"]
        floor = d["floor"]
        own, cross, close, bad = [], [], [], []
        for r in d["rows"]:
            reason = r["reason"]
            if reason == "excluded":
                continue
            # a row that reached the *floor* pass already passed every earlier
            # predicate; otherwise it was refused earlier and this census
            # re-checks only the predicates the row's own fields can decide.
            passed_early = reason.startswith("grade ") or reason in (
                "usable", "chosen") or reason.startswith("below catch floor")
            if not passed_early:
                bad.append(r)
                continue
            verdict = _main_belt(r, d["belt_top"])
            if verdict != "ok":
                bad.append(r)
                continue
            if r["along"] < floor:
                # the fruit is already inside the catch floor: it will be past
                # the pick point when the setup ends, so it is not a candidate
                # for *this* arm at *this* tick (it is the v9 under-lead miss).
                r["arr"] = 0.0
                close.append(r)
                continue
            r["arr"] = (r["along"] - floor) / v if v else float("nan")
            (own if r["grade"] == grade else cross).append(r)
        own.sort(key=lambda r: r["along"])
        cross.sort(key=lambda r: r["along"])
        chosen = next((r for r in d["rows"] if r["reason"] == "chosen"), None)
        best_own = own[0] if own else None
        best_any = min(own + cross, key=lambda r: r["along"]) if (own or cross) else None
        earlier_cross = [
            r for r in cross if best_own is None or r["along"] < best_own["along"]
        ]
        out.append({
            "arm": d["arm"], "t": d["t"], "floor": floor, "v": v,
            "grade": grade, "live": d["live"], "on_belt": d["on_belt"],
            "window": d["window"], "admitted": d["admitted"], "pick": d["pick"],
            "n_own": len(own), "n_cross": len(cross), "n_close": len(close),
            "bad": len(bad),
            "chosen": chosen, "best_own": best_own, "best_any": best_any,
            "earlier_cross": earlier_cross,
            "cross_earlier": bool(earlier_cross),
            "cross_only": bool(best_own is None and cross),
            "starved": chosen is None,
            # the arrival wait the attempt pays: (along_chosen - floor)/v, the
            # model `logs/p91/AUDIT.md` measured as the descent block's first
            # term (2.17 s on `logs/p87/T5.log`)
            "wait_s": ((chosen["along"] - floor) / v
                       if (chosen is not None and v) else None),
            "own_gap_s": ((best_own["arr"] - earlier_cross[0]["arr"])
                          if (best_own and earlier_cross) else None),
            "rule_gap_s": ((best_own["arr"] - chosen["arr"])
                           if (best_own and chosen) else None),
            "chosen_gap_s": (
                None if chosen is None else
                max(0.0, (chosen["along"] - (earlier_cross[0]["along"]
                                             if earlier_cross else chosen["along"]))
                    / v) if v else None
            ),
        })
    return out


# ---------------------------------------------------------------- report -----
def _f(x, w=6, p=2):
    return f"{x:{w}.{p}f}" if isinstance(x, (int, float)) and x == x else f"{'-':>{w}}"


def report(rec: dict, det: bool = True) -> None:
    print(f"\n== {rec['path']}")
    tl = timeline(rec)
    iv = interval(rec)
    res = rec["results"]
    print(f"   attempts={len(res)} placed={sum(r['placed'] for r in res)} "
          f"grasped={sum(r['grasped'] for r in res)} "
          f"interval mean={_f(iv['mean'])}s p50={_f(iv.get('p50'))} "
          f"p90={_f(iv.get('p90'))} n={iv['n']}")
    per_arm = {a: interval(rec, a) for a in ("left", "right")}
    print(f"   per-arm interval: left mean={_f(per_arm['left']['mean'])}s "
          f"(n={per_arm['left']['n']})  right mean={_f(per_arm['right']['mean'])}s "
          f"(n={per_arm['right']['n']})")
    # polls outside the attempt chain: the batch prime and the tail
    for arm in ("left", "right"):
        slots = rec["slots"][arm]
        att = [i for i, s in enumerate(slots) if not s["poll"]]
        if not att:
            continue
        prime = sum(1 for s in slots[:att[0]] if s["poll"])
        tail = sum(1 for s in slots[att[-1] + 1:] if s["poll"])
        if prime or tail:
            print(f"   {arm}: starved polls outside the chain: "
                  f"batch-prime={prime} tail={tail}")
    print("   [A] slot wait split (seconds, per attempt slot)")
    hdr = (f"       {'arm':5s} {'slots':>5s} {'polls':>5s} {'gate':>6s} "
           f"{'park':>6s} {'feed':>6s} {'poll':>6s} {'dead':>6s} {'cycle':>6s}")
    print(hdr)
    for arm in ("left", "right"):
        rows = [r for r in tl[arm] if "gap" in r]
        n = len(rows)
        if not n:
            continue
        gate = sum(r["park_wait"] for r in rows) / n
        park = sum(r["park_move"] for r in rows) / n
        polls = sum(r["polls"] for r in rows)
        poll_s = 0.5 * polls / n
        feed = sum(r["feed"] for r in rows) / n
        span = sum(r["span"] for r in rows) / n
        gap = sum(r["gap"] for r in rows) / n
        print(f"       {arm:5s} {n:5d} {polls:5d} {_f(gate)} {_f(park)} "
              f"{_f(feed)} {_f(poll_s)} {_f(gap)} {_f(span)}")
    tot = [r for arm in ("left", "right") for r in tl[arm] if "gap" in r]
    if tot:
        n = len(tot)
        gate = sum(r["park_wait"] for r in tot) / n
        park = sum(r["park_move"] for r in tot) / n
        polls = sum(r["polls"] for r in tot)
        poll_s = 0.5 * polls / n
        feed = sum(r["feed"] for r in tot) / n
        gap = sum(r["gap"] for r in tot) / n
        print(f"       {'all':5s} {n:5d} {polls:5d} {_f(gate)} {_f(park)} "
              f"{_f(feed)} {_f(poll_s)} {_f(gap)} "
              f"{_f(sum(r['span'] for r in tot) / n)}")
        iem = iv["mean"]
        print(f"       per-attempt dead time (gate+park+feed+polls) = {gap:.2f}s; "
              f"per placement with 2 arms = {gap / 2:.2f}s"
              + (f" = {100 * gap / 2 / iem:.1f}% of the {iem:.2f}s interval"
                 if iem == iem else ""))
        print(f"       of which starvation (polls) = {poll_s:.2f}s/attempt = "
              f"{poll_s / 2:.2f}s/placement"
              + (f" = {100 * poll_s / 2 / iem:.1f}% of the interval"
                 if iem == iem else ""))
    # the grade-purity ledger: which lane each attempt's fruit went to
    tgt = {}
    for line in open(rec["path"], errors="replace"):
        m = TARGET.search(line)
        if m:
            tgt.setdefault((m.group(4), m.group(2)), 0)
            tgt[(m.group(4), m.group(2))] += 1
    if tgt:
        cells = []
        for arm, want in (("left", "A"), ("right", "B")):
            row = {g: tgt.get((arm, g), 0) for g in "ABC"}
            cross = sum(v for g, v in row.items() if g != want)
            cells.append(f"{arm}: A={row['A']} B={row['B']} C={row['C']} "
                         f"cross-lane={cross}/{sum(row.values())}")
        print("   [D] grade-purity ledger  " + " | ".join(cells))
    if not det or not rec["decisions"]:
        return
    drows = decision_rows(rec)
    if not drows:
        print("   [B] no FRUIT_BED_DIAG=2 rows in this record (offline record)")
        return
    print(f"   [B] candidate read over {len(drows)} decisions")
    starved = [d for d in drows if d["starved"]]
    cross_only = [d for d in drows if d["cross_only"]]
    cross_earlier = [d for d in drows if d["cross_earlier"]]
    print(f"       decisions={len(drows)} starved={len(starved)} "
          f"own-lane-empty-but-cross-lane-present={len(cross_only)} "
          f"cross-lane-arrives-sooner={len(cross_earlier)}")
    bad = sum(d["bad"] for d in drows)
    close = sum(d["n_close"] for d in drows)
    print(f"       rows refused by a non-grade, non-floor predicate "
          f"(below belt / output belt / too big)={bad}; "
          f"own-or-cross rows inside the catch floor={close}")
    for arm in ("left", "right"):
        a = [d for d in drows if d["arm"] == arm]
        if not a:
            continue
        so = [d for d in a if d["cross_only"]]
        se = [d for d in a if d["cross_earlier"]]
        print(f"       {arm:5s} decisions={len(a)} starved={sum(d['starved'] for d in a)} "
              f"cross_only={len(so)} cross_earlier={len(se)} "
              f"own_gap_s_sum={_f(sum(d['own_gap_s'] for d in se if d['own_gap_s']), 7, 3)}")
    # rule gap: did the shipped rule take the nearest of its own lane?
    rg = [d["rule_gap_s"] for d in drows if d["rule_gap_s"] is not None]
    if rg:
        print(f"       delay-aware headroom (nearest own-lane minus chosen): "
              f"n={len(rg)} mean={sum(rg) / len(rg):+.3f}s max={max(rg):+.3f}s "
              f"(0 = the rule already takes the nearest)")
    wins = [d for d in drows if d["window"] <= 1 and not d["starved"]]
    print(f"       selections with window<=1 (a forced choice): {len(wins)}/"
          f"{len([d for d in drows if not d['starved']])}")
    w = [d["wait_s"] for d in drows if d["wait_s"] is not None]
    if w:
        print(f"       arrival wait (along_chosen-floor)/v: n={len(w)} "
              f"mean={sum(w) / len(w):.2f}s total={sum(w):.1f}s "
              f"(p91's block audit: 2.17 s/attempt)")
    # separate the batch prime from the in-chain starvation: the prime is paid
    # once per batch, before an arm's first attempt
    prime_cross = 0
    starved_cross = [d for d in starved if d["cross_only"] or d["cross_earlier"]]
    for arm in ("left", "right"):
        s = rec["slots"][arm]
        att = [i for i, x in enumerate(s) if not x["poll"]]
        if not att:
            continue
        t0 = s[att[0]]["t"]
        prime_cross += sum(
            1 for d in drows
            if d["arm"] == arm and d["starved"] and d["t"] < t0
            and (d["cross_only"] or d["cross_earlier"])
        )
    starved_cross_chain = [d for d in starved_cross
                           if not (d["t"] < min(
                               (x["t"] for x in rec["slots"][d["arm"]]
                                if not x["poll"]), default=-1.0))]
    gate_all = sum(r["park_wait"] for arm in ("left", "right") for r in tl[arm])
    n_att = sum(len([r for r in tl[a] if "gap" in r]) for a in ("left", "right")) or 1
    conv_i = sum(d["chosen_gap_s"] or 0.0 for d in drows) or 0.0
    conv_ii = sum(rg) if rg else 0.0
    n_pl = max(1, iv["n"])
    print("   [C] convertible seconds")
    print(f"       (i)  cross-lane, in-attempt arrival:   {conv_i:7.2f}s "
          f"= {conv_i / n_pl:.3f}s/placement")
    print(f"       (i') in-chain starved polls with a cross-lane fruit "
          f"at/above the floor: {len(starved_cross_chain)} "
          f"= {0.5 * len(starved_cross_chain):.2f}s "
          f"= {0.5 * len(starved_cross_chain) / n_pl:.3f}s/placement "
          f"(batch-prime polls of the same kind: {prime_cross} "
          f"= {0.5 * prime_cross:.1f}s once per batch)")
    print(f"       (ii) delay-aware (nearest vs chosen):  {conv_ii:7.2f}s "
          f"= {conv_ii / n_pl:.3f}s/placement")
    print(f"       (iii) joint / park-gate wait:          {gate_all:7.2f}s over "
          f"{n_att} attempt slots = {gate_all / n_att:.3f}s/attempt "
          f"= {gate_all / n_pl:.3f}s/placement")
    tot = conv_i + 0.5 * len(starved_cross_chain) + conv_ii + gate_all
    print(f"       TOTAL = {tot:.2f}s = {tot / n_pl:.3f}s/placement"
          + (f" = {100 * tot / (iv['mean'] * (n_pl - 1)):.1f}% of the placed span"
             if iv["mean"] == iv["mean"] else ""))


def slot_table(rec: dict) -> list[str]:
    """The per-slot deliverable table (one CSV row per slot, both arms)."""
    tl = {a: {r["t"]: r for r in timeline(rec)[a]} for a in ("left", "right")}
    out = ["arm,slot,t_start,kind,park_gate_s,park_move_s,feed_s,polls,span_s,"
           "grade,along,floor,arr_wait_s,n_own,n_cross,n_close,cross_only,"
           "chosen_s,cross_gap_s"]
    for arm in ("left", "right"):
        for i, s in enumerate(rec["slots"][arm]):
            d = s["decision"] or {}
            tlrow = tl[arm].get(s["t"], {})
            kind = "poll" if s["poll"] else "attempt"
            if not s["poll"] and not any(
                x["t"] < s["t"] and not x["poll"] for x in rec["slots"][arm]
            ):
                kind = "prime"
            chosen = next(
                (r for r in d.get("rows", []) if r["reason"] == "chosen"), None
            )
            own = [r for r in d.get("rows", [])
                   if r["grade"] == ("A" if arm == "left" else "B")
                   and r["reason"] in ("usable", "chosen")]
            cross = [r for r in d.get("rows", [])
                     if r["grade"] != ("A" if arm == "left" else "B")
                     and r["reason"].startswith("grade ")]
            floor = d.get("floor")
            wait = ((chosen["along"] - floor) / d["v"]
                    if (chosen and floor is not None and d.get("v")) else None)
            cross_gap = None
            if chosen and cross and floor is not None:
                nearer = [r for r in cross if floor <= r["along"] < chosen["along"]]
                if nearer and d.get("v"):
                    cross_gap = (chosen["along"]
                                 - min(r["along"] for r in nearer)) / d["v"]
            out.append(",".join([
                arm, str(i), f"{s['t']:.2f}", kind,
                f"{tlrow.get('park_wait', 0.0):.2f}",
                f"{tlrow.get('park_move', 0.0):.2f}",
                f"{tlrow.get('feed', 0.0):.2f}",
                str(tlrow.get("polls", 0)),
                f"{s['span']:.2f}" if s["span"] is not None else "",
                chosen["grade"] if chosen else "",
                f"{chosen['along']:+.3f}" if chosen else "",
                f"{floor:+.3f}" if floor is not None else "",
                f"{wait:.2f}" if wait is not None else "",
                str(len(own)) if d else "", str(len(cross)) if d else "",
                str(sum(1 for r in d.get("rows", [])
                        if not r["reason"].startswith("grade ")
                        and r["reason"] not in ("usable", "chosen"))) if d else "",
                "1" if (d and not own and cross) else "0",
                f"{min(r['along'] for r in own):+.3f}" if own else "",
                f"{cross_gap:.2f}" if cross_gap is not None else "",
            ]))
    return out


# ------------------------------------------------------------------ same -----
def _strip(path: str) -> list[str]:
    """The `[fruit]` stream with P99's own instrument rows removed."""
    skip = ("[fruit] [bed-sel]", "[fruit] [biarm] left: park",
            "[fruit] [biarm] right: park")
    return [ln.rstrip("\n") for ln in open(path, errors="replace")
            if ln.startswith("[fruit]") and not ln.startswith(skip)]


def same(a: str, b: str) -> int:
    A, B = _strip(a), _strip(b)
    print(f"-- replay {a} vs {b}: {len(A)} vs {len(B)} [fruit] lines")
    if A == B:
        print("   IDENTICAL")
        return 0
    for i, (x, y) in enumerate(zip(A, B)):
        if x != y:
            print(f"   first difference at {i}:")
            print(f"     A {x[:150]}")
            print(f"     B {y[:150]}")
            break
    n = min(len(A), len(B))
    same_n = sum(1 for x, y in zip(A[:n], B[:n]) if x == y)
    print(f"   identical prefix rows: {same_n}/{n}")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="*")
    ap.add_argument("--same", nargs=2, metavar=("CELL", "RECORD"))
    ap.add_argument("--slots", metavar="CSV",
                    help="write the per-slot table of the last named log")
    args = ap.parse_args(argv)
    if args.same:
        return same(*args.same)
    for p in args.logs:
        report(parse(p))
    if args.slots:
        if not args.logs:
            ap.error("--slots needs a log")
        rows = slot_table(parse(args.logs[-1]))
        open(args.slots, "w").write("\n".join(rows) + "\n")
        print(f"\n-- per-slot table: {len(rows) - 1} slots -> {args.slots}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
