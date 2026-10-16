# P8-1 detail record: the C-3 carry monitor load-floor implementation (default-off, byte-inert at default), offline-verified

Companion to `logs/p8c/IMPLEMENTATION.md` (the orchestrator's completion
record, written 00:35 +0800 after it believed this lane had been killed by the
server restart; **that file was left untouched**). This file is this lane's
full detail: the exact diff summary, both stub pins through two independent
harnesses, the md5s, the verification and the concurrent-writer history. The
lane (`ses_eba80bf33ffe56YiPd1iW2b2RR`) resumed after the restart and
re-verified everything end to end; no `src/` file changed after the
orchestrator's verification (see section 7).

Object under test: the frozen pre-registration
`logs/p8/PREREG_CARRY_MONITOR_LF.md` (md5 `b3604b7fb30e825a1f5c9c9b2a285fb6`),
section 7.2 (the one rule change) and 7.3 (the two stub pins), implementing the
unblock list of `logs/p8b/B2_RESULTS.md` section 4. Branch `p-supply`, HEAD
`7ff9f48`. Offline only: no simulator, no claim, no shipped-default change.

**Verdict: implemented and verified offline.** floor=0 -> **TP=29 FP=0 FN=2
TN=33** (P7-2b exactly); floor=3.5 -> **TP=28 FP=0 FN=3 TN=33**, third FN
exactly `w8/B_traces_mech_run1/trace_12`#0; `asym@fire` in the diag; the knob
wiring pinned against the real source; `rl_env.py::TASKS_MD5` matches
`tasks.py`; `scripts/selfcheck.sh` PASS (0 failures, 1 skipped).

## 1. Files changed

| file | md5 at HEAD | md5 after | lines |
| --- | --- | --- | --- |
| `src/fruit_sorting/tasks.py` | `7489f302c14e65aa9771f674e4ee199b` | **`12feced3b6204f06bb32cb878efb5e15`** | +73 / -15 |
| `src/fruit_sorting/rl_env.py` | `75b315d3c9a2680d973dabeac045b631` | **`7bd07b662595c56fa45ca12e7a87a7ff`** | +9 / -1 |

Full diffs: `logs/p8c/02_diff_tasks.txt`, `logs/p8c/03_diff_rl_env.txt`; md5s:
`logs/p8c/01_md5s.txt`. `configs/*` untouched; nothing under `scripts/`,
`datasets/`, `checkpoints/`, `Paper/` touched.

## 2. The diff (exact, by site)

### 2.1 `_CarryMonitorLeg` (the frozen 7.2 rule change)

```python
    def __init__(self, load_floor: float = 0.0) -> None:
        ...
        self.load_floor = float(load_floor)
        self.asym_min = float("inf")      # running min over the current hot run
        self.fire_asym = None             # `asym_min` at the fire tick (diag)

    def step(self, tick, sep, gap_cmd, ft_min, force, contacts) -> bool:
        ...
        if z < 0.0:
            self.run = 0
            self.asym_min = float("inf")
            return False
        asym = max(0.0, float(force) - 2.0 * float(ft_min))
        if contacts != 0 and asym < self.load_floor:
            self.run = 0
            self.asym_min = float("inf")
            return False
        self.hot += 1
        if self.min_contacts <= 0:
            self.blocked += 1
            self.run = 0
            self.asym_min = float("inf")
            return False
        self.run += 1
        self.asym_min = min(self.asym_min, asym)
        if self.run >= _CARRY_MONITOR_PERSIST:
            self.fire = tick - _CARRY_MONITOR_PERSIST + 1
            self.fire_z = z
            self.fire_asym = self.asym_min
            self.done = True
            return True
        return False
```

Hot predicate = the pre-registered `z >= 0.0 AND (contacts == 0 OR
force - 2*ft_min >= floor)`; the `contacts == 0` exemption is live-inert (that
tick also closes the running-min gate below it) and is kept for offline
continuity. Persistence 2, the loaded-contact gate, the direct-capture scope
and the fast-skip action are unchanged. `asym_min` is the min over the current
hot run; a leg fires the moment `run` reaches `PERSIST`, so at the fire tick it
is exactly the min over the firing window (ticks `fire .. fire + PERSIST - 1`).

### 2.2 The knob (read once, at `PickAndPlaceTask.__init__`, next to the two existing monitor knobs)

```python
        self._carry_monitor_load_floor = float(
            os.environ.get("FRUIT_CARRY_MONITOR_LOAD_FLOOR", "0.0")
        )
```

### 2.3 The construction site (`_carry`, the single site)

```python
            mon_leg = (
                _CarryMonitorLeg(self._carry_monitor_load_floor)
                if mon_armed
                else None
            )
```

### 2.4 The `[monitor] fire` diag (the K2 classification field)

```python
                                f"[monitor] fire {side} {name}: "
                                f"tick={mon_leg.fire}/{len(commands)} "
                                f"z={mon_leg.fire_z:+.2f} "
                                f"asym@fire={mon_leg.fire_asym:.2f} "
                                f"hot={mon_leg.hot} "
                                f"blocked={mon_leg.blocked} "
                                f"min_contacts={mon_leg.min_contacts}"
```

`asym@fire` is the firing window's min `asym` (the pre-registered definition),
so K2 can classify every fire from the log alone.

### 2.5 Comments

The module constants block, the class docstring, the `__init__` knob block and
the monitor step-site comment document the new term, its default and the
byte-inert argument (no functional effect).

## 3. The two stub pins (independent harnesses, all PASS)

**This lane's harness** `logs/p8c/verify_monitor_stub_lf_p81.py` (md5
`668f42a0bf9f47b22368696fc26a5178`; the P7-2b harness copied and extended:
both floors replayed through the real extracted class in one run, each against
a floor-parameterized independent reference; the `asym@fire` field checked
against the independent window min on every fire; the floor=3.5 FN set
asserted; floor accept/reject + window min + exemption + clamp pinned
synthetically; the knob wiring pinned against the real source). Output
(`logs/p8c/20_stub_pins_p81.txt`, exit=0):

```
== 2. corpus replay through the real state machine (both floor pins) ==
  floor=0.0: legs=89 per-leg mismatches=0  TP=29 FP=0 FN=2 TN=33  no-contact fires=0/25  min asym@fire=0.900 (n=29)
  floor=3.5: legs=89 per-leg mismatches=0  TP=28 FP=0 FN=3 TN=33  no-contact fires=0/25  min asym@fire=3.663 (n=28)

== 3. synthetic semantics ==
  hot-state z=+2.12 (>= 0; derived from the corpus), persistence/gate/done: OK
  floor states: high-load asym=6.77 z=+2.12; low-load asym=0.64 z=+0.77; no-contact z=+4.00; clamp probe raw=-0.364 z=+0.27
  floor 0.0 / 3.5 accept-reject, window-min `asym@fire`, exemption, clamp: OK

== 4. knob wiring (real source) ==
  env line default/pin, single call site, `asym@fire` diag: OK

STUB PASS (...)
```

- floor=0.0 reproduces the P7-2b pins exactly (29/0/2/33, 0/25 no-contact
  fires, per-leg fire ticks identical to the floor-0 reference; the two FNs
  are the frozen rule's own no-lead-time pair).
- floor=3.5 reproduces the frozen pin exactly (28/0/3/33); the FN set is
  exactly `w8mech trace_13`#1, `w8mech trace_15`#0 and
  `logs/w8/B_traces_mech_run1/trace_12_right_direct_fail.json` (the leg
  `logs/p8/B_OFFLINE.md` section 4 names). The tightest fire window reads
  **3.663 N** (`trace_08`, +0.16 over the floor), matching the offline
  B-lane's "tightest +0.16 N (`w8mech trace_08`'s 3.66 window)".
- Section 4 exec's the real `FRUIT_CARRY_MONITOR_LOAD_FLOOR` assignment from
  `PickAndPlaceTask.__init__` (unset -> `0.0`, `"3.5"` -> `3.5`), asserts the
  single `_CarryMonitorLeg(...)` call site passes
  `self._carry_monitor_load_floor`, and that the source carries
  `asym@fire={mon_leg.fire_asym:.2f}` - the check that would have caught B2's
  silent-mismeasure failure mode.

**The unchanged P7-2b harness** `logs/p7c/verify_monitor_stub.py` (md5
`6ddd966fd9dd621b186cd510f6d79a70`): still **STUB PASS at 29/0/2/33** on this
tree (`logs/p8c/21_stub_p7c_compat.txt`, exit=0) - the floor-default-0
byte-inert reading at the rule level.

**The wrap-up/battery harness** `logs/p8c/verify_monitor_stub_lf.py` (md5
`6965d2adc71048ddc53012d01dd5ebe6`, written by the concurrent lane): default
(`STUB_FLOOR` unset = 3.5) **STUB PASS, 28/0/3/33**
(`logs/p8c/22_stub_battery_harness_floor35.txt`). Its `STUB_FLOOR=0` path
replays **29/0/2/33** but prints **STUB FAIL** because its expected-counts
assertion is hardcoded to `(28, 0, 3, 33, 0)` regardless of `STUB_FLOOR`
(`logs/p8c/23_stub_battery_harness_floor0.txt`) - a harness-side limitation of
that copy, not a tree failure; the floor=0 pin is covered by the P7-2b harness
and by this lane's harness. See `logs/p8c/04_concurrent_write_note.txt` item 6
for the flag to the battery lane.

## 4. The clamp (one deliberate reading, documented)

The pre-registered formula is `force - 2*ft_min >= floor`; the live
implementation clamps `asym = max(0.0, force - 2*ft_min)`. Reasons and scope:

- the offline convention already clamps (`scripts/205_c3_fp_retry.py` builds
  `leg["asym"] = np.maximum(0.0, feats[:,4] - 2*feats[:,3])`), so the corpus
  replay and the pins are defined on the clamped value;
- the live read site takes `force` as the sum of the same per-finger values
  whose min is `ft_min` (two sensors), so `asym = |ft0 - ft1| >= 0`; but 3 of
  the 21,831 corpus ticks carry a tiny negative raw value (-0.001 N), and an
  unclamped `>= 0` would make those ticks non-hot under the default floor -
  breaking the pre-registration's own requirement that **default 0 = the
  P7-2b behavior exactly**;
- for every measured floor (>= 2.58 N) the clamp is decision-equivalent:
  `x >= f` iff `max(0, x) >= f` for `f > 0`;
- the stub pins the clamp explicitly (a hot tick with raw `-0.364 N` fires at
  floor 0.0 and is rejected at 3.5), so the reading cannot drift silently.

## 5. `rl_env.py` TASKS_MD5

`TASKS_MD5` follows `7489f302...` -> **`12feced3b6204f06bb32cb878efb5e15`**
(the new `tasks.py`), with a P8-1 paragraph in the pin-lineage comment; the
match is verified (`logs/p8c/01_md5s.txt`; the value in the file equals
`md5sum src/fruit_sorting/tasks.py`). The selfcheck's `rl env smoke` leg
(length-32 check) passes.

Pin history (details in `logs/p8c/04_concurrent_write_note.txt`): a concurrent
write to `rl_env.py` landed mid-lane at 00:24:40 +0800 setting
`TASKS_MD5 = "2e33427c..."`, which is exactly this lane's `tasks.py` minus its
final comment-only edit (a mid-edit snapshot); this lane's follow replaced it
with the real md5 and the orchestrator's completion record cites the same
value. A later `src/` edit by any lane invalidates the pin - the battery-time
re-pin (prereg 7.8) must be taken after all writers stop.

## 6. Verification (all offline; commands and results)

```
python3 -m py_compile src/fruit_sorting/tasks.py src/fruit_sorting/rl_env.py   # exit 0   (logs/p8c/10_compile.txt)
python3 logs/p8c/verify_monitor_stub_lf_p81.py                                 # exit 0; both pins  (logs/p8c/20_stub_pins_p81.txt)
python3 logs/p7c/verify_monitor_stub.py                                        # exit 0; P7-2b back-compat  (logs/p8c/21_stub_p7c_compat.txt)
STUB_FLOOR=0 python3 logs/p8c/verify_monitor_stub_lf.py                        # replay 29/0/2/33; its own assertion FAILs (harness-side)  (logs/p8c/23_...)
SELFCHECK_LOG=logs/p8c/30_selfcheck.log scripts/selfcheck.sh                   # exit 0: PASS 0 failures, 1 skipped
```

The selfcheck's 21 checks all PASS; `motion budgets` is SKIP (needs an
acceptance run log, a simulator step this lane must not take). Its stdout is
`logs/p8c/31_selfcheck_stdout.txt`; the full per-check log is
`logs/p8c/30_selfcheck.log`.

Byte-inert at default (offline evidence): the P7-2b harness passes unchanged;
the floor=0 pin is per-leg identical to the floor-0 reference; the knob
default is 0.0 and at 0.0 the load term is a tautology (the clamp probe); and
with `FRUIT_CARRY_MONITOR` unset `mon_leg` is `None`, so no monitor code runs
at all (the new env read is one `os.environ.get` at task construction, like
the two existing monitor knobs). The remaining no-harm items of the frozen
prereg (7.6: acceptance 9/10 + fingerprint + stream identity; the two-line
dense re-record + `190`) are simulator battery steps, not run here.

## 7. Pins (end of lane)

| item | value |
| --- | --- |
| HEAD / branch | `7ff9f4804734209490f052708b4a24076235779d` / `p-supply` |
| `git status --short` | exactly `M src/fruit_sorting/rl_env.py`, `M src/fruit_sorting/tasks.py` (`logs/` is gitignored; `logs/p8c/` holds the artifacts) |
| `src/fruit_sorting/tasks.py` | **`12feced3b6204f06bb32cb878efb5e15`** |
| `src/fruit_sorting/rl_env.py` | **`7bd07b662595c56fa45ca12e7a87a7ff`** (`TASKS_MD5 = 12feced3...`) |
| `src/fruit_sorting/policy/trigger.py` | `d7ec85fca5661a54473f7c6a69445fbc` (untouched) |
| `src/fruit_sorting/policy/runtime.py` | `ffb76bfd9bed1e71f6599c075d06a6c1` (untouched) |
| `src/fruit_sorting/fruits.py` | `f5671a65d6f72eb69a81e12ac6e0bf53` (untouched) |
| harness `logs/p8c/verify_monitor_stub_lf_p81.py` | `668f42a0bf9f47b22368696fc26a5178` |
| harness `logs/p8c/verify_monitor_stub_lf.py` (concurrent lane) | `6965d2adc71048ddc53012d01dd5ebe6` |
| `logs/p7c/verify_monitor_stub.py` (P7-2b, unchanged) | `6ddd966fd9dd621b186cd510f6d79a70` |
| `logs/p8/PREREG_CARRY_MONITOR_LF.md` | `b3604b7fb30e825a1f5c9c9b2a285fb6` |
| checkpoint `moe_v13s` | `61da390a85fa209496b54477a8255d23` (untouched) |
| `configs/*` | untouched |

No commit, no branch change, no simulator step. The battery-time re-pin
(prereg 7.8) happens on the battery lane per the P7-2b pattern.

## 8. Artifact list (`logs/p8c/`)

`00_head_status.txt`, `01_md5s.txt`, `02_diff_tasks.txt`, `03_diff_rl_env.txt`,
`04_concurrent_write_note.txt` (the collision/pin history),
`05_final_state.txt` (final re-verification), `10_compile.txt`,
`20_stub_pins_p81.txt` (this lane's harness, both pins),
`21_stub_p7c_compat.txt` (P7-2b harness, floor=0 pin),
`22_stub_battery_harness_floor35.txt` / `23_stub_battery_harness_floor0.txt`
(the concurrent harness, both floors), `30_selfcheck.log` /
`31_selfcheck_stdout.txt`, `verify_monitor_stub_lf_p81.py`,
`IMPLEMENTATION.md` (the orchestrator's completion record), `P81_DETAIL.md`
(this file), `WORKLOG_entry.md`.
