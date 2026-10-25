#!/usr/bin/env python3
"""P40 lane B / TASK 1: does `FRUIT_REGRASPS` (default 3) ever rescue an attempt?

Parses the printed re-seat row against each attempt's outcome over the existing
log corpus.  Two row formats exist, one per grasp branch in
`src/fruit_sorting/tasks.py`:

  single arm    `[task]   dynamic regrasp: re-seated on the moving fruit`
                (the `else` branch at tasks.py:10632, `_dynamic_capture_active`
                and `regrasp_keep` False)
  two-line      `[task]   dynamic regrasp: re-seated in place (gap N mm kept)`
                (the W1 keep branch at tasks.py:10591, `FRUIT_DYNAMIC_REGRASP_KEEP`
                resolved on for the two-line by `_dynamic_profile`)
  last-resort   `[task]   recovery: re-grasped (open, re-seat, close)`
                (tasks.py:10665, `FRUIT_REGRASP_REOPEN=1`, default OFF)
  direct/policy none - the policy loop passes `verbose=False` AND never sets
                `_dynamic_capture_active`, so both prints are unreachable there.

Attribution
-----------
* single-arm logs: the attempt's own rows are contiguous (`[run] attempt N:
  picking` ... `[run] attempt N: grasped=`), so the rows are counted in place.
* two-line logs: the two arms' grip phases *interleave* in the file (measured:
  `logs/p39/p3/twoline_C.log` 439-451 has 6 rows for 2 attempts) and the row
  carries neither an arm nor a tick, so it cannot be attributed by position.
  The per-attempt count is therefore read from the attempt's own `[cycle] grip`
  segment, which is printed per attempt and is a deterministic function of the
  loop iteration count (each failed probe iteration costs one full
  probe+re-seat+squeeze block).  The read is calibrated and *checked*: the
  per-file row total must equal sum(k) over the attempts (closure printed).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (path, line-label).  The first five are the brief's required corpus.
CORPUS = [
    ("logs/p39/p3/accept_C.log", "single"),
    ("logs/p39/p3/pear_C.log", "single"),
    ("logs/p39/p3/twoline_C.log", "twoline"),
    ("logs/p32/A0_bed_twoline_1.log", "twoline"),
    ("logs/w7/10_dense_twoline_1.log", "twoline"),
    # extras that carry the row / a [cycle] arm-side record
    ("logs/g/20_rate_single_1.log", "single"),
    ("logs/p32/D1_accept_pear.log", "single"),
    # the P35/P36/P37 acceptance no-harm logs (single-arm, hybrid canary's
    # scripted primitive).  `logs/p37/P2_accept_raw.log` is the same run as
    # `accept_no_harm.log` (identical [task] and [run] rows) and the
    # `*_stream*.log` pair is a filtered copy (md5 bc7ca8f0), so each run is
    # counted once.  Not part of the brief's list - reported as an extension.
    ("logs/p35/B_accept_no_harm.log", "single"),
    ("logs/p35/C_accept_no_harm.log", "single"),
    ("logs/p37/accept_no_harm.log", "single"),
]

RE_SEAT = re.compile(r"dynamic regrasp: re-seated")
RE_REOPEN = re.compile(r"recovery: re-grasped")
RE_CYCLE = re.compile(r"\[cycle\] attempt (\d+): (.*)$")
RE_SEG = re.compile(r"(\w+)=([0-9.]+)s")
# single-arm attempt rows
RE_S_PICK = re.compile(r"\[run\] attempt (\d+): picking (\w+) grade (\w)")
RE_S_OUT = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([+-][0-9.]+) m "
    r"force=([0-9.]+) N notes=\[(.*?)\](?: sim=([0-9.]+)-([0-9.]+)s)?"
)
# two-line attempt rows (arm-tagged, span on the picking row)
RE_T_PICK = re.compile(
    r"\[run\] attempt (\d+) \((\w+)\): picking (\w+) grade (\w) .* sim=([0-9.]+)-([0-9.]+)s"
)
RE_T_OUT = re.compile(
    r"\[run\] attempt (\d+) \((\w+)\): grasped=(\w+) placed=(\w+) lift=([+-][0-9.]+) m "
    r"force=([0-9.]+) N sim=([0-9.]+)s notes=\[(.*?)\]"
)


def read(path: Path) -> list[str]:
    return path.read_text(errors="replace").splitlines()


def parse_single(lines: list[str]) -> tuple[list[dict], int]:
    """Contiguous attempt blocks; the re-seat rows are counted in place.

    `[cycle]` rows are printed at the attempt's end in completion order, so they
    attach to the attempts in the same order (n-th cycle row -> n-th attempt).
    """
    attempts: list[dict] = []
    cycles: list[dict] = []
    cur: dict | None = None
    seats = 0
    for line in lines:
        seats += len(RE_SEAT.findall(line))
        m = RE_CYCLE.search(line)
        if m:
            cycles.append({k: float(v) for k, v in RE_SEG.findall(m.group(2))})
            continue
        m = RE_S_PICK.search(line)
        if m:
            cur = {"idx": int(m.group(1)), "fruit": m.group(2), "grade": m.group(3),
                   "arm": "", "reseats": 0}
            continue
        if RE_SEAT.search(line) and cur is not None:
            cur["reseats"] += 1
        if RE_REOPEN.search(line) and cur is not None:
            cur["reopen"] = cur.get("reopen", 0) + 1
        m = RE_S_OUT.search(line)
        if m:
            cur.update(
                idx=int(m.group(1)),
                grasped=m.group(2) == "True",
                placed=m.group(3) == "True",
                lift=float(m.group(4)),
                force=float(m.group(5)),
                notes=m.group(6),
                sim_start=float(m.group(7)) if m.group(7) else None,
                sim_end=float(m.group(8)) if m.group(8) else None,
            )
            attempts.append(cur)
            cur = None
    for i, a in enumerate(attempts):
        a["grip"] = cycles[i].get("grip") if i < len(cycles) else None
        a["total"] = cycles[i].get("total") if i < len(cycles) else None
    return attempts, seats


def parse_twoline(lines: list[str]) -> tuple[list[dict], int, list[dict]]:
    """Outcomes from the arm-tagged summary rows, k from the `[cycle] grip` segment."""
    picks: dict[int, dict] = {}
    outs: dict[int, dict] = {}
    cycles: dict[int, dict] = {}
    seats = 0
    for line in lines:
        seats += len(RE_SEAT.findall(line))
        m = RE_T_PICK.search(line)
        if m:
            picks[int(m.group(1))] = {
                "arm": m.group(2), "fruit": m.group(3), "grade": m.group(4),
                "sim_start": float(m.group(5)), "sim_end": float(m.group(6)),
            }
            continue
        m = RE_T_OUT.search(line)
        if m:
            outs[int(m.group(1))] = {
                "arm": m.group(2), "grasped": m.group(3) == "True",
                "placed": m.group(4) == "True", "lift": float(m.group(5)),
                "force": float(m.group(6)), "span": float(m.group(7)),
                "notes": m.group(8),
            }
            continue
        m = RE_CYCLE.search(line)
        if m:
            cycles[int(m.group(1))] = {
                k: float(v) for k, v in RE_SEG.findall(m.group(2))
            }
    # `[cycle] attempt i` is 1-based and printed at the attempt's *completion*,
    # while the `[run] attempt N` summary rows are printed at the end sorted by
    # index.  The two orders differ when the first two arms finish out of index
    # order (measured: `logs/w7/10_dense_twoline_1.log`, cycle 1 = attempt 1).
    # Match on the total span, which the cycle row prints and the summary row
    # prints independently, and report the residual so the join is auditable.
    attempts: list[dict] = []
    free = sorted(i for i in outs if outs[i].get("span") is not None)
    for i in sorted(cycles):
        att = dict(cycles[i])
        total = att.get("total")
        best, best_d = None, 1e9
        for idx in free:
            d = abs(float(outs[idx]["span"]) - float(total))
            if d < best_d:
                best, best_d = idx, d
        if best is None:
            print(f"    ! cycle {i} has no candidate attempt (total={total})")
            continue
        free.remove(best)
        if best_d > 0.35:
            print(f"    ! cycle {i} total={total:.2f}s best attempt {best} "
                  f"span={outs[best]['span']:.2f}s (residual {best_d:.2f}s)")
        o = outs.get(best, {})
        p = picks.get(best, {})
        attempts.append({
            "idx": best, "arm": o.get("arm", p.get("arm", "?")),
            "fruit": p.get("fruit", "?"), "grade": p.get("grade", "?"),
            "grasped": o.get("grasped"), "placed": o.get("placed"),
            "lift": o.get("lift"), "force": o.get("force"),
            "notes": o.get("notes", ""),
            "sim_start": p.get("sim_start"), "sim_end": p.get("sim_end"),
            "grip": att.get("grip"), "total": total,
            "join_residual": round(best_d, 3),
        })
    attempts.sort(key=lambda a: a["idx"])
    return attempts, seats, [cycles[i] for i in sorted(cycles)]


def k_from_grip(grip: float, base: float) -> int:
    """Iteration count implied by the `[cycle] grip` segment.

    Two-line healthy grip is 1.67-1.77 s (n=15 in the three two-line logs) and a
    re-seat adds ~1.24-1.56 s, so the classes are separated by a wide margin:
    k=0 <= 1.95 s, k=1 3.08-3.28 s, k=3 5.38-5.45 s.  Thresholds sit in the
    middle of those gaps.
    """
    if grip is None:
        return -1
    if grip >= 5.0:
        return 3
    if grip >= 2.5:
        return 1
    return 0


def main() -> int:
    rows: list[dict] = []
    print("=" * 108)
    print("PER-FILE ATTEMPT TABLE   (k = re-seats printed for that attempt)")
    print("=" * 108)
    for rel, kind in CORPUS:
        path = ROOT / rel
        if not path.exists():
            print(f"{rel}: MISSING")
            continue
        lines = read(path)
        if kind == "single":
            attempts, seats = parse_single(lines)
            for a in attempts:
                a["file"] = rel
                a["line"] = "single"
                a["k"] = a.get("reseats", 0)
            note = ("contiguous rows, counted in place (exact)"
                    if seats or attempts else "")
        else:
            attempts, seats, _ = parse_twoline(lines)
            base = 1.73
            for a in attempts:
                a["file"] = rel
                a["line"] = "twoline"
                a["k"] = k_from_grip(a["grip"], base)
            note = (f"[cycle] grip segment (k=0 <=1.95 s, k=1 2.5-5.0 s, "
                    f"k=3 >=5.0 s); closure {sum(a['k'] for a in attempts)} "
                    f"= rows {seats}")
            print(f"\n{rel}  [{kind}]  attempts={len(attempts)}  "
                  f"re-seat rows={seats}  {note}")
            for a in attempts:
                print(f"  attempt {a['idx']:2d} {a['arm']:5s} {a['fruit']:10s} "
                      f"k={a['k']} grip={a['grip']:5.2f}s placed={a['placed']} "
                      f"grasped={a['grasped']} lift={a['lift']:+.3f} "
                      f"notes={a['notes'][:38]}")
            rows.extend(attempts)
            continue
        print(f"\n{rel}  [{kind}]  attempts={len(attempts)}  "
              f"re-seat rows={seats}  {note}")
        for a in attempts:
            print(f"  attempt {a['idx']:2d} {'':5s} {a['fruit']:10s} "
                  f"k={a['k']} placed={a['placed']} grasped={a['grasped']} "
                  f"lift={a['lift']:+.3f} notes={a['notes'][:38]}")
        rows.extend(attempts)

    print("\n" + "=" * 108)
    print("POOLED")
    print("=" * 108)
    n = len(rows)
    hit = [a for a in rows if a["k"] >= 1]
    miss = [a for a in rows if a["k"] == 0]
    placed_hit = [a for a in hit if a["placed"]]
    placed_miss = [a for a in miss if a["placed"]]
    print(f"attempts parsed           : {n}  "
          f"({sum(1 for a in rows if a['line']=='single')} single-arm, "
          f"{sum(1 for a in rows if a['line']=='twoline')} two-line)")
    print(f"attempts with >=1 re-seat : {len(hit)}   "
          f"placed {len(placed_hit)}  -> P(placed | k>=1) = "
          f"{len(placed_hit)/max(1,len(hit)):.3f}")
    print(f"attempts with  0 re-seats : {len(miss)}   "
          f"placed {len(placed_miss)}  -> P(placed | k==0) = "
          f"{len(placed_miss)/max(1,len(miss)):.3f}")
    for k in (1, 2, 3):
        sel = [a for a in rows if a["k"] == k]
        if not sel:
            continue
        g = sum(1 for a in sel if a["grasped"])
        p = sum(1 for a in sel if a["placed"])
        print(f"  exactly k={k}            : n={len(sel):2d}  grasped {g:2d} "
              f"({g/len(sel):.2f})  placed {p:2d} ({p/len(sel):.2f})")
    print(f"re-seat rows total        : {sum(a['k'] for a in rows)}")
    print("\nthe k>=1 population, one row per attempt:")
    for a in hit:
        grip = "  n/a" if a["grip"] is None else f"{a['grip']:5.2f}s"
        print(f"  {a['file']:34s} attempt {a['idx']:2d} k={a['k']} "
              f"{a['fruit']:10s} placed={str(a['placed']):5s} "
              f"grasped={str(a['grasped']):5s} lift={a['lift']:+.3f} "
              f"grip={grip} notes={a['notes'][:44]}")
    # rescued = a k>=1 attempt that placed
    print("\nRESCUES (k>=1 and placed):")
    for a in placed_hit:
        print(f"  {a['file']} attempt {a['idx']} k={a['k']} {a['fruit']} "
              f"grip={a['grip']}")
    if not placed_hit:
        print("  none")

    cost_block(rows, placed_hit)
    return 0


# --- the cost / rate block -------------------------------------------------
# Per failed probe iteration the loop pays, at 120 Hz (CONTROL_DT = 1/120 s):
#   two-line  (W1 keep branch)  probe 60 + descend 40 + squeeze 60 = 160 ticks
#   single arm (else branch)    probe 40 + chase 40 + close 45 + squeeze 60
#                               = 185 ticks
# (`FRUIT_DYNAMIC_PROBE_TICKS` 60/40, `FRUIT_PROBE_TICKS` 40 in the else path,
#  `min_jerk_ramp(gap_open, grip_gap, 45)`, and the trailing 60-tick squeeze).
CODE_TICKS = {"twoline": 160, "single": 185}
DT = 1.0 / 120.0


def cost_block(rows: list[dict], placed_hit: list[dict]) -> None:
    print("\n" + "=" * 108)
    print("COST: the `[cycle] grip` segment by re-seat count (the measured block)")
    print("=" * 108)
    for line in ("single", "twoline"):
        sel = [a for a in rows if a["line"] == line and a["grip"] is not None]
        if not sel:
            print(f"{line:8s}: no [cycle] marks in the corpus for this line")
            continue
        for k in (0, 1, 3):
            g = sorted(a["grip"] for a in sel if a["k"] == k)
            if not g:
                continue
            med = g[len(g) // 2]
            print(f"{line:8s} k={k}: n={len(g):2d} grip median={med:5.2f}s "
                  f"range {g[0]:.2f}-{g[-1]:.2f}s")
        base = sorted(a["grip"] for a in sel if a["k"] == 0)
        k3 = sorted(a["grip"] for a in sel if a["k"] == 3)
        if base and k3:
            b = base[len(base) // 2]
            m3 = k3[len(k3) // 2]
            print(f"         -> tax on a k=3 attempt = {m3 - b:.2f}s "
                  f"= {(m3 - b) / 3:.2f}s per failed probe iteration "
                  f"(code path {CODE_TICKS[line]} ticks = "
                  f"{CODE_TICKS[line] * DT:.2f}s)")

    print("\n" + "=" * 108)
    print("WHAT A BOUND WOULD SAVE  (measured per-iteration cost per line)")
    print("=" * 108)
    # measured per-iteration cost, two-line / single-arm
    per_iter = {}
    for line in ("twoline", "single"):
        sel = [a for a in rows if a["line"] == line and a["grip"] is not None]
        base = sorted(a["grip"] for a in sel if a["k"] == 0)
        k3 = sorted(a["grip"] for a in sel if a["k"] == 3)
        if base and k3:
            per_iter[line] = ((k3[len(k3) // 2] - base[len(base) // 2]) / 3.0,
                              CODE_TICKS[line] * DT)
        else:
            per_iter[line] = (CODE_TICKS[line] * DT, CODE_TICKS[line] * DT)
    for line in ("twoline", "single"):
        print(f"{line:8s} per iteration: measured {per_iter[line][0]:.2f}s / "
              f"code {per_iter[line][1]:.2f}s")

    print("\nper-file batch arithmetic (removing N extra iterations from the "
          "attempts that burn three):")
    for rel, _kind in CORPUS:
        sel = [a for a in rows if a["file"] == rel]
        if not sel:
            continue
        line = sel[0]["line"]
        it = per_iter[line][0]
        k3 = [a for a in sel if a["k"] == 3]
        failed = [a for a in sel if not a["placed"]]
        tax_failed = sum(a["k"] * it for a in failed)
        if line == "twoline":
            # a two-line batch overlaps its arms: the census's batch window is
            # max(sim_end) - min(sim_start)
            span = max((a["sim_end"] or 0) for a in sel) - min(
                (a["sim_start"] or 0) for a in sel)
        else:
            # the single arm serialises: sum of the per-attempt spans
            # (= the `[stats] ... sim=Ns total` row)
            span = sum((a["sim_end"] or 0) - (a["sim_start"] or 0) for a in sel)
        placed = sum(1 for a in sel if a["placed"])
        at3 = span
        at2 = span - len(k3) * it
        at1 = span - len(k3) * 2 * it
        f = lambda s: placed / s * 60 if s > 0 else 0.0
        span_txt = f"{span:6.1f}s" if span > 0 else "  n/a "
        print(f"  {rel:34s} n={len(sel):2d} placed={placed:2d} k=3:{len(k3):2d} "
              f"re-seat sim-s on failed attempts {tax_failed:5.1f} | "
              f"span {span_txt} -> =3 {f(at3):.2f}, =2 {f(at2):.2f}, "
              f"=1 {f(at1):.2f} placed/min")
    print("\n(the span is the batch's own window: for the two-line "
          "max(sim_end) - min(sim_start), for the single arm the sum of the "
          "per-attempt spans = the `[stats] ... sim=Ns total` row)")


if __name__ == "__main__":
    sys.exit(main())
