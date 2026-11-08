# P132 pre-registration - the serrated pad face, fixture first

**Registered after the fixture's build smoke, before the final 48-cell battery's
table was analysed.** The fixture's shapes and parameters are the owner's brief
(5 ridges, 1.0 mm high, 8 mm pitch, 60 deg flanks; `serr45`; `lip20`), and the
promotion rule is the brief's; the only free interpretations are declared below
(D1-D3). The build smoke read 2 profiles on the pear (`logs/p132/smoke1.log`) and
is what found the facet-frame defect; the final battery was then run once and its
table is deterministic from `logs/p132/fixture.log`. Nothing in the rule moved
after the battery.

Pins at registration: `tasks.py` **`76dbfc6b`**, `rl_env.py` **`b11113fb`**,
`scene.py` **`b3bf8067`**, `assets.py` **`24d29679`**, `fruits.py` **`c8f19228`**,
`cage_hand.py` **`0f56b2ff`**, `configs/motion_reference.json` =
`..._twoline.json` = **`30fb99f8`**, `..._single.json` = **`8952c320`**,
checkpoint `moe_v13s` **`61da390a`**. Nothing is adopted, no default changes,
`configs/` is untouched.

## 0. The question

The loaded-slide class is **75 % of the shipped two-line's failures** (`cnp`), the
class ceiling is **93.8 %**, and the shipped cell is **58/80 = 72.5 %** at four
seeds (`logs/p93`, `logs/p120`). The record's static measurement of the pinch says
the escape is not a capacity deficit (`Fexit` 9.20-14.12 N against the 1.2-1.7 N
demand) and not a load-axis creep (`dz` -0.03..+0.03 mm; the total creep is a
lateral seat shift, P117/P129). P75's mechanism is a **dynamic pry**: a 0.3 mm
slide, the force collapses, the servo opens the gap; the payload walks along the
tool axis. **The hypothesis**: ridges **perpendicular to that walk** (across the
pad's width, spaced along the tool axis) present a normal against it, like a
ratchet. P117's grooves run the other way.

## 1. The faces (the brief's, with the declared readings)

| profile | geometry |
|---|---|
| `flat` | the shipped 61.0 x 84.9 mm plate, 10 mm facet - the control |
| `serr` | 5 ridges, **1.0 mm** high, **8 mm** pitch, **60 deg flanks**, the ridge line across the pad (y), the pitch along the tool axis (z) |
| `serr45` | the same ridges at **45 deg flanks** (D1) |
| `lip20` | the flat face with a **20 mm** distal lip (9.5 mm more face below the equator; fixture-only - the belt forbids it on the hand) |

**D1**: the brief's "`serr45` (the same ridges at 45 deg)" is read as the **flank
angle** (a milder tooth), not a 45-deg rotation of the ridge line. A rotated-ridge
variant is not registered and not built.

**D2**: the **sustained walk** is the **load-axis component of the payload's
displacement during the 0.75 s `m(g+5.83)` hold**, measured from the start of the
hold (`walk`). The weight settle's load-axis component (`settle_dz`) is reported
separately (P104's creep). The *total* displacement (`creep_op`) and the *lateral*
part are reported and **not** promoted (P117's dead end).

**D3**: the "30 mm fruit" crush bound is read on the pool's smallest class
(**34.4 mm lychee**, then the 37.2 mm strawberry); the fixture cannot draw a 30 mm
fruit, and the crush guard is the P76 rule (`contact span - dia >= -15 mm`) plus
the delivered 4.90 N force cap.

## 2. The fixture gates (before any table is read)

**A1 support (gate).** Two dedicated zero-pad-force cells: weight-compensated 200
ticks -> drift **<= 0.05 mm**; no compensation 40 ticks -> fall **>= 20 mm**. A
passive support is not admissible for a grasp fixture (P117's inverse form). If A1
fails, **no table is read and the phase reports the fixture failure**.

**A2 manipulation (gate).** Every real cell must load **2 pads** at 4.54-4.99 N
of the 4.90 N cap (P117's own gate). A cell with one pad is not a pinch and is
excluded from the ratios and named.

**A3 facet geometry (gate, added by this phase).** Each authored facet's world
extent must be **10 mm on x** (the thickness) and its long/width axes on y/z;
P117's rig had one 62 mm block per pair (METHOD §2). The corrected rig's flat is
the same-batch control.

## 3. The promotion rule (the brief's, verbatim)

A shape is promoted **only if all three hold**:

1. **`|walk| <= 0.6 x |walk(flat)|`** on every fruit (the class's own direction);
2. **`F2mm >= flat` and `Fexit >= flat`** on every fruit (the break-away is not
   below flat);
3. **no crush**: the commanded contact span is `>= dia - 15 mm` and the delivered
   force is the 4.90 N cap (no cell above it).

**The floor clause**: if the flat's `|walk| <= 0.05 mm` (the rig's support
tolerance, and P117's measured resolution), the first clause is **not resolvable**
and **cannot be satisfied by evidence** - a shape's 0.01 mm against a 0.00 mm
control is not a reduction. In that case no shape promotes, regardless of the
break-away column; the phase reports the fixture's limit as the finding.

## 4. If a shape promotes

Build it on the **OpenArm hand's fingers** with the existing
`scene._add_contact_faces` machinery, **default off** (`FRUIT_FINGER_FACE` unset =
shipped), the collider keeping the **10.5 mm lip and the 80.5 mm distal plane**
(no shape below the shipped distal plane; the belt is there). Then the two-line
cell: seeds **5/6 x 20 attempts**, the shipped scenario, **same-seed controls on
the same tree** (a pad asset moves the collider set - P71's rule - so compare
**budgets + class + count**, never a fingerprint). Endpoints: the **placed count**
and the **loaded-slide class** (`cnp` + `clean_slip > 100 mm` legs). Guards:
crush (`sep@loss - dia`), landing (`on_belt`), descent budgets (not re-tuned),
and the acceptance with the knob unset (**8/10 + `fingerprint: matches` + 421/421
identical to `logs/p127/accept_restored.log`**).

## 5. If no shape promotes

**No build, no cell.** Publish the negative and **close the pad-asset lane**: the
decision book then has no geometric route left but the workstation, which the
owner's constraint (the dynamic scattered pipeline must not be stopped, diverted,
gated or paused) excludes. The report must still name the **dynamic residual**:
the class is a dynamic pry and the fixture is a static pull, so the negative is a
statement about the *static* pad-asset lane, not a proof that no dynamic shape
could ever act.

## 6. Falsifiers

* **F1**: the support proof fails -> the phase reports the fixture, no table.
* **F2**: the flat's `|walk| > 0.05 mm` and a shape beats it by >= 40 % -> the
  first clause is live; the shape promotes only if the other two clauses hold.
* **F3**: a promoted shape cannot be built inside the shipped distal plane (the
  lip/height) -> the phase reports the mechanism and does not build.
* **F4**: a shape's only gain is the total/lateral creep -> **not a promotion**
  (P117's dead end), recorded as such.

## 7. What would make this negative wrong

A **dynamic** cell of the serration, built blind, is the only test that could
overturn it. It is not registered here because the phase's rule requires the
fixture's promotion first, and the fixture's sustained walk is at the floor. The
named next owner decision, if the dynamic residual matters, is that cell - with
the shape's 2 mm break-away already priced on the small class (0.42-0.76x flat).
