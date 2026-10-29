# P64 gate screen - is `q_cmd` admissible?

**VERDICT (first line): `q_cmd` = `[+0.01675, -0.68786, +0.68786, +0.23113]` is
NOT admissible. It solves 0/3 at the probe's 6 mm tolerance (residual
42.6-72.9 mm), its smallest joint-limit margin is `+0.000/-0.000 rad at j6/j7`
(the control's worst is `+0.204 rad @ j2`), and its commanded jaw axis has
`jaw_z = +0.2949`, i.e. the two pads of the 98 mm jaw sit **28.9 mm** apart in
height (14.5 mm each side of the jaw centre) - exactly the class the
`configs/waypoints_oriented.json` note rejects ("one finger above the other").
So P64's "**the response is inverted**" is **not a mechanism**: the command was
never on the admissible set P62's own probe defines. The Oracle's gate finding is
**confirmed**. The two reachable directions behave as the Oracle predicted:
`QDRIFT` (belt projection **+0.341**) **solves 3/3** (res 5.8-6.0 mm,
qerr <= 0.93 deg, margin `+0.057..+0.282 rad @ j6`), and `QFILE`
(`waypoints_oriented`'s left, projection **+0.513**) is **byte-for-byte the
control `C0`** - the "+0.299 rad j2 margin" direction *is* the shipped control,
so it reproduces `C0` row for row (an independent determinism check).

Nothing adopted, no default changed, no `src/`/`configs/` edit, no commit.

## 1. Method (and the knob's real name)

The probe knob is **`FRUIT_P62_CANDIDATES`** (comma list; the file's default is
`C0,Y31,Y46,Y62`), with `FRUIT_P62_X` (`0.274,0.34,0.398` - the delivered p50 /
station / max the probe already sweeps), `FRUIT_P62_TOL` (0.006 m) and
`FRUIT_P62_RESTARTS` (1). The docstring also advertised `FRUIT_P62_JSON` for the
raw-row path but the code never read it, so it hard-wrote
`logs/p62/ik_probe_rows.json`; the screen wires that env var (the only behaviour
change in the evidence script) and writes
`logs/p64/ik_screen_rows.json`, leaving the P62 artifact **untouched**
(md5 `c41688c7` before and after).

Edits to `logs/p62/ik_probe.py`, both additive and default-off:

* the candidate list may name three **derived** attitudes that are not in
  `candidates.json` - `QPREC` (P64's literal file value), `QDRIFT`
  (`q_drift (x) q_T0`) and `QFILE` (`waypoints_oriented.json`'s left
  `grasp_quaternion`) - so the P62 rows stay byte-reproducible;
* each row also carries the **jaw-opening axis' z**, the **jaw separation**, the
  derived **pad height difference across the jaw**, the **commanded** and the
  **achieved** belt projection.

The drifts are P64's own: axis `(-0.7564, -0.6541, 0)`, angle `26.798 deg`
(`log_drift` on 7 left `grasp_lift` legs), `q_T0 = [0, -0.707107, +0.707107, 0]`
(the `T0` row `candidates.py` derives). Checked at run time:

```
QPREC check: q_drift^-1(x)q_T0 = [+0.016763,-0.687859,+0.687859,+0.231124]
   vs file [+0.016750,-0.687860,+0.687860,+0.231130]   |dot| = 1.000000
```

(`1.000000` = the same rotation; the file value is the exact pre-compensation,
so the screen screens the arm P64 actually ran.)

| candidate | quat (w, x, y, z) | proj_cmd | jaw_z_cmd |
| --- | --- | --- | --- |
| `C0` (control) | `+0.184162, +0.709672, -0.193123, +0.652038` | +0.5132 | +0.0095 |
| `QPREC` | `+0.016750, -0.687860, +0.687860, +0.231130` | **-0.3410** | +0.2949 |
| `QDRIFT` | `-0.016763, -0.687859, +0.687859, -0.231124` | **+0.3410** | -0.2949 |
| `QFILE` | `+0.184162, +0.709672, -0.193123, +0.652038` (identical to `C0`) | +0.5132 | +0.0095 |

Frame semantics were re-settled on the shipped seed before the ladder
(`|approach x cols| = 0.000 0.000 1.000`, `|jaw x cols| = 0.000 1.000 0.000`,
`jaw_sep = 98.0 mm`): **`col2` is the approach/TCP axis, `col1` is the
jaw-opening axis (negated)**, so `rot[:,1][2]` is the jaw axis' z. Both finger
links are prismatic, so their world orientations are identical and the pad read
(which reuses the left finger's quat for the right link) is exact.

## 2. Raw rows

`res` = IK position residual, `qerr` = achieved vs **commanded** attitude,
`margin` = smallest joint-limit margin and its joint, `pad`/`finger` = static
belt-top clearance of the pads / of the lower finger origin, `pad dz` =
`|jaw_z_ach| * jaw_sep` (the pad height difference across the jaw),
`proj` = belt projection of the approach axis (commanded / achieved).

| cand | x | res mm | qerr deg | margin rad | pad mm | finger mm | tcp mm | jaw_z cmd | jaw_z ach | jaw sep mm | pad dz mm | proj cmd | proj ach | pad vs C0 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C0 | 0.274 | 5.9 | 1.48 | +0.377 @j2 | +38.9 | +84.5 | +78.5 | +0.0095 | +0.0301 | 98.0 | 3.0 | +0.5132 | +0.5114 | - |
| C0 | 0.340 | 5.7 | 0.98 | +0.299 @j2 | +49.0 | +94.5 | +88.1 | +0.0095 | +0.0203 | 98.0 | 2.0 | +0.5132 | +0.5123 | - |
| C0 | 0.398 | 8.3 | 1.98 | +0.204 @j2 | +30.2 | +76.0 | +67.1 | +0.0095 | +0.0023 | 98.0 | 0.2 | +0.5132 | +0.5135 | - |
| **QPREC** | 0.274 | **67.9** | **19.95** | **+0.000 @j7** | +61.3 | +85.3 | +27.3 | +0.2949 | +0.3235 | 98.0 | **31.7** | -0.3410 | -0.0001 | +22.3 |
| **QPREC** | 0.340 | **42.6** | **33.09** | **-0.000 @j6** | +53.1 | +77.1 | +18.0 | +0.2949 | +0.3119 | 96.0 | **30.0** | -0.3410 | +0.1043 | +4.1 |
| **QPREC** | 0.398 | **72.9** | **31.91** | **+0.000 @j6** | +55.0 | +79.6 | +13.5 | +0.2949 | +0.1839 | 98.0 | **18.0** | -0.3410 | -0.0791 | +24.8 |
| QDRIFT | 0.274 | 5.9 | 0.78 | +0.282 @j6 | +43.3 | +78.2 | +23.0 | -0.2949 | -0.2895 | 98.0 | 28.4 | +0.3410 | +0.3529 | +4.3 |
| QDRIFT | 0.340 | 5.8 | 0.93 | +0.144 @j6 | +42.9 | +77.8 | +22.4 | -0.2949 | -0.2880 | 98.0 | 28.2 | +0.3410 | +0.3543 | -6.1 |
| QDRIFT | 0.398 | 6.0 | 0.91 | +0.057 @j6 | +44.1 | +79.1 | +24.1 | -0.2949 | -0.2913 | 98.0 | 28.6 | +0.3410 | +0.3544 | +13.9 |
| QFILE | 0.274 | 5.9 | 1.48 | +0.377 @j2 | +38.9 | +84.5 | +78.5 | +0.0095 | +0.0301 | 98.0 | 3.0 | +0.5132 | +0.5114 | -0.0 |
| QFILE | 0.340 | 5.7 | 0.98 | +0.299 @j2 | +49.0 | +94.5 | +88.1 | +0.0095 | +0.0203 | 98.0 | 2.0 | +0.5132 | +0.5123 | +0.0 |
| QFILE | 0.398 | 8.3 | 1.98 | +0.204 @j2 | +30.2 | +76.0 | +67.1 | +0.0095 | +0.0023 | 98.0 | 0.2 | +0.5132 | +0.5135 | -0.0 |

Per-candidate verdict rows printed by the probe:

```
C0     solved 2/3 (<=tol), max_res=8.3mm  worst_qerr=1.98deg  worst_margin=+0.204rad  pad_delta=-
QPREC  solved 0/3 (<=tol), max_res=72.9mm worst_qerr=33.09deg worst_margin=-0.000rad pad_delta=+4.1mm
QDRIFT solved 3/3 (<=tol), max_res=6.0mm  worst_qerr=0.93deg  worst_margin=+0.057rad  pad_delta=-6.1mm
QFILE  solved 2/3 (<=tol), max_res=8.3mm  worst_qerr=1.98deg  worst_margin=+0.204rad  pad_delta=-0.0mm
```

## 3. Findings

1. **`q_cmd` fails every clause of the admissibility screen.** Solve: 0/3 vs the
   control's 2/3 (both fail at x = 0.398, where the control reads 8.3 mm - the
   known reach cliff). Residual 42.6-72.9 mm is **7-12x the 6 mm tolerance** and
   lands in P62's measured *infeasible* band (Y46/Y62: 41.7-118.0 mm), not in an
   attitude-response regime. Margin is `+0.000` / `-0.000 rad` at **j6/j7** -
   i.e. the solver ran onto a joint limit and stayed there, while the control
   binds on **j2 at all three x** with `+0.204..+0.377 rad` (so the ratio is not
   even quotable: QPREC's margin is zero to the printed digit). The residual is
   lateral (jaw `dz` to target is only +11.1/+2.1/-1.4 mm while the 3-D residual
   is 43-73 mm), which is the signature P62 already recorded: the 6-DoF solve
   runs out of *position* when handed an orientation it cannot hold.
2. **The jaw twist is quantitative, and it is why the note rejects the class.**
   `jaw_z_cmd = +0.2949` gives a `0.2949 x 98 mm = 28.9 mm` pad-height
   difference across the jaw (14.5 mm above/below the jaw centre). The control is
   `+0.0095` (**0.9 mm**). The probe's achieved `jaw_z` at `QPREC`
   (+0.18..+0.32) confirms the arm ends up with one pad visibly higher, so even
   the *achieved* pose is a one-pad-first contact - a second, independent reason
   this direction cannot catch a fruit resting on the belt.
3. **The Oracle's `QDRIFT` prediction is confirmed and then some.** It is the
   only candidate in either run that solves **3/3**, with qerr <= 0.93 deg and a
   positive margin everywhere (worst `+0.057 rad @ j6` at the x = 0.398 cliff).
   Compared at the same x its margin is 0.28-0.75x the control's, but it is
   **better conditioned than `T0`** - the attitude P62 phase 2 armed - which
   reads `+0.007`/`+0.008 rad @ j3` and solves only 2/3 (`logs/p62/
   ik_probe_rows.json`). Its pads are not systematically worse (-6.1..+13.9 mm
   vs control) - but it inherits `|jaw_z| = 0.2949`, i.e. the **same 28.2-28.6 mm
   pad twist as `QPREC`**: it is *reachable*, not *better*, and it is the
   attitude the arm already reaches.
4. **`QFILE` is `C0`, bit for bit.** Every field matches to the printed digit
   (pad delta `-0.0/+0.0/-0.0`), so the Oracle's "+0.299 rad j2 margin"
   reachable direction *is* the shipped control at the station, and the probe is
   deterministic across candidate order (it ran first and last in the same
   claim). That also means `QFILE` is not an independent candidate at all - it is
   the control's own file value, which the P62 table had already labelled `C0`.
5. **New, cheap, and it sharpens P64's conclusion: the drift is not a
   station-level offset.** At the station the static solve tracks its command to
   **<= 1 deg** in *both* admissible directions - `T0` (proj 0) 0.77/0.78 deg
   (P62 rows) and `QDRIFT` (proj +0.35) 0.78/0.93/0.91 deg here - while P63
   measured a median **24.6 deg** (22.4-29.4, n = 11) on the left's *failing
   carry* legs and P64's own 7-leg fit is 26.798 deg. So there is nothing to
   pre-compensate at the pick solve: the 25 deg is created during the lift, which
   is exactly why P64's write at the `grasp_lift` start moved the achieved
   attitude by 17-32 deg (the IK trades orientation for position while the arm is
   loaded and moving). **The `hold_quaternion` pre-compensation lane has no
   target at the station, in either sign** - a stronger and cleaner negative than
   "the response is inverted".

## 4. What this does not show

* `FRUIT_P62_RESTARTS = 1`, so every cell is one solve from the shipped seed (the
  P62 phase-1 convention; `..._RESTARTS=2` is the catch's own random-restart
  fallback and was **not** run here).
* This is the **static pre-grasp solve**. It does not reproduce P64's live
  achieved `+0.51..+0.83` (that number comes from the carry leg); the probe
  refutes the *command's admissibility*, it does not re-measure the carry. Its
  own achieved projections under `QPREC` are `-0.0001 / +0.1043 / -0.0791`, i.e.
  the arm falls back toward ~0 when it cannot hold the command - a different
  regime from the loaded lift, and the two must not be quoted interchangeably.
* For `QPREC` the pad/finger columns are measured at a pose **43-73 mm away from
  the target**, so they say nothing about belt clearance at the pick point; they
  are printed for completeness, and the clearance reading that matters is the
  control's and `QDRIFT`'s (both >= +30 mm).
* The `qerr` sign convention is `quaternion_error`'s shortest arc (it flips `w`),
  so no value here is inflated by a `+/-q` representation choice.

## 5. Reproduction

```bash
RUN_LIMIT=1800 FRUIT_P62_CANDIDATES=C0,QPREC,QDRIFT,QFILE \
  FRUIT_P62_JSON=logs/p64/ik_screen_rows.json \
  scripts/154_claim_run.sh logs/p64/ik_screen.log scripts/run.sh logs/p62/ik_probe.py
```

One claim, 44 s wall (19:20:12 -> 19:20:56). Artifacts: `logs/p64/ik_screen.log`
(console), `logs/p64/ik_screen_rows.json` (raw rows, candidate quats and the
`|dot| = 1.000000` check), this file. Only `logs/p62/ik_probe.py` changed in the
tree (plus `logs/p64/*`); `logs/p36/offline_obs_diff.txt` was already dirty on
entry and is not mine.
