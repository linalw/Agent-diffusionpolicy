# P42 phase 2 pre-registration — the bounded pre-close centring
# (`FRUIT_SEAT_CENTRE`)

Drafted 2026-10-26 in **phase 1**, *after* the seat census was read
(`logs/p42/SEAT_CENSUS.md`). That ordering is stated rather than hidden: the
census is phase 1's own deliverable, so this registration carries its numbers as
a **prior**, and §5 records that one falsifier has already fired against the
lever's premise. Everything below is nevertheless written as the rule phase 2
must be read by - in particular the endpoints are not negotiable after the run.

No commit, no `configs/` change. Tree pins at the end.

---

## 1. What is being tested

The carried-not-placed class is a **loaded slide** (`logs/p41/P3_RESULTS.md` §3,
W8-B): the pads hold (two-sided at the freeze, 9.8-9.9 N pinch after the
`finger_damp02` flip), the payload walks out along the finger axis, and the
contact is single-sided at the loss. The force family is closed (P41: 10 -> 30 ->
60 N deletes the pad pry and the class *worsens*). The two fingers are **rigidly
geared** (`PhysxMimicJointAPI:rotY`, gearing -1, `naturalFrequency = 0`,
`assets/openarm_flat/openarm_flat_deinst.usda:3822-3843`), so the jaw is
symmetric by construction and the remaining candidate is **the seat**: where the
pads' midpoint sits relative to the fruit's centre when the close freezes.

Phase 1 measured the seat (20 grips, two corpora, default-off instrument,
proven run-free): **lateral seat error 1.36-4.65 mm, median 1.72-2.41 mm, two-
sided contact on 20/20, force split balanced (asym median 0.06-0.17)**, and the
escapes are *not* the off-centre grips (on the species-locked pear the four
escapes are the tightest cluster, and the corpus's largest lateral offset
placed). What separates is the payload's displacement *during the lift*
(28-74 mm on placed legs, 104-276 mm on escapes by the lift's last sample) and
the one-sided contact that follows it (18/32 escape carry samples, 0/48 placed).

The lever tests the remaining causal reading of that census: **if a part of the
lateral seat error is still present at the close, removing it should reduce the
walk.** The census says the available correction is at most ~4.6 mm - this
registration runs the lever so the answer is *measured* rather than argued.

---

## 2. The lever, exactly as registered

**Knob.** `FRUIT_SEAT_CENTRE=<m>` - a **per-axis clamp in metres**.
Unset, empty or `0` = **off** = byte-identical (not a code-path change: like
`FRUIT_SEAT_DIAG`, the resolved value is read once in `__init__` and every
downstream branch is a single false test). Resolution: `m = min(float(env),
0.020)`, and a value > 0.020 prints one note (`clamped to the registered bound`)
rather than being silently honoured. Negative / unparseable = off.

**Site.** The dynamic close of the scripted moving catch, in the window **after
the catch-up loop's last tick and before the close ramp's first `ik_step`** -
i.e. after `dynamic catch-up: residual=... (< 6 mm)` and before
`for _close_step, gap in enumerate(close_ramp):`. No time is scheduled there: the
arm is already at the station, the fruit is already tracked, and the close's
ramp is unchanged.

**Form (one correction, no re-approach).**

```
d  = pad_centre() - spawner.position(sample)        # world, one read
c  = clip(-d[0], -m, +m), clip(-d[1], -m, +m)       # x and y only
arm.ik_step(arm.tcp_target_for_jaw(pad_centre() + [c_x, c_y, 0.0]))
```

then close exactly as shipped. **One** measurement, **one** IK command, no
re-measure, no loop, no re-approach, no change to the close command, the freeze
criterion, the interference or the grasp pose.

**z is excluded by construction**, not by omission: `dz` at the freeze is
+69.3..+71.7 mm in all 20 grips and equals `_pad_standoff(True, sample)`
(`FRUIT_FINGER_LEN` 60 mm + the dynamic pad lift) - i.e. it is the *commanded*
standoff, so "centring z" is a grip-plane / standoff change, and the bounded
grip-plane drop (D2a) was measured **negative** in R8-A (`logs/r8/A_RESULTS.md`).
This lever must not re-open that lane under a new name.

**Why one command persists through the close.** With the OpenArm hand every
measured close runs the **non-coherent** path: the close's own `coherent` flag
(`self._coherent[side]`, set during the close and read back by the carry's
`[diag] carry-assist ... coherent=False hand_is_jaw=True` rows) reads **False on
60/60 legs in all three corpora** (`logs/p42/p2/seat_{accept,pear}.log`,
`logs/p41/p3/accept_control.log`), and that path **does not command the arm at
all** during the close - the drives keep the target the caller last set
(`hold_target`, `tasks.py`). So the pre-close re-aim *is* the close's aim.
**Evaluability check (mandatory in phase 2)**: the lever's own legs must read
`coherent=False`; if any leg reads `coherent=True` the close re-aims the jaw at
the fruit's live centre every tick, the one-shot correction is overwritten, and
that leg is not evaluable. On the coherent/kinematic path the lever is
therefore meaningless **by construction**, so it is registered
**scripted-OpenArm-scope only**; the two-line scheduler and the direct/policy
handover are out of scope and must not be armed.

**The catch window.** Untouched: the correction is applied *after* the catch-up
has converged to its 6 mm tolerance, it is ≤ 20 mm (registered bound; the census
says ≤ 4.65 mm in practice), nothing is re-selected, nothing is re-scheduled, and
the close's own tracking lead is unchanged.

---

## 3. Endpoints (in order; all measured on the same pair of runs)

| # | endpoint | rule |
|---|---|---|
| **P1** | **mechanism** | the **freeze-time lateral seat error** `abs(xy)` falls, paired per grip, median, by **>= 50 % relative** on the pear battery vs the same-tree control (`FRUIT_SEAT_CENTRE` unset) |
| **P2** | secondary | the freeze-time per-pad force split `asym` median falls by **>= 20 % relative** |
| **P3** | class | the **left-arm not-placed (cnp) count** on the pear battery falls **with the left attempt count invariant** (the P39 A1.3 evaluability rule) |
| **P4** | cost | attempt span **<= +0.2 s** (`[stats]` per-attempt, both corpora) |
| **P5** | no-harm | knob unset -> the `[fruit]` stream **byte-identical** (minus `[seat]`/`[carry]`) to `logs/p42/p2/control_accept.log`; `105_motion_regression.py` reads `fingerprint: matches configs/motion_reference.json`; `scripts/selfcheck.sh` PASS; `configs/**` unchanged; the lever-on runs carry `[seat]` so P1/P2 are read from the instrument, not inferred |

**Why P1 is a relative rule**: the census's escape median is 1.72 mm and the
instrument's resolution is 0.1 mm, so an absolute threshold would be arbitrary;
50 % of 1.7 mm is 0.86 mm, i.e. a change the instrument *can* see. P1 passing
with P3 failing is the **expected** outcome (see §5) and is a publishable
"mechanism works, class does not move" pair.

---

## 4. Falsifiers (any one stops the lane; F1 is already measured)

* **F1 - the seat is not the term.** Median freeze `abs(xy)` on the escape legs
  **<= 2 mm**. **Measured in phase 1: the pear escapes read 1.36-2.06 mm,
  median 1.72 mm** (and the corpus's largest lateral offset, 4.65 mm, placed).
  **FIRED.** The lever's whole available correction is therefore ~2 mm against a
  100-350 mm walk.
* **F2 - the lever moves nothing.** P1's median does not fall (or falls < 20 %),
  i.e. the arm cannot execute a bounded re-aim. Named mechanism: the pick pose
  sits at the workspace boundary - *every* descent ends 40-90 mm short of its
  commanded point (AGENTS §2) - so a +-10 mm re-aim may be unreachable in one
  direction.
* **F3 - a new failure reason.** Any note outside the recorded baseline set after
  digit normalisation (`scripts/113_rl_report.py` `reasons()` semantics).
* **F4 - the catch window breaks.** `dynamic catch-up: residual=` above its 6 mm
  tolerance on a majority of attempts, or the attempt count / selection changes
  (a fruit that would have been caught is missed). The correction is applied
  after the catch-up, so a *selection* change would be a scope bug, and it fails.
* **F5 - the class endpoint is a moved attractor.** If the left attempt count
  changes, P3 is a **report**, not a verdict (P39 A1.3), and no adoption is
  possible on that pair.

---

## 5. The phase-1 prior, and what phase 2 is therefore for

**F1 has fired.** The centre-piece of the census is that the freeze-time seat is
already centred to 1-5 mm, that the escaping grips are the *most* centred, and
that the payload leaves **after** a centred freeze by walking 100-350 mm. Two
consequences the Oracle should weigh before spending phase 2:

1. **The lever cannot convert the class by magnitude.** Its largest possible
   effect (<= 4.65 mm, in practice ~2 mm on the escapes) is 50-170x smaller than
   the escape's own displacement, and the walk's driver is inside the lift (the
   vertical sag of 3-9 mm at the lift start plus a ~10 mm `lip` margin), which an
   x/y re-aim does not touch.
2. **It can still be worth one pair** because it converts a *measured premise
   failure* into a *measured lever null*: P1 may pass trivially (the arm moves
   1-2 mm and the instrument resolves 0.1 mm) while P3 does not move, which is
   the cleanest possible statement that the seat is not the term - and it is the
   evidence the phase-3 "B" record wants, rather than an argument from the
   census alone.

**Recommendation to the Oracle**: run phase 2 as **one pear pair** (control vs
`FRUIT_SEAT_CENTRE=0.010`, `ATTEMPTS=10 SEED=5 FRUIT_SUPPLY_SPECIES=pear
FRUIT_SEAT_DIAG=1 FRUIT_CARRY_DIAG=1 FRUIT_MOTION_REPORT=1`) plus the acceptance
no-harm pair, then either adopt (P3 passes, F5 clear) or write **B** - the
sim-limit record - with both the census and the lever's null behind it. **Do not**
run a second lever arm, a z variant, or a bigger clamp: a z variant is D2a
(measured negative) and a bigger clamp is bounded by the catch-up's own 6 mm
tolerance, which the arm has already spent.

---

## 6. What this lever is NOT (non-duplication, against the existing knobs)

| existing knob | why this is not it |
|---|---|
| `FRUIT_GRIP_PLANE_DROP` (D2a, R8-A) | moves the **commanded standoff** (z) and the catch target; measured **negative**; out of scope here by §2 |
| `FRUIT_DYNAMIC_WALK_LEAD`, `FRUIT_DYNAMIC_X_TRACK_*` (R2) | act **during** the close, per tick, and move the aim onto the *live* (moving) fruit; this is **one** pre-close command derived from the *measured seat error* |
| `FRUIT_CARRY_GUARD` / `FRUIT_CARRY_RELIEF` (W8-B, R6-B) | act **after** the slip onset (hold + re-seat); measured not adopted; this acts **before** the first close tick |
| `FRUIT_DYNAMIC_MIN_INTERFERENCE`, `FRUIT_FINGER_MAXFORCE` (P41) | force / depth; P41 closed the force family |
| `FRUIT_DYNAMIC_HOLD`, `FRUIT_DYNAMIC_CATCH_TOL` | timing / catch tolerance; the lever changes neither |
| `FRUIT_POLICY_TRIGGER_ACQ`, `FRUIT_DIRECT_RESEED` (W7-B, R2) | direct/policy-handover acquisition; out of scope by §2 |

---

## 7. Read protocol

* **One claim at a time**, sequential (`scripts/154_claim_run.sh`), both arms in
  the same stretch, and the fingerprint probed before the pair: a run in a
  different attractor is a different scenario, not a repeat.
* **Pear battery = the species-locked primary** (`ATTEMPTS=10 SEED=5
  FRUIT_SUPPLY_SPECIES=pear`); the acceptance and the two-line are reports.
* **N**: P1/P2 are **paired per-grip mechanism** endpoints (n = the grips, not a
  rate). P3 needs the left attempt count invariant, so one pair is one branch; a
  second pair is run **only** if the control does not reproduce itself
  bit-identically (documented practice, not a re-roll of the treatment).
* Everything quoted carries its attractor: a knob-on log that differs from its
  control in the *pre-close* stream is a different scenario and its P1 is void.

---

## 8. Pins at registration

`src/fruit_sorting/tasks.py` **e34e0f58** (`[seat]` instrument + `FRUIT_SEAT_DIAG`),
`src/fruit_sorting/rl_env.py` **7c438ef7** (`TASKS_MD5` metadata-only follow),
`configs/motion_reference.json` **8a399626**, `configs/motion_reference_twoline.json`
**2246f83c**, HEAD `c2760bf`. Phase 2 will change `tasks.py` (+ the `TASKS_MD5`
follow) and must pin both again. Evidence for the prior: `logs/p42/SEAT_CENSUS.md`,
`logs/p42/p2/`.

---

## Amendment A1 (2026-10-26, Oracle gate at close-out, **after the phase-2 run**)

Gate verdict: **ACCEPT WITH AMENDMENTS**. This block is the correction record, not
a rewrite: everything above stays readable as the registration the phase was
actually run under (the P39 `PREREG.md` A1 / P41 `DEVIATION.md` precedent), and
the sharpest of the corrections is that **a premise of §2 was false**.

**A1.1 - §2's coherence premise was wrong, and it is a variable confusion.**
§2 quotes `self._coherent[side]` ("False on 60/60 legs in all three corpora") and
concludes that the OpenArm close runs the **non-coherent** path, "which does not
command the arm at all during the close". That variable is the **carry
bookkeeping's** flag. The close's own local `coherent` - the one that gates the
per-tick `ik_step` - reads **True on 20/20 grip closes** (10/10 pear, 10/10
acceptance; printed by `[seat] centre ... coherent=`,
`logs/p42/p3/CENTRE_READ.txt` §1). It is True **structurally**, not by luck:
`coherent` is set `False` in exactly two places, both guarded by
`if openarm: ... else:`, so with the OpenArm hand - the only hand this line runs -
the close can never take the non-coherent branch. `self._coherent[arm_name]` is
only ever set `True` on the `pad_error <= FRUIT_COHERENT_FALLBACK` (20 mm) branch,
is never reset on the "closing anyway" branches, and the OpenArm's pre-grasp
`pad_error` exceeds 20 mm, so it stays `False` for the whole session while the
close's own flag is `True`. **Two different variables**
(`logs/p42/P2_RESULTS.md` §2). The docstring of `_seat_centre_step` repeated the
false premise and was corrected in **comment only** at this close-out
(`tasks.py` `3e6ea4cf -> e2d0f12a`; the reverse substitution reproduces the
measured md5 byte-for-byte, so every measured number below is that code).

**A1.2 - §8's lever is therefore absorbed, and the registration's own mandatory
clause makes it so.** §2 says "if any leg reads `coherent=True` the close re-aims
the jaw at the fruit's live centre every tick, the one-shot correction is
overwritten, and that leg is not evaluable". On this hand **every** leg reads
`coherent=True`, so the clause fires on all 20 grip closes and the lever's whole
available action (|c| median **2.99 mm** pear / **2.91 mm** acceptance, the 10 mm
clamp never binding) is removed again before the freeze (paired freeze `|d_xy|`
change **+0.00 mm** pear, **+0.01 mm** acceptance). What the close actually
issues is an **absolute** `ik_step` every close tick with
`aim = [frozen_x, fruit_y + vy*lead, z = _pad_standoff]`
(`tasks.py:10064-10074`), the freeze at `tasks.py:9996-10007`: with the P2b
x-lock on (shipped default, `FRUIT_DYNAMIC_CLOSE_LOCK_X=1`) **x is pinned** at the
first close tick, **y is live** and **z is the commanded standoff** - so the
sub-clause "the close re-aims live in x" is also false, but y and z are
commanded, which is enough on its own to overwrite a one-shot. The residual
**1.4-4.6 mm** `|d_xy|` the freeze reads is **servo following error**, not a
seating error. Any future pre-close command on this line must be registered
against the coherent path (e.g. a per-*tick* aim offset), not around it.

**A1.3 - P1/P2/P3 are not evaluable; they are not "negative results".** By
A1.2's mandatory clause and the registration's own §3, the lever's legs cannot
carry P1 (mechanism) or P2 (secondary), and P3 is additionally hit by **F5**
(the pear's left attempt count moved **6 -> 4**, so the class endpoint is a
report). What **is** evaluable and stands: **P4 PASS** (span 15.7 -> 15.5 s pear,
15.0 -> 15.0 s acceptance, inside the +0.2 s rule) and the P5 read as measured
(knob unset: structural identity plus the phase-1 control's
`fingerprint: matches` - no re-run was spent; the lever arm's own fingerprint
**DIFFERS** at leg 3, 0.109 vs 0.108 m/s, i.e. a moved attractor; `selfcheck.sh`
PASS; `configs/**` untouched).

**A1.4 - F2 fired by its letter, not by its named mechanism.** §4's F2 names "the
pick pose sits at the workspace boundary ... a +-10 mm re-aim may be unreachable in
one direction". The arm **executes** the command (every grip, no `unavailable`
row, no clamp binding); the close removes it. The falsifier's *statement* ("the
lever moves nothing") is satisfied, its *named mechanism* is refuted - so F2 is
recorded as fired on the letter, with the correct mechanism (A1.2) beside it. F1
fired in phase 1 (the pear escapes are the *tightest* seat cluster, 1.36-2.06 mm),
**F3 clear** (no failure note in either arm, 40/40 `notes=[]`), **F4 clear**
(catch-up residuals are the shipped 5.6-6.0 mm on all 40 attempts).

**A1.5 - the measured record stands exactly as `logs/p42/P2_RESULTS.md` states
it, and is not re-derived.** The seat is centred (20/20 grips, `|d_xy|`
1.36-4.65 mm, two-sided, `asym` 0.01-0.35); the only systematic axis is the
commanded z standoff; the escapes are **not** the off-centre grips (on the pear
they are the tightest cluster) - and the escape-vs-placed rank difference is
**noise at n = 4/6**, so the claim is carried by the **30-60x magnitude**
comparison (~3-4.6 mm available vs a 104-276 mm mid-lift walk), not by the rank;
the walk separates the classes late (104-276 vs 28-58 mm; one-sided 18/32 vs
0/48). No count from this phase is a rate: the pear's 6/10 vs 7/10 is a **moved
branch** (F5, first divergence attempt 5's selected fruit) and the acceptance is
6/10 in both arms on **two different attractors** - **never quote a bare
6/10 -> 7/10**. The seat family is therefore **closed in this parameter space**
(reopen only via a new pad asset or a real-jaw clamp-force anchor,
`logs/p42/SIM_LIMIT.md` §4), and **nothing is adopted**:
`FRUIT_SEAT_CENTRE` stays default **off**, a measurement interface with a
documented null.

**Pins after A1.** `src/fruit_sorting/tasks.py` **e2d0f12a** (comment-only
docstring correction; the measured tree was **3e6ea4cf**),
`src/fruit_sorting/rl_env.py` **50980bf5** (`TASKS_MD5` follow
`3e6ea4cf -> e2d0f12a`), `configs/motion_reference.json` **8a399626**,
`configs/motion_reference_twoline.json` **2246f83c** (both untouched), HEAD
`c2760bf` + the P42 commits. Evidence: `logs/p42/P2_RESULTS.md`,
`logs/p42/p3/CENTRE_READ.txt`, `logs/p42/SIM_LIMIT.md`.
