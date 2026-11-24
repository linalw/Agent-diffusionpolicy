# P247 results: the axis-aware exit holds at 15/16 in a fresh cell - 26/28 pooled

**2026-11-25, `logs/p247/`.** The confirmation P243/P246 owed:
`FRUIT_CATCH_TOL_AXIS=1` at 0.08, seeds 901/902 x **8** episodes.

---

## 1. The cells

| seed | placed | catch `ticks` |
|---|---|---|
| 901 | **7/8** | **200**, 21, 33, 21, 21, 21, 21, 21 |
| 902 | **8/8** | 24, 21, 39, 24, 41, 21, 21, 21 |

* residuals: **8.6-10.5 mm** on every attempt except the one 200-tick outlier
  (**36.9 mm**).
* **Pooled with P243** (11/12): **26/28 = 92.9 % placed**, and the catch-up costs
  **21-42 ticks on 27 of 28**.

## 2. What it confirms

* **The 200-tick tax is gone on 27 of 28** - not a branch, not a seed.
* **The placed count is at parity**: 26/28 against the shipped cell's 11/12
  (and the shipped cells' 0/30 on excursions is the *instrument* difference
  P246 documented, not a quality difference).
* **The cycle saving is the one measured**: `seat` 1.67 -> 0.17-0.34 s,
  **-1.44 s of ~13.3 (-11 %)**.

## 3. The one outlier is the known class, again at the first attempt

The single 200-tick row is **seed 901's episode 0** (36.9 mm) - the same position as
every excursion in P241-P246, and the one attempt of the 16 that did not place.
**So the open class behaves exactly as P246 bounded it**: at most one per run, at the
first episode, 0-1 placement. **No new information and no rate** - it stays open.

## 4. Status of the lever, stated for a decision

| | shipped | axis exit |
|---|---|---|
| placed | 11/12 (P230) | **26/28** |
| cycle | ~13.3 s | **~11.9 s** |
| catch-up | 200 ticks always | **21-42 on 27/28** |
| command | - | **untouched** |
| open class | 0/30 observed | 1 per run at the first attempt (the same class P246 bounds) |

**A promotion to default still owes P93's powered cell** (~40/arm), the two-line
gate, both references and a store re-baseline. What this phase adds is that **the
first 28 attempts show parity and the time saving**, which is the evidence a
promotion decision needs to *start* from.

## 5. Pins

No `src/` or `configs/` change; `tasks.py` **`9ce34845`**, `rl_env.py` unchanged by
this phase; references **`61fb5202` / `61fb5202` / `18b101bf`** untouched;
checkpoint `p227_panda156`. Evidence `logs/p247/conf/`.
