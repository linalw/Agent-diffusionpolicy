# P75 method — the place leg's first ticks, at 1-tick resolution

**Diagnostic-only phase.** One new default-off trace, two direct cells, no
adoption, no default change, no commit. The question is the one P73 and P74 left
open: **what exactly happens in the first ~40 ticks of the left's place leg,
where the payload leaves the pinch?**

Registration written **before any simulator run of this phase** (its md5 is
recorded in `logs/p75/PREREG.md5` and in the batch header, so the classification
rule below cannot be chosen after seeing the rows).

* tree at registration: `src/fruit_sorting/tasks.py` **`303d025d`**,
  `src/fruit_sorting/rl_env.py` (the metadata-only `TASKS_MD5` follow),
  `scripts/241_p75_place_trace_selftest.py`, `scripts/242_p75_classify.py`,
  `scripts/selfcheck.sh` (the `P75 place-onset trace` leg)
* checkpoint `moe_v13s` **`61da390a`**, `configs/*` **untouched**
  (`motion_reference.json` `8952c320`, `..._twoline.json` `eb697f23`)
* the measured cell is the P66-phase-3 / P71-phase-2 / P73 / P74 cell **verbatim**

---

## 1. Why new instrumentation is needed at all (what is already printed)

The existing carry instrumentation is rich, and the question is one of
**resolution**, not of a missing data source. What a shipped `FRUIT_CARRY_DIAG=1`
log already carries per `place*` leg:

| row | what it gives | what it cannot give |
|---|---|---|
| `[carry] … place0:` | `onset_row` (first tick `clean_slip > 2 mm`), `force@onset`, `sep@onset`, `contacts@onset`, `loss_row` (first tick `contacts == 0`), `sep@loss`, `sep_end`, `clean_slip_max`, `slip_xyz`, `in-hand_vmax`, `q_margin`, `q_step_max`, `res_end` | **the `sep`/force at the leg's *start***, so "did the pads close *before* the payload moved?" is not answerable - only "what was `sep` at the 2 mm crossing"; and **no per-tick ordering** of `sep`/force vs displacement |
| `[seat] …` | 5 samples per grip (`fracs`) of the pads-vs-fruit seat | 5 samples, and it stops before the place leg |
| `[diag] carry-assist` | the first **3** ticks of a carry leg: `cmd_centre`, `offset_tool`, `jaw_target`, `jaw`, `coherent`, `hand_is_jaw` | only 3 ticks, only the *non-coherent* branch, no payload/fruit term, no `sep`, no force |
| `[attitude]` | the leg-end tilt | leg-end only (P73: saturated by the place pose) |
| `[motion] carry` | `|v|cmd`/`|a|cmd` max, `slip_max` (frame-contaminated), `in-hand |v|max` | leg extremes, not a time series |

So the two facts the phase needs are **missing by construction**, not merely
coarse: the leg-start `sep`/force (the reference a "collapse" is measured
against) and the tick-by-tick **order** of the three candidate symptoms.

## 2. The instrument

`FRUIT_PLACE_ONSET_TRACE=<ticks>` (`src/fruit_sorting/tasks.py`, **0 = off =
the shipped path**; recommend and used here: **60**). One row per tick for the
first `<ticks>` ticks of every `place*` leg, printed **post-step**, inside the
existing W8-B carry block:

```
[fruit] [place-trace] left place0 t=7 |d|=0.6mm d=(+0.1,-0.2,+0.6)mm
        sep=68.2mm gap=66.8mm f=(4.21,4.19)N n=1 tcp_err=12.3mm
        v_cmd=0.343 v_ach=0.121 q_margin=0.031@j3
```

| field | meaning | source |
|---|---|---|
| `t` | tick index from the leg's first tick | loop index |
| `\|d\|`, `d=(x,y,z)` | the payload's displacement from the leg's reference in the **hand frame** (`rot_now.T @ (fruit - pads) - ref`, the `clean_slip` expression), norm and **components** separately - `z` is the **tool/finger axis** (P61's escape axis), `y` the jaw-opening axis | `rot_now`, `fruit`, `pads` - the block's own reads |
| `sep` | the **measured** pad separation | `arm.jaw_separation()` (reporting reader; the same one `sep_end`/`sep@loss` take) |
| `gap` | the **commanded** gap this tick (after the force servo / relief) | local `gap_command` |
| `f=(f0,f1)`, `n` | the two tactile faces and the contact count | one `tactile.read()` per traced tick |
| `tcp_err` | commanded vs achieved TCP position error (`res_end`'s quantity, per tick) | `_tcp_pos` and `_tcp_tgt_issued` - the P66 block's own pair |
| `v_cmd`, `v_ach` | the profile's speed at this tick, and the achieved TCP speed (finite difference of two post-step `tcp_pose()` reads) | `velocities[i]`, `_tcp_pos` |
| `q_margin=…@jN` | **this tick's** smallest joint-limit margin | `_marg` - the P65 block's own read |

**No articulation read is added.** `rot_now`, `pads`, `_tcp_pos`, `_marg` and
`gap_command` are all produced by the block already; the two additions are
`jaw_separation()` (two finger-prim world poses, which the loop's own pad-midpoint
call reads every tick anyway) and one tactile set - both `FRUIT_CARRY_DIAG`-class
reporting readers. The only new bookkeeping is the previous tick's TCP position.

**Cost and honesty.** This is a *diagnostic*: it arms the carry block and adds
two reads per traced tick, so **its run is allowed to differ from the shipped
one** and **no rate may be quoted from it** - only the per-tick mechanism. The
shipped path is byte-inert (one integer compare, `trace_ticks == 0`), proven by
`scratch/accept.sh`'s 346 `[fruit]` lines against `logs/p73/accept_noharm.log`.

## 3. The cell

Two direct cells, **seeds 77 and 101**, 15 picks, `moe_v13s` `61da390a`, the
P66-phase-3 / P71-phase-2 / P73 / P74 environment verbatim:

```
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
FRUIT_POLICY_TRIGGER=arrival FRUIT_POLICY_TRIGGER_LEAD=0.9 FRUIT_DYNAMIC_PICK=1
FRUIT_POLICY_SEED=11 FRUIT_BED_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_ATTITUDE=1
FRUIT_MOTION_REPORT=1 FRUIT_PLACE_ONSET_TRACE=60
```

One arm, no control: the shipped default with the trace **off** is the record
this phase's no-harm run compares against, and the diagnostic's own run is not a
comparison arm. Expect 4-6 left place-leg escapes across the two cells (P74's C
arm drew 3 in seed 77 and 2 in seed 101 at `clean_slip_max` 617-921 mm).

## 4. The classification rule (pinned)

Per escape, with `t` = ticks from the place leg's first tick and the leg-start
values taken at `t = 0`:

* `t_d` = first `t` with **`|d| >= 2.0 mm`** (the repo's own
  `FRUIT_CARRY_GUARD_TRIGGER`, i.e. the threshold the existing diag already calls
  "slipping");
* `t_sep` = first `t` with `sep <= sep_0 - 1.0 mm`; `t_f` = first `t` with
  `min(f0,f1) < 0.5 * max(f_min@0, 1 N)` **or** `n == 0`; `t_geom` = the earlier
  of the two;
* `t_err` = first `t` with `tcp_err >= median(tcp_err over the last third of the
  window) + 20 mm` (a transient **above the leg's own steady state**, so a leg
  that tracks with a large constant error is not a transient); `t_v` = first `t`
  with `|v_cmd - v_cmd(prev)| >= 0.10 m/s` **or** `v_ach >= 1.5*v_cmd + 0.05` (a
  speed discontinuity / an achieved speed the command does not ask for);
  `t_cmd` = the earlier of the two.

Then, **priority c -> a -> b** (a boundary step that precedes everything is the
cause the other two definitions would also accept as a predecessor):

1. **(c) command transient** if `t_cmd is not None and t_cmd <= t_d - 2`;
2. **(a) expulsion** if `t_geom is not None and t_geom <= t_d`;
3. **(b) slip at constant `sep`** otherwise (the displacement crosses with `sep`
   and the force still inside those bands; `t_geom` may still exist, later).

A leg whose `|d|` never reaches 2 mm inside the window is `none` (no escape read).
The rule and its arithmetic are pinned by `scripts/241_p75_place_trace_selftest.py`
(four synthetic cases plus the flat-error and same-tick controls) and executed by
`scripts/242_p75_classify.py`.

**What each class would imply**

* **(a) expulsion** - the pinch depth/force geometry is the object: the pads
  close *behind* a payload that is already past the lip, so the escape is
  decided at the lip, not by the slide. That is a grip-plane/standoff family, and
  it is the one family P42/P61/P69 measured closed by *geometry* - so (a) would
  re-open it with a new mechanism, not a new magnitude.
* **(b) slip at constant `sep`** - the pad material/geometry is the object, i.e.
  `logs/p42/SIM_LIMIT.md`'s closure stands unchanged and the only sanctioned
  levers remain a **new pad asset** or a **real-jaw clamp-force anchor**.
* **(c) command transient at the leg boundary** - a **profile-continuity lever
  exists**: the first ticks of the place leg would be the actuator, and a
  boundary blend / a start-from-rest constraint would be the fix. **That** is
  registrable as a next-phase candidate (its own PREREG, the standard N=3 seeds,
  the two references re-recorded if adopted); nothing is implemented in P75.

If the escapes split across classes, the phase reports the counts and the
residual mechanism rather than a single verdict.

---

## 5. AMENDMENT A1 (written after the smoke, before any measured cell)

One **smoke** run (`logs/p75/smoke.log`: 1 episode, seed 77, 15-pick cell's env,
`FRUIT_PLACE_ONSET_TRACE=60`) was spent to prove the row prints and parses. It is
**not a measured cell** (its own leg is clean, `clean_slip_max=0.0 mm`), and it
changed one clause of §4:

* **The `v_ach >= 1.5*v_cmd + 0.05` clause is withdrawn.** On a *clean* leg the
  achieved TCP speed reads **0.095-0.099 m/s for t=1..3 while `v_cmd` is
  0.000** (the arm closing the residual the previous leg left), so that clause
  fires on **every** leg and discriminates nothing. The boundary test is now
  `|Δv_cmd| >= 0.10 m/s` **or** the `tcp_err` clause; the achieved-side transient
  is `tcp_err`'s job, since `tcp_err` is the integral of exactly that gap.
* The smoke also fixes the **scale** of the leg-boundary transient for a clean
  leg, which the rule must not mistake for a cause: `tcp_err` starts at
  **19.4 mm** and decays monotonically to 6.7 mm by t=59 (the steady-state
  reference `err_ss` is ~5 mm, so `err_lim ≈ 25 mm` and tick 0 does not fire).
  A place leg therefore **always** begins with a ~7-20 mm commanded-vs-achieved
  deficit that it spends ~100 ticks removing - that is a property of the leg
  boundary, not of the escape, and it is the reason (c) needs a *larger or
  sharper* transient than the clean-leg one to own a leg.
* `q_margin` reads **0.000 @ j2** on the clean leg, i.e. the standing joint
  saturation P65 already measured on 86/86 legs; the field is reported but is
  not expected to discriminate (as recorded there).
* Leg-start geometry on the clean leg: `sep=70.8 mm` against `gap=60.1 mm`
  (**+10.7 mm pad shell**), `f=(4.88,5.12) N` two-sided, `n=2`, both constant to
  the print for 60 ticks - the "constant `sep`/force" reference (b) is measured
  against.

No other clause changed. The measured cells are seeds 77 and 101, launched after
this amendment.

