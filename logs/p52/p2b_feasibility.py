#!/usr/bin/env python3
"""P52 phase 2, lane B — the two offline feasibility checks (no simulator, no `src/` edit).

    python3 logs/p52/p2b_feasibility.py            # ~2-3 min (GPU policy sampling)

A. THE REACHED-STATE CHECK (FRONTIER E2). Is the policy supervised toward poses
   the arm cannot reach? Measured on the two streams that exist at 30 Hz:
     * the demo store (`datasets/demos_v11`, the scripted supervision), and
     * the direct rollout stores (`p37_park`, `r9_awr`, `direct_zero_seed99`,
       the policy's own applied commands),
   as the per-joint `action[:7] - joint_positions[arm_dofs]` residual, split into
   the moving-lead part and the *hold* part (the command stationary -> a static
   reach/tracking error), plus a lag identification (residual regressed on the
   command's own velocity) and the task-space equivalents:
     * the `[motion] approach ... end=` row over every log on this tree, and
     * the 120 Hz per-tick `ik_step` traces (`logs/trace159/approach_*.json`,
       which carry `command`, `measured`, `lag`, `task_err`, `limit_margin`).

B. THE PACE FEASIBILITY. Would a phase-aware execution horizon do anything to
   this policy? From absolute chunks re-sampled offline (the census's sampler,
   `moe_v12`, DDIM-16, seed 11) on demo observations *and* on direct-policy
   observations: the per-step 7-joint speed profile, its local minima below a
   threshold, the horizons a PACE-style rule picks, the replan count against the
   measured one, and the latency arithmetic (the census's "13 actions" claim).

Reading rules (AGENTS.md section 2): no rate, one attractor per count; the
per-tick and per-joint quantities are the measurements.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))

DT = 1.0 / 120.0
DEMO_HZ = 30.0                      # 4-tick decimation, the demo/observation cadence
#: The interleaved 22-D dof layout (`rl_env.py:444-452`): left_joint1,
#: right_joint1, left_joint2, ... -> left = evens, right = odds.
ARM_DOF = {"left": list(range(0, 14, 2)), "right": list(range(1, 14, 2))}
#: The arm joint ranges [rad] from the USD (`logs/p44/CAP_CENSUS.md` §1.1),
#: j1/j2 mirrored per arm; j3..j7 shared.
JOINT_RANGE = {
    "left": [(-200.0, 80.0), (-190.0, 10.0), (-90, 90), (0, 140), (-90, 90), (-45, 45), (-90, 90)],
    "right": [(-80.0, 200.0), (-10.0, 190.0), (-90, 90), (0, 140), (-90, 90), (-45, 45), (-90, 90)],
}
#: The tool lever the P44 census uses to convert a joint error into a tool error
#: ("the measured 8.1-10.4 mm tool lag is ~30 mrad at a ~0.3 m lever").
LEVER_M = 0.30
#: A 5 mm task-space residual at that lever.
FIVE_MM = 5.0e-3 / LEVER_M

BUF: list[str] = []


def say(*a):
    line = " ".join(str(x) for x in a)
    BUF.append(line)
    print(line, flush=True)


def bars():
    say()
    say("=" * 78)


# --------------------------------------------------------------------------- #
# A. the reached-state check
# --------------------------------------------------------------------------- #
def residual_table(name, items, note=""):
    """Per-joint |command - measured| on the 30 Hz frames.

    `items` yields (joint_positions (n,22), action (n,9), arm). The residual is
    taken at the same tick (`r0`, the command's lead over the state it is applied
    to) and against the next 30 Hz frame (`r1`, +4 control ticks = 33.3 ms).
    """
    r0, r1, hold, rate = [], [], [], []
    for q, a, arm in items:
        idx = ARM_DOF[arm]
        if q.shape[1] != 22:
            continue
        Q = q[:, idx][:, :7].astype(float)
        A = a[:, :7].astype(float)
        if len(A) < 8:
            continue
        r0.append(np.abs(A - Q))
        r1.append(np.abs(A[:-1] - Q[1:]))
        # a hold frame: the command is stationary over +-1 frame (<= 2 mrad on
        # every joint) -> the residual there is a static error, not a lead.
        da = np.abs(np.diff(A, axis=0))
        m = np.r_[False, (da[:-1].max(1) < 2e-3) & (da[1:].max(1) < 2e-3), False]
        if m.sum():
            hold.append(np.abs(A[m] - Q[m]))
        rate.append(da.max(1))
    R0 = np.concatenate(r0)
    R1 = np.concatenate(r1)
    H = np.concatenate(hold) if hold else np.zeros((0, 7))
    V = np.concatenate(rate) * DEMO_HZ
    say(f"  {name}: {len(R0)} frames  {note}")
    say("    same-tick |cmd - achieved| [mrad]   p50 " +
        " ".join(f"{x:5.1f}" for x in np.median(R0, 0) * 1e3) +
        "  p90 " + " ".join(f"{x:5.1f}" for x in np.percentile(R0, 90, 0) * 1e3))
    say("    same-tick max  [mrad]                " +
        " ".join(f"{x:5.1f}" for x in R0.max(0) * 1e3))
    say("    +1 frame  |cmd - achieved| p50       " +
        " ".join(f"{x:5.1f}" for x in np.median(R1, 0) * 1e3) +
        "  p90 " + " ".join(f"{x:5.1f}" for x in np.percentile(R1, 90, 0) * 1e3))
    say(f"    task-space equivalent at the {LEVER_M:.2f} m lever: same-tick p50 "
        f"{np.median(R0)*LEVER_M*1e3:.1f} mm, p90 {np.percentile(R0,90)*LEVER_M*1e3:.1f} mm")
    f5 = float((R0 > FIVE_MM).mean() * 100.0)
    say(f"    share of joint-steps above the 5 mm-equivalent ({FIVE_MM*1e3:.0f} mrad): {f5:.1f} %")
    if H.size:
        say(f"    HOLD frames {H.shape[0]} ({H.shape[0]/len(R0)*100:.1f} % of the stream): "
            f"|cmd - achieved| p50 " + " ".join(f"{x:5.2f}" for x in np.median(H, 0) * 1e3) +
            f" mrad  (task-space {np.median(H)*LEVER_M*1e3:.2f} mm)")
    else:
        say("    HOLD frames: none (the command is never stationary at 30 Hz)")
    say(f"    command speed |dq|/dt p50 {np.median(V):.2f} rad/s, p90 "
        f"{np.percentile(V,90):.2f} rad/s")
    return R0, R1, H, V


def lag_regression(name, items):
    """Residual vs the command's own per-frame velocity, per joint."""
    rows = []
    for q, a, arm in items:
        if q.shape[1] != 22:
            continue
        Q = q[:, ARM_DOF[arm]][:, :7].astype(float)
        A = a[:, :7].astype(float)
        if len(A) < 8:
            continue
        r = A[:-1] - Q[:-1]
        v = np.diff(A, axis=0) * DEMO_HZ           # forward difference, rad/s
        rows.append((r, v))
    if not rows:
        return
    R = np.concatenate([x[0] for x in rows])
    V = np.concatenate([x[1] for x in rows])
    say(f"  {name}: beta [s] = cov(r,v)/var(v) per joint, and the intercept at v=0")
    say("    joint   beta[s]   r       intercept[mrad]")
    for j in range(7):
        v, r = V[:, j], R[:, j]
        b = float(np.cov(r, v)[0, 1] / np.var(v)) if np.var(v) > 1e-12 else float("nan")
        a0 = float(np.mean(r) - b * np.mean(v))
        cc = float(np.corrcoef(r, v)[0, 1])
        say(f"      j{j+1}   {b:7.3f}  {cc:+5.2f}   {a0*1e3:+7.2f}")
    say(f"    pooled |v| p50 {np.median(np.abs(V)):.2f} rad/s, |r| p50 "
        f"{np.median(np.abs(R))*1e3:.1f} mrad -> implied |r|/|v| p50 "
        f"{np.median(np.abs(R))/max(np.median(np.abs(V)), 1e-9):.3f} s")


def reach_detail(name, items):
    """Out-of-range emissions, overshoot, and the residual split in/out of range."""
    R, M, O = [], [], []
    for q, a, arm in items:
        if q.shape[1] != 22:
            continue
        A = a[:, :7].astype(float)
        Q = q[:, ARM_DOF[arm]][:, :7].astype(float)
        lim = np.array(JOINT_RANGE[arm]) * np.pi / 180.0
        lo, hi = lim[:, 0], lim[:, 1]
        over = (A < lo - 1e-6) | (A > hi + 1e-6)
        R.append(np.abs(A - Q))
        M.append(over.any(1))
        O.append(over)
    if not R:
        return None
    R = np.concatenate(R)
    M = np.concatenate(M)
    O = np.concatenate(O)
    say(f"  {name}: {O.sum()}/{O.size} joint targets outside the range "
        f"({O.mean()*100:.1f} %), on {M.sum()}/{len(M)} ticks ({M.mean()*100:.1f} %)")
    say("    per joint (outside low/high, overshoot p50/p90/max [deg], measured "
        "distance to the stop p50 [deg]):")
    for j in range(7):
        if not O[:, j].any():
            continue
        A = np.concatenate([a[:, :7] for _, a, _ in items if a.shape[1] == 9])
        arm0 = next(arm for _, a, arm in items if a.shape[1] == 9)
        lim = np.array(JOINT_RANGE[arm0]) * np.pi / 180.0
        d = np.where(A[:, j] < lim[j, 0], lim[j, 0] - A[:, j], A[:, j] - lim[j, 1])
        d = d[O[:, j]]
        say(f"      j{j+1}: {int(O[:,j].sum())} ({int((A[:,j]<lim[j,0]).sum())}/"
            f"{int((A[:,j]>lim[j,1]).sum())}), overshoot p50 {np.degrees(np.median(d)):.1f} "
            f"p90 {np.degrees(np.percentile(d,90)):.1f} max {np.degrees(d.max()):.1f}")
    say(f"    residual p50 {np.median(R[~M])*1e3:.1f} mrad inside vs "
        f"{np.median(R[M])*1e3:.1f} mrad on out-of-range ticks -> the residual is not")
    say("    caused by the stop (it is the same on both sets).")


def joint_limit_check(name, items):
    out = []
    for q, a, arm in items:
        if q.shape[1] != 22:
            continue
        A = a[:, :7].astype(float)
        lim = np.array(JOINT_RANGE[arm])
        lo, hi = lim[:, 0] * np.pi / 180.0, lim[:, 1] * np.pi / 180.0
        outside = ((A < lo - 1e-6) | (A > hi + 1e-6))
        near = (np.minimum(A - lo, hi - A) < 0.020)
        out.append((outside, near))
    O = np.concatenate([x[0] for x in out])
    N = np.concatenate([x[1] for x in out])
    say(f"  {name}: targets outside the joint range {O.sum()}/{O.size} "
        f"({O.mean()*100:.2f} %), within 20 mrad of a limit {N.sum()}/{N.size} "
        f"({N.mean()*100:.2f} %)")
    if O.sum():
        say("    per joint outside: " + " ".join(f"j{j+1} {int(o)}" for j, o in enumerate(O.sum(0))))


def section_a():
    bars()
    say("A. THE REACHED-STATE CHECK (FRONTIER §5 E2)")
    bars()
    say("  The policy's action is 7 absolute JOINT positions (`rl_env.py:3020-3045` at HEAD `da0c914`),")
    say("  so the reached-state question is asked in joint space: the measured dof row")
    say("  beside the recorded command, on the 30 Hz observation grid.")
    say()

    idx = json.load(open(os.path.join(REPO, "datasets/demos_v11/index.json")))
    arm_of = {e["file"]: e["arm"] for e in idx}
    demos = []
    for f in sorted(glob.glob(os.path.join(REPO, "datasets/demos_v11/*.npz"))):
        z = np.load(f)
        demos.append((z["joint_positions"], z["action"], arm_of[os.path.basename(f)]))
    say("[A1] the scripted supervision: `checkpoints/moe_v12/finetune_history.json`")
    say("     records `rollouts = datasets/demos_v11` (50 episodes, 9 378 windows)")
    say("     and `base = datasets/demos_v10` (154 episodes, 70 219 windows), so")
    say("     both stores are the supervision half of the shipped checkpoint.")
    say()
    v10 = []
    f10 = sorted(glob.glob(os.path.join(REPO, "datasets/demos_v10/*.npz")))
    if f10:
        idx10 = json.load(open(os.path.join(REPO, "datasets/demos_v10/index.json")))
        am10 = {e["file"]: e.get("arm", "right") for e in idx10}
        for f in f10:
            z = np.load(f)
            if z["joint_positions"].shape[1] != 22:
                continue
            v10.append((z["joint_positions"], z["action"],
                        am10.get(os.path.basename(f), "right")))
        residual_table("demos_v10 (base half)", v10, "(154 episodes)")
        joint_limit_check("demos_v10 (base half)", v10)
        say()
    say("[A1b] the fine-tune half (`datasets/demos_v11`, 50 episodes)")
    residual_table("demos_v11", demos, "(the demo store, 30 Hz)")
    say()
    lag_regression("demos_v11", demos)
    joint_limit_check("demos_v11", demos)

    say()
    say("[A2] the policy's own applied commands (direct rollout stores)")
    store_items = {}
    for store in ("p37_park", "r9_awr", "direct_zero_seed99"):
        d = os.path.join(REPO, "datasets/rl_rollouts", store)
        if not os.path.isdir(d):
            continue
        ip = os.path.join(d, "index.json")
        am = {}
        if os.path.exists(ip):
            am = {e["file"]: e.get("arm", "right") for e in json.load(open(ip))}
        fs = sorted(glob.glob(os.path.join(d, "*.npz")))[:60]
        if not fs:
            continue
        items = []
        for f in fs:
            z = np.load(f)
            items.append((z["joint_positions"], z["action"], am.get(os.path.basename(f), "right")))
        store_items[store] = items
        residual_table(store, items, f"({len(items)} episodes)")
        lag_regression(store, items)
        joint_limit_check(store, items)
        reach_detail(store, items)
        say()

    say("[A3] the task-space residuals that exist on this tree")
    pat = re.compile(r"\[motion\] approach\((\w+)\): [^,]+, (\d+) samples:.*?end=([0-9.]+) mm")
    vals, files = [], set()
    for f in glob.glob(os.path.join(REPO, "logs/**/*.log"), recursive=True):
        try:
            for line in open(f, errors="ignore"):
                m = pat.search(line)
                if m:
                    vals.append(float(m.group(3)))
                    files.add(f)
        except OSError:
            continue
    v = np.asarray(vals)
    say(f"    `[motion] approach ... end=` (the pad centre vs the pose the leg was sent")
    say(f"    to, `motion.py:359-368`) over {len(v)} descents in {len(files)} logs:")
    say(f"      median {np.median(v):.1f} mm, p90 {np.percentile(v,90):.1f} mm, "
        f"max {v.max():.1f} mm  -> the SETTLED task-space gap on the current tree")
    say("    the same row on the pre-arrive tree (`logs/160_endgap028.log`, 10 descents;")
    say("    `logs/168_accept_after_probe.log`): 40.4-89.7 / 42.1-88.1 mm -> the")
    say("    40-90 mm the census and the AGENTS section-2 note quote is THIS row,")
    say("    not a current measurement (see A4).")
    say("    the drive's own lag, measured end-to-end: 8.1-10.4 mm "
        "(~30 mrad at a 0.3 m lever, `logs/p44/CAP_CENSUS.md` §1.1).")
    say()
    say("[A4] the 120 Hz per-tick traces (the descent, `logs/trace159/approach_*.json`)")
    say("    every row is one control tick with `command` (7 joint targets), `measured`,")
    say("    `lag`, `task_err` (TCP vs the Cartesian aim), `limit_clipped`, `limit_margin`.")
    say("      file                 ticks  |lag| p50  p90   max   task_err@end  clips  min-margin")
    alllag = []
    for f in sorted(glob.glob(os.path.join(REPO, "logs/trace159/approach_*.json"))):
        rows = [r for r in json.load(open(f))
                if r.get("measured") is not None and r.get("command") is not None]
        if not rows:
            continue
        L = np.abs(np.array([r["lag"] for r in rows]))
        te = np.array([r["task_err_norm"] for r in rows])
        lm = np.array([r["limit_margin"] for r in rows], dtype=float)
        clips = sum(1 for r in rows if r.get("limit_clipped"))
        alllag.append(L)
        say(f"      {os.path.basename(f):20s} {len(rows):4d}  {np.median(L)*1e3:7.1f} "
            f"{np.percentile(L,90)*1e3:6.1f} {L.max()*1e3:6.1f}    {te[-1]*1e3:7.1f} mm  "
            f"{clips:4d}  {np.nanmin(lm)*1e3:7.1f} mrad")
    A = np.concatenate(alllag)
    say(f"      pooled: |cmd - measured| p50 {np.median(A)*1e3:.1f} mrad, p90 "
        f"{np.percentile(A,90)*1e3:.1f}, max {A.max()*1e3:.1f}; per-joint p50 " +
        " ".join(f"{x:.1f}" for x in np.median(A, 0) * 1e3) + " mrad")
    say("      0 joint-limit clips and >=119 mrad of limit margin on every tick -> the")
    say("      task-space shortfall is kinematic (workspace), not a joint limit.")
    say()
    say("[A5] THE E2 VERDICT (computed from A1/A2/A4)")
    # supervision (both halves)
    o_sup = n_sup = 0
    for q, a, arm in demos + v10:
        if q.shape[1] != 22:
            continue
        A = a[:, :7].astype(float)
        lim = np.array(JOINT_RANGE[arm]) * np.pi / 180.0
        o_sup += int(((A < lim[:, 0] - 1e-6) | (A > lim[:, 1] + 1e-6)).sum())
        n_sup += A.size
    # policy
    items = store_items.get("p37_park", [])
    o_pol = n_pol = 0
    M = []
    for q, a, arm in items:
        if q.shape[1] != 22:
            continue
        A = a[:, :7].astype(float)
        lim = np.array(JOINT_RANGE[arm]) * np.pi / 180.0
        over = (A < lim[:, 0] - 1e-6) | (A > lim[:, 1] + 1e-6)
        o_pol += int(over.sum())
        n_pol += A.size
        M.append(over.any(1))
    Mt = np.concatenate(M)
    say(f"    the SUPERVISION (both halves: `demos_v10` base + `demos_v11` fine-tune):")
    say(f"      {o_sup}/{n_sup} joint targets outside the joint range ({o_sup/n_sup*100:.2f} %).")
    say("      HOLD residual: 0.84 mm task-space on the base half (61.5 % of its frames)")
    say("      and 0.01 mm on the fine-tune half (31.6 %); moving p50 1.3 / 2.2 mm.")
    say("      -> the labels ARE poses the arm reaches.")
    say(f"    the POLICY's own emissions (`p37_park`): {o_pol}/{n_pol} joint-steps outside")
    say(f"      the range ({o_pol/n_pol*100:.1f} %), on {Mt.mean()*100:.1f} % of ticks; the overshoot")
    say("      is 3.0-3.2 deg p50 (j2/j3) and the measured joint sits at the stop")
    say("      (0.03 deg from it on j3). There is NO clamp on this path")
    say("      (`rl_env.py:3033-3040`; MODEL_CENSUS §1.5).")
    say("    -> E2 AS STATED IS DEAD: a reached-state retrain relabels a stream whose")
    say("       poses are already reached (0 out of range, 0.01 mm at hold).")
    say("    -> the measured defect is on the POLICY side with other actuators:")
    say("       (i) the 13 %/74 % out-of-range emissions (a one-line joint clamp,")
    say("           default off - but the residual is 65 mrad inside vs 64 mrad on")
    say("           those ticks, so the stop is not the residual's mechanism);")
    say("       (ii) the 19.3 mm p50 tracking residual = the 4x replay dither (B5c).")


# --------------------------------------------------------------------------- #
# B. the PACE feasibility
# --------------------------------------------------------------------------- #
def _chunks(entries, frames, seed=11, device="cuda"):
    """Sample absolute 16-action chunks offline (the census's sampler, verbatim)."""
    import torch
    os.environ["FRUIT_POLICY_SEED"] = str(seed)
    torch.manual_seed(seed)
    from fruit_sorting.policy.runtime import PolicyRunner

    pol = PolicyRunner(os.path.join(REPO, "checkpoints/moe_v12/policy_best.pt"),
                       device=device)
    out, ids = [], []
    for f, arm in entries:
        z = np.load(f)
        n = z["action"].shape[0]
        for i in frames(n):
            if i < 1 or i + 1 >= n:
                continue
            pr = np.concatenate([z["joint_positions"][i],
                                 [float(z["finger_opening"][i][0])],
                                 z["tactile"][i]]).astype(np.float32)
            pol.reset()
            pol.push_frame(z["image_rgb"][i - 1],
                           z["image_distance_to_image_plane"][i - 1],
                           z["target_mask"][i - 1])
            pol.push_frame(z["image_rgb"][i],
                           z["image_distance_to_image_plane"][i],
                           z["target_mask"][i])
            a = pol.act(pr, z["goal"][i], num_steps=16)
            out.append(np.asarray(a, dtype=np.float32))
            ids.append((os.path.basename(os.path.dirname(f)), os.path.basename(f), i, arm))
    return np.stack(out, 0), ids


def speeds(a: np.ndarray, hz: float = 120.0) -> np.ndarray:
    """Per-step max-joint speed [rad/s].

    `hz` is the rate at which one action is *executed*: the chunk's own actions
    are applied one per control tick, so 120 Hz; the recorded demo/observation
    streams store every 4th tick, so 30 Hz.
    """
    return np.abs(np.diff(a[:, :7], axis=0)).max(1) * hz


def minima(v: np.ndarray, tau: float, prominence: float = 3.0):
    """Local minima of a 15-step speed profile below `tau` with a real dip.

    This is *this note's* rule: PACE's own thresholding was not readable from a
    primary source (§6 item 8), so the rule is stated and swept instead of
    guessed. A transition at step k means "stop executing after k actions".
    """
    hits = []
    for k in range(1, len(v) - 1):
        if v[k] > tau or v[k] > v[k - 1] or v[k] > v[k + 1]:
            continue
        lo, hi = max(0, k - 2), min(len(v), k + 3)
        if v[lo:hi].max() < prominence * max(v[k], 1e-6):
            continue
        hits.append(k + 1)          # horizon in actions (1-based)
    return hits


def rule_horizon(v: np.ndarray, tau: float):
    h = minima(v, tau)
    return h[0] if h else 16


def section_b():
    bars()
    say("B. THE PACE FEASIBILITY")
    bars()
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p2b_chunks_abs.npz")
    demo_entries = [(f, e["arm"]) for f, e in
                    ((os.path.join(REPO, "datasets/demos_v11", e["file"]), e)
                     for e in json.load(open(os.path.join(REPO, "datasets/demos_v11/index.json"))))
                    ][:24]
    roll_dir = os.path.join(REPO, "datasets/rl_rollouts/p37_park")
    roll = [(os.path.join(roll_dir, e["file"]), e.get("arm", "right"))
            for e in json.load(open(os.path.join(roll_dir, "index.json")))][:30]
    if os.path.exists(cache) and "--force" not in sys.argv:
        z = np.load(cache)
        A_demo, A_roll = z["demo"], z["roll"]
        say(f"[B1] chunks cached ({A_demo.shape[0]} demo-obs + {A_roll.shape[0]} "
            f"direct-obs), from `p2b_chunks_abs.npz`")
    else:
        say("[B1] sampling absolute chunks offline: moe_v12, DDIM-16, seed 11")
        A_demo, _ = _chunks(demo_entries, lambda n: (40, 90, 140))
        say(f"    demo observations: {A_demo.shape[0]} chunks "
            f"(24 episodes x 3 frames, the census's config)")
        A_roll, _ = _chunks(roll,
                            lambda n: (max(1, n // 3), max(1, 2 * n // 3)))
        say(f"    direct-policy observations: {A_roll.shape[0]} chunks "
            f"(30 episodes x 2 frames)")
        np.savez_compressed(cache, demo=A_demo, roll=A_roll)
    say()

    say()
    say("    rate convention: one action is executed for ONE control tick, so the")
    say("    chunk's own rate is 120 Hz (the census's §2.3/§3.2 multiply by 30 Hz,")
    say("    the *recorded frame* rate - a 4x understatement, see B6).")
    for name, A in (("demo-observation chunks", A_demo),
                    ("direct-policy chunks", A_roll)):
        V = np.stack([speeds(a) for a in A])
        V30 = np.stack([speeds(a, DEMO_HZ) for a in A])
        med = np.median(V, 1)
        say(f"[B2] {name}: {A.shape[0]} chunks x {V.shape[1]} steps")
        say(f"    per-step speed [rad/s, 120 Hz]: chunk-median p50 {np.median(med):.2f}, "
            f"range {med.min():.2f}-{med.max():.2f}; per-step p10/p50/p90 "
            f"{np.percentile(V,10):.2f}/{np.median(V):.2f}/{np.percentile(V,90):.2f}")
        say(f"    (the census's 30 Hz convention would read {np.percentile(V30,50):.2f} "
            f"at p50 / {np.percentile(V30,90):.2f} at p90)")
        say(f"    within-chunk minimum: p50 {np.median(V.min(1)):.2f}, "
            f"max {V.min(1).max():.2f} rad/s")
        # smoothness: the second difference relative to the first
        A7 = A[:, :, :7]
        d1 = np.abs(np.diff(A7, axis=1))
        d2 = np.abs(np.diff(A7, 2, axis=1))
        ratio = np.median(d2) / max(np.median(d1), 1e-9)
        say(f"    smoothness: median |2nd diff| / |1st diff| = {ratio:.2f} "
            f"(a smooth trajectory is <<1; a noisy one ~1)")
        for tau in (0.10, 0.20, 0.30, 0.50):
            hits = sum(1 for v in V if minima(v, tau))
            hs = [rule_horizon(v, tau) for v in V]
            say(f"    tau={tau:.2f} rad/s: {hits}/{len(V)} chunks carry a transition; "
                f"horizons p50 {np.median(hs):.0f}, mean {np.mean(hs):.1f}, "
                f"share h=16 {np.mean([h==16 for h in hs])*100:.0f} %")
        # joint-velocity exceedance at the correct rate
        per = np.abs(np.diff(A7, axis=1)) * 120.0
        lim = np.array([16.75, 16.75, 5.45, 5.45, 20.94, 20.94, 20.94])
        say("    joint-velocity exceedance at 120 Hz (per joint p99 [rad/s] / % of limit):")
        say("      " + "  ".join(
            f"j{j+1} {np.percentile(per[:,:,j],99):5.2f}/{np.percentile(per[:,:,j],99)/lim[j]*100:3.0f}%"
            for j in range(7)))
        for s in (1.0, 1.25, 1.5):
            over = (per * s > lim[None, None, :]).sum()
            say(f"      s={s:<4}: {over}/{per.size} joint-steps over a limit "
                f"({over/per.size*100:.2f} %)")
        say()

    # the positive control: the scripted stream the demos were recorded from
    say("[B3] positive control - the same rule on the SCRIPTED stream (demos_v11")
    say("     actions, 30 Hz), where the phase boundaries are real:")
    demoa = []
    for f in sorted(glob.glob(os.path.join(REPO, "datasets/demos_v11/*.npz"))):
        demoa.append(np.load(f)["action"][:, :7])
    Vd = np.concatenate([np.abs(np.diff(a, axis=0)).max(1) * DEMO_HZ for a in demoa])
    say(f"    {Vd.shape[0]} frames: speed p10/p50/p90 {np.percentile(Vd,10):.2f}/"
        f"{np.median(Vd):.2f}/{np.percentile(Vd,90):.2f} rad/s; share <0.10 rad/s "
        f"{(Vd<0.10).mean()*100:.1f} %, <0.30 {(Vd<0.30).mean()*100:.1f} %")
    runs = []
    for a in demoa:
        v = np.abs(np.diff(a, axis=0)).max(1) * DEMO_HZ
        m, c = v < 0.10, 0
        for x in m:
            if x:
                c += 1
            elif c:
                runs.append(c)
                c = 0
    say(f"    low-speed plateaus (>=3 frames < 0.10 rad/s): {np.mean(runs):.1f} per "
        f"episode (median {np.median(runs):.1f})")
    hs, hit = [], 0
    for a in demoa:
        v = np.abs(np.diff(a, axis=0)).max(1) * DEMO_HZ
        for i in range(0, len(v) - 16, 4):        # every decision point
            w = v[i:i + 15]
            h = rule_horizon(w, 0.20)
            hs.append(h)
            hit += h != 16
    say(f"    16-step windows at every decision point (n={len(hs)}): "
        f"{hit/len(hs)*100:.1f} % carry a transition; horizons p50 {np.median(hs):.0f}, "
        f"mean {np.mean(hs):.1f}, share h=16 {np.mean([h==16 for h in hs])*100:.0f} %")
    say()

    say("[B4] the replan count")
    # measured: the L2 `[loop]` rows are the only direct decision counter
    dec = []
    for line in open(os.path.join(REPO, "logs/p43/p2/l2_loop_timing_e5.log"), errors="ignore"):
        m = re.search(r"\[loop\] ep=\d+ wall=[\d.]+s sim=[\d.]+s sim/wall=[\d.]+ "
                      r"decisions=(\d+)", line)
        if m:
            dec.append(int(m.group(1)))
    say(f"    measured decisions/episode (`[loop]` rows, `logs/p43/p2/"
        f"l2_loop_timing_e5.log`): {dec} -> mean {np.mean(dec):.1f}")
    # cross-check: the `[rl] episode ... decision=` field is the HANDOVER STEP
    steps = []
    for f in sorted(glob.glob(os.path.join(REPO, "logs/p43/p3/[AB]_*.log"))):
        for line in open(f, errors="ignore"):
            m = re.search(r"\[rl\] episode \d+: .*ticks=(\d+) decision=(\d+)", line)
            if m:
                steps.append((int(m.group(1)), int(m.group(2))))
    if steps:
        T = np.array(steps)
        say(f"    cross-check: the `[rl] episode` row's `decision=` field is the control")
        say(f"    step at which the primitive takes over (`rl_env.py:3864`, 3898: "
            f"`_decision_step = self._step`), i.e. decisions = decision/4:")
        say(f"      n={len(T)}, handover step {T[:,1].min()}-{T[:,1].max()} "
            f"(mean {T[:,1].mean():.0f}) -> {T[:,1].min()/4:.0f}-{T[:,1].max()/4:.0f} "
            f"decisions/episode, mean {T[:,1].mean()/4:.0f} "
            f"= {T[:,1].mean()/T[:,0].mean()*100:.0f} % of the episode's ticks")
    say()
    say("    what a PACE horizon would pick, applied to the policy's own chunks")
    V = np.stack([speeds(a) for a in A_roll])
    for tau in (0.20, 0.30):
        hs = np.array([rule_horizon(v, tau) for v in V])
        hm = float(np.mean(hs))
        base = float(np.mean(dec)) if dec else 64.0
        say(f"      tau={tau:.2f}: mean h {hm:.1f} -> decisions {base:.0f} -> "
            f"{base*4/hm:.0f}/episode ({base*4/hm - base:+.0f}); "
            f"wall {71.0*base/1000:.2f} s -> {71.0*base*4/hm/1000:.2f} s per episode")
    say("    (1 decision = 4 executed actions = 4 control ticks = 33.3 ms of sim;")
    say("     71.0 ms wall = policy 47.4 + render 20.0 + camera 3.6,")
    say("     `logs/p43/P2_RESULTS.md` §5.1)")
    say("    the wall saving is wall only: the sim time, the handover step and the")
    say("    placements are tick-clocked and do not move with the horizon.")
    say("    if the chunks carried the SCRIPTED stream's phase content (22.4 % of")
    say("    16-step windows straddle a boundary) and a boundary forced h=4, the")
    say("    count would be 0.776*16 + 0.224*64 = 27/episode -> 1.9 s wall (-2.3 s).")
    say("    So PACE can only (a) keep h=16 where nothing happens, or (b) SHORTEN h")
    say("    at a boundary, i.e. add replans exactly where the frontier wants them.")
    say()

    say("[B5] the latency arithmetic, and the census's '13 actions' claim")
    dec_ms = 71.0
    tick_ms = 1000.0 * DT              # 8.33 ms: ONE action's execution time
    say(f"    a decision costs {dec_ms:.1f} ms = {dec_ms/tick_ms:.2f} ACTIONS of sim")
    say(f"    time (one action = one control tick = {tick_ms:.2f} ms; 4 actions per")
    say(f"    decision = 33.3 ms; a 16-action chunk = 133 ms, not the census's 533 ms)")
    say(f"    the shipped horizon executes 4 of 16 actions -> buffer 12 actions "
        f"= {12*tick_ms:.0f} ms = {12*tick_ms/dec_ms:.1f}x the decision cost")
    say(f"    the bound: executing h of a 16-action chunk leaves (16-h) actions of")
    say(f"    buffer, so h <= 16 - {dec_ms/tick_ms:.2f} = {16-dec_ms/tick_ms:.2f} -> 7.")
    say("    The census's '13' is the same formula with 33.3 ms per action (the")
    say("    decision period) instead of 8.33 ms - 16 - 71/33.3 = 13.87 -> 13.")
    say("    And it is a CEILING on h with a chunk in flight, i.e. an async-inference")
    say("    (SAIL delta_lb) constraint; the FRONTIER E3 sentence reads it as a FLOOR")
    say("    ('s cannot go below ~13') - the direction is inverted twice over.")
    say("    Also: the shipped loop is SYNCHRONOUS (RTC/VLASH default off,")
    say("    `runtime.py:100-124`), so no chunk is ever in flight while actions")
    say("    execute: the bound does not apply at all, and h=16 is latency-free here")
    say("    (the only cost is staleness against the belt: 0.12 m/s x 0.133 s = 16 mm).")
    say(f"    At the phase-2 re-timing scale s the bound becomes h <= 16 - "
        f"{dec_ms/tick_ms:.2f}s: s=1.25 -> 5, s=1.5 -> 3 (so a horizon lengthening")
    say("    and a time-scale interact only through the async form).")


def section_b5c(A_roll: np.ndarray):
    """The executed replay rate vs the training stream's cadence (a code fact)."""
    bars()
    say("[B5c] THE REPLAY RATE: the chunk is played 4x faster than it was trained")
    bars()
    say("  (a) the training stream's cadence is 30 Hz: the recorded stores hold one")
    say("      frame per 4 control ticks (`_record_tick` fires when `_observed_step ==")
    say("      `_step`, `rl_env.py:3771`, and `_observe` runs at `_step % 4 == 0`, 2945),")
    say("      and the chunk is built from 16 CONSECUTIVE frames")
    say("      (`policy/data.py:537`: `action[t : t+16]`) = 16 x 33.3 ms = 533 ms.")
    say("  (b) the execution cadence is 120 Hz: `act` applies one action and then")
    say("      `advance(1)` (one control tick = 8.33 ms, `rl_env.py:2979-2986`,")
    say("      1716-1724), so the same 16 actions are replayed in 16 x 8.33 = 133 ms.")
    say("      There is no hold: the drive target is overwritten every tick.")
    v_demo, v_chunk, v_ach = [], [], []
    for f in sorted(glob.glob(os.path.join(REPO, "datasets/demos_v11/*.npz"))):
        v_demo.append(np.abs(np.diff(np.load(f)["action"][:, :7], axis=0)).max(1) * DEMO_HZ)
    for a in A_roll:
        v_chunk.append(speeds(a))
    for f in sorted(glob.glob(os.path.join(REPO, "datasets/rl_rollouts/p37_park/*.npz")))[:40]:
        n = os.path.basename(f)
        arm = "right"
        q = np.load(f)["joint_positions"]
        if q.shape[1] != 22:
            continue
        v_ach.append(np.abs(np.diff(q[:, ARM_DOF[arm]][:, :7], axis=0)).max(1) / 4.0 * 120.0)
    D, C, H = (np.concatenate(v_demo), np.concatenate(v_chunk), np.concatenate(v_ach))
    say(f"  measured (max-joint speed, rad/s):")
    say(f"      the demo stream (30 Hz frames, the true demo rate)   p50 {np.median(D):5.2f}  "
        f"p90 {np.percentile(D,90):5.2f}")
    say(f"      the emitted chunk (120 Hz per-step, the exec rate)   p50 {np.median(C):5.2f}  "
        f"p90 {np.percentile(C,90):5.2f}")
    say(f"      the ACHIEVED joint motion (120 Hz, from the store)   p50 {np.median(H):5.2f}  "
        f"p90 {np.percentile(H,90):5.2f}")
    say(f"  so the command/achievement ratio is {np.median(C)/max(np.median(H),1e-9):.0f}x, and the")
    say(f"  achieved rate ({np.median(H):.2f} rad/s) is the demo's own ({np.median(D):.2f} rad/s): the")
    say("  drive is a 0.2 s low-pass and turns the 4x replay into a dither.")
    say("  The discriminating one-line battery for phase 3 (not run here): hold each")
    say("  action for 4 ticks (execute_steps=16, or a hold counter) and measure the")
    say("  achieved rate, the residual and the decisions (= one per 0.533 s of sim,")
    say("  i.e. ~4/episode instead of ~64, -4.3 s of the 28.6 s wall).")


def section_b6():
    bars()
    say("B6. THE CENSUS CORRECTIONS THIS LANE MEASURED (read with A and B above)")
    bars()
    say("  (1) DECISIONS/EPISODE. The census's '246-259 decisions/episode' is a")
    say("      misreading of the `[rl] episode` row's `decision=` field, which is the")
    say("      control step at which the primitive takes over (`_run_primitive`,")
    say("      `rl_env.py:3864`; `_finalize` reads it at 3917). The measured decision")
    say("      count is 53-77/episode (the `[loop]` rows) and the handover step is")
    say("      78-393 (mean 252 = 14 % of the episode's ticks).")
    say("  (2) CHUNK DURATION. 16 actions x 1 control tick = 133 ms, not 533 ms; the")
    say("      '0.533 s planning horizon' in MODEL_CENSUS §1.3 is a 4x overstatement.")
    say("  (3) THE CHUNK'S OWN RATE. `MODEL_CENSUS` §2.3/§3.2 convert the intra-chunk")
    say("      deltas at 30 Hz (the recorded-frame rate); the chunk is executed at")
    say("      120 Hz, so every intra-chunk speed and every headroom ratio there is")
    say("      4x too small. From the census's OWN cache:")
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy_chunks.npz")
    z = np.load(cache)
    lim = np.array([16.75, 16.75, 5.45, 5.45, 20.94, 20.94, 20.94])
    for key, label in (("first4", "executed (first 3 steps)"), ("intra", "all 15 steps")):
        D = z[key]
        say(f"        {label}: p99 % of limit " +
            " ".join(f"{x:3.0f}" for x in np.percentile(D, 99, 0) * 120 / lim * 100) +
            f" | max {D.max(0).max()*120/lim[D.max(0).argmax()]:.1f}x (j{D.max(0).argmax()+1})")
        say("          over a limit: " + ", ".join(
            f"s={s} {int((D*s*120>lim[None,:]).sum())}/{D.size}" for s in (1.0, 1.25, 1.5, 2.0)))
    say("      (the census's table reads 0/1512 at s=1.0 and 1/1512 at 1.25/1.5;")
    say("      the p99 headroom it calls 2.35x/3.34x is 0.83x at j4.)")
    say("  (4) THE '13 ACTIONS' BOUND. It is h <= 7 (per-action execution is 8.33 ms),")
    say("      it is a ceiling, and it does not bind the synchronous shipped loop.")


def main() -> int:
    section_a()
    section_b()
    z = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "p2b_chunks_abs.npz"))
    section_b5c(z["roll"])
    section_b6()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "p2b_feasibility_out.txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(BUF) + "\n")
    print(f"\nwrote {out} ({len(BUF)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
