#!/usr/bin/env python3
"""P112 fixture report - the closure's own numbers, tabulated.

Reads the `[p112] cell` rows from `logs/p112/fixture_*.log` and prints:

  1. the **centring** table: `off0 -> off_end` per hand kind x protocol x arrival
     offset, with the pad count and the delivered force;
  2. the **stiffness** read: the same change per k, i.e. whether the cap is what
     bounds the closure;
  3. the **measured penetration**: a contacting pad's face radius IS the
     payload's extent along that pad axis, so `pen = face - cmd/2` is the *real*
     over-penetration - the number the width law (`meshes.axis_extent` x 0.98)
     is supposed to set to ~0.5-1 % of the diameter;
  4. the **crush / bat** columns the battery gates on.

    python3 logs/p112/p112_fixture_report.py logs/p112/fixture_*.log
    python3 logs/p112/p112_fixture_report.py --check logs/p112/fixture_*.log
"""

from __future__ import annotations

import glob
import re
import statistics as st
import sys

ROW = re.compile(
    r"\[p112\] cell kind=(?P<kind>\w+) k=\s*(?P<k>[0-9.]+) hold=\s*(?P<hold>[0-9.]+) "
    r"freeze=(?P<frz>[01]) (?P<fruit>\w+)\s+d=\s*(?P<d>[0-9.]+) "
    r"off0=\s*(?P<off0>[0-9.]+) off_frz=\s*(?P<off_frz>[0-9.nan]+) "
    r"off_end=\s*(?P<off_end>[0-9.]+) d_off=\s*(?P<d_off>[-+0-9.]+) "
    r"pads=(?P<pads>[0-9])/(?P<npads>[0-9]) fmax=\s*(?P<fmax>[0-9.]+)N "
    r"bat=\s*(?P<bat>[0-9.]+) aper=\s*(?P<aper>[-0-9.]+) \(cmd\s*(?P<cmd>[0-9.]+)\) "
    r"sep-dia=\s*(?P<sepdia>[-+0-9.]+) dz=\s*(?P<dz>[-+0-9.]+)"
)


def rows(paths):
    out = []
    for path in paths:
        try:
            text = open(path, errors="replace").read().splitlines()
        except OSError:
            continue
        for line in text:
            m = ROW.search(line)
            if m:
                r = {k: (float(v) if k not in ("kind", "fruit") else v)
                     for k, v in m.groupdict().items()}
                if r.get("hold") is None:
                    r["hold"] = 0.0
                out.append(r)
    return out


def table(rs, title):
    print(f"\n{title}")
    print("  " + "-" * 96)
    print(f"  {'group':26s} {'off0~':>6s} {'n':>3s} {'med d_off':>10s} {'min':>7s} "
          f"{'max':>7s} {'pads':>5s} {'fmax N':>7s} {'bat mm':>7s} {'sep-dia':>8s}")
    for key in sorted({(r["kind"], int(r["frz"]), r["hold"], r["k"]) for r in rs}):
        sub = [r for r in rs if (r["kind"], int(r["frz"]), r["hold"], r["k"]) == key]
        for off in sorted({round(r["off0"]) for r in sub}):
            cell = [r for r in sub if abs(r["off0"] - off) < 0.6]
            if not cell:
                continue
            ds = [r["d_off"] for r in cell]
            print(f"  {key[0]:6s} frz={key[1]} hold={key[2]:6.0f} k={key[3]:6.0f} "
                  f"{off:5d} {len(cell):3d} {st.median(ds):+10.2f} {min(ds):+7.2f} "
                  f"{max(ds):+7.2f} {sum(r['pads'] for r in cell) / len(cell):5.1f} "
                  f"{max(r['fmax'] for r in cell):7.2f} "
                  f"{st.median([r['bat'] for r in cell]):7.2f} "
                  f"{st.median([r['sepdia'] for r in cell]):+8.2f}")


def summary(rs):
    print("\nSUMMARY (one line per hand x protocol x k, all offsets pooled)")
    print("  " + "-" * 96)
    print(f"  {'kind':6s} {'frz':>3s} {'hold':>7s} {'k':>7s} {'n':>3s} "
          f"{'med d_off':>10s} {'<0 share':>9s} {'pads=all':>9s} {'sep-dia':>8s}")
    for key in sorted({(r["kind"], int(r["frz"]), r["hold"], r["k"]) for r in rs}):
        sub = [r for r in rs if (r["kind"], int(r["frz"]), r["hold"], r["k"]) == key]
        ds = [r["d_off"] for r in sub]
        neg = sum(1 for v in ds if v < -0.5)
        allp = sum(1 for r in sub if int(r["pads"]) == int(r["npads"]))
        print(f"  {key[0]:6s} {key[1]:3d} {key[2]:7.0f} {key[3]:7.0f} {len(sub):3d} "
              f"{st.median(ds):+10.2f} {neg / len(sub) * 100:8.0f}% "
              f"{allp:4d}/{len(sub):<4d} "
              f"{st.median([r['sepdia'] for r in sub]):+8.2f}")


def penetration(rs):
    """The measured over-penetration, from the pads' own face radii."""
    print("\nTHE MEASURED PENETRATION (the width law's own error)")
    print("  " + "-" * 96)
    print("  A contacting pad's **face radius** is the payload's extent along that")
    print("  pad's axis, so `face - cmd/2` is the real over-penetration.  The law")
    print("  (`axis_extent x 0.98`) is meant to set it to ~0.5-1 % of the diameter.")
    print(f"  {'kind':6s} {'fruit':10s} {'d mm':>6s} {'cmd/2':>7s} {'face':>7s} "
          f"{'pen mm':>7s} {'pen/d':>7s}")
    seen = set()
    for r in rs:
        key = (r["kind"], r["fruit"], round(r["d"]))
        if key in seen:
            continue
        seen.add(key)
        # the face radius is not in the regex (a 3-vector); recompute from the
        # aperture and the pad count-witnessed rows: `aper/2` is the mean face.
        face = r["aper"] / 2.0
        print(f"  {r['kind']:6s} {r['fruit']:10s} {r['d']:6.1f} {r['cmd'] / 2:7.2f} "
              f"{face:7.2f} {face - r['cmd'] / 2:+7.2f} "
              f"{(face - r['cmd'] / 2) / r['d'] * 100:+6.1f}%")


def main() -> int:
    paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not paths:
        paths = sorted(glob.glob("logs/p112/fixture_*.log"))
    rs = rows(paths)
    if "--check" in sys.argv:
        assert len(rs) >= 60, f"only {len(rs)} cells parsed from {paths}"
        for r in rs:
            assert r["npads"] in (3.0, 4.0), r
            assert r["d"] > 20.0, r
        print(f"fixture rows OK: {len(rs)} cells from {len(paths)} logs")
        return 0
    print(f"P112 fixture - {len(rs)} closures from {len(paths)} logs")
    table(rs, "1. THE CENTRING TABLE (every cell)")
    summary(rs)
    penetration(rs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
