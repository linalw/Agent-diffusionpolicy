# P40 phase 4 — the close-out: the one adoption, the two opt-ins, and the record

Measured 2026-10-26 on the P39-final tree `1790b87` + the P40 tree
(`tasks.py` `ec991e5c`, `rl_env.py` `8ebb8d87`). Oracle gate 3 returned
**AMEND** with one adoption (`FRUIT_REGRASPS`), two "do not flip" items
(the selector, the substeps) and a list of record corrections.

| pin | before phase 4 | after phase 4 |
|---|---|---|
| HEAD | `1790b87` | `1790b87` (+ the commits this file records) |
| `src/fruit_sorting/tasks.py` | `a5cfb6d8` | **`ec991e5c`** (the path-scoped regrasp cap) |
| `src/fruit_sorting/rl_env.py` | `c88a2107` | **`8ebb8d87`** (`TASKS_MD5` follow only) |
| `src/fruit_sorting/scene.py` | `988985ef` | `988985ef` (untouched) |
| `configs/motion_reference.json` | `25ade92b` | **`adef05c966133de5cc07a20772b9f7f1`** |
| `configs/motion_reference_twoline.json` | `d0326030` | **`d87c3cdf37f797342df3bbaebc0836e9`** |

Archives of the two replaced references (byte copies, md5s above):
`logs/p40/motion_reference_single_pre_p40.json`,
`logs/p40/motion_reference_twoline_pre_p40.json`.
`scripts/189_w7a_chain.sh` was **not** run (it rewrites the two-line reference).

---

## A. The one adoption — `FRUIT_REGRASPS` is now **path-scoped**

```python
regrasp_cap = int(
    os.environ.get(
        "FRUIT_REGRASPS", "2" if self._dynamic_capture_active else "3"
    )
)
for _regrasp in range(regrasp_cap):
    ...
    _regrasp == regrasp_cap - 1  # the FRUIT_REGRASP_REOPEN slot
```

`src/fruit_sorting/tasks.py` `_grasp_carry_place_impl` (the single loop; both
sites read the one resolved `regrasp_cap`, so the default-off reopen recovery
cannot disagree with the loop bound). An explicit `FRUIT_REGRASPS` wins on both
paths; the indexed / policy-handover path resolves to `3`.

**Why the scope is not cosmetic.** `REGRASP_YIELD.md` §3: over 109 attempts the
**17/17** attempts that burned three probes never closed on the fruit at all
(`grasped=False`, `lift <= 0.004 m`), and the only conversion in the corpus came
on the **second** probe (`k=1`: 2/3 grasped, 1/3 placed) — which `=2` keeps. The
per-failed-probe price is 1.24 s (two-line) / 1.50 s (single arm). But every one
of those rows sits inside `if self._dynamic_capture_active:` **and**
`if verbose:` (`tasks.py:10918`), and the direct/policy handover is
`scripted=False` (`dynamic_capture` False) with `DirectSortEnv(verbose=False)`,
so **nothing in that evidence covers the indexed/policy retry** — it is a
different mechanism (no moving fruit, no re-seat-in-place), and it keeps 3.

### A.1 The two runs (knob unset everywhere — the flip is what is being read)

**Single-arm acceptance** `logs/p40/p4/accept_flip.log` (one claim,
`SKIP_SELFCHECK=1 ACCEPT_LOG=... scripts/accept.sh`, 01:49:03 -> 01:53:01):

| | control `logs/p39/p3/accept_C.log` | flip (`FRUIT_REGRASPS` unset) |
|---|---|---|
| placed | **6/10** | **5/9** (attempt 7 `no eligible fruit`) |
| `[stats]` sim | 150.2 s | **133.0 s** |
| s/attempt | 15.0 | **14.8** |
| placed/min | 2.40 | 2.26 |
| **re-seat rows printed** | **3** | **2** |
| motion gate | 6/10, rate-only FAIL, fp `matches` | 5/9, rate-only FAIL, fp `matches` (new ref) |

**Two-line battery** `logs/p40/p4/twoline_flip.log` (one claim,
`FRUIT_BIARM=1 FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10 SEED=5 FRUIT_CYCLE_REPORT=1`,
01:53:48 -> 01:58:09):

| | control `logs/p39/p3/twoline_C.log` | flip |
|---|---|---|
| placed | **6/10** (left 3/5, right 3/5) | **7/10** (left 4/5, right 3/5) |
| `[stats]` sim | 90.2 s | **88.2 s** |
| s/attempt | 9.0 | **8.8** |
| placed/min (the `[biarm]` row) | 3.99 | 4.76 |
| `diverted` | 0 | **1** |
| **re-seat rows printed** | **13** | **5** |
| k-map closure (`k_map.py`) | `sum k = 13` = rows | `sum k = 5` = rows |
| `190` gate | — | **PASS** (7/10 >= 0.60, new ref `d87c3cdf`) |

**These counts are NOT a rate claim** (P1/P2 lesson): both pairs are in *moved*
attractors (`diverted` 0 -> 1; the fruit sequence diverges at slot 6 in the
two-line, and the single-arm run loses an attempt to `no eligible fruit` from
attempt 4), so with a fixed attempt count and a flat cadence every throughput
headline is a monotone transform of the count. `4.76 placed/min` is
`60 x 7 / 88.2`; the `9.27 s` pooled interval is `60 / 6.47`. AGENTS carries the
mechanism and the re-seat rows, **not** these rate columns.

**The flip reproduces the measured arm exactly, byte for byte:**

```
filter_stream.py --diff logs/p40/p3/regrasp2_accept.log  logs/p40/p4/accept_flip.log   -> 339/339 IDENTICAL
filter_stream.py --diff logs/p40/p3/regrasp2_twoline.log logs/p40/p4/twoline_flip.log  -> 430/430 IDENTICAL
```

i.e. the shipped path with the knob **unset** is the phase-3 `FRUIT_REGRASPS=2`
arm (`logs/p40/p3/`), not merely "equivalent to" it. The same-attempt mechanism
(P3_RESULTS §R-R (a)) is therefore unchanged: the two capped `k=3` attempts are
the control's own (`right peach idx 12`, `left kiwi idx 13`), they end
identically (`grasped=False`, `lift +0.003 / +0.000`, `fruit did not follow the
gripper`) and only the time moves — `5.45 -> 3.93 s` and `5.42 -> 4.00 s`, i.e.
the **k=3 tax is 1.42-1.52 s**.

### A.2 The two re-records, and the two gate verdicts

Both references were re-recorded **from these same-batch runs**, because the flip
moves both scenarios (`k_map.txt`, `w6_report.txt` in `logs/p40/p4/`):

```
python3 scripts/105_motion_regression.py logs/p40/p4/accept_flip.log \
    --write-fingerprint configs/motion_reference.json          # adef05c966133de5cc07a20772b9f7f1
python3 scripts/105_motion_regression.py logs/p40/p4/twoline_flip.log \
    --write-fingerprint configs/motion_reference_twoline.json  # d87c3cdf37f797342df3bbaebc0836e9
```

Both writes passed every **motion budget** (9 descents in budget on the single
arm, worst `|v|max` 0.109 vs 0.160-0.161; all 10 two-line descents in budget,
worst 0.110 vs 0.160-0.161, lurch 0.018 vs 0.291) and were refused by nothing;
the only failing item in each was the **rate floor** (5/9 = 56 %, 7/10 = 70 % —
the known post-P32 branch, below the single-arm 0.75), which by design does not
block a write.

The proofs, run after the writes:

| check | command | verdict |
|---|---|---|
| the single-arm gate | `python3 scripts/105_motion_regression.py logs/p40/p4/accept_flip.log --fingerprint configs/motion_reference.json` | **`fingerprint: matches configs/motion_reference.json`**, rate-only FAIL (5/9 = 56 % < 75 %) — `logs/p40/p4/10_gate_accept_flip.txt` |
| the two-line gate | `bash scripts/190_twoline_gate.sh logs/p40/p4/twoline_flip.log` | **PASS** — 7/10 >= the 0.60 two-line floor, fingerprint matches `d87c3cdf` — `logs/p40/p4/11_gate_twoline_flip.txt` |

Before the re-record, the same two commands read `fingerprint: DIFFERS` on both
(the expected moved branch, recorded and not adjudicated):
`logs/p40/p4/00_gate_pre_record.txt` (re-derived from the two archives, so it is
byte-for-byte the pre-record state).

**Note on the shape of the new single-arm reference**: it carries **9** descent
legs, not 10, because the flipped acceptance loses an attempt to
`no eligible fruit` from attempt 4. That is the shipped branch as it now runs;
a future run that recovers a tenth attempt will read
`leg 10: this=[...] reference=None` and be reported as a **moved attractor**
(which is what a length difference means to `105`), not as a broken descent.

**The acceptance's own verdict is unchanged in kind.** The shipped acceptance
already exits 1 on the **rate only** on this tree (the P32 6/10 = 60 % branch,
`AGENTS` §1), so 5/9 does not introduce a new failing item; the fingerprint item
now matches, which is the change.

---

## B. `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` **stays opt-in** (default off)

No flip and no re-record. The reason, as the Oracle recorded it:

* **the scope is not single-arm-safe.** `DirectSortEnv`'s *episode* selection
  calls `select_target(..., reach_anywhere=False)` with no lane and no
  `prefer_lane` (`rl_env.py:1656`), so the knob's
  `lane is None and prefer_lane is None` return **is** the direct loop's rule. A
  default flip would silently change every direct episode — and therefore
  invalidate every prior direct baseline (P33/P35/P36/P37/P38/W7-C/W8-A/R9 A-arm
  numbers) — with no A/B of its own. The two-line selector and the env's own
  reseed path pass a lane (`rl_env.py:3233`, `lane=int(self._bin_index)`) and are
  excluded structurally, which is why the measured battery says nothing about
  either.
* **the measured gain is small and on one branch.** 0.44 s of wait and
  0.37 s of span → **0.4 s of 15.0 s (2.7 %)**, plus `+1` discharge (4 -> 5) and
  `+1` placement, on a moved branch (`fingerprint: DIFFERS`) at n = 10.

It stays a measured, default-off lever with its own A/B named as the entry cost.

---

## C. `FRUIT_SUBSTEPS=4` ships as a **FINDING**, not a setting

Recorded with the Oracle's corrections (all applied to `EFFORT_READ.md`):

1. **The class is not deleted.** At 480 Hz the left still carries-not-places
   **2 of 7** left attempts — attempt 3's **orange** (`lift +0.218`,
   `N=9.58`) and attempt 9's **tomato** (`lift +0.136`, `N=10.03`) — against the
   shipped run's 4/4 left (`logs/p40/p2/effort_sub4.log` vs `effort_sub1.log`).
   The 8/10 is **a different attractor** (480 Hz is a different physics setting,
   not an instrument state), not a class gain.
2. **Substeps refine the physics; the controller stays at 120 Hz**
   (`common.py:13-20`). So a store's *consumability* is not the issue — the
   recorded actions are still 120 Hz commands against a finer solver.
3. **The unconditional precondition for any store is the `write_manifest`
   `substeps` field** — without it a shard collected at 4 substeps is
   indistinguishable from a shipped one and the provenance chain is broken.
   A **real-jaw clamp-force anchor** gates only a *fidelity* claim (it is what
   would let a 9.95 N sim read mean something about hardware), not the store.
4. **The force/wall pair is one pair, the law is unidentified**: 2.25x normal
   force (4.42 -> 9.95 N, both instruments agreeing to 0.5 %) for **3.08x wall**
   (266 -> 819 s) and **+0.66 s/attempt** of span (`[stats]` 150.2 -> 156.8 over
   10). A 4x rate giving 2.25x force is neither `dt^-1` nor `dt^-2`; this run
   does not separate stiffness from damping from the solver's
   implicit-spring regularisation, and `F/err` is an **operating-point ratio**
   (377 -> 1045 N/m), not a stiffness.
5. **Nothing is adopted**: `FRUIT_SUBSTEPS` keeps its shipped value; the knob
   needs its own pre-registration, its own motion reference and a 480 Hz
   side-effect check (p11b: escape speed -6 %, displacement -10 %).

---

## D. The record corrections (all applied)

| # | where | correction |
|---|---|---|
| 1 | `P3_RESULTS.md` §R-R (a) | the two-line **rate columns are captioned "NOT a rate claim"** — `4.76 placed/min` and the `9.27 s` interval are cross-attractor monotone transforms of the count (they are `60 x 7 / 88.2` and `60 / 6.47`). The same caveat is applied to the single-arm row. **They stay out of `AGENTS.md`.** |
| 2 | `P3_RESULTS.md` §R-R (a) | the **"`k=1` converted again"** sentence is **replaced**: the treatment's `k=1` row (slot 2, right pear `idx 9`, grip 3.23 s, span 15.3 -> 16.8 s) is a **new two-probe attempt on a fruit the control placed first-try** (control slot 2: `k=0`, grip 1.77 s, span 15.3 s), **not** the corpus rescue (`twoline_C` slot 4). The rescue path is preserved by construction, but this battery does not exhibit it. |
| 3 | `P3_RESULTS.md` §R-S | the **commit-distance sentence is replaced**: the parse excludes the ~0.76 s hover (0.09 m) that the floor's 1.5 s setup includes, so the naive 0.463 -> 0.411 m is a **lower bound**; the true commit is **~0.553 -> ~0.501 m** against the 0.399 m floor, i.e. **~0.15 / ~0.10 m above it**. The rule therefore **does not spend the floor's margin** (risk downgraded); it removes 0.05 m of the 0.21 m median over-commit. |
| 4 | `EFFORT_READ.md` §0/§6/§7 | **"the drive sits at 22 % of the cap"** -> **the *command* is at the 10 N cap on 40/40 contact rows; the *delivered reaction* is 22 % of it**; and **"implied `k_eff`"/"effective stiffness"** -> an **operating-point `F/err` ratio** (377 -> 1045 N/m), a **timestep signature**, the law **unidentified**. |
| 5 | `EFFORT_READ.md` §0/§7 | the substeps span is cited as **+0.66 s/attempt** (`[stats]` 150.2 -> 156.8 over 10), never "+0.90 s" and never "+4 %". |
| 6 | the evidence commit | `logs/p40/__pycache__` is **excluded** from the force-add (a `.pyc` cache directory, not evidence). |

---

## E. What this phase refuses

* **`scripts/189_w7a_chain.sh`** — not run; it rewrites the two-line reference.
* **The two-line rate columns as a finding** — see D.1.
* **A `FRUIT_SELECT_NEAREST_ABOVE_FLOOR` flip** — see B.
* **`FRUIT_SUBSTEPS` as a setting** — see C.
* **Any direct/policy-path statement about the regrasp cap** — the bound reaches
  `_grasp_carry_place_impl` but prints nothing there (`verbose=False`,
  `dynamic_capture=False`), so the path keeps 3 and needs its own A/B if the
  question ever matters. `src/fruit_sorting/grasp.py:278`'s
  `GraspPrimitive` loop (reached only under `FRUIT_NO_ATTACH=1`) is a *separate*
  loop and was **not** touched.

## F. No-harm

* `bash scripts/selfcheck.sh` -> `logs/p40/selfcheck.log`: **PASS, 0 failures**
  (1 skipped, the simulator leg).
* `python3 scripts/96_motion_check.py`: PASS (see `logs/p40/p4/20_motion_check.txt`).
* The flip's two runs are byte-identical to the phase-3 measured arms, so the
  only behaviour change on the tree is the dynamic line's third probe, which is
  the intended one; the indexed/policy path is untouched by construction
  (`3`) and by the branch pins.

## G. Reproduce

```bash
# the two runs (knob unset; the flip is the default under test)
RUN_LIMIT=2400 scripts/154_claim_run.sh logs/p40/p4/claim_accept_flip.log \
    SKIP_SELFCHECK=1 ACCEPT_LOG=logs/p40/p4/accept_flip.log scripts/accept.sh
HEADLESS=1 FRUIT_MOTION_REPORT=1 FRUIT_CYCLE_REPORT=1 FRUIT_BIARM=1 \
    FRUIT_BIARM_TWOLINE=1 ATTEMPTS=10 SEED=5 \
    scripts/run.sh scripts/20_pick_place.py > logs/p40/p4/twoline_flip.log 2>&1

# the two re-records + the two gates
python3 scripts/105_motion_regression.py logs/p40/p4/accept_flip.log \
    --write-fingerprint configs/motion_reference.json
python3 scripts/105_motion_regression.py logs/p40/p4/twoline_flip.log \
    --write-fingerprint configs/motion_reference_twoline.json
python3 scripts/105_motion_regression.py logs/p40/p4/accept_flip.log \
    --fingerprint configs/motion_reference.json          # fingerprint: matches
bash scripts/190_twoline_gate.sh logs/p40/p4/twoline_flip.log   # PASS

# the mechanism
python3 logs/p40/p3/k_map.py logs/p39/p3/twoline_C.log logs/p40/p4/twoline_flip.log
python3 scripts/186_w6_report.py logs/p39/p3/twoline_C.log logs/p40/p4/twoline_flip.log
python3 logs/p39/p3/filter_stream.py --diff logs/p40/p3/regrasp2_accept.log \
    logs/p40/p4/accept_flip.log
```
