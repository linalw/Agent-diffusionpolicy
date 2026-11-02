# P104 results - does more contact beat the pinch? (stage (ii), T1)

**VERDICT (first line).** **Yes, at the bar, but the pass belongs to the
4-contact form and it is a *static axial* pass.** The sustained axial break-away
is **2.0x the shipped pinch** with four contacts (21.8 / 26.6 / 26.0 N against
11.0 / 14.2 / 12.7 N, ratios **1.87-2.05x** at three fruit sizes) and **1.5x**
with three (18.1 / 18.9 / 19.7 N, **1.33-1.64x**, i.e. 2 of 3 clear the bar).
The analytic `n/2` holds to **within 10 %** in every cell. So the survey's kill
criterion **does not fire**: a hand's geometry is worth 1.5-2.0x on the static
axial wrench, and 4+ contacts - the topology of every candidate hand - clears it
at every size.

**But three measured caveats decide how far that goes, and they are the phase's
real product.**

1. **The 2 mm criterion the survey registered fails the 3-contact form.** Break
   at `clean_slip > 2 mm` reads **0.86-1.53x** for the tripod (it is 1.05x on the
   pear) because a 3+ contact grasp **re-seats** after 2 mm and carries on to its
   full capacity. The 4-contact still passes it (1.80-2.10x). The sustained
   (payload-lost) number is the one that matches "critical wrench".
2. **The static capacity is ~10-20x the load the cell applies**, and the cell
   still loses the payload. At the *operating* load (the payload's own weight,
   0.17-1.20 N) the difference is not 1.5x but **9-15x in creep**: the pinch
   slides **3.2-3.8 mm on the pear** (1.6-1.9x the 2 mm escape threshold, 30-36 %
   of the 10.5 mm lip) while the tripod slides 0.36-0.44 mm and the 4-pad
   0.15-0.25 mm.
3. **Under a moment the 3-contact advantage shrinks below the bar** (1.15-1.47x),
   and the lip - the *geometry* case the survey's hypothesis actually names -
   wins the static test trivially (>40 N) while the tree has **already measured
   that geometry as a net negative in the pipeline** (`logs/r8/A_RESULTS.md` §3).

**So: stage (ii) is justified at its letter and priced at 1.5-2.0x, and it is
necessary-not-sufficient.** A positive here does not promise a `cnp` conversion;
§7 says what would be needed to claim one.

---

## 0. The scope, before the numbers

This is a **fixture**, not a policy run: no arm, no scheduler, no attempt loop,
no camera. It measures one thing - the axial load at which a grasp loses the
payload - on the sim's own fruit meshes, the tree's measured pad geometry and
the tree's measured per-face pinch force. It does **not** test the approach, the
acquisition, a real hand's coupled fingers, or whether a `cnp` converts
(`METHOD.md` §1). The sim's pads are rigid and adhesion-free
(`logs/p42/SIM_LIMIT.md` §3), so by the survey's own rule (§3.3) this can
**falsify, never confirm**.

---

## 1. The analytic frame answers the bar by arithmetic

`analytic.py` / `analytic.txt`. Coulomb, independent point contacts, no peel, the
seat's normals perpendicular to the pull, `F_crit = n * mu * N_c`:

| form | n | `F_crit` at `mu_eff` 0.45 | at the measured pair 1.13-1.45 | ratio | clears 1.5x? |
|---|---|---|---|---|---|
| (a) two-pad pinch | 2 | 4.41 N | 11.07-14.21 N | 1.00 | - |
| (b) 3-contact tripod | 3 | 6.62 N | 16.61-21.32 N | **1.50** | **at its letter** |
| (c) 4-contact | 4 | 8.82 N | 22.15-28.42 N | **2.00** | **yes, +0.5x** |
| (d) two-pad + distal lip | 2 + block | not a friction quantity | | **unbounded** | yes, kinematic |

The ratio is `n/2` and **mu-free**, so the analytic half cannot fail; what it can
do is name the number to test. The fixture's job is to see whether the arithmetic
survives contact, and §3 says it does, to within 10 %.

**Scale, and this is the caveat the whole phase hangs on.** The shipped
lift/place cap is `a = 1.089 m/s^2`, so the cell's axial demand is `m(g+a)`:
**0.17 N** strawberry, **0.91 N** pear, **1.20 N** orange. The *conservative*
analytic pinch capacity is 4.41 N and the *measured* pinch capacity is 11.0-14.2 N
- i.e. **3.7-83x the demand** - and the cell still loses the payload on 17 of 80
attempts (`cnp`, P93). Whatever the escape is, **it is not a static capacity
deficit**, so the 1.5x bar tests a quantity that is not the binding term. §5
measures the term that is.

---

## 2. The fixture, and its manipulation check

Setup, geometry and procedure: `METHOD.md` §3. One row per cell in
`fixture.txt`; the aggregation is `p104_report.py` -> `fixture_table.txt`.

**Fidelity, four ways.**

* the pad face is the measured **61.000 x 84.902 mm** plate, its distal plane
  80.5 mm below the jaw centre, so the shipped lip (10.5 mm below the payload's
  equator) is reproduced;
* the per-face force is the measured **4.90 N** (9.75-9.9 N pinch over two faces,
  P41) applied through a **force-capped position drive** (k = 1e5 N/m, cap
  4.90 N), i.e. the shipped drive's saturated state;
* the payload is the pool's own mesh, mass and per-class friction draw;
* the seat: the pads' midpoint ends **0.2-3.8 mm** off the payload's centre in
  the two-pad cells - the same order as the real gripper's measured **1.4-4.7 mm**
  (`logs/p42/SEAT_CENSUS.md` §0). The pear is the worst (3.8 mm) because it is
  lobed, and it is the cell where the pinch is weakest - the same arm/fruit
  asymmetry the tree records.

**Manipulation check (per cell, printed in `fixture.txt`).** Every contact
carries the same normal force: **4.75-4.94 N** on the tripod, **4.80-4.90 N** on
the 4-pad, 4.89-4.90 N on the two-pad cells. This check is what forced the
interference change in `METHOD.md` A1, and its first reading is a result: at a
3 mm interference one tripod pad carried **3.09 N of 4.9** and the tripod was
worth **11.32 N against the pinch's 11.20 (1.01x)** - *a third contact that is
not loaded is worth nothing.*

---

## 3. The measurement: sustained axial capacity, 3 fruits x 3 repeats

`Fexit` = applied force + the payload's weight, at the tick the payload is lost
(30 mm). Mean of 3; the spread is in `fixture_table.txt`.

| form | pear 60.6 mm / 83.9 g | orange 65.8 mm / 110.2 g | strawberry 37.2 mm / 15.5 g |
|---|---|---|---|
| `pinch_plate` (the shipped pinch) | **11.03 N** (sd 0.78) | **14.21** | **12.69** |
| `pinch_tip` (matched control) | 11.19 (0.02) | 13.04 | 13.07 |
| `tripod` (3 x 120 deg) | **18.11** (0.15) | **18.90** (0.14) | **19.74** |
| `quad` (4 x 90 deg) | **21.81** (0.28) | **26.59** (0.05) | **25.97** (0.07) |
| `lip` (2 pads + distal ledge) | **>40** (no break) | **>40** | **>40** |

Ratios to the **shipped pinch** (plate) / the matched tip control:

| form | pear | orange | strawberry | mean |
|---|---|---|---|---|
| `tripod` | **1.64x** / 1.62 | 1.33 / **1.45** | **1.56x** / 1.51 | 1.51 / 1.53 |
| `quad` | **1.98x** / 1.95 | **1.87x** / 2.04 | **2.05x** / 1.99 | **1.97 / 1.99** |
| `lip` | **>3.63x** | **>2.82x** | **>3.15x** | - |

**The arithmetic holds within 10 %** (`analytic.txt` §4): predicted 1.50/2.00 vs
measured 1.45-1.64 and 1.87-2.05. No cell shows a new mechanism: **the pads do
not pry** (their radial travel at break is **0.06-1.52 mm** on every friction
form and 2.72 mm on the ledged strawberry, against an 80 mm stroke), and the
ratio is the friction count, as predicted. What
the pinch does show is the tree's **one-sided** signature at its break: on the
pear it reads **4.92 / 2.93 N** at the 2 mm event, i.e. one pad has unloaded -
the same single-sided contact `logs/p42/SIM_LIMIT.md` §0.4 records on 18 of 32
escape samples - while the 61 mm plate cell keeps **4.90-4.94 / 4.90-4.94**.

**Repeatability.** **4 of the 6 two-pad cells are bit-identical** across the
three repeats (sd 0.00 N); both pear cells are not - the plate control reads
**10.32 / 10.66 / 12.11 N** (sd 0.78) and the tip control 11.16-11.20 - because
the lobed pear settles into a seat that differs per close. That is a real
property of the fruit, not of the fixture's noise floor, and it is the reason the
ratios are quoted per fruit and never pooled.

**The registered criterion vs the sustained one.** Break at `clean_slip > 2 mm`
(the survey's own wording) reads, for the tripod, **1.05x / 0.94x / 1.48x**
against the tip control (**1.06 / 0.86 / 1.53** against the plate) - it *fails*
the bar - while the sustained capacity passes at 1.33-1.64. The reason is
mechanical and visible in the rows: after 2 mm the tripod's payload **re-seats**
and the force keeps rising to 18-20 N, whereas the pinch's 2 mm is already its
end (11.11 -> 11.19 N). **A 2 mm slip is recoverable with 3 contacts and terminal
with 2**, so the criterion measures the wrong event for the form it is testing.
The 4-pad passes both (F2mm **1.75-2.10x**, Fexit 1.87-2.05x).

---

## 4. The verdict against the bar

* **`quad` (4 contacts): PASS, 1.87-2.05x**, at every fruit size, against both
  controls, and under both the registered 2 mm criterion (1.75-2.10x) and the
  sustained one. This is the topology of every candidate in §3.1 of the survey
  (ORCA 17 DoF, LEAP 16 DoF/4 fingers, Allegro 16 DoF/4 fingers, DexHand 19 DoF).
* **`tripod` (3 contacts): at the bar, not above it** - 1.51-1.53 mean, 2 of 3
  fruits clear it against either control, and it **fails the registered 2 mm
  criterion** (0.86-1.53). A *three-finger* hand would sit on the line, not over
  it.
* **`lip`: trivially over** (>2.8x, unbounded inside the ramp) - and it is not a
  hand, it is a pad-geometry change the tree already ran: the scoop's ledges
  **bat the payload** (no-contact 2 -> 9 of 15, battery 6/20 x2,
  `logs/r8/A_RESULTS.md` §3). **A static pass that the pipeline already lost** -
  the cleanest illustration of §8's caveat 2.

**So the survey's kill does not fire, and the number that prices stage (ii) is
1.5-2.0x on the static axial wrench (1.87-2.05x for a 4-contact hand).** What
the pass buys is permission to spend the next decision (the architecture work in
§4, or the §3.2 bench T2), not a claim that `cnp` falls.

---

## 5. The quantity that actually separates: creep at the operating load

Before the ramp starts, the payload hangs on the grasp under **nothing but its
own weight** - 0.17 / 0.91 / 1.20 N, i.e. exactly the cell's demand. Its
displacement over the 0.75 s settle:

| form | pear | orange | strawberry |
|---|---|---|---|
| `pinch_plate` | **3.20 mm** | 0.85 | **2.68** |
| `pinch_tip` | **3.84** | 0.22 | 0.79 |
| `tripod` | **0.42** | 0.36 | 0.11 |
| `quad` | **0.25** | 0.15 | 0.11 |

On the pear - the fruit the tree's own escape census is cleanest on
(`logs/p75`, `logs/p76`) - the two-pad pinch **cannot statically hold the load
the cell applies without sliding 3.2-3.8 mm**, which is **1.6-1.9x the 2 mm
`clean_slip` escape threshold** and **30-36 % of the 10.5 mm lip**, while 3 and 4
contacts slide 0.11-0.42 mm. The ratio there is **9-15x**, not 1.5x.

**Why this is the number that matters, and its limit.** It is the *displacement*
at the *demand*, which is the quantity that carries a payload toward the lip
during a carry - and it is consistent with two things the tree already measured:
(i) the escape's onset is early in the leg and the pads are **not** pried
(`logs/p75`: one pad 0-8.5 N, the free pad at its stop), and (ii) P75's
"**inherited expulsion**" class - 2 of 6 escapes start with the payload already
single-sided at the place leg's first tick. The limit: the fixture's pads
**follow the payload inward** as it slides down the taper (a force-capped drive
with a deep target), which is *generous* to the pinch - the real close **freezes
the gap** at the fruit's width, so a real pad cannot keep 4.9 N as the fruit
narrows. **Every fidelity error in this direction makes the pinch look stronger
than it is**, so the ratios are a lower bound. This does not license a rate
claim; it says the mechanism the hand attacks is real and is *larger* at the
operating load than at the break-away.

---

## 6. The moment case: where the 3-contact advantage shrinks

The pipeline's escape is not a pure axial pull: the payload hangs off a
two-point contact line, so the load carries a moment. Pulling **20 mm off-axis**:

| form | pear | orange | strawberry |
|---|---|---|---|
| `pinch_tip_moment` | 8.53 N (0.76 of its axial) | 10.08 (0.77) | 12.94 (0.99) |
| `tripod_moment` | 9.78 (0.54) | 13.39 (0.71) | 18.99 (0.96) |
| **ratio** | **1.15x** | **1.33x** | **1.47x** |

**The tripod loses more of its capacity to the moment (46 % on the pear) than the
pinch does (24 %), and its advantage falls from 1.5-1.6x to 1.15-1.47x - below
the bar on 2 of 3 fruits.** A slipping payload tips, and on three contacts a tip
unloads one of them (measured: the contact forces at break go 4.92/4.91/**4.14**
N in the axial cell and 3.57/**5.06**/3.64 in the moment cell). So the hand's win
is **axial-specific**: if the real load is moment-dominated, a 3-contact grasp is
not the answer, and the 4-contact's advantage (which the fixture measures at
1.87-2.05x axially) is the one to test under load next.

---

## 7. Two by-products, recorded because they are checkable

**(a) The pair friction is the *average*, not the minimum.** The break-away
implies `mu_app = Fexit / (n * N)` = **1.05-1.45** (means 1.27-1.30) across every
form, i.e. consistent with PhysX's default *average* combine of the pad's
authored 2.0 with the fruit's own draw (0.52-0.81 -> 1.26-1.41) and **not** with
the *minimum* (0.52-0.81). `scene.py:_add_physics_material`'s comment says "PhysX
default friction combine takes the *minimum* ... which is exactly the friction
limit the A2/A8 carry slide lives under" - **the fixture measures the average**,
so the effective grip is ~2x that comment's assumption. This matters for the
motion budget (`mu_eff = 0.6 * 2.0 = 1.2` is then *not* conservative against the
physical pair, it is about right) and it makes the analytic table's `mu_eff`
0.45 column **2.3-3.2x pessimistic** against the measured pinch. It does **not**
change any ratio (they are mu-free). Recorded, not acted on: no `src/` edit, and
the comment fix belongs to a phase that re-measures the cone.

**(b) The shipped pinch is 11.0-14.2 N, not 4.4 N.** Against `mu_eff` 0.45 the
analytic pinch is 4.41 N; the measurement is 2.5-3.2x that, and within 10-15 % of
the *average-combine* prediction (12.30 N). So the tree's conservative
`mu_eff` is genuinely conservative by ~2.5x, and every measured "friction margin"
quoted against it (P40's 1.20x -> 2.70x) is conservative by the same factor.

---

## 8. What this prices, and what it does not

**Priced.** The static axial break-away of the shipped pinch is **11.0-14.2 N**
at the measured 4.9 N/face; 3 contacts buy **1.33-1.64x**, 4 contacts **1.87-2.05x**,
a distal lip **>2.8x**; the analytic `n/2` holds within 10 %. Stage (ii)'s T1 bar
(1.5x) is met by the 4-contact form at every fruit and by the 3-contact form at
its letter on 2 of 3; **the kill does not fire.**

**Not priced, and each is a real risk the next decision must carry.**

1. **The binding term is not the static capacity** (§1, §5). The measured pinch
   capacity is 10-20x the demand and the cell still loses 17 of 80 attempts. A
   1.5-2x improvement in a quantity that is already 10x oversized does not
   *mechanically* convert a `cnp` - what converts is the **creep** (§5, 9-15x) or
   the **moment** (§6, below the bar). So the honest reading is: the hand's
   *geometry* is worth having, the *1.5x bar* is the wrong scale, and the number
   that should gate a purchase is a **creep-under-load** endpoint, not a break.
2. **The lip case is a warning, not a candidate.** It wins the fixture
   unboundedly and the tree already measured the same geometry as a **negative**
   in the cell (`logs/r8/A_RESULTS.md` §3: the ledges bat the payload, 2 -> 9
   no-contact of 15). A static win is not a pipeline win - which is exactly the
   "necessary, not sufficient" clause, measured rather than asserted.
3. **The approach, the acquisition and the policy are untouched** - 4 of the 11
   failures in P102's join are acquisition failures that **no contact count can
   reach**, and a 1 kg hand in front of a 240x424 head camera needs a wrist view
   (`docs/PLATFORM_SURVEY.md` §1.1, §4). A hand's business case is the *74 %*
   `cnp` half, and this phase prices only one mechanism inside it.
4. **A real hand is not `n` prismatic pads** (coupled tendons, soft contacts,
   12 N class per fingertip). The fixture's 4.9 N/face is the fair comparison and
   also the ceiling of what it can say.

**The next decision it feeds.** With §3.3's T1 meeting its bar for a 4-contact
hand, the gate the survey set is satisfied; what it *does not* do is make the
purchase safe. The two cheapest things that would: (i) a **creep** endpoint at
the operating load (a 0.2 m/s carry of 5 s at the shipped caps, scored on the
payload's displacement in the hand frame - the metric and the threshold already
exist as `clean_slip > 2 mm`, `logs/w8/B_RESULTS.md`), and (ii) the §3.2 **T2
bench** (one GelSight, a printed 3-finger cradle, a luggage scale, ~$1,020),
which is the only test that can *confirm* rather than falsify - and it is now
cheaper than the hand.

---

## 9. Files, pins, and what was not run

**Files** (`logs/p104/`): `METHOD.md`, `RESULTS.md`, `fixture_probe.py`
(md5 `3f18b908`), `run_p104.sh`, `fixture.txt` (md5 `3fbb48f5`, 63 rows),
`fixture_table.txt`, `analytic.py`, `analytic.txt` (md5 `56a7e260`),
`p104_report.py`; this file.

**Tree pins** (unchanged by this phase - it is a fixture in `logs/`):
`tasks.py` `9e3e657b`, `scene.py` `472bfb6c`, `control.py` `9384ff4f`,
`fruits.py` `dcabe16b`, `meshes.py`, `assets.py` `540406fa`; `configs/motion_reference.json`
= `..._twoline.json` = **`30fb99f8`**, `..._single.json` = **`8952c320`** - all
untouched. `git status --short` on `src/` and `configs/` is empty.

**Run.** `bash logs/p104/run_p104.sh` (7 app sessions, 3 fruits x 3 repeats,
**2 m 51 s** on this box, 63 rows, no wedge); `python3 logs/p104/analytic.py`;
`python3 logs/p104/p104_report.py`; `scripts/selfcheck.sh`.

**Not run, deliberately.** No arm, no attempt, no scheduler, no policy, no
`accept.sh` (nothing shipped, so nothing to gate); no `190` two-line gate; no
`configs/` re-record; no recollection. The **moment** cells were added after the
axial battery (deviation A3) and the `lip` cells never break inside the ramp
(A4) - their ratios are bounds.
