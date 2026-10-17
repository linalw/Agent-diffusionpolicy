# P10-C.3 RESULTS (2026-10-17): the two-line carry-monitor default flip - all endpoints clear, the adoption verified

Pre-registration: `logs/p10c2/PREREG_ADOPT_FLIP.md` (frozen + the amendment). Tree at battery
time: `tasks.py` **6574d92eafe38f1025b880d39a9410f9**, `rl_env.py`
**8413fece2203c1bccd84b0d5c3830eb3**, `scripts/40_collect_demos.py`
**59cbe06443ecf18695856daa962a5f3e**.

## 1. The battery (5 runs + the acceptance) - every identity holds

| run | expectation | result |
| --- | --- | --- |
| `70_flip_seed5` (no resolution env) | bit-identical to the gated `61_seed5_B_gate` | **0 diff lines** (13/20, 196.7 s, 3.97) |
| `71_flip_seed11` (the same) | bit-identical to `62_seed11_B_gate` | **0 diff** (10/20, 183.4 s, 3.27) |
| `72_flip_seed23` (the same) | bit-identical to `63_seed23_B_gate` | **0 diff** (16/20, 184.7 s, 5.20) |
| `73_restore_gate0_seed11` (`FRUIT_CARRY_MONITOR_CONFIRM_MM=0`) | bit-identical to the ungated `51_seed11_B` | **0 diff** |
| `74_restore_off_seed5` (`FRUIT_CARRY_MONITOR_TWOLINE=0`) | bit-identical to the A control `10_armA_diag` | **0 diff** |
| `80_accept` (the shipped acceptance) | 9/10 + fingerprint matches + 385/385 | **PASS**: 9/10, `fingerprint: matches`, `logs/accept.log` **0 diff** vs `logs/p2d/90_accept.log` |

The diffs are on the `[fruit]` stream modulo the reporting rows (`[carry]`/`[monitor]`/
`[ready]`/`[diag]`).

## 2. The endpoints

1. **Primary (the flip reproduces the tested config): PASS** - all five identities hold.
2. **The acceptance no-harm: PASS** (9/10 + fingerprint matches + 385/385).
3. **The offline suite: PASS** - the new `check_flip_resolution.py` (37 checks: the 64-row
   truth table over the 4 knobs x the session kinds x the env states, the real
   `_dynamic_profile` statements exec'd vs an independent reference, every non-flip row
   byte-inert vs the real `__init__` reads, the manifest field, the `TASKS_MD5` pin); all
   historical stubs (the P10-C scope, the P10-C.2 confirm gate, the skip predicate, the
   P7c/P8c monitor family); `selfcheck.sh` PASS; `107_collect_merge_test.py` PASS (15 checks);
   `172` PASS (74 checks).

## 3. The kills

None fired: no flip run failed its identity; the acceptance did not move; no untouched-scope
stub failed; the collector manifest field verified (the flip stub's layer 4, `logs/p10c3/check_flip_resolution.py`; `107` does not read the manifest - `logs/p10c3/IMPLEMENTATION.md` section 3).

## 4. The re-baseline

`configs/motion_reference_patch.json` **re-recorded** from `70_flip_seed5` (the new branch);
the pre-flip file preserved as `configs/motion_reference_patch_pre_p10c3.json`. Verification:
`TWOLINE_REF=configs/motion_reference_patch.json scripts/190_twoline_gate.sh -m 0.5
logs/p10c3/70_flip_seed5.log` reads **PASS** + `fingerprint: matches` + the motion budgets
inside bounds. (The dense `configs/motion_reference_twoline.json` is untouched - the dense
scenario is not part of this battery; its re-record is a named follow-up when the dense
battery is next run.)

## 5. Verdict

**The two-line carry monitor + the slip-confirmation gate are the shipped two-line default.**
A two-line session (`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1`) now arms the monitor (gate 8.0 mm)
with no env set; `FRUIT_CARRY_MONITOR_TWOLINE=0`, `FRUIT_CARRY_MONITOR_CONFIRM_MM=0` and
`FRUIT_CARRY_MONITOR=0` restore their respective pre-flip behaviors (all verified
bit-identically). The shipped single-arm line, the shared-station bimanual and the
direct/policy interface are byte-unchanged. The collector manifests record
`collection.carry_monitor` (`"auto"` = the flip) so a post-flip two-line recollection is
identifiable as a new branch. The measured gain of the adopted config (from P10-C.2): the
pooled outcome 39/60 >= the control 38/60 > the ungated 36/60; the pooled interval -10.4 %.
