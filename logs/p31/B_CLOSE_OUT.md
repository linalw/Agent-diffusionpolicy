# P31-B close-out — the wait gate A/B is negative (no adoption)

Status: **closed negative** (2026-10-22). The knob stays default off; the shipped
default is `FRUIT_WAIT_GATE=0` (unset).

## Protocol (as run)

`logs/p31/run_ab_wait.sh` -> `scripts/112_rl_ab.sh`, 15 episodes x 5 runs per
arm, seeds 77/101/202/303/404, policy seed 11, both arms `moe_v13s`
(`61da390a`), direct presentation, the arrival trigger (lead 0.9, lateral 0.16,
ACQ on), the W6 patch supply (balanced A:B:C 0.375/0.375/0.25), belt 0.12.
ARM_A = `FRUIT_WAIT_GATE=0` (baseline), ARM_B = `FRUIT_WAIT_GATE=1`.

**Protocol deviation (material)**: `WAIT_GATE_DESIGN.md` section 8 / the P31-A
WORKLOG entry's Owed list required `FRUIT_WAIT_GATE_DIAG=1` on the treatment
arm so the endpoint would be the gate's own counters (`_wait_gate_skipped`,
`_wait_gate_held`) and the model-call count. The driver did **not** set it
(`run_ab_wait.sh` sets only `FRUIT_ACQ_DIAG=1 FRUIT_CARRY_DIAG=1`), so no
`[gate]` rows exist and the mechanism endpoint cannot be read from this batch.

## Outcome (the report, `logs/p31/90_driver_ab.log`)

| | A (gate off) | B (gate on) |
|---|---|---|
| pooled | **28/75 = 37.3 %** | **26/75 = 34.7 %** |
| paired | 5 both ok / 10 both fail / 5 B-only / 4 A-only | |
| sign test | p = 0.5000 (discordant 9) | |
| median cycle | 1837 ticks | 1837 ticks |
| new failure reasons | none | none |

Per class (A vs B): apple 2/10 vs 2/8; kiwi 2/5 vs 2/8; lychee 5/7 vs 6/9;
orange 1/11 vs 1/14; peach 0/6 vs 3/10; pear 3/7 vs 4/6; **strawberry 6/11 vs
3/8 (-17 pt)**; tomato 9/18 vs 5/12.

The `decision=` episode field (the policy steps) reads A 241.7 vs B 263.1
(+8.8 %) pooled - **not** the model-call counter and confounded by the class
mix (the two arms took different fruit after divergence); it cannot be read as
"the gate increased the inference count".

## Verdict

- **No measured improvement; no adoption.** The gate is not shipped (default
  off), the knob remains a default-off measurement interface.
- The pre-registered kill criterion ("a paired no-fire increase 5-0 or worse")
  is **not evaluable** from this batch (the fire census needs the gate diag or
  a per-episode fire extraction; the outcome is already non-positive).
- The mechanism (does the gate cut the model calls?) is **unanswered** because
  of the missing `FRUIT_WAIT_GATE_DIAG=1`. A single diagnostic re-run
  (1 run/arm with the diag) is the only named follow-up; it would not change
  the outcome verdict.
- The lane's artifacts: `logs/p31/90_driver_ab.log` (the report),
  `logs/p31/ab/{A,B}_{1..5}.log`, `logs/p31/ab/raw/`, the driver
  `logs/p31/run_ab_wait.sh`, the design `logs/p31/WAIT_GATE_DESIGN.md`, the
  implementation `logs/p31/WORKLOG_ENTRY.md`, the probes
  `logs/p31/router_*.py`.
