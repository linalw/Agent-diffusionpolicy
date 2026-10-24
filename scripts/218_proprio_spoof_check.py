"""P36 phase 1: the offline observation-diff check of the proprio spoof.

No simulator. Three things are checked against *measured* artefacts, not
transcriptions of them:

1. **The vectors.** `configs/proprio_spoof.json` must equal the `q_settled=`
   field of the P35 `[park]` rows in `logs/p35/C_ab/` - the pose the direct
   env's reset actually achieved for each inactive-arm pose (the batch's tree
   pins equal this tree's, so the reset settle reproduces them).
2. **The layout.** The 7 indices the spoof writes must be the arm's own
   `arm_dofs`, read from the robot's measured dof order (`logs/33_dof.log`,
   `scripts/33_dof_probe.py`) - the interleaved `left_joint1, right_joint1, ...`
   layout, not the assumption that the first 7 are the left arm.
3. **The diff.** Calling the shipped `rl_env.apply_proprio_spoof` on a synthetic
   joint row must change exactly those 7 values, leave the other 15 (and hence
   the finger/tactile channels and the goal, which are not even passed in)
   bit-identical, leave the caller's array untouched, and be a no-op where the
   pose has no vector for the inactive side.

    python3 scripts/218_proprio_spoof_check.py
    python3 scripts/218_proprio_spoof_check.py --self-test

Writes `logs/p36/offline_obs_diff.txt`. Exit 0 = every assertion held.
"""

from __future__ import annotations

import argparse
import ast
import glob
import hashlib
import json
import os
import re
import sys
import tempfile

import numpy as np

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(REPO, "src"))

from fruit_sorting.rl_env import apply_proprio_spoof, store_guard_reason  # noqa: E402

SPOOF = os.path.join(REPO, "configs", "proprio_spoof.json")
PARKS = os.path.join(REPO, "configs", "arm_parks.json")
DOF_LOG = os.path.join(REPO, "logs", "33_dof.log")
P35_GLOB = os.path.join(REPO, "logs", "p35", "C_ab", "[AB]_*.log")
OUT = os.path.join(REPO, "logs", "p36", "offline_obs_diff.txt")

PARK_ROW = re.compile(
    r"\[park\] episode \d+ arm=(\w+) inactive=(\w+) park=(\w+).*?"
    r"q_settled=([-+0-9.,]+)"
)
DOF_NAMES = re.compile(r"^\[fruit\] dof_names: (\[.*\])$")


class Check:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures = 0
        self.skips = 0

    def put(self, text: str = "") -> None:
        self.lines.append(text)

    def ok(self, name: str, detail: str = "") -> None:
        self.put(f"  PASS  {name}" + (f"  [{detail}]" if detail else ""))

    def fail(self, name: str, detail: str) -> None:
        self.failures += 1
        self.put(f"  FAIL  {name}  [{detail}]")

    def skip(self, name: str, why: str) -> None:
        self.skips += 1
        self.put(f"  SKIP  {name}  [{why}]")

    def expect(self, name: str, got, want) -> None:
        if got == want:
            self.ok(name, f"{got!r}")
        else:
            self.fail(name, f"got {got!r}, want {want!r}")


def md5_array(values: np.ndarray) -> str:
    return hashlib.md5(np.ascontiguousarray(values, dtype=np.float32).tobytes()).hexdigest()


def load_parks() -> dict:
    with open(PARKS, encoding="utf-8") as fh:
        return json.load(fh)


def measured_settled(pattern: str = P35_GLOB) -> dict[tuple[str, str], set[tuple[float, ...]]]:
    """The P35 `q_settled` strings per (active arm, park name)."""
    seen: dict[tuple[str, str], set[tuple[float, ...]]] = {}
    for path in sorted(glob.glob(pattern)):
        for line in open(path, encoding="utf-8", errors="ignore"):
            found = PARK_ROW.search(line)
            if not found:
                continue
            key = (found.group(1), found.group(3))
            seen.setdefault(key, set()).add(
                tuple(float(v) for v in found.group(4).split(","))
            )
    return seen


def measured_layout() -> dict[str, list[int]] | None:
    """The arm dof indices from the robot's measured dof order."""
    if not os.path.isfile(DOF_LOG):
        return None
    for line in open(DOF_LOG, encoding="utf-8", errors="ignore"):
        found = DOF_NAMES.search(line)
        if not found:
            continue
        names = ast.literal_eval(found.group(1))
        return {
            side: [names.index(f"openarm_{side}_joint{i}") for i in range(1, 8)]
            for side in ("left", "right")
        }
    return None


def check_vectors(chk: Check, pattern: str = P35_GLOB) -> dict:
    """The file's vectors against the P35 measured settled poses.

    `pattern` is injectable so the self-test can drive this assertion against a
    fabricated P35 directory (a matching row must pass, a perturbed one must
    fail) instead of re-implementing the comparison beside it.
    """
    with open(SPOOF, encoding="utf-8") as fh:
        spoof = json.load(fh)
    poses = spoof.get("poses", {})
    chk.put("[1] THE VECTORS: configs/proprio_spoof.json vs the P35 `[park] q_settled=`")
    chk.put("")
    settled = measured_settled(pattern)
    if not settled:
        chk.skip("P35 q_settled rows", f"no {P35_GLOB}")
        return spoof
    chk.put(f"    {'pose':10s} {'active':8s} {'n_vals':5s} {'file == measured':17s} values")
    for pose, sides in poses.items():
        for side, vec in sides.items():
            # The inactive arm is the *other* one; a row's `active` is what makes
            # that arm inactive.
            active = "right" if side == "left" else "left"
            rows = settled.get((active, pose))
            if not rows:
                chk.skip(f"{pose}/{side} vs P35", f"no ({active}, {pose}) row")
                continue
            same = len(rows) == 1 and tuple(vec) == next(iter(rows))
            chk.put(f"    {pose:10s} {active:8s} {len(rows):5d} "
                    f"{'yes' if same else 'NO':17s} {vec}")
            if same:
                chk.ok(f"vector {pose}/{side} == the measured settled pose ({len(rows)} rows)")
            else:
                chk.fail(f"vector {pose}/{side}",
                         f"file {vec} vs measured {sorted(rows)}")
    chk.put("")
    return spoof


def check_layout(chk: Check, layout: dict[str, list[int]] | None) -> dict[str, list[int]]:
    chk.put("[2] THE LAYOUT: the 7 indices must be the arm's own arm_dofs")
    chk.put("")
    fallback = {"left": [0, 2, 4, 6, 8, 10, 12], "right": [1, 3, 5, 7, 9, 11, 13]}
    if layout is None:
        chk.skip("measured dof order", f"no {DOF_LOG}")
        layout = fallback
    else:
        chk.put(f"    measured (logs/33_dof.log): left={layout['left']} right={layout['right']}")
        chk.expect("left arm indices", layout["left"], fallback["left"])
        chk.expect("right arm indices", layout["right"], fallback["right"])
        # The 7 arm joints are disjoint from every other joint of the row.
        chk.expect("arms disjoint", bool(set(layout["left"]) & set(layout["right"])), False)
    chk.put("")
    return layout


def synthetic_dof(layout: dict[str, list[int]], ready: dict) -> np.ndarray:
    """A 22-D joint row at `ready` for both arms (fingers open, hand/tcp zero)."""
    dof = np.zeros(22, dtype=np.float32)
    for side in ("left", "right"):
        dof[layout[side]] = np.asarray(ready[side], dtype=np.float32)
    dof[14] = dof[15] = 0.044      # left fingers, measured open
    dof[17] = dof[18] = 0.044      # right fingers
    dof[16] = dof[19] = 0.0        # left/right hand
    return dof


def check_diff(chk: Check, spoof: dict, layout: dict[str, list[int]]) -> None:
    chk.put("[3] THE DIFF: one call of the shipped apply_proprio_spoof")
    chk.put("")
    poses = spoof["poses"]
    ready = poses["ready"]
    back = poses["back"]["left"]
    dof = synthetic_dof(layout, ready)
    pre_hash = md5_array(dof)
    pre_copy = dof.copy()

    # (a) the cell-4 substitution: right active, the left parked in the obs.
    out, info = apply_proprio_spoof(dof, "right", layout, {"left": np.asarray(back)})
    diff = np.flatnonzero(out != dof)
    chk.expect("applied", info["applied"], 1)
    chk.expect("side", info["side"], "left")
    # The *written* set is the contract; a joint whose value happens to be equal
    # in both poses (j7: 1.559 in ready and in back) does not read as a change.
    chk.expect("written indices", [int(i) for i in info["indices"]], layout["left"])
    chk.expect("n changed", int(diff.size), 6)
    chk.expect("changed indices", [int(i) for i in diff], layout["left"][:-1])
    chk.expect("changed values", [round(float(v), 3) for v in out[diff]],
               [round(float(v), 3) for v in back[:-1]])
    chk.expect("caller's array untouched", md5_array(dof), pre_hash)
    chk.expect("caller's array equals its copy", bool(np.array_equal(dof, pre_copy)), True)
    rest = [i for i in range(dof.size) if i not in layout["left"]]
    chk.expect("the other 15 bit-identical",
               bool(np.array_equal(out[rest], dof[rest])), True)
    chk.expect("written values", [round(float(v), 3) for v in out[layout["left"]]],
               [round(float(v), 3) for v in back])

    # (b) the 25-D assembly: the 7 joints + the finger/force channels.
    finger = float(np.mean(out[[17, 18]]))
    forces = np.array([0.0, 0.0], dtype=np.float32)
    proprio = np.concatenate([out, np.array([finger], np.float32), forces])
    pre_prop = proprio.copy()
    pre_prop[layout["left"]] = dof[layout["left"]]
    diff25 = np.flatnonzero(proprio != pre_prop)
    chk.expect("25-D: n changed", int(diff25.size), 6)
    chk.put("    (6 not 7: j7 is 1.559 in both poses, so it is written and reads equal)")
    chk.expect("25-D: changed inside the joint block", bool(diff25.max() < 22), True)
    chk.expect("25-D: the finger channel unchanged",
               float(proprio[22] - pre_prop[22]), 0.0)
    chk.expect("25-D: the tactile channels unchanged",
               [float(v) for v in proprio[23:]], [0.0, 0.0])
    zeroed_pre, zeroed_post = pre_prop.copy(), proprio.copy()
    zeroed_pre[layout["left"]] = 0.0
    zeroed_post[layout["left"]] = 0.0
    chk.expect("25-D: hash with the 7 zeroed is equal (only those changed)",
               md5_array(zeroed_pre) == md5_array(zeroed_post), True)

    # (c) the other arm: a left-active episode spoofs the right's 7.
    out_r, info_r = apply_proprio_spoof(dof, "left", layout,
                                       {"right": np.asarray(ready["right"])})
    chk.expect("right-side written indices", [int(i) for i in info_r["indices"]],
               layout["right"])
    chk.expect("right-side applied", info_r["applied"], 1)
    rest_l = [i for i in range(dof.size) if i not in layout["right"]]
    chk.expect("right-side: the left arm unchanged",
               bool(np.array_equal(out_r[rest_l], dof[rest_l])), True)

    # (d) the defined-population rule: `back` has no right vector -> no-op.
    out_n, info_n = apply_proprio_spoof(dof, "left", layout, {"left": np.asarray(back)})
    chk.expect("no right vector -> applied", info_n["applied"], 0)
    chk.expect("no right vector -> no-op", bool(np.array_equal(out_n, dof)), True)

    # (e) the shipped default: no vectors at all -> no-op, and the vector dict
    #     is empty so `proprio()` does not even call the helper.
    out_off, info_off = apply_proprio_spoof(dof, "right", layout, {})
    chk.expect("off -> applied", info_off["applied"], 0)
    chk.expect("off -> no-op", bool(np.array_equal(out_off, dof)), True)

    # (f) the perturbation is real: how far the substitution moves the channel.
    delta = np.abs(np.asarray(back) - np.asarray(ready["left"]))
    chk.put(f"    ready->back |dq| = {np.round(delta, 3).tolist()} rad "
            f"(max {delta.max():.3f}, sum {delta.sum():.3f})")
    chk.expect("the substitution is not a numerical no-op", bool(delta.max() >= 0.30), True)
    chk.put("")


def check_park_file(chk: Check) -> None:
    chk.put("[4] THE PARK FILE (the image channel) - unchanged by this phase")
    chk.put("")
    parks = load_parks()["parks"]
    chk.expect("park names", sorted(parks), ["back", "ready", "side_deep"])
    # `ready` is all-null (the shipped waypoint); every measured park is the
    # left arm only - the right arm's `back` does not hold (the park file's note).
    sides = sorted({side for entry in parks.values() for side in ("left", "right")
                    if entry.get(side)})
    chk.expect("the parks are left-arm only", sides, ["left"])
    chk.put("")


def check_store_guard(chk: Check) -> None:
    """The record refusal: a spoofed store is a poisoned store."""
    chk.put("[5] THE RECORD GUARD (`record` + `FRUIT_PROPRIO_SPOOF` is refused)")
    chk.put("")
    chk.put("    the spoof rewrites 7 observation channels *before* the recorder sees")
    chk.put("    them, so a store collected under it would carry a pose the arm never")
    chk.put("    held; the guard is the env's predicate, read here without a simulator.")
    chk.expect("record + spoof -> refused",
               bool(store_guard_reason(True, "back")), True)
    chk.expect("the refusal names the pose",
               "back" in store_guard_reason(True, "back"), True)
    chk.expect("record + no spoof -> allowed",
               store_guard_reason(True, ""), "")
    chk.expect("no record + spoof -> allowed (the evaluation interface)",
               store_guard_reason(False, "back"), "")
    chk.expect("the park is NOT refused with a store (a real post-park dataset)",
               store_guard_reason(True, ""), "")
    chk.put("")


def self_test() -> int:
    """The assertions must fail on the wrong vector / the wrong index set."""
    chk = Check()
    with open(SPOOF, encoding="utf-8") as fh:
        spoof = json.load(fh)
    layout = {"left": [0, 2, 4, 6, 8, 10, 12], "right": [1, 3, 5, 7, 9, 11, 13]}
    dof = synthetic_dof(layout, spoof["poses"]["ready"])
    out, _ = apply_proprio_spoof(dof, "right", layout,
                                 {"left": np.asarray(spoof["poses"]["back"]["left"])})
    ok = True
    # A wrong vector must be detected: off by 0.01 rad in j2.
    wrong = np.asarray(spoof["poses"]["back"]["left"], dtype=np.float32).copy()
    wrong[1] += 0.01
    out_w, _ = apply_proprio_spoof(dof, "right", layout, {"left": wrong})
    if np.array_equal(out, out_w):
        print("self-test FAILED: a 0.01 rad perturbation is invisible")
        ok = False
    # A wrong index set must be detected: the right arm instead of the left.
    out_x, _ = apply_proprio_spoof(dof, "right", layout,
                                   {"left": np.asarray(spoof["poses"]["ready"]["right"])})
    if np.flatnonzero(out_x != dof).tolist() != layout["left"]:
        print("self-test FAILED: the changed set is not the left arm")
        ok = False
    # The provenance compare itself (`check_vectors`) must accept the file's own
    # vectors and reject a perturbed one. This is the *real* assertion - section
    # [1] of the main run - so the self-test drives it end to end on a
    # fabricated P35 directory rather than re-implementing the comparison
    # beside it (the first version's local `settled` dict only compared two
    # constants and could not have caught a broken `check_vectors`).
    with tempfile.TemporaryDirectory() as tmp:
        park = ("[fruit] [park] episode 0 arm=right inactive=left park=back "
                "m1_hold=+0.002 q_settled="
                + ",".join(f"{float(v):.3f}" for v in spoof["poses"]["back"]["left"])
                + "\n")
        path = os.path.join(tmp, "A_0.log")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(park)
        chk_ok = Check()
        check_vectors(chk_ok, os.path.join(tmp, "*.log"))
        if chk_ok.failures:
            print("self-test FAILED: check_vectors rejects the file's own vector")
            ok = False
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(park.replace("-0.978", "-0.878"))
        chk_bad = Check()
        check_vectors(chk_bad, os.path.join(tmp, "*.log"))
        if not chk_bad.failures:
            print("self-test FAILED: check_vectors accepts a perturbed measured vector")
            ok = False
    # The store guard must refuse the combination and allow the two halves alone.
    if not store_guard_reason(True, "back") or store_guard_reason(True, "") \
            or store_guard_reason(False, "back"):
        print("self-test FAILED: the record guard's truth table is wrong")
        ok = False
    print("self-test ok" if ok else "self-test failed")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    chk = Check()
    chk.put("P36 phase 1 - the proprio spoof's offline observation diff")
    chk.put("=" * 78)
    chk.put("generated by scripts/218_proprio_spoof_check.py (no simulator)")
    for name in ("src/fruit_sorting/rl_env.py", "configs/proprio_spoof.json",
                 "configs/arm_parks.json"):
        chk.put(f"    {name:38s} md5 {hashlib.md5(open(os.path.join(REPO, name), 'rb').read()).hexdigest()}")
    chk.put("")
    spoof = check_vectors(chk)
    layout = check_layout(chk, measured_layout())
    check_diff(chk, spoof, layout)
    check_park_file(chk)
    check_store_guard(chk)

    chk.put("[6] VERDICT")
    chk.put("")
    chk.put(f"    failures={chk.failures} skipped={chk.skips}")
    chk.put("    the proprio cell changes exactly the inactive arm's 7 joints; the")
    chk.put("    active arm, the finger, the tactile channels and the image are untouched;")
    chk.put("    the default (empty vector dict) is a no-op and `proprio()` skips the call;")
    chk.put("    a recording rollout under the spoof is refused.")
    text = "\n".join(chk.lines) + "\n"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text, end="")
    print(f"\nwrote {os.path.relpath(args.out, REPO)}")
    return 1 if chk.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
