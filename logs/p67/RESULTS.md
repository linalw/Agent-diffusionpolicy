# P67 results — the place-leg **climb** re-shape of P66 phase 4's rail-crossing gate

Written by the P67 lane. Two cells, four runs, seed 77, `FRUIT_CARRY_DIAG=1`,
`FRUIT_LIFT_DZ=-0.08` in every arm (`logs/p67/run_p67.sh`,
`logs/p67/run_p67_pop.sh`, logs `logs/p67/{A,B,A2,B2}_77.log`, numbers
`logs/p67/p67_report.txt`, `python3 logs/p67/p67_report.py --check` -> PASS).

## Verdict

**The geometry works and the gate passes on the arm the lever exists for — the
climb clears the +33 mm floor — but the same 0.18 m raise costs the left its
payload on the larger fruit, so the pair is the form that clears the crossing and
is *not* shippable on its own.**

* **The crossing (`clr=`)** on the population cell's held left place legs
  (`FRUIT_SUPPLY_GRADES=A:0.96,B:0.02,C:0.02`, so every attempt is the left's):
  **+33 .. +54 mm, median +37, worst +33** (n = 5) against the control's
  **+3 .. +17, median +12, worst -1** on the 0.20 m rung — i.e. the measured rise
  is **+21 .. +30 mm** against the derived **+31.5 mm** (§2), and +33 is exactly
  the floor of record. **Gate (a) PASS.**
* **The attitude still holds.** The lift leg is untouched by this knob and reads
  `drift_end` **0.7 [0.6..5.0] deg** (control, n = 7) / **1.1 [0.6..1.2] deg**
  (climb, n = 8) — both inside the 0.20 m rung's own band (P66 phase 3: 0.7 deg
  median), and the transit's *end* attitude (`[attitude] tilt`) is unchanged
  (90.0-94.3 vs 86.1-90.3 on the clean legs).
* **The cost.** 3 of the 8 climbed left place legs lose the payload — and they are
  the larger fruit, with the slip onset at rows **113-152**, i.e. **at the climb's
  own exit** (the climb is 121 ticks): two same-instance pairs go from "in place,
  crossing +7 / +3" (control) to "gone, slip 0.92-1.00 m". The place leg runs with
  **no wrist hold** (`hold_drift=0.0deg(no-hold)`), which is exactly the window the
  losses sit in, so the named next cell is this pair **plus**
  `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S=1.0` (an existing knob; §6).
* **The ticks**: the left's place leg goes **391 -> 526 ticks (median), +136 =
  +1.13 s** (the climb segment alone is 121 ticks; the transit itself shortens
  because it starts 0.18 m higher — quote the net).

So: **`FRUIT_LIFT_DZ=-0.08 FRUIT_LIFT_CLIMB=0.18` is the exact pair that clears
the crossing** (worst held leg +33 mm, 5/8 legs readable) **and it is not
certifiable as a shipping default until the carry cost is fixed** — the required
dose is set from below by the floor (0.16 m is level and lands at the control's
own +30, 3 mm short; §2), and 0.18 m is where the left's grip on the pear/apple
class gives way.

> **Provenance note.** Two in-flight commits were made by the parent session
> *while this lane was still running*: `f0216bb` (the knob; its subject says "does
> not yet recover the rail crossing", which reflects the **registered cell only**,
> where the left had no read) and `41b7cf8` (evidence as of the registered cell +
> the partial population control). **This file is the authority** for the read:
> after the population cell the crossing **does** clear the floor (+33..+54 mm) and
> the cost is the carry class (§5). `git diff HEAD -- src scripts` is empty, so the
> code those commits carry is the code measured here.

---

## 1. What was built, and where (and why there)

**`FRUIT_LIFT_CLIMB=<metres>`** — an opt-in vertical climb at the **start of the
place leg**: `direct` + **left** only, default **off**, `None` = **no arithmetic
at all** (not "a climb of zero"), the `FRUIT_LIFT_DZ` pattern end to end.

| layer | site | what it does |
|---|---|---|
| resolve | `rl_env.resolve_lift_climb(presentation, value)` | `None` for every presentation but `direct` and for an unset/empty value; strict parse (a non-number, a non-finite and **any value `<= 0`** raise — the off state is *unset*, never `0`); returns `{"left": climb}` |
| thread | `SortingRLEnv.__init__` -> `PickAndPlaceTask(lift_climb=...)` | one resolve, one caller-owned kwarg (the P64/P66 pattern: no caller mutates the process environment to move a trajectory) |
| scope | `tasks.lift_climb_for(offsets, side, name)` | pure; `None` unless the leg is a **`place*`** leg and the side is named — a `grasp_lift` leg's end pose (P66's own lever) is structurally out of reach |
| build | `tasks.lift_climb_commands(start, climb, limits)` | pure; the climb as absolute pad-centre commands, a vertical `jerk_limited` segment whose **last sample is exactly `start + climb*z_hat`** |
| apply | `tasks._carry` | `transit_start = start` by default (`is`-identical, so the shipped command list is built by exactly the same expressions); an armed climb rebinds it to `start + climb*z`, builds the transit from there, and **prepends** the climb's commands |
| report | `[grasp] lift_climb:` row, manifest `lift_climb` block | the resolved climb, the scope, the two heights and the crossing the formula gives; absent when unset (there is no presentation default to report) |

**Why a prepended waypoint and not a first-segment z offset**: the waypoint keeps
the leg's **end pose** (`jaw_target`) untouched, so the release geometry,
`_place_low` and every downstream read are the shipped ones — the change is one
extra segment in front of an unchanged transit. A z offset on the first segment
would bend every intermediate sample *and* have to be unwound to keep the end
pose, i.e. two changes at once (against the P66/P44 one-variable rule), and it
would have no exact waypoint to assert. The climb is generated by the same
`jerk_limited` family, cone-limited along **+Z** (the direction the dynamic lift
uses), so `limited_by_cone` can only *tighten* the place profile and the segment
never asks for more than the transit it precedes; `jerk_limited` starts and ends
at rest, so there is no velocity step at the waypoint.

**Two honest boundary notes.** `_carry`'s pad-hand slip rebase
(`slip_enabled`) is refused when a climb is armed (the profile arrays describe the
transit only; the combination is already unreachable on the shipped hand, where
`hand_is_jaw` is True). And the climb is scoped to the place legs, not to the
lift, so a `grasp_lift` leg's `drift_end` is not even reachable by the knob.

## 2. The derivation of `climb = 0.18 m` (from the code's own construction)

The place leg is a straight line from the pads' position at the lift's end
(`belt_top + 0.28 + dz` = **1.370 m** at `dz = -0.08`) to `jaw_target("placeN")`
= `output_place_z + the hand's add` = **1.530 m**. The crossing of record is the
inner rail's centreline, `|y| = 0.4125 m`, against a place span of
`|y| = 0.50 m`, so **f = 0.825** and

```
z_crossing = transfer - (1 - f) * (transfer - lift_end - climb)
           = 1.530 - 0.175 * (1.530 - 1.370 - climb)
climb = 0   -> 1.502 m        (P66's L2 measured +5 mm there)
climb = 0.16-> 1.530 m        (level transit: exactly the shipped lift's own
                               crossing -> the control's +30, 3 mm SHORT)
```

The measured slope from P66's own pair (L2 `+5 mm` at z 1.502, control `+30 mm` at
1.530) is **0.89 mm of clearance per mm of z**, so `+33 mm` needs
`z = 1.502 + 28/0.89 = 1.5334 m` and therefore
`climb = (1.5334 - 1.502)/0.175 = 0.179 m` -> the cell's **0.18**.

`scripts/237_p67_climb_selftest.py` **re-derives** all of it offline (`f` from the
scene config, cross-checked against `tasks._output_rail_y`; the 0.175 leverage; the
0.16 "level" identity; and the 0.179 solve) and **fails if the number stops being
the solve** — 0.18 is the rounded-up solve, not a tuned value. The
`[grasp] lift_climb:` row prints the same arithmetic from the run's own numbers
(`-> z_crossing 1.5335 m (+31.5 mm vs no climb)`).

Note the shape this produces: the transit starts **20 mm above** the transfer and
descends onto it, so the binding read is the *centreline* crossing (a descending
leg's window is *looser* than its crossing, the mirror of P66's climbing leg where
the window bound). That is why the climb arm's `clr` and `clr_win` agree to 1 mm.

## 3. The cells, and the recorded deviation

**Registered cell** (`run_p67.sh`, the phase-3/P4 scenario verbatim): A = control
(`dz = -0.08`), B = A + `FRUIT_LIFT_CLIMB=0.18`, 15 picks each, same batch.
It **cannot answer gate (a)**: the direct env picks the arm from the fruit's grade
(grade A -> bin 0 -> left), and this branch drew only **two** left attempts — both
payloads left the hand inside the climb (`slip 970.7 / 958.6 mm`, `clr = n/a`, one
onset at row **71**, inside the 121-tick climb). Right arm: a clean no-op
(crossing **+44 -> +43**, window **+44 -> +43**, medians over 8 and 13 held legs),
which is the check that the tree and the instrument did not move.

**Population cell** (a **deviation**, `run_p67_pop.sh` + `logs/p67/pop_header.txt`):
the same A/B on a **grade-A-only supply**
(`FRUIT_SUPPLY_GRADES=A:0.96,B:0.02,C:0.02` -> 16/0/0 by largest remainder), so
every attempt is the left's place leg. The crossing is a *geometric* quantity of
that leg (bin 0, drop y = +0.50), so this populates the arm without touching the
path under test; everything else (seed, checkpoint, instruments, `FRUIT_LIFT_DZ`)
is the registered cell's. Two things to state: `FRUIT_SUPPLY_GRADES` needs all
three keys (`_mix_env`; the first smoke's `A:1` was **refused**, logged, and fell
back to the mixed mix), and the control arm was **stopped at 8 of its 15 episodes**
(the all-A supply means every attempt is the left, the slow arm: ~3.4 min/episode)
so the treatment was run at the same 8 picks. Both arms therefore have **8
episodes / 7 and 8 left place legs**; the truncation costs the control nothing it
needs (the read counts legs, not episodes).

## 4. The read

### The crossing on the left's place legs (the population cell)

| arm | legs | in place (slip <= 50 mm) | **crossing** | **window min** | verdict |
|---|---|---|---|---|---|
| **A2** control (0.20) | 7 | 4 | **+12 [+3..+17]** | **+8 [-1..+13]** | **MARGINAL** (worst **-1 mm**) |
| **B2** climb (0.20 + 0.18) | 8 | 5 | **+37 [+33..+54]** | **+37 [+33..+53]** | **CLEAR** (worst **+33 mm**) |

Per leg (B2, in place): lychee **+51/+50**, peach **+37/+37**, peach **+33/+33**,
strawberry **+54/+53**, orange **+36/+35**. Control (A2, in place): strawberry
**+17/+12**, strawberry **+16/+13**, pear **+7/+4**, apple **+3/-1**. The strict
P66 convention (in place **and** tactile contact at the crossing tick) reads the
same on B2 (5 legs) and 2 legs on A2 (+16/+12, +17/+13) — the same band.

Also in A2: one leg slid 94.3 mm and read `+8 / -21` (excluded as not in place),
one ended **short of the rail** (slip 1.2 mm, no crossing — P4's known
short-leg class) and one was lost and recycled mid-leg (a `clean_slip` respawn
artefact of 114.7 m); B2 has two respawn artefacts of the same kind (0.9-1.0 m on
the two real escapes, 87.8 m on one). **Read a 5-6 figure `clean_slip` as "gone",
and a 10^4-10^5 one as "recycled"** — neither is a millimetre measurement.

### The attitude (the mediator) and the transit's end state

| arm | left `grasp_lift` `drift_end` | `[attitude] tilt` on the held place legs |
|---|---|---|
| A2 control | **0.7 [0.6..5.0] deg** (n = 7) | 86.1, 90.3 (held), 84.9, 90.4 |
| B2 climb | **1.1 [0.6..1.2] deg** (n = 8) | 90.8, 92.3, 94.3, 90.0, 90.4 |
| registered A / B | 0.6 [0.6..1.1] (n=4) / 0.9 [0.6..1.2] (n=2) | 89.8-92.3 |

**The attitude holds**: both arms sit in the 0.20 m rung's band (P66 phase 3's
`drift_end` median 0.7 deg, range 0.6-24.9), and the place legs' end attitude is
unchanged. `drift_end` is `n/a` on place legs by construction (there is no hold to
compare against) — the `[attitude]` tilt is the transit's *end* read, not the
mediator, and it is reported as such.

### The class and the count

Both arms place the same way (`placed` 11/15 + 13/15 registered; 5/8 + 5/8
population). **Do not read those as a rate**: the direct loop conditions on
rendered frames and the two arms are different branches from episode 0 (the
control's ep0 pear places, the climb's is lost, so the fruit sequence diverges
immediately). Only the per-leg geometry and the per-leg classes are comparable.

### The ticks

| cell | left place legs, median ticks | net |
|---|---|---|
| registered | A 402 (n=4) -> B 518 (n=2) | **+116 ticks = +0.97 s** |
| population | A2 391 (n=7) -> B2 526 (n=8) | **+136 ticks = +1.13 s** |

The climb segment alone is **121 ticks** at the place profile; the transit gets
shorter (it starts 0.18 m higher, so ~5-20 ticks less), which is why the net is
+100..+136 rather than +121. The untouched right arm's two place-leg columns
(+400 vs +355) show the same-configuration branch spread is ~+/-45 ticks, so quote
the net as **"+1.0 to +1.1 s per left place leg"** (7 % of a 15 s attempt), with
the 121-tick segment as the hard upper bound.

## 5. The carry cost — the finding that decides the verdict

The climb arm's losses are not the left's *usual* place-leg loss. Per leg, with
the climb window = rows 0..120:

| arm | ep | fruit | slip | onset | loss | crossing |
|---|---|---|---|---|---|---|
| A2 (control) | 0 | pear | 21.3 mm | 312 | 319 | **+7** |
| A2 | 3 | apple | 15.9 mm | 281 | 292 | **+3** |
| B2 (climb) | 0 | pear | **997.5 mm** | **152** | 266 | n/a |
| B2 | 3 | apple | **916.4 mm** | **113 (IN the climb)** | 210 | n/a |
| B2 | 7 | pear | 87.8 m (recycled) | **142** | 260 | n/a |
| registered B | 0 | pear | 970.7 mm | **150** | 260 | n/a |
| registered B | 3 | orange | 958.6 mm | **71 (IN the climb)** | 117 | n/a |

* **Two same-instance pairs** (same seed -> same fruit at the same episode index
  before the branch diverges): the **pear** ep0 and the **apple** ep3 are *in
  place* through the control's whole transit (slip 21.3 / 15.9 mm, crossing
  +7 / +3) and **gone** with the climb (997 / 916 mm). Same fruit, same station,
  same lift, same target — the climb is the only difference.
* **The onset clusters at the climb's exit** (rows 113-152 against a 121-tick
  climb; one at 71, i.e. inside it) in **all five** climb-arm losses, versus
  252-312 in the control — i.e. late in the transit, after the crossing. In the
  control the same rows are just the start of the diagonal transit.
* **It is the marginal-grip class, not a new one**: `contacts@onset` 1,
  `force@onset` 9.7-10.8 N (the pinch is at its cap), `sep@onset` 73-81 mm, then
  `force_min 0.00 N` — W8-B's loaded slide (`logs/p42/SIM_LIMIT.md`). What the
  climb changes is *when* it starts.
* **The small fruit survives**: the 3.4 cm lychee reads **+51/+50 mm** (and also
  did in the separate 2-pick smoke, `+51/+50`), so the mechanism is a *survivability*
  boundary, not a broken path.
* **Across the batch runs** (a per-leg class read, not a rate): the climb arm's
  left place legs lose the payload on **5 of 10** (registered B 2/2, B2 3/8), the
  control on **2 of 11** (A 1/4, A2 1/7 — one 830 mm slide and one recycled leg;
  the control's other "escapes" are contact losses with the payload still in place
  at 13-22 mm). The single-pick smokes add 3 pear losses and 1 held lychee at
  +51 mm. That is the cost side of the verdict, and it is a **class** statement on
  n = 2 matched pairs plus the onset clustering, not a measured rate.

**Why a vertical raise at the place leg's start is the worst place for it**: this
leg runs **without a wrist hold** — `_carry` clears `arm.hold_quaternion` for
every leg but `grasp_lift` (the `[carry]` rows print `hold_drift=0.0deg(no-hold)`),
so the position-only IK re-finds the wrist *during* the climb, and the record
already knows this boundary tips a marginal grip out ("the A2 peach is lost in the
first place ticks", `logs/dyn_v3c`). The shipped `FRUIT_LIFT_DZ=+0.08` performs
the *same* vertical raise in the **lift** leg, where the hold is still installed
and the left carries fine (the control arm's place legs) — which is the strongest
argument that the height is not the problem and the *free-wrist window* is.

## 6. What the arithmetic needs (the named next cell)

* **The pair that clears the crossing is exact**: `FRUIT_LIFT_DZ=-0.08
  FRUIT_LIFT_CLIMB=0.18`. It is the only dose that clears: `0.16` makes the
  transit level and lands at the control's own **+30** (3 mm short), `0.14` gives
  ~+29, and anything larger spends more free-wrist time for 0.175 mm per mm.
* **The next cell is that pair plus `FRUIT_DYNAMIC_PLACE_WRIST_HOLD_S=1.0`** —
  the shipped knob that holds the attitude the leg starts with for N ticks
  (121 ticks = 1.008 s covers the climb) and then releases. If the free-wrist
  window is the mechanism (§5), this is the cheapest test of it: no new code, one
  env var, same instruments. **Not run here** — it is a different lever and its
  own cell.
* **The alternatives P66 named are unchanged and now better priced**: the rail
  (`FRUIT_OUTPUT_RAILS=outer`, +35 mm by construction, against the catch-ledge
  trade), and a **transfer-height** raise, which is 1:1 with the crossing *and* is
  re-descended by `_place_low` before the jaws open, so it may not move the
  release at all — but the transfer pose is where the left's TCP already reads
  `res_end ~30 mm` short, so its reach has to be measured before it is believed.
* **Do not try a rung instead**: 0.24 buys +7 mm at the crossing (P66 phase 4 §4).

## 7. No-harm

* `scripts/selfcheck.sh`: **PASS, 0 failures** (`logs/selfcheck.log`), with the new
  `P67 place-leg climb` leg (`scripts/237_p67_climb_selftest.py`) registered.
* `scripts/96_motion_check.py`: **all motion checks passed**.
* `scripts/accept.sh` (scripted, `SKIP_SELFCHECK=1`): **6/10 +
  `fingerprint: matches configs/motion_reference.json`**, its **377/377
  `[fruit]` lines byte-identical** to `logs/p66/p2/accept_noharm.log` (and to
  `logs/p65/accept_noharm_final.log`) - i.e. the scripted line is untouched, which
  is what "`None` builds the shipped expression" has to mean. The FAIL is the
  rate floor only (6/10 vs 0.75), the tree's recorded pear-on branch since P32
  phase B. Gate output: `logs/p67/pop_batch.out` (tail), log `logs/accept.log`.
* No `configs/` edit, no shipped default moved, no commit. `TASKS_MD5` is the
  metadata-only follow `1296bd44 -> e5168578` (the P43/P62/P64/P65/P66 precedent).
* The hybrid canary is unaffected: `60_eval_policy.py` never constructs
  `SortingRLEnv`, and the climb resolves to `None` for every presentation but
  `direct`.

## 8. Pins

`tasks.py` **`e5168578633bf094e86042d5ec54ce0f`** (`lift_climb_for` +
`lift_climb_commands` + the `_carry` climb + the `lift_climb` kwarg),
`rl_env.py` **`d88c3729749bc471bbd769c393701228`** (`resolve_lift_climb`, the
kwarg, the `[grasp] lift_climb:` row, the manifest block, `TASKS_MD5`),
`scripts/237_p67_climb_selftest.py` **`1016818702bdd9af922fc061cff0802a`**,
`scripts/selfcheck.sh` **`7dca2c7d38825d6c00c90bf915c50a97`**,
`configs/motion_reference.json` **`8a399626`** and
`configs/motion_reference_twoline.json` **`2246f83c`** both untouched, checkpoint
`moe_v13s` **`61da390a`**, HEAD **`540ae99`** at the batch.

Evidence: `logs/p67/{run_p67.sh,run_p67_pop.sh,header.txt,pop_header.txt}`,
`logs/p67/{A,B,A2,B2}_77.log`, `logs/p67/p67_report.{py,txt}`, the fixture smokes
`logs/p67/{smoke,smoke_pop,smoke_pop2}.log`, `logs/p67/pop_batch.out` (the batch
timeline + the acceptance gate output), `logs/p67/accept_noharm_gate.txt` (the
gate's own tail: `success: 6/10`, `fingerprint: matches`), `logs/selfcheck.log`,
`logs/accept.log`; rollouts under `logs/p67/{rollouts,rollouts_pop,smoke_rollouts}`.
