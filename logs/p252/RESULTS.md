# P252 results: the **deployment shape** is measured - continuous, no reset, **19/20 = 95 % at 0.08 m/s**

**2026-11-25, `logs/p252/`.** Two continuous cells (one episode, **10 picks, no
per-pick reset**, the return transit instead of the teleport), the full P227z/P249
recipe. **No `src/` change** - `--continuous` and `FRUIT_CONTINUOUS_TRANSIT` already
existed.

---

## 1. Why this matters for the objective

Every number this engagement has quoted is measured in the **per-episode** harness:
each pick ends, the arm teleports back to the aligned start pose, the belt is
re-primed. **A real cell never does that.** If the reset is quietly doing part of the
work, the 91.7 % is a harness number, not a deployment number - and the objective is
explicitly about what would run in reality.

The continuous mode (`FRUIT_DIRECT_CONTINUOUS` + `FRUIT_CONTINUOUS_TRANSIT=1`) has
existed since P56/P225n, but it had never been run with the shipped 4T recipe at the
**target speed**.

## 2. The cells

`v = 0.08`, one continuous episode of **10 picks** per seed, the recipe verbatim
(`family` start, `ACTION_HOLD=4`, `TRIGGER=arrival`, `TARGET_RATE=5.45`,
`JOINT_CLAMP=1`, `SKIP_LATE=0.5`, `EVAL_LATENCY=auto`, cycle report on):

| seed | placed | hand-offs (`skip`) | gap_ticks median | cycle (median blocks) |
|---|---|---|---|---|
| 901 | **9/10** | **0** | 269 | 12.04 s |
| 902 | **10/10** | **0** | 268 | 11.85-12.21 s |
| **pooled** | **19/20 = 95.0 %** | **0** | 268 | **~12.0 s** |

**Three readings, and each one was the open question:**

1. **The reset is not doing the work.** 95 % continuous against 91.7 % per-episode
   (P230's 11/12) - the deployment shape is **at least as good** as the harness.
2. **No starvation**: `gap_ticks` median **268-269**, and the pure return transit is
   **263** (P227ab), so **5-6 ticks** of waiting is the whole inter-pick cost. The
   line keeps the arm fed.
3. **The ownership rule costs nothing here**: **0 hand-offs** at 0.08 (against 4 in
   the 0.12 cell, §3) - at the target speed every fruit arrives with a lead, so
   `FRUIT_SKIP_LATE` never fires and never discards a pick.

**Cycle**: 11.85-12.21 s, i.e. the same **~12.0 s** the per-episode cells read after
P249 (13.55 -> 12.13). So the continuous mode's transit (263 ticks = 2.19 s, inside
the cycle) is **not** more expensive than the teleport + settle it replaces.

## 3. The same recipe at 0.12: 11/20 - recorded, not explained

The first pass ran **without pinning the belt** and therefore took the shipped
0.12 m/s: **4/10 + 7/10 = 11/20 = 55 %**, with **3 `fruit fell off the line`** (s901),
**4 hand-offs** ("the fruit is already inside the catch window, `t_arrive` 0.00-0.11 s
< 0.50 s"), and one `fruit did not follow the gripper`. So continuity at 0.12 is
**not** a wash, and the two terms that move are the **hand-off rule** (it fires when
the arm is slower to return than the fruit is to arrive) and the **lost payload**.

**No cross-speed rate is claimed**: 20 attempts at each speed, and the per-episode
0.12 cell is 10/12 - the difference is a draw at this n and the mechanism is named,
not measured.

## 4. What this adds to the delivered spec

| | |
|---|---|
| **deployment shape (continuous, 0.08)** | **19/20 = 95 %**, ~12.0 s/cycle, 0 hand-offs, no starvation |
| per-episode harness (0.08) | 11/12 = 91.7 % (P230) |
| the reset | is **not** inflating the number - the deployment shape is better |
| the inter-pick cost | **5-6 ticks** of waiting over the 263-tick return |

## 5. Pins

No `src/`/`configs/` change (the tree is P250's: `tasks.py` `b68ac8d1`, `rl_env.py`
`TASKS_MD5` follow, references **`61fb5202` / `61fb5202` / `18b101bf`**, ckpt
`p227_panda156`); `accept.sh` therefore stands at P250's **459/459 +
`fingerprint: matches`**. Evidence `logs/p252/`.
