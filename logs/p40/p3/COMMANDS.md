# P40 phase 3 — the exact commands (provenance)

Tree at every battery: `tasks.py` **`a5cfb6d8`** (the P39 tree `1790b87` +
the P40-G0 `FRUIT_GRIP_EFFORT` instrument + this phase's default-off R-S
selection knob), `rl_env.py` `TASKS_MD5` metadata-only follow,
`scene.py` `988985ef`, `configs/motion_reference.json` `25ade92b`,
`configs/motion_reference_twoline.json` `d0326030` unchanged
(`tree_md5_before.txt`, taken before the metadata-only pin follow
`e137eb59 -> 9f15f3b5`; `tree_md5_after.txt` is the tree every battery ran on).
No commit, no `configs/` change.

Every battery is **one `scripts/154_claim_run.sh` claim**. Two naming notes:
the claim's log path *is* the payload's own output (the payload is the run, not
a multi-arm driver), so `claim_regrasp2_twoline.log` and
`regrasp2_twoline.log` are the same bytes (the second is the brief's filename);
and `RUN_LIMIT` is the wall ceiling of the claim, not the expected duration.

| # | item | claim log | payload | RUN_LIMIT | claimed -> exit |
|---|---|---|---|---|---|
| 1 | R-R (a) two-line | `claim_regrasp2_twoline.log` | `run_regrasp2_twoline.sh` | 1800 s | 01:13:55 -> 01:18:55 (300 s) |
| 2 | R-R (b) acceptance | `claim_regrasp2_accept.log` | `env SKIP_SELFCHECK=1 ACCEPT_LOG=... FRUIT_REGRASPS=2 scripts/accept.sh` | 1800 s | 01:19:25 -> 01:23:22 (237 s) |
| 3 | R-S knob-OFF arm (byte-identity) | `claim_nearest_pair.log` | `run_nearest_pair.sh` | 2400 s | 01:25:36 -> 01:30:02 (266 s) |
| 4 | R-S knob-ON arm | `claim_nearest_on.log` | `run_nearest_on.sh` | 1800 s | 01:30:49 -> 01:35:11 (262 s) |

Claim 1 was retried once after 5 s: `run_regrasp2_twoline.sh` had the wrong
relative `cd` depth, so `scripts/run.sh` was not found (exit 127, **no simulator
started**). Claim 3's second arm never ran: `run_nearest_pair.sh` passed the env
assignment through `"$@"`, which bash cannot expand into a prefix assignment
(`FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1: command not found`, exit 127, again with
no simulator run), so the ON arm is claim 4 and `nearest_off.log` — which did
run, the first arm of claim 3 — is the byte-identity arm of the same stretch.

## The exact per-arm commands

### 1. R-R (a) — two-line, `FRUIT_REGRASPS=2`

```
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 \
    FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 \
    FRUIT_REGRASPS=2 ATTEMPTS=10 SEED=5 \
    scripts/run.sh scripts/20_pick_place.py
```

Control: `logs/p39/p3/twoline_C.log` (same command without `FRUIT_REGRASPS`;
`ATTEMPTS=10 SEED=5` are the shipped defaults for this scenario).

### 2. R-R (b) — single-arm acceptance, `FRUIT_REGRASPS=2`

```
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p40/p3/regrasp2_accept.log \
    FRUIT_REGRASPS=2 scripts/accept.sh
```

Control: `logs/p39/p3/accept_C.log` (same command, knob unset).

### 3. R-R (c) — the two-line gate (offline)

```
bash scripts/190_twoline_gate.sh logs/p40/p3/regrasp2_twoline.log
# -> logs/p40/p3/190_regrasp2_twoline.txt
```

(The brief wrote `python3 scripts/190_twoline_gate.sh ...`; 190 is a bash
script, so `python3` dies on its `case` block. `scripts/189_w7a_chain.sh` was
**not** run — it rewrites `configs/motion_reference_twoline.json`.)

### 4. R-S — the knob-OFF arm (byte-identity of the unset path)

```
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p40/p3/nearest_off.log scripts/accept.sh
```

### 5. R-S — the knob-ON arm

```
export FRUIT_SELECT_NEAREST_ABOVE_FLOOR=1
SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p40/p3/nearest_accept.log scripts/accept.sh
```

## Analysis

```
python3 logs/p39/p3/filter_stream.py --diff logs/p39/p3/accept_C.log logs/p40/p3/nearest_off.log
python3 logs/p39/p3/filter_stream.py --diff logs/p39/p3/twoline_C.log logs/p40/p3/regrasp2_twoline.log
python3 logs/p40/p3/k_map.py logs/p39/p3/twoline_C.log logs/p40/p3/regrasp2_twoline.log
python3 scripts/186_w6_report.py logs/p39/p3/twoline_C.log logs/p40/p3/regrasp2_twoline.log
python3 logs/p40/p3/p3_report.py logs/p39/p3/accept_C.log \
    logs/p40/p3/regrasp2_accept.log logs/p40/p3/nearest_off.log \
    logs/p40/p3/nearest_accept.log
```
