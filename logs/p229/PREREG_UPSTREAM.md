# P229 addendum pre-registration: does the envelope equation predict?

**Pinned 2026-11-24, before the upstream cells ran.**

P229's main result is an equation, not a rate:

```
v_max(ext) = (0.68 + ext - 0.06) / (1.267 + 1.5 + 0.25)
           = (0.62 + ext) / 3.017
```

with `ext = FRUIT_BELT_UPSTREAM` (P225t, default 0, lengthens the belt upstream
only, `spawn_y = 0.68 + ext`, station and despawn unchanged). Fitted to the
shipped scene it reads `v_max(0) = 0.2055 m/s`, which matched the bisect
(0.20 engages, 0.22 does not).

**A two-point fit is not a prediction.** This addendum tests the **slope**: if
the equation is right, adding belt should move the ceiling by `ext/3.017`.

| cell | `ext` | `v` | prediction |
|---|---|---|---|
| A | 0.10 | 0.22 | **engages** (ceiling 0.2387) |
| B | 0.10 | 0.24 | **does not engage** |
| C | 0.15 | 0.24 | **engages** (ceiling 0.2552) |
| D | 0.15 | 0.30 | **does not engage** |

The four cells fail in two different directions if the equation is wrong: **B
engaging** means it is pessimistic (the slope is under-estimated, or the poll
term is not the binding one); **C not engaging** means it is optimistic (the
`1.5 s` select term or the `t_desc` is too small, or a longer belt costs
something the equation does not carry).

`seed 901`, `3 episodes`, `FRUIT_EVAL_LATENCY=auto`, the `284` recipe; the claim
is **engagement** (a `0/0` cell is not a rate) plus the placed count as a
footnote. The cells are scene changes, so they are **measured, not shipped**, and
they owe nothing unless a flip is proposed.
