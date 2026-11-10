# P136 results - the prediction-gated handover is the default

The flip is `tracking.tracking_resolution`: `FRUIT_TRACK` unset resolves **on for
the scripted line** (`default`), **off for the two policy interfaces**
(`scope-off`); `=0` restores the pre-P136 path. `FRUIT_DESCENT_TRACK` and
`FRUIT_TRACK_WAIT` unset follow `FRUIT_TRACK`; an explicit value wins.

| check | result |
|---|---|
| shipped acceptance (two-line, 10 attempts) | **7/10 = 70 %**, 9.5 s/attempt, **budgets pass** (worst `|v|max` 0.126 against 0.161, lurch 0.059 against 0.291) |
| its fingerprint | moved (the gate shifts the descent's start) -> **`configs/motion_reference.json` = `configs/motion_reference_twoline.json` = `61fb5202`**, re-recorded from that same run; `190: PASS` against it |
| single arm (`FRUIT_BIARM=0`, flip on, 10 attempts) | **5/9 = 56 %**, 15.4 s/attempt -> **`configs/motion_reference_single.json` = `18b101bf`** (pre-flip `8952c320` archived) |
| policy canary smoke (2 episodes) | **2/2**, and it resolves **`track=0(scope-off)`** - the interface of record keeps the pre-P136 catch |
| collector probe (1 episode) | its `manifest.json` carries **`physics.tracking`**: `{on: true, origin: default, mode: cv, gate: 0.04, tau: 0.3, corr_max: 0.08, source: truth, scripted: true}` |
| `selfcheck.sh` | **PASS (0 failures, 1 skipped)**, the P135 leg now 40 checks (the resolver table: unset/scripted on, unset/policy off, `=0` restores, each sub-knob independent) |
| `106` / `107` | **OK** / **PASS (21 checks)** |

**No rate is claimed.** On the nominal belt the tracker is a measured **tie**
(P135 §4: 11/13/11 ticks against 10/13/11), so the acceptance's 7/10 against the
pre-flip 8/10 is a branch draw, not a regression and not an improvement; the
argument for the flip is §0 of `PREREG.md` - under a varying conveyor the shipped
gate misses the handover by 298-407 mm and the gated one converts every one.

**Pre-flip archives**: `logs/p136/motion_reference_pre_flip.json`,
`..._twoline_pre_flip.json`, `..._single_pre_flip.json`. `FRUIT_TRACK=0`
reproduces them.

**Direct/policy paths are untouched by construction**: `rl_env` and
`60_eval_policy.py` build the task with `scripted=False`, so their rows print
`track=0(scope-off)` and their stores say `origin: scope-off`.
