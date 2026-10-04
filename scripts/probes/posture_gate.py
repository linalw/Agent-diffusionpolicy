"""Offline posture-gate check on a recorded joint stream (P2 acceptance).

Reads the stream the posture probe wrote and prints the Oracle's P2 criteria,
each with PASS/FAIL:

  * measured per-tick joint step (flag > 0.30 rad)
  * commanded per-tick step (flag > 0.15 rad)
  * wrist rate (flag > 1.0 rad/tick)
  * tool-axis flips (must be 0)
  * tool tilt > 90 deg (must be 0)
  * reconfigured attempts (must be 0)
  * deliberate teleports (must be 0)
  * ready_err after every transit_to_ready (<= 0.05 rad)
  * leg-boundary command jumps that are not teleports (<= 0.05 rad/tick)

Usage: python3 /tmp/posture_gate.py logs/461_posture/stream.jsonl
"""

from __future__ import annotations

import importlib.util
import sys

PROBE = "/home/ubuntu/linalw/Projects/opencode/Agent-diffusionpolicy/scripts/421_posture_probe.py"


def load_module(path):
    spec = importlib.util.spec_from_file_location("posture_probe", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["posture_probe"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    stream = sys.argv[1] if len(sys.argv) > 1 else "logs/461_posture/stream.jsonl"
    p = load_module(PROBE)
    report = p.analyze_stream(p.load_stream(stream))

    fails = []

    def check(name, value, ok, limit=""):
        status = "PASS" if ok else "FAIL"
        if not ok:
            fails.append(name)
        print(f"[gate] {status}  {name}: {value} {limit}")

    m_step = max((s["dq_max"] for s in report["segments"]), default=0.0)
    worst_step = max(report["segments"], key=lambda s: s["dq_max"])
    check("max measured step <= 0.30 rad/tick", f"{m_step:.4f}",
          m_step <= 0.30, f"(A{worst_step['attempt']} {worst_step['arm']} {worst_step['leg']})")

    m_cmd = max((s["cmd_max"] for s in report["segments"]), default=0.0)
    worst_cmd = max(report["segments"], key=lambda s: s["cmd_max"])
    check("max commanded step <= 0.15 rad/tick", f"{m_cmd:.4f}",
          m_cmd <= 0.15, f"(A{worst_cmd['attempt']} {worst_cmd['arm']} {worst_cmd['leg']})")

    m_wrist = max((s["wrist_max"] for s in report["segments"]), default=0.0)
    check("max wrist rate <= 1.0 rad/tick", f"{m_wrist:.4f}", m_wrist <= 1.0)

    flips = report["totals"]["axis_flips"]
    check("tool-axis flips == 0", flips, flips == 0)

    m_tilt = max((s["tilt_max"] or 0.0 for s in report["segments"]), default=0.0)
    worst_tilt = max(report["segments"], key=lambda s: s["tilt_max"] or 0.0)
    check("max tool tilt <= 90 deg", f"{m_tilt:.1f}",
          m_tilt <= 90.0, f"(A{worst_tilt['attempt']} {worst_tilt['arm']} {worst_tilt['leg']})")

    recon = [f"A{f['attempt']} {f['arm']}" for f in report["flags"] if f.get("reconfigured")]
    check("reconfigured == 0", recon or 0, not recon)

    tele = report["totals"]["teleports"]
    tele_list = [f"A{t['attempt']} {t['arm']} {t['leg']} {t['max_rad']:.2f}" for t in report["teleports"]]
    check("deliberate teleports == 0", tele_list or 0, tele == 0)

    ready_bad = [
        (e["attempt"], e["arm"], e["ready_err"], e["ready_err_joint"])
        for e in report["attempts"]
        if e["ready_err"] > 0.05
    ]
    worst_ready = max((e["ready_err"] for e in report["attempts"]), default=0.0)
    check("ready_err <= 0.05 after every transit_to_ready", f"{worst_ready:.4f} rad",
          not ready_bad, str(ready_bad[:4]))

    jumps = [b for b in report["boundaries"] if not b["teleports"]]
    worst_jump = max((b["cmd_jump"] for b in jumps), default=0.0)
    bad_jumps = [(b["cmd_jump"], b["cmd_joint"], b["from"], b["to"]) for b in jumps
                 if b["cmd_jump"] > 0.05]
    check("non-teleport boundary command jumps <= 0.05 rad/tick", f"{worst_jump:.4f}",
          not bad_jumps, str(bad_jumps[:3]))

    print()
    if fails:
        print(f"[gate] VERDICT: FAIL - {len(fails)} criterion/criteria: {', '.join(fails)}")
        return 1
    print("[gate] VERDICT: PASS - all P2 posture criteria met")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
