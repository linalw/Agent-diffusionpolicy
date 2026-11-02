# P102 method — the contact-patch statistic a vision tactile would give, and the lead-time census

**Instrument-only phase.** One default-off diagnostic (`FRUIT_TACTILE_PATCH`,
**0 = off**, the shipped path), one census script, no command change, no
`configs/` change, no `src/` control-path change. The endpoint is not a new
default — it is `docs/PLATFORM_SURVEY.md` §5.1's own **kill criterion** for
stage (i):

> **P1 (mechanism)**: slip onset is detectable **>= 10 ticks (83 ms)** before
> `clean_slip > 2 mm`, on **>= 70 %** of escapes. Below 50 % → the sensor is a
> labeller, go to P2.
> **Kill**: P2 fails at both seeds → tactile on a parallel jaw is a *labelling*
> channel on this cell.

The survey's hypothesis, stated as a mechanical claim: a **spatial** tactile
channel — the contact patch's centroid moving on the pad — leads the **force
collapse**, because a patch can slide while the normal force is still at its
static-friction level. The record says the 2-scalar channel cannot: "where force
collapses the payload is out within **0-3 ticks**" (`logs/w5/C_RESULTS.md`,
restated `logs/p42/SIM_LIMIT.md` §1).

This phase does not test the sensor. It tests **whether the information exists
in the cell's own kinematics**, which is the only part that can be settled
without buying $1,020 of GelSight. §5 gives the exact sense in which a negative
here is decisive and the exact sense in which it is not.

---

## 1. Why a patch channel is *not* just a smoothed force

The two channels are different **variables**, and that is the whole hypothesis:

| channel | the variable it reads | what it can lead |
|---|---|---|
| the shipped `f=(f0,f1)` | the normal force on each finger link, aggregated to one scalar per finger (`tactile.py`: `ContactSensor` value + `in_contact`) | nothing about **where** the payload is on the pad |
| a patch channel | the contact **location** on the pad (a 2-D position) + the patch's **occupancy** of the pad | a tangential walk that has not yet changed the normal force |

So the patch channel can lead a force collapse if — and only if — the payload
**walks while still pinched**. That is exactly the `logs/p42/SIM_LIMIT.md`
loaded-slide class (P61: the payload leaves along the tool axis, 25.2 deg from
it; P75: the pads are driven to their 98.1 mm stop 9 ticks later). Whether the
walk is *gradual enough* to be caught is the question.

---

## 2. The statistic, derived (and why it is the simplest defensible form)

`tasks.tactile_patch_state(fruit, pad_origins, rot, radius)` → one dict per pad,
per control tick, from geometry the sim already has:

1. **The pad's face frame is measured, not assumed.** `n` is the unit jaw axis
   from the two finger **link origins** (`arm.jaw_positions()`, the same two
   prim reads `jaw_separation()` takes); `e_long` is the **tool axis**
   (`rot[:, 2]`, the axis `_pad_standoff` offsets along) projected off `n`;
   `e_mid = n x e_long`.
   **Why the tool axis and not `n x rot[:,0]`**: the sign of `n` depends on which
   finger link is on which side, so only the tool axis gives `v` a consistent
   meaning (+ = toward the tip). Measured, not argued: the first version used
   `e_b = n x rot[:,0]` and the seated payload read `v = -66 mm` on one grasp and
   `+66 mm` on another, which would have flipped the pad-rectangle offset's sign
   run to run.
2. **The centroid** is the payload centre projected on that pad's face:
   `u = (fruit - o_k) . e_mid`, `v = (fruit - o_k) . e_long`. **Exact.** It needs
   no fruit model, no pad model and no calibration — it is where the payload is,
   on the pad. `dc` (the norm of the centroid's displacement since the leg's
   first **seated** tick) is the reflex operand.
3. **The patch** is the payload's **equatorial disc** (radius = `diameter/2`, the
   widest cross-section the jaws can touch), because the sim has **no
   elastomer** (`logs/p42/SIM_LIMIT.md` §3: rigid, adhesion-free pads) and the
   only patch the geometry defines is the sphere against the plate. `frac` is
   that disc's **occupancy** of the pad's face rectangle, from a 48-point
   equal-area (sunflower) quadrature — deterministic, no lattice bias, 48
   compares per pad per tick.
4. **The pad's face rectangle** is the measured plate: `61.000 x 84.902 mm`
   across x long (`logs/p66/COLLIDER_READ.md`, the P39 `S` arm's authored AABB
   at `FRUIT_FINGER_TIP_DELTA=0`), centred **0.033549 m from the link origin
   along the finger** (`finger_length` 0.076 - half-long 0.042451). That offset
   is not cosmetic: the shipped `_pad_standoff` (`FRUIT_FINGER_LEN` 60 mm +
   `PAD_LIFT` 10 mm) puts a seated payload at `v = +66.2 mm`, i.e. **~9.8 mm
   behind the distal border**, so a rectangle centred on the link origin scores
   every good seat as *already off the pad* — measured before the constant
   existed: `frac = 0.062`, `edge = -23.8 mm` (`logs/p102/smoke.log`). With the
   face centre it reads `frac = 0.646`, `edge = +9.8 mm`.

**Why the equatorial disc is the *generous* choice, and why that matters.** A
real soft pad images a patch **smaller** than the equatorial disc, and a smaller
disc clips off the pad **later** as its centre approaches a border (its occupancy
only starts falling once the centre is within one radius of the edge). So a lead
measured on the equatorial disc is an **upper bound** on the lead any smaller,
more realistic patch model could give. A negative on this model is therefore
decisive for the class; a positive would have had to be re-run at a realistic
radius.

**The per-pad degeneracy, declared rather than hidden.** Two **parallel** rigid
pads on a sphere project the same point, so `u`/`v`/`frac`/`edge` are identical
on the two per-pad rows; they differ only in `h` (the payload centre's signed
distance to each pad's *own* plane — the two sum to the measured span) and in
each pad's **own** force. A real sensor's two elastomers deform differently and
this sim cannot represent that — a second reason (with the missing elastomer) the
sim can only falsify the tactile claim, never confirm it. The one-sided read that
*is* available is the per-pad force, and it is the escape's own signature
(P75 2b: `f = (0.00, 4.93) N` for a whole leg).

### The one derivation the census also checks numerically

`dc` is the **in-plane part of the already-measured `clean_slip`**: `clean_slip`
is `||rot_now.T (fruit - pads) - ref||` in 3-D (the W8-B tracker the `[carry]`
row prints), and the patch centroid's displacement is the same vector with the
jaw-axis component dropped. For an escape along the tool axis (P61: 25.2 deg from
it) the tool axis lies **in the pad plane**, so `dc` and `clean` should agree to
within a few percent. The census prints that ratio, because it is the mechanism
of the answer: **a spatial centroid channel carries no timing information the
shipped `clean_slip` lacks, unless the payload's motion is mostly *out of* the pad
plane (a jaw-axis push) — which is the normal-force channel's own variable.**
The only genuinely independent term is `frac`/`edge`, and it is a function of the
same `(u, v)`.

---

## 3. The instrument: what it prints, and its cost

`FRUIT_TACTILE_PATCH=<ticks>` — one `[tactile]` row **per pad per tick** for the
first `<ticks>` ticks of every carry leg, inside the existing W8-B carry block
(the one `FRUIT_PLACE_ONSET_TRACE` uses), post-step:

```
[tactile] <side> <leg> pad=<0|1> t=<i> u= v= du= dv= dc= h= frac= edge=
          sep= gap= f= n= clean= dia=
```

(all mm except `frac`, `n`, `dia` in mm too). `u`/`v` are the raw centroid;
`du`/`dv`/`dc` its displacement since the leg's first tick; `f` this pad's
normal force; `clean` the running `clean_slip`; `dia` the payload's diameter.

**Cost and containment** (AGENTS §2). The block reuses the block's own
`rot_now`, `_sep_now`, `fruit`, `rel_frame`; it adds **one tactile set and one
`jaw_positions()`** per traced tick and **no `ik_step` work and no articulation
read** — asserted by the selfcheck leg (`scripts/255_p102_tactile_selftest.py`,
item [3]). Setting the knob also **arms the block it lives in**
(`guard_armed` gains `or self._tactile_patch > 0`), so the instrument is
self-sufficient and the reference tracker comes with it. Unset, the whole thing
is one integer test per leg and the shipped path is byte-identical — which the
census proves line for line (§5).

A diagnostic's run is allowed to differ from the shipped one (two `say()` per
tick), so **no rate may be quoted from a traced run**: the cells here are the
shipped cell's *branch*, read for the per-tick ordering only.

---

## 4. The census, and its rules pinned before the run

`logs/p102/census.py` reads the logs and, **per carry leg**:

**Reference tick = the seat, not the leg's first tick.** A `grasp_lift` leg
starts *before* the dynamic catch (the payload is caught 80-160 ticks in), so a
displacement from t=0 includes the catch's own approach — measured: a 13.7 mm
reading on a leg that then held for 110 ticks and placed. Every signal is
referenced to `t_seat` = the first tick the strong face (max of the two pad
forces) reads **> 1 N**. A leg that never reads > 1 N is **never-held** and
excluded (P76 A3).

| event | definition | why this definition |
|---|---|---|
| `t_seat` | first tick `max(f0,f1) > 1 N` | the seat is the reference; a `grasp_lift` leg starts before the catch |
| `t_2mm` | first tick `clean - clean(seat) > 2 mm` | **the survey's P1 reference, verbatim** ("detectable >= 10 ticks before `clean_slip > 2 mm`") |
| `t_force` | first tick after the seat after which the strong face **stays** < 1 N for >= 5 ticks | the escape's own pry reads *one* face at 0.00 N for a whole leg (P75 2b), so a per-face drop fires at the seat on the legs it should detect; a bounce gap is 1-2 ticks and is rejected by the 5-tick persistence |
| `t_left` | first tick `clean - clean(seat) > 100 mm` | P74's mechanism count ("the payload left"), not the `> 800 mm` threshold |
| `t_static` | first tick `dc > 0.5 mm` | "the patch moved at all" |

**Escape leg** = P76 A3: `clean_slip_max > 100 mm` **and** `fmax > 0` (a pinch
happened). **Held leg** = everything else that seated. The same thresholds are
applied to the held legs, because a threshold that trips a held leg is not a
trigger.

**The swept candidate signals** (all offsets from the seat):

* `dc > theta` at **theta = 5 / 10 / 20 % of the pad's half-length**
  (`TACTILE_PAD_HALF_LONG` = 42.451 mm → **2.12 / 4.25 / 8.49 mm**), *and* at the
  absolute **1 / 2 / 5 / 10 mm**. The absolute set exists because the pad-size
  assumption is the instrument's one soft number: a GelSight Mini's pad is
  30 x 40 mm class (survey §2.2), i.e. a 20 mm half-length → 1 / 2 / 4 mm. Quoting
  both makes the assumption visible instead of hiding it in a percentage.
* `frac < 0.75 frac0` and `frac < 0.50 frac0` (the patch's occupancy leaving the
  pad, relative to its own seat value — the absolute value depends on the fruit's
  size against the 61 mm pad width and is not a threshold).
* `edge < 0` (the centroid off the pad's face).

**The battery.** The **shipped cell** (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`
default), 20 attempts, seeds **5 and 6** — P92's own population, whose `cnp`
class is 9 of 40 attempts — with P91/P92's control instrumentation verbatim
(`FRUIT_MOTION_REPORT FRUIT_CYCLE_REPORT FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`)
plus the new knob at 800 ticks (the longest carry leg on this cell is ~560 ticks,
so nothing is truncated; the census's `ticks=` column shows it if one is).

**Neutrality (the proof, not the argument).** Each cell's whole log must equal
`logs/p91/{C5,C6}.log` **line for line** with the phase's own `[tactile]` rows
dropped:

```
python3 logs/p102/census.py --same logs/p102/T5.log logs/p91/C5.log
```

That is stronger than the registered `[fruit]`-stream replay (P75/P95/P96): it
also covers the `[carry]` diag rows, the `[place-trace]` rows and every motion
row. A single differing line means the instrument moved the branch and no lead
number is admissible from that cell.

**What would make the hypothesis win**: on >= 50 % of escape legs, some swept
threshold fires >= 10 ticks before `t_force` (and, per the survey's P1, before
`t_2mm`), **and** the same threshold does not trip the held legs. The kill fires
if no defensible threshold reaches 10 ticks on the majority.

---

## 5. What a negative here does and does not cover

**Covers, decisively.** The *kinematic* part: whether the payload's position on
the pad moves measurably before the pinch is lost. If the payload is
*motionless* until the tick of the expulsion, then **no tactile sensor — of any
kind, at any rate — can see the slip earlier**, because there is no slip to see:
the event is a static hold followed by a 2-tick expulsion (P75's mechanism). That
is a property of the cell, not of the sensor.

**Does not cover.** The *elastomer* part. A real pad's patch moves with the
**shear deformation of the skin**, which can ramp while the payload's *centre*
is still static (the classic "incipient slip" signal: the contact annulus slips
while the central region sticks). This sim's pads are rigid and adhesion-free
(`logs/p42/SIM_LIMIT.md` §3), so it has **no shear compliance to deform** and
cannot represent that signal at all. A negative here therefore says: *the
payload's motion gives no notice*, not *no sensor could*. The distinction is
exactly the survey §2.4 caveat ("the sim can only falsify, never confirm") — and
it is why the kill is worded as a decision about **this failure class on this
cell**, not about tactile sensing in general.

**And the load path.** The escape is a *pry* (P75: `sep` rises 78 → 98.1 mm in 9
ticks against a *closing* command, 0.00 N on one face), so the quantity that
would lead is the **tangential contact force** — shear — which the shipped
`ContactSensor` aggregation does not report at all (`tactile.py` returns
`normal_force`, `contact_count` and per-finger magnitudes). That is a *third*
channel, not the patch centroid and not the 2 scalars, and this phase does not
build it; it is named in `logs/p102/RESULTS.md` as the only remaining
tactile-side measurement.

---

## 6. Reproduction

```bash
bash logs/p102/run_p102.sh                       # the two cells (~15 min)
python3 logs/p102/census.py --check logs/p102/T5.log logs/p102/T6.log
python3 logs/p102/census.py       logs/p102/T5.log logs/p102/T6.log \
    > logs/p102/census.txt
python3 logs/p102/census.py --lead logs/p102/T5.log logs/p102/T6.log \
    > logs/p102/lead_table.txt     # the lead-time table: every escape's walk
python3 logs/p102/census.py --same logs/p102/T5.log logs/p91/C5.log   # neutrality
python3 logs/p102/census.py --same logs/p102/T6.log logs/p91/C6.log
bash logs/p102/gates.sh                          # G1/G2 neutrality, G3 relocation, G4 reader
python3 scripts/255_p102_tactile_selftest.py     # the instrument's own leg
scripts/selfcheck.sh
```

No `configs/` file is touched, no reference is re-recorded and none is owed: the
knob is default-off and the neutrality replay is the proof.
