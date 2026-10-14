#!/usr/bin/env python3
"""R9: the bounded post-training lane's N=5 endpoint readout.

    python3 scripts/196_r9_report.py --dir logs/r9/A_direct_ab --a A --b B
    python3 scripts/196_r9_report.py --self-test

Reads the per-run logs of a direct-presentation A/B (the `scripts/112_rl_ab.sh`
convention: `<ARM>_<run>.log`), parses the `[rl] episode ...` outcome lines and
the `[carry] ...` diag lines (`FRUIT_CARRY_DIAG=1`, W8-B), and prints:

  * per arm: pooled + per-run outcomes, per-class/per-arm table, median cycle;
  * the same-fruit pairing (fruit name only - the W7-C/W8-A convention) with the
    one-sided sign test;
  * the R9 primary endpoint: the **paired carried-class conversion**
    (carried -> ok vs ok -> carried on same-fruit pairs), its sign p and the
    pre-registered reading (a 6-0 discordant split is the p <= 0.05 edge at
    N=5; the W8-B 5-1 read was p = 0.109);
  * the P4 qualifiers (pooled rate vs baseline, strawberry bucket, new failure
    reasons, cycle) and the R9 endpoint verdict lines;
  * the `[carry]` mechanism readout (R9 section 3): clean vs slip-event legs by
    leg name, the `clean_slip` distribution, and the pre-onset facet (onset
    row, force / separation / contact state at onset, the onset -> loss
    window) - the live line is contact-agnostic at onset, so no-contact legs
    are split out by `force@onset`.

Report only: no simulator, no writes. The pre-registered endpoint and the
adoption separation are stated in the output; adoption itself always needs its
own owner gate and is never implied by this script.

**Baseline scope.** The primary endpoint's pooled-rate baseline is the
**batch's own arm A** - the same-instrumentation control inside the same
interleaved runs - not the pre-registration's wording of a "28-29 % record
baseline": that figure is the W8-A record of the same checkpoint, quoted for
context only, and this script never reads an external rate record. A single
batch is one instrumented scenario (the known spread: `moe_v13s` reads 28 % in
W8-A and 33 % in this batch), which is why the paired within-batch read is the
endpoint.
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import re
import statistics as st
import tempfile

EP_ENV = re.compile(
    r"\[rl\] episode (\d+): (\w+) grade=(\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+)"
)
EP_OUT = re.compile(
    r"\[rl\] episode (\d+): (\w+) d=([\d.]+)cm bin=(-?\d+) arm=(\w+) "
    r"success=(\w+) grasped=(\w+) placed=(\w+) ticks=(\d+)(?: decision=(\d+))? "
    r"reward=([-+0-9.eE]+) notes=(\[.*?\]) presentation="
)
CARRY = re.compile(
    r"\[carry\] (?P<side>\w+) (?P<leg>\w+): ticks=(?P<ticks>\d+)/(?P<n>\d+) "
    r"clean_slip_max=(?P<slip>[\d.]+)mm in-hand_vmax=(?P<vmax>[\d.]+) "
    r"onset_row=(?P<onset>\w+) force@onset=(?P<force>\S+?)N "
    r"sep@onset=(?P<sep>\S+?)mm contacts@onset=(?P<con>\S+?) "
    r"min_contacts=(?P<cmin>\d+) force_min=(?P<fmin>[-\d.]+)N "
    r"loss_row=(?P<loss>\w+) guard=(?P<guard>\d+)"
)
#: `FRUIT_ACQ_DIAG=1`: the close-start tip-fruit offset (the pre-onset centring
#: read, mm, three channels) and the fire-time latin geometry.
ACQ = re.compile(
    r"\[acq\] \w+ idx=\d+: .*close_start=\(([^)]*)\)mm "
)
NOTE_SUFFIX = re.compile(r",\s*lead=[\d.]+s/reach=[\d.]+\)")


def sign_test_p(better: int, worse: int) -> float:
    """One-sided P(X >= better), X ~ Bin(better + worse, 0.5)."""
    n = better + worse
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(better, n + 1)) / (2.0 ** n)


def _floats(text: str) -> list[float]:
    out = []
    for part in text.split(","):
        part = part.strip()
        try:
            out.append(float(part))
        except ValueError:
            out.append(float("nan"))
    return out


def _median(values):
    values = [v for v in values if v is not None and not math.isnan(v)]
    return st.median(values) if values else float("nan")


def parse_log(path: str) -> dict:
    """One run's episodes + its `[carry]` legs + its `[acq]` close offsets."""
    episodes: list[dict] = []
    carries: list[dict] = []
    close_start: list[float] = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = EP_ENV.search(line)
        if m:
            episodes.append(
                {
                    "ep": int(m.group(1)),
                    "fruit": m.group(2),
                    "grade": m.group(3),
                    "d": float(m.group(4)),
                    "arm": m.group(6),
                    "success": None,
                }
            )
            continue
        m = EP_OUT.search(line)
        if m and episodes and episodes[-1]["ep"] == int(m.group(1)):
            episodes[-1].update(
                success=m.group(6) == "True",
                grasped=m.group(7) == "True",
                placed=m.group(8) == "True",
                ticks=int(m.group(9)),
                reward=float(m.group(11)),
                notes=m.group(12),
            )
            continue
        m = CARRY.search(line)
        if m:
            d = m.groupdict()
            carries.append(
                {
                    "side": d["side"],
                    "leg": d["leg"],
                    "slip": float(d["slip"]),
                    "onset": None if d["onset"] == "None" else int(d["onset"]),
                    "force": (
                        float(d["force"]) if d["force"] not in ("n/a",) else None
                    ),
                    "sep": float(d["sep"]) if d["sep"] not in ("n/a",) else None,
                    "con": int(d["con"]) if d["con"].isdigit() else None,
                    "loss": None if d["loss"] == "None" else int(d["loss"]),
                }
            )
            continue
        m = ACQ.search(line)
        if m:
            close_start.extend(_floats(m.group(1)))
    return {"episodes": episodes, "carries": carries, "close_start": close_start}


def load(directory: str, a_label: str, b_label: str):
    arms: dict[str, dict[int, dict]] = {a_label: {}, b_label: {}}
    for path in sorted(glob.glob(os.path.join(directory, "*.log"))):
        stem = os.path.basename(path)[:-4]
        if "_" not in stem:
            continue
        label, run = stem.rsplit("_", 1)
        if label in arms and run.isdigit():
            arms[label][int(run)] = parse_log(path)
    return arms


def klass(ep: dict) -> str:
    if ep.get("success"):
        return "ok"
    if ep.get("grasped") is False:
        return "no-contact"
    if ep.get("grasped") and not ep.get("placed"):
        return "carried"
    return "other"


def classes(rows: list[dict]) -> dict[str, int]:
    out = {"ok": 0, "no-contact": 0, "carried": 0, "other": 0}
    for ep in rows:
        out[klass(ep)] += 1
    return out


def _norm_notes(notes: str) -> set[str]:
    """Failure reasons: split the notes list, drop the acq-note suffix and
    numbers. The W7-B lesson: the adaptive-lead suffix is an instrumentation
    artifact, not a failure class."""
    text = notes.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    out = set()
    for part in re.split(r"',\s*'|\",\s*\"", text):
        part = part.strip().strip("'\"")
        if not part:
            continue
        part = NOTE_SUFFIX.sub(")", part)
        out.add(re.sub(r"[-+0-9.]+", "#", part))
    return out


def carry_section(label: str, legs: list[dict]) -> None:
    print(f"  [{label}] carry legs: {len(legs)}")
    for group, pred in (
        ("grasp_lift", lambda x: x["leg"].startswith("grasp_lift")),
        ("place", lambda x: x["leg"].startswith("place")),
    ):
        sel = [x for x in legs if pred(x)]
        if not sel:
            continue
        onset = [x for x in sel if x["onset"] is not None]
        clean = [x for x in sel if x["onset"] is None]
        lost = [x for x in sel if x["loss"] is not None]
        vals = sorted(x["slip"] for x in sel)
        n = len(vals)
        p90 = vals[min(n - 1, int(math.ceil(0.9 * n)) - 1)]
        print(
            f"    {group:10s} n={len(sel):3d} clean(<2mm)={len(clean):3d} "
            f"slip_event={len(onset):3d} contact_loss={len(lost):3d} | "
            f"clean_slip mm min={vals[0]:.2f} med={st.median(vals):.2f} "
            f"p90={p90:.2f} max={vals[-1]:.2f}"
        )
        if onset:
            contacts = [x for x in onset if (x["force"] or 0.0) > 0.0]
            zero = len(onset) - len(contacts)
            rows = [x["onset"] for x in onset]
            forces = [x["force"] for x in contacts if x["force"] is not None]
            window = [
                x["loss"] - x["onset"]
                for x in onset
                if x["loss"] is not None and x["onset"] is not None
            ]
            single = sum(1 for x in onset if x["con"] == 1)
            pried = sum(1 for x in onset if x["sep"] is not None and x["sep"] >= 97.0)
            print(
                f"      pre-onset facet: onset_row med={_median(rows):.0f} "
                f"(range {min(rows)}-{max(rows)}); force@onset med="
                f"{_median(forces):.2f}N over {len(forces)} contact legs "
                f"({zero} zero-force/no-contact); contacts@onset==1 {single}/"
                f"{len(onset)}; onset->loss med={_median(window):.0f} ticks "
                f"({len(window)} lost); sep@onset>=97mm {pried}/{len(onset)}"
            )


def report(directory: str, a_label: str, b_label: str) -> int:
    arms = load(directory, a_label, b_label)
    if not arms[a_label] or not arms[b_label]:
        print(f"no {a_label}_*/{b_label}_*.log pairs in {directory}")
        return 2
    runs = sorted(set(arms[a_label]) & set(arms[b_label]))

    for label in (a_label, b_label):
        print(f"=== arm {label}")
        for run in runs:
            eps = arms[label][run]["episodes"]
            line = "  ".join(
                f"{e['ep']}:{e['fruit'][:4]}/{e['d']:.1f}/"
                f"{klass(e) if e.get('success') is not None else '?'}"
                for e in eps
            )
            ok = sum(1 for e in eps if e.get("success"))
            print(f"  run {run}: {ok}/{len(eps)}  {line}")

    pooled = {
        label: [e for run in runs for e in arms[label][run]["episodes"]]
        for label in (a_label, b_label)
    }
    print()
    for label in (a_label, b_label):
        rows = pooled[label]
        ok = sum(1 for e in rows if e.get("success"))
        ticks = [e["ticks"] for e in rows if e.get("ticks")]
        succ = [e["ticks"] for e in rows if e.get("success") and e.get("ticks")]
        if ticks:
            print(
                f"  pooled {label}: {ok}/{len(rows)} ({ok / max(len(rows), 1):.0%})"
                f"  median ticks {st.median(ticks):.0f} (successes "
                f"{st.median(succ):.0f})"
            )
        else:
            print(f"  pooled {label}: no episodes")
    for label in (a_label, b_label):
        rows = pooled[label]
        t = classes(rows)
        left = classes([e for e in rows if e.get("arm") == "left"])
        right = classes([e for e in rows if e.get("arm") == "right"])
        print(
            f"  classes {label}: ok={t['ok']} no-contact={t['no-contact']} "
            f"carried-not-placed={t['carried']} other={t['other']} | "
            f"left n={sum(left.values())} {left} | "
            f"right n={sum(right.values())} {right}"
        )

    # ---------------- same-fruit pairing (fruit name only) ----------------- #
    better = worse = both_ok = both_fail = 0
    mismatched = 0
    transitions: dict[tuple[str, str], list[str]] = {}
    disc_b: list[str] = []
    disc_a: list[str] = []
    for run in runs:
        left = {e["ep"]: e for e in arms[a_label][run]["episodes"]}
        right = {e["ep"]: e for e in arms[b_label][run]["episodes"]}
        for ep in sorted(set(left) & set(right)):
            ea, eb = left[ep], right[ep]
            if ea.get("success") is None or eb.get("success") is None:
                continue
            if ea["fruit"] != eb["fruit"]:
                mismatched += 1
                continue
            pair = (klass(ea), klass(eb))
            text = (
                f"  run{run} ep{ep:2d} {ea['fruit']:10s} "
                f"A={pair[0]:11s} -> B={pair[1]:11s}"
            )
            transitions.setdefault(pair, []).append(text)
            oka, okb = bool(ea["success"]), bool(eb["success"])
            if oka and okb:
                both_ok += 1
            elif oka and not okb:
                worse += 1
                disc_a.append(text)
            elif not oka and okb:
                better += 1
                disc_b.append(text)
            else:
                both_fail += 1
    p_rate = sign_test_p(better, worse)
    print()
    print(
        f"  paired same-fruit: both ok {both_ok}, both fail {both_fail}, "
        f"{b_label}-only ok {better}, {a_label}-only ok {worse} "
        f"(excluded fruit-class differs {mismatched})"
    )
    print(f"  sign test ({b_label} better): p = {p_rate:.4f} "
          f"(discordant {better + worse})")

    # ------------- the R9 primary endpoint: carried-class pairs ------------ #
    car_conv = len(transitions.get(("carried", "ok"), []))
    car_reg = len(transitions.get(("ok", "carried"), []))
    p_car = sign_test_p(car_conv, car_reg)
    print()
    print(f"  [r9] carried-class pair transitions (same-fruit):")
    for pair in sorted(transitions):
        mark = ""
        if pair == ("carried", "ok"):
            mark = "  <== candidate conversion"
        elif pair == ("ok", "carried"):
            mark = "  <== baseline conversion (regression)"
        print(f"    {pair[0]:11s} -> {pair[1]:11s} {len(transitions[pair]):3d}{mark}")
    print(
        f"  [r9] carried-class conversion: {b_label}-only {car_conv} / "
        f"{a_label}-only {car_reg}; one-sided sign p = {p_car:.4f} "
        f"(6-0 is the p<=0.05 edge at N=5)"
    )
    if disc_a:
        print("  [r9] baseline-conversion pairs:")
        print("\n".join(disc_a))
    if disc_b:
        print("  [r9] candidate-conversion pairs:")
        print("\n".join(disc_b))

    # --------------------------- P4 qualifiers ----------------------------- #
    rate_a = sum(1 for e in pooled[a_label] if e.get("success")) / max(
        len(pooled[a_label]), 1
    )
    rate_b = sum(1 for e in pooled[b_label] if e.get("success")) / max(
        len(pooled[b_label]), 1
    )
    straw_a = [e for e in pooled[a_label] if e["fruit"] == "strawberry"]
    straw_b = [e for e in pooled[b_label] if e["fruit"] == "strawberry"]
    sa = sum(1 for e in straw_a if e.get("success"))
    sb = sum(1 for e in straw_b if e.get("success"))
    straw_ok = (not straw_a) or (not straw_b) or (
        sb / len(straw_b) >= sa / len(straw_a)
    )
    reasons_a: set[str] = set()
    reasons_b: set[str] = set()
    for e in pooled[a_label]:
        if not e.get("success"):
            reasons_a |= _norm_notes(e.get("notes", "[]"))
    for e in pooled[b_label]:
        if not e.get("success"):
            reasons_b |= _norm_notes(e.get("notes", "[]"))
    new = sorted(reasons_b - reasons_a)
    ta = st.median([e["ticks"] for e in pooled[a_label] if e.get("ticks")])
    tb = st.median([e["ticks"] for e in pooled[b_label] if e.get("ticks")])
    print()
    print(f"  [r9] pooled rate {b_label} {rate_b:.0%} vs {a_label} {rate_a:.0%} "
          f"[{'above' if rate_b > rate_a else 'not above'}]")
    print(f"  [r9] strawberry {b_label} {sb}/{len(straw_b)} vs {a_label} "
          f"{sa}/{len(straw_a)} [{'ok' if straw_ok else 'worse'}]")
    print(f"  [r9] new failure reasons: {new if new else 'none'}")
    print(f"  [r9] cycle {b_label} {tb:.0f} vs {a_label} {ta:.0f} ticks "
          f"({(tb - ta) / ta:+.1%})")

    primary = (rate_b > rate_a) and (car_conv > car_reg) and (p_car <= 0.05)
    secondary = (tb <= 0.95 * ta and rate_b >= rate_a) or (
        rate_b >= rate_a and p_rate <= 0.05 and better > worse
    )
    print()
    print(f"  [r9] primary endpoint (pooled rate above baseline AND "
          f"carried-class conversion significant): "
          f"{'PASS' if primary else 'FAIL'}")
    print(f"  [r9] secondary (P4 rule: cycle >=5% faster with success "
          f"non-inferior, or rate+sign p<=0.05): "
          f"{'PASS' if secondary else 'FAIL'}")
    print("  [r9] adoption: never implied by this readout - the pre-registration "
          "requires the owner gate, a fresh pinned canary and (on an interface "
          "change) a new reference set.")
    if not primary:
        print("  [r9] kill criterion: the N=5 paired carried-class split is not "
              "candidate-positive -> close the lane negative and publish.")

    # --------------------------- carry mechanism --------------------------- #
    print()
    print("== [carry] mechanism readout (FRUIT_CARRY_DIAG live lines; the live "
          "onset is contact-agnostic, so zero-force onsets are split out):")
    for label in (a_label, b_label):
        legs = [x for run in runs for x in arms[label][run]["carries"]]
        carry_section(label, legs)
        close = [
            v for run in runs for v in arms[label][run]["close_start"]
            if not math.isnan(v)
        ]
        if close:
            import statistics as _st

            print(f"  [{label}] close-start tip-fruit |y| offset: n={len(close)} "
                  f"median={_st.median(close):.1f}mm "
                  f"max={max(close):.1f}mm")
    return 0 if primary else 1


# --------------------------------------------------------------------------- #
def _ep(ep, fruit, d, arm, outcome="ok", ticks=1800, notes="[]"):
    ok = outcome == "ok"
    grasped = outcome != "no-contact"
    placed = ok
    return (
        f"[fruit] [rl] episode {ep}: {fruit} d={d}cm bin=1 arm={arm} "
        f"success={ok} grasped={grasped} placed={placed} ticks={ticks} "
        f"decision=800 reward=0.8 notes={notes} presentation=direct ablate=none"
    )


def _env(ep, fruit, arm="left"):
    return f"[fruit] [rl] episode {ep}: {fruit} grade=A d=6.0cm bin=1 arm={arm} y=+0.1"


def _carry(side, leg, slip, onset=None, force="n/a", sep="n/a", con="n/a",
           loss=None, cmin=1):
    onset_s = "None" if onset is None else str(onset)
    loss_s = "None" if loss is None else str(loss)
    return (
        f"[fruit] [carry] {side} {leg}: ticks=150/150 clean_slip_max={slip}mm "
        f"in-hand_vmax=0.100 onset_row={onset_s} force@onset={force}N "
        f"sep@onset={sep}mm contacts@onset={con} min_contacts={cmin} "
        f"force_min=4.00N loss_row={loss_s} guard=0 events=0 holds=0 "
        f"reseat=0.0mm relief=0 gap_start=0.0mm open_max=0.0mm"
    )


def self_test() -> int:
    failures = []
    fruits = ["peach", "kiwi", "apple", "peach", "grape", "pear", "orange", "tomato"]
    with tempfile.TemporaryDirectory() as tmp:
        # Scenario 1: the candidate converts 6 carried -> ok (6-0, p = 0.0156).
        with open(os.path.join(tmp, "A_1.log"), "w", encoding="utf-8") as fh:
            for i, fruit in enumerate(fruits):
                fh.write(_env(i, fruit) + "\n")
                fh.write(_ep(i, fruit, "6.0", "left",
                             "ok" if i < 1 else "carried") + "\n")
                fh.write(_carry(
                    "left", "grasp_lift", "0.04" if i < 1 else "250.0",
                    None if i < 1 else 90,
                    "0.00" if i < 1 else "4.90",
                    "n/a" if i < 1 else "55.0",
                    "n/a" if i < 1 else 1,
                    None if i < 1 else 140,
                ) + "\n")
        with open(os.path.join(tmp, "B_1.log"), "w", encoding="utf-8") as fh:
            for i, fruit in enumerate(fruits):
                fh.write(_env(i, fruit) + "\n")
                fh.write(_ep(i, fruit, "6.0", "left",
                             "ok" if i < 7 else "carried") + "\n")
                fh.write(_carry("left", "grasp_lift", "0.03",
                                None if i < 7 else 150) + "\n")
        out = report(tmp, "A", "B")
        if out != 0:
            failures.append("6-0 carried conversion did not read PASS")
        # Scenario 2: a carried regression (candidate worse) must read negative.
        with open(os.path.join(tmp, "B_1.log"), "w", encoding="utf-8") as fh:
            for i, fruit in enumerate(fruits):
                fh.write(_env(i, fruit) + "\n")
                fh.write(_ep(i, fruit, "6.0", "left",
                             "ok" if i < 1 else "carried") + "\n")
        if report(tmp, "A", "B") == 0:
            failures.append("carried regression read PASS")
    if failures:
        print("196 self-test FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("196 self-test PASS (parse, pairing, carried endpoint, verdict)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="logs/r9/A_direct_ab")
    ap.add_argument("--a", default="A")
    ap.add_argument("--b", default="B")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return report(args.dir, args.a, args.b)


if __name__ == "__main__":
    raise SystemExit(main())
