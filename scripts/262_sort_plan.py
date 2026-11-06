#!/usr/bin/env python3
"""P116 sort-plan preview: what an instruction does to a cell, before it runs.

The owner's example - *"put grade-A fruit in the left box, put apples in the
right box"* - contains a real conflict: an A-grade apple matches both rules.
The runtime resolves it by **precedence** (first match wins), which is correct
but invisible. This tool makes it visible offline, on the cell's own attribute
space, so an operator sees the decision before spending a run:

  python3 scripts/262_sort_plan.py \
      --instruction configs/instructions/owner_a_left_apples_right.txt

It prints

  1. the rule table, with the arm that will carry each destination;
  2. the **overlap pairs** (a later rule that a earlier one shadows), with the
     number of attribute cells in the intersection and an example;
  3. the **partition** over the enumerated attribute space - how many fruit go
     to each destination, how many are skipped, how many match no rule;
  4. the refusals the parser would raise (it runs the real parser, not a copy).

`--strict-overlap` exits 1 when any pair overlaps, for a pre-commit check.
`--scenario <json>` plans against a descriptor other than the shipped cell.

The enumeration is species x diameter x grade from `SceneConfig` (5 sizes per
species, 3 grades; 120 cells). `ripeness`/`defective` are only enumerated when
a rule names them. This is a **preview**, not a run: no simulator, no motion.
"""

from __future__ import annotations

import argparse
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# --- stub pxr / isaacsim just enough to import `assets.SceneConfig` --------- #
for name in ("pxr", "isaacsim", "isaacsim.core", "isaacsim.core.experimental"):
    sys.modules.setdefault(name, types.ModuleType(name))
pxr = sys.modules["pxr"]
for attr in ("Gf", "PhysxSchema", "Sdf", "Usd", "UsdGeom", "UsdPhysics", "UsdShade"):
    if not hasattr(pxr, attr):
        setattr(pxr, attr, types.ModuleType(f"pxr.{attr}"))
app_mod = types.ModuleType("isaacsim.core.experimental.utils.app")
app_mod.update_app = lambda **kwargs: None
sys.modules.setdefault("isaacsim.core.experimental.utils.app", app_mod)
sys.modules.setdefault(
    "isaacsim.core.experimental.utils", types.ModuleType("isaacsim.core.experimental.utils")
)
prims_mod = types.ModuleType("isaacsim.core.experimental.prims")
prims_mod.RigidPrim = object
sys.modules.setdefault("isaacsim.core.experimental.prims", prims_mod)

from fruit_sorting import scenario  # noqa: E402
from fruit_sorting.assets import SceneConfig  # noqa: E402


def attribute_cells(cfg, instruction) -> list[dict]:
    """The cell's own attribute space: species x diameter x grade (+ labels)."""
    names = {term[0] for rule in instruction.rules for term in (rule.terms or ())}
    cells: list[dict] = []
    for species, (low, high) in cfg.fruit_dimensions.items():
        if high <= low:
            continue
        sizes = [low + (high - low) * frac for frac in (0.0, 0.25, 0.5, 0.75, 1.0)]
        for diameter in sizes:
            for grade in cfg.grades:
                cell = {"species": species, "grade": grade, "diameter": diameter}
                if "ripeness" in names:
                    cell["ripeness"] = 0.5
                if "defective" in names:
                    cell["defective"] = 0.0
                cells.append(cell)
    return cells


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction", required=True, help="path or inline rules")
    parser.add_argument("--scenario", default=None, help="descriptor JSON (default: shipped)")
    parser.add_argument("--strict-overlap", action="store_true",
                        help="exit 1 when any two rules can match the same fruit")
    args = parser.parse_args()

    cfg = SceneConfig()
    if args.scenario:
        descriptor = scenario.load_scenario(str(ROOT / args.scenario))
    else:
        descriptor = scenario.shipped_descriptor(cfg)
    instruction = scenario.parse_instruction(
        args.instruction,
        descriptor,
        grades=tuple(cfg.grades),
        species=tuple(cfg.fruit_dimensions),
    )
    capability = scenario.capability_map(descriptor)

    print(f"P116 plan - instruction {instruction.source}")
    print(f"  scenario {descriptor.name}: destinations {list(descriptor.ids)}")
    for index, rule in enumerate(instruction.rules, start=1):
        arm = ""
        if isinstance(rule.dest, int):
            served = [a for a, ids in capability.items() if int(rule.dest) in ids]
            arm = f" arm={served[0]}" if served else " [UNSERVED]"
        print(f"  rule {index}: {rule.text}{arm}")

    cells = attribute_cells(cfg, instruction)
    winners: list[int] = []
    for cell in cells:
        destination, rule_index = instruction.match(cell)
        winners.append(rule_index or 0)

    # ---- overlaps: a later rule that an earlier one can shadow -------------- #
    overlaps = []
    for i, earlier in enumerate(instruction.rules):
        if earlier.key is None:
            continue
        for j in range(i + 1, len(instruction.rules)):
            later = instruction.rules[j]
            if later.key is None:
                continue
            example = None
            count = 0
            for cell in cells:
                if scenario.rule_matches(earlier, cell) and scenario.rule_matches(later, cell):
                    count += 1
                    if example is None:
                        example = cell
            if count:
                overlaps.append((i + 1, j + 1, count, example, earlier, later))

    print()
    if overlaps:
        print(f"  OVERLAP: {len(overlaps)} pair(s) - the earlier rule wins:")
        for i, j, count, example, earlier, later in overlaps:
            print(
                f"    rule {i} ({earlier.text}) x rule {j} ({later.text}): "
                f"{count} cell(s); rule {i} wins"
            )
            print(
                f"      e.g. {example['species']} "
                f"{example['diameter'] * 1000:.0f}mm grade {example['grade']} "
                f"-> dest {earlier.dest} (not {later.dest})"
            )
    else:
        print("  OVERLAP: none - the rules partition the attribute space")

    # ---- the partition ----------------------------------------------------- #
    per_dest: dict[int | str, int] = {}
    per_rule: dict[int, int] = {}
    for rule_index in winners:
        per_rule[rule_index] = per_rule.get(rule_index, 0) + 1
    for cell, rule_index in zip(cells, winners):
        destination = instruction.match(cell)[0]
        key = "unmatched" if destination is None else destination
        per_dest[key] = per_dest.get(key, 0) + 1

    print()
    print(f"  PARTITION over {len(cells)} attribute cells:")
    for key in sorted(per_dest, key=str):
        label = f"dest {key}" if isinstance(key, int) else key
        if key == "skip":
            label = "skip (never selected)"
        print(f"    {label:<22} {per_dest[key]:>3} cell(s)")
    print("  by rule (cells won):")
    for index, rule in enumerate(instruction.rules, start=1):
        won = per_rule.get(index, 0)
        dest = rule.dest
        print(f"    rule {index} {rule.text:<36} {won:>3} cell(s) -> {dest}")
    unmatched = per_dest.get("unmatched", 0)
    if unmatched:
        print(
            f"  NOTE: {unmatched} cell(s) match no rule; they are never selected. "
            "Add a 'default' rule or a skip rule to make that explicit."
        )

    if args.strict_overlap and overlaps:
        print("\n  FAIL: overlaps exist and --strict-overlap was given")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
