#!/usr/bin/env python3
"""P84 report: fail-fast on the two-line, and where the freed time goes.

    python3 logs/p84/p84_report.py            # reads logs/p84 + logs/p80
    python3 logs/p84/p84_report.py --check    # exit 1 if any registered guard fails

Read-only (opens logs, prints). It borrows P80's parser (`logs/p80/p80lib.py`,
which borrows `scripts/186_w6_report.py`'s W6/P33 metric definitions) and P81's
two-line reads (`concurrency`, per-arm classes), so every number here is computed
by the same code as P80's and P81's and is directly comparable. Sections:

  0  provenance: the PREREG md5, the tree pins
  1  G1: the `[fruit]` stream identity of each control against P80's record,
     modulo the `[fruit] [carry]` diag rows (the tracker/park-trace neutrality)
  2  the arms at a glance: E1-E3, E8, the starved polls
  3  per arm: attempts/placed, idle, lock-on, starved polls, class split
  4  the interval decomposition and the registered arithmetic (PREREG section 2)
  5  the park gate (E6): gate-blocked vs return motion, per arm
  6  the abort audit (E9): every trip, and every placed leg's `ticks=X/X`
  7  G2/G3: the in-batch prefix and the failure-reason ledger
  8  the decision rule (PREREG section 6), clause by clause
  9  the gates and the wall as recorded

Exit 0 when every input the decision needs is readable and (with `--check`)
every registered guard passes; 1 otherwise (a missing arm is printed as missing,
never inferred).
"""

from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "logs/p80"))
import p80lib  # noqa: E402

#: tag -> (label, seed, role). D = control (scheduler only), F = the lever.
#: The P80 records are the branch references for G1, not controls of this A/B.
ARMS = {
    "D5": ("control", 5, "D"),
    "F5": ("fail-fast 150 mm", 5, "F"),
    "D6": ("control", 6, "D"),
    "F6": ("fail-fast 150 mm", 6, "F"),
}
P80_REF = {"D5": "T20", "D6": "T6"}
SEEDS = (5, 6)
A = {"5": ("D5", "F5"), "6": ("D6", "F6")}

IDLE_BAR = 0.0            # PREREG T2: the mean per-arm idle fraction must FALL
SPAN_BAR = 3.0            # PREREG M2: the failed attempt's span must fall >= 3.0 s
INT_SEED_BAR = 3.0        # PREREG T1: per-seed interval fall >= 3 %
INT_POOL_BAR = 8.0        # PREREG T1: pooled interval fall >= 8 %
WALL_BAR = 5.0            # PREREG T3: the wall rate may not fall more than 5 %
TRIP_MM = 150.0

CARRY = re.compile(r"^\[fruit\] \[carry\] ")
CARRY_ASSIST = re.compile(r"^\[fruit\] \[diag\] carry-assist ")
PARK_ROW = re.compile(r"^\[fruit\] \[biarm\] \w+: park (wait start|moving|done) ")
#: The diag rows this phase adds to the stream on **both** arms. The identity
#: test (G1/G2) drops exactly these and nothing else.
DIAG = (("carry", CARRY), ("carry-assist", CARRY_ASSIST), ("park", PARK_ROW))
FAILFAST = re.compile(
    r"\[fail-fast\] (?P<leg>\w+) (?P<kind>[a-z_0-9]+): trip=t(?P<tick>\d+)/(?P<ticks>\d+) "
    r"clean_slip=(?P<slip>[\d.]+)mm >= (?P<thr>[\d.]+)mm "
    r"d=\((?P<dx>[+\-\d.]+),(?P<dy>[+\-\d.]+),(?P<dz>[+\-\d.]+)\)mm "
    r"sep=(?P<sep>[+\-\d.]+)mm gap=(?P<gap>[+\-\d.]+)mm "
    r"force=(?P<force>[\d.]+)N force_min=(?P<fmin>[+\-\d.]+)N "
    r"contacts=(?P<contacts>\d+) onset_row=(?P<onset_row>\S+) loss_row=(?P<loss_row>\S+)")
CARRY_ROW = re.compile(
    r"\[fruit\] \[carry\] (?P<arm>\w+) (?P<leg>\w+): ticks=(?P<ran>\d+)/(?P<total>\d+) "
    r".*?clean_slip_max=(?P<slip>[\d.]+)mm")
BIARM_RESULT = re.compile(r"\[biarm\] result (?P<arm>\w+) index=(?P<index>\d+)")


def md5(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def f(v, nd=2):
    return p80lib.fmt(v, nd)


def path_of(tag: str) -> str:
    return os.path.join(HERE, f"{tag}.log")


def read(tag: str) -> dict | None:
    path = path_of(tag)
    return p80lib.metrics(path) if os.path.exists(path) else None


def stream(path: str, drop_diag: bool = True) -> list[str]:
    """The `[fruit]` physics record; the phase's own diag rows droppable."""
    out = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "[fruit]" not in line:
                continue
            if drop_diag and any(pat.match(line) for _, pat in DIAG):
                continue
            out.append(line.rstrip("\n"))
    return out


def diag_counts(path: str) -> dict:
    counts = {name: 0 for name, _ in DIAG}
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            for name, pat in DIAG:
                if pat.match(line):
                    counts[name] += 1
                    break
    return counts


def same(reference: str, candidate: str, drop_diag: bool = True) -> tuple[bool, int, int, int]:
    """(identical, n_ref, n_cand, prefix) for the `[fruit]` streams."""
    a, b = stream(reference, drop_diag), stream(candidate, drop_diag)
    if a == b:
        return True, len(a), len(b), len(a)
    prefix = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return False, len(a), len(b), prefix


def first_diff(reference: str, candidate: str, drop_diag: bool = True) -> tuple[int, str, str]:
    """(index, ref line, cand line) of the first differing `[fruit]` line."""
    a, b = stream(reference, drop_diag), stream(candidate, drop_diag)
    index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return (index,
            a[index] if index < len(a) else "(end)",
            b[index] if index < len(b) else "(end)")


def carry_rows(tag: str) -> list[dict]:
    """Every `[carry]` row in the log, joined to its attempt's outcome.

    The rows print per leg in attempt order and the attempt's `[biarm] result`
    line prints **after** them, so the rows seen between two result lines belong
    to the first of the two; the groups are zipped to the results in order and
    `placed` is taken from that attempt's own result line.
    """
    path = path_of(tag)
    if not os.path.exists(path):
        return []
    groups: list[list[dict]] = []
    results: list[dict] = []
    pending: list[dict] = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            m = BIARM_RESULT.search(line)
            if m:
                groups.append(pending)
                pending = []
                results.append({"arm": m.group("arm"),
                                "placed": "placed=True" in line})
                continue
            m = CARRY_ROW.search(line)
            if m:
                pending.append(
                    {"arm": m.group("arm"), "leg": m.group("leg"),
                     "ran": int(m.group("ran")), "total": int(m.group("total")),
                     "slip": float(m.group("slip"))}
                )
    if pending:
        groups.append(pending)
    out: list[dict] = []
    for i, group in enumerate(groups):
        placed = results[i]["placed"] if i < len(results) else None
        for row in group:
            out.append(dict(row, placed=placed))
    return out


def trips(tag: str) -> list[dict]:
    path = path_of(tag)
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = FAILFAST.search(line)
        if m:
            out.append({k: (float(v) if k in ("slip", "thr", "dx", "dy", "dz", "sep",
                                              "gap", "force", "fmin")
                            else int(v) if k in ("tick", "ticks", "contacts") else v)
                        for k, v in m.groupdict().items()})
    return out


def failed_span(m: dict) -> tuple[float | None, int, dict]:
    """Mean `t1-t0` over the failed attempts, per arm and pooled."""
    rows = [r for r in p80lib.rows_of(m["path"])
            if not r.get("no_fruit") and r.get("t0", 0) > 0 and r.get("t1", 0) > 0]
    bad = [r for r in rows if not r.get("placed")]
    xs = [r["t1"] - r["t0"] for r in bad]
    per = {}
    for arm in sorted({r["arm"] for r in bad}):
        sub = [r["t1"] - r["t0"] for r in bad if r["arm"] == arm]
        per[arm] = (sum(sub) / len(sub), len(sub)) if sub else (None, 0)
    return (sum(xs) / len(xs)) if xs else None, len(xs), per


def idle_mean(m: dict):
    """The mean of the two arms' idle fractions (PREREG E4 / T2)."""
    vals = [c["idle_frac"] for c in m["per_arm"].values() if c["idle_frac"] is not None]
    return (sum(vals) / len(vals)) if vals else None


def lock_on_mean(m: dict):
    vals = [c["mean"] for c in m["lock_on"].values() if c["mean"] is not None]
    return (sum(vals) / len(vals)) if vals else None


def polls(tag: str, m: dict) -> dict:
    r = p80lib.w6.parse(path_of(tag))["retries"] if os.path.exists(path_of(tag)) else {}
    return {"left": r.get("left"), "right": r.get("right"),
            "total": sum(v for v in r.values() if v) if r else None}


def park(tag: str) -> dict:
    """The `[biarm] ... park` trace: gate-blocked vs return motion, per arm."""
    path = path_of(tag)
    if not os.path.exists(path):
        return {}
    data = p80lib.w6.parse(path)
    out = {}
    for arm in ("left", "right"):
        blocked = list(data.get("park_blocked", {}).get(arm) or [])
        motion = list(data.get("park_motion", {}).get(arm) or [])
        ticks = list(data.get("park_ticks", {}).get(arm) or [])
        out[arm] = {"n_moved": len(motion),
                    "blocked": sum(blocked), "blocked_mean": (sum(blocked) / len(blocked)) if blocked else 0.0,
                    "motion": sum(motion), "ticks": sum(ticks)}
    return out


def classes(tag: str) -> dict:
    path = path_of(tag)
    if not os.path.exists(path):
        return {}
    data = p80lib.w6.parse(path)
    out = {}
    for arm, rows in data["results"].items():
        cell = {"placed": 0, "cnp": 0, "never": 0}
        for row in rows:
            if row["placed"]:
                cell["placed"] += 1
            elif row["grasped"]:
                cell["cnp"] += 1
            else:
                cell["never"] += 1
        out[arm] = cell
    return out


def concurrency(m: dict):
    rows = [r for r in p80lib.rows_of(m["path"])
            if not r.get("no_fruit") and r.get("t0", 0) > 0 and r.get("t1", 0) > 0]
    xs = [r["t1"] - r["t0"] for r in rows]
    mean = (sum(xs) / len(xs)) if xs else None
    return (len(rows) * mean / m["batch_span"]) if (mean and m["batch_span"]) else None


# --------------------------------------------------------------------------- #
def section_provenance() -> None:
    print("=" * 78)
    print("0. PROVENANCE")
    print("=" * 78)
    pin = os.path.join(HERE, "PREREG.md5")
    if os.path.exists(pin):
        pinned = open(pin, encoding="utf-8").read().split()[0]
        now = md5(os.path.join(HERE, "PREREG.md"))
        print(f"  PREREG.md md5 {pinned} (pinned before the runs)  now {now}  "
              f"{'UNCHANGED' if pinned == now else 'CHANGED - edited after the runs'}")
    header = os.path.join(HERE, "header.txt")
    if os.path.exists(header):
        for line in open(header, encoding="utf-8"):
            if line.startswith("# arm") or line.startswith("# controls"):
                print(f"  {line.rstrip()}")
    print("  tree now (a mismatch against header.txt means the tree moved):")
    for name in ("src/fruit_sorting/tasks.py", "src/fruit_sorting/bimanual.py",
                 "src/fruit_sorting/fruits.py",
                 "configs/motion_reference_twoline.json",
                 "logs/p80/motion_reference_twoline_p80_20.json"):
        print(f"    {md5(os.path.join(ROOT, name))}  {name}")


def section_identity() -> bool:
    print()
    print("=" * 78)
    print("1. G1 - THE TRACKER + PARK TRACE ARE NEUTRAL ON THE TWO-LINE")
    print("=" * 78)
    print("  `[fruit]` stream identity against P80's record. The phase's own diag")
    print("  rows are dropped and nothing else (see DIAG in this file).")
    ok = True
    for tag, ref in P80_REF.items():
        ref_path = os.path.join(ROOT, "logs/p80", f"{ref}.log")
        if not os.path.exists(path_of(tag)) or not os.path.exists(ref_path):
            print(f"  {tag} vs {ref}: MISSING -> the neutrality proof is not available")
            ok = False
            continue
        ident, n_ref, n_cand, prefix = same(ref_path, path_of(tag))
        dropped = diag_counts(path_of(tag))
        drop_txt = ", ".join(f"{k} {v}" for k, v in dropped.items())
        print(f"  {tag} vs logs/p80/{ref}.log: "
              f"{'IDENTICAL' if ident else 'DIFFERS'} "
              f"({n_ref} ref / {n_cand} candidate physics lines; dropped: {drop_txt}; "
              f"prefix {prefix})")
        if not ident:
            index, ref_line, cand_line = first_diff(ref_path, path_of(tag))
            print(f"    first difference at {index}:")
            print(f"      ref  : {ref_line[:140]}")
            print(f"      cand : {cand_line[:140]}")
            print("    -> the tracker/park trace IS a control input on this line (G1 FAIL)")
            ok = False
    return ok


def section_arms() -> dict:
    print()
    print("=" * 78)
    print("2. THE ARMS AT A GLANCE (E1-E3, E8; wall from the stamps)")
    print("=" * 78)
    print(f"{'arm':>4} {'seed':>4} {'placed':>7} {'s/att':>6} {'interval':>13} "
          f"{'p90':>6} {'failed att':>10} {'win':>5} {'batch':>5} {'wall':>5} "
          f"{'w/sim':>5} {'trips':>5} {'polls':>6}")
    got = {}
    for tag, (label, seed, role) in ARMS.items():
        m = read(tag)
        if m is None:
            print(f"{tag:>4} {seed:>4}   MISSING")
            continue
        st = m["stats"] or {}
        fs, n_failed, _ = failed_span(m)
        p = polls(tag, m)
        tp = trips(tag)
        wall = st.get("wall")
        wr = (60.0 * m["placed"] / wall) if wall else None
        print(f"{tag:>4} {seed:>4} {m['placed']:>3}/{m['attempts']:<3} "
              f"{f(st.get('per_attempt')):>6} {f((m['pooled'] or {}).get('mean')):>13} "
              f"{f((m['pooled'] or {}).get('p90')):>6} "
              f"{f(fs) + ' s/' + str(n_failed):>10} "
              f"{f(m['window_rate']):>5} {f(m['batch_rate']):>5} {f(wr):>5} "
              f"{f(st.get('wall_over_sim')):>5} {len(tp):>5} {p['total'] if p['total'] is not None else 'n/a':>6}")
        got[tag] = {"m": m, "wall": wall, "wall_rate": wr, "failed": fs,
                    "n_failed": n_failed, "trips": len(tp), "polls": p}
    return got


def section_per_arm(got: dict) -> None:
    print()
    print("=" * 78)
    print("3. PER ARM - idle, lock-on, starvation, class split (E4-E7)")
    print("=" * 78)
    for tag in ARMS:
        if tag not in got:
            continue
        m = got[tag]["m"]
        p = got[tag]["polls"]
        print(f"  {tag}: places {p['left']} left / {p['right']} right polls; "
              f"mean idle {f(100.0 * (idle_mean(m) or 0))} %")
        cls = classes(tag)
        for arm in ("left", "right"):
            c = m["per_arm"].get(arm)
            if not c:
                continue
            lo = m["lock_on"].get(arm) or {}
            cell = cls.get(arm, {})
            print(f"    {arm:<5} att={c['attempts']:>2} placed={c['placed']:>2} "
                  f"idle={f(100.0 * (c['idle_frac'] or 0), 0):>3} % "
                  f"interval={f(c['interval_mean']):>6} (p90 {f(c['interval_p90'])}) "
                  f"lock-on={f(lo.get('mean'))} (p90 {f(lo.get('p90'))}, "
                  f"retries {lo.get('retries_total')}) "
                  f"| placed {cell.get('placed')} cnp {cell.get('cnp')} never {cell.get('never')}")


def section_decomposition(got: dict) -> dict:
    print()
    print("=" * 78)
    print("4. THE DECOMPOSITION AND THE REGISTERED ARITHMETIC (PREREG section 2)")
    print("=" * 78)
    print("  interval ~= (attempts/placement x mean span) / concurrency + idle/concurrency")
    print(f"  {'seed':>4} {'D/F':>4} {'interval':>9} {'att/plc':>8} {'span':>6} "
          f"{'span term':>10} {'conc':>5} {'idle':>6} {'trips':>5} {'failed':>6}")
    rows = {}
    for seed in SEEDS:
        d, ft = A[str(seed)]
        for tag in (d, ft):
            if tag not in got:
                continue
            m = got[tag]["m"]
            rows_ = [r for r in p80lib.rows_of(m["path"])
                     if not r.get("no_fruit") and r.get("t0", 0) > 0 and r.get("t1", 0) > 0]
            span = (sum(r["t1"] - r["t0"] for r in rows_) / len(rows_)) if rows_ else None
            att_plc = (m["attempts"] / m["placed"]) if m["placed"] else None
            conc = concurrency(m)
            term = (att_plc * span) if (att_plc and span) else None
            print(f"  {seed:>4} {tag:>4} {f((m['pooled'] or {}).get('mean')):>9} "
                  f"{f(att_plc):>8} {f(span):>6} {f(term):>10} {f(conc):>5} "
                  f"{f(100.0 * (idle_mean(m) or 0), 0):>5}% {len(trips(tag)):>5} "
                  f"{got[tag]['n_failed']:>6}")
            rows[tag] = {"span": span, "att_plc": att_plc, "conc": conc, "term": term}
    return rows


def section_park(got: dict) -> None:
    print()
    print("=" * 78)
    print("5. THE PARK GATE (E6) - `FRUIT_BIARM_PARK_TRACE=1`, both arms")
    print("=" * 78)
    print("  An arm already at ready returns with no trace line, so n counts real parks.")
    for tag in ARMS:
        if tag not in got:
            continue
        pk = park(tag)
        parts = []
        for arm in ("left", "right"):
            c = pk.get(arm) or {}
            parts.append(f"{arm[:1]}: n={c.get('n_moved', 0)} "
                         f"blocked={f(c.get('blocked'), 1)}s "
                         f"(mean {f(c.get('blocked_mean'), 1)}) "
                         f"motion={f(c.get('motion'), 1)}s "
                         f"gate-wait={c.get('ticks', 0)}tk")
        print(f"  {tag}: " + " | ".join(parts))


def section_cycle(got: dict) -> None:
    """E10: which block the abort removes, from the `[cycle]` marks."""
    print()
    print("=" * 78)
    print("6b. THE CYCLE DECOMPOSITION (E10) - mean s per attempt, by class")
    print("=" * 78)
    ORDER = ("prepose", "hover", "descent", "close", "grip", "lift", "place",
             "release", "return", "end")
    print(f"  {'arm':>4} {'class':>7} {'n':>3} " + " ".join(f"{k[:7]:>7}" for k in ORDER)
          + f" {'total':>7}")
    for tag in ARMS:
        if tag not in got:
            continue
        path = path_of(tag)
        data = p80lib.w6.parse(path)
        attempts = data["attempts"]
        # the `[cycle]` row is 1-based (`attempt 1` = the `[run] attempt 0` slot)
        cells = {"placed": [], "failed": []}
        joined = 0
        for cyc in data["cycles"]:
            row = attempts.get(cyc["n"] - 1) or attempts.get(cyc["n"]) or {}
            if "placed" not in row:
                continue
            joined += 1
            cells["placed" if row["placed"] else "failed"].append(cyc)
        for cls, rows in cells.items():
            if not rows:
                continue
            acc = {k: 0.0 for k in ORDER}
            for cyc in rows:
                for name, dur in cyc["blocks"]:
                    if name in acc:
                        acc[name] += dur
            n = len(rows)
            tot = sum(c["total"] for c in rows) / n
            print(f"  {tag:>4} {cls:>7} {n:>3} "
                  + " ".join(f"{acc[k] / n:>7.2f}" for k in ORDER)
                  + f" {tot:>7.2f}")


def section_class_split(got: dict) -> dict:
    """6c: the saving by failure class, and what the shipped line already cuts."""
    print()
    print("=" * 78)
    print("6c. THE SAVING BY FAILURE CLASS - and what the shipped line already skips")
    print("=" * 78)
    out = {}
    for tag in ARMS:
        if tag not in got:
            continue
        m = got[tag]["m"]
        rows = [r for r in p80lib.rows_of(m["path"])
                if not r.get("no_fruit") and r.get("t0", 0) > 0 and r.get("t1", 0) > 0]
        cells = {}
        for r in rows:
            cls = "placed" if r.get("placed") else ("cnp" if r.get("grasped") else "never")
            cells.setdefault(cls, []).append(r["t1"] - r["t0"])
        out[tag] = cells
    print(f"  {'seed':>4} {'class':>7} {'control':>16} {'treatment':>16} {'delta':>7}")
    for seed in SEEDS:
        d, ft = A[str(seed)]
        for cls in ("placed", "cnp", "never"):
            a = out.get(d, {}).get(cls) or []
            b = out.get(ft, {}).get(cls) or []
            am = (sum(a) / len(a)) if a else None
            bm = (sum(b) / len(b)) if b else None
            delta = (bm - am) if (am is not None and bm is not None) else None
            print(f"  {seed:>4} {cls:>7} "
                  f"{(f(am) + ' s (n=' + str(len(a)) + ')') if a else 'n/a (n=0)':>16} "
                  f"{(f(bm) + ' s (n=' + str(len(b)) + ')') if b else 'n/a (n=0)':>16} "
                  f"{f(delta) if delta is not None else 'n/a':>7}")
    print()
    print("  The shipped two-line already ends most lost attempts at a leg boundary:")
    print("  a `grasped=False` attempt returns right after the lift (the shipped")
    print("  `not result.grasped` return), and the P10-C carry monitor - armed by")
    print("  default in a two-line session - skips the next leg at its boundary. Both")
    print("  are read here as `place` absent from the `[cycle]` row.")
    print(f"  {'arm':>4} {'never: no place':>16} {'cnp: no place':>14} {'cnp: no release':>16}")
    for tag in ARMS:
        if tag not in got:
            continue
        data = p80lib.w6.parse(path_of(tag))
        att = data["attempts"]
        never_cut = never_n = cnp_cut = cnp_n = cnp_rel = 0
        for cyc in data["cycles"]:
            row = att.get(cyc["n"] - 1) or {}
            if "placed" not in row:
                continue
            blocks = dict(cyc["blocks"])
            if not row["placed"] and not row.get("grasped"):
                never_n += 1
                never_cut += "place" not in blocks
            elif not row["placed"]:
                cnp_n += 1
                cnp_cut += "place" not in blocks
                cnp_rel += "release" not in blocks and "place" in blocks
        print(f"  {tag:>4} {f'{never_cut}/{never_n}':>16} {f'{cnp_cut}/{cnp_n}':>14} "
              f"{f'{cnp_rel}/{cnp_n}':>16}")
    return out


def section_audit(got: dict) -> dict:
    print()
    print("=" * 78)
    print("6. THE ABORT AUDIT (E9 / G4 / G5)")
    print("=" * 78)
    audit = {}
    for tag in ARMS:
        if tag not in got:
            continue
        tp = trips(tag)
        rows = carry_rows(tag)
        placed = [r for r in rows if r["placed"]]
        shortened = [r for r in placed if r["ran"] != r["total"]]
        worst_placed = max((r["slip"] for r in placed), default=None)
        empty = [t for t in tp if t["force"] == 0.0 and t["contacts"] == 0]
        audit[tag] = {"trips": len(tp), "empty": len(empty),
                      "placed_legs": len(placed), "shortened": len(shortened),
                      "worst_placed_slip": worst_placed}
        print(f"  {tag}: trips={len(tp)}  empty-pinch={len(empty)}/{len(tp)}  "
              f"placed legs={len(placed)}  shortened={len(shortened)}  "
              f"worst placed clean_slip={f(worst_placed, 1)} mm  "
              f"carry rows={len(rows)}")
        if tp:
            left_ticks = [(t["ticks"] - t["tick"]) + 50 for t in tp]
            print(f"    leg remainder + 50-tick tail: "
                  f"{min(left_ticks)}-{max(left_ticks)} ticks "
                  f"(mean {sum(left_ticks) / len(left_ticks):.0f} = "
                  f"{sum(left_ticks) / len(left_ticks) / 120.0:.2f} s); "
                  f"a place-leg trip also skips release + return")
        for t in tp:
            print(f"    trip {t['leg']:<10} t{t['tick']:>4}/{t['ticks']:<4} "
                  f"slip {t['slip']:.1f} mm  sep/gap {t['sep']:.1f}/{t['gap']:.1f}  "
                  f"force {t['force']:.2f}/{t['fmin']:+.2f} N  contacts {t['contacts']}  "
                  f"onset/loss {t['onset_row']}/{t['loss_row']}  "
                  f"d=({t['dx']:+.1f},{t['dy']:+.1f},{t['dz']:+.1f}) mm")
    return audit


def section_guards(got: dict, rows: dict) -> dict:
    print()
    print("=" * 78)
    print("7. G2 - THE IN-BATCH PREFIX, AND G3 - THE FAILURE-REASON LEDGER")
    print("=" * 78)
    checks = {}
    for seed in SEEDS:
        d, ft = A[str(seed)]
        if d not in got or ft not in got:
            print(f"  seed {seed}: MISSING arm -> prefix not evaluable")
            checks[f"prefix{seed}"] = False
            continue
        ident, n_ref, n_cand, prefix = same(path_of(d), path_of(ft))
        tp = trips(ft)
        index, ref_line, cand_line = first_diff(path_of(d), path_of(ft))
        ok = bool(tp) and cand_line.startswith("[fruit] [fail-fast]")
        print(f"  seed {seed}: {ft} vs {d} {'IDENTICAL' if ident else 'DIFFERS'} "
              f"({n_ref} ref / {n_cand} candidate physics lines, {len(tp)} trips)")
        print(f"    first difference at line {index}:")
        print(f"      ref  : {ref_line[:140]}")
        print(f"      cand : {cand_line[:140]}")
        print(f"    -> the candidate's first new line is the trip row itself: "
              f"{'YES' if ok else 'NO'}")
        checks[f"prefix{seed}"] = ok
    print()
    print("  failure reasons (p80lib `reasons`, control vs treatment), per seed:")
    for seed in SEEDS:
        d, ft = A[str(seed)]
        ledger = {}
        for tag in (d, ft):
            if tag not in got:
                continue
            ledger[tag] = got[tag]["m"]["reasons"]
        print(f"  seed {seed}:")
        for tag, rs in ledger.items():
            print(f"    {tag}: " + ", ".join(f"{k} x{v}" for k, v in sorted(rs.items())))
        if len(ledger) == 2:
            new = set(ledger[ft]) - set(ledger[d])
            print(f"    -> new in treatment: {sorted(new) if new else 'none'}"
                  + ("   (a class this seed's control drew ZERO of, not a new text)"
                     if new else ""))
            checks[f"reasons_seed{seed}"] = not new
        else:
            checks[f"reasons_seed{seed}"] = False
    # The registered clause is the A/B-level ledger (PREREG G3: "the treatment's
    # reason set is a subset of the control's ledger"), so the decision reads the
    # pooled set; the per-seed sets above are reported, and a per-seed difference
    # that is only a class the control drew zero of is not a new reason.
    pooled = {}
    for tag in ARMS:
        if tag in got:
            pooled[tag] = set(got[tag]["m"]["reasons"])
    treat = set().union(*[v for k, v in pooled.items() if k.startswith("F")] or [set()])
    ctrl = set().union(*[v for k, v in pooled.items() if k.startswith("D")] or [set()])
    new_pooled = treat - ctrl
    print(f"  pooled over the two seeds: new in treatment = "
          f"{sorted(new_pooled) if new_pooled else 'none'}")
    checks["reasons_pooled"] = not new_pooled
    return checks


def section_decision(got: dict, audit: dict, guard: dict, rows: dict) -> bool:
    print()
    print("=" * 78)
    print("8. THE REGISTERED DECISION (PREREG section 6)")
    print("=" * 78)
    if any(tag not in got for tag in ARMS):
        print("  at least one arm is missing -> the decision is not evaluable")
        return False
    m1 = all(audit[t]["empty"] == audit[t]["trips"] and audit[t]["shortened"] == 0
             for t in ("F5", "F6"))
    m2_cells = []
    for seed in SEEDS:
        d, ft = A[str(seed)]
        before, after = got[d]["failed"], got[ft]["failed"]
        ok = (before is not None and after is not None and (before - after) >= SPAN_BAR)
        m2_cells.append((seed, before, after, ok))
    m2 = all(c[3] for c in m2_cells)
    print(f"  M1 (G4+G5: empty-pinch trips, no placed leg shortened): "
          f"{'PASS' if m1 else 'FAIL'}")
    for seed, before, after, ok in m2_cells:
        print(f"  M2 seed {seed} (failed attempt span): {f(before)} -> {f(after)} s  "
              f"delta {f((after - before) if (before and after) else None)} s  "
              f"(bar <= -{SPAN_BAR:.1f})  {'PASS' if ok else 'FAIL'}")
    m2_txt = "PASS" if m2 else "FAIL"
    print(f"  M2 overall: {m2_txt}")

    # T1: the pooled interval, per seed and pooled over the two seeds
    t1_cells = []
    for seed in SEEDS:
        d, ft = A[str(seed)]
        before = got[d]["m"]["pooled"]["mean"]
        after = got[ft]["m"]["pooled"]["mean"]
        pct = (100.0 * (after - before) / before) if (before and after) else None
        ok = (pct is not None) and (pct <= -INT_SEED_BAR)
        t1_cells.append((seed, before, after, pct, ok))
        print(f"  T1 seed {seed} (pooled interval): {f(before)} -> {f(after)} s  "
              f"{f(pct)} %  (bar <= -{INT_SEED_BAR:.0f} %)  {'PASS' if ok else 'FAIL'}")
    means = [c[1] for c in t1_cells] + [c[2] for c in t1_cells]
    pooled = (100.0 * ((means[2] + means[3]) / 2 - (means[0] + means[1]) / 2)
              / ((means[0] + means[1]) / 2)) if all(means) else None
    t1_pool = (pooled is not None) and (pooled <= -INT_POOL_BAR)
    print(f"  T1 pooled (mean of the two seeds): {f(pooled)} %  "
          f"(bar <= -{INT_POOL_BAR:.0f} %)  {'PASS' if t1_pool else 'FAIL'}")
    t1 = all(c[4] for c in t1_cells) and t1_pool

    # T2: the mean per-arm idle fraction must fall at both seeds
    t2_cells = []
    for seed in SEEDS:
        d, ft = A[str(seed)]
        before = idle_mean(got[d]["m"])
        after = idle_mean(got[ft]["m"])
        delta = (after - before) if (before is not None and after is not None) else None
        ok = (delta is not None) and (delta < IDLE_BAR)
        t2_cells.append(ok)
        print(f"  T2 seed {seed} (mean per-arm idle): {f(100.0 * (before or 0), 1)} % -> "
              f"{f(100.0 * (after or 0), 1)} %  delta {f(100.0 * (delta or 0), 1)} pt  "
              f"{'PASS' if ok else 'FAIL'}")
    t2 = all(t2_cells)

    # T3: both sim denominators at the pooled level, and the wall rate not down > 5 %
    def pooled_rate(key):
        a = sum(got[A[str(s)][0]]["m"][key] or 0 for s in SEEDS) / 2
        b = sum(got[A[str(s)][1]]["m"][key] or 0 for s in SEEDS) / 2
        return a, b
    win = pooled_rate("window_rate")
    bat = pooled_rate("batch_rate")
    wl = (sum(got[A[str(s)][0]]["wall_rate"] or 0 for s in SEEDS) / 2,
          sum(got[A[str(s)][1]]["wall_rate"] or 0 for s in SEEDS) / 2)
    t3_sim = win[1] > win[0] and bat[1] > bat[0]
    wall_pct = (100.0 * (wl[1] - wl[0]) / wl[0]) if wl[0] else None
    t3_wall = (wall_pct is not None) and (wall_pct >= -WALL_BAR)
    print(f"  T3 window placed/min pooled: {f(win[0])} -> {f(win[1])}  {'PASS' if win[1] > win[0] else 'FAIL'}")
    print(f"  T3 batch  placed/min pooled: {f(bat[0])} -> {f(bat[1])}  {'PASS' if bat[1] > bat[0] else 'FAIL'}")
    print(f"  T3 wall   placed/min pooled: {f(wl[0])} -> {f(wl[1])} ({f(wall_pct)} %)  "
          f"(bar >= -{WALL_BAR:.0f} %)  {'PASS' if t3_wall else 'FAIL'}")
    t3 = t3_sim and t3_wall

    m3 = all(guard.values())
    detail = ", ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in guard.items())
    print(f"  M3 (G1, G2, G3, G6, G7, G8): {'PASS' if m3 else 'FAIL'}  ({detail})")

    # the pooled count, quoted with the branch caveat (PREREG R0/R1/R5)
    dp = sum(got[A[str(s)][0]]["m"]["placed"] for s in SEEDS)
    da = sum(got[A[str(s)][0]]["m"]["attempts"] for s in SEEDS)
    fp = sum(got[A[str(s)][1]]["m"]["placed"] for s in SEEDS)
    fa = sum(got[A[str(s)][1]]["m"]["attempts"] for s in SEEDS)
    print(f"  count (report only, a branch draw): control {dp}/{da} = "
          f"{100.0 * dp / max(1, da):.1f} % -> treatment {fp}/{fa} = "
          f"{100.0 * fp / max(1, fa):.1f} %")
    verdict = m1 and m2 and m3 and t1 and t2 and t3
    print()
    print(f"  MECHANISM GATE: {'PASS' if (m1 and m2 and m3) else 'FAIL'}   "
          f"THROUGHPUT GATE: {'PASS' if (t1 and t2 and t3) else 'FAIL'}")
    print(f"  -> {'ADOPT (recommendation only)' if verdict else 'NOT ADOPTED'}")
    return verdict


def section_wall(got: dict) -> None:
    print()
    print("=" * 78)
    print("9. THE WALL AS RECORDED (E11) - within-batch only")
    print("=" * 78)
    print("  P82's wake-on-request ships default on, so the two-line wall/sim here is")
    print("  ~1.7 against P80's recorded 2.57: P80's wall column is a different harness.")
    print(f"  {'arm':>4} {'wall s':>8} {'sim/att':>8} {'wall/pick':>9} {'wall/sim':>8} "
          f"{'placed/min wall':>15}")
    for tag in ARMS:
        if tag not in got:
            continue
        st = got[tag]["m"]["stats"] or {}
        print(f"  {tag:>4} {f(got[tag]['wall'], 1):>8} {f(st.get('per_attempt')):>8} "
              f"{f(st.get('wall_per_pick')):>9} {f(st.get('wall_over_sim')):>8} "
              f"{f(got[tag]['wall_rate']):>15}")


def main(argv: list[str]) -> int:
    check = "--check" in argv
    section_provenance()
    guard = {}
    guard["G1_neutral"] = section_identity()
    got = section_arms()
    section_per_arm(got)
    rows = section_decomposition(got)
    section_park(got)
    section_cycle(got)
    section_class_split(got)
    audit = section_audit(got)
    extra = section_guards(got, rows) if len(got) == len(ARMS) else {}
    guard.update(extra)
    # G4 / G5 are the audit; G6/G7 are recorded in the .gate/.budgets/.driver
    # files and asserted here from those files (a missing file fails, never
    # inferred). G6: the controls must PASS their per-seed two-line reference
    # (D5 -> P80's 20-attempt seed-5 file, D6 -> the seed-6 file written from
    # P80's own T6); the treatments are gated on motion BUDGETS only, because
    # the abort re-times the presentation (PREREG R0).
    guard["G4_G5_audit"] = all(
        audit[t]["empty"] == audit[t]["trips"] and audit[t]["shortened"] == 0
        for t in ("F5", "F6")) if all(t in audit for t in ("F5", "F6")) else False

    def gate_passed(name: str) -> bool:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            return False
        text = open(path, encoding="utf-8", errors="ignore").read()
        return "190: PASS" in text

    def budgets_clean(name: str) -> bool:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            return False
        text = open(path, encoding="utf-8", errors="ignore").read()
        return "FAIL" not in text

    guard["G6_gate_control_s5"] = gate_passed("D5.gate")
    guard["G6_gate_control_s6"] = gate_passed("D6.gate_t6")
    guard["G6_budgets_F5"] = budgets_clean("F5.budgets")
    guard["G6_budgets_F6"] = budgets_clean("F6.budgets")
    guard["G7_no_timeout"] = all(
        "TIMEOUT" not in open(os.path.join(HERE, f"{t}.driver.log"), encoding="utf-8",
                              errors="ignore").read()
        for t in ARMS
        if os.path.exists(os.path.join(HERE, f"{t}.driver.log")))
    verdict = section_decision(got, audit, guard, rows)
    section_wall(got)
    print()
    print("=" * 78)
    print("10. GATES AS RECORDED")
    print("=" * 78)
    for name in ("D5.gate", "D6.gate_t6", "F5.gate", "F6.gate"):
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            print(f"  {name}: MISSING")
            continue
        lines = [l.rstrip() for l in open(path, encoding="utf-8", errors="ignore")
                 if "PASS" in l or "FAIL" in l or "fingerprint" in l]
        print(f"  {name}: " + ((" | ".join(lines[-3:])) if lines else "(empty)"))
    print(f"  D6.gate (recorded, against the SEED-5 reference - DIFFERS by "
          f"construction: a different seed is a different scenario)")
    print(f"  budgets: F5/F6 are gated on motion budgets only (105, "
          f"--min-success-rate 0.0) - the treatment is its own attractor")
    if check:
        print()
        if not verdict:
            print("  --check: the registered decision is NOT ADOPTED (exit 1 by design)")
            return 1
        print("  --check: ADOPT")
    return 0 if len(got) == len(ARMS) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
