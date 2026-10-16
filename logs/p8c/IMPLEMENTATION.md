# P8-2 implementation (the load-floor C-3 monitor): completion record

The implementation lane was killed by the server restart after landing the code edit but
before its verification/report. The orchestrator completed the wrap-up on the same edit.

**The edit** (`src/fruit_sorting/tasks.py`, +70/-14, md5 `12feced3b6204f06bb32cb878efb5e15`):
- `_CarryMonitorLeg.__init__(load_floor=0.0)` + `asym_min`/`fire_asym` slots.
- The hot predicate: `asym = max(0.0, force - 2*ft_min)`; a tick is hot only if
  `z >= 0` AND (`contacts == 0` OR `asym >= load_floor`); `load_floor=0.0` is a tautology
  (`asym >= 0`), so the P7-2b rule is preserved exactly.
- `PickAndPlaceTask` reads `FRUIT_CARRY_MONITOR_LOAD_FLOOR` (default `0.0`) and passes it to
  the leg; the `[monitor] fire` diag gains `asym@fire`.
- `rl_env.py` `TASKS_MD5` -> `12feced3b6204f06bb32cb878efb5e15` (match verified).

**The two frozen stub pins (both PASS):**
- floor=0 (default; `logs/p7c/verify_monitor_stub.py`): `TP=29 FP=0 FN=2 TN=33`, 0/25
  no-contact fires, 0 per-leg mismatches - the P7-2b pin reproduced (default inertness).
- floor=3.5 (`logs/p8c/verify_monitor_stub_lf.py`, `STUB_FLOOR` default 3.5): `STUB PASS`,
  `TP=28 FP=0 FN=3 TN=33` - the frozen LF pin, the real state machine reproducing the
  floored rule on all 89 legs.

**Offline verification:** `python3 -m py_compile` OK. The battery (steps 1-4 of
`logs/p8/PREREG_CARRY_MONITOR_LF.md`) is the next Tier-A step.
