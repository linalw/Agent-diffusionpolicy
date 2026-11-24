# P230 results: the close grips at 0.24 after all - the loss is after it

**2026-11-24, `logs/p230/`.** 0.08 baseline + a close-phase trace. **No
`configs/` change, nothing adopted.** The only `src/` change is a default-off
diagnostic (`FRUIT_CLOSE_TRACE`, added this phase).

---

## 1. The objective's starting point: 0.08 m/s

| `v` | seed | placed | `t_arrive` at fire | `lead` | `dy` at fire |
|---|---|---|---|---|---|
| 0.08 | 901 | **5/6** | 1.68 s | 1.73 s | 0.134 m |
| 0.08 | 902 | **6/6** | 1.96 s | 2.05 s | 0.157 m |
| | | **11/12 = 91.7 %**, CI [65, 99] | 1.71 s | 1.83 s | 0.136 m |

One failure, the known grip key (`fruit did not follow the gripper`). This sits on
the same plateau as 0.06 / 0.12 / 0.18 (11 / 10 / 11 of 12) - the slow belt the
objective names as the starting point is **inside** the cell's envelope, not at
its edge.

## 2. The close-phase trace, and the two defects that made it necessary to run a control

`FRUIT_CLOSE_TRACE=1` (default off) prints one row per **close tick**, after the
physics step:

```
[close-trace] t=<s> step=<i> cmd=<mm> aim_minus_fruit=<mm> x_off=<mm> n=<contacts> f=<N>
```

`aim_minus_fruit` is `v x lead` at that tick - the close's lead read directly in
millimetres - and `n`/`f` are this pad's own load.

**It failed twice before it ran, and only the control cell caught it**: the first
version called `self._say` (that is the *env's* method; the task uses the
module-level `say`) and the second used `self._step` (also the env's). Both raised
**inside the close loop**, so the attempt died before any `[rl] episode` row.
At 0.24 that looks *exactly* like the known 0/3 - **the 0.12 control is what
proved the instrument was broken rather than the cell.** A mechanism cell without
a cell that is known to work cannot tell a broken instrument from a broken line.

## 3. The control (0.12): what a close that works looks like

| tick | `cmd` | `aim − fruit` | `n` | `f` |
|---|---|---|---|---|
| 0 | 90.0 mm | -21.7 mm | 0 | 0.00 N |
| 10 | 64.2 | -21.7 | 0 | 0.00 |
| **22** | **28.9** | -21.7 | **2** (first contact) | 8.46 |
| 40 | 25.8 | -28.9 | 2 | 8.43 |
| 83 | 25.8 | -37.6 | 2 | 8.45 |

Contact at **tick 22**, when the commanded span reaches the fruit's width; the
load holds at ~8.4 N to the end. `aim − fruit` is `-21.7 mm` at the start, which
is `0.12 m/s x 0.181 s` - the shipped `FRUIT_DYNAMIC_TRACK_LEAD = 0.18`.

## 4. At 0.24 all three closes grip

Same cell (`v=0.24`, `ext=0.10`), 3 episodes:

| close | `aim − fruit` (start → end) | `cmd` at the end | `n` at the end | `f` max | first contact |
|---|---|---|---|---|---|
| 0 (placed) | -43.2 → **-21.4** mm | 29.5 mm | **2** | 9.4 N | tick 24 |
| 1 (failed) | -43.2 → **-63.1** | 61.7 mm | **2** | 9.1 N | tick 50 |
| 2 (failed) | -43.2 → **-75.8** | 35.6 mm | **2** | 5.7 N | tick 48 |

**Every close ends loaded at 2 contacts and 5.7-9.4 N.** The two episodes that
finish `grasped=False` **were gripping the fruit when the close ended.**

## 5. Two of the phase's own hypotheses are falsified, and the fix they implied is not built

**(a) The aim-lead geometric criterion is wrong.** P229 predicted the failure from
`L - d/2 <= cmd/2` (`L = v x lead` = 43.2 mm, `d` = 40 mm, `cmd/2` = 13 mm ->
23.2 > 13 -> "no contact"). **Measured: contact at tick 24.** The model treats the
pads as fingertips meeting at `cmd`; the OpenArm's plates are **26-61 mm wide flat
faces**, so a fruit 43 mm behind the aim centre is still under the plate. The
criterion has to be stated on the plate's footprint, not the span.

**(b) "The pads close on air" is not the 0.24 mechanism.** P229's decisive-looking
row (`contacts@onset = 0`, `force@onset = 0.00 N`, `sep_end = 0.0 mm`) is measured
on the **lift** leg - by which time the payload is already gone. The close itself
grips. So the reading was right about the leg and wrong about the phase.

**Consequently the "shrink the close's lead as the pads close" lever
(`FRUIT_CLOSE_LEAD_CAP`) was not built**: its premise - a fruit left outside the
span - is false, and building it would have changed a mechanism that is working.

## 6. What the failure actually is, and the lever it implies

The payload is **held at 5.7-9.4 N when the close ends and is gone by the lift**.
That is the record's loaded-slide class (`logs/p42/SIM_LIMIT.md`: the pads hold and
the payload walks out along the tool axis), whose force / pad-face / friction /
seat levers are all measured out. What is **not** in that closed set is the
**relative velocity**: at 0.24 m/s the belt drags the payload twice as fast as at
0.12 while the hand is nearly stationary in y through the lift, and the drag is
the load the pinch has to resist.

**Registered for the next cell, not built**: `FRUIT_LIFT_TRACK_BELT` - translate
the hand **with the belt** through `grasp_lift` (add `v x t` to the lift's y
target), so the pads do not drag the payload at all. It is software only, it is
what a human does, it is inert at `v = 0`, and its prediction is specific: the
payload's `clean_slip` through the lift falls and `grasped` rises at 0.20-0.24
without touching the close.

## 7. Caveat on the traced cells

The trace adds **one tactile read per close tick**, which is exactly the kind of
per-tick work AGENTS section 2 says can move the branch: the untraced 0.24 cell
read **0/6** (`logs/p229/up10`, `up15`) and the traced cell read **1/3**. **No
rate is quoted from a traced cell**; the mechanism columns are the claim.

## 8. Pins

`tasks.py` **`1434f4b2`** (the `FRUIT_CLOSE_TRACE` knob and its row),
`rl_env.py` `TASKS_MD5` follow, `scripts/selfcheck.sh` (leg
`P230 close trace` - default off, the row's site after the step, its fields);
references **`61fb5202` / `61fb5202` / `18b101bf`** untouched; checkpoint
`p227_panda156` used as-is. Evidence `logs/p230/{PREREG.md, base08/, smoke2/,
ct024/}`.
