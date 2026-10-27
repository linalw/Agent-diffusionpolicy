#!/usr/bin/env python3
"""P52 phase 1 — the offline model census (no simulator, no `src/` edit).

Reproduce every number in `logs/p52/MODEL_CENSUS.md`:

    python3 logs/p52/model_census.py --write      # ~60 s (GPU policy sampling)

Sections
  A  the plumbing: the action space/units, the chunk, the execution cadence,
     the DDIM steps, the env-side shapers, the episode tick census
  B  the action streams: the demos' (scripted, 30 Hz) and the policy's own
     emitted chunks (offline GPU sampling of the shipped checkpoint), the
     executed-command stream recorded by the rollout stores
  C  the demo's per-leg dynamics, parsed from the `[motion]` rows
  D  the re-timing headroom: per-leg `s_*` ratios against every measured cap
  E  the direct corpora's failure classes (P43 park A/B)

Reading rules (AGENTS.md section 2): every count is one draw of an attractor;
the per-leg and per-decision quantities are the measurements.
"""

from __future__ import annotations

import glob
import json
import os
import re
import statistics
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))

#: `maxJointVelocity` read back from the USD (`logs/p44/CAP_CENSUS.md` §1.1):
#: 960 / 312 / 1200 deg/s -> rad/s. Joint order = the arm's `arm_dofs`.
JOINT_VLIM = np.array([16.75, 16.75, 5.45, 5.45, 20.94, 20.94, 20.94])
#: The tip speed each joint's own limit buys at the nominal lever arms
#: (`CAP_CENSUS.md` §1.3) - the tightest are j4 0.84 and j7 0.79 m/s.
JOINT_TIP_AT_VLIM = np.array([8.38, 7.37, 1.63, 0.84, 2.00, 2.52, 0.79])
#: The friction cone's acceleration budget per leg (`CAP_CENSUS.md` §2.4),
#: `g*(sqrt(uz^2+mu_eff^2-1)-uz)` at `mu_eff = 0.6*2.0 = 1.2`.
CONE_A_BUDGET = {"grasp_lift": 1.962, "place0": 4.273, "place1": 4.273,
                 "place low": 1.962, "approach": float("inf")}

DT = 1.0 / 120.0
DEMO_HZ = 30.0                     # 4-tick decimation, the demo cadence


#: Every printed line is also kept here and written to `model_census_out.txt`.
BUF: list[str] = []


def say(*a):
    line = " ".join(str(x) for x in a)
    BUF.append(line)
    print(line, flush=True)


# --------------------------------------------------------------------------- #
# A. the plumbing
# --------------------------------------------------------------------------- #
def section_a():
    import torch

    say("=" * 78)
    say("A. THE PLUMBING")
    say("=" * 78)
    rows = []
    for name in ("moe_v12", "moe_v13s"):
        path = os.path.join(REPO, "checkpoints", name, "policy_best.pt")
        ck = torch.load(path, map_location="cpu", weights_only=False)
        cfg, norm = ck["config"], ck["normalizer"]
        say(f"[A] {name}: " + " ".join(
            f"{k}={cfg[k]}" for k in ("action_dim", "action_horizon", "obs_horizon",
                                      "proprio_dim", "goal_dim", "image_size",
                                      "image_channels", "num_diffusion_steps",
                                      "beta_schedule")))
        am = np.asarray(norm["action_mean"], dtype=float)
        asd = np.asarray(norm["action_std"], dtype=float)
        say("[A]   action_mean [j1..j7, finger, finger] = "
            + " ".join(f"{v:+.3f}" for v in am))
        say("[A]   action_std  = " + " ".join(f"{v:.3f}" for v in asd)
            + f"   (finger {asd[7]*1000:.1f} mm)")
        # the raw action units: the mean target of the demo distribution, per joint
        rows.append((name, am, asd, cfg))
    say("[A] units: action[:7] = the active arm's 7 ABSOLUTE joint POSITIONS [rad]")
    say("          action[7] = the finger opening [m] (clipped to [0, 0.044]),")
    say("          action[8] = the same value, recorded only (rl_env.py:62-64, 3036-3045)")
    say("    NOT deltas, NOT Cartesian: `_apply` writes them straight to the drive")
    say("    targets (`set_dof_position_targets([action[:7]])`, rl_env.py:3033-3039;")
    say("    the same two lines in the hybrid evaluator, 60_eval_policy.py:393-395).")
    return rows


def section_a_sites():
    """Every `FRUIT_POLICY_*` / loop knob that touches the applied action."""
    say("[A] the env-side shapers that touch the action before the drive:")
    say("    FRUIT_POLICY_TRACK      (rl_env.py:945, 3584-3609)  default 0: adds")
    say("                            J^+ v_fruit dt to the 7 joint targets (a")
    say("                            velocity feed-forward, not a scale)")
    say("    FRUIT_A2C2              (rl_env.py:1291-1298, 3026-3030) default off:")
    say("                            a trained 9-D correction head, gain/clamp")
    say("                            via FRUIT_A2C2_GAIN/_CLAMP")
    say("    FRUIT_POLICY_EVENT      (rl_env.py:2939-2940, 3560-3582) changes the")
    say("                            per-decision horizon, not the action")
    say("    FRUIT_RTC / FRUIT_VLASH (runtime.py:100-124) default off: continuous")
    say("                            chunk switching (one action per control tick)")
    say("    NO clamp, NO IK: `ik_step`'s FRUIT_IK_MAX_STEP 0.5 rad (control.py:147,")
    say("    423) is on the SCRIPTED path only; the direct path never calls IK.")
    say("    NO scaling: the only clip is the finger [0, 0.044] (rl_env.py:3036).")
    say("    Consequence: a policy command past a joint limit is not refused - the")
    say("    drive pushes into the limit (the `[acq] ... clip_min` class).")


def section_a_cadence():
    say("[A] the cadence (code sites):")
    say("    control/physics tick  1/120 s, FRUIT_SUBSTEPS 1      (control.py:30, common.py)")
    say("    observation + model   every 4th control tick -> 30 Hz of sim")
    say("                           (rl_env.py:2945 `if self._step % 4 == 0`)")
    say("    execute_steps          4 (rl_env.py:900 default; 2931 `steps`)")
    say("    one action per control tick, physics advanced one tick per action")
    say("                           (rl_env.py:2978-2990 `_apply` then `advance(1)`)")
    say("    => one DECISION = 4 control ticks = 33.3 ms of sim; it executes 4 of")
    say("       the 16 predicted actions (25 % of the chunk, receding horizon)")
    say("    chunk                  16 actions x 33.3 ms = 0.533 s of geometric path")
    say("    DDIM                   16 denoising steps, training chain 100 (cosine)")
    say("                           (60_eval_policy.py:49, rl_env.py:901)")
    say("    policy horizon         1500 control steps = 12.5 s of sim, reward.horizon")
    say("                           (rl_env.py:457-481)")
    say("    demo cadence           30 Hz (4-tick decimation), same as the policy's")


def section_a_transport():
    """The policy phase's belt-transport floor (how much of it is *waiting*)."""
    say("[A] the policy phase's belt floor (the part a time-scale CANNOT touch):")
    out = {}
    for arm in ("A", "B"):
        files = sorted(glob.glob(os.path.join(REPO, f"logs/p43/p3/{arm}_*.log")))
        travel, phase, speed, ticks = [], [], [], []
        for f in files:
            text = open(f, errors="replace").read()
            first = {int(m.group(1)): float(m.group(2)) for m in re.finditer(
                r"\[align\] episode (\d+) knob=\d+ .*? first=([+-][\d.]+)", text)}
            for m in re.finditer(
                    r"\[rl\] episode (\d+): \w+(?: grade=\w+)? d=[\d.]+cm "
                    r"bin=\d arm=\w+(?: y=[+-][\d.]+)? success=(\w+) grasped=\w+ "
                    r"placed=(\w+) ticks=(\d+) decision=(\d+).*?notes=\[(.*?)\]",
                    text):
                ep, _succ, placed, tk, dec, notes = m.groups()
                if placed != "True" or int(ep) not in first:
                    continue
                t = re.search(r"intercept trigger \(dy=([\d.]+)cm", notes)
                sp = re.search(r"speed=([\d.]+)m/s", notes)
                if not t or not sp:
                    continue
                travel.append(first[int(ep)] - float(t.group(1)) / 100.0)
                phase.append(int(dec) * 4.0)
                speed.append(float(sp.group(1)))
                ticks.append(int(tk))
        if not travel:
            continue
        floor = np.array(travel) / np.array(speed)
        ph_s = float(np.mean(phase) * DT)
        fl_s = float(np.mean(floor))
        ep_s = float(np.mean(ticks) * DT)
        motion = ph_s - fl_s
        say(f"    arm {arm}: n={len(floor)} placed episodes | fruit travel during the")
        say(f"      policy phase {np.mean(travel):.3f} m at {np.mean(speed):.3f} m/s -> "
            f"belt floor {fl_s:.2f} s ({fl_s/ph_s*100:.0f} % of the {ph_s:.2f} s "
            f"policy phase)")
        say(f"      => arm motion {motion:.2f} s of the {ph_s:.2f} s phase; at s=1.25 "
            f"it falls {motion*0.25:.2f} s = {motion*0.25/ep_s*100:.0f} % of the "
            f"{ep_s:.2f} s episode; at s=1.5 {motion/3:.2f} s = "
            f"{motion/3/ep_s*100:.0f} %")
        out[arm] = dict(floor=fl_s, phase=ph_s, motion=motion, episode=ep_s)
    return out


def section_a_episodes():
    say("[A] the direct corpus's own tick census (P43 A/B, `[rl] episode` rows):")
    out = {}
    for arm, files in (("A", sorted(glob.glob(os.path.join(REPO, "logs/p43/p3/A_*.log")))),
                       ("B", sorted(glob.glob(os.path.join(REPO, "logs/p43/p3/B_*.log"))))):
        ticks, dec, walls, placed_flags = [], [], [], []
        for f in files:
            text = open(f, errors="replace").read()
            for m in re.finditer(r"success=(\w+) grasped=(\w+) placed=(\w+) "
                                 r"ticks=(\d+) decision=(\d+)", text):
                ticks.append(int(m.group(4)))
                dec.append(int(m.group(5)))
                placed_flags.append(m.group(3) == "True")
            w = re.search(r"run wall end [\d.]+ duration ([\d.]+)s", text)
            if w and ticks:
                walls.append(float(w.group(1)))
        if not ticks:
            continue
        say(f"    arm {arm}: n={len(ticks)} episodes  ticks mean {np.mean(ticks):.0f} "
            f"(median {np.median(ticks):.0f}, range {min(ticks)}-{max(ticks)})")
        say(f"           sim time/episode {np.mean(ticks)*DT:.2f} s   decisions "
            f"{np.mean(dec):.0f} ({np.mean(dec)*4:.0f} policy ticks = "
            f"{np.mean(dec)*4/np.mean(ticks)*100:.0f} % of the episode)")
        if walls:
            say(f"           app wall {sum(walls)/len(ticks):.1f} s/episode over "
                f"{len(files)} runs of 15 (startup included)")
        placed_ticks = [t for t, ok in zip(ticks, placed_flags) if ok]
        placed_dec = [d for d, ok in zip(dec, placed_flags) if ok]
        if placed_ticks:
            pre = np.mean(placed_dec) * 4.0
            say(f"           placed episodes: n={len(placed_ticks)} ticks "
                f"{np.mean(placed_ticks):.0f} = policy phase {pre:.0f} ticks "
                f"({pre*DT:.2f} s) + scripted phase "
                f"{(np.mean(placed_ticks)-pre):.0f} ticks "
                f"({(np.mean(placed_ticks)-pre)*DT:.2f} s)")
        out[arm] = dict(n=len(ticks), ticks=float(np.mean(ticks)),
                        decisions=float(np.mean(dec)),
                        sim_s=float(np.mean(ticks) * DT),
                        policy_ticks=float(np.mean(dec) * 4.0))
    return out


# --------------------------------------------------------------------------- #
# B1. the demos' action stream (scripted, 30 Hz commanded joint targets)
# --------------------------------------------------------------------------- #
def dq_stats(A: np.ndarray) -> np.ndarray:
    """|delta| per 30 Hz step inside one episode (no cross-episode diffs)."""
    if A.shape[0] < 3:
        return np.zeros((0, 7))
    return np.abs(np.diff(A[:, :7], axis=0))


def split_jumps(dq: np.ndarray, lo: float = 0.02, hi: float = 0.05):
    """Split per-joint deltas into 'smooth' and single-tick 'jump' steps.

    A jump is a step above `hi` whose neighbours are both below `lo` (the
    scripted line's mode switches - the grasp-config snap, a leg boundary).
    Only the smooth part is a velocity.
    """
    smooth, jumps = [], []
    for j in range(dq.shape[1]):
        c = dq[:, j]
        smooth_j, jump_j = [], []
        for i, v in enumerate(c):
            prev = c[i - 1] if i > 0 else 0.0
            nxt = c[i + 1] if i + 1 < len(c) else 0.0
            (jump_j if (v > hi and prev < lo and nxt < lo) else smooth_j).append(v)
        smooth.append(np.array(smooth_j) if smooth_j else np.zeros(1))
        jumps.append(np.array(jump_j) if jump_j else np.zeros(1))
    return smooth, jumps


def section_b_demos():
    say()
    say("=" * 78)
    say("B1. THE DEMOS' ACTION STREAM (the scripted line, 30 Hz commands)")
    say("=" * 78)
    files = sorted(glob.glob(os.path.join(REPO, "datasets/demos_v11/*.npz")))
    dqs, finger = [], []
    for f in files:
        A = np.load(f)["action"]
        dqs.append(dq_stats(A))
        if A.shape[0] > 2:
            finger.append(np.abs(np.diff(A[:, 7])))
    dq = np.concatenate([d for d in dqs if len(d)], axis=0)
    fing = np.concatenate(finger) if finger else np.zeros(1)
    smooth, jumps = split_jumps(dq)
    say(f"    {len(files)} episodes, {dq.shape[0]} 30 Hz steps "
        f"({dq.shape[0]*4*DT:.0f} s of demo time)")
    say("    per joint: p50 / p90 / p99 | smooth-only max | jumps (n) |")
    say("               p99 speed [rad/s] (% of the joint limit) | smooth max speed")
    for j in range(7):
        c = dq[:, j]
        sm = smooth[j]
        say(f"      j{j+1}: {np.percentile(c,50):.4f} {np.percentile(c,90):.4f} "
            f"{np.percentile(c,99):.4f} | {sm.max():.4f} | {len(jumps[j]):5d} | "
            f"{np.percentile(c,99)*DEMO_HZ:5.2f} rad/s "
            f"({np.percentile(c,99)*DEMO_HZ/JOINT_VLIM[j]*100:4.0f} %) | "
            f"{sm.max()*DEMO_HZ:5.2f} rad/s ({sm.max()*DEMO_HZ/JOINT_VLIM[j]*100:4.0f} %)")
    say("    finger channel (m/step): p50 %.4f p99 %.4f max %.4f -> p99 %.3f m/s of the"
        % (np.percentile(fing, 50), np.percentile(fing, 99), fing.max(),
           np.percentile(fing, 99) * DEMO_HZ))
    say("      1.0 m/s drive limit (the close is a 48-tick clock, not a speed)")
    net4, net16 = [], []
    for f in files:
        A = np.load(f)["action"][:, :7]
        n = A.shape[0]
        for i in range(0, n - 4, 4):
            net4.append(np.abs(A[i + 4] - A[i]))
        for i in range(0, n - 16, 16):
            net16.append(np.abs(A[i + 16] - A[i]))
    net4d = np.stack(net4, 0)
    net16d = np.stack(net16, 0)
    say("    NET DISPLACEMENT the demo stream asks for (non-overlapping, rad):")
    say("      per 4 steps  median "
        + " ".join(f"{v:.3f}" for v in np.median(net4d, 0))
        + f"  | summed {np.median(net4d.sum(1)):.3f}")
    say("      per 16 steps median "
        + " ".join(f"{v:.3f}" for v in np.median(net16d, 0))
        + f"  | summed {np.median(net16d.sum(1)):.3f}")
    say("    the joint-space speed the demo stream actually commands:")
    say("      p99 = %.2f rad/s over the 7 joints, i.e. %.2fx the tightest limit"
        % (np.percentile(dq, 99) * DEMO_HZ,
           np.percentile(dq, 99) * DEMO_HZ / JOINT_VLIM.max()))
    return dq


# --------------------------------------------------------------------------- #
# B2. the policy's own emitted chunks (offline, GPU, no simulator)
# --------------------------------------------------------------------------- #
def _push(policy, d, i):
    policy.push_frame(d["image_rgb"][i],
                      d["image_distance_to_image_plane"][i],
                      d["target_mask"][i])


def section_b_policy(n_ep: int = 24, frames=(40, 90, 140), seed: int = 11):
    """Sample the shipped checkpoint on demo observations; census the chunks."""
    import torch

    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "policy_chunks.npz")
    if os.path.exists(cache) and "--force" not in sys.argv:
        z = np.load(cache)
        say()
        say("=" * 78)
        say("B2. THE POLICY'S OWN CHUNKS (cached from %s)" % os.path.basename(cache))
        say("=" * 78)
        say("    moe_v12, 16 DDIM steps, FRUIT_POLICY_SEED=%d (%d chunk pairs)" % (
            seed, z["bound"].shape[0]))
        return z["intra"], z["first4"], z["bound"], z["net4"], z["net16"]

    os.environ["FRUIT_POLICY_SEED"] = str(seed)
    torch.manual_seed(seed)
    from fruit_sorting.policy.runtime import PolicyRunner

    say()
    say("=" * 78)
    say("B2. THE POLICY'S OWN CHUNKS (offline sampling, moe_v12, %d DDIM steps, seed %d)"
        % (16, seed))
    say("=" * 78)
    files = sorted(glob.glob(os.path.join(REPO, "datasets/demos_v11/*.npz")))[:n_ep]
    policy = PolicyRunner(os.path.join(REPO, "checkpoints/moe_v12/policy_best.pt"),
                          device="cuda")
    intra, first4, bound, net4, net16 = [], [], [], [], []
    for f in files:
        d = np.load(f)
        n = d["action"].shape[0]
        for i in frames:
            if i + 1 >= n:
                continue
            proprio = np.concatenate([
                d["joint_positions"][i],
                [float(d["finger_opening"][i][0])],
                d["tactile"][i]]).astype(np.float32)
            policy.reset()
            _push(policy, d, i - 1)
            _push(policy, d, i)
            a = policy.act(proprio, d["goal"][i], num_steps=16)
            proprio2 = np.concatenate([
                d["joint_positions"][i + 1],
                [float(d["finger_opening"][i + 1][0])],
                d["tactile"][i + 1]]).astype(np.float32)
            policy.reset()
            _push(policy, d, i)
            _push(policy, d, i + 1)
            b = policy.act(proprio2, d["goal"][i + 1], num_steps=16)
            intra.append(np.abs(np.diff(a[:, :7], axis=0)))     # 15 x 7
            first4.append(np.abs(np.diff(a[:4, :7], axis=0)))   # 3 x 7 (executed)
            bound.append(np.abs(b[0, :7] - a[3, :7]))            # 1 x 7 (re-plan)
            net4.append(np.abs(a[3, :7] - a[0, :7]))             # net per decision
            net16.append(np.abs(a[15, :7] - a[0, :7]))           # net per chunk
    intra = np.concatenate(intra, 0)
    first4 = np.concatenate(first4, 0)
    bound = np.stack(bound, 0)
    net4 = np.stack(net4, 0)
    net16 = np.stack(net16, 0)
    np.savez_compressed(cache, intra=intra, first4=first4, bound=bound,
                        net4=net4, net16=net16)
    say(f"    {len(files)} episodes x {len(frames)} frames = {bound.shape[0]} chunk "
        f"pairs, {intra.shape[0]} intra-chunk steps")
    for label, arr in (("intra-chunk (all 15)", intra),
                       ("intra-chunk (executed 3)", first4),
                       ("re-plan boundary jump", bound)):
        say(f"    {label}:")
        for j in range(7):
            c = arr[:, j]
            say(f"      j{j+1}: p50 {np.percentile(c,50):.4f} p90 "
                f"{np.percentile(c,90):.4f} p99 {np.percentile(c,99):.4f} max "
                f"{c.max():.4f} | p99 {np.percentile(c,99)*DEMO_HZ:5.2f} rad/s "
                f"({np.percentile(c,99)*DEMO_HZ/JOINT_VLIM[j]*100:5.0f} %)")
    return intra, first4, bound, net4, net16


def scale_table(name: str, per_step: np.ndarray):
    """At each time-scale, how many steps exceed a joint-velocity limit."""
    say(f"    {name}: steps whose command exceeds the joint limit")
    per30 = JOINT_VLIM / DEMO_HZ
    for s in (1.0, 1.25, 1.5, 2.0):
        over = (per_step * s > per30[None, :]).sum(0)
        worst = int(over.argmax())
        say(f"      s={s:<4}: total {int(over.sum()):5d} over-limit joint-steps "
            f"({over.sum()/per_step.size*100:5.1f} % of {per_step.size}) | "
            f"worst j{worst+1} {int(over[worst]):4d} "
            f"({over[worst]/per_step.shape[0]*100:4.1f} % of steps)")


# --------------------------------------------------------------------------- #
# B3. the recorded executed stream (rollout stores)
# --------------------------------------------------------------------------- #
def section_b_rollouts():
    say()
    say("=" * 78)
    say("B3. THE RECORDED EXECUTED COMMAND (rollout stores, 30 Hz observation ticks)")
    say("=" * 78)
    say("    CAVEAT (structural): `_record_tick` fires only when `_step == "
        "`_observed_step`")
    say("    (rl_env.py:3767-3772), i.e. on the FIRST tick of each 4-tick `act` call,")
    say("    which is chunk index 0. A recorded 30 Hz pair therefore spans one full")
    say("    re-plan (3 executed intra-chunk steps + the boundary jump), so this")
    say("    stream is the *decision-cadence* command, not the intra-chunk rate.")
    out = {}
    for store in ("p37_park", "r9_awr"):
        files = sorted(glob.glob(os.path.join(REPO, "datasets/rl_rollouts", store, "*.npz")))
        if not files:
            continue
        dqs = [dq_stats(np.load(f)["action"]) for f in files]
        dq = np.concatenate([d for d in dqs if len(d)], 0)
        say(f"    {store}: {len(files)} episodes, {dq.shape[0]} steps")
        for j in range(7):
            c = dq[:, j]
            say(f"      j{j+1}: p50 {np.percentile(c,50):.4f} p90 {np.percentile(c,90):.4f} "
                f"p99 {np.percentile(c,99):.4f} | p99 "
                f"{np.percentile(c,99)*DEMO_HZ:5.2f} rad/s "
                f"({np.percentile(c,99)*DEMO_HZ/JOINT_VLIM[j]*100:5.0f} %)")
        scale_table(store, dq)
        out[store] = dq
    return out


# --------------------------------------------------------------------------- #
# C. the demo's per-leg dynamics ([motion] rows)
# --------------------------------------------------------------------------- #
CARRY_RE = re.compile(
    r"\[motion\] carry (\w+): ([\d.]+) cm, (\d+) ticks, \|v\|cmd=([\d.]+) "
    r"\|a\|cmd=([\d.]+),.*?steps=(\d+), \|v\|max=([\d.]+) m/s, "
    r"\|a\|max=([\d.]+) m/s\^2,.*?cone=([\d.]+)x budget \((\d+) pct over\)")
APPR_RE = re.compile(
    r"\[motion\] approach\(cartesian\): ([\d.]+) cm, (\d+) samples: steps=(\d+), "
    r"\|v\|max=([\d.]+) m/s, \|a\|max=([\d.]+) m/s\^2,.*?ends \|v\|=([\d.]+)/([\d.]+) m/s"
    r".*?a_med=([\d.]+).*?end=([\d.]+) mm")

MOTION_LOGS = [
    "logs/p41/p2/accept_profile.log",
    "logs/p41/p2/pear_profile.log",
    "logs/p41/p2/twoline_profile.log",
    "logs/p43/accept_p4.log",
    "logs/p44/p2/accept_s5_C.log",
    "logs/p44/p2/accept_s6_C.log",
]


def section_c():
    say()
    say("=" * 78)
    say("C. THE DEMO'S PER-LEG DYNAMICS (the `[motion]` rows)")
    say("=" * 78)
    say("    `|v|cmd` / `|a|cmd` = the COMMANDED profile's peak (tasks.py:4287);")
    say("    `|v|max` in the `steps=` block = the ACHIEVED TCP speed (MotionMonitor).")
    legs = {}
    for rel in MOTION_LOGS:
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            say(f"    (missing {rel})")
            continue
        text = open(path, errors="replace").read()
        for m in CARRY_RE.finditer(text):
            name, d, ticks, vc, ac, steps, vm, am, cone, over = m.groups()
            legs.setdefault(name, []).append(
                dict(log=rel, d=float(d), ticks=int(ticks), v_cmd=float(vc),
                     a_cmd=float(ac), v_max=float(vm), a_max=float(am),
                     cone=float(cone), over=int(over)))
        for m in APPR_RE.finditer(text):
            d, n, steps, vm, am, v_end, v_end2, a_med, endmm = m.groups()
            legs.setdefault("approach", []).append(
                dict(log=rel, d=float(d), ticks=int(steps), v_cmd=float("nan"),
                     a_cmd=float("nan"), v_max=float(vm), a_max=float(am),
                     cone=float("nan"), over=0,
                     v_end=float(v_end), a_med=float(a_med),
                     end_mm=float(endmm) if endmm else float("nan")))
    for name, rows in legs.items():
        vc = [r["v_cmd"] for r in rows if not np.isnan(r["v_cmd"])]
        ac = [r["a_cmd"] for r in rows if not np.isnan(r["a_cmd"])]
        vmax = [r["v_max"] for r in rows]
        say(f"    {name}: n={len(rows)}  d {np.mean([r['d'] for r in rows]):.1f} cm  "
            f"ticks {np.mean([r['ticks'] for r in rows]):.0f}")
        if vc:
            say(f"      |v|cmd {np.mean(vc):.3f} (range {min(vc):.3f}-{max(vc):.3f}) "
                f"|a|cmd {np.mean(ac):.3f} ({min(ac):.3f}-{max(ac):.3f})")
            overs = sum(1 for r in rows if r["v_max"] > 1.5 * r["v_cmd"])
            say(f"      achieved |v|max median {np.median(vmax):.3f} "
                f"({min(vmax):.3f}-{max(vmax):.3f}) | {overs}/{len(rows)} legs above "
                f"1.5x their command (the escape signature)")
        else:
            say(f"      achieved |v|max {np.median(vmax):.3f} "
                f"({min(vmax):.3f}-{max(vmax):.3f}) |a|max median "
                f"{np.median([r['a_max'] for r in rows]):.3f}")
        cones = [r["cone"] for r in rows if not np.isnan(r["cone"])]
        if cones:
            say(f"      cone {np.mean(cones):.2f}x budget "
                f"(range {min(cones):.2f}-{max(cones):.2f}); "
                f"{sum(1 for c in cones if c > 1.0)}/{len(cones)} legs over 1.0x")
        if name == "approach":
            says = [r for r in rows if "end_mm" in r and not np.isnan(r["end_mm"])]
            if says:
                say(f"      end= shortfall {np.mean([r['end_mm'] for r in says]):.1f} mm "
                    f"({min(r['end_mm'] for r in says):.1f}-{max(r['end_mm'] for r in says):.1f})"
                    f"  ends |v| {np.mean([r['v_end'] for r in says]):.3f} m/s"
                    f"  a_med {np.mean([r['a_med'] for r in says]):.2f} m/s^2")
    return legs


# --------------------------------------------------------------------------- #
# D. the re-timing headroom, per leg
# --------------------------------------------------------------------------- #
def profile_ticks(d: float, v: float, a: float, j: float = 25.0) -> float:
    """`motion.py::jerk_limited`'s duration in ticks (the three-term max, x1.02)."""
    if d <= 0:
        return 0.0
    dur = max(1.875 * d / v, np.sqrt(5.774 * d / a), (60.0 * d / j) ** (1.0 / 3.0)) * 1.02
    return dur / DT


def section_d(legs, intra=None, first4=None, bound=None, net4=None, net16=None):
    say()
    say("=" * 78)
    say("D. THE RE-TIMING HEADROOM (a time-scale s: same path, 1/s the ticks)")
    say("=" * 78)
    say("    A time-scale multiplies v by s, a by s^2, j by s^3 (the same path).")
    say("    `s_*` columns are the scale at which that one limit is reached:")
    say("      s_joint  joint velocity, tip-equivalent (tightest joint 0.79-0.84 m/s)")
    say("      s_cone   the friction cone's a-budget (loaded legs only)")
    say("      s_pay    where the profile's v-term meets its a-term (raise v alone")
    say("               and the duration stops falling - CAP_CENSUS section 4.3)")
    say("      s_drive  the achieved/commanded speed ratio (how well the servo")
    say("               tracks the CURRENT cap; < 1 means it cannot track it)")
    table = []
    # the shipped dynamic caps (tasks.py:3516-3555, 6066, 12323)
    caps = {"grasp_lift": (0.30, 1.0), "place0": (0.35, 1.089),
            "place1": (0.35, 1.089), "approach": (0.15, 0.8),
            "place low": (0.30, 1.962)}
    for name, rows in legs.items():
        if name not in caps:
            continue
        v_cap, a_cap = caps[name]
        vc = np.nanmean([r["v_cmd"] for r in rows if not np.isnan(r["v_cmd"])]) \
            if any(not np.isnan(r["v_cmd"]) for r in rows) else np.nan
        ac = np.nanmean([r["a_cmd"] for r in rows if not np.isnan(r["a_cmd"])]) \
            if any(not np.isnan(r["a_cmd"]) for r in rows) else np.nan
        v_ach = np.mean([r["v_max"] for r in rows])
        if np.isnan(vc):
            vc = v_cap
        if np.isnan(ac):
            ac = a_cap
        s_joint = JOINT_TIP_AT_VLIM.min() / max(vc, 1e-9)
        budget = CONE_A_BUDGET.get(name, float("inf"))
        s_cone = np.sqrt(budget / ac) if np.isfinite(budget) else float("inf")
        # where raising v alone stops paying: v = a*t_v = a*(1.875 d / v) -> v^2 = 1.875 d a
        d = np.mean([r["d"] for r in rows]) / 100.0
        v_pay = np.sqrt(1.875 * d * a_cap)
        s_pay = v_pay / max(vc, 1e-9)
        # the achieved/commanded ratio: median, so a single escape leg cannot fake it
        s_drive = float(np.median([r["v_max"] for r in rows])) / max(vc, 1e-9)
        s_hard = min(s_joint, s_cone)
        binding = "joint" if s_joint <= s_cone else "cone"
        table.append((name, d, vc, ac, v_ach, s_joint, s_cone, s_pay, s_drive,
                      s_hard, binding, profile_ticks(d, v_cap, a_cap)))
        say(f"    {name:10s} d={d*100:5.1f} cm | cmd v={vc:.3f} a={ac:.3f} | "
            f"ach v={v_ach:.3f} (ach/cmd {s_drive:.2f})")
        say(f"               s_joint={s_joint:5.2f}  s_cone={s_cone:5.2f}  "
            f"s_pay={s_pay:5.2f} | MAX SAFE s={s_hard:4.2f} ({binding} binds) | "
            f"profile {profile_ticks(d, v_cap, a_cap):.0f} ticks at the shipped cap")
    if intra is not None:
        say()
        say("    THE POLICY'S OWN STREAM (the object a time-scale actually multiplies):")
        per30 = JOINT_VLIM / DEMO_HZ
        for label, arr in (("emitted intra-chunk", intra),
                           ("executed (first 3)", first4),
                           ("re-plan boundary", bound)):
            ratio_p99 = (JOINT_VLIM / (np.percentile(arr, 99, axis=0) * DEMO_HZ))
            ratio_max = (JOINT_VLIM / (arr.max(axis=0) * DEMO_HZ))
            j = int(ratio_p99.argmin())
            k = int(ratio_max.argmin())
            say(f"      {label:20s}: max safe s at p99 = {ratio_p99.min():5.2f} "
                f"(j{j+1} binds) | at the worst single step = {ratio_max.min():5.2f} "
                f"(j{k+1} binds)")
        say("      NOTE the boundary row is NOT a rate: it is a position discontinuity")
        say("      between two plans, so a time-scale does not shorten it and the")
        say("      drive's 0.2 s time constant is what converts it into motion.")
        if net4 is not None:
            say()
            say("    NET COMMANDED DISPLACEMENT (the path the chunk asks for, rad):")
            say("      policy: per decision (4 actions) median "
                + " ".join(f"{v:.3f}" for v in np.median(net4, 0)))
            say("              per chunk (16 actions)   median "
                + " ".join(f"{v:.3f}" for v in np.median(net16, 0)))
            say(f"      => median net per chunk summed over the 7 joints = "
                f"{np.median(net16.sum(1)):.3f} rad (range "
                f"{net16.sum(1).min():.3f}-{net16.sum(1).max():.3f})")
            say(f"      => median net per decision summed = "
                f"{np.median(net4.sum(1)):.3f} rad")
    return table


# --------------------------------------------------------------------------- #
# E. the direct corpora's failure classes
# --------------------------------------------------------------------------- #
EP_RE = re.compile(r"\[rl\] episode (\d+): (\w+)(?: grade=\w+)? d=([\d.]+)cm "
                   r"bin=(\d) arm=(\w+)(?: y=[+-][\d.]+)? success=(\w+) "
                   r"grasped=(\w+) placed=(\w+) ticks=(\d+) decision=(\d+)"
                   r".*?notes=(\[.*?\])")
NOTE_KINDS = {
    "grip loss": r"grip loss",
    "station escape": r"left the pick station",
    "no follow": r"fruit did not follow",
    "grasp-hold fail": r"grasp_hold",
    "timeout": r"timeout:",
    "no firable": r"no firable fruit",
    "lateral refuse": r"lateral refuse",
    "fell off line": r"fell off",
}


def section_e():
    say()
    say("=" * 78)
    say("E. THE FAILURE CLASSES (P43 park A/B: A = park `ready`, B = park `back`)")
    say("=" * 78)
    out = {}
    for arm in ("A", "B"):
        files = sorted(glob.glob(os.path.join(REPO, f"logs/p43/p3/{arm}_*.log")))
        rows = []
        for f in files:
            for m in EP_RE.finditer(open(f, errors="replace").read()):
                rows.append(dict(species=m.group(2), arm=m.group(5),
                                 success=m.group(6) == "True",
                                 grasped=m.group(7) == "True",
                                 placed=m.group(8) == "True",
                                 ticks=int(m.group(9)), notes=m.group(11)))
        if not rows:
            continue
        n = len(rows)
        by_arm = {}
        for r in rows:
            a = r["arm"]
            d = by_arm.setdefault(a, dict(n=0, placed=0, cnp=0, nongrasp=0))
            d["n"] += 1
            if r["placed"]:
                d["placed"] += 1
            elif r["grasped"]:
                d["cnp"] += 1
            else:
                d["nongrasp"] += 1
        say(f"    arm {arm}: n={n} placed={sum(1 for r in rows if r['placed'])} "
            f"({sum(1 for r in rows if r['placed'])/n*100:.1f} %)")
        for a, d in sorted(by_arm.items()):
            say(f"      {a:5s}: n={d['n']:3d} placed {d['placed']:3d} "
                f"({d['placed']/d['n']*100:5.1f} %)  carried-not-placed {d['cnp']:3d} "
                f"({d['cnp']/d['n']*100:5.1f} %)  no-grasp {d['nongrasp']:3d} "
                f"({d['nongrasp']/d['n']*100:5.1f} %)")
        kinds = {}
        for r in rows:
            if r["placed"]:
                continue
            for k, pat in NOTE_KINDS.items():
                if re.search(pat, r["notes"]):
                    kinds[k] = kinds.get(k, 0) + 1
        say("      note classes among the failures: "
            + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items(),
                                                      key=lambda kv: -kv[1])))
        out[arm] = dict(n=n, by_arm=by_arm, kinds=kinds)
    return out


def main() -> int:
    write = "--write" in sys.argv
    say("P52 phase 1 — MODEL_CENSUS (offline; no simulator, no src/ edit)")
    say("tree: HEAD " + os.popen(f"cd {REPO} && git rev-parse --short HEAD").read().strip())
    section_a()
    section_a_sites()
    section_a_cadence()
    section_a_episodes()
    section_a_transport()
    section_b_demos()
    intra, first4, bound, net4, net16 = section_b_policy()
    scale_table("policy intra-chunk (the emitted rate)", intra)
    scale_table("policy executed steps", first4)
    scale_table("policy re-plan boundary", bound)
    section_b_rollouts()
    legs = section_c()
    section_d(legs, intra, first4, bound, net4, net16)
    section_e()
    if write:
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "model_census_out.txt")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(BUF) + "\n")
        say(f"[written] {out} ({len(BUF)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
