# P12-A implementation: the property-realism batch (`FRUIT_PHYSICS_REAL`), offline

Status: **implemented, offline-verified** (branch `p-supply`, 2026-10-18). **No simulator run in
this lane** - the Tier-A battery is a separate lane (`logs/p12/run_battery.sh`, written by the
battery lane: `FRUIT_PHYSICS_REAL=1` on the two-line anchor, seeds 11/5/23). Writes:
`src/fruit_sorting/meshes.py` (the real-property table + the switch + the resolvers),
`src/fruit_sorting/fruits.py` (the mass lookup, the restitution band, the material authoring),
`logs/p12/` (this record, `check_physics_real.py`, `executed_compare.py`, `smoke_create_pool.py`,
the evidence logs, `WORKLOG_entry.md`). No commit by this lane; no branch operation; `Paper/`,
`datasets/`, `checkpoints/` untouched; `tasks.py` untouched (its md5 is unchanged, so
`rl_env.py`'s `TASKS_MD5` pin needs no follow - the mission's "it should not" holds).

Reference: the P11-A audit `logs/p11/A_PHYSICS_AUDIT.md` sections 1-2 and 5b (the measured real
values + the provenance of every shipped value); the owner directive (2026-10-18) that the
two-line anchor is the only re-measured reference and the physics-side iteration is unblocked -
**no full re-baseline in this lane**.

## 1. The diff

| file | md5 (new) | md5 (was, HEAD `0feaf39`) | change |
| --- | --- | --- | --- |
| `src/fruit_sorting/meshes.py` | `10fa005e4f8ebcbb087c37643dfe3dc1` | `f980df575f18cc1a4a389d61fbed3d42` | +85/-1: two default-0 `FruitShape` fields, the P12-A value table, the switch + resolvers |
| `src/fruit_sorting/fruits.py` | `7283e4bf92425ffc81bcd3d64d72ad00` | `f5671a65d6f72eb69a81e12ac6e0bf53` | +96/-17: the restitution band + damping + `_author_fruit_physics_material` + the two authoring sites + the banner |
| `src/fruit_sorting/tasks.py` | `810658b802d22bbd63013726fc78af81` | same | **untouched** (the P11-C.3 baseline; the `TASKS_MD5` pin still matches) |
| `src/fruit_sorting/rl_env.py` | `9a2c38721b32f0af91371ca3e8809196` | same | **untouched** (no pin follow needed) |

**Hunk 1** (`meshes.py`, `FruitShape`): two new default-0 fields -

```python
    #: kg/m^3 under `FRUIT_PHYSICS_REAL=1` (P12-A): the measured real density
    #: (`logs/p11/A_PHYSICS_AUDIT.md` section 2.1) or a documented estimate.
    #: 0.0 = no real value, the shipped `density` stands.
    density_real: float = 0.0
    #: N/m under `FRUIT_PHYSICS_REAL=1` (P12-A): the Hertzian whole-fruit
    #: contact stiffness at 1 mm of compression (audit sections 2.2/5b.1) or a
    #: size-and-firmness estimate. 0.0 = the shipped rigid contact.
    contact_stiffness_real: float = 0.0
```

The shipped `density` field and every other field are untouched (verified against HEAD, section
4.4).

**Hunk 2** (`meshes.py`, the table): each of the eight `FRUIT_SHAPES` entries gains
`density_real=` and `contact_stiffness_real=` (section 3's table), preceded by a comment block
naming the audit sections, the FULL/abstract/est. provenance per class, and the kept-0.82 note.

**Hunk 3** (`meshes.py`, after the table): the switch and the resolvers -

```python
_PHYSICS_REAL_RAW = os.environ.get("FRUIT_PHYSICS_REAL")   # read once at import

def physics_real() -> bool: ...            # the exact `== "1"` parse
def fruit_density(shape, real=None): ...   # shipped, or density_real when on
def fruit_contact_stiffness(shape, real=None): ...  # 0.0 (rigid), or the class value when on
```

**Hunk 4** (`fruits.py`, after `tune_contact_body`): the restitution band
(`_RESTITUTION_SHIPPED = (0.02, 0.2)`, `_RESTITUTION_REAL = (0.35, 0.50)`),
`REAL_CONTACT_DAMPING = 80.0`, `restitution_range()`, and the single material authoring helper
`_author_fruit_physics_material(stage, prim, path, friction, restitution, stiffness)` - the
shipped statements verbatim, plus

```python
    if stiffness > 0.0:
        contact = PhysxSchema.PhysxMaterialAPI.Apply(phys_material.GetPrim())
        contact.CreateCompliantContactStiffnessAttr().Set(float(stiffness))
        contact.CreateCompliantContactDampingAttr().Set(float(REAL_CONTACT_DAMPING))
```

**Hunk 5** (`fruits.py`, both authoring sites): the mass uses `fruit_density(shape)` in the
unchanged `density * 4/3 pi r^3 * 0.82` expression (the `_create_fruit` preliminary
`700.0`-literal line is untouched), and the inline material block becomes the helper call with
`self.rng.uniform(*restitution_range())` + `fruit_contact_stiffness(shape)`. The restitution
draw stays at the same statement position in the rng stream (the helper consumes no rng), so
the knob-off rng stream is unchanged (section 4.3).

**Hunk 6** (`fruits.py`, `create_pool`): one banner line, only when the knob is on -
`[physics] FRUIT_PHYSICS_REAL=1: real class densities + restitution 0.35-0.50 + per-class
compliant contact (P12-A)`; the knob-off log stream is byte-identical (no line).

## 2. The knob semantics

* **Name / default**: `FRUIT_PHYSICS_REAL`, default `0` (unset) = the shipped values. The exact
  `== "1"` parse the other `FRUIT_*` flags use: `0`/unset/any other string stays shipped.
* **Resolution**: read **once at import** in `meshes.py` (`_PHYSICS_REAL_RAW`), because this
  gates build-time physics authoring - the switch cannot change mid-run. `fruits.py` never reads
  the env; it consumes `physics_real()` / the resolvers. The `real=` argument on the resolvers is
  an offline-stub seam only (the runtime call sites never pass it).
* **Scope**: every fruit, all paths (single arm, two-line, policy, collector). The knob is
  **not** scoped to the two-line - it is a scenario-level physics change; the two-line anchor is
  the measurement reference per the owner directive, not a scope rule.
* **Effect (all four items of the mission)**:
  1. **masses**: `fruit_density(shape)` replaces `shape.density` at both mass sites
     (`_create_fruit`, `rescale`); the formula (`x 4/3 pi r^3 x 0.82`) is unchanged (section 3);
  2. **restitution**: the per-fruit draw becomes `uniform(0.35, 0.50)` (section 3);
  3. **fruit-side compliant contact**: each fruit's material gets
     `physxMaterial:compliantContactStiffness` = the class value and
     `physxMaterial:compliantContactDamping` = 80 Ns/m (the audit's option 5b.1);
  4. **finger side**: **left as shipped** (`FRUIT_FINGER_COMPLIANCE=30000`,
     `FRUIT_FINGER_CONTACT_DAMPING=80`, `assets.py`/`scene.py`). Why not scaled: the finger
     material is process-wide (one env var, authored by `scene.py` before the fruit pool
     exists), so a per-class scaling is not expressible at that point, and the material-pair
     combination rule (series vs one side governing) is a PhysX question the audit left
     unverified offline (audit section 6) - the battery's traces measure the pair instead of
     guessing here. If PhysX combines by series, the pair is already fruit-dominated
     (tomato 3.5 kN/m, apple 14.2 kN/m effective).
* **Observability**: the one banner line when on (section 1, hunk 6). Nothing else changes in
  the log stream; no control-loop read is added (all resolution is build-time; `rescale` runs
  in the recycler, not the control loop, and reads the cached constant).

## 3. The value table + sources/estimates

Reference: `logs/p11/A_PHYSICS_AUDIT.md` sections 2.1 (density), 2.2/5b.1 (stiffness), 2.5
(restitution). "FULL" = the complete paper read in the audit; "abstract" = abstract only;
"est." = no audited source - a documented estimate.

**Densities [kg/m^3] and contact stiffnesses [N/m at 1 mm of compression]**

| class | shipped density | real density | source | shipped stiffness | real stiffness | source |
| --- | --- | --- | --- | --- | --- | --- |
| apple | 850 | **840** | FULL - Jia et al. 2026 (model density) | rigid | **27000** | model - Hertzian (E 2.091 MPa, nu 0.35, R 33 mm) |
| tomato | 780 | **960** | FULL - Geasa & Hassan 2022 (0.96 g/cm^3) | rigid | **4000** | model - Hertzian (E 0.30 MPa, nu 0.45, R 26.5 mm; the audit's 3.9 kN/m) |
| orange | 900 | **1000** | abstract - 0.97-1.03 g/cm^3, midpoint | rigid | **13000** | est. - firm rind |
| peach | 820 | **1000** | est. (audit has mass 137 g @ ~60 mm only) | rigid | **19000** | E 1.53 MPa FULL; nu 0.35/R 30 mm assumed |
| pear | 880 | **950** | est. | rigid | **15000** | est. - firm flesh |
| kiwi | 900 | **1050** | est. | rigid | **7000** | est. - soft flesh |
| lychee | 850 | **1000** | est. | rigid | **23000** | est. - hard pericarp |
| strawberry | 700 | **950** | est. | rigid | **3000** | est. - very soft |

* The estimated stiffnesses use the same Hertzian form the audit used,
  `k(1 mm) = 2 E* sqrt(R d)` with `E* = E/(1-nu^2)`, an assumed `E` per firmness tier and
  `R` from the class's mid-diameter (`assets.py:400-417`).
* The estimated densities sit in the mission's 950-1050 kg/m^3 band. **Peach caveat**: the
  audit's own mass/diameter reading (137.37 g at ~60 mm) would imply ~1215 kg/m^3 if a sphere
  is trusted, so the peach estimate is deliberately conservative; with the kept 0.82 factor a
  1000 kg/m^3 peach is 92.7 g at 60 mm against the measured 137 g.
* **The mass formula is unchanged** (the mission's optional per-class volume proxy was not
  taken): `density * 4/3 pi r^3 * 0.82`. The real densities narrow but do not close the mass
  gap - apple ~12 % light at 81 mm (194 g vs 220 g), tomato ~27 % at 53 mm (61 g vs 84 g),
  peach ~32 % at 60 mm (93 g vs 137 g) - the 0.82 sphere-shape discount is the residual, and
  the per-class volume proxy is the named follow-up if the mass itself becomes the lever.
* **Restitution**: shipped `uniform(0.02, 0.20)` -> real `uniform(0.35, 0.50)`. Source: apple
  vs apple COR 0.4 and apple vs PE bin COR 0.5 (Jia et al. 2026, FULL; audit section 2.5). No
  per-class COR was sourced, so one band is used for every class. The audit's own note (3.4):
  restitution does not drive the launch, it only shapes the bounce after a fall.
* **Compliant-contact damping**: 80 Ns/m for every class (the audit's option 5b.1 suggests
  matching the finger's 80 Ns/m). It is ~2x the 0.1 kg critical value for the softest class
  (tomato) and ~0.77 of critical for the stiffest (apple) - overdamped-to-mildly-underdamped,
  the stable side.

## 4. The verification (offline only)

1. `python3 -m py_compile` on `meshes.py`, `fruits.py`, `check_physics_real.py`,
   `executed_compare.py`, `smoke_create_pool.py`: OK.
2. **The new stub** `logs/p12/check_physics_real.py` (**PASS, 40/40 checks**; archived output
   `logs/p12/10_stub_check.txt`) pins the four required layers:
   * *source*: the env is read exactly once into the cached constant with the exact `== "1"`
     parse; `fruits.py` never reads it directly; both mass expressions are the shipped formula
     modulo `fruit_density(shape)` (the 0.82 discount present exactly twice); the inline
     `uniform(0.02, 0.2)` draws are gone (both sites call `restitution_range()`); one helper
     definition + two call sites; the compliant attributes are authored in exactly one place;
     the helper consumes no rng; the banner is gated on `physics_real()`.
   * *the value table under both settings*: all 8 classes; the shipped table pinned to the
     audit's F4 values; the real table and the stiffness table pinned; `fruit_density` /
     `fruit_contact_stiffness` off = shipped / on = real; the restitution bands and the
     byte-identity of both draws vs the literals; the mass arithmetic at a pinned diameter
     (tomato 59 mm: 68.8 g off = the literal 780 kg/m^3 mass; 84.7 g on).
   * *the import-time resolution (subprocess)*: unset -> off (tomato 780, apple stiffness 0.0,
     restitution 0.02-0.2); `0` -> off; `1` -> on (tomato 960, apple 27000, 0.35-0.5);
     `true` -> off (the exact parse); and the read-once cache (setting the env after import
     does not move the switch).
   * *the authored material (the REAL helper, recording fakes)*: knob off authors exactly the
     three shipped attributes (static/dynamic friction + restitution) and never applies
     `PhysxMaterialAPI`; knob on adds the compliant stiffness/damping with the class values
     (apple 27000/80, tomato 4000/80) and applies it exactly once per fruit.
3. **The one-off executed old-vs-new identity** (`logs/p12/executed_compare.py`, archived
   `logs/p12/10_executed_compare.txt`): the pre-change inline material statements of **both**
   authoring sites (extracted from `HEAD` via `git show`) and the pre-change mass expression
   were exec'd against the same recording fakes with identically seeded rngs. Result:
   **execution-identical** on all three - the attribute dicts (including the restitution draw
   0.07828989766996923), the bindings, the zero `PhysxMaterialAPI` applies, and the tomato mass
   (0.06878014900033248 kg at 59 mm). This is the strongest offline form of the byte-inertness
   claim; it is a one-off (it compares against `HEAD`, so it must not be re-run after a commit
   of this change) and is not a permanent gate.
4. **The `FRUIT_SHAPES` field comparison vs HEAD** (same log): all 11 shipped fields of all 8
   classes - including the generated profile curves - are identical to HEAD; the only
   additions are `density_real`/`contact_stiffness_real`. **0 mismatches.**
5. **The end-to-end smoke** (`logs/p12/smoke_create_pool.py`, archived
   `logs/p12/11_smoke_create_pool.txt`): the REAL `create_pool()` -> `_create_fruit` path
   (16 fruit, the shipped scatter pool) executed with generic pxr fakes, in both settings.
   Knob off: 16/16 masses equal the shipped-formula expectation, 16 materials with exactly the
   3 shipped attribute keys, **0** `PhysxMaterialAPI` applies, no banner. Knob on: 16/16 masses
   equal the real-density expectation (the same drawn diameters - the pool draws are
   unchanged), 16 compliant materials, 16 applies, the eight recorded stiffnesses are exactly
   the class table (3000-27000), the banner printed once. `RESULT: PASS` both runs.
6. **`scripts/selfcheck.sh`** (`SELFCHECK_LOG=logs/p12/selfcheck.log`): **PASS, 0 failures, 1
   skipped** (motion budgets - it needs a run log and this lane made no simulator run). The
   supply-scatter leg imports the modified `fruits.py` with stubbed pxr and passes.
7. **The pin check**: `rl_env.TASKS_MD5 == md5(tasks.py)` and `tasks.py` is still the
   P11-C.3 baseline `810658b802d22bbd63013726fc78af81` (pinned in the stub).

## 5. The battery (deferred, a separate lane)

`logs/p12/run_battery.sh` (written by the battery lane) runs the **two-line anchor** -
`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1`
`FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25 ATTEMPTS=20 SEED=11/5/23`, with
`FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1` -
against `FRUIT_PHYSICS_REAL=1`, three seeds. What it must measure (the lane's to fix, listed
here as the named expectations):

* the **carry class** and its mechanism: the W8-B `clean_slip` window (the loaded-slide
  signature, the re-seats), and the P10-E no-grasp class split - the audit's whole point is
  that a compliant fruit absorbs a squeeze instead of converting it into motion, so the
  ejection class (falls ~1.3 m below the belt, `|v|max` 4.78-5.05 m/s) is the endpoint;
* the **mass effect**: the fruit are heavier (e.g. tomato +23 %, strawberry +36 %), so the same
  interference carries more momentum;
* the **motion budgets** (`scripts/105_motion_regression.py`, the two-line gate
  `scripts/190_twoline_gate.sh`) with a **new reference if the branch moves** - a physics change
  is a new scenario per AGENTS.md section 2;
* the **pair-combination readout** (the finger stays 30 kN/m): the contact penetration/force
  in the trace tells whether the series response materialised;
* the **knob-off control**: the two-line replay must be the pre-change record modulo reporting
  rows (the P12-A default is off, so the control is the shipped branch by construction).

Per the owner directive there is **no full re-baseline in this lane**: the single-arm
acceptance, the motion references, the collectors/datasets/checkpoints and the policy canary
are only re-recorded if the batch is ever adopted (audit section 5b.4 lists the whole lineage).
Provenance gap worth noting for the battery lane: `meshes.py` is not in `rl_env.py`'s
`_MANIFEST_SOURCES` nor in the collector manifest's source list (`fruits.py` is, and it changes
with P12-A), and no manifest field records `FRUIT_PHYSICS_REAL` - if the batch reaches a
collection, the manifest should gain a `collection.physics_real` field (the W7-C.1
`park_early` pattern) and `meshes.py` should join the source list.

## 6. Honest limits

1. **No simulator run** - every claim here is static + executed-statement evidence; the
   contact behaviour (the pair response, the ejection class, the falls) is the battery's to
   measure.
2. **The material-pair combination rule is unverified offline** (audit section 6): whether the
   fruit-side stiffness combines with the finger's 30 kN/m by series, min or max decides the
   effective pair stiffness. The finger is deliberately left shipped; the battery's traces
   decide.
3. **The contact frequency for the firm classes**: under the series reading the effective pair
   is ~3.5 kN/m (tomato, ~33 Hz at 0.1 kg) to ~14.2 kN/m (apple, ~59 Hz); under a min-rule
   reading the apple sits at ~81 Hz, above the 120 Hz step's resolvable band the repo notes
   (the shipped finger contact was already at ~87 Hz). The audit's named escape hatch
   `FRUIT_SUBSTEPS=4` remains available to the battery if a firm-class contact misbehaves.
4. **The mass gap is narrowed, not closed** (section 3): the 0.82 factor is the residual; the
   per-class volume proxy is a named follow-up, not taken here.
5. **Restitution is post-fall only** (audit section 3.4): the 0.35-0.50 band does not drive the
   launch; it shapes the bounce and the post-release roll.
6. **The knob-off byte-inertness is static + executed evidence** (sections 4.3/4.4/4.5), not a
   simulator replay: the shipped path is unchanged in code path, arithmetic, rng stream and
   authored attributes, and the battery's control run is the confirmation.
7. **Adoption is a new scenario**: the whole lineage (references, gates, datasets,
   checkpoints, the policy canary) re-baselines per audit section 5b.4; out of scope here by
   the owner directive.
