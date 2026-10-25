"""P39 phase 1 - the left carried-not-placed corpus, per leg, from existing logs.

Read-only. Parses the shipped scripted attempts out of the named logs and prints
one row per attempt plus the aggregates the pre-registration's endpoints are
defined on. Re-derivable:

    python3 logs/p39/left_corpus.py            # table + aggregates
    python3 logs/p39/left_corpus.py --assert   # + the pins the read depends on

The columns are the ones the P39 read quotes:

  arm, species, dia   the attempt header (`[task] target ...`)
  grip gap-dia [mm]   `kinematic grip closed to X cm around a Y cm fruit`
  close F, tick       `dynamic close: sustained contact after N ticks (force=..)`
  lift                `[run] attempt N: ... lift=+0.135 m ...`
  in-hand lift/place  `[motion] carry <leg> ... in-hand |v|max=<v> m/s`
  leg dist/ticks      the same row's leading `<dist> cm, <ticks> ticks`
  clear               the `[motion] carry <leg> clearance:` reference object and
                      its signed distance (the place-leg read is the outcome's
                      physical witness: the payload is on the *main belt* when the
                      jaws open over the output line)

No `[carry]` rows exist in this corpus: `FRUIT_CARRY_DIAG` was never set on the
scripted line, so the loaded-slide *onset* facet (onset row, force@onset,
contacts-at-onset, contact-loss delay) is quoted from the W8-B trace corpus
(`logs/w8/B_RESULTS.md` section 2), not from here.  That is stated in the read.
"""

from __future__ import annotations

import re
import sys

# (label, path, scenario note)
LOGS = [
    ("accept-pear-on", "logs/p32/D1_accept_pear.log", "accept.sh, 10 attempts"),
    ("accept-pear-off", "logs/p32/92_accept_raw_pear_off_current.log", "accept.sh, 10 attempts"),
    ("pear-new", "logs/p32/90_pear_battery_new.log", "species-locked battery"),
    ("pear-old", "logs/p32/91_pear_battery_old.log", "species-locked battery"),
    ("bed-single", "logs/p33/20_single_control.log", "W6-A patch bed battery, 20 (no [motion] rows)"),
]

RE_ATTEMPT = re.compile(r"\[run\] attempt (\d+): picking (\w+) grade (\w+) into output lane (\d+)")
RE_TARGET = re.compile(r"\[task\] target (\w+) \(grade (\w+), ([\d.]+) cm\) with (?:the )?(\w+) arm")
RE_CLOSE = re.compile(
    r"\[task\] dynamic close: sustained contact after (\d+) ticks \(force=([\d.]+) N, span=([\d.]+) mm\)"
)
RE_GRIP = re.compile(
    r"\[task\] kinematic grip closed to ([\d.]+)cm around a ([\d.]+)cm fruit"
)
RE_LEG = re.compile(
    r"\[motion\] carry (\w+): ([\d.]+) cm, (\d+) ticks, .*?in-hand \|v\|max=([\d.]+) m/s, "
    r"recoveries=(\d+)"
)
RE_CLEAR = re.compile(
    r"\[motion\] carry (\w+) clearance: lowest payload point ([-+]?\d+) mm to the (.+)$"
)
RE_RESULT = re.compile(
    r"\[run\] attempt (\d+): grasped=(\w+) placed=(\w+) lift=([-+][\d.]+) m "
    r"force=([\d.]+) N notes=\[(.*?)\]"
)
RE_SERVO = re.compile(r"\[task\] force servo: (\w+): ref=([\d.]+)N F\[([\d.]+),([\d.]+)\]N")
RE_RELEASE = re.compile(r"\[task\] released at \[([^\]]+)\], placed=(\w+)")
RE_STARVE = re.compile(r"\[run\] attempt (\d+): no eligible fruit")

#: `(log, attempt)` slots the selector could not fill at all (a supply class,
#: not a grasp outcome).  Filled by `parse`, read by `--assert`.
starved: list[tuple[str, int]] = []


def parse(path: str):
    rows: list[dict] = []
    cur: dict | None = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if (m := RE_STARVE.search(line)):
                starved.append((path, int(m.group(1))))
                continue
            m = RE_ATTEMPT.search(line)
            if m:
                if cur is not None:
                    rows.append(cur)
                cur = {
                    "attempt": int(m.group(1)),
                    "species": m.group(2),
                    "grade": m.group(3),
                    "lane": int(m.group(4)),
                    "arm": "",
                    "dia_cm": None,
                    "close_ticks": None,
                    "close_force": None,
                    "grip_cm": None,
                    "fruit_cm": None,
                    "legs": {},
                    "clear": {},
                    "grasped": None,
                    "placed": None,
                    "lift": None,
                    "force": None,
                    "notes": "",
                    "servo_fmin": None,
                }
                continue
            if cur is None:
                continue
            if (m := RE_TARGET.search(line)):
                cur["arm"] = m.group(4)
                cur["dia_cm"] = float(m.group(3))
            elif (m := RE_CLOSE.search(line)):
                cur["close_ticks"] = int(m.group(1))
                cur["close_force"] = float(m.group(2))
            elif (m := RE_GRIP.search(line)):
                cur["grip_cm"] = float(m.group(1))
                cur["fruit_cm"] = float(m.group(2))
            elif (m := RE_LEG.search(line)):
                cur["legs"][m.group(1)] = {
                    "dist_cm": float(m.group(2)),
                    "ticks": int(m.group(3)),
                    "in_hand": float(m.group(4)),
                    "recoveries": int(m.group(5)),
                }
            elif (m := RE_CLEAR.search(line)):
                cur["clear"][m.group(1)] = (int(m.group(2)), m.group(3).strip())
            elif (m := RE_RESULT.search(line)):
                cur["grasped"] = m.group(2) == "True"
                cur["placed"] = m.group(3) == "True"
                cur["lift"] = float(m.group(4))
                cur["force"] = float(m.group(5))
                cur["notes"] = m.group(6)
                rows.append(cur)
                cur = None
            elif (m := RE_SERVO.search(line)):
                cur["servo_fmin"] = float(m.group(3))
    return rows


def classify(row: dict) -> str:
    if row["placed"]:
        return "placed"
    if not row["grasped"]:
        return "no-grasp"
    return "cnp"


def main() -> int:
    want_assert = "--assert" in sys.argv
    all_rows: list[tuple[str, dict]] = []
    print("# P39 phase-1 left corpus (generated by logs/p39/left_corpus.py)\n")
    for label, path, note in LOGS:
        rows = parse(path)
        print(f"## {label} - `{path}` ({note}), {len(rows)} attempts\n")
        hdr = (
            "| # | arm | fruit | dia cm | grip-dia mm | close F N | close t | "
            "lift | in-hand lift | in-hand place | place cm/t | clear(place) | outcome |"
        )
        print(hdr)
        print("|" + "---|" * 14)
        for r in rows:
            grip = ""
            if r["grip_cm"] is not None and r["fruit_cm"] is not None:
                grip = f"{(r['grip_cm'] - r['fruit_cm']) * 10:+.2f}"
            lift = r["legs"].get("grasp_lift", {})
            place = r["legs"].get("place0") or r["legs"].get("place1") or {}
            clear = r["clear"].get("place0") or r["clear"].get("place1") or ("", "")
            clr = f"{clear[0]:+d} {clear[1]}" if isinstance(clear[0], int) else ""
            print(
                f"| {r['attempt']} | {r['arm'] or '?'} | {r['species']} {r['grade']} | "
                f"{r['dia_cm'] if r['dia_cm'] is not None else ''} | {grip} | "
                f"{r['close_force'] if r['close_force'] is not None else ''} | "
                f"{r['close_ticks'] if r['close_ticks'] is not None else ''} | "
                f"{r['lift']:+.3f} | {lift.get('in_hand', '')} | {place.get('in_hand', '')} | "
                f"{place.get('dist_cm', '')}/{place.get('ticks', '')} | "
                f"{clr} | {classify(r)} |"
                if r["lift"] is not None
                else "|"
            )
            all_rows.append((label, r))
        print()

    # ---- aggregates -------------------------------------------------------
    print("## Aggregates\n")
    print("| family | arm | attempts | placed | cnp | no-grasp |")
    print("|---|---|---|---|---|---|")
    for label, _path, _note in LOGS:
        rows = [r for lab, r in all_rows if lab == label]
        for arm in ("left", "right"):
            sel = [r for r in rows if r["arm"] == arm]
            if not sel:
                continue
            print(
                f"| {label} | {arm} | {len(sel)} | "
                f"{sum(r['placed'] for r in sel)} | "
                f"{sum(classify(r) == 'cnp' for r in sel)} | "
                f"{sum(classify(r) == 'no-grasp' for r in sel)} |"
            )
    print()

    # the frame-free band split (the metric that needs no diag)
    print("### The frame-free leg band (`in-hand |v|max`, m/s)\n")
    print("| class | leg | n | min | max |")
    print("|---|---|---|---|---|")
    for cls in ("placed", "cnp"):
        for leg in ("grasp_lift", "place0/1"):
            vals = []
            for _lab, r in all_rows:
                if classify(r) != cls:
                    continue
                for name, d in r["legs"].items():
                    if (leg == "grasp_lift" and name == "grasp_lift") or (
                        leg == "place0/1" and name.startswith("place")
                    ):
                        vals.append(d["in_hand"])
            if vals:
                print(f"| {cls} | {leg} | {len(vals)} | {min(vals):.3f} | {max(vals):.3f} |")
    print()

    # the place-leg transfer asymmetry (left vs right, placed only)
    print("### The place-leg transfer, placed attempts only\n")
    print("| arm | n | place cm | place ticks |")
    print("|---|---|---|---|")
    for arm in ("left", "right"):
        ds, ts = [], []
        for _lab, r in all_rows:
            if r["arm"] != arm or not r["placed"]:
                continue
            for name, d in r["legs"].items():
                if name.startswith("place"):
                    ds.append(d["dist_cm"])
                    ts.append(d["ticks"])
        if ds:
            print(f"| {arm} | {len(ds)} | {min(ds):.0f}-{max(ds):.0f} | {min(ts)}-{max(ts)} |")
    print()

    # the closed span minus the diameter (is the close looser on the failures?)
    print("### Closed span minus diameter (mm), the close-geometry check\n")
    for cls in ("placed", "cnp"):
        vals = [
            (r["grip_cm"] - r["fruit_cm"]) * 10
            for _lab, r in all_rows
            if classify(r) == cls and r["grip_cm"] is not None
        ]
        if vals:
            vals.sort()
            med = vals[len(vals) // 2]
            print(
                f"- {cls}: n={len(vals)} median {med:+.2f}, range "
                f"{vals[0]:+.2f} .. {vals[-1]:+.2f}"
            )
    print()

    # the force-servo consequence (F_min on the escaping legs)
    print("### The close force and the post-release servo (`F_min`)\n")
    for cls in ("placed", "cnp"):
        fs = [r["close_force"] for _l, r in all_rows if classify(r) == cls and r["close_force"]]
        fm = [r["servo_fmin"] for _l, r in all_rows if classify(r) == cls and r["servo_fmin"] is not None]
        if fs:
            print(
                f"- {cls}: close force {min(fs):.2f}-{max(fs):.2f} N; "
                f"servo F_min {min(fm):.2f}-{max(fm):.2f} N (n={len(fm)})"
            )
    print()

    if want_assert:
        # The pins the read depends on.  A changed corpus must fail loudly rather
        # than silently re-write the numbers in the markdown.
        left_cnp = sum(classify(r) == "cnp" and r["arm"] == "left" for _l, r in all_rows)
        right_cnp = sum(classify(r) == "cnp" and r["arm"] == "right" for _l, r in all_rows)
        left_all = sum(r["arm"] == "left" for _l, r in all_rows)
        right_all = sum(r["arm"] == "right" for _l, r in all_rows)
        def band(cls, prefix):
            vals = []
            for _l, r in all_rows:
                if classify(r) != cls:
                    continue
                for name, d in r["legs"].items():
                    if name.startswith(prefix):
                        vals.append(d["in_hand"])
            return (min(vals), max(vals)) if vals else (0.0, 0.0)

        grip = {
            cls: sorted(
                (r["grip_cm"] - r["fruit_cm"]) * 10
                for _l, r in all_rows
                if classify(r) == cls and r["grip_cm"] is not None
            )
            for cls in ("placed", "cnp")
        }
        servo = {
            cls: [r["servo_fmin"] for _l, r in all_rows
                  if classify(r) == cls and r["servo_fmin"] is not None]
            for cls in ("placed", "cnp")
        }
        place = {}
        for arm in ("left", "right"):
            ts = []
            for _l, r in all_rows:
                if r["arm"] == arm and r["placed"]:
                    for name, d in r["legs"].items():
                        if name.startswith("place"):
                            ts.append(d["ticks"])
            place[arm] = (min(ts), max(ts)) if ts else (0, 0)
        lift_placed, lift_cnp = band("placed", "grasp_lift"), band("cnp", "grasp_lift")
        place_placed, place_cnp = band("placed", "place"), band("cnp", "place")
        checks = [
            ("zero right-arm carried-not-placed", right_cnp == 0, right_cnp),
            ("the left cnp count", left_cnp == 15, left_cnp),
            ("the corpus's attempts", left_all + right_all == 48, left_all + right_all),
            ("the supply-starvation slots (no eligible fruit)", len(starved) == 2, starved),
            ("in-hand lift bands do not overlap",
             lift_placed[1] < lift_cnp[0], (lift_placed, lift_cnp)),
            ("in-hand place bands do not overlap",
             place_placed[1] < place_cnp[0], (place_placed, place_cnp)),
            ("servo F_min is 0.00 on every cnp leg and > 2 N on every placed leg",
             max(servo["cnp"]) == 0.0 and min(servo["placed"]) > 2.0,
             (min(servo["placed"]), max(servo["cnp"]))),
            ("the left's place legs are longer than the right's",
             place["left"][0] > place["right"][1], place),
            ("the close arithmetic overlaps between classes",
             grip["cnp"][0] < grip["placed"][-1] and grip["placed"][0] < grip["cnp"][-1],
             (grip["placed"][0], grip["placed"][-1], grip["cnp"][0], grip["cnp"][-1])),
        ]
        print("### `--assert`\n")
        bad = 0
        for name, ok, got in checks:
            print(f"- {'PASS' if ok else 'FAIL'} {name} (got {got})")
            bad += 0 if ok else 1
        print(f"\n{'PASS' if bad == 0 else f'{bad} FAILED'}")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
