# P269 method notes: two harness hazards that cost wall time

**2026-11-25, `logs/p269/`.** Neither is about the robot; both are about running this cell on
this machine. They are recorded because each one silently produced a *missing* cell rather
than a failed one.

---

## 1. A cell can hang **before it allocates any GPU memory**

Observed: `C_s907` sat for **2 h 31 min** with a two-line log (`[run.sh] soft nofile=...` and
the conda warning), the kit python in state `S` / `futex_wait_queue`, **0 % CPU**, **2
threads**, and **no entry in `nvidia-smi --query-compute-apps`** - i.e. it was blocked in
start-up, never reaching the scene.

**The machine's state at the time**: **16.5 GB of 32.6 GB of GPU memory held by other
processes** (six `dynvla*` envs, one of them 7.4 GB). This is the condition the record already
names for the two-line ("this build wedges at the loop header when other simulators hold ~16
GB"), and here it manifested **earlier**: before the SDK init.

**What to do**: treat a log that has not grown past the wrapper's two lines in ~10 min as a
**hang, not a slow start**, and re-run that cell. A hung cell leaves **no result row**, so a
missing `V*.log`/`picks placed` must be re-run - **never** read as a zero or as "not
evaluable".

**And it is transient**: after the stuck cell was cleared, the *same* command form ran
normally on the same GPU (17.2 GB held by others) - the next two cells logged 17-22 KB within
their first minute.

## 2. `pkill -f "<script>"` kills **your own shell**

`pkill -f 110_rl_rollout.py` matched the **calling shell's own command line** (which contains
that string), so the shell was **SIGTERMed (exit 143)** mid-command and the rest of the line
never ran - twice, each time killing a *live* cell and letting the batch advance.

**What to do**: bracket one character, `pkill -9 -f "[1]10_rl_rollout"`, so the pattern cannot
match itself. Kill by the **wrapper's** PID from `ps`, not by a substring of the command that
launched it.

## 3. Consequence for the P269 cells

The batch order was `C(907, 908)` then `T(907, 908)`. The two kills consumed `C_907` and
`C_908`, so the batch produced the **T** arm only; **the C arm has to be re-run** before the
registration is read. The pre-registration stands unchanged - it does not care which order
the cells ran in, only that both arms are complete and the seeds are 907/908.
