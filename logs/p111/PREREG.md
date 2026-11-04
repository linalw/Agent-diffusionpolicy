# P111 pre-registration - the compliant closure (P110's item 1)

Pinned **before any P111 simulator cell**.  The only things that exist at pin
time are: the offline algebra (`logs/p111/algebra.py` -> `algebra.txt`), the
`src/` build (`cage_hand.py`'s hard stop, `tasks.py`'s one call site and the
`[cage]` row's `off0`/`off`), and `scripts/257_p111_cage_compliance_selftest.py`
(PASS).  No cell of any arm has run.  The md5 of this file is `PREREG.md5`.

## 1. What the owner chose, and the hypothesis stated as an inequality

P110 closed the presentation lane and named **the compliant closure** as the one
term its arithmetic leaves standing.  The hypothesis is specific: the ring's four
pads are force-capped *position* drives, so at the shipped `k = 1e5 N/m` a pad
yields only `cap/k = 0.049 mm`; a payload offset by `delta` therefore has its far
pad `2*delta` short of contact, the near pad pushes at the cap, and the payload
is **launched** rather than pushed.  **If each pad yields `cap/k` of travel
instead (a low `k`), the four pads balance toward the ring's centre - a
self-centring chuck.**

`algebra.py` writes that as a static balance.  The payload's motion is *normal*
to the near/far faces (no friction there) and *tangential* to the perpendicular
pair, so

```
drive = near - far                 fric = 2*mu*perp + mu_belt*m*g
terminal offset  delta_inf = (2*mu - 1) * min(s, cap/(2*mu*k))
4-contact state  delta < s - 0.5/k
```

with `s = 0.01 d` (the shipped 1 % per face), `mu = (2.0 + mu_fruit)/2` =
**1.25-1.46** (P104's measured `mu_app` 1.05-1.45), `mu_belt` 0.71-0.91 and the
pool's own masses (P110's fixture table).  Three consequences are registered as
**predictions, not hopes**:

* **the four-jaw cannot close the last millimetre at `mu > 1`.**  The residual is
  exactly `(2*mu - 2)*s`, so a 4-jaw lands at 1.1-1.9 s where a **3-jaw**
  (`delta_inf = 2 mu s/(1.5 + mu)` = 0.82 s) would centre.  `mu > 1` is the term,
  not the stiffness.
* **there is a knee, not a slope**: above `k* ~ 2.2e3 N/m` the perpendicular pair
  is at the cap (`friction = 2 mu cap > cap`) and *nothing slides*; below it the
  payload slides to `(2*mu - 1) s` - a 5-8x centring from P108's 8.8 mm.
* **the registered `pads >= 3` endpoint and the centring mechanism are in
  tension**: the aperture is `0.98 x the WIDEST extent`, so a fruit whose narrow
  axis is smaller leaves the perpendicular pair short.  A ring whose
  perpendicular pair is *free* centres but cannot read 3 pads; a ring that reads
  3-4 pads is one whose perpendicular pair is jammed.  The clean-enclosure
  endpoint is therefore predicted to stay where P110 measured it (2/74 = 2.7 %).

## 2. The arms

The **scripted single arm** (`FRUIT_BIARM=0`; the two-line scheduler refuses a
non-`openarm` hand by construction, `tasks.py:9543` - that still holds on this
tree).  `ATTEMPTS=20`, one claim per run, every arm with the **same**
instrumentation (`FRUIT_CAGE_PROBE=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_DIAG=1
FRUIT_PLACE_TRACE=1` - the cage probe is a no-op on the shipped hand), so the
arms are compared inside one instrumented batch.

| arm | hand | close drive | hold drive | seeds |
|---|---|---|---|---|
| **C** | shipped `openarm` | - | - | 5, 6, 101, 202 |
| **R** | `cage4`, aperture **200 mm** | k 1e5, c 100, cap 4.90 | - | 5, 6, 101, 202 |
| **T1** | `cage4`, aperture **200 mm** | **k 1e3, c 8.9**, cap 4.90 | **k 1e5, c 89.4** | 5, 6, 101, 202 |
| **T2** | `cage4`, aperture **200 mm** | **k 5e3, c 14.1**, cap 4.90 | **k 1e5, c 89.4** | 5, 6, 101, 202 |

* The aperture is P108's **E** (200 mm) on every cage arm, so the only variable
  between R and T1/T2 is the **drive** - the compliance is isolated.
* **T1 is the registered point** (`cap/k` = 4.90 mm, ~the line's own 6 mm catch
  tolerance, P110's framing).  **T2 is the algebra's stiff side of the knee**: the
  ladder's own optimum sits between 1.7e3 and 2.7e3, so T1 and T2 bracket it and
  the pair is a **dose check** - if only the knee matters, T2 > T1; if compliance
  is monotone, T1 > T2.
* `c = 2 sqrt(k m)` at the fixture's 0.020 kg pad (P104's near-critical rule;
  P107 measured `c = 2000` unstable and `c = 100` stable at `k = 1e5`).
* **Seeds 101 and 202 are fresh** (P93's rule: two seeds reuse the same control
  branches, so a two-seed count over-states a gain).

**Admissibility.**  C and R are P108's `S`/`E` arms; before either is reused the
same-seed cell is **re-run on this tree** and its `[fruit]` stream is required to
be **byte-identical** to `logs/p108/{S,E}_s<seed>.log` with the phase's own rows
dropped (`[cage]`, `[cycle]`, `[carry]`, `place trace`).  If a replay does not
hold, the whole four-seed battery is re-run for that arm (`logs/p111/PLAN.md`).

## 3. Endpoints

**Primary (the mechanism - what "centring" means).**  The `[cage]` row's
`off0 -> off`: the payload's horizontal distance from the **ring's axis** at the
close's start and at the flush.  Registered as: **the compliant arms' `off`
distribution is lower than the rigid arm's** (one-sided, pooled over four seeds,
per-arm medians quoted).  This is the phase's new instrument and it is exact in
the sense the question needs - it measures the offset the ring has to absorb.

**Primary (the record's endpoint).**  The **clean enclosure** at `>= 3` pads with
P110's split as the classifier: *jam* (`[motion] approach ... end > 15 mm`),
*over-closure* (`aper < dia - 4 mm` or `F > 4 * cap * 1.5`), *clean* (the rest).
The raw pad count is **not** the endpoint.

**Secondary (delivered).**  The **placed count** per arm and per seed; the
**no-contact/ejection class** (`[cage] no_contact=1`, and `bat`/`bat_rel`); the
`[carry] force_min == 0` loaded-slide legs.  The interval is not estimable at
these counts and is not read; `s/attempt` is reported as the clock.

**Guards (all must pass).**

* **G1 the landing**: `FRUIT_PLACE_TRACE`'s `on_belt=True` on **every**
  payload-present release (`release_bottom >= 0`; the upstream-lost `-184 mm`
  rows are P86/P87's own class and are reported separately).
* **G2 the crush**: no leg with `sep@loss - dia < -15 mm` (P76's registered
  crush rule) and the `[cage]` row's `F <= 4 * cap` on every clean row (the cap
  bounds the delivered force by construction; a row above it is a non-payload
  contact and belongs to the jam class).
* **G3 the descent budgets**: `FRUIT_MOTION_REPORT`'s `|v|max` against the shipped
  profile per leg (the 2.5 %-of-legs 1.1x branch property is P93's, not
  re-tuned).  A hand moves the collider set (P71's rule), so the cage arms are
  gated on **budgets only** and their fingerprints are reported, never matched.
* **G4 the slots**: no lost slot (`[stats] attempts` = 20 and no `no eligible
  fruit` growth against the arm's own control).

## 4. The decision rule

A **win** requires all four:

1. the clean enclosure **rises** on a compliant arm against R (pooled, four seeds);
2. the **placed count does not fall** against R (and is reported against C);
3. **no new failure form** enters the class set (digit-normalised note keys);
4. **no crush** (G2).

Not a win, but a **mechanism pass** (the phase's honest middle case): (1) `off`
falls significantly while (2) the clean enclosure and the count do not.

The kill: if **no** compliant arm lowers `off`, the chuck hypothesis is refuted
and the phase reports compliance as a *gentler* closure only - with the algebra's
own statement of what would have to change (a pad material with `mu < 1`, a
3-jaw ring, or a positioning change).

## 5. Falsifiers (each is a registered prediction)

| id | registered prediction | fires if |
|---|---|---|
| **F1** | compliance **centres**: `off` falls from ~8.8 mm to ≥ 2x lower on T1 *or* T2 | no compliant arm's median `off` is at least 1.5x below R's |
| **F2** | the **counted** clean enclosure does **not** rise (the `mu > 1` residual + the roundness) | a compliant arm's clean rate exceeds R's by > 10 points pooled |
| **F3** | the **hard stop is load-bearing**: a pure-soft arm under-grips | (measured only if a pure-soft screen is run; if it is not, this row is `not measured`, never `passed`) |
| **F4** | **no crush** at the shipped cap | any leg's `sep@loss - dia < -15 mm`, or a clean row with `F > 4 cap` |
| **F5** | the design's own arithmetic: `off ~ (2*mu - 1)*s` = 1.1-1.9 s = 0.8-1.3 mm | the compliant arms' median `off` is > 2x the predicted value (the model's fidelity is the claim, so a 2x miss is a miss) |

## 6. What is *not* claimed before the cells

* No rate, count, or interval from any arm until the same-batch cells exist.
* The `[cage]` `off` field is a **new** instrument: it is two reads per attempt
  (the fruit pose and the cage's base pose, both already taken), so it cannot
  move the branch - but that is asserted from the code, not measured, and the
  replay guard above is what proves the control cells are unaffected.
* The two-line has **no path** to a non-`openarm` hand (`tasks.py:9543`), so the
  phase says nothing about it.  The hybrid canary (`accept_policy.sh`) builds its
  own `PickAndPlaceTask` with the default hand: **no path** either.
* `configs/` is untouched: nothing is licensed to ship (a compliant pad is a
  hardware change - a spring or a force-controlled finger - and the phase's job
  is to price it, not to adopt a simulator setting).

## 7. The battery, in order, and where it stops

1. **Replay** (2 cells): `C_s5`, `R_s5` -> `--same` against P108's `S_s5`,
   `E_s5`.  If both hold, P108's other six control cells are admissible.
2. **Screen** (1 cell): `T1_s5` - the mechanism (`off`, `pads`, `bat`, `F`).
   Stop here and write a negative if `off` does not move.
3. **Battery** (the rest): all four arms x four seeds, reported per seed and
   pooled.
4. **No-harm**: `scripts/selfcheck.sh`, `scripts/accept.sh` (every knob unset -
   the cage does not exist on the shipped path), `106`, `107`.
