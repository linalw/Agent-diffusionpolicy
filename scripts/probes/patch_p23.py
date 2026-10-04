"""Apply the P2-3 carry-clearance instrumentation to tasks.py (one-shot patch).

The dedicated edit tools are failing on this host, so the patch is applied with
exact-text anchors and a single-match assertion per hunk.
"""

from __future__ import annotations

import sys

PATH = "src/fruit_sorting/tasks.py"
text = open(PATH, encoding="utf-8").read()
original = text


def replace_once(anchor: str, replacement: str, name: str) -> None:
    global text
    count = text.count(anchor)
    if count != 1:
        raise SystemExit(f"anchor {name!r} matched {count} times (want 1)")
    text = text.replace(anchor, replacement, 1)


# 1. tracker initialisation, in `_carry`'s assisted branch
replace_once(
    "            slip_max = 0.0\n            slip_vel_max = 0.0\n            rel_prev = slip_ref\n",
    "            slip_max = 0.0\n"
    "            slip_vel_max = 0.0\n"
    "            # P2-3: per-leg clearance. The payload hangs from the pads, so the\n"
    "            # fruit's lowest point is what has to clear the belts and rails; it\n"
    "            # is measured against the highest surface under it every tick and\n"
    "            # reported per carry leg (the motion gate does not read it).\n"
    "            clearance_min = float(\"inf\")\n"
    "            clearance_where = \"\"\n"
    "            rel_prev = slip_ref\n",
    "trackers",
)

# 2. per-tick update in the carry loop
replace_once(
    "                fruit = np.asarray(self.spawner.position(sample), dtype=float)\n"
    "                pads = np.asarray(self.grippers[side].pad_centre(), dtype=float)\n",
    "                fruit = np.asarray(self.spawner.position(sample), dtype=float)\n"
    "                pads = np.asarray(self.grippers[side].pad_centre(), dtype=float)\n"
    "                clearance, where = self._payload_clearance(sample, fruit)\n"
    "                if clearance < clearance_min:\n"
    "                    clearance_min, clearance_where = clearance, where\n",
    "loop",
)

# 3. per-tick update in the 30-tick settle loop
replace_once(
    "                self._grip_centre[side] = placed\n"
    "                arm.ik_step(arm.tcp_target_for_jaw(placed - rot @ offset_tool))\n",
    "                self._grip_centre[side] = placed\n"
    "                clearance, where = self._payload_clearance(\n"
    "                    sample, np.asarray(self.spawner.position(sample), dtype=float)\n"
    "                )\n"
    "                if clearance < clearance_min:\n"
    "                    clearance_min, clearance_where = clearance, where\n"
    "                arm.ik_step(arm.tcp_target_for_jaw(placed - rot @ offset_tool))\n",
    "settle",
)

# 4. the report line
replace_once(
    "                say(MotionMonitor.format(summary))\n",
    "                say(MotionMonitor.format(summary))\n"
    "                if clearance_min < float(\"inf\"):\n"
    "                    say(\n"
    "                        f\"[motion] carry {name} clearance: lowest payload point \"\n"
    "                        f\"{clearance_min * 1000:+.0f} mm to the {clearance_where}\"\n"
    "                    )\n",
    "report",
)

# 5. the helper, before `_carry`
replace_once(
    "    def _carry(self, side: str, sample, name: str, steps: int = 200) -> None:\n",
    "    def _payload_clearance(self, sample, fruit) -> tuple[float, str]:\n"
    "        \"\"\"Vertical gap from the payload's lowest point to the surface under it.\n"
    "\n"
    "        The P2-3 check. The pads carry the payload, so the fruit's lowest point\n"
    "        is what has to clear the line. The surfaces are the main belt top, the\n"
    "        raised output belt top, and the output belt's side rail top near the\n"
    "        edge - the rail is what the payload crosses when it moves from the\n"
    "        pick station to the output line.\n"
    "        \"\"\"\n"
    "        lowest = float(fruit[2]) - self._shape_support(\n"
    "            sample, np.array([0.0, 0.0, -1.0])\n"
    "        )\n"
    "        y = abs(float(fruit[1]))\n"
    "        if y < 0.40:\n"
    "            surface, where = self.belt_top, \"main belt\"\n"
    "        else:\n"
    "            surface, where = float(self.cfg.output_belt_top_z), \"output belt\"\n"
    "            if y <= 0.46:\n"
    "                rail = float(self.cfg.output_belt_top_z) + 0.035\n"
    "                if rail > surface:\n"
    "                    surface, where = rail, \"output rail\"\n"
    "        return lowest - surface, where\n"
    "\n"
    "    def _carry(self, side: str, sample, name: str, steps: int = 200) -> None:\n",
    "helper",
)

if text == original:
    raise SystemExit("nothing changed")

open(PATH, "w", encoding="utf-8").write(text)
print("patched", PATH)
