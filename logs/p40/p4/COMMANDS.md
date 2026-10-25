# P40 phase 4 — the exact commands (provenance)

Tree at every run: `tasks.py` **`ec991e5c`** (the P39 tree `1790b87` + the
P40-G0 `FRUIT_GRIP_EFFORT` instrument + the phase-3 R-S knob + the phase-4
path-scoped `regrasp_cap`), `rl_env.py` **`8ebb8d87`** (`TASKS_MD5`
metadata-only follow), `scene.py` `988985ef`,
`configs/motion_reference.json` `25ade92b -> adef05c9` and
`configs/motion_reference_twoline.json` `d0326030 -> d87c3cdf` (both re-recorded
*by this phase*, from runs 1 and 2 below), HEAD `1790b87`.
`logs/p40/p4/tree_md5_before.txt` is the pin set taken before run 1;
`logs/p40/tree_md5_after.txt` is the final tree.

Both simulator runs are one `scripts/154_claim_run.sh` claim each, **knob unset**
(the flip is the configuration under test).

| # | item | claim log | payload | RUN_LIMIT | claimed -> exit |
|---|---|---|---|---|---|
| 1 | the flip, single arm | `claim_accept_flip.log` | `SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p40/p4/accept_flip.log scripts/accept.sh` | 2400 s | 01:49:03 -> 01:53:01 (exit 1, rate only) |
| 2 | the flip, two-line | (the log itself) | the /tmp payload below | 2400 s | 01:53:48 -> 01:58:09 (exit 0) |

## 1. The single-arm acceptance (the flip, knob unset)

```
RUN_LIMIT=2400 SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p40/p4/accept_flip.log \
    scripts/154_claim_run.sh logs/p40/p4/claim_accept_flip.log \
    SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p40/p4/accept_flip.log scripts/accept.sh
```

Control: `logs/p39/p3/accept_C.log` (the same command before the flip).

## 2. The two-line battery (the flip, knob unset)

```
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 \
    FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 \
    ATTEMPTS=10 SEED=5 \
    scripts/run.sh scripts/20_pick_place.py        # -> logs/p40/p4/twoline_flip.log
```

`FRUIT_MOTION_REPORT=1` is set to match the control (`logs/p39/p3/twoline_C.log`)
and is what the `190` gate reads the descent/carry rows from.

Control: `logs/p39/p3/twoline_C.log` (the same command before the flip; the
brief's version of this line omits `FRUIT_MOTION_REPORT=1`, which would leave
the gate without `[motion]` rows).

## 3. The re-records (both references move with the flip)

```
cp configs/motion_reference.json          logs/p40/motion_reference_single_pre_p40.json
cp configs/motion_reference_twoline.json  logs/p40/motion_reference_twoline_pre_p40.json
python3 scripts/105_motion_regression.py logs/p40/p4/accept_flip.log \
    --write-fingerprint configs/motion_reference.json          # adef05c966133de5cc07a20772b9f7f1
python3 scripts/105_motion_regression.py logs/p40/p4/twoline_flip.log \
    --write-fingerprint configs/motion_reference_twoline.json  # d87c3cdf37f797342df3bbaebc0836e9
```

`scripts/189_w7a_chain.sh` was **not** run (it rewrites the two-line reference).

## 4. The two gate proofs (after the re-record)

```
python3 scripts/105_motion_regression.py logs/p40/p4/accept_flip.log \
    --fingerprint configs/motion_reference.json     > logs/p40/p4/10_gate_accept_flip.txt
bash scripts/190_twoline_gate.sh logs/p40/p4/twoline_flip.log \
                                                    > logs/p40/p4/11_gate_twoline_flip.txt
# the pre-record state, re-derived from the two archives:
python3 scripts/105_motion_regression.py logs/p40/p4/accept_flip.log \
    --fingerprint logs/p40/motion_reference_single_pre_p40.json   # DIFFERS
TWOLINE_REF=logs/p40/motion_reference_twoline_pre_p40.json \
    bash scripts/190_twoline_gate.sh logs/p40/p4/twoline_flip.log # FAIL (fingerprint)
```

## 5. The mechanism, offline

```
python3 logs/p39/p3/filter_stream.py --diff logs/p40/p3/regrasp2_accept.log \
    logs/p40/p4/accept_flip.log          # 339/339 IDENTICAL
python3 logs/p39/p3/filter_stream.py --diff logs/p40/p3/regrasp2_twoline.log \
    logs/p40/p4/twoline_flip.log         # 430/430 IDENTICAL
python3 logs/p40/p3/k_map.py logs/p39/p3/twoline_C.log logs/p40/p4/twoline_flip.log
python3 scripts/186_w6_report.py logs/p39/p3/twoline_C.log logs/p40/p4/twoline_flip.log
```

## 6. No-harm

```
bash scripts/selfcheck.sh > logs/p40/selfcheck.log        # PASS: 0 failures, 1 skipped
python3 scripts/96_motion_check.py > logs/p40/p4/20_motion_check.txt   # all motion checks passed
```
