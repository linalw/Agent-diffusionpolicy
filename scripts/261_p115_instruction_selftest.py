#!/usr/bin/env python3
"""P115 sort-instruction selftest (offline; selfcheck leg).

P114 gave the cell a scenario descriptor and an instruction of
`condition => destination` rules.  P115 makes the instruction **expressive
enough to write a real sorting spec** and **safe to start**:

1. `and` conjoins up to three attribute terms in one rule
   (`species=apple and size>=66 => 1`); every term must match.  `or` stays
   written as more rules, because the first match wins.
2. Every armed run prints its rule table (`[sort] rule N: ... (arm X)`) and the
   `FRUIT_SORT_STRICT=1` guard turns an instruction that drops fruit into a
   startup refusal instead of a silent skip.

The leg pins the grammar (terms, precedence, first-term compatibility with the
P114 `Rule` fields), every refusal (a `default` carrying a condition, an empty
or trailing term, more than three terms, a rule after `default`, an unknown
attribute), the four canonical instruction files in `configs/instructions/`,
and the `tasks.py` shape of the table print + the strict guard (one environment
read, the check before the first attempt, `skip` allowed, `None` refused).

Exit 0 on pass, 1 on the first failure.
"""

from __future__ import annotations

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
utils_mod = types.ModuleType("isaacsim.core.experimental.utils")
sys.modules.setdefault("isaacsim.core.experimental.utils", utils_mod)
prims_mod = types.ModuleType("isaacsim.core.experimental.prims")
prims_mod.RigidPrim = object
sys.modules.setdefault("isaacsim.core.experimental.prims", prims_mod)

from fruit_sorting import scenario  # noqa: E402
from fruit_sorting.assets import SceneConfig  # noqa: E402

FAILS: list[str] = []
CHECKS = 0


def check(cond, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(msg)


def refuses(text: str, descriptor, needle: str, why: str,
            grades=("A", "B", "C"), species=None) -> None:
    """One refusal: the parse raises and the message names the reason."""
    try:
        scenario.parse_instruction(
            text, descriptor, grades=grades, species=species
        )
    except scenario.ScenarioError as exc:
        check(needle in str(exc), f"{why}: message does not name it ({exc})")
    else:
        check(False, f"{why}: no refusal")


def main() -> int:
    cfg = SceneConfig()
    shipped = scenario.shipped_descriptor(cfg)
    species = tuple(cfg.fruit_dimensions)

    # ---------------------------------------------------------- the grammar
    compound = scenario.parse_instruction(
        str(ROOT / "configs/instructions/compound.txt"),
        shipped,
        grades=tuple(cfg.grades),
        species=species,
    )
    check(len(compound.rules) == 3, "compound.txt parses to three rules")
    first = compound.rules[0]
    check(
        first.terms == (("species", "=", "apple"), ("size", ">=", 66.0)),
        f"the first rule's terms are species=apple and size>=66 (got {first.terms})",
    )
    check(
        first.key == "species" and first.value == "apple",
        "the P114 Rule fields still carry the first term (compatibility)",
    )
    check(
        compound.rules[2].key is None and compound.rules[2].terms == (),
        "the default rule carries no terms",
    )

    # ---------------------------------------------------------- the decision
    def dest(species_name: str, millimetres: float, grade: str = "A"):
        return compound.destination(
            {"species": species_name, "diameter": millimetres / 1000.0,
             "grade": grade}
        )

    check(dest("apple", 68.0) == 1, "a 68 mm apple meets `species=apple and size>=66`")
    check(dest("apple", 64.0) == 0, "a 64 mm apple falls through the compound rule")
    check(dest("kiwi", 52.0) == 0, "a 52 mm kiwi is left by `default`")
    check(dest("strawberry", 36.0) == 1, "a 36 mm strawberry is right by `size<45`")
    check(
        dest("apple", 68.0, grade="C") == 1,
        "the compound rule does not look at grade (the destination is a fruit property)",
    )

    # ------------------------------------------------ which rule fired (P115)
    check(
        compound.match({"species": "apple", "diameter": 0.068}) == (1, 1),
        "the ledger reports rule 1 for a big apple",
    )
    check(
        compound.match({"species": "apple", "diameter": 0.064}) == (0, 3),
        "the ledger reports rule 3 (default) for a mid-size apple",
    )
    check(
        compound.match({"species": "strawberry", "diameter": 0.036}) == (1, 2),
        "the ledger reports rule 2 for a small strawberry",
    )
    no_default = scenario.parse_instruction("grade=A => 0", shipped)
    check(
        no_default.match({"species": "kiwi", "diameter": 0.055, "grade": "B"})
        == (None, None),
        "an unmatched fruit with no default reports (None, None)",
    )

    # ------------------------------------------- `or` = more rules; precedence
    either = scenario.parse_instruction(
        "species=apple => 0\nspecies=orange => 0\ndefault => 1", shipped
    )
    check(either.destination({"species": "apple", "diameter": 0.068}) == 0, "apple -> 0")
    check(either.destination({"species": "orange", "diameter": 0.065}) == 0, "orange -> 0")
    check(either.destination({"species": "kiwi", "diameter": 0.055}) == 1, "kiwi -> default 1")

    ordered = scenario.parse_instruction(
        "species=apple and size>=66 => 0\nsize<45 => 1\ndefault => 0", shipped
    )
    check(
        ordered.destination({"species": "apple", "diameter": 0.068}) == 0,
        "a big apple takes the first matching rule, not the later size rule",
    )
    check(
        ordered.destination({"species": "apple", "diameter": 0.040}) == 1,
        "a small apple misses the compound rule and takes `size<45`",
    )

    # the inline `;` separator composes with `and` (one shell line)
    inline = scenario.parse_instruction(
        "size<40 and grade=C => 1; default => 0", shipped
    )
    check(
        inline.destination({"species": "x", "diameter": 0.036, "grade": "C"}) == 1,
        "the inline `;` separator carries an `and` rule",
    )
    check(
        inline.destination({"species": "x", "diameter": 0.036, "grade": "A"}) == 0,
        "an `and` rule requires every term (grade=A falls through)",
    )

    # ---------------------------------------------------------- the refusals
    refuses("default and size<40 => 1", shipped, "cannot carry a condition",
            "a default with a condition")
    refuses("size<40 and => 1", shipped, "cannot parse condition",
            "a trailing `and`")
    refuses(
        "size<40 and size<50 and size<60 and size<70 => 1",
        shipped,
        "at most 3",
        "four terms",
    )
    refuses("default => 0\nsize<40 => 1", shipped, "rule after",
            "a rule after default")
    refuses("colour=red => 0", shipped, "unknown attribute",
            "an attribute the cell does not have")
    refuses("size<40 => 7", shipped, "not in scenario",
            "a destination the descriptor does not define")
    refuses("size<40 => -1", shipped, "negative", "a negative destination")
    refuses("", shipped, "empty", "an empty instruction")

    # --------------------- every canonical file parses and is servable here
    for name in ("shipped_grade.txt", "by_size.txt", "species_split.txt", "compound.txt"):
        path = ROOT / "configs/instructions" / name
        check(path.is_file(), f"{name} exists")
        if not path.is_file():
            continue
        parsed = scenario.parse_instruction(
            str(path), shipped, grades=tuple(cfg.grades), species=species
        )
        check(len(parsed.rules) >= 2, f"{name} has rules")
        for rule in parsed.rules:
            if isinstance(rule.dest, int):
                check(
                    rule.dest in shipped.ids,
                    f"{name} names destination {rule.dest}, which the shipped cell has",
                )

    # ------------------------------- the tasks.py shape: table row + strict
    tasks_src = (ROOT / "src/fruit_sorting/tasks.py").read_text(encoding="utf-8")
    check(
        '[sort] rule {index}: {rule.text}' in tasks_src,
        "the armed run prints one `[sort] rule N` row per rule",
    )
    check(
        tasks_src.count('os.environ.get("FRUIT_SORT_STRICT"') == 1,
        "FRUIT_SORT_STRICT is read at one site",
    )
    check(
        "self._sort_require_coverage()" in tasks_src,
        "the strict guard is called",
    )
    check(
        tasks_src.index("self._sort_require_coverage()")
        < tasks_src.index("self._sort_coverage_done = False"),
        "the strict guard runs at construction, before the first attempt",
    )
    check(
        'raise ScenarioError(\n            f"[sort] REFUSED: FRUIT_SORT_STRICT=1'
        in tasks_src,
        "the strict guard raises a ScenarioError that names FRUIT_SORT_STRICT",
    )
    strict_body = tasks_src[
        tasks_src.index("def _sort_require_coverage"):tasks_src.index("def _sort_ledger_coverage")
    ]
    check(
        "if self.sort_destination(sample) is None" in strict_body,
        "the strict guard trips on an unmatched fruit (None), not on a deliberate skip",
    )
    check(
        "rule={self._sort_rule_for(attrs)}" in tasks_src,
        "the ledger row names the firing rule",
    )
    check(
        "def _sort_rule_for(self, attrs: dict)" in tasks_src,
        "_sort_rule_for is defined",
    )

    if FAILS:
        print(f"P115 instruction selftest: {len(FAILS)} failure(s)")
        for failure in FAILS:
            print(f"  - {failure}")
        return 1
    print(f"P115 instruction selftest: PASS ({CHECKS} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
