# P12-A.2 implementation: the property-realism component split (`FRUIT_PHYSICS_REAL_MASS` / `_REST` / `_COMPLIANCE`), offline

Status: **implemented, offline-verified** (branch `p-supply`, 2026-10-18). **No simulator run in
this lane** - the component batteries are a separate lane (section 5 lists the deferred
measurements). Writes: `src/fruit_sorting/meshes.py` (the sub-knob reads + the component
resolvers), `src/fruit_sorting/fruits.py` (the rest resolver + the banner helper),
`logs/p12a2/` (this record, `check_subknobs.py`, `executed_compare.py`, the evidence logs,
`WORKLOG_entry.md`). No commit by this lane; no branch operation; `Paper/`, `datasets/`,
`checkpoints/` untouched; `tasks.py` untouched (its md5 `810658b802d22bbd63013726fc78af81` is
unchanged, so `rl_env.py`'s `TASKS_MD5` pin needs no follow).

Reference: the committed P12-A implementation (`4f51fff`; `logs/p12/IMPLEMENTATION.md`,
`logs/p12/A_RESULTS.md` - the two-line-anchor battery: the falls halve 14 -> 7, the pooled
interval -4.7 %, the window rate +3.9 %, the outcomes in the draw band 35 vs 39) and the
P12-A.2 next step named there: split the batch into the mass / restitution / compliance
sub-knobs so the component batteries can find which property carries the falls reduction and
the interval gain (the restitution is the least likely driver per the audit) - so a refinement
can keep the winners and drop the seed-5 carried-class side effect.

## 1. The diff

Full diff: `logs/p12a2/01_diff.txt` (`git diff` of the two files; 278 lines).

| file | md5 (new) | md5 (was, HEAD `31ac0b1`) | change |
| --- | --- | --- | --- |
| `src/fruit_sorting/meshes.py` | `0e32b1ad1830b04dc0a4bddadfc84a5f` | `10fa005e4f8ebcbb087c37643dfe3dc1` | +81/-22: the three sub-knob read-once constants, `_component_real`, the three component resolvers, the consumption-point routing, comments |
| `src/fruit_sorting/fruits.py` | `d28546d26137d4540421caa7fa34a139` | `7283e4bf92425ffc81bcd3d64d72ad00` | +53/-19: `restitution_range` reads the rest resolver, `_physics_banner`, the `create_pool` gating, comments |
| `src/fruit_sorting/tasks.py` | `810658b802d22bbd63013726fc78af81` | same | **untouched** (the P11-C.3 baseline; the `TASKS_MD5` pin still matches) |
| `src/fruit_sorting/rl_env.py` | `9a2c38721b32f0af91371ca3e8809196` | same | **untouched** (no pin follow needed) |

**Hunk 1** (`meshes.py`, the switch block): the committed single read
(`_PHYSICS_REAL_RAW = os.environ.get("FRUIT_PHYSICS_REAL")`) gains the three sub-knob reads,
all four read **once at import** (the repo convention; this gates build-time physics authoring
and cannot change mid-run):

```python
_PHYSICS_REAL_RAW = os.environ.get("FRUIT_PHYSICS_REAL")
_PHYSICS_REAL_MASS_RAW = os.environ.get("FRUIT_PHYSICS_REAL_MASS")
_PHYSICS_REAL_REST_RAW = os.environ.get("FRUIT_PHYSICS_REAL_REST")
_PHYSICS_REAL_COMPLIANCE_RAW = os.environ.get("FRUIT_PHYSICS_REAL_COMPLIANCE")


def physics_real() -> bool:            # the master, unchanged: exact `== "1"`
    return _PHYSICS_REAL_RAW == "1"


def _component_real(sub_raw: str | None) -> bool:
    if sub_raw is not None:            # an explicit sub-knob wins for its component
        return sub_raw == "1"          # the exact `== "1"` parse (0/other = off)
    return physics_real()              # unset -> the component follows the master


def physics_real_mass() -> bool: ...        # _component_real(_PHYSICS_REAL_MASS_RAW)
def physics_real_rest() -> bool: ...        # _component_real(_PHYSICS_REAL_REST_RAW)
def physics_real_compliance() -> bool: ...  # _component_real(_PHYSICS_REAL_COMPLIANCE_RAW)
```

**Hunk 2** (`meshes.py`, the consumption points): `fruit_density` reads
`physics_real_mass()` and `fruit_contact_stiffness` reads `physics_real_compliance()` instead
of the master; the `real=` argument stays the offline-stub seam (it now overrides the
component resolution, unchanged semantics). The `density_real` / `contact_stiffness_real`
field comments and the value-table header name the component sub-knobs.

**Hunk 3** (`fruits.py`, `restitution_range`): reads `physics_real_rest()` instead of the
master.

**Hunk 4** (`fruits.py`, the banner): the inline `if physics_real(): say(...)` in `create_pool`
becomes `banner = _physics_banner()` / `if banner is not None: say(banner)`. The helper:

```python
def _physics_banner() -> str | None:
    mass_on = physics_real_mass(); rest_on = physics_real_rest()
    compliance_on = physics_real_compliance()
    if not (mass_on or rest_on or compliance_on):
        return None                                # the knob-off stream: no line
    if physics_real() and mass_on and rest_on and compliance_on:
        return ("[physics] FRUIT_PHYSICS_REAL=1: real class densities + "
                "restitution 0.35-0.50 + per-class compliant contact (P12-A)")   # verbatim
    return ("[physics] FRUIT_PHYSICS_REAL components: "
            f"mass={int(mass_on)} rest={int(rest_on)} "
            f"compliance={int(compliance_on)} (P12-A.2)")
```

The master all-on case keeps the **committed P12-A line verbatim**, so a
`FRUIT_PHYSICS_REAL=1` log replays the committed line (section 4.3 proves it by execution);
a partial (or sub-knob-only) activation names the resolved component states, so a component
battery log identifies its physics. `fruits.py` never reads the environment (all four knobs
through the resolvers); nothing else in the log stream changes and no control-loop read is
added (`rescale` runs in the recycler and reads the cached constants).

## 2. The knob semantics and the resolution table

* **Names / defaults**: `FRUIT_PHYSICS_REAL` (master) plus `FRUIT_PHYSICS_REAL_MASS`,
  `FRUIT_PHYSICS_REAL_REST`, `FRUIT_PHYSICS_REAL_COMPLIANCE` (components); every one default
  `0` (unset) = the shipped values, so the fully-unset tree is byte-inert.
* **Resolution (per component)**: a sub-knob **explicitly present in the environment always
  wins** for its component, with the exact `== "1"` parse the other `FRUIT_*` flags use
  (`0`/`true`/any other value = off); when unset, the component follows the master. So
  `FRUIT_PHYSICS_REAL=1` alone is the committed P12-A batch, and
  `FRUIT_PHYSICS_REAL=1 FRUIT_PHYSICS_REAL_REST=0` is mass + compliance only.
* **Read once**: all four are captured at import in `meshes.py` (the module comment documents
  this); `fruits.py` consumes the resolvers only.
* **Scope**: every fruit, all paths (single arm, two-line, policy, collector) - the split is
  scenario-level physics, not two-line-scoped.

The per-component truth table (the master x the sub-knob):

| `FRUIT_PHYSICS_REAL` | sub-knob | component |
| --- | --- | --- |
| unset / `0` / other | unset | **off** (shipped) |
| unset / `0` / other | `1` | **on** (real) |
| unset / `0` / other | `0` / other | **off** (explicit off) |
| `1` | unset | **on** (the component follows the master) |
| `1` | `1` | **on** |
| `1` | `0` / other | **off** (the explicit sub-knob overrides the master) |

The 8 component combinations (the values the executed stub pins; tomato density [kg/m^3],
apple contact stiffness [N/m], restitution band):

| mass | rest | compliance | tomato density | apple stiffness | band |
| --- | --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 780 | 0 (rigid) | 0.02-0.20 |
| 1 | 0 | 0 | 960 | 0 | 0.02-0.20 |
| 0 | 1 | 0 | 780 | 0 | 0.35-0.50 |
| 0 | 0 | 1 | 780 | 27000 | 0.02-0.20 |
| 1 | 1 | 0 | 960 | 0 | 0.35-0.50 |
| 1 | 0 | 1 | 960 | 27000 | 0.02-0.20 |
| 0 | 1 | 1 | 780 | 27000 | 0.35-0.50 |
| 1 | 1 | 1 | 960 | 27000 | 0.35-0.50 |

The banner: none when every component is off; the committed P12-A line when the master is on
and all three components resolve on; the `[physics] FRUIT_PHYSICS_REAL components: mass=X
rest=Y compliance=Z (P12-A.2)` line otherwise.

## 3. The value table (unchanged by the split)

The real values themselves are the committed P12-A table (`logs/p12/IMPLEMENTATION.md`
section 3): per-class densities (tomato 780 -> 960, apple 850 -> 840, orange/peach/lychee
1000, pear 950, kiwi 1050, strawberry 950), the per-class Hertzian contact stiffnesses
(tomato 4000, apple 27000, the rest 3000-23000 N/m), the restitution band 0.35-0.50 and the
compliant damping 80 Ns/m. The split moved **which switch gates them**, not a value. The
mass formula (`density x 4/3 pi r^3 x 0.82`), both authoring sites, the single material
helper and the finger-side scope (left shipped) are untouched; the p12 doc's sections 3 and
6 (the mass gap, the restitution's post-fall role, the pair-combination rule) all still
apply.

## 4. The verification (offline only)

1. **`python3 -m py_compile`** on `meshes.py`, `fruits.py`, `check_subknobs.py`,
   `executed_compare.py`: OK (`logs/p12a2/09_py_compile.txt`).
2. **The new stub** `logs/p12a2/check_subknobs.py`: **PASS, 78/78 checks**
   (`logs/p12a2/10_stub_check.txt`; ~1.5 s). Layers:
   * *source* (section 1): each of the four knobs is read exactly once in `meshes.py` with
     its cached constant; the master parse is the exact `== "1"`; the three resolvers route
     through `_component_real` (the explicit-wins precedence pinned by AST); the consumption
     points read the right resolver (and no stale `on = physics_real()` remains); `fruits.py`
     never reads the environment; the banner helper gates on the resolved components and
     keeps the committed text for the master all-on case; the mass formulas / the 0.82
     discount / both authoring sites / the single compliant-authoring place are unchanged.
   * *the knob-off byte-identity* (section 2, in-process): all four knobs off with every raw
     constant `None`; the shipped F4 density table, tomato 780 / apple stiffness 0.0 / band
     (0.02, 0.2); the shipped draw byte-identical to the literal `uniform(0.02, 0.2)` (and the
     seam-on draw to `uniform(0.35, 0.50)`); the tomato mass arithmetic (68.8 g off = the
     literal 780 kg/m^3 mass at 59 mm, 84.7 g via the seam); the banner is `None`; the REAL
     helper authors exactly the three shipped attributes and zero `PhysxMaterialAPI` applies.
   * *the 8 combinations* (section 3, subprocesses enumerated through the master + explicit
     sub-knob overrides): per combination the resolved triple + the raw capture, the
     per-component shipped/real values, the executed REAL `_create_fruit` path (the authored
     mass at the drawn diameter, the authored material attribute set, the compliant pair only
     with compliance on, the authored restitution inside the resolved band), and the banner
     text. The drawn tomato diameter is **identical in every combination** (the knobs do not
     touch the rng stream).
   * *the master + override semantics* (section 4, subprocesses): each sub-knob alone; the
     sub-knobs-only all-on (the component banner, not the committed line); the mission's
     example `FRUIT_PHYSICS_REAL=1 FRUIT_PHYSICS_REAL_REST=0` = mass + compliance; the exact
     parse (`true` = off); plus the read-once cache (setting the env after import does not
     move any knob).
   * *the pins* (section 5): `rl_env.TASKS_MD5 == md5(tasks.py)`, tasks.py untouched.
3. **The one-off executed old-vs-new identity** (`logs/p12a2/executed_compare.py`, archived
   `logs/p12a2/11_executed_compare.txt`): the HEAD package is extracted with
   `git archive HEAD src/fruit_sorting` (fruits.py `7283e4bf`, meshes.py `10fa005e` - the
   committed P12-A revision) and the REAL `create_pool()` 16-fruit scatter path runs against
   generic pxr fakes in both trees, comparing the resolution values, the 16 authored masses,
   the 16 material attribute dicts, the `PhysxMaterialAPI` apply count **and the full
   captured stdout**. Result: **execution-identical in both settings** -
   * knob-off (everything unset): all fields identical, stdout 2 lines, no banner (the
     knob-off log stream is byte-identical);
   * master=1: all fields identical, stdout 3 lines, the committed
     `[fruit] [physics] FRUIT_PHYSICS_REAL=1: ... (P12-A)` banner line verbatim.
   This is the strongest offline form of both claims (the split's off path is byte-inert and
   the master all-on path is the committed P12-A behavior). It is a one-off (it compares
   against `HEAD`, so it must not be re-run after a commit of this change) and is not a
   permanent gate.
4. **The committed P12-A stub** (`logs/p12/check_physics_real.py`) re-run against this tree
   (`logs/p12a2/12_p12_stub_superseded.txt`): **39/40 PASS**. The one FAIL is the *source*
   check that pinned the single-switch banner gating (`if physics_real():` exactly once);
   the split supersedes exactly that shape. Every value / resolution / material layer of the
   committed stub still passes (including the master truth table unset/0/1/true and the
   read-once cache), which is independent evidence that the master semantics are preserved.
   The live stub for this revision is `logs/p12a2/check_subknobs.py`.
5. **`scripts/selfcheck.sh`** (`SELFCHECK_LOG=logs/p12a2/selfcheck.log`): **PASS, 0 failures,
   1 skipped** (motion budgets - it needs a run log and this lane made no simulator run). All
   21 offline legs pass; the supply-scatter leg imports the modified `fruits.py` with stubbed
   pxr and passes.
6. **The pin check**: `rl_env.TASKS_MD5 == md5(tasks.py) == 810658b8...` and tasks.py is still
   the P11-C.3 baseline (pinned in the stub). Provenance gap unchanged from P12-A:
   `meshes.py` is not in `rl_env.py`'s `_MANIFEST_SOURCES` nor in the collector manifest's
   source list, and no manifest field records the knobs - if a component batch reaches a
   collection, the manifest should gain a `collection.physics_real`-style field naming the
   components (the W7-C.1 `park_early` pattern) and `meshes.py` should join the source list.

## 5. The batteries (deferred, a separate lane)

The component batteries run the **two-line anchor** - `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1
FRUIT_SUPPLY_SCATTER=1 FRUIT_SUPPLY_PATCH=1 FRUIT_SUPPLY_GRADES=A:0.375,B:0.375,C:0.25
ATTEMPTS=20 SEED=11/5/23`, with `FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1
FRUIT_CARRY_DIAG=1 FRUIT_CARRY_MONITOR_DIAG=1` - under the component settings:

* **mass-only**: `FRUIT_PHYSICS_REAL_MASS=1` (the heavier bodies: tomato +23 %, strawberry
  +36 %; the same interference carries more momentum);
* **compliance-only**: `FRUIT_PHYSICS_REAL_COMPLIANCE=1` (the audit's point: a compliant
  fruit absorbs a squeeze instead of converting it into motion);
* optionally **rest-only** (`FRUIT_PHYSICS_REAL_REST=1`) as the audit's least-likely
  driver, and any pairing the decision needs - every combination is expressible.

What the lane must measure (the same endpoints the P12-A battery used, so the reads are
comparable): the **falls count** (the primary endpoint; P12-A halved it 14 -> 7) and the
carry class with its mechanism (the W8-B `clean_slip` loaded-slide signature, the re-seats,
the P10-E no-grasp split), the **pooled inter-placement interval** and the window rate (the
P12-A pooled -4.7 % / +3.9 %), the class re-draws (the seed-5 carried-class side effect), the
**motion budgets** and the two-line gate (`scripts/190_twoline_gate.sh`) with a **new
reference if the branch moves** (a physics change is a new scenario per `AGENTS.md` section
2), and the knob-off control replay. The decision rule per the P12-A next-step note: keep the
component(s) that carry the falls reduction / interval gain and drop the seed-5 carried-class
side effect; the restitution is expected to be the least likely driver (audit section 3.4).

Per the owner directive there is **no full re-baseline in this lane** (and none was made):
the single-arm acceptance, the motion references, the collectors/datasets/checkpoints and the
policy canary are only re-recorded if a component batch is ever adopted.

## 6. Honest limits

1. **No simulator run** - every claim here is static + executed-statement evidence; the
   contact behavior of each component (the pair response, the ejection class, the falls) is
   the battery's to measure.
2. **The material-pair combination rule is still unverified offline** (the P12-A limit,
   unchanged): the finger stays shipped at 30 kN/m; the traces decide the effective pair.
3. **The master all-on equivalence is execution-identity, not a simulator replay**: the
   probe runs the real `create_pool` path with fakes; the shipped simulator behavior under
   `FRUIT_PHYSICS_REAL=1` was the committed P12-A battery's to measure and its A records
   stand.
4. **The component banner text is new** (not present in the committed P12-A) - it appears
   only for partial/sub-knob-only activations; the master all-on case keeps the committed
   line (proven in section 4.3), so no committed log's physics line changes.
5. **The resolution is import-time** (read once): a mid-run env change cannot move any knob
   (pinned in the stub); the `real=` seam on the three resolvers remains an offline-stub
   override only.
6. **The stub's executed layer runs one tomato per combination**, not the full pool; the
   full 16-fruit pool path is exercised by the executed compare (section 4.3). The
   combination's per-class stiffness is checked for tomato (4000 N/m) and the resolution for
   apple (27000 N/m); the class table itself is pinned for all 8 classes.
7. **Adoption is a new scenario**: the whole lineage (references, gates, datasets,
   checkpoints, the policy canary) re-baselines if adopted; out of scope by the owner
   directive.
