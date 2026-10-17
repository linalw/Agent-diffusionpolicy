# P10-C.3 PREREG (FROZEN): the two-line carry-monitor default flip (the adoption)

Frozen 2026-10-17 before any Tier-A run. Tree pin recorded at battery time (the
implementation lane's md5). Branch `p-supply`; the P10-C.2 wrap at `f2cdadd` (tag
`p10c2-gate`).

## Why (the adoption case, `logs/p10c2/C2_RESULTS.md`)

The P10-C.2 battery cleared every pre-registered endpoint: **zero false positives** (the gate
cancels the marginal-slide trips; the 6.3 mm pear places again), **10/15 clean fires retained**
(all >= 19 mm), the pooled outcome **39/60 >= the control's 38/60 > the ungated 36/60**, the
pooled interval **-10.4 %** (14.99 vs 16.73 s), no new failure reasons, the motion budgets
clean, and the knob-off paths byte-identical (the A anchor 0 diff; the acceptance 385/385).
The P10-C.1 pre-committed framework said: "If B >= A pooled on the interval across
SEED=5/11/23 AND no kill fires on any seed -> adoption case solid: a new pre-registration for
the two-line default flip following the W7-A park-gate pattern". That condition is met.

## The flip (the W7-A pattern; two-line-scoped only)

A two-line session (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`) resolves, with the relevant env
unset:

* `FRUIT_CARRY_MONITOR` -> **1** (the monitor arms on the two-line scripted catch);
* `FRUIT_CARRY_MONITOR_TWOLINE` -> **1** (the scope knob);
* `FRUIT_CARRY_MONITOR_CONFIRM_MM` -> **8.0** (the gate; the P10-C.2 tested value);
* `FRUIT_CARRY_MONITOR_LOAD_FLOOR` -> **3.5** (already the shipped default).

Explicit restores (each tested): `FRUIT_CARRY_MONITOR_TWOLINE=0` -> the pre-flip two-line
behavior (no monitor); `FRUIT_CARRY_MONITOR_CONFIRM_MM=0` -> the ungated monitor;
`FRUIT_CARRY_MONITOR=0` -> the monitor off (the master wins).

**Untouched scopes (the no-harm claims):** the shipped single-arm scripted line (the
acceptance), the shared-station bimanual (`FRUIT_BIARM=1` without TWOLINE - the scope
predicate excludes it), and the direct/policy interface (its knobs stay default-off).

**The collector guardrail** (the W7-B lesson): the two-line collector
(`40_collect_demos.py` with `FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`) inherits the flip, so the
shard manifest gains a `collection.carry_monitor` field recording the resolution (`"auto"` =
the flip; an explicit value otherwise) - the W7-C.1 `collection.park_early` pattern. A
post-flip two-line recollection is a **new branch**; the manifest field identifies it.

## The verification battery (Tier A)

| run | expectation |
| --- | --- |
| `flip_seed5` - the patch battery, **no relevant env** | **bit-identical to the P10-C.2 gated seed-5 run** (`61_seed5_B_gate.log`) modulo reporting rows - the flip resolves to the tested config |
| `flip_seed11` - the same | **bit-identical to `62_seed11_B_gate.log`** (the acting branch) |
| `flip_seed23` - the same | **bit-identical to `63_seed23_B_gate.log`** |
| `restore_seed11` - `FRUIT_CARRY_MONITOR_TWOLINE=0` | **bit-identical to the P10-C.1 ungated `51_seed11_B.log`** (the explicit restore) |
| `accept` - the shipped acceptance | 9/10 + `fingerprint: matches` + 385/385 vs `logs/p2d/90_accept.log` |

**The re-baseline** (the flip moves the two-line branches): `configs/motion_reference_patch.json`
re-recorded from the flip seed-5 run (the reference the patch battery gates against; the old
file preserved as `configs/motion_reference_patch_pre_p10c3.json`). The dense two-line
reference (`configs/motion_reference_twoline.json`) is **not** re-recorded here - the dense
scenario is not part of this battery; its re-record is a named follow-up when the dense
battery is next run (the W7-A tooling note's own convention).

## Endpoints (pre-registered)

1. **Primary: the flip reproduces the tested config** - the three flip runs bit-identical to
   their gated records (modulo reporting rows) and the restore run bit-identical to the
   ungated record.
2. The acceptance no-harm: 9/10 + fingerprint matches + 385/385.
3. The offline stub suite: the extended scope truth table (the flip resolution + the explicit
   restores + the untouched scopes) PASS; `selfcheck.sh` PASS; `172` PASS.

## Kills (any one)

1. Any flip run failing its bit-identity expectation (the flip does not resolve to the tested
   config);
2. the acceptance moving (any diff vs `logs/p2d/90_accept.log`, the rate, or the fingerprint);
3. any untouched-scope stub failing;
4. the collector manifest field missing or wrong (verified by the offline collect test).

## What this does NOT do

It does not change the shipped single-arm line, the shared-station bimanual, or the
direct/policy interface; it does not change the threshold (8.0 mm stays the shipped two-line
value; the Oracle's 9.5 mm robustness note remains a named untested option); it does not make
the two-line the overall default (the R5 decision stands - `FRUIT_BIARM_TWOLINE=1` remains
opt-in).
