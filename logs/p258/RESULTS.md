# P258 results: the continuous lane did **two clearance motions per pick** - removing one is **-0.43 s at 60/60**

**2026-11-25, `logs/p258/`.** One scoped change: in a continuous episode the release's
60-tick retreat/settle is skipped, because the return's own `_lift_clear` raises the hand
anyway. **Measured, then adopted for the continuous lane only.**

---

## 1. The defect, stated exactly

A lowered place ends with its pads near the belt, so the release block runs a **60-tick
min-jerk retreat of 8 cm** (`FRUIT_PLACE_LOW_RETREAT`) to clear before the next cycle -
`FRUIT_RELEASE_RETREAT=0` only swaps it for the plain 60-tick settle, **the same 60
ticks**. In a **continuous** episode the next thing that happens is
`_continuous_return`, which starts with `_catch_up_drive` and then **`_lift_clear` to
`belt_top + 0.30`** - the very clearance the retreat had just bought.

So the lane did **two clearance motions per pick**, and the second made the first
redundant.

## 2. The build (scoped, caller-owned)

`task.skip_release_settle` (default `False`) with the env setting it only when
`_continuous_picks` is non-zero; `FRUIT_CONTINUOUS_SKIP_SETTLE` (default **on** since
this phase, `=0` restores). The branch sits **before** the retreat and the plain settle,
and the env applies it **after** `PickAndPlaceTask(...)` - P249's defect class, pinned by
the same leg (`P258 skip release settle`: the default, the branch order, the continuous
scope, and the construction order).

**Scope by construction**: the scripted single arm and the two-line never set the
attribute, so their streams cannot move - proved below.

## 3. The cells (0.08, 20 picks per cell, one continuous episode)

| cell | placed | attempt `total` | `return` block |
|---|---|---|---|
| control (P257, seed 905) | **20/20** | **11.91 s** | **0.50 s** |
| skip-settle, seed 905 | **20/20** | **11.43 s** | **0.00 s** |
| skip-settle, seed 906 | **20/20** | **11.49 s** | **0.00 s** |

**Every other block is unchanged to the hundredth** (place 3.48, release 2.16, grip 1.58,
close 1.10, seat 0.17, lift 1.25, descent 1.19-1.25) - the delta is **exactly** the
`return` block, which is what a correct surgical change looks like.

**Quality**: **60/60 picks placed** across the three cells. And it **cannot** be a
quality trade by construction: the payload is released *before* the settle, so the
removed motion only moves an **open hand**; the landing is decided at the release.

## 4. What it is worth

`14.08 -> 13.60 s/pick` (**-3.4 %**), i.e. **4.26 -> 4.41 picks/min** at **98.6 %**
(the 0.08 deployment numbers of P257 unchanged). At the 0.12 cell the same block exists,
so the saving transfers; it is not measured at 0.12 here.

## 5. No-harm

`scripts/accept.sh` is **`fingerprint: matches configs/motion_reference.json`** and its
**459 `[fruit]` lines are 459/459 identical** to `logs/p227/accept_final.log` (the
scripted acceptance is a per-episode cell, so it never sets the attribute);
`scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new `P258 skip release
settle` leg.

## 6. Pins

`tasks.py` **`c470cb18`** (the caller-owned flag + the branch), `rl_env.py` (the
continuous-only scope, the strict parsing, the post-construction apply), `rl_env.py`
`TASKS_MD5` follow, `scripts/selfcheck.sh`; references **`61fb5202` / `61fb5202` /
`18b101bf`** untouched; ckpt `p227_panda156`. Evidence `logs/p258/`.
