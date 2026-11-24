# P238 results: the 1.44 s is the catch-up, not the attitude - P237's attribution falsified

**2026-11-24, `logs/p238/`.** One default-off diagnostic row (`[seat] init`). It
exists to test P237's attribution, and it **kills it**.

---

## 1. The measurement

`[seat] init 1-cos=... tol=... deg=...`, printed once per attempt at the attitude
servo's entry, gated on `FRUIT_CYCLE_REPORT=1`:

| attempt | init `1-cos` | init deg | `seat` |
|---|---|---|---|
| s901 e0 | 0.0001 | **0.6** | 1.67 s |
| s901 e1 | 0.0000 | 0.1 | 1.67 s |
| s901 e2 | 0.0000 | 0.1 | 1.67 s |
| s902 e0 | 0.0000 | **0.0** | **0.22 s** |
| s902 e1 | 0.0000 | 0.1 | 1.67 s |
| s902 e2 | 0.0000 | 0.1 | 1.67 s |

`FRUIT_AXIS_TOL = 0.01` is **8.1 deg**. **Every attempt enters the servo already
inside tolerance**, so the servo exits on its first check and costs ~1 tick. The
attitude is **not** what the 1.67 s is spent on - the approach leaves the wrist
square, as P64/P65 said it should.

## 2. What it is instead

`1.67 s = 200 ticks`, and the only 200-tick budget in that segment
(`descent` mark -> `seat` mark) is

```
catch_ticks = int(os.environ.get("FRUIT_DYNAMIC_CATCH_TICKS", "200"))   # tasks.py:15395
for _ in range(catch_ticks): ...                                        # tasks.py:15427
```

the primitive's **pursuit** of the fruit after the descent. `seat` is bimodal
(26 ticks vs 200) because **the catch-up either converges quickly - the fruit is
where the aim expected it - or runs out its budget**.

**So P237's shape survives and its object changes**: the primitive pays **1.44 s**
for a gap the approach left, but the gap is the **aim residual** (where the pads
are relative to the fruit at the handover), not the wrist's attitude. The lever is
**"arrive closer"**, and the record already has its instruments: the
`dynamic catch-up: residual` row (P47), the 6 mm `FRUIT_DYNAMIC_CATCH_TOL`, and
P232/P233's finding that the trigger's `t_arrive` was up to 2x wrong under a wave -
which is one way the aim can be off.

## 3. Why the correction matters more than the original finding

P237 read `1.67 s = 200 ticks` and picked, from the code, the *only 180-iteration
loop it could see* - the attitude servo - and stated it as the cause. **The
measurement says the code read picked the wrong loop**, and the wrong loop has a
different lever attached (a vertical arrival vs a closer arrival). The record's
rule is that a mechanism claim needs the instrument that discriminates it, and
P237's did not have one. **This phase is that instrument.**

Two consequences kept:
1. `seat`'s 1.44 s is real and is **the largest bimodal term** in the cycle
   (`place 3.48`, `release 2.2`, `grip 1.58` are all constants).
2. The lever it names is **the aim residual at the handover**, which is a
   *cross-layer* object again: the policy's approach sets it, the primitive's
   pursuit pays for it, and neither is charged.

## 4. Pins

`tasks.py` **`e72b2c7c`** (the `[seat] init` row, gated on the cycle report),
`rl_env.py` `TASKS_MD5` follow; references **`61fb5202` / `61fb5202` / `18b101bf`**
untouched; checkpoint `p227_panda156`. Evidence `logs/p238/init/`. `logs/p237/`
carries the correction in its own §6 and AGENTS' P237 paragraph is amended in
place.
