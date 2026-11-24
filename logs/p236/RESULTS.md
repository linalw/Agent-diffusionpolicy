# P236 results: the direct lane now has a block report - and it prices a block the record never saw

**2026-11-24, `logs/p236/`.** The gap P235 named, closed. One default-off
instrument path (`[cycle]` on the direct entry); **no behaviour change**.

---

## 1. What was missing and what was done

P235 could not read a place-speed cell because `FRUIT_CYCLE_REPORT=1` printed
**nothing** on the direct single-arm lane. The cause is structural:
`_cycle_begin`/`_cycle_mark` live in `_grasp_carry_place_impl` (the marks fire),
but `_cycle_report` is only called by **`note_result`** - which the scripted driver
runs and the direct entry (`grasp_carry_place`) never does. So the marks were
recorded into `None` and reported by nobody.

The fix is an **ownership test**: `grasp_carry_place` begins a cycle only when the
report is enabled and no cycle is open (`_cycle_marks is not None and not
_cycle_marks`), and reports it in its `finally`. A scripted `_run_impl` has already
begun one, so its path is untouched; `note_result` keeps its own report. Off
(`_cycle_marks is None`) is a no-op.

## 2. The decomposition at 0.08 (6 placed attempts, both seeds)

| attempt | descent | **close** | grip | lift | **place** | release | return | total |
|---|---|---|---|---|---|---|---|---|
| s901 e0 | 2.12 | **2.77** | 1.57 | 1.25 | 3.47 | 2.41 | 0.50 | **14.10** |
| s901 e1 | 1.31 | **2.77** | 1.57 | 1.20 | 3.47 | 2.15 | 0.50 | **12.98** |
| s901 e2 | 2.12 | **2.77** | 1.59 | 1.18 | 3.47 | 2.16 | 0.50 | **13.79** |
| s902 e0 | 1.36 | 1.27 | 1.58 | 1.26 | 3.48 | 2.28 | 0.50 | **11.73** |
| s902 e1 | 1.57 | **2.77** | 1.58 | 1.19 | 3.48 | 2.16 | 0.50 | **13.25** |
| s902 e2 | 0.98 | **2.77** | 1.58 | 1.89 | 3.51 | 2.14 | 0.50 | **13.37** |

**`close` is 2.77 s on five of six placed attempts** (one at 1.27) - the
**second-largest block**, and the only one that is *constant to the hundredth*.
`place` is 3.47-3.51 s, also constant. The rest move with the fruit.

## 3. Why this matters: the record's audit never saw this block

P91's `[cycle]` audit - the one that priced every "speedable" block - read the
**two-line** cell, where `close` is **1.36 s**. **On the direct single-arm lane it
is 2.77 s, twice that**, and it is the *fixed* part of the cycle: the same value on
a lychee and a pear, at both seeds. The block covers the coherent track, the axis
servo and the close attempts (`_close_attempt` retries), so a 2.77 s figure is
consistent with one close ramp plus one retry.

**So the single-arm lane's grasp establishment is ~4.3 s (`close` 2.77 + `grip`
1.57) - 30 % of the attempt - and no record entry has ever priced it.**

## 4. What the numbers do and do not say

* `release` reads 2.14-2.41 s, but the marks bound **phases, not profile cells**:
  this segment includes the post-release settle (the 0.5 s `on_output_belt`
  sample P142 introduced) and the retreat. **It is not comparable to P86's
  `release=` cell** (2.35 -> 1.63 s) and must not be quoted as "the trim is off".
* `descent` 0.98-2.12 s includes the **arrival wait** (P91's audit: the block is
  `lead/speed - margin` and cannot be shortened by a faster leg).
* `grip` 1.57 s is the probe/validation ramp plus the mode mix (P91: clean 210
  ticks, and the retries cost more).
* `place` 3.47 s is the **transit** (the joint blend to `bin{i}_above` + the
  Cartesian run) - the block P227r's cell moved and P235 could not see.

## 5. Next lever, now measurable

The direct lane's cycle at 0.08 is **~13.3 s** decomposed as
**place 3.48 + close 2.77 + release 2.2 + grip 1.57 + lift 1.2 + descent 1.5 +
return 0.5**. The two constants (place, close) are 6.2 s of it, and **both are now
readable**, which was the point of the phase. The registered next cell would be the
**close block**: it is constant, it is large, and its structure (one ramp + one
retry) is visible in `_close_attempt`.

## 6. Pins

`tasks.py` **`a8ca62cf`** (the ownership test, the begin/report), `rl_env.py`
`TASKS_MD5` follow, `scripts/selfcheck.sh` (leg `P236 direct cycle report`: the
ownership test, begin-before-impl, report-in-finally, and `note_result`'s report
untouched); references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
checkpoint `p227_panda156` used as-is. Evidence
`logs/p236/{smoke/, blocks/}`.
