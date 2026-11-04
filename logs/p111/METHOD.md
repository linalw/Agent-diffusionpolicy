# P111 method - the compliant closure: what was built, and why each number

The phase's own record of the *design*: what the algebra asked for, what was
built to deliver it, and which knob owns which parameter.  The measurements are
in `RESULTS.md`; the registration (pinned before any cell) is `PREREG.md`.

## 1. The question, restated as a mechanism

P110's closure arithmetic: the ring is **one radial synergy on four
force-capped position pads**.  A pad's force is `min(k * penetration, cap)`, so
at the shipped `k = 1e5 N/m` and `cap = 4.90 N` the drive saturates at
**0.049 mm** of penetration and is then a *force source at the cap* for the rest
of the close.  A payload offset by `delta` therefore has

```
near pad  penetration  s + delta     -> at the cap, pushes at 4.90 N
far  pad  penetration  s - delta     -> NO contact (a gap of 2*delta)
perp pair penetration  s - roundness -> at the cap (its own friction source)
```

and the near pad's 4.90 N is spent accelerating the payload, not seating it: P107
measured `bat` 27-82 mm and P108 measured `clr = -0.3..-33.4 mm` on 7/15 closes
with the pads *through* the fruit.  So the ring **grips where it sits** (and
sometimes launches).

The hypothesis the owner chose: **make the pad a spring**.  At `k = 1e3` the same
1 % squeeze delivers `k*s` = 0.6-0.7 N per pad instead of the cap, and the
saturation needs `cap/k = 4.90 mm` of penetration - 100x the shipped yield.  Then
the four pads can balance at the ring's centre.

## 2. The static balance, and the one inequality that decides it

`logs/p111/algebra.py` writes it out.  With the payload offset along one jaw axis,
its motion is **normal** to the near/far faces (Coulomb friction is zero there)
and **tangential** to the perpendicular pair (friction `mu*N`), so

```
drive = near - far = 2 k delta          (both loaded, linear regime)
fric  = 2 mu (k s) + mu_belt m g        (the perpendicular pair + the belt)
```

Sliding stops where they balance:

```
delta_inf = (2 mu - 1) * min(s, cap / (2 mu k))
```

* **`mu > 1` is the term, not the stiffness.**  The residual is `(2mu - 2) s`, so a
  four-jaw lands at `1.1-1.9 s` where the 4-contact state needs `< s`.  The
  measured pad-payload friction is `mu_pair = (2.0 + mu_fruit)/2 = 1.25-1.46`
  (P104's `mu_app` 1.05-1.45, and PhysX averages the pair), so the ring **cannot
  close the last millimetre** at any k or cap - the ratio is k-free and cap-free.
* **A three-jaw would**: `delta_inf = 2 mu s/(1.5 + mu)` = 0.82 s < s.  The
  number of *tangential* contacts is the lever (2 of 3 jaws vs 2 of 4).
* **The knee**: above `k* = cap/(2 mu s) ~ 2.2e3 N/m` the perpendicular pair is at
  the cap, `fric = 2 mu cap = 12.8 N > cap`, and *nothing slides at all* - that is
  exactly the shipped ring.  Below it the payload slides to `(2mu-1)s`, a **5-8x
  centring** from P108's 8.8 mm.

So the algebra predicts a **mechanism pass and a conversion miss**: the offset
shrinks by ~5-8x, the 4-pad count does not rise, and the count is the rigid ring's.

## 3. What was built

Three pieces, one knob per parameter.

### 3.1 `cage_hand.py` - the drive profiles

The cage already authored its own drive (`k`, `c`, `maxForce` per pad), so the
*close* profile is P107's existing knobs:

| parameter | knob | value used | why |
|---|---|---|---|
| close stiffness | `FRUIT_CAGE_PAD_STIFFNESS` | **1e3** N/m (T1), 5e3 (T2) | `cap/k` = 4.90 / 0.98 mm; T1 is the registered point (`cap/k` ~ the line's 6 mm catch tolerance, P110's framing) and T2 is the algebra's stiff side of the 2.2e3 knee |
| close damping | `FRUIT_CAGE_PAD_DAMPING` | **8.9** / **14.1** Ns/m | `2 sqrt(k m)` at the fixture's 0.020 kg pad - P104's near-critical rule (P107: `c = 2000` unstable, `c = 100` stable at `k = 1e5`) |
| cap | `FRUIT_CAGE_PAD_FORCE` | **4.90** N | P41's per-face 9.8/2 N.  **Not lowered**: the ladder's geometry is cap-free below the knee, and a lower cap only lightens the grip (the `cap 2.0` column is the algebra's negative control) |
| hold stiffness | **`FRUIT_CAGE_HOLD_STIFFNESS`** (new) | **1e5** N/m | the hard stop - see 3.2 |
| hold damping | **`FRUIT_CAGE_HOLD_DAMPING`** (new) | 0 -> `2 sqrt(k_hold m)` = 89.4 | same rule |

### 3.2 The hard stop (`CageHand.close_done`)

A soft close is a **4-7x weaker hold**: at the shipped 1 % squeeze a `k = 1e3` pad
delivers 0.6-0.7 N, and the grip capacity that matters (`n * mu * N`, P104) falls
from 12.7 N to 1.6-1.8 N.  A pure-soft arm would therefore lose placements for a
**grip** reason and could not answer the centring question - the measurement would
be confounded by a known engineering defect.

A real spring-loaded pad *bottoms out*, and that is what `close_done` authors: one
call per attempt, from the task, right after the close settles the depth the carry
will hold.  It re-writes the four drives at the hold pair **with their target
unchanged**, so the pad re-loads to `min(k_hold * penetration, cap)` = the cap
**at the aperture it found**.  The pad body cannot move (the payload is in the
way), so the stop loads the grip without shifting the aperture - which the
selfcheck asserts (`scripts/257_p111_cage_compliance_selftest.py`).

The release is automatic: an **open** command (`FRUIT_GRIPPER_OPEN`, 90 mm, or the
cage's 120/200 mm) reverts the profile, and the pre-pose, the hover and `park()`
all send one before the next close.  So the profile needs no second call site.

### 3.3 The centring instrument (`[cage] off0= off=`)

The record's endpoint (`pads >= 3`) counts pads; it does **not** say whether the
payload is centred - and the phase's question is exactly that.  The probe already
reads the fruit pose every tick and the cage's base pose every tick, and the four
pads are symmetric about the base's axis, so the **ring's centre line is the
base's xy**.  Two reads per attempt give the offset at the close's start
(`off0`) and at the flush (`off`), both as `hypot(dx, dy)`:

```
off0 -> off      the payload's radial distance from the ring's axis, before/after
```

No new per-tick read, no new control input; `off` is taken against the axis
**where it is now** (the cage rides the arm, so it moves with the payload).  The
row is a default-off diagnostic (`FRUIT_CAGE_PROBE=1`), so the shipped path is
untouched.

## 4. The cells, and the admissibility rule

`logs/p111/cells.sh ARM:seed`:

```
C   shipped `openarm`                                  the delivered reference
R   cage4, 200 mm, k 1e5 c 100                         the compliance control
T1  cage4, 200 mm, k 1e3 c 8.9  + hold 1e5/89.4        the registered point
T2  cage4, 200 mm, k 5e3 c 14.1 + hold 1e5/89.4        the stiff side of the knee
S1  cage4, 200 mm, k 1e3 c 8.9  (no hold)              the pure-soft screen (F3)
```

The aperture is P108's **E** (200 mm) on every cage arm, so R vs T1/T2 differ only
in the drive.  Every arm carries P108's instrumentation verbatim
(`FRUIT_CAGE_PROBE FRUIT_MOTION_REPORT FRUIT_CARRY_DIAG FRUIT_PLACE_TRACE`), so the
arms are compared inside one instrumented batch.

**Admissibility**: C and R are P108's `S`/`E` arms, so the same-seed cells are
re-run on this tree and their `[fruit]` streams must be **byte-identical** to
`logs/p108/{S,E}_s5.log` with the phase's own rows dropped.  If that holds,
P108's other seeds are admissible controls (P95's rule: prove the replay, then
reuse); if it does not, the arm is re-run in full.

## 5. What the phase cannot say

* **A compliant pad is a hardware change.**  The sim's drive is a spring; a real
  gripper would need a **spring-loaded pad with a hard stop** (the form modelled
  here: a die spring behind the pad face, bottoming out on a shoulder) or a
  **force-controlled finger** (a load cell and a current loop).  The phase prices
  the mechanism and does not ship a setting: `configs/` is untouched and the
  shipped hand is byte-unchanged.
* **The two-line has no path** to a non-`openarm` hand (`tasks.py` refuses it), so
  the phase says nothing about the two-line; the hybrid canary builds its own task
  with the default hand, so it has no path either.
* **The 1-D algebra cannot resolve the bat's sign** - the launch needs a 2-D ring
  with an exit, which the cells have and the model does not.  The model's job was
  the *knee* and the *inequality*, and both are quoted as such.
