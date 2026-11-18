#!/usr/bin/env python3
"""P207: read the `[cmd]` stream of a direct-policy cell.

The row is printed every 4 control ticks (one executed waypoint at
`FRUIT_POLICY_ACTION_HOLD=4`). With `FRUIT_POLICY_TARGET_RATE` armed the row also
carries the requested target (`req=`), so the emitted and the requested streams
can be compared in the same run.

Endpoints per cell:
  * per-waypoint target step (max over joints): p50 / p95 / max
  * the fraction of steps > 0.10 rad
  * lag-1 autocorrelation of each joint's target step (p50 over joints)
  * achieved/target RMS ratio per joint (the drive's follow)
  * the raw request's step and how much the cap removed
  * the `[rl] episode` outcomes and the `[close]` rows
"""
from __future__ import annotations

import argparse
import re
import numpy as np

CMD = re.compile(
    r"\[cmd\] t=(\d+) tgt=\[([^\]]*)\](?:\s+req=\[([^\]]*)\])?\s+meas=\[([^\]]*)\]"
)
EP = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([0-9.]+)cm bin=(\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+)"
)


def rows(path):
    out = []
    for line in open(path, errors="ignore"):
        m = CMD.search(line)
        if m:
            out.append(
                (
                    int(m.group(1)),
                    np.array([float(x) for x in m.group(2).split()]),
                    None if m.group(3) is None else np.array([float(x) for x in m.group(3).split()]),
                    np.array([float(x) for x in m.group(4).split()]),
                )
            )
    return out


def segments(r):
    segs = []
    cur = []
    for row in r:
        if cur and row[0] < cur[-1][0]:
            segs.append(cur)
            cur = []
        cur.append(row)
    if cur:
        segs.append(cur)
    return segs


def stats(name, deltas):
    if deltas is None or len(deltas) == 0:
        return
    mx = np.abs(deltas).max(axis=1)
    print(
        f"  {name}: n={len(deltas):4d} max-joint step p50={np.median(mx):.4f} "
        f"p95={np.percentile(mx, 95):.4f} max={mx.max():.4f} "
        f">0.10={np.mean(mx > 0.10):.1%}"
    )
    rho = []
    for j in range(deltas.shape[1]):
        x = deltas[:, j] - deltas[:, j].mean()
        if x.std() > 1e-12:
            rho.append(float((x[:-1] * x[1:]).sum() / (x * x).sum()))
    if rho:
        print(
            f"     lag-1 step autocorr: p50={np.median(rho):+.2f} "
            f"range=[{min(rho):+.2f},{max(rho):+.2f}]"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    a = ap.parse_args()
    r = rows(a.log)
    print(f"{a.log}: {len(r)} [cmd] rows")
    segs = segments(r)
    d_emit = []
    d_req = []
    d_meas = []
    for ep in segs:
        if len(ep) < 4:
            continue
        # Only adjacent printed waypoints (4 ticks at action_hold=4). A servo
        # hand-back skips many ticks between two `[cmd]` rows; differencing across
        # that gap reads a 0.5-1.1 rad "step" that is not a command transient
        # (measured: 3 of 780 pairs in C_s303).
        tt = np.array([x[0] for x in ep])
        keep = np.diff(tt) == 4
        tgt = np.array([x[1] for x in ep])
        meas = np.array([x[3] for x in ep])
        d_emit.append(np.diff(tgt, axis=0)[keep])
        dm = np.diff(meas, axis=0)[keep]
        # A measured step above the joint speed limit is a physics/teleport
        # event, not a tracking read; exclude it from the achieved/target ratio.
        physical = np.abs(dm).max(axis=1) <= 5.45 * 4.0 / 120.0
        d_meas.append(dm[physical])
        if ep[0][2] is not None:
            d_req.append(np.diff(np.array([x[2] for x in ep]), axis=0)[keep])
    if d_emit:
        de = np.concatenate(d_emit)
        dm = np.concatenate(d_meas)
        stats("emitted", de)
        stats("measured", dm)
        rms_t = np.sqrt((de ** 2).mean(axis=0))
        rms_m = np.sqrt((dm ** 2).mean(axis=0))
        print(f"     achieved/target RMS per joint={np.round(rms_m / np.maximum(rms_t, 1e-12), 2)}")
    if d_req:
        dr = np.concatenate(d_req)
        stats("requested", dr)
        de = np.concatenate(d_emit)
        print(f"     cap removed p50={np.median(np.abs(dr) - np.abs(de)):.4f} rad")
        # The cap's own signature: how far the emitted target trails the request.
        residual = []
        for ep in segs:
            if len(ep) < 4 or ep[0][2] is None:
                continue
            tt = np.array([x[0] for x in ep])
            keep = np.r_[True, np.diff(tt) == 4]
            for x, k in zip(ep, keep):
                if k and x[2] is not None:
                    residual.append(np.abs(x[2] - x[1]).max())
        if residual:
            r = np.array(residual)
            print(
                f"     request-target residual: p50={np.median(r):.4f} "
                f"p95={np.percentile(r, 95):.4f} max={r.max():.4f} "
                f"binding={np.mean(r > 1e-9):.1%}"
            )
    print("outcomes:")
    for line in open(a.log, errors="ignore"):
        m = EP.search(line)
        if m:
            extra = ""
            g = re.search(r"gap_close=([0-9.]+)mm", line)
            if g:
                extra = f" gap_close={g.group(1)}mm"
            print(
                f"  ep{m.group(1)} {m.group(2):10s} d={m.group(3)}cm "
                f"arm={m.group(5):5s} s={m.group(6):5s} g={m.group(7):5s} "
                f"p={m.group(8):5s} ticks={m.group(9)}{extra}"
            )


if __name__ == "__main__":
    main()
