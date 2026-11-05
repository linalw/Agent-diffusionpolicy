"""Scenario descriptor + sort-instruction layer (P114, default off).

The shipped cell hard-codes the same object three times: the *arm* is the
*grade* is the *output lane* (``rl_env.py:3520``, ``tasks.py:11460``), and the
place target is the lane index into ``SceneConfig.output_belt_drop_points``.
This module is the data layer that lets a new pipeline be a JSON plus a solve
instead of a code edit, and lets the *destination* be a decision rather than
the arm's identity.

Two independent objects:

* **the scenario descriptor** - the stations, the pick/place points, the belt,
  the destinations (with their physical release targets) and the supply. It is
  read only when ``FRUIT_SCENARIO=<path>`` is set (unset = the shipped code
  path, byte for byte), and its geometry overrides are applied in
  ``assets.SceneConfig.__post_init__`` / ``fruits.SupplyPlan.from_env``.
* **the sort instruction** - an ordered list of ``condition => destination``
  rules (``apple=>0``, ``size<40=>2``, ``default=>0``), read only when
  ``FRUIT_SORT_INSTRUCTION=<path|inline>`` is set. The resolver validates every
  destination against the descriptor's destinations and the capability map
  (which arm can physically reach which destination), and *refuses* a mapping
  no arm can serve instead of placing it wrongly.

The capability model is the physical one the record measured: an arm only
reaches the output belt on its own side (``tasks.py`` "the arm cannot change
lanes mid-attempt"), so a destination is servable by ``left`` iff its side is
``+y`` and by ``right`` iff its side is ``-y`` - and, for a destination whose
reach is ``auto``, only after the startup solve converges.

Nothing here reads the simulator. The reach solve lives in
``tasks.PickAndPlaceTask._calibrate_sort_destinations`` and is called only when
a descriptor with an ``auto`` destination (or an instruction) is armed.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from .common import say

#: The descriptor's schema tag. A file without it is rejected, not guessed.
SCHEMA = "fruit-sorting-scenario/1"

#: A rule's right-hand side can be the literal ``skip``: the fruit matched by
#: that rule is never selected (today's grade-C behaviour under pure routing).
SKIP = "skip"

#: The arms' physical side. Left serves +Y (lane 0), right serves -Y (lane 1) -
#: the shipped geometry in ``assets.SceneConfig.output_belt_drop_points`` and
#: the two-line stations in ``tasks.run_bimanual``.
ARM_SIDE = {"left": "+y", "right": "-y"}

_DEST_KEYS = {"schema", "name", "stations", "pick", "belt", "place",
              "destinations", "supply", "calibration", "notes"}
_DEST_ENTRY_KEYS = {"id", "name", "side", "kind", "target", "reach", "note"}
_SUPPLY_KEYS = {"x_min", "x_max", "grades", "classes", "schedule"}
_CALIBRATION_KEYS = {"place_tolerance_mm"}
_REACH_KEYS = {"status", "residual_mm", "source"}
_REACH_STATUS = {"auto", "verified", "unreachable"}


class ScenarioError(ValueError):
    """A descriptor or an instruction is not internally consistent."""


# --------------------------------------------------------------------------- #
# The descriptor
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Destination:
    """One physical delivery target.

    ``target`` is the ``(x, y)`` release point the place leg is commanded to,
    in the world frame and at the one place height the cell has
    (``SceneConfig.output_place_z``). ``kind`` is descriptive (``belt`` /
    ``tray`` / ``bin``); the dispatcher only uses the target and the side.
    """

    id: int
    name: str
    side: str
    kind: str
    target: tuple[float, float]
    reach: str = "auto"
    reach_residual_mm: float | None = None
    reach_source: str = ""

    @property
    def sign(self) -> float:
        return 1.0 if self.side == "+y" else -1.0


@dataclass(frozen=True)
class ScenarioDescriptor:
    name: str
    source: str
    stations: dict
    pick: dict
    belt: dict
    place: dict
    destinations: tuple[Destination, ...]
    supply: dict
    calibration: dict
    raw: dict

    def destination(self, dest_id: int) -> Destination:
        for dest in self.destinations:
            if dest.id == int(dest_id):
                return dest
        raise ScenarioError(
            f"[sort] REFUSED: destination {dest_id} is not in scenario "
            f"{self.name!r} (ids {[d.id for d in self.destinations]})"
        )

    @property
    def ids(self) -> tuple[int, ...]:
        return tuple(d.id for d in self.destinations)

    def reach_tolerance_m(self) -> float:
        return float(self.calibration.get("place_tolerance_mm", 25.0)) / 1000.0


def _bad(source: str, message: str) -> ScenarioError:
    return ScenarioError(f"FRUIT_SCENARIO={source}: {message}")


def _number(source: str, where: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _bad(source, f"{where} must be a number, got {value!r}")
    out = float(value)
    if not (out == out) or out in (float("inf"), float("-inf")):
        raise _bad(source, f"{where} must be finite, got {value!r}")
    return out


def load_scenario(path: str) -> ScenarioDescriptor:
    """Read and validate one descriptor JSON. Strict: unknown keys raise."""
    path = str(path)
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise _bad(path, "file not found") from exc
    except json.JSONDecodeError as exc:
        raise _bad(path, f"not valid JSON ({exc})") from exc
    if not isinstance(payload, dict):
        raise _bad(path, "the top level must be an object")
    unknown = set(payload) - _DEST_KEYS
    if unknown:
        raise _bad(path, f"unknown top-level key(s) {sorted(unknown)}")
    schema = payload.get("schema")
    if schema != SCHEMA:
        raise _bad(path, f"schema is {schema!r}, expected {SCHEMA!r}")
    name = str(payload.get("name") or os.path.splitext(os.path.basename(path))[0])

    stations = payload.get("stations", {})
    if not isinstance(stations, dict) or set(stations) - {"left", "right"}:
        raise _bad(path, "stations must be an object with left/right")
    stations = {k: _number(path, f"stations.{k}", v) for k, v in stations.items()}

    pick = payload.get("pick", {})
    if not isinstance(pick, dict) or set(pick) - {"x", "y"}:
        raise _bad(path, "pick must be an object with x/y")
    pick = {k: _number(path, f"pick.{k}", v) for k, v in pick.items()}

    belt = payload.get("belt", {})
    if not isinstance(belt, dict) or set(belt) - {"speed_m_s"}:
        raise _bad(path, "belt must be an object with speed_m_s")
    belt = {"speed_m_s": abs(_number(path, "belt.speed_m_s", belt["speed_m_s"]))} if belt else {}

    place = payload.get("place", {})
    if not isinstance(place, dict) or set(place) - {"x", "y"}:
        raise _bad(path, "place must be an object with x/y")
    place = {k: _number(path, f"place.{k}", v) for k, v in place.items()}

    supply = payload.get("supply", {})
    if not isinstance(supply, dict):
        raise _bad(path, "supply must be an object")
    unknown = set(supply) - _SUPPLY_KEYS
    if unknown:
        raise _bad(path, f"unknown supply key(s) {sorted(unknown)}")
    supply = dict(supply)
    for key in ("x_min", "x_max"):
        if key in supply:
            supply[key] = _number(path, f"supply.{key}", supply[key])
    if "schedule" in supply:
        schedule = str(supply["schedule"]).strip().lower()
        if schedule not in ("scatter", "wave", "patch", "bed"):
            raise _bad(
                path,
                f"supply.schedule={supply['schedule']!r}: expected one of "
                "scatter/wave/patch/bed",
            )
        supply["schedule"] = schedule
    for key in ("grades", "classes"):
        if key in supply:
            table = supply[key]
            if not isinstance(table, dict) or not table:
                raise _bad(path, f"supply.{key} must be a non-empty object")
            parsed = {}
            for k, v in table.items():
                parsed[str(k)] = _number(path, f"supply.{key}.{k}", v)
                if parsed[str(k)] <= 0.0:
                    raise _bad(path, f"supply.{key}.{k} must be positive")
            supply[key] = parsed

    calibration = payload.get("calibration", {})
    if not isinstance(calibration, dict):
        raise _bad(path, "calibration must be an object")
    unknown = set(calibration) - _CALIBRATION_KEYS
    if unknown:
        raise _bad(path, f"unknown calibration key(s) {sorted(unknown)}")
    calibration = {
        k: _number(path, f"calibration.{k}", v) for k, v in calibration.items()
    }

    entries = payload.get("destinations")
    if not isinstance(entries, list) or not entries:
        raise _bad(path, "destinations must be a non-empty list")
    destinations: list[Destination] = []
    seen: set[int] = set()
    for index, entry in enumerate(entries):
        where = f"destinations[{index}]"
        if not isinstance(entry, dict):
            raise _bad(path, f"{where} must be an object")
        unknown = set(entry) - _DEST_ENTRY_KEYS
        if unknown:
            raise _bad(path, f"{where}: unknown key(s) {sorted(unknown)}")
        try:
            dest_id = int(entry["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise _bad(path, f"{where}.id must be an integer") from exc
        if dest_id < 0 or dest_id in seen:
            raise _bad(path, f"{where}.id={dest_id} must be a unique non-negative integer")
        seen.add(dest_id)
        side = str(entry.get("side", "")).strip().lower()
        if side not in ("+y", "-y"):
            raise _bad(path, f"{where}.side must be '+y' or '-y', got {side!r}")
        kind = str(entry.get("kind", "belt")).strip().lower()
        if kind not in ("belt", "tray", "bin"):
            raise _bad(path, f"{where}.kind={kind!r}: expected belt/tray/bin")
        target = entry.get("target")
        if not isinstance(target, (list, tuple)) or len(target) != 2:
            raise _bad(path, f"{where}.target must be [x, y]")
        tx = _number(path, f"{where}.target[0]", target[0])
        ty = _number(path, f"{where}.target[1]", target[1])
        if abs(ty) > 1e-9 and ((ty > 0.0) != (side == "+y")):
            # The target's side is what the arm rule keys on; a target whose
            # y-sign contradicts its declared side would be dispatched to one
            # arm and released over the other's belt.
            raise _bad(
                path,
                f"{where}.target y={ty:+.3f} contradicts side {side!r}",
            )
        reach = entry.get("reach", {"status": "auto"})
        if not isinstance(reach, dict):
            raise _bad(path, f"{where}.reach must be an object")
        unknown = set(reach) - _REACH_KEYS
        if unknown:
            raise _bad(path, f"{where}.reach: unknown key(s) {sorted(unknown)}")
        status = str(reach.get("status", "auto")).strip().lower()
        if status not in _REACH_STATUS:
            raise _bad(
                path,
                f"{where}.reach.status={status!r}: expected one of "
                f"{sorted(_REACH_STATUS)}",
            )
        residual = reach.get("residual_mm")
        if residual is not None:
            residual = _number(path, f"{where}.reach.residual_mm", residual)
        destinations.append(
            Destination(
                id=dest_id,
                name=str(entry.get("name") or f"dest{dest_id}"),
                side=side,
                kind=kind,
                target=(tx, ty),
                reach=status,
                reach_residual_mm=residual,
                reach_source=str(reach.get("source", "")),
            )
        )
    destinations.sort(key=lambda d: d.id)

    return ScenarioDescriptor(
        name=name,
        source=path,
        stations=stations,
        pick=pick,
        belt=belt,
        place=place,
        destinations=tuple(destinations),
        supply=supply,
        calibration=calibration,
        raw=payload,
    )


_SCENARIO_CACHE: dict[str, ScenarioDescriptor] = {}


def resolve_scenario(env_value: str | None = None) -> ScenarioDescriptor | None:
    """The armed descriptor, or ``None`` when ``FRUIT_SCENARIO`` is unset.

    Cached per absolute path so every entry script's ``SceneConfig`` and the
    spawner's ``SupplyPlan`` read the same object. Unset is one ``os.environ``
    lookup and a dictionary miss - no file read, no print (byte-inert).
    """
    raw = os.environ.get("FRUIT_SCENARIO", "") if env_value is None else env_value
    raw = str(raw or "").strip()
    if not raw:
        return None
    path = os.path.abspath(os.path.expanduser(raw))
    if path not in _SCENARIO_CACHE:
        descriptor = load_scenario(path)
        _SCENARIO_CACHE[path] = descriptor
        say(
            f"[scenario] {descriptor.name}: {len(descriptor.destinations)} "
            f"destination(s) {list(descriptor.ids)}, stations "
            f"{descriptor.stations or 'shipped'}, source {path}"
        )
    return _SCENARIO_CACHE[path]


def shipped_descriptor(cfg) -> ScenarioDescriptor:
    """The shipped two-lane cell expressed as a descriptor (read-only).

    Used when an instruction is armed without ``FRUIT_SCENARIO``: the
    instruction still validates against the destinations the code actually has,
    and the capability map is the physical side rule. The two lanes are
    ``reach=verified`` by the shipped line's own record (no startup solve, so
    an instruction that reproduces today's routing is byte-identical to the
    un-instructed run).
    """
    destinations = []
    for index, (x, y) in enumerate(cfg.output_belt_drop_points):
        destinations.append(
            Destination(
                id=int(index),
                name=f"lane{index}",
                side="+y" if float(y) > 0.0 else "-y",
                kind="belt",
                target=(float(x), float(y)),
                reach="verified",
                reach_source="shipped line (SceneConfig.output_belt_drop_points)",
            )
        )
    return ScenarioDescriptor(
        name="shipped",
        source="<shipped>",
        stations={"left": float(cfg.pick_y), "right": float(cfg.pick_y) - 0.10},
        pick={"x": float(cfg.pick_x), "y": float(cfg.pick_y)},
        belt={"speed_m_s": abs(float(cfg.belt_speed))},
        place={"x": float(cfg.output_place_x), "y": float(cfg.output_place_y)},
        destinations=tuple(destinations),
        supply={},
        calibration={},
        raw={},
    )


# --------------------------------------------------------------------------- #
# The instruction
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rule:
    line: int
    text: str
    key: str | None      # None for `default`
    op: str | None
    value: object | None
    dest: int | str


@dataclass(frozen=True)
class SortInstruction:
    """An ordered ``condition => destination`` list with a static default."""

    source: str
    text: str
    rules: tuple[Rule, ...]
    default: int | str | None

    def destination(self, attrs: dict) -> int | str | None:
        """First matching rule's right-hand side, else the default, else None.

        ``None`` and ``skip`` both mean "do not select this fruit"; they are
        kept distinct in the ledger so a deliberate skip is not reported as a
        mapping gap.
        """
        for rule in self.rules:
            if rule.key is None:
                return rule.dest
            if _match(rule, attrs):
                return rule.dest
        return self.default

    def assigned_destinations(self) -> tuple[int, ...]:
        out = []
        for rule in self.rules:
            if isinstance(rule.dest, int) and rule.dest not in out:
                out.append(rule.dest)
        if isinstance(self.default, int) and self.default not in out:
            out.append(self.default)
        return tuple(out)


_CONDITION = re.compile(r"^\s*([A-Za-z_]+)\s*(<=|>=|=|<|>)\s*([^\s]+)\s*$")
_INT = re.compile(r"^-?\d+$")


def _parse_rhs(source: str, line: int, raw: str) -> int | str:
    token = raw.strip().lower()
    if token == SKIP:
        return SKIP
    if not _INT.match(token):
        raise ScenarioError(
            f"[sort] REFUSED: {source} line {line}: destination {raw.strip()!r} "
            f"is neither an integer id nor {SKIP!r}"
        )
    value = int(token)
    if value < 0:
        raise ScenarioError(
            f"[sort] REFUSED: {source} line {line}: destination {value} is negative"
        )
    return value


def _parse_condition(source: str, line: int, text: str) -> tuple[str, str, object]:
    match = _CONDITION.match(text)
    if match is None:
        raise ScenarioError(
            f"[sort] REFUSED: {source} line {line}: cannot parse condition "
            f"{text!r} (expected e.g. 'grade=A', 'apple', 'size<40')"
        )
    key, op, value = match.group(1).lower(), match.group(2), match.group(3)
    if key in ("size", "diameter"):
        if op not in ("<", "<=", ">", ">=", "="):
            raise ScenarioError(
                f"[sort] REFUSED: {source} line {line}: size supports "
                "<, <=, >, >=, =; got {op!r}"
            )
        raw = value.lower()
        if raw.endswith("mm"):
            raw = raw[:-2]
        try:
            millimetres = float(raw)
        except ValueError as exc:
            raise ScenarioError(
                f"[sort] REFUSED: {source} line {line}: size {value!r} is not "
                "a number of millimetres"
            ) from exc
        return "size", op, millimetres
    if key in ("grade",):
        if op != "=":
            raise ScenarioError(
                f"[sort] REFUSED: {source} line {line}: grade only supports '=', "
                f"got {op!r}"
            )
        return "grade", op, value
    if key in ("species", "class", "category"):
        if op != "=":
            raise ScenarioError(
                f"[sort] REFUSED: {source} line {line}: species only supports "
                f"'=', got {op!r}"
            )
        return "species", op, value.lower()
    if key in ("ripeness", "defective"):
        # Present in the sim as *drawn labels*, not measured attributes. The
        # instruction language accepts them so a scenario can say what it
        # means, and the design names the perception they would need.
        try:
            number = float(value)
        except ValueError as exc:
            raise ScenarioError(
                f"[sort] REFUSED: {source} line {line}: {key} needs a number, "
                f"got {value!r}"
            ) from exc
        return key, op, number
    raise ScenarioError(
        f"[sort] REFUSED: {source} line {line}: unknown attribute {key!r} "
        "(grade/species/size/ripeness/defective, or 'default')"
    )


def _read_text(raw: str) -> tuple[str, str]:
    """Resolve ``<path|inline>``: an existing file is read, else the text itself.

    Inline text may separate rules with ``;`` as well as newlines, so
    ``FRUIT_SORT_INSTRUCTION="size<40 => 1; default => 0"`` is one line in a
    shell. A file is read verbatim (a ``;`` there is not a separator).
    """
    candidate = os.path.expanduser(raw.strip())
    if os.path.isfile(candidate):
        with open(candidate, encoding="utf-8") as handle:
            return handle.read(), os.path.abspath(candidate)
    return raw.replace(";", "\n"), "<inline>"


def parse_instruction(
    raw: str,
    descriptor: ScenarioDescriptor,
    *,
    grades: tuple[str, ...] | None = None,
    species: tuple[str, ...] | None = None,
) -> SortInstruction:
    """Parse + validate one instruction against a descriptor.

    Refusals (all raise ``ScenarioError`` before any attempt runs):
      * a right-hand side that is not an integer id or ``skip``;
      * a destination id the descriptor does not define;
      * a destination no arm can serve (wrong side, or declared unreachable);
      * a condition on an attribute the cell does not have;
      * a grade/species the pool cannot produce (when the vocabulary is given);
      * a second ``default`` or a rule after ``default``.

    An *unmatched* fruit is not an error: ``destination()`` returns ``None``
    and the selectors never choose it (reported as ``unassigned`` in the
    coverage row).
    """
    text, source = _read_text(raw)
    rules: list[Rule] = []
    default: int | str | None = None
    seen_default = False
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if "=>" not in line:
            raise ScenarioError(
                f"[sort] REFUSED: {source} line {line_number}: no '=>' in "
                f"{line!r} (expected 'condition => destination')"
            )
        lhs, rhs = line.split("=>", 1)
        dest = _parse_rhs(source, line_number, rhs)
        if dest != SKIP:
            try:
                target = descriptor.destination(int(dest))
            except ScenarioError:
                raise ScenarioError(
                    f"[sort] REFUSED: {source} line {line_number}: destination "
                    f"{dest} is not in scenario {descriptor.name!r} "
                    f"(ids {list(descriptor.ids)})"
                ) from None
            if target.reach == "unreachable" or target.side not in ARM_SIDE.values():
                raise ScenarioError(
                    f"[sort] REFUSED: {source} line {line_number}: destination "
                    f"{dest} ({target.name}) is not served by any arm "
                    f"(side {target.side}, reach {target.reach})"
                )
        if lhs.strip().lower() == "default":
            if seen_default:
                raise ScenarioError(
                    f"[sort] REFUSED: {source} line {line_number}: a second "
                    "'default' rule"
                )
            if rhs.strip() == "":
                raise ScenarioError(
                    f"[sort] REFUSED: {source} line {line_number}: empty default"
                )
            seen_default = True
            default = dest
            rules.append(Rule(line_number, line, None, None, None, dest))
            continue
        if seen_default:
            raise ScenarioError(
                f"[sort] REFUSED: {source} line {line_number}: a rule after "
                "'default' can never fire (default is last)"
            )
        key, op, value = _parse_condition(source, line_number, lhs)
        if key == "grade" and grades and str(value) not in tuple(grades):
            raise ScenarioError(
                f"[sort] REFUSED: {source} line {line_number}: grade {value!r} "
                f"is not in the pool's grades {list(grades)}"
            )
        if key == "species" and species and str(value) not in tuple(species):
            raise ScenarioError(
                f"[sort] REFUSED: {source} line {line_number}: species {value!r} "
                f"is not in the pool's classes {list(species)}"
            )
        rules.append(Rule(line_number, line, key, op, value, dest))
    if not rules:
        raise ScenarioError(f"[sort] REFUSED: {source}: the instruction is empty")
    return SortInstruction(source=source, text=text, rules=tuple(rules), default=default)


def resolve_instruction(
    descriptor: ScenarioDescriptor | None,
    cfg,
    env_value: str | None = None,
) -> SortInstruction | None:
    """The armed instruction, or ``None`` when ``FRUIT_SORT_INSTRUCTION`` is unset.

    Unset is one environment read and a string test: no parse, no print, no
    descriptor (the task then keeps every shipped selector branch). The
    descriptor is the armed scenario or the shipped two-lane cell, so an
    instruction can be used without a scenario file.
    """
    raw = (
        os.environ.get("FRUIT_SORT_INSTRUCTION", "")
        if env_value is None
        else env_value
    )
    raw = str(raw or "").strip()
    if not raw:
        return None
    if descriptor is None:
        descriptor = shipped_descriptor(cfg)
    return parse_instruction(
        raw,
        descriptor,
        grades=tuple(cfg.grades),
        species=tuple(cfg.fruit_dimensions),
    )


def _match(rule: Rule, attrs: dict) -> bool:
    if rule.key == "size":
        diameter_mm = float(attrs.get("diameter", 0.0)) * 1000.0
        value = float(rule.value)
        return {
            "<": diameter_mm < value,
            "<=": diameter_mm <= value,
            ">": diameter_mm > value,
            ">=": diameter_mm >= value,
            "=": abs(diameter_mm - value) < 1e-6,
        }[str(rule.op)]
    if rule.key == "grade":
        return str(attrs.get("grade", "")).strip().upper() == str(rule.value).strip().upper()
    if rule.key == "species":
        return str(attrs.get("species", attrs.get("category", ""))).strip().lower() == str(rule.value)
    if rule.key in ("ripeness", "defective"):
        actual = float(attrs.get(rule.key, 0.0))
        value = float(rule.value)
        return {
            "<": actual < value,
            "<=": actual <= value,
            ">": actual > value,
            ">=": actual >= value,
            "=": abs(actual - value) < 1e-6,
        }[str(rule.op)]
    return False


# --------------------------------------------------------------------------- #
# Capability
# --------------------------------------------------------------------------- #
def arm_for_destination(
    descriptor: ScenarioDescriptor,
    dest_id: int,
    reach: dict | None = None,
) -> str | None:
    """The arm that can deliver to ``dest_id``, or ``None`` (refused).

    ``reach`` is the startup solve's verdict, keyed ``(arm, dest_id) -> bool``.
    Without it, the side rule decides and a destination declared ``unreachable``
    is still refused. A ``verified`` destination needs no solve; an ``auto`` one
    is *provisional* until the solve runs (the task re-asks with ``reach``).
    """
    try:
        dest = descriptor.destination(int(dest_id))
    except ScenarioError:
        return None
    if dest.reach == "unreachable":
        return None
    for arm, side in ARM_SIDE.items():
        if side != dest.side:
            continue
        if reach is not None:
            ok = reach.get((arm, dest.id))
            if ok is None:
                ok = dest.reach == "verified"
            if not ok:
                continue
        return arm
    return None


def capability_map(
    descriptor: ScenarioDescriptor, reach: dict | None = None
) -> dict[str, frozenset[int]]:
    caps: dict[str, set[int]] = {arm: set() for arm in ARM_SIDE}
    for dest in descriptor.destinations:
        arm = arm_for_destination(descriptor, dest.id, reach)
        if arm is not None:
            caps[arm].add(dest.id)
    return {arm: frozenset(ids) for arm, ids in caps.items()}


def instruction_against(
    descriptor: ScenarioDescriptor,
    reach: dict | None = None,
) -> dict[int, str]:
    """``dest -> arm`` for every destination an instruction may name."""
    out = {}
    for dest in descriptor.destinations:
        arm = arm_for_destination(descriptor, dest.id, reach)
        if arm is not None:
            out[dest.id] = arm
    return out
