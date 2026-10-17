#!/usr/bin/env python3
"""P10-E no-grasp census: per-attempt table for the two-line scripted catch logs.

Pairing rules (all verified against the run summary rows):
  - [carry] <side> rows pair with that side's attempts in order.
  - [motion] carry / clearance / grip / catchup / descent / moving / coherent rows
    pair with attempts in global order (one per attempt).
  - [task] lift rows are matched by value to the result lift (monitor runs skip some).
  - close rows: the next unclaimed close row before the attempt's grip row; an
    attempt with none keeps None (the close never froze).
  - servo rows: the nearest servo row at/after the result line (same attempt end).
  - cycle rows: the nearest cycle row before the result line.
  - regrasp rows: counted in the (grip_line, carry_line] window; the count is a
    probe-failure proxy (caveat: concurrent arms can interleave one or two rows).
"""
from __future__ import annotations

import re
import sys

RUN_START = re.compile(
    r"\[run\] attempt (\d+) \((left|right)\): picking (\w+) grade (\w) into output lane (\d) "
    r"at \(([-\d.]+), ([-\d.]+)\) sim=([\d.]+)-([\d.]+)s"
)
RUN_END = re.compile(
    r"\[run\] attempt (\d+) \((left|right)\): grasped=(\w+) placed=(\w+) lift=([+\-\d.]+) m "
    r"force=([\d.]+) N sim=([\d.]+)s notes=\[(.*?)\]"
)
CARRY = re.compile(r"\[carry\] (left|right) (\w+): (.*)")
MOTION_CARRY = re.compile(r"\[motion\] carry (\w+): (.*)")
CLEAR = re.compile(r"\[motion\] carry grasp_lift clearance: lowest payload point ([+\-\d]+) mm to the (.+)")
LIFT_ROW = re.compile(r"\[task\] lift ([+\-\d.]+) m, grasped=(\w+)")
GRIP = re.compile(r"\[task\] kinematic grip closed to ([\d.]+)cm around a ([\d.]+)cm fruit")
CLOSE = re.compile(
    r"\[task\] dynamic close: sustained contact after (\d+) ticks \(force=([\d.]+) N, "
    r"span=([\d.]+) mm\); freezing the closing command at ([\d.]+) mm"
)
CATCHUP = re.compile(r"\[task\] dynamic catch-up: residual=([\d.]+) mm \(tol ([\d.]+) mm\)")
DESCENT = re.compile(
    r"\[task\] dynamic descent: waited (\d+) ticks, intercept=([+\-\d.]+) m "
    r"\(station ([+\-\d.]+), shift ([+\-\d.]+) m\), fruit dy=([+\-\d.]+) m, "
    r"deadline=([\d.]+) m, t_desc=([\d.]+) s"
)
MOVING = re.compile(r"\[task\] moving pick: meeting the fruit (\d+) mm upstream of the pick centre")
COHERENT = re.compile(r"\[task\] coherent track (\d+) ticks: fingertip-to-fruit=([\d.]+) mm")
REGRASP = re.compile(r"\[task\]   dynamic regrasp: re-seated in place \(gap ([\d.]+) mm kept\)")
FORCE_SERVO = re.compile(r"\[task\] force servo: (.*)")
CYCLE = re.compile(
    r"\[cycle\] attempt (\d+): prepose=([\d.]+)s hover=([\d.]+)s descent=([\d.]+)s "
    r"close=([\d.]+)s grip=([\d.]+)s lift=([\d.]+)s(.*)total=([\d.]+)s"
)
BIARM_RESULT = re.compile(
    r"\[biarm\] result (left|right) index=(\d+) (\w+) grasped=(\w+) placed=(\w+) "
    r"lift=([+\-\d.]+) force=([\d.]+) sim=([\d.]+)s notes=\[(.*?)\]"
)
TARGET = re.compile(r"\[task\] target (\w+) \(grade (\w), ([\d.]+) cm\) with (left|right) arm")


def fnum(s):
    return float(s)


def parse(path: str):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    attempts = {}
    for i, ln in enumerate(lines):
        m = RUN_START.search(ln)
        if m:
            num = int(m.group(1))
            attempts.setdefault(num, {})["start"] = dict(
                side=m.group(2), species=m.group(3), grade=m.group(4), lane=int(m.group(5)),
                sim0=fnum(m.group(8)), sim1=fnum(m.group(9)), line=i,
            )
        m = RUN_END.search(ln)
        if m:
            num = int(m.group(1))
            attempts.setdefault(num, {})["end"] = dict(
                grasped=m.group(3) == "True", placed=m.group(4) == "True",
                lift=fnum(m.group(5)), force=fnum(m.group(6)), sim=fnum(m.group(7)),
                notes=m.group(8), line=i,
            )
    rows = {k: [] for k in ("carry", "motion", "clear", "lift", "grip", "close", "catchup",
                            "descent", "moving", "coherent", "regrasp", "servo", "cycle",
                            "biarm_result", "target")}
    for i, ln in enumerate(lines):
        m = CARRY.search(ln)
        if m and m.group(2) == "grasp_lift":
            body = m.group(3)
            d = dict(side=m.group(1), line=i)
            for key, pat in (
                ("ticks", r"ticks=(\d+)/(\d+)"), ("slip", r"clean_slip_max=([\d.]+)mm"),
                ("vmax", r"in-hand_vmax=([\d.]+)"), ("onset", r"onset_row=(\d+|None)"),
                ("f_onset", r"force@onset=([\d.]+|n/a)N"), ("sep_onset", r"sep@onset=([\d.]+|n/a)mm"),
                ("c_onset", r"contacts@onset=(\d+|None)"), ("min_c", r"min_contacts=(\d+)"),
                ("f_min", r"force_min=([\d.]+)N"), ("loss", r"loss_row=(\d+|None)"),
                ("gap_start", r"gap_start=([\d.]+)mm"), ("open_max", r"open_max=([\d.]+)mm"),
            ):
                mm = re.search(pat, body)
                d[key] = mm.groups() if (mm and mm.lastindex and mm.lastindex > 1) else (mm.group(1) if mm else None)
            rows["carry"].append(d)
        m = MOTION_CARRY.search(ln)
        if m and m.group(1) == "grasp_lift":
            body = m.group(2)
            d = dict(line=i)
            mm = re.search(r"(\d+) cm, (\d+) ticks", body)
            d["cm"] = int(mm.group(1)) if mm else None
            d["ticks"] = int(mm.group(2)) if mm else None
            mm = re.search(r"slip_max=([\d.]+) mm", body)
            d["slip_max"] = fnum(mm.group(1)) if mm else None
            mm = re.search(r"in-hand \|v\|max=([\d.]+) m/s", body)
            d["vmax"] = fnum(mm.group(1)) if mm else None
            mm = re.search(r"cone=([\d.]+)x", body)
            d["cone"] = fnum(mm.group(1)) if mm else None
            rows["motion"].append(d)
        m = CLEAR.search(ln)
        if m:
            rows["clear"].append(dict(line=i, lowest=int(m.group(1)), where=m.group(2)))
        m = LIFT_ROW.search(ln)
        if m:
            rows["lift"].append(dict(line=i, lift=fnum(m.group(1)), grasped=m.group(2) == "True"))
        m = GRIP.search(ln)
        if m:
            rows["grip"].append(dict(line=i, G=fnum(m.group(1)) * 10, D=fnum(m.group(2)) * 10))
        m = CLOSE.search(ln)
        if m:
            rows["close"].append(dict(line=i, ticks=int(m.group(1)), force=fnum(m.group(2)),
                                      span=fnum(m.group(3)), freeze=fnum(m.group(4))))
        m = CATCHUP.search(ln)
        if m:
            rows["catchup"].append(dict(line=i, res=fnum(m.group(1)), tol=fnum(m.group(2))))
        m = DESCENT.search(ln)
        if m:
            rows["descent"].append(dict(line=i, wait=int(m.group(1)), intercept=fnum(m.group(2)),
                                        station=fnum(m.group(3)), shift=fnum(m.group(4)),
                                        dy=fnum(m.group(5)), deadline=fnum(m.group(6)),
                                        t_desc=fnum(m.group(7))))
        m = MOVING.search(ln)
        if m:
            rows["moving"].append(dict(line=i, jump=int(m.group(1))))
        m = COHERENT.search(ln)
        if m:
            rows["coherent"].append(dict(line=i, ticks=int(m.group(1)), pad_err=fnum(m.group(2))))
        m = REGRASP.search(ln)
        if m:
            rows["regrasp"].append(dict(line=i, gap=fnum(m.group(1))))
        m = FORCE_SERVO.search(ln)
        if m:
            rows["servo"].append(dict(line=i, body=m.group(1)))
        m = CYCLE.search(ln)
        if m:
            rows["cycle"].append(dict(line=i, n=int(m.group(1)), prepose=fnum(m.group(2)),
                                      hover=fnum(m.group(3)), descent=fnum(m.group(4)),
                                      close=fnum(m.group(5)), grip=fnum(m.group(6)),
                                      lift=fnum(m.group(7)), total=fnum(m.group(9))))
        m = BIARM_RESULT.search(ln)
        if m:
            rows["biarm_result"].append(dict(line=i, side=m.group(1), idx=int(m.group(2)),
                                             species=m.group(3), grasped=m.group(4) == "True",
                                             placed=m.group(5) == "True", lift=fnum(m.group(6)),
                                             force=fnum(m.group(7)), sim=fnum(m.group(8))))
        m = TARGET.search(ln)
        if m:
            rows["target"].append(dict(line=i, species=m.group(1), grade=m.group(2),
                                       size=fnum(m.group(3)) * 10.0, side=m.group(4)))
    return lines, attempts, rows


def pair_attempts(attempts, rows):
    """Return a per-attempt dict with the paired rows (see module docstring)."""
    order = sorted(attempts)
    out = {}
    # carry rows per side in order
    carry_by_side = {"left": [r for r in rows["carry"] if r["side"] == "left"],
                     "right": [r for r in rows["carry"] if r["side"] == "right"]}
    idx = {"left": 0, "right": 0}
    for num in order:
        a = attempts[num]
        side = a["start"]["side"]
        rec = dict(num=num, side=side, species=a["start"]["species"], grade=a["start"]["grade"],
                   lane=a["start"]["lane"], sim0=a["start"]["sim0"], sim1=a["start"]["sim1"])
        rec.update(a.get("end", {}))
        if idx[side] < len(carry_by_side[side]):
            rec["carry"] = carry_by_side[side][idx[side]]
        idx[side] += 1
        out[num] = rec
    # global-order rows: one per attempt, in attempt order
    for key in ("grip", "catchup", "moving", "coherent"):
        lst = rows[key]
        for j, num in enumerate(order):
            if j < len(lst):
                out[num][key] = lst[j]
    # descent rows carry the station (the side): assign to the attempt of the
    # matching side, in order (the two arms' legs can complete out of order)
    desc = sorted(rows["descent"], key=lambda r: r["line"])
    for side in ("left", "right"):
        want = 0.0 if side == "left" else -0.1
        side_att = [num for num in order if out[num]["side"] == side]
        got = [r for r in desc if abs(r["station"] - want) <= 0.001]
        for num, r in zip(side_att, got):
            out[num]["descent"] = r
    # Unlabeled one-per-attempt rows (grip / catchup / moving / coherent): the two
    # threads interleave and the legs can complete out of attempt order, so assign
    # each row to a candidate attempt whose window contains it, with the per-side
    # order preserved.  Windows: descent..carry for catchup/grip (thread order is
    # descent -> catchup -> close -> grip -> carry); prev-carry..descent for
    # moving/coherent (they precede the descent).  For the grip rows the measured
    # `sample.diameter` (D) must match the attempt's target nominal within 0.6 mm.
    # pair the target rows per side by order first
    for side in ("left", "right"):
        side_att = [num for num in order if out[num]["side"] == side]
        tg = [t for t in rows["target"] if t["side"] == side]
        for num, t in zip(side_att, tg):
            out[num]["target"] = t
    for key, anchor in (("grip", "inner"), ("catchup", "inner"),
                        ("moving", "outer"), ("coherent", "outer")):
        lst = sorted(rows[key], key=lambda r: r["line"])
        if not lst:
            continue
        cands = []
        for r in lst:
            c = []
            for num in order:
                rec = out[num]
                d = rec.get("descent")
                cr = rec.get("carry")
                if not d or not cr:
                    continue
                if anchor == "inner":
                    if d["line"] < r["line"] < cr["line"]:
                        c.append(num)
                else:
                    side = rec["side"]
                    prev = [out[m]["carry"]["line"] for m in order
                            if out[m]["side"] == side and out[m].get("carry")
                            and out[m]["carry"]["line"] < cr["line"]]
                    lo = prev[-1] if prev else 0
                    if lo < r["line"] < d["line"]:
                        c.append(num)
            cands.append(c)
        side_att = {s: [num for num in order if out[num]["side"] == s] for s in ("left", "right")}
        assign = {}

        def ok_row(num, r):
            if key == "grip":
                tg = out[num].get("target")
                if tg is not None and abs(r["D"] - tg["size"]) > 0.6:
                    return False
            return True

        def dfs(i, nl, nr):
            if i == len(lst):
                return len(assign) == len(lst)
            key_state = (i, nl, nr)
            if key_state in memo:
                return False
            memo.add(key_state)
            for num in cands[i]:
                rec = out[num]
                s = rec["side"]
                k = (nl if s == "left" else nr)
                if k >= len(side_att[s]) or side_att[s][k] != num:
                    continue  # per-side order must be preserved
                if not ok_row(num, lst[i]):
                    continue
                assign[i] = num
                ok = dfs(i + 1, nl + (1 if s == "left" else 0),
                         nr + (1 if s == "right" else 0))
                if ok:
                    return True
                del assign[i]
            # skip an attempt that has no row of this type (per side)
            if nl < len(side_att["left"]) and dfs(i, nl + 1, nr):
                return True
            if nr < len(side_att["right"]) and dfs(i, nl, nr + 1):
                return True
            return False

        memo = set()
        if dfs(0, 0, 0):
            for i, num in assign.items():
                out[num][key] = lst[i]
        else:
            # fall back to global order
            for j, num in enumerate(order):
                if j < len(lst):
                    out[num][key] = lst[j]
    # motion / clearance rows: pair to the carry rows by global order (the k-th
    # motion row follows the k-th carry row; the leg-completion order can differ
    # from the attempt-number order when one leg runs long)
    carry_global = sorted(rows["carry"], key=lambda r: r["line"])
    for key in ("motion", "clear"):
        lst = sorted(rows[key], key=lambda r: r["line"])
        if len(lst) != len(carry_global):
            # fall back to attempt order if the counts do not match
            for j, num in enumerate(order):
                if j < len(lst):
                    out[num][key] = lst[j]
            continue
        for cr, rr in zip(carry_global, lst):
            for num in order:
                if out[num].get("carry") is cr:
                    out[num][key] = rr
                    break
    # cycle rows: the nearest cycle row at/before the result line
    # biarm result rows: pair per side + lift value, in order
    br = sorted(rows["biarm_result"], key=lambda r: r["line"])
    used_br = set()
    for num in order:
        rec = out[num]
        for j, b in enumerate(br):
            if j in used_br:
                continue
            if b["side"] == rec["side"] and rec.get("lift") is not None and abs(b["lift"] - rec["lift"]) < 0.0005:
                rec["biarm_result"] = b
                used_br.add(j)
                break
    cyc = sorted(rows["cycle"], key=lambda r: r["line"])
    for num in order:
        rec = out[num]
        rl = rec.get("biarm_result", {}).get("line")
        if rl is None:
            continue
        cands = [c for c in cyc if 0 <= rl - c["line"] <= 6]
        if cands:
            rec["cycle"] = min(cands, key=lambda c: rl - c["line"])
    # lift rows: match by value to the result lift
    used = set()
    for num in order:
        rec = out[num]
        want = rec.get("lift")
        for j, lr in enumerate(rows["lift"]):
            if j in used:
                continue
            if want is not None and abs(lr["lift"] - want) < 0.0005 and lr["grasped"] == rec.get("grasped"):
                rec["lift_row"] = lr
                used.add(j)
                break
    # close rows: assign by the window (descent < close < grip) with the per-side
    # order preserved and the hard constraint freeze >= G - 0.5 mm (the close's
    # frozen command is >= the recorded grip depth by construction); an attempt
    # with no feasible close row keeps None (the close never froze).
    close_sorted = sorted(rows["close"], key=lambda r: r["line"])
    side_att = {s: [num for num in order if out[num]["side"] == s] for s in ("left", "right")}
    assign = {}

    def close_ok(num, cr):
        g = out[num].get("grip")
        if g is not None and cr["freeze"] + 0.5 < g["G"]:
            return False
        return True

    def dfs(i, nl, nr):
        if i == len(close_sorted):
            return len(assign) == len(close_sorted)
        st = (i, nl, nr)
        if st in memo:
            return False
        memo.add(st)
        # option 1: assign to the next attempt (per side) whose window contains it
        for s, k in (("left", nl), ("right", nr)):
            if k >= len(side_att[s]):
                continue
            num = side_att[s][k]
            d = out[num].get("descent")
            g = out[num].get("grip")
            if not d or not g:
                continue
            if not (d["line"] < close_sorted[i]["line"] < g["line"]):
                continue
            if not close_ok(num, close_sorted[i]):
                continue
            assign[i] = num
            ok = dfs(i + 1, nl + (1 if s == "left" else 0),
                     nr + (1 if s == "right" else 0))
            if ok:
                return True
            del assign[i]
        # option 2: skip the next attempt of a side (its close never froze)
        if nl < len(side_att["left"]) and dfs(i, nl + 1, nr):
            return True
        if nr < len(side_att["right"]) and dfs(i, nl, nr + 1):
            return True
        return False

    memo = set()
    if dfs(0, 0, 0):
        for i, num in assign.items():
            out[num]["close"] = close_sorted[i]
    # regrasp rows: assign to the attempt whose (grip, carry] window contains the
    # row AND whose grip depth is consistent with the keep-gap (keep_gap <= G+3.5
    # from the servo backoff, >= G-15.5 from the close range), with the per-side
    # attempt order preserved.  Every regrasp row belongs to exactly one attempt.
    reg = sorted(rows["regrasp"], key=lambda r: r["line"])
    if reg:
        att_side = {s: [num for num in order if out[num]["side"] == s] for s in ("left", "right")}
        cand = {s: [] for s in ("left", "right")}
        for s in ("left", "right"):
            for r in reg:
                c = None
                for k, num in enumerate(att_side[s]):
                    g = out[num].get("grip")
                    c_ = out[num].get("carry")
                    if not g or not c_:
                        continue
                    if g["line"] < r["line"] < c_["line"] and (
                        g["G"] - 15.5 <= r["gap"] <= g["G"] + 3.5
                    ):
                        c = k
                        break
                cand[s].append(c)
        assign_r = {}

        def dfs_r(i, kl, kr):
            if i == len(reg):
                return True
            st = (i, kl, kr)
            if st in memo_r:
                return False
            memo_r.add(st)
            for s, k, num in (("left", cand["left"][i], None), ("right", cand["right"][i], None)):
                if k is None:
                    continue
                last = kl if s == "left" else kr
                if k < last:
                    continue  # per-side attempt order
                assign_r[i] = (s, att_side[s][k])
                ok = dfs_r(i + 1, k if s == "left" else kl, k if s == "right" else kr)
                if ok:
                    return True
                del assign_r[i]
            return False

        memo_r = set()
        if dfs_r(0, -1, -1):
            for num in order:
                out[num]["regrasps"] = []
            for i, (s, num) in assign_r.items():
                out[num]["regrasps"].append(reg[i])
            for num in order:
                out[num]["regrasps"].sort(key=lambda r: r["line"])
        else:
            # fall back to the window rule
            for num in order:
                rec = out[num]
                g = rec.get("grip")
                c = rec.get("carry")
                if not g or not c:
                    continue
                rec["regrasps"] = [r for r in reg if g["line"] < r["line"] < c["line"]]
    # servo rows: the nearest at/after the result line (within 6 lines)
    for num in order:
        rec = out[num]
        rl = rec.get("biarm_result", {}).get("line")
        if rl is None:
            continue
        cands = [s for s in rows["servo"] if -2 <= s["line"] - rl <= 10]
        if cands:
            rec["servo"] = min(cands, key=lambda s: abs(s["line"] - rl))
    return out


def main(path: str):
    lines, attempts, rows = parse(path)
    out = pair_attempts(attempts, rows)
    print(f"== {path}: {len(out)} attempts, "
          f"no-grasp={sum(1 for r in out.values() if r.get('grasped') is False)} ==")
    for num in sorted(out):
        r = out[num]
        c = r.get("carry", {})
        g = r.get("grip", {})
        cl = r.get("close", {})
        cu = r.get("catchup", {})
        de = r.get("descent", {})
        mo = r.get("motion", {})
        ce = r.get("clear", {})
        cy = r.get("cycle", {})
        rg = r.get("regrasps", [])
        tag = "OK " if r.get("grasped") else "NG "
        close_txt = "-" if not cl else "t=%d F=%.2f span=%.1f freeze=%.1f" % (
            cl["ticks"], cl["force"], cl["span"], cl["freeze"])
        servo_txt = ""
        sv = r.get("servo")
        if sv:
            side = r["side"]
            for part in sv["body"].split("|"):
                if part.strip().startswith(side):
                    servo_txt = part.strip()
        print(
            f"{tag}a{num:02d} {r['side']:5s} {r['species']:10s} g{r['grade']} "
            f"lift={r.get('lift', float('nan')):+.3f} sim={r.get('sim', 0):5.1f} "
            f"| grip G={g.get('G', 0):5.1f} D={g.get('D', 0):5.1f} "
            f"| close={close_txt} "
            f"| cu={cu.get('res', 0):6.1f} | desc w={de.get('wait', 0):3d} dy={de.get('dy', 0):+.3f} "
            f"| regr={len(rg)} | carry sl={c.get('slip', '?'):>9} vmax={c.get('vmax', '?'):>8} "
            f"onset={c.get('onset', '?'):>4} F@o={c.get('f_onset', '?'):>6} sep@o={c.get('sep_onset', '?'):>6} "
            f"c@o={c.get('c_onset', '?'):>4} minC={c.get('min_c', '?')} Fmin={c.get('f_min', '?')} "
            f"loss={c.get('loss', '?'):>4} gap0={c.get('gap_start', '?')} "
            f"| low={ce.get('lowest', 0)} | grip_s={cy.get('grip', 0)} tot={cy.get('total', 0)}"
            f" | servo[{servo_txt}]"
        )
    return 0


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
