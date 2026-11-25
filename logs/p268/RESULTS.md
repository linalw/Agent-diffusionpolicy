# P268 results: the force exit cannot see the stall - **there is no contact** - and the 0.12 acquisition arc closes

**2026-11-25, `logs/p268/`.** One default-off force exit, PREREG pinned first, two cells. **P1
fails**, and the way it fails **closes the arc**: the true stall is a **free-space chase**.

---

## 1. The build and the cells

`FRUIT_CATCH_FORCE_EXIT=<N>` (default 0 = off; with the knob off not even the tactile read
exists): break the catch-up when **the pad force stays >= N for 30 ticks** *and* the residual
is no better than it was 30 ticks ago - "pushing, not closing".

0.12, `FRUIT_TRACK_DIAG=1`, 20 picks x 2 seeds per arm:

| arm | placed | catches | `>= 100` ticks | **true stalls** | cycle |
|---|---|---|---|---|---|
| C (shipped, from P266) | 24/40 | 34 | 11 | **10 (29 %)** | 9.65 s |
| T (`FORCE_EXIT=2`) | 30/40 | 38 | 9 | **8 (21 %)** | 9.57 s |

## 2. P1 fails, and the way it fails is the finding

The registered bar was **<= 5/34** true stalls (or the long rows halving). T reads **8/38**:
**2 of the 10 stalls were cut, 8 were not.**

**The exit needs 30 sustained ticks of >= 2 N pad force.** In a chase the pads sit **open at
`gap_open` (~98 mm)** behind a fruit 47-55 mm ahead of them: for most of those rows the pads
**never touch the fruit at all**. So there is no force to detect, no "pushing", and the
intervention has nothing to act on.

**That is the mechanism, stated for the record: the true stall is a *free-space chase*.** The
pads are not shoving a fruit they are in contact with - they are simply too far behind and
too slow. Which is why:

* a **clock** fails (P266: it cut chases that were converging, because convergence and a
  stall look identical on the *residual's slope* at these speeds);
* a **tolerance** moves the class but crosses a measured boundary (P267: 29 % -> 8 %, but 1 mm
  from P48's 6 mm and unpriced at the required power);
* a **force** criterion cannot see it (**this phase**: only 2 of 10 stalls ever had the
  contact the criterion needs).

## 3. The falsifier fired, and the arc closes as the PREREG said it would

The PREREG's falsifier for P1 was: *"the force is not the discriminator either, and the 0.12
acquisition class closes as **hardware** (the record's `SIM_LIMIT.md` list)"*. It fired.

**The 0.12 acquisition arc, in one table:**

| lever | measured | verdict |
|---|---|---|
| the catch-up's clock (P266) | true stalls 10 -> 3, **but it truncated conversions** | closed |
| the exit tolerance 6 -> 7 mm (P267) | true stalls 29 % -> 8 %, count +8 (a branch) | **a candidate**, unpriced at power; crosses P48's boundary |
| the pad force (P268) | 29 % -> 21 %; **8 of 10 stalls have no contact** | **closed - nothing to detect** |

**And the only software lever the record leaves is the arrival side** - `past_aim` vs upstream,
P109's window - which is **narrow** and whose far end is the **bistable runaway** (5 of 79
attempts, the placed count at 4 of 4 seeds). **Beyond that it is the y-axis** (a faster,
hardware/controller question) or the grasp itself (`logs/p42/SIM_LIMIT.md`).

**So the 0.12 step stands where P264/P267 left it**: **72.5-85 %** across draws with **two
classes** - the grip/hold class (hardware) and this free-space chase (arrival side or axis) -
and the cycle work does not touch either.

## 4. No-harm

The knob is default-off, the tactile read is inside the gate, and the exit adds no `notes`
entry: `scripts/accept.sh` is **`fingerprint: matches configs/motion_reference.json`** with its
**459 `[fruit]` lines 459/459 identical** to `logs/p227/accept_final.log`;
`scripts/selfcheck.sh` **PASS (0 failures, 1 skipped)** with the new `P268 catch force exit`
leg.

## 5. Pins

`tasks.py` **`141cd178`** (the gated exit), `rl_env.py` (`TASKS_MD5` follow),
`scripts/selfcheck.sh`, `logs/p268/PREREG.md`; references **`61fb5202` / `61fb5202` /
`18b101bf`** untouched; ckpt `p227_panda156`. Evidence `logs/p268/`.
