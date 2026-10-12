# OPS: the periodic self-check and the anti-stall playbook

`scripts/191_ops_selfcheck.sh` is the periodic ops self-check for this repo
(P-PLAN P1, 2026-10-12; hardened by P1.1 - true resume semantics, the guarded
group-kill, the GPU-idle gate, the wrap suppression while a wrapper is alive,
path-anchored sim matching). It answers one question in a few seconds: *is the
project moving, and if not, what exactly should be resumed?* It is built for the
observed failure modes of long multi-lane sessions - renderer wedges, lanes
parked on unanswerable permissions, chains whose wrap never happened, idle
lanes, and stale claims - and it is safe to run while a simulator is running.

## Contract

* **Read-only.** The default mode reads (`stat`, `readlink /proc`, `pgrep`,
  `ps`, `git`, a `flock -n` probe on free slot locks, and read-only sqlite).
  It **never kills, restarts, moves or commits anything**. The `actions:` block
  is a recommendation list, with the exact command lines for a human or a
  wrapper to run.
* **Exit codes** (a wrapper can branch on them):
  * `0` - `OK`, `STALLED-SIM` or `STALLED-CHAIN` (report-only);
  * `2` - `ACTION` (a stall with an identified recovery);
  * `1` - `--selftest` failure; `64` - usage error.
* **No side files outside `logs/ops/`**: `state.tsv` (growth snapshots) and
  `watch.log` (one line per watch iteration). Both are ignored by git.

## What it checks

| section | what it reads | why |
| --- | --- | --- |
| `sims` | `pgrep -f` for the simulator with a **path-anchored** pattern (`(^|/)python.sh( |$)`, `(^|/)kit/python/bin/python3( |$)`, so a stray `foo_python.sh` helper is not read as a sim), deduplicated by process group; each mapped to its log via `/proc/<pid>/fd/1` (fallback: the newest `*.log` under `logs/`, excluding `logs/ops/`), with size and mtime age | a sim whose log stops growing is a renderer wedge |
| growth | the previous check's size/mtime from `logs/ops/state.tsv` | `growth=+120B/35s` distinguishes "quiet for a moment" from "frozen" |
| `lanes` | `pgrep -af '[1]54_claim_run|[1]80_claim_slot|_driver'` | a live claim wrapper/driver means the lane is between its own steps; the `[wrap]` action is downgraded to a hint while one exists |
| `claims` | `logs/claims/slot*.lock` + `slot*.owner`; owner liveness via `kill -0`, free locks probed with `flock -n` | a dead owner's slot is already reclaimed by the kernel; the stale file is informational |
| `artifacts` | the newest logs per area (`logs/w*/*.log`, top `OPS_TOP_N`) | which chain was last active, and when |
| `git` | branch, dirty-path count, last commit age, the newest tags, whether HEAD is tagged | "chain done, wrap never happened" needs the dirty state |
| `gpu` | `nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader` | corroborates a wedge (CPU burning, GPU idle) - but only once the log has been frozen `>= 2x OPS_STALL_S`; an idle GPU alone is not corroboration |
| `load` | `/proc/loadavg` | machine-level context |
| `permissions` | `~/.local/share/opencode/opencode.db` read-only: `session_pending` rows mentioning permissions, and recent `permission` (`external_directory`) asks | the "lane parked on a permission the plugin transport cannot answer" class |

The check degrades silently per-section: no `nvidia-smi` -> `gpu: n/a`, no
`sqlite3`/DB -> `permissions: n/a`, not a git repo -> `git: n/a`.

## Verdicts

| verdict | condition | exit |
| --- | --- | --- |
| `OK` | nothing below | 0 |
| `STALLED-SIM` | a sim runs and its log has not grown for > `OPS_STALL_S` (default 300 s), but no recovery is corroborated yet | 0 |
| `STALLED-CHAIN` | no sim runs and the newest chain log is stale > `OPS_CHAIN_S` (default 600 s) | 0 |
| `ACTION` | a stall with an identified recovery: a frozen sim with a wedge marker / zero growth proved by the state snapshot / an idle GPU **with the freeze age >= 2x `OPS_STALL_S`**; a crash marker in a stale chain log; a chain that looks finished but the tree is dirty **and no claim wrapper is alive**; a stale claim owner; a pending permission ask | 2 |

`STALLED-*` are deliberately report-only: a quiet log during startup, a buffered
writer, or a genuinely idle night is not an emergency. `ACTION` only fires when
the tool can name what to do.

## Environment knobs

| variable | default | meaning |
| --- | --- | --- |
| `OPS_STALL_S` | `300` | sim-log no-growth threshold (seconds) |
| `OPS_CHAIN_S` | `600` | chain-log staleness threshold (seconds) |
| `OPS_TOP_N` | `5` | artifact rows printed |
| `OPS_CHAIN_GLOB` | `w*/*.log` | chain-log glob under `logs/` |
| `OPS_SIM_PATTERN` | `(^|/)[p]ython\.sh( |$)\|(^|/)[k]it/python/bin/python3( |$)` | path-anchored `pgrep -f` pattern for sims |
| `OPS_LANE_PATTERN` | `[1]54_claim_run\|[1]80_claim_slot\|_driver` | `pgrep -f` pattern for claim wrappers / drivers (`lanes`, `[wrap]` suppression) |
| `OPS_GPU_QUERY` | the `nvidia-smi` query | set empty to skip the GPU probe |
| `OPS_GPU_IDLE_PCT` | `5` | util % at/below which a frozen sim escalates - only with the log frozen `>= 2x OPS_STALL_S` |
| `OPS_WEDGE_MARKERS` | `Too many open files\|[collect] STALL\|Texture creation failed\|core dumped\|…` | `grep -E` crash/wedge signatures |
| `OPS_DONE_MARKERS` | `fingerprint: matches\|[claim_(run\|slot)] exit=0\|[fruit] DONE` | completion signatures for the wrap heuristic (no bare `PASS`) |
| `OPS_PERMISSION_S` | `3600` | "recent permission ask" window |
| `OPS_OPENCODE_DB` | `$HOME/.local/share/opencode/opencode.db` | session store; point at a missing file to skip |
| `OPS_ROOT` / `OPS_LOGS_DIR` / `OPS_CLAIM_DIR` / `OPS_STATE_FILE` / `OPS_WATCH_LOG` | repo defaults | path overrides (used by `--selftest`) |

## Modes

```bash
scripts/191_ops_selfcheck.sh                 # one check; humans + wrappers
scripts/191_ops_selfcheck.sh --watch 300     # loop; full report on verdict
                                             # transitions, one line per check
                                             # to logs/ops/watch.log
scripts/191_ops_selfcheck.sh --selftest      # offline: synthetic stale logs,
                                             # a fake sim and a fake claim in a
                                             # temp dir; asserts OK does not
                                             # fire and STALLED-SIM /
                                             # STALLED-CHAIN / ACTION do
```

The `--selftest` is deterministic and needs no simulator, GPU, DB or git repo.

## Cadence

* **During a Tier A sim batch** (a collection or an acceptance, 15 min - 2 h):
  run the one-shot check between steps, or keep
  `scripts/191_ops_selfcheck.sh --watch 300` in a side terminal. 300 s matches
  the shipped `OPS_STALL_S`; a wedge is visible within ~10 min worst case.
* **Between batches / at wrap time**: one one-shot check before dispatching new
  work (`ACTION`/`STALLED-CHAIN` tells you the previous chain did not land) and
  one after it finishes (the wrap heuristic).
* **In a wrapper**: branch on the exit code - `0` keep waiting; `2` print the
  `actions:` block to the operator (or automate only the *printed* commands);
  `1` selftest broken.
* The dataset collector has its **own** in-process guards that the ops check
  does not replace: `FRUIT_COLLECT_EPISODE_S` (600 s soft per-episode skip) and
  `FRUIT_COLLECT_STALL_S` (600 s hard progress window, `os._exit(3)` with a
  stack dump; the shard loop advances the seed). The ops check catches what
  those cannot: a wedge outside a collector, a lane parked on a permission, or
  work that simply never started.

## Recovery playbook per stall class

### (a) A lane parked on an unanswerable permission

*Detection*: `permissions: pending_asks>0` and/or a stale chain with a
`waiting_input` / parked prompt (the known incident: a lane requesting
`external_directory` for `/tmp/*` in a loop; `task_reply` cannot answer those
requests on this host).
*Recovery*: do not wait on it. Respawn the lane from the same prompt, with an
explicit **"no `/tmp`, no external directories; write everything under
`logs/`"** rule, and keep its partial artifacts (`logs/600_stall_fk.py`,
`logs/490_prepose.log` in the historical case) for the respawned lane to
reconcile.

### (b) A renderer wedge (a sim with no log growth)

*Detection*: `STALLED-SIM`, escalated to `ACTION` when the tail shows a wedge
marker (`Too many open files`, `Texture creation failed`, `[collect] STALL`,
a traceback), `state.tsv` proves zero growth across the window, or the GPU has
been idle with the log frozen `>= 2x OPS_STALL_S` (600 s at the defaults).
Historical instance: a blocking `RenderingManager.render()` under the
bimanual bridge (2026-10-10) with ~0 s of sim per 600 s of wall.
*Recovery* (the exact pid/pgid/log are printed by the tool):

```bash
kill -TERM -- -<pgid>          # the whole session; sleep 5
kill -KILL -- -<pgid> 2>/dev/null
# resume: re-run the SAME wrapper invocation that wrote <log>:
#   scripts/180_claim_slot.sh <log> ENV=... (or 154_claim_run.sh <log> ENV=...)
# The wrappers do NOT retry by themselves and do not remember anything; a
# re-run reclaims a slot via flock (and 180 also refuses a duplicate log
# namespace). A collector shard RESTARTS FROM ZERO into its own dir
# (`while saved < EPISODES`): the store is the union of shard dirs,
# renumbered/skipped-duplicates by scripts/41_merge_demos.py.
scripts/180_claim_slot.sh --status   # confirm the pool state afterwards
```

If the tool prints that the sim's pgid **equals the tool's own process
group**, the group-kill line is deliberately refused - kill from the shell
that launched the sim, or through the claim wrapper (a group kill would take
the tool and its launching shell down). Always kill the session before
resuming: never start a second sim by hand to "replace" a wedged one while its
session is still alive - `180_claim_slot.sh` refuses the duplicate log
namespace, and a zombie holding the GPU is the `vkAllocateMemory` failure mode.

### (c) A dead lane after a detached chain (the wrap never happened)

*Detection*: `STALLED-CHAIN` + a completion marker in the newest chain log tail
(+ `git dirty>0` -> `ACTION [wrap]`). The chain's measurements exist but the
commit/tag/report step did not run. While a claim wrapper / driver is alive the
tool downgrades the action to a hint (the lane may still be wrapping) - only a
quiet tree with no live wrapper is the manual-wrap case.
*Recovery*: inspect the lane's last log and the dirty paths; commit **only the
lane's own files** (`git add <paths>`, never `git add -A` - parallel lanes keep
uncommitted work), append the WORKLOG entry, tag the phase, then dispatch the
next work.

### (d) Long idle lanes

*Detection*: `STALLED-CHAIN` with a clean tree and no sims - nothing has been
produced for > `OPS_CHAIN_S` and no work is queued in the visible logs.
*Recovery*: ping the lane if it is alive; otherwise re-dispatch the next
backlog item. If the idle is intentional (owner asleep), the exit code is 0 and
the report is just a timestamp.

### (e) Resource waste

*Detection*: `ACTION [claim]` (a stale owner file whose pid is dead - the lock
was already released); a wedged sim holding the GPU (per (b)); the `lanes`
section naming a wrapper with no sim and no log growth. An idle GPU **alone**
is deliberately not an action: the tool only escalates it once the sim's log
has been frozen >= 2x `OPS_STALL_S`, and it says so in the hint meanwhile.
*Recovery*: `scripts/180_claim_slot.sh --status` to confirm the pool; remove
stale `*.owner` files (informational - they do not hold locks); kill wedged
sessions per (b); before dispatching new work, check that the machine is not
running a sim with no consumer (the `sims` + `lanes` sections show the cmd and
the log).

## Limits and caveats

* The per-sim log mapping uses fd 1; a sim launched without a log redirect (or
  logging to a tty/pipe) falls back to the newest `*.log` under `logs/`, which
  may belong to another lane. The `via=` field says which path was used.
* Log buffering can delay writes; `OPS_STALL_S=300` is deliberately longer than
  any healthy inter-line gap of the shipped entry scripts, but a lane with a
  very chatty-then-quiet pattern could still trip `STALLED-SIM` (exit 0, hint
  only). Escalation to `ACTION` additionally requires corroboration.
* The permission check is best-effort against the local OpenCode session store
  (`session_pending` / `permission` tables). A future storage change degrades
  the section to `n/a`; the `ACTION` lines remain valid for the operator who
  reads the lane list manually.
* `--watch` uses `sleep`, so a suspended machine resumes with one overdue
  iteration rather than catching up; records in `watch.log` are still one line
  per iteration with real timestamps.
