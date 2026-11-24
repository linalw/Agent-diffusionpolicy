# P259 results: the place blend was 2-4x over-timed - **-0.5 s/attempt** at 39/40

**2026-11-25, `logs/p259/`.** The `place` block decomposed, one measurement cell, and
one adopted default (**Panda-only by construction**).

---

## 1. The block, decomposed

`place` = `_place_clear` (0.10 m up, `move_to` tol 12 mm) + `_blend_to(bin_above)`
(**150 ticks + 40 settle**) + the Cartesian transit + `_place_low`. Each phase has its
own knob, so it decomposes by perturbation:

| arm | `place` | attempt `total` | placed |
|---|---|---|---|
| P258 armed (control) | **3.48 s** | **11.43 s** | 20/20 |
| `FRUIT_PLACE_CLEAR=0` (measurement) | **3.05 s** | 11.02 s | 8/8 |
| `FRUIT_PLACE_BLEND_TICKS=90`, s905 | **2.99 s** | **10.96 s** | **19/20** |
| `FRUIT_PLACE_BLEND_TICKS=90`, s906 | **2.99 s** | **10.73 s** | **20/20** |

**So: clear 0.43 s, blend ~1.58 s, transit+low ~1.47 s.** The clear is **not touched** -
P227p measured it as the pear's protection (`clr_win=-74 mm@belt` and a lost cleanly
lifted payload without it) and 0.43 s is what that insurance costs.

**The blend is 150+40 ticks whatever the distance**, and P254's arithmetic says a
0.36-2.3 rad move needs **15-95** ticks at the arm's 5.445 rad/s - i.e. it was
**2-4x over-timed**. At 90:

* `place` **3.48 -> 2.99 s** at **both** seeds (the block is a deterministic clock);
* the attempt **11.43 -> 10.96 / 10.73 s** (**-0.47 / -0.70 s**);
* **39/40 placed**, and **the one loss is the known 2.8 cm grasp class**
  (`grasped=False`, `fruit did not follow the gripper`, `grasp_lift` stored pad centre
  101 mm off) - **not a place-side loss: all 39 placements landed**.

## 2. Adopted, and it cannot reach the scripted lines

The blend sits inside `if robot_kind() == "franka"` (P227n's scope), so the OpenArm
scripted and two-line paths **cannot read it** - the default is now **90**
(`FRUIT_PLACE_BLEND_TICKS=150` restores). Proved: `accept.sh` is **`fingerprint:
matches`** with its **459 `[fruit]` lines 459/459 identical** to
`logs/p227/accept_final.log`; `selfcheck.sh` **PASS (0 failures, 1 skipped)**.

## 3. Where the throughput now is

**Attempt cycle**: **13.55 -> 12.13** (P249, the catch-up exit) **-> 11.43** (P258, the
duplicated clearance) **-> 10.85** (P259, the over-timed blend) = **-20 %** over the arc,
at the same success (98.6 % pooled at 0.08).

**And the honest caveat on throughput**: `s/pick` cannot be quoted from one cell - the
`gap` (the return + the next pick's setup) is **bimodal per cell** (median 267-270 in
most cells, **432** in two of the five measured here, i.e. the arm waited for fruit), so
`s/pick` swings 13.6-15.0 s on the same cycle. The **cycle** is the arm's own work and it
is stable to the hundredth; a throughput figure should be quoted as a **range over
cells** (`~4.4-4.6 picks/min` at 0.08), not as a point.

## 4. Pins

`tasks.py` **`05457705`** (the default + its note), `rl_env.py` (`TASKS_MD5` follow);
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; ckpt `p227_panda156`.
Evidence `logs/p259/`.
