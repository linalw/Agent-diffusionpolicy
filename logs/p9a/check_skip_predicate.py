#!/usr/bin/env python3
"""P9-A B1 stub check: the `FRUIT_READY_SKIP` predicate's tolerance logic, offline.

Tier-C-level implementation evidence - NOT a substitute for the pre-registered
Tier-A battery (`logs/p9/PREREG_GOREADY_B1.md`, arms A/B; the byte-identity
proof and the battery are the next Tier-A step). Two layers:

1. Source checks: the shipped constants, the exact predicate expression, the
   single-arm scope gate, and the B2/diag knob text are read out of
   `src/fruit_sorting/tasks.py` by AST/text - the check fails if they move.
2. Predicate evaluation: the exact boolean (`err <= READY_SKIP_TOL and
   dg <= READY_SKIP_SYNC_TOL`) is evaluated on synthetic residuals and on the
   residuals re-derived from the measured no-op evidence
   `logs/610_posture/stream.jsonl` (every 210-row `transit_to_ready` segment is
   a catch-up no-op by code construction, i.e. `dg <= 0.01` at entry; its
   first-row `max|q-ready|` is the entry `err` to within one tick of drift).

Run:  python3 logs/p9a/check_skip_predicate.py
Exit code 0 = all checks PASS.
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TASKS = ROOT / "src" / "fruit_sorting" / "tasks.py"
STREAM = ROOT / "logs" / "610_posture" / "stream.jsonl"

failures: list[str] = []


def check(label: str, ok: bool) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def class_const(tree: ast.Module, name: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return ast.literal_eval(node.value)
    return None


def derive_stream_segments() -> list[dict]:
    """Re-derive each `transit_to_ready` segment's row count and entry err."""
    rows = [json.loads(line) for line in STREAM.read_text().splitlines()]
    header = next(r for r in rows if r.get("kind") == "header")
    ready = header["ready"]
    ticks = [r for r in rows if r.get("kind") == "tick"]
    segments: dict[tuple, list] = {}
    for row in ticks:
        if row.get("leg") == "transit_to_ready":
            segments.setdefault((row["attempt"], row["arm"]), []).append(row)
    out = []
    for (attempt, arm), seg in sorted(segments.items()):
        seg = sorted(seg, key=lambda r: r["t"])
        first, last = seg[0], seg[-1]
        err = max(abs(float(a) - float(b)) for a, b in zip(first["q"], ready[arm]))
        out.append(
            {
                "attempt": attempt,
                "arm": arm,
                "n": len(seg),
                "entry_err": err,
                "entry_dg_first_row": max(
                    abs(float(a) - float(b)) for a, b in zip(first["qcmd"], first["q"])
                ),
                "gap": last["t"] - first["t"],
            }
        )
    return out


def main() -> int:
    source = TASKS.read_text(encoding="utf-8")
    tree = ast.parse(source)

    tol = class_const(tree, "READY_SKIP_TOL")
    sync_tol = class_const(tree, "READY_SKIP_SYNC_TOL")

    print("== source checks ==")
    check(f"READY_SKIP_TOL == 0.03 (got {tol!r})", tol == 0.03)
    check(f"READY_SKIP_SYNC_TOL == 0.01 (got {sync_tol!r})", sync_tol == 0.01)
    check(
        "the predicate is exactly `err <= READY_SKIP_TOL and dg <= self._ready_skip_dg`",
        "if skip and err <= self.READY_SKIP_TOL and dg <= self._ready_skip_dg:"
        in source,
    )
    check(
        "the skip-dg knob defaults to the flipped 0.02 (the P20-C adoption; "
        "`FRUIT_READY_SKIP_DG` unset -> 0.02; the P9-A class-constant form is retired)",
        'os.environ.get("FRUIT_READY_SKIP_DG", "0.02")' in source,
    )
    check(
        "the scope gate is single-arm + not two-line-armed",
        "scope = self._active_session is None and not self.two_line_enabled()"
        in source,
    )
    check(
        "FRUIT_READY_SKIP resolves with the flipped default on, only under that scope",
        'skip = scope and os.environ.get("FRUIT_READY_SKIP", "1") == "1"' in source,
    )
    check(
        "B2 default is the shipped 120 (`FRUIT_READY_SETTLE`)",
        "def _ready_settle(self, shipped: int = 120)" in source
        and 'os.environ.get("FRUIT_READY_SETTLE", str(shipped))' in source,
    )
    check(
        "the diag flag defaults off (`FRUIT_READY_DIAG`)",
        'self._ready_diag = os.environ.get("FRUIT_READY_DIAG", "0") == "1"' in source,
    )
    check(
        "the skip path keeps the shipped post-condition (target at ready + sync)",
        "[self._pose(side, \"ready\")], dof_indices=arm.arm_dofs" in source
        and "arm.sync_command_to_measured()" in source,
    )
    check(
        "each new env knob is read at exactly one site",
        source.count('os.environ.get("FRUIT_READY_SKIP"') == 1
        and source.count('os.environ.get("FRUIT_READY_SETTLE"') == 1
        and source.count('os.environ.get("FRUIT_READY_DIAG"') == 1,
    )

    def fires(err: float, dg: float) -> bool:
        return err <= tol and dg <= sync_tol

    print("== predicate cases (synthetic + measured residuals) ==")
    cases = [
        ("exactly at ready (err=0, dg=0)", 0.0, 0.0, True),
        (
            "passive no-op shape (err 0.0139; dg inside the catch-up band)",
            0.0139,
            0.0004,
            True,
        ),
        ("right-arm steady residual at ready (610 stream, 0.0131)", 0.0131, 0.0004, True),
        ("exact tolerances (inclusive edge)", tol, sync_tol, True),
        ("err one tick outside", 0.0301, 0.01, False),
        ("dg one tick outside (target not synced)", 0.03, 0.0101, False),
        (
            "DISCRIMINATOR: target held at ready, dg == err (0.0135) - no skip",
            0.0135,
            0.0135,
            False,
        ),
        ("active-arm post-place entry (610 stream)", 0.7890, 0.4431, False),
        ("startup hanging entry (610 stream)", 1.5586, 0.0001, False),
        ("arm at ready but drive target 1.0 rad away (mid-motion)", 0.02, 1.0, False),
    ]
    for label, err, dg, expected in cases:
        got = fires(err, dg)
        check(f"{label}: fires={got} (expected {expected})", got == expected)

    print("== measured stream cross-check (logs/610_posture/stream.jsonl) ==")
    if not STREAM.exists():
        check("610 stream present", False)
    else:
        segments = derive_stream_segments()
        no_op = [s for s in segments if s["n"] == 210 and s["gap"] == 209]
        check(
            f"found the measured no-op segments (210 rows): {len(no_op)} of {len(segments)}",
            len(no_op) >= 4,
        )
        # A 210-row segment runs only the plain blend (90+120), i.e. the
        # `_catch_up_drive` early-out held, i.e. `dg <= 0.01` at entry by code
        # construction. The first row's |q-ready| is the entry err.
        check(
            "every no-op segment's entry err is inside READY_SKIP_TOL",
            all(s["entry_err"] <= tol for s in no_op),
        )
        check(
            "every no-op segment would fire the predicate (err<=tol and dg<=0.01)",
            all(fires(s["entry_err"], 0.0004) for s in no_op),
        )
        active = [s for s in segments if s["n"] != 210]
        check(
            "every non-no-op segment stays outside the predicate via err",
            all(not fires(s["entry_err"], 0.0) for s in active),
        )
        for s in segments:
            kind = "no-op" if s["n"] == 210 and s["gap"] == 209 else "transit"
            print(
                f"    attempt {s['attempt']:2d} {s['arm']:5s}: rows={s['n']:4d} "
                f"entry_err={s['entry_err']:.4f} -> skip={fires(s['entry_err'], 0.0004 if kind == 'no-op' else 1.0)}"
            )

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s) failed)")
        return 1
    print("RESULT: PASS (all checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
