#!/usr/bin/env python3
"""P75 place-onset trace selftest (offline; a selfcheck leg).

Pins the **diagnostic-only** instrument `logs/p75/METHOD.md` registers:
`FRUIT_PLACE_ONSET_TRACE=<ticks>` (default **0 = off, the shipped path**), one
`[place-trace]` row per tick for the first `<ticks>` ticks of every `place*`
leg. The question it answers is the one P73/P74 left open - *what exactly happens
in the first ~40 ticks of the left's place leg, where the payload leaves the
pinch* - so the row must carry the three candidate symptoms **on one
tick-indexed line** and in a fixed order.

What this leg checks:

1. the knob resolves strictly (`FRUIT_PLACE_ONSET_TRACE`, unset/empty/
   unparseable/`<= 0` -> off) and `__init__`'s attribute starts at 0;
2. the row is inside the existing `if guard_armed:` block, and `guard_armed`
   gains exactly one term (`self._place_onset_trace > 0`) so the trace is
   self-sufficient and the boolean is unchanged when the knob is off;
3. the scope: `trace_ticks` is the knob on `place*` legs and **0 elsewhere**, so
   a lift leg is untouched;
4. the field set and order, and that a printed row parses back through the
   report's own reader (`scripts/242_p75_classify.py`);
5. **no new articulation read**: the block calls none of `tcp_pose()`,
   `joint_positions()`, `jaw_centre()`, `pad_centre()` - it reuses the block's
   own reads; the two reporting readers it does add (`jaw_separation()`, one
   tactile set) are named in the docstring rather than hidden;
6. the `|v|ach` convention at the first traced tick (0.0, "no predecessor") and
   `|v|cmd` clamped to the profile's own length;
7. the **classification arithmetic** on four synthetic sequences - one per class
   plus a non-escape - because the verdict rule is what the phase reports.

Exit 0 on pass, 1 on the first failure. No simulator, no file writes.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(cond: bool, what: str) -> None:
    if not cond:
        print(f"FAIL: {what}")
        raise SystemExit(1)
    print(f"ok: {what}")


def indented_body_contains(src: str, header: str, needle: int) -> bool:
    """True when `needle` (a character offset) lies in `header`'s indented body."""
    start = src.rfind(header, 0, needle)
    if start == -1:
        return False
    line_start = src.rfind("\n", 0, start) + 1
    indent = start - line_start
    for line in src[start:].splitlines()[1:]:
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= indent:
            end = start + src[start:].index(line)
            return needle < end
    return True


def load_classifier():
    """Import `scripts/242_p75_classify.py` by path (it is not a package)."""
    path = ROOT / "scripts/242_p75_classify.py"
    spec = importlib.util.spec_from_file_location("p75_classify", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def resolve(raw: str) -> int:
    """`__init__`'s resolver, verbatim, on a raw env value."""
    value = 0
    text = raw.strip()
    if text:
        try:
            value = max(0, int(text))
        except ValueError:
            value = 0
    return value


def tick(t: int, d: float, sep: float, fmin: float, err: float, vcmd: float,
         vach: float, n: int = 1, gap: float = 66.8) -> dict:
    return {
        "side": "left",
        "leg": "place0",
        "t": t,
        "d": d,
        "dx": 0.0,
        "dy": 0.0,
        "dz": d,
        "sep": sep,
        "gap": gap,
        "f0": fmin,
        "f1": fmin,
        "n": n,
        "err": err,
        "vcmd": vcmd,
        "vach": vach,
        "qm": 0.0,
        "qj": 3,
    }


def main() -> int:
    src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")

    # ---- 1. the knob ----------------------------------------------------
    for token in (
        'os.environ.get("FRUIT_PLACE_ONSET_TRACE", "")',
        "self._place_onset_trace = 0",
        "self._place_onset_trace = max(0, int(_place_trace_raw))",
    ):
        check(token in src, f"the resolver carries {token}")
    check(resolve("") == 0, "unset -> off")
    check(resolve("  ") == 0, "blank -> off")
    check(resolve("60") == 60, "60 -> 60")
    check(resolve("0") == 0, "0 -> off")
    check(resolve("-5") == 0, "a negative value clamps to off")
    check(resolve("sixty") == 0, "an unparseable value is off, not a crash")

    # ---- 2. containment + the guard_armed term --------------------------
    idx = src.index('f"[place-trace] {side} {name} t={i} "')
    check(
        indented_body_contains(src, "if guard_armed:", idx),
        "the row is printed inside `if guard_armed:`",
    )
    check(
        indented_body_contains(src, "for i in range(n_ticks):", idx),
        "the row is inside the per-tick carry loop",
    )
    check(
        "or self._place_onset_trace > 0" in src,
        "guard_armed gains the trace term (self-sufficient when traced)",
    )
    check(
        "(self._carry_guard_active or self._carry_diag)" in src,
        "the pre-P75 two-term gate is kept as one operand (the four legs that pin it stay valid)",
    )
    check(
        'self._carry_diag = os.environ.get("FRUIT_CARRY_DIAG", "0") == "1"' in src,
        "FRUIT_CARRY_DIAG still defaults to off",
    )

    # ---- 3. the scope ---------------------------------------------------
    check(
        "trace_ticks = (\n                self._place_onset_trace if name.startswith(\"place\") else 0\n            )"
        in src,
        "trace_ticks is the knob on place* legs and 0 elsewhere",
    )
    check(
        "if trace_ticks and i < trace_ticks:" in src,
        "the row is gated on a positive, bounded tick budget",
    )

    # ---- 4. the fields, in order, and the row parses back ---------------
    order = [
        "|d|=",
        "d=(",
        "sep=",
        "gap=",
        "f=(",
        "n=",
        "tcp_err=",
        "v_cmd=",
        "v_ach=",
        "q_margin=",
    ]
    pos = -1
    for token in order:
        nxt = src.find(token, src.index('f"[place-trace] {side} {name} t={i} "'))
        check(nxt > pos, f"the row prints {token} after the previous field")
        pos = nxt
    mod = load_classifier()
    row = (
        "[fruit] [place-trace] left place0 t=7 |d|=0.6mm "
        "d=(+0.1,-0.2,+0.6)mm sep=68.2mm gap=66.8mm f=(4.21,4.19)N n=1 "
        "tcp_err=12.3mm v_cmd=0.343 v_ach=0.121 q_margin=0.031@j3"
    )
    parsed = mod.parse_trace(row)
    check(parsed is not None, "a printed row parses back")
    check(parsed["t"] == 7 and parsed["side"] == "left", "the parse round-trips t/side")
    check(abs(parsed["sep"] - 68.2) < 1e-9, "the parse round-trips sep")
    check(abs(parsed["dz"] - 0.6) < 1e-9, "the parse round-trips the +z component")
    check(abs(parsed["d"] - 0.6) < 1e-9, "the parse round-trips |d|")
    check(abs(parsed["vach"] - 0.121) < 1e-9, "the parse round-trips v_ach")
    check(parsed["qj"] == 3, "the parse round-trips the binding joint index")
    check(mod.parse_trace("[carry] left place0: ticks=1/1") is None,
          "a non-trace row does not parse as a trace row")

    # ---- 5. no new articulation read ------------------------------------
    start = src.index("                    # ---- P75: the place leg's onset trace")
    end = src.index('f"q_margin={float(_marg[_j]):.3f}@j{_j}"')
    block = src[start:end]
    for forbidden in ("tcp_pose()", "joint_positions()", "jaw_centre()", "pad_centre()"):
        check(forbidden not in block, f"the P75 block calls no {forbidden}")
    for documented in ("self.tactile.read()", "arm.jaw_separation()"):
        check(documented in block, f"the block's reporting reader {documented} is explicit")
    check("_tcp_pos" in block and "_tcp_tgt_issued" in block,
          "the achieved/commanded TCP pair is the P66 block's own, reused")

    # ---- 6. the speed conventions ---------------------------------------
    check(
        '_tr_vcmd = float(\n                            np.linalg.norm(velocities[min(i, len(velocities) - 1)])\n                        )'
        in src,
        "|v|cmd is clamped to the profile's own length",
    )
    check(
        "_tr_vach = 0.0" in block and "_tr_tcp_prev is None" in block,
        "the first traced tick reports |v|ach = 0 (no predecessor, not a stale pose)",
    )
    check(
        "_tr_vach = float(\n                                np.linalg.norm(_tcp_pos - _tr_tcp_prev) / CONTROL_DT\n                            )"
        in src,
        "|v|ach is a finite difference of the block's two post-step TCP reads",
    )

    # ---- 7. the classification arithmetic -------------------------------
    # (b) a genuine slide: the displacement walks, sep/force hold at their
    # leg-start values, then the geometry answers only after the payload is out.
    slide = [tick(i, d=0.2 * i, sep=68.0, fmin=9.8, err=12.0, vcmd=0.34, vach=0.34)
             for i in range(20)]
    slide += [tick(i, d=4.0 + 3.0 * (i - 20), sep=68.0 - 3.0 * (i - 20),
                   fmin=max(0.0, 9.8 - 2.0 * (i - 20)), err=12.0, vcmd=0.34,
                   vach=0.34, n=0 if i > 24 else 1) for i in range(20, 28)]
    r = mod.classify(slide)
    check(r["cls"] == "b", f"a slide at constant sep/force classifies b (got {r['cls']})")
    check(r["t_d"] is not None and r["t_geom"] is not None and r["t_geom"] > r["t_d"],
          "b's geometry onset is AFTER the displacement onset")
    # (a) an expulsion: the pads close / the contact is lost first.
    expel = [tick(i, d=0.1, sep=68.0 - 1.5 * i, fmin=max(0.0, 9.8 - 3.0 * i),
                  err=12.0, vcmd=0.30, vach=0.30, n=0 if i >= 2 else 1) for i in range(6)]
    expel += [tick(i, d=6.0 * (i - 5), sep=60.0, fmin=0.0, err=12.0, vcmd=0.30,
                   vach=0.30, n=0) for i in range(6, 10)]
    r = mod.classify(expel)
    check(r["cls"] == "a", f"an early sep/force collapse classifies a (got {r['cls']})")
    check(r["t_geom"] is not None and r["t_d"] is not None and r["t_geom"] <= r["t_d"],
          "a's geometry onset is at or before the displacement onset")
    # (c) a boundary transient: the commanded-vs-achieved error dominates the
    # first ticks and the payload only moves later.
    trans = [tick(i, d=0.2 * max(0, i - 12), sep=68.0, fmin=9.8,
                  err=60.0 if i < 6 else 12.0, vcmd=0.34 if i else 0.0,
                  vach=0.9 if i < 6 else 0.34) for i in range(30)]
    r = mod.classify(trans)
    check(r["cls"] == "c", f"a boundary transient classifies c (got {r['cls']})")
    check(r["t_cmd"] is not None and r["t_d"] is not None and r["t_cmd"] <= r["t_d"] - 2,
          "c's command symptom precedes the displacement by at least the lead")
    # a leg that tracks with a large CONSTANT error is not a boundary transient:
    # the baseline is its own steady state, not zero.
    flat_err = [tick(i, d=0.0 if i < 8 else 4.0 * (i - 7), sep=68.0, fmin=9.8,
                     err=45.0, vcmd=0.34, vach=0.34) for i in range(20)]
    r = mod.classify(flat_err)
    check(r["t_err"] is None, "a flat 45 mm tracking error is not read as a transient")
    check(r["cls"] != "c", f"the flat-error leg is not (c) (got {r['cls']})")
    # a leg that never moves is not an escape at all
    calm = [tick(i, d=0.0, sep=68.0, fmin=9.8, err=12.0, vcmd=0.34, vach=0.34)
            for i in range(60)]
    check(mod.classify(calm)["cls"] == "none", "a leg that never slips inside the window is `none`")
    # the same-tick coincidence must NOT be read as (c): the rule needs the lead
    coincident = [tick(i, d=0.0 if i < 5 else 5.0, sep=68.0, fmin=9.8,
                       err=60.0 if i >= 5 else 12.0, vcmd=0.34, vach=0.34)
                  for i in range(10)]
    check(mod.classify(coincident)["cls"] != "c",
          "a same-tick command step does not own the leg (the lead is required)")

    print("PASS: P75 place-onset trace instrument")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
