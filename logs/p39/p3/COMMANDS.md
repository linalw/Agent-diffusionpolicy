# P39 phase 3 — the exact commands (provenance)

Tree at every battery: `scene.py` `988985ef`, `tasks.py` `112d2cb1`,
`rl_env.py` `238e90a4`, `configs/motion_reference.json` `25ade92b`,
`configs/motion_reference_twoline.json` `181c9151`, HEAD `e061d94`
(`tree_md5_before.txt`; re-checked after, `tree_md5_after.txt`).
No commit, no `configs/` change, no `src/` edit.

Every battery is **one `scripts/154_claim_run.sh` claim** (A1.6) whose payload is
a driver that runs the arms **interleaved C -> S -> F1** inside that one claim
(so the claim is held for the whole battery and no other lane's simulator can
interleave). The drivers are `logs/p39/p3/run_*.sh`; each arm's own log is
`logs/p39/p3/<battery>_<arm>.log`; the claim log is
`logs/p39/p3/claim_<battery>.log` and carries the per-arm wall times.

| # | battery | claim | claim log | RUN_LIMIT |
|---|---|---|---|---|
| 1 | pear (PRIMARY) | `RUN_LIMIT=5400 bash scripts/154_claim_run.sh logs/p39/p3/claim_pear.log bash logs/p39/p3/run_pear.sh` | `claim_pear.log` | 5400 s |
| 2 | acceptance | `RUN_LIMIT=5400 bash scripts/154_claim_run.sh logs/p39/p3/claim_accept.log bash logs/p39/p3/run_accept.sh` | `claim_accept.log` | 5400 s |
| 3 | `47` probe | `RUN_LIMIT=2400 bash scripts/154_claim_run.sh logs/p39/p3/claim_probe47.log bash logs/p39/p3/run_probe47.sh` | `claim_probe47.log` | 2400 s |
| 4 | mechanism | `RUN_LIMIT=5400 bash scripts/154_claim_run.sh logs/p39/p3/claim_mech.log bash logs/p39/p3/run_mech.sh` | `claim_mech.log` | 5400 s |
| 5 | two-line | `RUN_LIMIT=5400 bash scripts/154_claim_run.sh logs/p39/p3/claim_twoline.log bash logs/p39/p3/run_twoline.sh <arms>` | `claim_twoline.log` | 5400 s |

## Per-arm commands, exactly as executed inside each driver

Arms: **C** = both knobs unset; **S** = `FRUIT_FINGER_TIP_DELTA=0` (re-authored
AABB control); **F1** = `FRUIT_FINGER_TIP_DELTA=-0.004`.

### 1. Pear battery (PRIMARY)

```
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_SUPPLY_SPECIES=pear ATTEMPTS=10 SEED=5 \
    scripts/run.sh scripts/20_pick_place.py
# S  + FRUIT_FINGER_TIP_DELTA=0
# F1 + FRUIT_FINGER_TIP_DELTA=-0.004
```

The WORKLOG/P32 recipe (shipped scatter, species lock, 9 attempts expected:
attempt 7 is `no eligible fruit`).

### 2. Acceptance (report + N1)

```
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p39/p3/accept_<arm>.log \
    FRUIT_FINGER_TIP_DELTA=<arm, omitted for C> scripts/accept.sh
```

`accept.sh` itself supplies `HEADLESS=1 FRUIT_MOTION_REPORT=1 ATTEMPTS=10` and
the default `SEED=5`, then runs `105_motion_regression.py` against
`configs/motion_reference.json` (the gate + the fingerprint line).

### 3. `47` probe (N4 / N4b)

```
HEADLESS=1 FRUIT_FINGER_TIP_DELTA=<arm, omitted for C> \
    scripts/run.sh scripts/47_robot_collision.py
```

### 4. Mechanism batch (A2.7)

```
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CARRY_ATTITUDE=1 ATTEMPTS=10 SEED=5 \
    FRUIT_FINGER_TIP_DELTA=<arm, omitted for C> \
    scripts/run.sh scripts/20_pick_place.py
```

The acceptance scenario with the `[attitude]` print ON in every arm (C is the
lip anchor); the identity/class claims are made on the print-off runs.

### 5. Two-line gate (N3)

```
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_BIARM=1 \
    FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10 SEED=5 \
    FRUIT_FINGER_TIP_DELTA=<arm> scripts/run.sh scripts/20_pick_place.py
python3 scripts/190_twoline_gate.sh logs/p39/p3/twoline_<arm>.log
```

Run only for the arms whose pear/acceptance **filtered** `[fruit]` stream moved
vs C (A2.7 deviation, recorded in `RESULT.md`).

## Analysis

```
python3 logs/p39/p3/filter_stream.py --counts logs/p39/p3/<battery>_<arm>.log    # A2.2 counts
python3 logs/p39/p3/filter_stream.py --diff   logs/p39/p3/<A> logs/p39/p3/<B>    # filtered identity
python3 logs/p39/p3/p3_report.py                                                 # the whole report
```

Filter (A2.2): `grep '\[fruit\]' <log> | grep -v '\[attitude\]'` (plus the
phase-2-only `grep -v 'finger tip delta'`).
